#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
konkretna.py — КОНКРЕТНА СХЕМА С РЕШЕНИЯ ЗА ГАСЕНЕ (чл. 7, ал. 4, т. 1 и Приложение № 3а от Указанията
Iз-2749/2010) за един вариант на плана: етажът е подложката от одобрения чертеж (scripts/cdr_import.py), а
хидрантите и сградата – от КАИС и базата с водоизточници (_shared/scripts/kais.py … --shema --voda), т.е.
същите данни като в ситуационната схема. Пожарът, разходът и броят на струйниците са от разчета по
методиката (sili-i-sredstva: sili.py … – неговият JSON). Скриптът само подрежда входа за scripts/shema.py:

    python3 scripts/konkretna.py --podlozhka etazh2.json --kais shema.json --pomeshtenie "Гардероб" \
        --blizo "Духов оркестър" --vhod "Зала" --pat "Фоайе" --hidrant 56722-099 --hidrant-etiket "С-125/4 ПХ" \
        --sili sili.json --etazh 2 --ogneustoychivost III --obekt "…" -o konkretna.json
    python3 scripts/shema.py konkretna.json -o Konkretna_shema_….png

Правилата: струйникът е винаги ПРЕД пожара – в коридора, пред вратата на помещението, насочен към нея,
никога в защрихованата площ; шланговите линии са плавни (shema.py ги заглажда); I ПА застава пред входа
откъм --vhod, II ПА – на хидранта и захранва I ПА; размерите на помещението се котират (б. „р“), а Fп, Iг
и Qг се изписват в него (б. „л“ – „н“). Без легенда; листът е с рамката и антетката (чл. 9, ал. 3–4).
"""
import argparse
import os
import json
import math
import sys


def bad(msg):
    sys.stderr.write("BAD_INPUT: " + msg + "\n")
    sys.exit(2)


def unit(v):
    n = math.hypot(*v)
    return (v[0] / n, v[1] / n) if n else (0.0, 0.0)


def add(p, v, k=1.0):
    return (p[0] + v[0] * k, p[1] + v[1] * k)


def merge(openings, gap=1.3):
    """The two masks of one door (its frame and its leaf) – one opening."""
    out = []
    for o in openings:
        for g in out:
            if math.dist((o["x"], o["y"]), (g["x"], g["y"])) < gap:
                break
        else:
            out.append(dict(o))
    return out


def num_bg(v):
    s = f"{v:.2f}".rstrip("0").rstrip(".") if isinstance(v, float) else str(v)
    return s.replace(".", ",")


def main():
    ap = argparse.ArgumentParser(description="Конкретна схема с решения за гасене (Приложение № 3а)")
    ap.add_argument("--podlozhka", required=True, help="JSON от cdr_import.py")
    ap.add_argument("--kais", required=True, help="shema.json от kais.py obekt --shema --voda")
    ap.add_argument("--pomeshtenie", required=True, help="помещението с пожара – името му в чертежа")
    ap.add_argument("--blizo", help="при две помещения с това име – онова до това помещение")
    ap.add_argument("--vhod", required=True, help="помещението, през което се влиза (I ПА застава отвън пред него)")
    ap.add_argument("--pat", default="", help="помещенията по пътя до пожара, със запетая (стълбище, фоайе …)")
    ap.add_argument("--hidrant", required=True, help="водоизточникът – voda_id от shema.json")
    ap.add_argument("--hidrant-etiket", help="надписът на хидранта (иначе – от базата)")
    ap.add_argument("--max-razstoyanie", type=float, default=12.0,
                    help="хидрант по-далеч от сградата се чертае на толкова метра от нея, в посоката си (m)")
    ap.add_argument("--sili", required=True, help="JSON от sili.py tvardi за този пожар")
    ap.add_argument("--etazh", required=True)
    ap.add_argument("--ogneustoychivost", required=True)
    ap.add_argument("--kategoriya", default="", help="категорията (класът) по пожарна опасност – в Приложение № 3б")
    ap.add_argument("--tablitsa-3b", help="JSON с полетата на Приложение № 3б за помещението (горимо натоварване, "
                                          "гасителни вещества, РВМ, други данни) – слива се с известното от разчета")
    ap.add_argument("--obekt", required=True, help="антетката – наименование, адрес, телефон")
    ap.add_argument("--sobstvenik", default="")
    ap.add_argument("--izgotvil", default="")
    ap.add_argument("--data", default="")
    ap.add_argument("--fail", default="")
    ap.add_argument("--ulitsi", default="", help="улиците, които да се виждат (по подразбиране – именуваните до 15 m "
                                                 "от сградата; за ориентиране – откъде идват колите), "
                                             "със запетая; заедно с тях – и тревните площи от КАИС/OpenStreetMap")
    ap.add_argument("--bez-evakuatsiya", action="store_true", help="без стрелките за евакуация (б. „с“)")
    ap.add_argument("-o", "--out", required=True)
    a = ap.parse_args()

    pod = json.load(open(a.podlozhka))
    kais = json.load(open(a.kais))
    # the scheme JSON of the object may be in another frame than the floor (e.g. the situational scheme, cut round
    #   the parcel): it is moved to the floor's frame by their origins in КС2005
    o_p, o_k = pod.get("_kais") or {}, kais.get("kais") or {}
    if o_p.get("x0") is not None and o_k.get("x0") is not None:
        dx, dy = o_k["x0"] - o_p["x0"], o_k["y0"] - o_p["y0"]
        if abs(dx) > 1e-6 or abs(dy) > 1e-6:
            kais = _move(kais, dx, dy)
    sili = json.load(open(a.sili))
    if not sili.get("ok"):
        bad("разчетът (sili.py) не е успешен")
    R = sili["rezultat"]
    rooms = {p["ime"]: p for p in pod["pomeshtenia"] if p["ime"]}
    same = [p for p in pod["pomeshtenia"] if p["ime"] == a.pomeshtenie]
    if not same:
        bad(f"помещението „{a.pomeshtenie}“ го няма в чертежа: {', '.join(sorted(rooms))}")
    if len(same) > 1:
        if not a.blizo or a.blizo not in rooms:
            bad(f"„{a.pomeshtenie}“ са {len(same)} – посочи --blizo")
        ref = rooms[a.blizo]["tsentar"]
        same.sort(key=lambda p: math.dist(p["tsentar"], ref))
    room = same[0]
    for n in [a.vhod] + [x.strip() for x in a.pat.split(",") if x.strip()]:
        if n not in rooms:
            bad(f"помещението „{n}“ го няма в чертежа")

    ang = pod["zavartane"]
    c, s = math.cos(math.radians(ang)), math.sin(math.radians(ang))
    rot = lambda p: (p[0] * c - p[1] * s, p[0] * s + p[1] * c)                 # noqa: E731
    unrot = lambda v: (v[0] * c + v[1] * s, -v[0] * s + v[1] * c)              # noqa: E731
    page_x, page_y = unrot((1, 0)), unrot((0, 1))      # the axes of the drawing as it is printed, in КАИС

    # the fire – the whole room (the area of the calculation), hatched; the box is along the printed axes
    rk = [rot(p) for p in room["kontur"]]
    w = max(p[0] for p in rk) - min(p[0] for p in rk)
    h = max(p[1] for p in rk) - min(p[1] for p in rk)
    cx, cy = room["tsentar"]
    pozhar = [{"x": cx - w / 2, "y": cy - h / 2, "w": round(w, 2), "h": round(h, 2), "etiket": ""}]

    # the door to the fire – an inner opening of the room, the one nearest the way in
    doors = merge([o for o in room["otvori"] if not o["vanshen"]])
    if not doors:
        bad(f"„{a.pomeshtenie}“ няма врата в чертежа")
    path = [rooms[x.strip()]["tsentar"] for x in a.pat.split(",") if x.strip()]
    toward = path[-1] if path else rooms[a.vhod]["tsentar"]
    door = min(doors, key=lambda o: math.dist((o["x"], o["y"]), toward))
    dpt = (door["x"], door["y"])
    out_v = unit((dpt[0] - cx, dpt[1] - cy))            # out of the room, through the door

    # the forces: I ПА in front of the entrance, II ПА on the hydrant
    hyd = next((v for v in kais.get("vodoiztochnitsi", []) if v.get("voda_id") == a.hidrant), None)
    if not hyd:
        bad(f"водоизточникът {a.hidrant} го няма в {a.kais} (kais.py … --voda)")
    outline = next((b["kontur"] for b in kais["sgradi"] if not b.get("sasedna")), None)
    vc = rooms[a.vhod]["tsentar"]
    bc0 = (sum(p[0] for p in outline) / len(outline), sum(p[1] for p in outline) / len(outline))
    face = unit((vc[0] - bc0[0], vc[1] - bc0[1]))        # the entrance room faces out of the building
    foot = vc
    face = max((page_x, page_y, (-page_x[0], -page_x[1]), (-page_y[0], -page_y[1])),   # square to the sheet
               key=lambda v: v[0] * face[0] + v[1] * face[1])
    from shapely.geometry import LineString as _LS
    hit = _LS(outline + outline[:1]).intersection(_LS([vc, add(vc, face, 80)]))        # in front of the room
    if not hit.is_empty:
        pts_ = [hit] if hit.geom_type == "Point" else list(getattr(hit, "geoms", []))
        if pts_:
            q = min(pts_, key=lambda g: math.dist(vc, (g.x, g.y)))
            foot = (q.x, q.y)
    entrance = add(foot, face, 1.5)
    pa1 = add(foot, face, 6.5)
    hp_true = (hyd["x"], hyd["y"])
    # a hydrant far from the building is drawn nearer, in its true direction, and its line carries its true length
    #   (б. „п“) – as on the approved schemes, so that the floor keeps a scale in which it can be read
    from shapely.geometry import LineString as _LS2, Point as _Pt
    ring_ = _LS2(outline + outline[:1])
    near_b = ring_.interpolate(ring_.project(_Pt(hp_true)))
    d_true = ring_.distance(_Pt(hp_true))
    if d_true > a.max_razstoyanie:
        hp = add((near_b.x, near_b.y), unit((hp_true[0] - near_b.x, hp_true[1] - near_b.y)), a.max_razstoyanie)
    else:
        hp = hp_true
    to_b = unit((pa1[0] - hp[0], pa1[1] - hp[1]))
    pa2 = add(hp, to_b, 4.5)
    along = math.degrees(math.atan2(face[1], face[0]))                   # square to the front, as on the approved schemes
    trucks = [{"id": "I ПА", "x": pa1[0], "y": pa1[1], "ugal": round(along, 1), "vid": "pa"},     # shema.py turns
              {"id": "II ПА", "x": pa2[0], "y": pa2[1], "ugal": round(along, 1), "vid": "pa"}]    #   them with the sheet

    # the hose lines – smooth (shema.py rounds them); the nozzle in front of the fire, at the door, never in it
    mid = add(((pa2[0] + pa1[0]) / 2, (pa2[1] + pa1[1]) / 2), unit((-(pa1[1] - pa2[1]), pa1[0] - pa2[0])), 4.0)
    lines = [{"tochki": [list(hp), list(add(hp, to_b, 2.5))], "vid": "glavna"},
             {"tochki": [list(add(pa2, to_b, 1.5)), list(mid), list(add(pa1, (-face[0], -face[1]), -1.5))], "vid": "glavna"}]
    n_g = int(R.get("struinitsi_za_gasene") or 1)
    side = unit((-out_v[1], out_v[0]))
    for i in range(n_g):
        off = (i - (n_g - 1) / 2) * 0.9
        pts = [add(pa1, face, -1.0), entrance, foot, vc] + path
        front = add(add(dpt, out_v, 3.6), side, off * 0.5)          # straight at the door, from the corridor:
        tip = add(add(dpt, out_v, 3.2), side, off * 0.5)            #   shema.py keeps the nozzle's head out of the fire
        lines.append({"tochki": [list(add(p, side, off * 0.6)) for p in pts] + [list(front), list(tip)],
                      "vid": "malka", "struinik": "malak"})
    # the lengths of the lines (б. „п“): the main one from the hydrant to I ПА – along the ground, the working ones –
    #   from I ПА to the nozzle, with a floor height of 3.5 m for each floor above the ground
    def plen(pts_):
        return sum(math.dist(p, q) for p, q in zip(pts_, pts_[1:]))
    L_main = math.dist(hp_true, pa1) * 1.1
    lines[1]["etiket"] = f"{num_bg(round(L_main))} m – {math.ceil(L_main / 20)} шл."
    for ln in lines[2:]:
        L_w = plen(ln["tochki"]) + 3.5 * max(0, int(a.etazh) - 1) + 3.0
        ln["_L"] = L_w
    if len(lines) > 2:
        L_w = max(ln.pop("_L") for ln in lines[2:])
        lines[2]["etiket"] = f"{num_bg(round(L_w))} m – {math.ceil(L_w / 20)} шл."
        lines[2]["etiket_pri"] = "nachalo"
    lines[1]["etiket_pri"] = "sreda"
    n_z = int(R.get("struinitsi_za_zashtita") or 0)
    for i in range(n_z):                                # protection – beside, along the corridor
        pts = [add(pa1, face, -1.0), entrance, foot, vc] + path
        front = add(add(dpt, side, 3.0 * (1 if i % 2 == 0 else -1)), out_v, 1.8)
        lines.append({"tochki": [list(p) for p in pts] + [list(front), list(add(front, side, 1.0 * (1 if i % 2 == 0 else -1)))],
                      "vid": "malka", "struinik": "malak"})

    # the way out (б. „с“) – from the door of the room along the corridor to the entrance and out, beside the
    #   hose lines (on the other side), green; the second exit, when the drawing does not show it, is not guessed
    ev = [add(dpt, out_v, 1.6)] + list(reversed(path)) + [vc, foot, add(foot, face, 3.5)]
    ev = [list(add(p, side, -1.3)) for p in ev]
    evakuatsiya = [] if a.bez_evakuatsiya else [{"tochki": [[round(x, 2), round(y, 2)] for x, y in ev]}]

    # the texts of the fire – in the room, on white, as on the approved schemes
    ime = a.pomeshtenie
    sizes = sorted(t.get("razmer", 1.0) for t in pod["tekst"])
    fs_room = sizes[len(sizes) // 2] if sizes else 1.0
    lab = [(ime, None), (f"гр.огн. {a.ogneustoychivost}, {a.etazh} ет.", None),
           (f"Fп = {num_bg(R['plosht_na_pozhara_m2'])} m²", "cherven"),
           (f"Iг = {num_bg(sili['vhodni']['i'].split()[0].replace('.', ','))} l/s.m²", None),
           (f"Qг = {num_bg(R['razhod_za_gasene_l_s'])} l/s", None)]
    q_z = R.get("razhod_obshto_l_s", 0) - R.get("razhod_za_gasene_l_s", 0)
    if q_z > 0:                                          # the protection, when the calculation has it (б. „н“)
        lab.append((f"Qз = {num_bg(round(q_z, 2))} l/s", None))
    tekst = [t for t in pod["tekst"] if not _inside(room["kontur"], (t["x"], t["y"]))]
    tekst.append({"x": round(cx, 2), "y": round(cy, 2), "tekst": "\n".join(t_ for t_, _ in lab), "kray": "sreda",
                  "fon": True, "razmer": fs_room})
    hl = add(add(hp, page_x, -4.0), page_y, 3.4)        # beside the hydrant, inside the drawing
    tekst.append({"x": round(hl[0], 2), "y": round(hl[1], 2), "tekst": a.hidrant_etiket or hyd.get("etiket", ""),
                  "kray": "sreda", "razmer": fs_room})

    # the sizes of the room (б. „р“) – along the printed axes
    x0, x1 = min(p[0] for p in rk), max(p[0] for p in rk)
    y0, y1 = min(p[1] for p in rk), max(p[1] for p in rk)
    back = lambda x, y: (x * c + y * s, -x * s + y * c)                          # noqa: E731
    big, small = room["razmeri_m"]                      # to the middle of the walls – the same as Fп
    dw, dh = (big, small) if w >= h else (small, big)
    dims = [{"ot": list(back(x0, y0 - 1.2)), "do": list(back(x1, y0 - 1.2)), "etiket": num_bg(dw)},
            {"ot": list(back(x0 - 1.2, y0)), "do": list(back(x0 - 1.2, y1)), "etiket": num_bg(dh)}]

    # the situation round the building – the same data as in the situational scheme (kais.py: КАИС and OSM):
    #   the streets asked for and the grass, so that one sees where everything is and where the vehicles come from
    names = [n.strip() for n in a.ulitsi.split(",") if n.strip()]
    if not names:                                        # not given: the named streets next to the building (≤ 15 m)
        from shapely.geometry import LineString as _Ls, Polygon as _Pg0
        body = _Pg0(outline)
        for u in kais.get("ulitsi", []):
            nm = u.get("ime") or u.get("ime_ulitsa")
            pts_ = u.get("kontur") or u.get("tochki") or []
            if nm and not u.get("pateka") and len(pts_) >= 2 and nm not in names:
                geo = _Pg0(pts_) if u.get("kontur") and len(pts_) >= 3 else _Ls(pts_)
                if geo.buffer(0).distance(body) <= 15.0:
                    names.append(nm)
    ulitsi = [u for u in kais.get("ulitsi", []) if (u.get("ime") or u.get("ime_ulitsa")) and
              any(n in (u.get("ime") or u.get("ime_ulitsa") or "") for n in names)]
    if names:                                            # the alleys round the building and through the grass
        ulitsi += [u for u in kais.get("ulitsi", []) if u.get("pateka")]
    teren_tochki = []
    bc = (sum(p[0] for p in outline) / len(outline), sum(p[1] for p in outline) / len(outline))
    for u in [u for u in ulitsi if not u.get("pateka")]:  # the near edge of the street, and a little beyond it
        pts_ = u.get("kontur") or u.get("tochki") or []
        if pts_:
            q = min(pts_, key=lambda p: math.dist(p, bc))
            out_ = unit((q[0] - bc[0], q[1] - bc[1]))
            teren_tochki += [q, add(q, out_, 22.0)]                 # both edges of the street
            u = dict(u)
            u["ime_pos"] = list(add(q, out_, 6.0))                  # its name – in the street, where it is seen
            ulitsi[ulitsi.index(next(x for x in ulitsi if x is not u and x.get("kontur") == u.get("kontur")))] = u
    from shapely.geometry import Polygon as _Pg
    trevni = []
    if names:                                            # the grass – not under the buildings
        from shapely.geometry import Polygon as _Pg
        from shapely.ops import unary_union as _uu
        bld = _uu([_Pg(b["kontur"]).buffer(0.3) for b in kais["sgradi"] if not b.get("sasedna")])
        for t in kais.get("trevni", []):
            g = _Pg(t["kontur"], [h for h in (t.get("otvori") or []) if len(h) >= 3]).buffer(0).difference(bld)
            for part in getattr(g, "geoms", [g]):
                if part.geom_type == "Polygon" and part.area > 4:
                    trevni.append({"kontur": [[round(x, 2), round(y, 2)] for x, y in part.exterior.coords][:-1],
                                   "otvori": [[[round(x, 2), round(y, 2)] for x, y in h.coords][:-1]
                                              for h in part.interiors]})

    flag = add((cx, cy), page_x, -w / 4)
    d = {"podlozhka": pod["podlozhka"], "tekst": tekst, "obekti": pod.get("obekti", []),
         "pozhar": pozhar, "ognishte": [{"x": round(flag[0], 2), "y": round(flag[1], 2)}],
         "razstoyaniya": dims, "avtomobili": trucks, "evakuatsiya": evakuatsiya,
         "vodoiztochnitsi": [{"vid": hyd["vid"], "x": round(hp[0], 2), "y": round(hp[1], 2), "etiket": ""}], "linii": lines,
         "ulitsi": ulitsi, "trevni": trevni, "teren_tochki": teren_tochki,
         "sgradi": [{"kontur": b["kontur"], "etiket": "", "etazhnost": b.get("etazhnost", ""), "kratko": True,
                     "razmeri": False} for b in kais["sgradi"][1:] if not b.get("sasedna")
                    and _Pg(b["kontur"]).distance(_Pg(outline)) < 8.0] if names else [],      # the annexes built on
         "zavartane": ang, "pole_m": 2, "cvetna": True, "legenda": False, "shlang_m": 20,
         "list": {"nomer": "", "obekt": a.obekt, "sobstvenik": a.sobstvenik, "izgotvil": a.izgotvil, "data": a.data,
                  "fail": a.fail, "naslov": f"Конкретна схема за гасене на пожар в {ime.lower()} на {a.etazh} ет."},
         "tablitsa_3b": tablitsa_3b(a, sili),
         "_vrata": [round(dpt[0], 2), round(dpt[1], 2)], "_pomeshtenie": {k: room[k] for k in ("ime", "plosht_m2", "razmeri_m")}}
    json.dump(d, open(a.out, "w"), ensure_ascii=False, indent=1)
    print(json.dumps({"output": a.out, "pomeshtenie": d["_pomeshtenie"], "vrata": d["_vrata"],
                      "do_hidranta_m": round(d_true, 1), "linii": [ln.get("etiket") for ln in lines if ln.get("etiket")],
                      "struinitsi": n_g + n_z}, ensure_ascii=False))


def tablitsa_3b(a, sili):
    """Приложение № 3б for the room – what is known from the calculation and the arguments, merged with the
    rest given in --tablitsa-3b (one row – the main fire load; more rows – from the given file)."""
    vl = str((sili.get("vhodni") or {}).get("vl") or "").split(" ")[0].replace(".", ",")
    row = {"kategoriya": a.kategoriya, "ogneustoychivost": a.ogneustoychivost, "vl_m_min": vl}
    extra = json.load(open(a.tablitsa_3b, encoding="utf-8")) if a.tablitsa_3b else {}
    rows = extra.get("redove") or [{}]
    rows = [{**row, **{k: v for k, v in rows[0].items() if v not in (None, "")}}] + list(rows[1:])
    return {"redove": rows, "prazni_redove": extra.get("prazni_redove", 4)}


def _move(o, dx, dy, key=None):
    """Every point of a scheme JSON moved by (dx, dy) – the outlines, the lines and the x/y of the symbols."""
    if isinstance(o, dict):
        r = {}
        for k, v in o.items():
            if k in ("kais", "teren", "list", "tablitsa", "w", "h", "shirina", "ugal"):
                r[k] = v
            elif k == "x" and isinstance(v, (int, float)):
                r[k] = v + dx
            elif k == "y" and isinstance(v, (int, float)):
                r[k] = v + dy
            else:
                r[k] = _move(v, dx, dy, k)
        return r
    if isinstance(o, list):
        if len(o) == 2 and all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in o):
            return [o[0] + dx, o[1] + dy]
        return [_move(v, dx, dy, key) for v in o]
    return o


def _foot(p, a, b):
    ax, ay = b[0] - a[0], b[1] - a[1]
    t = max(0.0, min(1.0, ((p[0] - a[0]) * ax + (p[1] - a[1]) * ay) / (ax * ax + ay * ay)))
    return (a[0] + t * ax, a[1] + t * ay)


def _dist_seg(p, a, b):
    return math.dist(p, _foot(p, a, b))


def _inside(poly, p):
    x, y, inside = p[0], p[1], False
    for (x1, y1), (x2, y2) in zip(poly, poly[1:] + poly[:1]):
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            inside = not inside
    return inside


if __name__ == "__main__":
    main()
