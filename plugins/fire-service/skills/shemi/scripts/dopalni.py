#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
dopalni.py — попълва в JSON-а на ситуационната схема всичко, което не се пита (references/formulyar.md,
„Какво не се пита“; references/pravila.md, „Категория и огнеустойчивост“, „Когато данни липсват“), и връща
списък „прието“ – какво е взето и откъде. Пуска се преди situacionna.py: с личен ключ – от Claude, с конектора –
от сървъра (fire-render) при всяко chertai. Така въпросите след формуляра отпадат и на безплатния план.

    python3 scripts/dopalni.py situacionna.json --kais kais.json      # записва JSON-а на място

Попълва само празното – каквото потребителят или Claude вече са дали, не се пипа; пускането отново не добавя нищо
второ път:
  - "obekt_gps" – центърът на имота (КАИС, КС2005 → WGS84): от него situacionna.py смята разстоянието и времето;
  - категорията (подкласа) и степента на огнеустойчивост на главната сграда – подкласът по името на обекта или
    предназначението в КАИС (Наредба № Iз-1971, табл. 1), степента – най-ниската, която табл. 4 допуска за етажите и
    застроената площ (references/ogneustoychivost.json); клас Ф5 (по дейността, табл. 2) – не, казва се в „prieto“;
  - входа за колите – при точката от ортофотото (отговорът „portali“, номерът); без номер – само когато имотът опира
    в улицата от „vhod_kola“ (иначе не се гадае, а се казва в „ne_e_popalneno“);
  - главното ел. табло („Ел.“) – в главната сграда, откъм входа за колите (предполагаемо);
  - собственика в антетката – видът собственост от КАИС, докато не се намери точното наименование;
  - табличната част – горимото натоварване по вида обект (БДС EN 1991-1-2, Прил. E), ПГИ и газа по формуляра,
    забранените гасителни вещества, рисковите вещества и защитата на служителите.

Отпечатва JSON {"prieto": [ред, …], "ne_e_popalneno": [ред, …]}.
"""
import argparse
import json
import math
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (os.path.join(os.path.dirname(HERE), "_shared", "scripts"),
           os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(HERE))), "shared", "scripts")):
    if os.path.isdir(_p):
        sys.path.insert(0, _p)
        break
from kais import kc_to_wgs  # noqa: E402

try:
    from shapely.geometry import LineString, Point, Polygon
    from shapely.ops import nearest_points, unary_union
except ImportError:  # pragma: no cover – shapely е в requirements.txt
    Polygon = None

VHOD_TOCHNO_M = 5.0    # до толкова имотът опира в улицата; по-далеч – входът е през съседен имот (паркинг, алея)

# Подкласът по името на обекта / предназначението в КАИС (Наредба № Iз-1971, табл. 1). Редът има значение.
PODKLAS = [
    ("Ф1.1", r"детск\w* град|ясл[аи]|болниц|дом за (стари|деца|възраст)|социален дом"),
    ("Ф1.2", r"хотел|мотел|хостел|пансион|общежити|почивна станция"),
    ("Ф1.3", r"многофамилн"),
    ("Ф1.4", r"еднофамилн"),
    ("Ф2.1", r"театър|театрал|кино|концерт|опер[аи]|читалищ|библиотек|филхармони"),
    ("Ф2.2", r"музе[йя]|галери|дискотек|казино"),
    ("Ф3.2", r"ресторант|обществено хранене|заведение за хранене|кафе"),
    ("Ф3.1", r"магазин|търгов|супермаркет|хипермаркет|мол\b"),
    ("Ф3.4", r"поща|банк[аи]"),
    ("Ф4.1", r"училищ|гимнази|университет|колеж"),
    ("Ф4.2", r"административн|делова|офис"),
]

# Горимо натоварване – средната плътност по БДС EN 1991-1-2, Приложение E, табл. E.4 (MJ/m²); kg/m² = MJ / 17,5
NATOVARVANE = [
    (r"театър|театрал|кино|концерт|опер", 300, "декори, завеси и текстил, тапицирани седалки, дървен под на сцената"),
    (r"библиотек|читалищ", 1500, "книги и хартия, рафтове, мебели"),
    (r"детск\w* град|ясл|училищ|гимнази", 285, "мебели, играчки и учебни пособия, текстил"),
    (r"болниц", 230, "легла и матраци, текстил, мебели"),
    (r"хотел|мотел|хостел|пансион|общежити", 310, "мебели, легла и матраци, текстил"),
    (r"магазин|търгов|супермаркет|мол\b", 600, "стоки, опаковки от картон и пластмаса, стелажи"),
    (r"административн|офис|делова|поща|банк", 420, "мебели, хартия и документи, офис техника"),
    (r"жилищ|многофамилн|еднофамилн", 780, "мебели, текстил, битова техника"),
]
STEPENI = ["I", "II", "III", "IV", "V"]


GENERIC_BUILDING = "сграда със специално предназначение"


def low1(s):
    return s[:1].lower() + s[1:] if s else s


def main_buildings(d):
    return [s for s in d.get("sgradi") or [] if isinstance(s, dict) and not s.get("sasedna") and not s.get("naves")
            and not s.get("kratko")]


def kais_building(kais, sid):
    for s in (kais or {}).get("sgradi") or []:
        if s.get("id") == sid:
            return s
    return {}


def polygon_of(pts):
    try:
        p = Polygon(pts)
        return p if p.is_valid and p.area > 1 else p.buffer(0)
    except (ValueError, TypeError):
        return None


def street_geoms(d, name):
    """Всички парчета на улицата с това име: площите от КАИС и ивиците от OpenStreetMap."""
    core = re.sub(r"^(ул\.|бул\.|пл\.)\s*", "", name.strip(" „“\"")).strip(" „“\"").lower()
    out = []
    for u in d.get("ulitsi") or []:
        if not isinstance(u, dict) or u.get("pateka"):
            continue
        names = (str(u.get("ime") or "") + " " + str(u.get("ime_ulitsa") or "")).lower()
        if not core or core not in names:
            continue
        if u.get("kontur"):
            g = polygon_of(u["kontur"])
        elif u.get("tochki"):
            g = LineString(u["tochki"]).buffer(float(u.get("shirina") or 6) / 2)
        else:
            g = None
        if g is not None and not g.is_empty:
            out.append(g)
    return unary_union(out) if out else None


def site_polygon(d):
    if d.get("teren_tochki") and len(d["teren_tochki"]) >= 3:
        p = polygon_of(d["teren_tochki"])
        if p is not None and not p.is_empty:
            return p
    blds = [polygon_of(s["kontur"]) for s in main_buildings(d) if s.get("kontur")]
    blds = [b for b in blds if b is not None and not b.is_empty]
    return unary_union(blds) if blds else None


def fill_gps(d, prieto, kais):
    if str(d.get("obekt_gps") or "").strip() or not (d.get("kais") or {}).get("x0"):
        return
    site = site_polygon(d)
    if site is None:
        return
    c = site.centroid
    lat, lon = kc_to_wgs(d["kais"]["x0"] + c.x, d["kais"]["y0"] + c.y)
    d["obekt_gps"] = f"{lat:.7f},{lon:.7f}"
    prieto.append("разстояние и време – от службата по заповедта за районите до центъра на имота (по пътищата, "
                  "1 km/min и 1 min излизане)")


def fill_label(d, kais, prieto):
    """Надписът на главната сграда – по дейността (името на обекта), не общото предназначение от КАИС."""
    blds, name = main_buildings(d), str((d.get("list") or {}).get("obekt") or "")
    if not blds or not name:
        return
    s = blds[0]
    kb = kais_building(kais, s.get("kais_id"))
    if str(s.get("etiket") or "").strip() not in ("", str(kb.get("predn") or "").strip()):
        return                                         # вече е по дейността – не се пипа
    short = re.split(r"\s*[„\"(,]", name)[0].strip() or name
    s["etiket"] = short
    prieto.append(f"надписът на главната сграда – „{short}“ (по името на обекта; в КАИС – „{kb.get('predn') or '–'}“)")


def arhiv_of(d):
    """Данните от стария оперативен план (arhiv_danni.py), запомнени в JSON-а – търсят се веднъж."""
    a = d.get("arhiv_danni")
    if a is None and d.get("arhiv", True) is not False and (d.get("list") or {}).get("obekt"):
        try:
            from arhiv_danni import lookup
            a = d["arhiv_danni"] = lookup(d["list"]["obekt"], (d.get("list") or {}).get("adres") or "")
        except Exception:  # noqa: BLE001 – архивът е допълнение: без него схемата пак се прави
            a = None
    return a if isinstance(a, dict) and a.get("namereno") else None


def fill_from_archive(d, kais, prieto, ne):
    """Каквото КАИС няма, а старият план на обекта казва – взема се оттам, без въпрос, с годината на плана
    (_shared/arhiv.md). План отпреди 2010 г. е ориентир – „да се провери на място“."""
    a = arhiv_of(d)
    if not a:
        return
    dn, src = a.get("danni") or {}, a.get("iztochnik") or "по стария план"
    chk = " – да се провери на място" if a.get("star") else ""
    form = d.setdefault("formulyar", {})
    blds = main_buildings(d)
    if blds and dn.get("ogneustoychivost") and not blds[0].get("ogneustoychivost"):
        blds[0]["ogneustoychivost"] = dn["ogneustoychivost"]
        prieto.append(f"{dn['ogneustoychivost']} ст. огнеустойчивост – {src}{chk}")
    if blds and dn.get("etazhi") and not form.get("etazhi"):
        kb = kais_building(kais, blds[0].get("kais_id"))
        nad = kb.get("etazhi") or int((re.findall(r"\+(\d+)", str(blds[0].get("etazhnost") or "")) or [0])[-1])
        if nad and dn["etazhi"] > nad:
            form["etazhi"] = "сутерен или тавански етаж"
            prieto.append(f"етажи – {dn['etazhi']} {src}, в КАИС {nad} надземни: разликата е сутерен или тавански "
                          "етаж – да се уточни на място")
        elif nad:
            form["etazhi"] = "няма"
            prieto.append(f"етажи – {dn['etazhi']} {src}, колкото и в КАИС; без сутерен и тавански етаж")
    if dn.get("el_tablo"):
        form.setdefault("el_tablo", dn["el_tablo"])
        prieto.append(f"главното ел. табло – „{dn['el_tablo'].rstrip('.')}“ ({src}); на листа – откъм входа, "
                      "приблизително{chk}".replace("{chk}", chk))
    if dn.get("gaz") and not form.get("gaz"):
        form["gaz"] = "не" if dn["gaz"] == "не" else "да – природен газ от улицата"
        prieto.append(f"газ – {form['gaz']} ({src}){chk}")
    inst = [x for x, k in (("спринклерна инсталация", "sprinkler"), ("водна завеса", "vodna_zavesa")) if dn.get(k)]
    extra = ([f"{dn['vpk']} ВПК"] if dn.get("vpk") else []) + \
        ([f"водоем {dn['vodoem_m3']:g} m³"] if dn.get("vodoem_m3") else [])
    if inst or extra:
        rows = d.setdefault("tablitsa", {}).setdefault("redove", [])
        if not rows:
            rows.append({})
        pgi = str(form.get("pgi") or "")
        if not pgi or pgi == "не знам":
            form["pgi"] = ", ".join(inst) or "няма"
            rows[0].setdefault("pgi_vid", ", ".join(inst + extra))
        elif "спринклер" in pgi and not dn.get("sprinkler"):
            ne_txt = (f"ПГИ – отговорено „{pgi}“, а {src} има " + (", ".join(inst + extra) or "друго")
                      + " и спринклер няма; остава отговорът – провери на място")
            prieto.append(ne_txt)
        prieto.append(f"инсталации – {', '.join(inst + extra + (['АПИИ'] if dn.get('apii') else []))} ({src}){chk}")
    if dn.get("vodoprovod_mm"):
        for v in d.get("vodoprovod") or []:
            if str(v.get("diametar")) in ("70/80", "", "None"):
                v["diametar"] = dn["vodoprovod_mm"]
        d["_vodoprovod_arhiv"] = f"Ø {dn['vodoprovod_mm']} mm ({src})"
        prieto.append(f"водопровод – Ø {dn['vodoprovod_mm']} mm"
                      + (f", {dn['hidranti']} ПХ около обекта" if dn.get("hidranti") else "") + f" ({src}){chk}")


def fill_category(d, kais, prieto, ne):
    name = str((d.get("list") or {}).get("obekt") or "")
    own = [s for s in d.get("sgradi") or [] if isinstance(s, dict) and not s.get("sasedna") and not s.get("naves")]
    for i, s in enumerate(own):
        kb = kais_building(kais, s.get("kais_id"))     # името на обекта – само за главната сграда
        text = f"{name if i == 0 else ''} {s.get('etiket') or ''} {kb.get('predn') or ''}".lower()
        if not s.get("kategoriya"):
            hit = next(((k, m.group(0)) for k, rx in PODKLAS for m in [re.search(rx, text)] if m), None)
            if not hit and i:
                continue
            if not hit:
                ne.append("категорията на главната сграда – по дейността (Наредба № Iз-1971, табл. 1 и табл. 2); "
                          "определи я по normativna-uredba, не питай")
                continue
            sub = s["kategoriya"] = hit[0]
            prieto.append(f"категория {sub} – по „{hit[1]}“ в името или предназначението (Наредба № Iз-1971, табл. 1)")
        if s.get("ogneustoychivost") or not str(s.get("kategoriya", "")).startswith(("Ф1", "Ф2", "Ф3", "Ф4")):
            continue
        with open(os.path.join(os.path.dirname(HERE), "references", "ogneustoychivost.json"), encoding="utf-8") as f:
            t4 = json.load(f)["tablitsa"]
        rows = t4.get(s["kategoriya"])
        floors = kb.get("etazhi") or int((re.findall(r"\+(\d+)", str(s.get("etazhnost") or "")) or [1])[-1])
        area = kb.get("zastroena_m2")
        if not rows or not area:
            continue
        key = "1" if floors <= 1 else "2" if floors == 2 else "3-5" if floors <= 5 else ">5"
        allowed = [i for i, v in enumerate(rows[key]) if v and v >= area]
        if not allowed:
            ne.append(f"огнеустойчивостта: {area} m² и {floors} ет. надхвърлят табл. 4 за {s['kategoriya']} – има "
                      "пожарни сектори; да се уточни при огледа")
            continue
        st = STEPENI[max(allowed)]
        s["ogneustoychivost"] = st
        prieto.append(f"{st} ст. огнеустойчивост – най-ниската, която табл. 4 на Наредба № Iз-1971 допуска за "
                      f"{s['kategoriya']}, {floors} ет. и {area} m² застроена площ (минимално изискване, не по конструкцията)")


def mark_entrance(d, x, y, toward=None):
    """Входът за колите при (x, y) на ръба на улицата: прекъсване, надпис „вход“ и площ без паркиране пред него."""
    d.setdefault("prohodi", []).append({"x": x, "y": y, "shirina": 6})
    d.setdefault("bez_parkirane", []).append({"x": round(x - 3, 1), "y": round(y - 2.5, 1), "w": 6, "h": 5})
    ux, uy = (toward[0] - x, toward[1] - y) if toward else (0.0, 1.0)
    n = math.hypot(ux, uy) or 1.0
    d.setdefault("tekst", []).append({"x": round(x + 4 + 2 * ux / n, 1), "y": round(y + 2 * uy / n, 1),
                                      "tekst": "вход", "fon": True})


def point_numbers(ans):
    """Номерата на точките от отговора на „portali“ – без пешеходните врати."""
    out = []
    for a in (ans if isinstance(ans, list) else [ans]):
        if isinstance(a, (int, float)):
            out.append(int(a))
        elif isinstance(a, str) and "пешеход" not in a:
            out += [int(m) for m in re.findall(r"\d+", a)]
    return out


def fill_entrance(d, prieto, ne):
    """Входът за колите – по номера на точката от ортофотото (portali); без номер – само когато имотът опира в
    улицата от отговора vhod_kola. Иначе не се гадае: през съседен паркинг най-близката точка често е грешната."""
    if d.get("prohodi") or d.get("vhodove") or Polygon is None:
        return None
    form = d.get("formulyar") or {}
    site = site_polygon(d)
    tochki = {int(t["n"]): (t["x"], t["y"]) for t in d.get("ortofoto_tochki") or [] if "n" in t}
    streets = [a[3:].strip() for a in (form.get("vhod_kola") if isinstance(form.get("vhod_kola"), list)
                                       else [form.get("vhod_kola")]) if isinstance(a, str) and a.startswith("от ")]
    road = unary_union([g for g in (street_geoms(d, x) for x in streets) if g is not None]) if streets else None
    first = None
    for n_ in point_numbers(form.get("portali")):
        if n_ not in tochki:
            ne.append(f"точка {n_} я няма на ортофотото – поискай номера отново")
            continue
        x, y = tochki[n_]
        if d.get("ograda"):
            d.setdefault("vhodove", []).append({"x": x, "y": y, "shirina": 6})
            prieto.append(f"порталът за колите – при точка {n_} на ортофотото")
        elif road is not None and Point(x, y).distance(road) <= 15:
            q = nearest_points(Point(x, y), road.boundary)[1]
            mark_entrance(d, round(q.x, 1), round(q.y, 1), (x, y))
            prieto.append(f"входът за колите – при точка {n_}, откъм улицата")
        else:
            mark_entrance(d, round(x, 1), round(y, 1), site.centroid.coords[0] if site is not None else None)
            prieto.append(f"входът за колите – при точка {n_} на ортофотото")
        first = first or (x, y)
    if first or not streets or site is None:
        return first
    for name in streets:
        g = street_geoms(d, name)
        if g is None:
            continue
        p_site, p_str = nearest_points(site.exterior, g)
        if p_site.distance(p_str) > VHOD_TOCHNO_M:
            ne.append(f"входът „от {name}“ – имотът не опира в улицата (влиза се през съседен имот); покажи "
                      "ортофотото и поискай номера на точката (въпросът portali)")
            continue
        near = site.exterior.intersection(g.buffer(VHOD_TOCHNO_M + 3))
        mid = near.centroid if not near.is_empty else p_site
        q = nearest_points(mid, g.boundary)[1]
        mark_entrance(d, round(q.x, 1), round(q.y, 1), (mid.x, mid.y))
        prieto.append(f"входът за колите от {name} – в средата на участъка, където имотът опира в улицата; провери на огледа")
        first = first or (q.x, q.y)
    return first


def fill_tablo(d, vhod, prieto):
    if any(isinstance(o, dict) and str(o.get("etiket", "")).startswith("Ел") for o in d.get("obekti") or []):
        return
    blds = main_buildings(d)
    if not blds or not blds[0].get("kontur") or Polygon is None:
        return
    b = polygon_of(blds[0]["kontur"])
    if b is None or b.is_empty:
        return
    ref = Point(vhod) if vhod else b.centroid
    p = nearest_points(b.exterior, ref)[0]
    c = b.centroid
    k = 2.5 / (math.hypot(c.x - p.x, c.y - p.y) or 1.0)
    x, y = p.x + (c.x - p.x) * k, p.y + (c.y - p.y) * k
    d.setdefault("obekti", []).append({"x": round(x - 1.5, 1), "y": round(y - 1, 1), "w": 3, "h": 2, "etiket": "Ел."})
    tano = (d.get("formulyar") or {}).get("el_tablo")
    if tano and tano == ((arhiv_of(d) or {}).get("danni") or {}).get("el_tablo"):
        return                                         # казано е при стария план
    prieto.append("главното ел. табло – " + (f"по формуляра („{tano}“), " if tano and tano != "не знам" else "")
                  + "в главната сграда откъм входа за колите; предполагаемо – провери на място")


def fill_water(d, prieto):
    if d.get("vodoprovod") or not d.get("vodoiztochnitsi") or d.get("_vodoprovod_arhiv"):
        return
    prieto.append("водопровод – Ø 70/80, 3–5 bar (прието, схема от ВиК няма); трасето не е начертано: хидрантите не са "
                  "по улица от кадастъра, а хидрант извън трасето не се свързва с измислена линия")


def fill_owner(d, kais, prieto):
    lst = d.setdefault("list", {})
    vid = ((kais or {}).get("imot") or {}).get("sobstvenost")
    if str(lst.get("sobstvenik") or "").strip() or not vid:
        return
    lst["sobstvenik"] = owner_text(vid)                # the source goes to the chat, not onto the sheet
    prieto.append(f"собственик – „{lst['sobstvenik']}“ по КАИС; ако намериш точното наименование в интернет, "
                  "смени /list/sobstvenik")


def owner_text(vid):
    """КАИС: „Държавна публична“ → „Публична държавна собственост“, „Частна“ → „Частна собственост“."""
    words = str(vid).split()
    if len(words) == 2 and words[1].lower() in ("публична", "частна"):
        words.reverse()
    text = " ".join(words).lower()
    return f"{text[:1].upper()}{text[1:]} собственост"


def note_generic_buildings(d, prieto):
    n = sum(1 for s in d.get("sgradi") or [] if str(s.get("etiket") or "").strip().lower() == GENERIC_BUILDING)
    if n:
        prieto.append(f"{n} сгради са само „със специално предназначение“ по КАИС - напиши кои са, с кратко име "
                      "(„01 РУ“, „РДПБЗН“)")


def fill_table(d, prieto):
    tab = d.setdefault("tablitsa", {})
    rows = tab.setdefault("redove", [])
    if not rows:
        rows.append({})
    r = rows[0]
    form = d.get("formulyar") or {}
    text = f"{(d.get('list') or {}).get('obekt') or ''} " + " ".join(
        str(s.get("etiket") or "") for s in main_buildings(d)[:1]).lower()
    text = text.lower()
    if not r.get("natovarvane_vid"):
        hit = next(((mj, what) for rx, mj, what in NATOVARVANE if re.search(rx, text)), None)
        if hit:
            r["natovarvane_vid"], r["natovarvane_kg_m2"] = hit[1], f"≈ {round(hit[0] / 17.5)}"
            prieto.append(f"горимо натоварване ≈ {round(hit[0] / 17.5)} kg/m² – {hit[0]} MJ/m² по БДС EN 1991-1-2, "
                          "Прил. E, табл. E.4 (средна стойност)")
    pgi = str(form.get("pgi") or "")
    if not r.get("pgi_vid") and pgi and pgi not in ("не знам",):
        r["pgi_vid"] = "няма" if pgi == "няма" else pgi.replace(" – ", ", ")
    gaz = str(form.get("gaz") or "")
    if not r.get("gazove_vid") and gaz.startswith("не") and gaz != "не знам":
        r["gazove_vid"] = "няма"
    defaults = {"gasitelni_neobhodimi": "вода, пяна", "gasitelni_zabraneni": "вода върху ел. уредби под напрежение",
                "rvm_vid": "няма", "zashtita": "ВДА, лични предпазни средства"}
    added = [k for k, v in defaults.items() if not r.get(k) and r.setdefault(k, v)]
    if added:
        prieto.append("табличната част – забранени вещества, рискови вещества и защита на служителите по правилата "
                      "(references/pravila.md, „Когато данни липсват“)")
    tab.setdefault("prazni_redove", 6)


def dopalni(d, kais=None):
    prieto, ne = [], []
    fill_gps(d, prieto, kais)
    fill_label(d, kais, prieto)
    fill_from_archive(d, kais, prieto, ne)             # старият план – преди правилата по подразбиране
    fill_category(d, kais, prieto, ne)
    vhod = fill_entrance(d, prieto, ne)
    fill_tablo(d, vhod, prieto)
    fill_water(d, prieto)
    fill_owner(d, kais, prieto)
    note_generic_buildings(d, prieto)
    fill_table(d, prieto)
    if not (d.get("formulyar") or {}).get("etazhi"):
        prieto.append("сутерен и тавански етаж – кадастърът дава само надземните; да се уточнят при огледа")
    done = [x for x in d.get("dopalneno") or [] if x not in prieto] + prieto   # и при второ пускане – цялото прието
    d["dopalneno"] = done
    return {"prieto": done, "ne_e_popalneno": ne}


def main():
    ap = argparse.ArgumentParser(description="Попълва непитаното в ситуационната схема")
    ap.add_argument("data", help="JSON на схемата – записва се на място")
    ap.add_argument("--kais", help="kais.json от kais.py obekt (предназначение, площ, собственост)")
    a = ap.parse_args()
    with open(a.data, encoding="utf-8") as f:
        d = json.load(f)
    kais = None
    if a.kais and os.path.isfile(a.kais):
        with open(a.kais, encoding="utf-8") as f:
            kais = json.load(f)
    res = dopalni(d, kais)
    with open(a.data, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=1)
    print(json.dumps(res, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
