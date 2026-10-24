#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
kais.py — кадастралната карта на АГКК (КАИС, kais.cadastre.bg) за ситуационните схеми и плановете за
пожарогасене: поземленият имот и сградите в него с точните им контури (КС2005, в метри), предназначение,
брой етажи и застроена площ, и кадастралната карта около тях като фон.

Данните идват от публичната карта на КАИС (без вход, без собственици) през n8n с личния ключ – КАИС не се
пита от тук. Без ключ скриптът спира с `NO_KEY`; тогава данните (без фона) идват от инструмента `kais`
на конектора Fire Service.

    python3 _shared/scripts/kais.py obekt --lat 43.41257 --lon 24.65047 -o kais.json
    python3 _shared/scripts/kais.py obekt --link "https://www.google.com/maps/place/…/@43.41257,24.65047,17z" -o kais.json
    python3 _shared/scripts/kais.py obekt --id 56722.27.446 -o kais.json --shema shema.json [--voda] [--radius 40]
    python3 _shared/scripts/kais.py tarsi "Плевен ул. Васил Левски 1"

obekt – имотът в точката (или по идентификатора) и всички сгради в него. Записва:
  kais.json         – отговорът: "imot", "sgradi" (контури в КС2005), "ulitsi" (OpenStreetMap), "ramka";
  --shema ФАЙЛ      – готово начало на JSON за scripts/shema.py на скила shemi (и situacionna.py), в знаците и
                      цветовете на Приложение № 6 и чл. 9, ал. 9: терен около имота, сградите като "kontur" в
                      метри с предназначението и етажността, границата на имота ("imot" – щрих-пунктир с
                      идентификатора, в легендата), улиците с имената им (от OpenStreetMap) и "kais" (началото в
                      КС2005). Допълва се: входове, ограда, водопровод, ел. табло, категория …;
  --voda            – и точните водоизточници (проверени на място или от ВиК) в терена – а ако там няма, най-
                      близкият, като теренът се разширява до него – с разстоянието от сградата до него
                      (от voda.py – трябва личен ключ);
  --radius N        – колко метра около имота да обхване теренът (30–300, по подразбиране 40);
  --bez-granitsa    – без границата на поземления имот;
  --fon             – и кадастралната карта около имота като блед фон (kais_fon.png до kais.json) – за
                      работа и сверка; не е по Приложение № 2а, затова не е по подразбиране.
tarsi – какво намира търсачката на картата по идентификатор или адрес. В промишлените зони много имоти са
записани само с местността (м. „…“), без улица и номер – тогава търси по точка.

Отпечатва JSON с кратко резюме: имотът, сградите (предназначение, етажи, застроена площ, размери),
файловете и бележките.

Грешки (на stderr, код ≠ 0):
    NO_KEY / KEY_REJECTED   — няма личен ключ / n8n не го приема
    BAD_INPUT: …            — неверни координати или идентификатор
    NOT_FOUND: …            — в точката няма имот / идентификаторът не е в КАИС
    KAIS_UNAVAILABLE: …     — КАИС не отговаря или е сменил картата си
"""
import argparse
import base64
import datetime
import json
import math
import os
import re
import subprocess
import sys
import urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import api_config  # noqa: E402

CONFIG_FIELD = "kais_url"
EXACT = ("проверена", "вик")       # the water sources whose coordinates are exact (voda.py)
SMALL_M = 8.0                     # a building narrower than this is drawn without a name and dimensions


# ── КС2005 (EPSG:7801) ⇄ WGS84 – Lambert conformal conic, 2SP, GRS80 (the same as the n8n node) ────────────────
_A, _F = 6378137.0, 1 / 298.257222101
_E = math.sqrt(2 * _F - _F * _F)
_D = math.pi / 180
_P1, _P2, _P0, _L0 = 42 * _D, (43 + 20 / 60) * _D, 42.66787568333333 * _D, 25.5 * _D
_X0, _Y0 = 500000.0, 4725824.3591


def _m(p):
    return math.cos(p) / math.sqrt(1 - _E * _E * math.sin(p) ** 2)


def _t(p):
    return math.tan(math.pi / 4 - p / 2) / ((1 - _E * math.sin(p)) / (1 + _E * math.sin(p))) ** (_E / 2)


_N = (math.log(_m(_P1)) - math.log(_m(_P2))) / (math.log(_t(_P1)) - math.log(_t(_P2)))
_FF = _m(_P1) / (_N * _t(_P1) ** _N)
_R0 = _A * _FF * _t(_P0) ** _N


def wgs_to_kc(lat, lon):
    """WGS84 (ETRS89) → КС2005 (x east, y north), metres."""
    r = _A * _FF * _t(lat * _D) ** _N
    th = _N * (lon * _D - _L0)
    return _X0 + r * math.sin(th), _Y0 + _R0 - r * math.cos(th)


def kc_to_wgs(x, y):
    dx, dy = x - _X0, _R0 - (y - _Y0)
    r = math.copysign(math.hypot(dx, dy), _N)
    tt = (r / (_A * _FF)) ** (1 / _N)
    th = math.atan2(dx, dy)
    p = math.pi / 2 - 2 * math.atan(tt)
    for _ in range(10):
        p = math.pi / 2 - 2 * math.atan(tt * ((1 - _E * math.sin(p)) / (1 + _E * math.sin(p))) ** (_E / 2))
    return p / _D, (th / _N + _L0) / _D


def fail(code, msg, rc=2):
    sys.stderr.write(f"{code}: {msg}\n")
    sys.exit(rc)


def call(body):
    cfg = api_config.load()
    if not cfg.get(CONFIG_FIELD):
        fail("N8N_UNAVAILABLE", f"в incident_api.json няма {CONFIG_FIELD}", 3)
    try:
        return api_config.post(CONFIG_FIELD, body, timeout=120)
    except urllib.error.HTTPError as e:
        try:
            msg = json.loads(e.read()).get("error", "")
        except ValueError:
            msg = ""
        msg = msg.split(" [line")[0] or f"HTTP {e.code}"
        code, _, rest = msg.partition(": ")
        if code in ("BAD_REQUEST", "NOT_FOUND", "KAIS_UNAVAILABLE"):
            fail("BAD_INPUT" if code == "BAD_REQUEST" else code, rest, 2 if code != "KAIS_UNAVAILABLE" else 3)
        fail("N8N_ERROR", msg, 3)
    except (urllib.error.URLError, OSError) as e:
        fail("N8N_UNAVAILABLE", f"n8n не отговаря: {e}", 3)


# ── geometry helpers ─────────────────────────────────────────────────────────────────────────────────────────
def area(ring):
    return abs(sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(ring, ring[1:] + ring[:1]))) / 2


def dims(ring):
    """Length and width of the smallest rectangle around the outline, in any direction (the walls' lengths)."""
    best = None
    pts = ring[:-1] if ring and ring[0] == ring[-1] else ring
    for a, b in zip(pts, pts[1:] + pts[:1]):
        ang = math.atan2(b[1] - a[1], b[0] - a[0])
        c, s = math.cos(ang), math.sin(ang)
        us = [p[0] * c + p[1] * s for p in pts]
        vs = [-p[0] * s + p[1] * c for p in pts]
        w, h = max(us) - min(us), max(vs) - min(vs)
        if best is None or w * h < best[0]:
            best = (w * h, max(w, h), min(w, h))
    return (round(best[1], 1), round(best[2], 1)) if best else (None, None)


def length(pts):
    return sum(math.dist(a, b) for a, b in zip(pts, pts[1:]))


def clip_polyline(pts, x0, y0, x1, y1):
    """The pieces of a polyline inside the rectangle (Liang–Barsky on every segment)."""
    pieces, cur = [], []
    for a, b in zip(pts, pts[1:]):
        dx, dy = b[0] - a[0], b[1] - a[1]
        t0, t1, ok = 0.0, 1.0, True
        for p, q in ((-dx, a[0] - x0), (dx, x1 - a[0]), (-dy, a[1] - y0), (dy, y1 - a[1])):
            if p == 0:
                if q < 0:
                    ok = False
                    break
                continue
            t = q / p
            if p < 0:
                t0 = max(t0, t)
            else:
                t1 = min(t1, t)
        if not ok or t0 > t1:
            if cur:
                pieces.append(cur)
                cur = []
            continue
        pa = (a[0] + t0 * dx, a[1] + t0 * dy)
        pb = (a[0] + t1 * dx, a[1] + t1 * dy)
        if not cur:
            cur = [pa]
        elif math.dist(cur[-1], pa) > 1e-6:
            pieces.append(cur)
            cur = [pa]
        cur.append(pb)
        if t1 < 1.0:
            pieces.append(cur)
            cur = []
    if cur:
        pieces.append(cur)
    return pieces


def street_name(name):
    """„бул. Русе“ → „бул. „Русе““ – the plugin's typography for street names; other names stay as they are."""
    m = re.match(r"^(ул\.|бул\.|пл\.|ж\.к\.|кв\.)\s*(.+)$", name.strip())
    if not m or m.group(2).startswith("„"):
        return name.strip()
    core = m.group(2).strip('"“”')
    return m.group(1) + " „" + core + "“"


def local(ring, x0, y0):
    pts = [[round(p[0] - x0, 2), round(p[1] - y0, 2)] for p in ring]
    if len(pts) > 1 and pts[0] == pts[-1]:
        pts = pts[:-1]
    return pts


def label(s):
    """„Промишлена сграда“ – the purpose as КАИС gives it, first letter capital."""
    p = (s.get("predn") or "Сграда").strip()
    return p[:1].upper() + p[1:]


# ── commands ─────────────────────────────────────────────────────────────────────────────────────────────────
def point_of(a):
    if a.link:
        import marshrut  # noqa: E402  (follows short links, reads !3d…!4d…, q=…, @lat,lon)
        return marshrut.from_link(a.link)
    if a.lat is not None and a.lon is not None:
        return a.lat, a.lon
    return None


def water(lat, lon, radius_m):
    """The exact water sources within radius_m of the point – via voda.py (personal key)."""
    script = os.path.join(HERE, "voda.py")
    r = subprocess.run([sys.executable, script, "blizo", "--lat", f"{lat:.7f}", "--lon", f"{lon:.7f}", "--broi", "25",
                        "--radius-m", str(int(radius_m)), "--json"], capture_output=True, text=True, timeout=180)
    if r.returncode != 0:
        return None, (r.stderr or r.stdout).strip().splitlines()[-1:] or ["voda.py не отговори"]
    try:
        return json.loads(r.stdout).get("vodoiztochnitsi", []), []
    except ValueError:
        return None, ["voda.py върна неочакван отговор"]


def cmd_obekt(a):
    body = {"action": "obekt", "fon": bool(a.fon), "radius_m": a.radius}
    p = point_of(a)
    if a.id:
        body["id"] = a.id.strip()
    elif p:
        body["lat"], body["lon"] = p
    else:
        fail("BAD_INPUT", "дай --id, или --lat и --lon, или --link")
    res = call(body)
    out = os.path.abspath(a.out)
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    fon_png = None
    fon = res.pop("fon", None)
    if fon and fon.get("png_base64") and a.fon:
        fon_png = os.path.splitext(out)[0] + "_fon.png"
        with open(fon_png, "wb") as f:
            f.write(base64.b64decode(fon["png_base64"]))
        res["fon"] = {k: v for k, v in fon.items() if k != "png_base64"} | {"png": fon_png}
    res["data_na_spravkata"] = datetime.date.today().strftime("%d.%m.%Y")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)

    imot, sgradi = res["imot"], res.get("sgradi") or []
    notes = list(res.get("zabelezhki") or [])
    summary = {
        "imot": {k: imot.get(k) for k in ("id", "adres", "ntp", "plosht_m2", "teritoriya", "sobstvenost") if imot.get(k)},
        "sgradi": [], "kais_json": out, "fon": fon_png,
    }
    for s in sgradi:
        d = dims(s.get("kontur") or [])
        summary["sgradi"].append({"id": s["id"], "predn": s.get("predn"), "etazhi": s.get("etazhi"),
                                  "zastroena_m2": s.get("zastroena_m2"), "razmeri_m": list(d) if d[0] else None})

    if a.shema:
        fx0, fy0, fx1, fy1 = res["ramka"]["bbox"]          # the picture: a square around the parcel
        ring = imot.get("kontur") or []
        r = res["ramka"].get("radius_m", a.radius)
        # the terrain: the parcel's own extent plus the radius – a rectangle, so the sheet's scale stays large
        bx0 = math.floor(min(p[0] for p in ring) - r) if ring else fx0
        by0 = math.floor(min(p[1] for p in ring) - r) if ring else fy0
        bx1 = math.ceil(max(p[0] for p in ring) + r) if ring else fx1
        by1 = math.ceil(max(p[1] for p in ring) + r) if ring else fy1

        # the water sources (exact ones only): those in the terrain, and the nearest one even outside it – the
        # scheme must show where the water is (чл. 7, ал. 3, т. 1, б. „в“ и „г“), so the terrain grows to it
        hydrants = []
        if a.voda:
            clat, clon = kc_to_wgs((bx0 + bx1) / 2, (by0 + by1) / 2)
            rows, errs = water(clat, clon, max(400.0, math.hypot(bx1 - bx0, by1 - by0) / 2))
            if rows is None:
                notes.append("Водоизточниците не се взеха: " + "; ".join(errs))
            else:
                exact = []
                for row in rows:
                    if row.get("tochnost") in EXACT:
                        x, y = wgs_to_kc(float(row["lat"]), float(row["lon"]))
                        exact.append((x, y, row))
                inside = [h for h in exact if bx0 <= h[0] <= bx1 and by0 <= h[1] <= by1]
                hydrants = inside or exact[:1]
                for x, y, _ in hydrants:
                    bx0, by0 = min(bx0, math.floor(x - 10)), min(by0, math.floor(y - 10))
                    bx1, by1 = max(bx1, math.ceil(x + 10)), max(by1, math.ceil(y + 10))
                if not exact:
                    notes.append("Няма водоизточници с точни координати до 400 m – виж vodoiztochnitsi за по-далечните.")
                elif not inside:
                    notes.append(f"В имота и около него няма хидрант – начертан е най-близкият ({round(exact[0][2].get('razstoyanie_m', 0))} m "
                                 "по права линия), теренът е разширен до него.")
        w, h = bx1 - bx0, by1 - by0
        sh = {
            "teren": [w, h],
            "kais": {"x0": bx0, "y0": by0, "imot": imot["id"], "data": res["data_na_spravkata"]},
            "sgradi": [],
        }
        if not a.bez_granitsa:
            sh["imot"] = {"kontur": local(ring, bx0, by0), "etiket": f"ПИ {imot['id']}"}
        if fon_png and a.fon:
            sh["fon"] = {"png": fon_png, "ramka": [fx0 - bx0, fy0 - by0, fx1 - bx0, fy1 - by0]}
        for s in sgradi:
            if not s.get("kontur"):
                continue
            b = {"kontur": local(s["kontur"], bx0, by0), "etiket": label(s), "kais_id": s["id"]}
            if (dims(s["kontur"])[1] or 0) < SMALL_M:      # an annex: no name and no dimension lines over its neighbour
                b["etiket"], b["razmeri"] = "", False
            if s.get("etazhi"):
                b["etazhnost"] = f"{s['etazhi']} ет."
            sh["sgradi"].append(b)
        if any(s.get("etazhi") for s in sgradi):
            notes.append("Етажността е „брой етажи“ от КАИС (надземните); сутерен, тавански етаж, категорията и "
                         "огнеустойчивостта не са в кадастъра – провери ги на място или в документацията на обекта.")

        # the streets (OpenStreetMap, from n8n): cut to the terrain, the name once per street – on its longest piece
        streets = []
        for u in res.get("ulitsi") or []:
            for piece in clip_polyline(u.get("tochki") or [], bx0, by0, bx1, by1):
                if len(piece) > 1 and length(piece) > 3:
                    streets.append({"tochki": [[round(x - bx0, 1), round(y - by0, 1)] for x, y in piece],
                                    "shirina": u.get("shirina") or 6, "ime": street_name(u.get("ime") or ""), "_len": length(piece)})
        for name in {st["ime"] for st in streets if st["ime"]}:
            same = [st for st in streets if st["ime"] == name]
            longest = max(same, key=lambda st: st["_len"])
            for st in same:
                if st is not longest:
                    st["ime"] = ""
        for st in streets:
            st.pop("_len")
        if streets:
            sh["ulitsi"] = streets
            summary["ulitsi"] = sorted({st["ime"] for st in streets if st["ime"]}) or ["(без имена)"]
            notes.append("Улиците са от OpenStreetMap – осовите линии са приблизителни, ширината е по вида на пътя; "
                         "провери имената и входовете на място.")
        elif "ulitsi" in res:
            notes.append("В OpenStreetMap няма улици около обекта – начертай ги на ръка.")

        if hydrants:
            sh["vodoiztochnitsi"] = []
            for x, y, row in hydrants:
                vid = ("nadzemen_hidrant" if row.get("tip") == "надземен" else "hidrant") if row.get("vid") == "хидрант" else (
                    "vodoem" if row.get("vid") == "водоем" else "hidrant")
                sh["vodoiztochnitsi"].append({"vid": vid, "x": round(x - bx0, 1), "y": round(y - by0, 1),
                                              "etiket": "ПХ " + row["diametar"] if row.get("diametar") else "ПХ",
                                              "voda_id": row.get("id")})
            # the distance from the nearest corner of a building to the nearest water source (б. „а“)
            corners = [(p[0] - bx0, p[1] - by0) for s in sgradi for p in (s.get("kontur") or [])]
            if corners:
                hx, hy = sh["vodoiztochnitsi"][0]["x"], sh["vodoiztochnitsi"][0]["y"]
                c = min(corners, key=lambda p: math.dist(p, (hx, hy)))
                sh["razstoyaniya"] = [{"ot": [round(c[0], 1), round(c[1], 1)], "do": [hx, hy]}]
                summary["do_vodoiztochnika_m"] = round(math.dist(c, (hx, hy)))
            summary["vodoiztochnitsi"] = len(hydrants)
        with open(a.shema, "w", encoding="utf-8") as f:
            json.dump(sh, f, ensure_ascii=False, indent=1)
        summary["shema"] = os.path.abspath(a.shema)
        summary["teren_m"] = [w, h]
    summary["zaiavki_kais"] = res.get("zaiavki_kais")
    summary["iztochnik"] = res.get("istochnik")
    if notes:
        summary["zabelezhki"] = notes
    print(json.dumps(summary, ensure_ascii=False, indent=1))


def cmd_tarsi(a):
    res = call({"action": "tarsi", "tekst": a.tekst})
    print(json.dumps(res, ensure_ascii=False, indent=1))


def main():
    ap = argparse.ArgumentParser(description="Кадастралната карта (КАИС) за ситуационни схеми и планове")
    sub = ap.add_subparsers(dest="cmd", required=True)
    o = sub.add_parser("obekt", help="имотът и сградите му – по точка или идентификатор")
    o.add_argument("--id", help="кадастрален идентификатор: 56722.27.446 (имот) или 56722.27.446.1 (сграда)")
    o.add_argument("--lat", type=float)
    o.add_argument("--lon", type=float)
    o.add_argument("--link", help="линк от Google Maps (и кратък) или „ширина,дължина“")
    o.add_argument("--radius", type=int, default=40, help="метри около имота (30–300, по подразбиране 40)")
    o.add_argument("--fon", action="store_true",
                   help="и картинката на кадастралната карта като блед фон (не по Приложение № 2а – за работа и сверка)")
    o.add_argument("--bez-granitsa", action="store_true", help="с --shema: без границата на поземления имот")
    o.add_argument("-o", "--out", default="kais.json", help="изходен JSON (фонът – до него, *_fon.png)")
    o.add_argument("--shema", help="и начало на JSON за shema.py / situacionna.py")
    o.add_argument("--voda", action="store_true", help="с --shema: и точните водоизточници в рамката")
    t = sub.add_parser("tarsi", help="търсачката на картата")
    t.add_argument("tekst")
    a = ap.parse_args()
    if a.cmd == "obekt" and a.link and "," in a.link and "://" not in a.link:
        try:
            a.lat, a.lon = (float(v) for v in a.link.split(",", 1))
            a.link = None
        except ValueError:
            fail("BAD_INPUT", f"„{a.link}“ не е „ширина,дължина“")
    {"obekt": cmd_obekt, "tarsi": cmd_tarsi}[a.cmd](a)


if __name__ == "__main__":
    main()
