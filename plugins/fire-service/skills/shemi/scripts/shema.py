#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
shema.py — чертае СХЕМА за разполагане на силите и средствата (за ПТЗ, план за пожарогасене,
справка, експертиза) като .png (и по желание .svg): сгради с размери, ограда и входове, пожар,
задимяване, огнище, посока на разпространение, главно направление, пожарните автомобили,
водоизточниците, шланговите линии, разклонителите и струйниците, стълбите, щаба, поста по
безопасност, вятъра, севера, мащаба и легенда само с използваните знаци.

Всички знаци идват от библиотеката scripts/znatsi.py (каталогът им: python3 scripts/znatsi.py -o znatsi.png).
Знаците и наименованията им са по Приложение № 6, част А (III) и част Б („Условни знаци, използвани при
разработка на планове за пожарогасене“) към Указанията за разработване на планове за пожарогасене,
рег. № Iз-2749/18.11.2010 г. на МВР – по рисунките в приложенията (PDF на МВР). В приложението
автомобилите, пожарът, огнището и направленията са в червено, а линиите, струйниците,
разклонителите, водоизточниците и задимяването – в синьо. Схемите са цветни по тези цветове;
"cvetna": false – черно-бяла.

Под схемата по подразбиране няма нищо – нито легенда („Условни знаци“), нито мащаб, нито вятър;
"legenda": true ги добавя (вятърът – ако е подаден "vyatar"). Знакът за посоките е винаги в горния ляв ъгъл.

    python3 scripts/shema.py shema.json -o shema.png [--svg shema.svg] [--shirina-cm 25.2 --visochina-cm 14]

Ширината на картинката е ширината на текста на страницата (по подразбиране 16,5 cm – A4 изправена;
25,2 cm – A4 легнала), а височината на чертежа е най-много --visochina-cm (по подразбиране 17 cm).
Шрифтовете и знаците са едни и същи при всяка ширина – картинката се вмъква без мащабиране.

Координатите са в метри: x – на изток (надясно), y – на север (нагоре), началото е долният ляв ъгъл
на терена. Сградите са правоъгълници, успоредни на осите. Ъглите са в градуси: 0 – изток, 90 – север.
Задължително е само "sgradi" (поне една сграда); всичко останало е по желание.

{
  "zaglavie": "",                               // надпис над схемата в картинката (обикновено празно –
                                                //   заглавието е в документа)
  "teren": [120, 90],                           // ширина и височина на чертежа, m (иначе – по елементите)
  "ograda": [[2, 2], [118, 2], [118, 88], [2, 88]],          // затворена ограда, точките по реда
  "ograda_vid": "metalna",                      // zhelezobetonna, kamenna, metalna, darvena, bodliva;
                                                //   без вид – пунктир „Ограда“
  "vhodove": [{"x": 60, "y": 2, "shirina": 8, "etiket": "КПП"}],    // отвор в оградата; „КПП“ – в кръг
  "sgradi": [{"x": 10, "y": 55, "w": 36, "h": 22, "etiket": "Склад\\nет. 1",   // или "kontur": [[x, y], …] –
                                                //   сграда с друга форма (размерите – общата дължина и ширина)
              "razmeri": true, "pokriv": "dvuskaten",   // "dvuskaten" чертае билото; "plosak" – нищо
              "etazhnost": "-1 +2", "kategoriya": "Ф5Б", "ogneustoychivost": "II",   // ситуационна схема:
                                                //   добавят се под името – „-1 +2 · Ф5Б · II ст.“ (чл. 8, ал. 1)
              "sasedna": false}],               // true – съседна сграда: по-тънък контур, без размери
  "obekti": [{"x": 3, "y": 58, "w": 4, "h": 3, "etiket": "Ел."}],   // малки обекти в рамка; „Ел.“ влиза в
                                                //   легендата като „Електрическо табло“; "legenda": "…" – друг текст
  "pozhar": [{"x": 34, "y": 60, "w": 12, "h": 12, "etiket": "≈ 140 m²", "na_otkrito": false}],
  "zadimyavane": [{"x": 10, "y": 55, "w": 24, "h": 22}],            // зона на задимяване
  "ognishte": [{"x": 40, "y": 66}],                                 // огнище на пожара (флагче)
  "posoka": [{"ot": [34, 66], "do": [26, 66]}],                     // посока на разпространение
  "napravlenie": [{"ot": [52, 44], "do": [46, 56]}],                // главно направление за действие
  "avtomobili": [{"id": "I ПА", "x": 60, "y": 40, "ugal": 90, "vid": "pa"}],   // ъгъл – накъдето гледа предницата
  "vodoiztochnitsi": [{"vid": "vodoem", "x": 85, "y": 20, "etiket": "120"},
                      {"vid": "hidrant", "x": 70, "y": 8, "etiket": "ПХ № 3"}],
  "linii": [{"tochki": [[60, 44], [52, 52], [46, 60]], "vid": "glavna"},
            {"tochki": [[46, 60], [40, 58], [36, 62]], "vid": "malka", "struinik": "malak", "myasto": "pokriv"},
            {"tochki": [[84, 20], [64, 38]], "vid": "smukatelna"}],
  "razklonitel": [{"x": 46, "y": 60, "patya": 3}],     // 2, 3 (по подразбиране) или 4 пътя; "ugal" – по
                                                       //   подразбиране по линията, която стига до него
  "stalbi": [{"ot": [40, 54], "do": [40, 58], "vid": "sglobna"}],
  "shtab": [{"x": 66, "y": 44}],                                    // място за разположение на щаба
  "pbt": [{"x": 56, "y": 30}],                                      // пост по безопасност на труда
  "vyatar": {"ugal": 200, "sila": "5 m/s"},                         // накъде духа и скоростта – в легендата
  "tekst": [{"x": 5, "y": 5, "tekst": "ул. „Христо Ботев“", "ugal": 0}],
  // --- елементите на ситуационната схема (чл. 7, ал. 3, т. 1 от Указанията) – по желание и в обикновената схема
  "ulitsi": [{"tochki": [[0, -6], [120, -6]], "shirina": 8, "ime": "ул. „Примерна“"}],   // знакът „Шосе“, кафяв
  "razstoyaniya": [{"ot": [46, 66], "do": [60, 66]}],          // разстояние между сгради – стойността се смята
  "vodoprovod": [{"tochki": [[0, -2], [120, -2]], "vid": "skluchena", "diametar": 150, "natisk": 0.5}],
                                                // skluchena / tupikova; диаметър в mm, налягане в MPa →
                                                //   надпис „С-150/5“ (налягането в bar), както в Приложение № 6
  "gazoprovod": [{"tochki": [[118, 10], [100, 10], [100, 40]]}],
  "gaz_armatura": [{"x": 100, "y": 30, "etiket": "СК", "ugal": 90}],  // спирателна арматура, жълта
  "bez_parkirane": [{"x": 50, "y": 4, "w": 20, "h": 6}],       // площ, неразрешена за паркиране, оранжева
  "geo": {"lat": 43.4100, "lon": 24.6100},      // долният ляв ъгъл на терена; тогава водоизточник може да е
                                                //   с "lat"/"lon" вместо "x"/"y" (напр. от voda.py на vodoiztochnitsi)
  // --- от кадастралната карта (КАИС) – началото на JSON-а го пише _shared/scripts/kais.py obekt --shema
  "kais": {"x0": 430981, "y0": 4808710},       // долният ляв ъгъл на терена в КС2005 – тогава "lat"/"lon" на
                                                //   водоизточник се смятат точно като контурите от КАИС (вместо "geo")
  "imot": {"kontur": [[x, y], …], "etiket": "ПИ 56722.27.446"},   // границата на поземления имот – тънка щрих-
                                                //   пунктирна линия с идентификатора
  "fon": {"png": "kais_fon.png", "ramka": [0, 0, 226, 226], "prozrachnost": 0.35},   // картинка под чертежа:
                                                //   кадастралната карта около обекта (съседните сгради и имоти);
                                                //   "ramka" – x0, y0, x1, y1 на картинката в метри
  "list": {...},                                // ЛИСТ НА СИТУАЦИОННА СХЕМА по Приложение № 2а – виж по-долу
  "shlang_m": 20,                               // дължина на един шланг – чертичка на всеки толкова метра
  "cvetna": true, "sever": true, "ramka": false,  // "ramka": true – рамка около чертежа
  "legenda": false,                             // true – легенда, мащаб ("mashtab") и вятър под чертежа
  "shirina_cm": 16.5, "visochina_cm": 17                           // или --shirina-cm / --visochina-cm
}

Видове (стойности на "vid"):
  автомобили  – pa (пожарен автомобил), pa_lafeten (с лафетен струйник), pas (автопомпена станция),
                shlangov, aerodrumen, pena_prah (за гасене с пяна и прах), prah (за гасене с прах),
                adz (за дихателна защита), spasitelen (за спасителна дейност), avtostalba
                (автомеханична стълба), avtopodemnik, shtaben, vodonoska (водоноска, бензиновоз)
  водоизточници – vodoem (пожарен водоем, "etiket" – обемът в m³), hidrant (подземен), nadzemen_hidrant,
                kran (пожарен кран, "etiket" – „ПК-4“), kula (водонапорна кула)
  линии       – glavna (главна, Ø 75 mm), malka (работна, Ø 52 mm), smukatelna (без чертички)
  струйници ("struinik" на линия) – malak, glaven, lafeten, penostruinik, prahov;
                "myasto": pokriv / etazh / maze – струйник на покрив, в етаж, в мазе („п“, „е“, „м“)
  стълби      – sglobna, razdvizhna (разтегателна), shturmova, palka

Струйникът е в края на линията, по посоката на последния ѝ участък. Чертичките по линиите (по една на
всеки "shlang_m" метра) показват броя на шланговете – те са от учебника по оперативна тактика, не от
Приложение № 6 (там знакът „Шланг“ е навит шланг – спирала).

ЛИСТ НА СИТУАЦИОННА СХЕМА ("list" – чл. 7, ал. 3, т. 1 и чл. 9 от Указанията, Приложение № 2а): картинката е
целият лист A4 легнал в рамката – 26,7 × 19 cm (полета на страницата: ляво 2 cm, останалите 1 cm), с поле
20 × 15 mm за номера в горния десен ъгъл и антетка 150 × 30 mm в долния десен. Чертежът е в стандартен мащаб
(1:200, 1:250, 1:500, 1:1000 …) – най-едрия, в който се събира; мащабът е изписан до антетката.

  "list": {"nomer": "12",                       // № по списъка по чл. 5, ал. 4 – полето горе вдясно
           "obekt": "Склад за горими течности, гр. …, ул. …, тел. …",   // „Наименование на обекта, адрес, телефон“
           "sobstvenik": "", "protokol": "", "izgotvil": "", "saglasuval": "", "utvardil": "",
           "fail": "", "data": ""}             // празно поле остава празно – попълва се на ръка

Таблицата (Приложение № 2б) и легендата не са в картинката – те са в .docx от scripts/situacionna.py.

Отпечатва JSON {"output", "svg", "elementi", "shlangove", "preduprezhdeniya"} (с "list" – и "mashtab"). "shlangove" е броят
шлангове по линиите (по чертичките). Предупрежденията казват, ако нещо излиза извън терена, линия не
започва до автомобил, разклонител, водоизточник или друга линия, или входът не е върху оградата.

Грешки (на stderr, код ≠ 0):
    BAD_INPUT: ...    — липсва поле, непознат вид, неверни координати
    NO_MATPLOTLIB     — няма matplotlib: pip install matplotlib
"""

import argparse
import json
import math
import os
import sys
import textwrap

from matplotlib.patches import Polygon

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from znatsi import (FENCES, INK, LEGEND_ORDER, LINE_KINDS, NETWORKS, NOZZLES, PLACES, SPLITTERS, TRUCKS,  # noqa: E402,F401
                    LADDERS, WATER, Pal, chaikin, draw_building, draw_dimension, draw_fence, draw_fire, draw_hydrant,
                    draw_gas_line, draw_gas_valve, offset_polyline, draw_main, draw_no_parking, draw_street, draw_streets, draw_tower, draw_valve_kran,
                    draw_kompas, draw_label_box, draw_ladder, draw_line, draw_nozzle, draw_reservoir, draw_ring,
                    draw_seat, draw_smoke, draw_splitter, draw_staff, draw_truck, draw_wind, big_arrow, is_el,
                    is_kpp, legend_text, length, obrazets, plt, point_at)

WIDTH_CM = 16.5            # the text width of an A4 document with the plugin's margins
MAX_DRAW_HEIGHT_CM = 17.0


def bad(msg):
    sys.stderr.write("BAD_INPUT: " + msg + "\n")
    sys.exit(2)

def num(v, what):
    try:
        f = float(v)
    except (TypeError, ValueError):
        bad(f"{what}: очаква се число, а е {v!r}")
    if math.isnan(f) or math.isinf(f):
        bad(f"{what}: очаква се число, а е {v!r}")
    return f

def pt(p, what):
    if not isinstance(p, (list, tuple)) or len(p) != 2:
        bad(f"{what}: очаква се [x, y], а е {p!r}")
    return num(p[0], what), num(p[1], what)

def rect(item, what, w_default=None, h_default=None):
    w = num(item.get("w", w_default), f"{what}.w")
    h = num(item.get("h", h_default), f"{what}.h")
    if w <= 0 or h <= 0:
        bad(f"{what}: ширината и височината трябва да са положителни")
    return {"x": num(item.get("x"), f"{what}.x"), "y": num(item.get("y"), f"{what}.y"), "w": w, "h": h}

def items(d, key):
    v = d.get(key) or []
    if isinstance(v, dict):
        v = [v]
    if not isinstance(v, list) or not all(isinstance(i, dict) for i in v):
        bad(f"{key}: очаква се списък от обекти")
    return v

def dist_to_segment(p, a, b):
    (px, py), (ax_, ay), (bx, by) = p, a, b
    dx, dy = bx - ax_, by - ay
    if dx == dy == 0:
        return math.dist(p, a)
    t = max(0, min(1, ((px - ax_) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    return math.dist(p, (ax_ + t * dx, ay + t * dy))

def overlap(a0, a1, b0, b1):
    return min(a1, b1) - max(a0, b0) > 0

def label_point(b, fires):
    """The centre of the building's label – in the biggest part of the building that no fire covers,
    so that the hatching does not hide the name."""
    cx, cy = b["x"] + b["w"] / 2, b["y"] + b["h"] / 2
    inside = [f for f in fires if overlap(b["x"], b["x"] + b["w"], f["x"], f["x"] + f["w"])
              and overlap(b["y"], b["y"] + b["h"], f["y"], f["y"] + f["h"])]
    if not inside:
        return cx, cy
    horiz = b["w"] >= b["h"]                           # look for a free strip along the longer side
    lo, hi = (b["x"], b["x"] + b["w"]) if horiz else (b["y"], b["y"] + b["h"])
    cuts = sorted((max(lo, f["x"] if horiz else f["y"]), min(hi, (f["x"] + f["w"]) if horiz else (f["y"] + f["h"])))
                  for f in inside)
    gaps, cur = [], lo
    for c0, c1 in cuts:
        if c0 > cur:
            gaps.append((cur, c0))
        cur = max(cur, c1)
    if cur < hi:
        gaps.append((cur, hi))
    if not gaps:
        return cx, cy
    g0, g1 = max(gaps, key=lambda g: g[1] - g[0])
    return ((g0 + g1) / 2, cy) if horiz else (cx, (g0 + g1) / 2)

def scale_step(units):
    raw = units / 5
    return next((v for v in (1, 2, 5, 10, 20, 25, 50, 100, 200, 500, 1000) if v >= raw), 1000)

def load(d):
    warnings = []
    if not isinstance(d, dict):
        bad("схемата трябва да е JSON обект")
    out = {k: [] for k in ("sgradi", "obekti", "pozhar", "zadimyavane", "ognishte", "posoka", "napravlenie",
                           "avtomobili", "vodoiztochnitsi", "linii", "razklonitel", "stalbi", "shtab", "pbt",
                           "tekst", "vhodove", "ulitsi", "razstoyaniya", "vodoprovod", "gazoprovod",
                           "gaz_armatura", "bez_parkirane")}
    out["ograda"] = None
    out["vyatar"] = None
    out["ograda_vid"] = d.get("ograda_vid") or None
    if out["ograda_vid"] not in (None, *FENCES):
        bad(f"ograda_vid: {', '.join(FENCES)}")
    for i, b in enumerate(items(d, "sgradi")):
        kontur = None
        if b.get("kontur"):                            # an outline of any shape – the points in order
            kontur = [pt(p, f"sgradi[{i}].kontur") for p in b["kontur"]]
            if len(kontur) < 3:
                bad(f"sgradi[{i}].kontur: трябват поне три точки")
            kx, ky = [p[0] for p in kontur], [p[1] for p in kontur]
            r = {"x": min(kx), "y": min(ky), "w": max(kx) - min(kx), "h": max(ky) - min(ky)}
        else:
            r = rect(b, f"sgradi[{i}]")
        if b.get("pokriv") not in (None, "", "plosak", "dvuskaten"):
            bad(f"sgradi[{i}].pokriv: „dvuskaten“ или „plosak“")
        sasedna = bool(b.get("sasedna", False))
        out["sgradi"].append({**r, "etiket": building_label(b), "razmeri": b.get("razmeri", not sasedna),
                              "pokriv": b.get("pokriv"), "sasedna": sasedna, "kontur": kontur,
                              "danni": {k: str(b.get(k) or "").strip() for k in ("etazhnost", "kategoriya", "ogneustoychivost")}})
    for i, b in enumerate(items(d, "obekti")):
        out["obekti"].append({**rect(b, f"obekti[{i}]", 5, 3), "etiket": str(b.get("etiket") or ""),
                              "legenda": str(b.get("legenda") or "")})
    for i, f in enumerate(items(d, "pozhar")):
        out["pozhar"].append({**rect(f, f"pozhar[{i}]"), "etiket": str(f.get("etiket") or ""),
                              "na_otkrito": bool(f.get("na_otkrito", False))})
    for i, z in enumerate(items(d, "zadimyavane")):
        out["zadimyavane"].append(rect(z, f"zadimyavane[{i}]"))
    for i, o in enumerate(items(d, "ognishte")):
        out["ognishte"].append((num(o.get("x"), f"ognishte[{i}].x"), num(o.get("y"), f"ognishte[{i}].y")))
    for key in ("posoka", "napravlenie"):
        for i, a in enumerate(items(d, key)):
            out[key].append((pt(a.get("ot"), f"{key}[{i}].ot"), pt(a.get("do"), f"{key}[{i}].do")))
    for i, t in enumerate(items(d, "avtomobili")):
        kind = t.get("vid") or "pa"
        if kind not in TRUCKS:
            bad(f"avtomobili[{i}].vid: {', '.join(TRUCKS)}")
        out["avtomobili"].append({"id": str(t.get("id") or f"{i + 1} ПА"), "vid": kind,
                                  "x": num(t.get("x"), f"avtomobili[{i}].x"), "y": num(t.get("y"), f"avtomobili[{i}].y"),
                                  "ugal": num(t.get("ugal", 0), f"avtomobili[{i}].ugal")})
    geo = d.get("geo")
    if geo is not None and not isinstance(geo, dict):
        bad("geo: очаква се обект {\"lat\", \"lon\"}")
    kais = d.get("kais")
    if kais is not None and not isinstance(kais, dict):
        bad("kais: очаква се обект {\"x0\", \"y0\"} – началото на терена в КС2005")
    for i, w in enumerate(items(d, "vodoiztochnitsi")):
        kind = w.get("vid") or "hidrant"
        if kind not in WATER:
            bad(f"vodoiztochnitsi[{i}].vid: {', '.join(WATER)}")
        if w.get("x") is None and w.get("lat") is not None and kais:
            x, y = from_kais(num(w.get("lat"), f"vodoiztochnitsi[{i}].lat"), num(w.get("lon"), f"vodoiztochnitsi[{i}].lon"),
                             num(kais.get("x0"), "kais.x0"), num(kais.get("y0"), "kais.y0"))
        elif w.get("x") is None and w.get("lat") is not None:
            if not geo:
                bad(f"vodoiztochnitsi[{i}]: дадени са \"lat\"/\"lon\" – трябва и \"geo\" (долният ляв ъгъл на терена)")
            x, y = from_geo(num(w.get("lat"), f"vodoiztochnitsi[{i}].lat"), num(w.get("lon"), f"vodoiztochnitsi[{i}].lon"),
                            num(geo.get("lat"), "geo.lat"), num(geo.get("lon"), "geo.lon"))
        else:
            x, y = num(w.get("x"), f"vodoiztochnitsi[{i}].x"), num(w.get("y"), f"vodoiztochnitsi[{i}].y")
        out["vodoiztochnitsi"].append({"vid": kind, "x": x, "y": y, "etiket": str(w.get("etiket") or "")})
    for i, ln in enumerate(items(d, "linii")):
        kind = ln.get("vid") or "malka"
        if kind not in LINE_KINDS:
            bad(f"linii[{i}].vid: {', '.join(LINE_KINDS)}")
        pts = [pt(p, f"linii[{i}].tochki") for p in (ln.get("tochki") or [])]
        if len(pts) < 2:
            bad(f"linii[{i}].tochki: трябват поне две точки")
        nozzle = ln.get("struinik")
        if nozzle not in (None, "", *NOZZLES):
            bad(f"linii[{i}].struinik: {', '.join(NOZZLES)}")
        place = ln.get("myasto")
        if place not in (None, "", *PLACES):
            bad(f"linii[{i}].myasto: {', '.join(PLACES)}")
        out["linii"].append({"tochki": pts, "vid": kind, "struinik": nozzle or None, "myasto": place or None,
                             "etiket": str(ln.get("etiket") or ""), "gladka": ln.get("gladka", True)})
    for i, r in enumerate(items(d, "razklonitel")):
        ways = int(num(r.get("patya", 3), f"razklonitel[{i}].patya"))
        if ways not in SPLITTERS:
            bad(f"razklonitel[{i}].patya: 2, 3 или 4")
        angle = num(r["ugal"], f"razklonitel[{i}].ugal") if r.get("ugal") is not None else None
        out["razklonitel"].append({"x": num(r.get("x"), f"razklonitel[{i}].x"), "y": num(r.get("y"), f"razklonitel[{i}].y"),
                                   "patya": ways, "ugal": angle})
    for i, st in enumerate(items(d, "stalbi")):
        kind = st.get("vid") or "sglobna"
        if kind not in LADDERS:
            bad(f"stalbi[{i}].vid: {', '.join(LADDERS)}")
        out["stalbi"].append({"ot": pt(st.get("ot"), f"stalbi[{i}].ot"), "do": pt(st.get("do"), f"stalbi[{i}].do"),
                              "vid": kind})
    for key in ("shtab", "pbt"):
        for i, o in enumerate(items(d, key)):
            out[key].append((num(o.get("x"), f"{key}[{i}].x"), num(o.get("y"), f"{key}[{i}].y")))
    for i, t in enumerate(items(d, "tekst")):
        out["tekst"].append({"x": num(t.get("x"), f"tekst[{i}].x"), "y": num(t.get("y"), f"tekst[{i}].y"),
                             "tekst": str(t.get("tekst") or ""), "ugal": num(t.get("ugal", 0), f"tekst[{i}].ugal")})
    for i, u in enumerate(items(d, "ulitsi")):
        pts = [pt(p, f"ulitsi[{i}].tochki") for p in (u.get("tochki") or [])]
        if len(pts) < 2:
            bad(f"ulitsi[{i}].tochki: трябват поне две точки")
        out["ulitsi"].append({"tochki": pts, "shirina": num(u.get("shirina", 7), f"ulitsi[{i}].shirina"),
                              "ime": str(u.get("ime") or "")})
    for i, r in enumerate(items(d, "razstoyaniya")):
        a, b = pt(r.get("ot"), f"razstoyaniya[{i}].ot"), pt(r.get("do"), f"razstoyaniya[{i}].do")
        out["razstoyaniya"].append({"ot": a, "do": b, "etiket": str(r.get("etiket") or f"{math.dist(a, b):.0f}")})
    for i, v in enumerate(items(d, "vodoprovod")):
        kind = v.get("vid") or "skluchena"
        if kind not in NETWORKS:
            bad(f"vodoprovod[{i}].vid: {', '.join(NETWORKS)}")
        pts = [pt(p, f"vodoprovod[{i}].tochki") for p in (v.get("tochki") or [])]
        if len(pts) < 2:
            bad(f"vodoprovod[{i}].tochki: трябват поне две точки")
        label = str(v.get("etiket") or "")
        if not label and v.get("diametar") is not None:
            label = f"{NETWORKS[kind]}-{num(v['diametar'], f'vodoprovod[{i}].diametar'):g}"
            if v.get("natisk") is not None:
                label += f"/{num(v['natisk'], f'vodoprovod[{i}].natisk') * 10:g}"
        out["vodoprovod"].append({"tochki": pts, "vid": kind, "etiket": label})
    for i, g in enumerate(items(d, "gazoprovod")):
        pts = [pt(p, f"gazoprovod[{i}].tochki") for p in (g.get("tochki") or [])]
        if len(pts) < 2:
            bad(f"gazoprovod[{i}].tochki: трябват поне две точки")
        out["gazoprovod"].append({"tochki": pts})
    for i, g in enumerate(items(d, "gaz_armatura")):
        out["gaz_armatura"].append({"x": num(g.get("x"), f"gaz_armatura[{i}].x"), "y": num(g.get("y"), f"gaz_armatura[{i}].y"),
                                    "etiket": str(g.get("etiket") or ""), "ugal": num(g.get("ugal", 0), f"gaz_armatura[{i}].ugal")})
    for i, z in enumerate(items(d, "bez_parkirane")):
        out["bez_parkirane"].append(rect(z, f"bez_parkirane[{i}]"))
    if d.get("ograda"):
        out["ograda"] = [pt(p, "ograda") for p in d["ograda"]]
        if len(out["ograda"]) < 3:
            bad("ograda: трябват поне три точки")
    for i, g in enumerate(items(d, "vhodove")):
        out["vhodove"].append({"x": num(g.get("x"), f"vhodove[{i}].x"), "y": num(g.get("y"), f"vhodove[{i}].y"),
                               "shirina": num(g.get("shirina", 6), f"vhodove[{i}].shirina"),
                               "etiket": str(g.get("etiket") or ""), "horiz": True})
    if d.get("vyatar"):
        v = d["vyatar"]
        if not isinstance(v, dict):
            bad("vyatar: очаква се обект {\"ugal\", \"sila\"}")
        out["vyatar"] = {"ugal": num(v.get("ugal"), "vyatar.ugal"), "sila": str(v.get("sila") or "")}
    out["imot"] = None
    if d.get("imot"):
        im = d["imot"]
        if not isinstance(im, dict) or not isinstance(im.get("kontur"), list):
            bad("imot: очаква се {\"kontur\": [[x, y], …], \"etiket\": \"ПИ …\"}")
        k = [pt(p, "imot.kontur") for p in im["kontur"]]
        if len(k) >= 3:
            out["imot"] = {"kontur": k, "etiket": str(im.get("etiket") or "")}
    out["fon"] = None
    if d.get("fon"):
        f = d["fon"]
        if not isinstance(f, dict) or not f.get("png") or not isinstance(f.get("ramka"), list) or len(f["ramka"]) != 4:
            bad("fon: очаква се {\"png\": \"файл\", \"ramka\": [x0, y0, x1, y1]}")
        if os.path.exists(str(f["png"])):
            out["fon"] = {"png": str(f["png"]), "ramka": [num(v, "fon.ramka") for v in f["ramka"]],
                          "alpha": min(1.0, max(0.05, num(f.get("prozrachnost", 0.35), "fon.prozrachnost")))}
        else:
            warnings.append(f"фонът {f['png']} го няма – чертая без него")
    if not out["sgradi"]:
        bad("няма нито една сграда в \"sgradi\"")

    # the extent of the drawing
    xs, ys = [], []
    for b in out["sgradi"] + out["obekti"] + out["pozhar"] + out["zadimyavane"] + out["bez_parkirane"]:
        xs += [b["x"], b["x"] + b["w"]]
        ys += [b["y"], b["y"] + b["h"]]
    for coll in (out["avtomobili"], out["vodoiztochnitsi"], out["vhodove"], out["razklonitel"], out["gaz_armatura"]):
        xs += [o["x"] for o in coll]
        ys += [o["y"] for o in coll]
    for p in out["ognishte"] + out["shtab"] + out["pbt"]:
        xs.append(p[0])
        ys.append(p[1])
    for ln in out["linii"] + out["vodoprovod"] + out["gazoprovod"]:
        xs += [p[0] for p in ln["tochki"]]
        ys += [p[1] for p in ln["tochki"]]
    for u in out["ulitsi"]:                        # a street counts with its width
        for k in (-1, 1):
            side = offset_polyline(u["tochki"], k * u["shirina"] / 2)
            xs += [p[0] for p in side]
            ys += [p[1] for p in side]
    for a, b in out["posoka"] + out["napravlenie"] + [(s["ot"], s["do"]) for s in out["stalbi"] + out["razstoyaniya"]]:
        xs += [a[0], b[0]]
        ys += [a[1], b[1]]
    if out["ograda"]:
        xs += [p[0] for p in out["ograda"]]
        ys += [p[1] for p in out["ograda"]]
    if out["imot"]:
        xs += [p[0] for p in out["imot"]["kontur"]]
        ys += [p[1] for p in out["imot"]["kontur"]]
    if d.get("teren"):
        tw, th = pt(d["teren"], "teren")
        if tw <= 0 or th <= 0:
            bad("teren: ширината и височината трябва да са положителни")
        x0, y0, x1, y1 = 0.0, 0.0, tw, th
        if min(xs) < 0 or min(ys) < 0 or max(xs) > tw or max(ys) > th:
            warnings.append("има елементи извън терена – провери координатите или увеличи \"teren\"")
            x0, y0, x1, y1 = min(x0, min(xs)), min(y0, min(ys)), max(x1, max(xs)), max(y1, max(ys))
    else:
        pad = 0.08 * max(max(xs) - min(xs), max(ys) - min(ys), 10)
        x0, y0, x1, y1 = min(xs) - pad, min(ys) - pad, max(xs) + pad, max(ys) + pad
    out["box"] = (x0, y0, x1, y1)
    out["s"] = symbol_size(x1 - x0, y1 - y0)

    # the gates sit on the fence – find the side each one is on
    if out["vhodove"] and out["ograda"]:
        sides = list(zip(out["ograda"], out["ograda"][1:] + out["ograda"][:1]))
        for g in out["vhodove"]:
            best = min(sides, key=lambda sd: dist_to_segment((g["x"], g["y"]), *sd))
            g["horiz"] = abs(best[1][0] - best[0][0]) >= abs(best[1][1] - best[0][1])
            if dist_to_segment((g["x"], g["y"]), *best) > 2:
                warnings.append(f"входът „{g['etiket'] or g['x']}“ не е върху оградата")

    # every hose line must start at a fire engine, a splitter, a water source or the end of another line
    anchors = [(t["x"], t["y"]) for t in out["avtomobili"]] + [(r["x"], r["y"]) for r in out["razklonitel"]] + \
              [(w["x"], w["y"]) for w in out["vodoiztochnitsi"]]
    for i, ln in enumerate(out["linii"]):
        others = [p for j, o in enumerate(out["linii"]) if j != i for p in (o["tochki"][0], o["tochki"][-1])]
        start = ln["tochki"][0]
        near = min((math.dist(start, a) for a in anchors + others), default=1e9)
        if near > max(3.5, 1.3 * out["s"]):
            warnings.append(f"линия № {i + 1} ({ln['vid']}) не започва до автомобил, разклонител, водоизточник "
                            f"или друга линия (най-близо е на {near:.0f} m)")
    for i, ln in enumerate(out["linii"]):
        if ln["vid"] == "smukatelna" and (ln["struinik"] or ln["myasto"]):
            warnings.append(f"линия № {i + 1} е смукателна, а има струйник – струйникът е пропуснат")
            ln["struinik"] = ln["myasto"] = None

    # a splitter turns its inlet towards the line that comes to it
    for r in out["razklonitel"]:
        if r["ugal"] is not None:
            continue
        r["ugal"] = 90.0
        for ln in out["linii"]:
            p = ln["tochki"]
            if math.dist(p[-1], (r["x"], r["y"])) < 1.5:
                r["ugal"] = math.degrees(math.atan2(p[-1][1] - p[-2][1], p[-1][0] - p[-2][0]))
                break
        else:
            for ln in out["linii"]:
                p = ln["tochki"]
                if math.dist(p[0], (r["x"], r["y"])) < 1.5:
                    r["ugal"] = math.degrees(math.atan2(p[1][1] - p[0][1], p[1][0] - p[0][0]))
                    break
    return out, warnings

def centroid(pts):
    """The centroid of a polygon (its area's centre) – falls inside an ordinary building outline."""
    a = cx = cy = 0.0
    for (x0, y0), (x1, y1) in zip(pts, pts[1:] + pts[:1]):
        c = x0 * y1 - x1 * y0
        a += c
        cx += (x0 + x1) * c
        cy += (y0 + y1) * c
    if abs(a) < 1e-9:
        return sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts)
    return cx / (3 * a), cy / (3 * a)

def building_label(b):
    """The building's name, and on the next line the floors, the fire-hazard category and the fire resistance
    (чл. 7, ал. 3, т. 1, б. „б“ от Указанията): „Склад\n-1 +2 · Ф5Б · II ст.“."""
    name = str(b.get("etiket") or "").replace("\\n", "\n")
    parts = [str(b.get("etazhnost") or "").strip(), str(b.get("kategoriya") or "").strip()]
    ogn = str(b.get("ogneustoychivost") or "").strip()
    if ogn:
        parts.append(ogn if "ст" in ogn else f"{ogn} ст.")
    extra = " · ".join(p for p in parts if p)
    return "\n".join(p for p in (name, extra) if p)

def from_kais(lat, lon, x0, y0):
    """Metres east and north of the terrain's origin (x0, y0 in КС2005) – the same projection as the contours from
    КАИС, so a hydrant lands exactly where it is against the buildings."""
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "_shared", "scripts"))
    try:
        from kais import wgs_to_kc
    except ImportError:  # pragma: no cover – the development tree
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))))), "shared", "scripts"))
        from kais import wgs_to_kc
    x, y = wgs_to_kc(lat, lon)
    return x - x0, y - y0

def from_geo(lat, lon, lat0, lon0):
    """Metres east and north of (lat0, lon0) – plenty accurate over a site of a few hundred metres."""
    return ((lon - lon0) * 111_320 * math.cos(math.radians(lat0)), (lat - lat0) * 110_574)

def symbol_size(wu, hu):
    """The size of a symbol (a fire engine is about 1.7 of it long) in drawing units – about 4.5 % of the drawing."""
    return min(0.045 * max(wu, hu), 0.11 * min(wu, hu) + 0.02 * max(wu, hu))

def legend_keys(data, hose_m):
    used = {"sgrada"}
    if data["ograda"]:
        used.add(data["ograda_vid"] or "ograda")
    used.update("pozhar_otkrito" if f["na_otkrito"] else "pozhar" for f in data["pozhar"])
    for key in ("zadimyavane", "ognishte", "posoka", "napravlenie", "shtab", "pbt"):
        if data[key]:
            used.add(key)
    if data["vyatar"]:
        used.add("vyatar")
    used.update(t["vid"] for t in data["avtomobili"])
    used.update(v["vid"] for v in data["vodoprovod"])
    for key in ("ulitsi", "gazoprovod", "gaz_armatura", "bez_parkirane"):
        if data[key]:
            used.add({"ulitsi": "ulitsa"}.get(key, key))
    used.update(w["vid"] for w in data["vodoiztochnitsi"])
    used.update(ln["vid"] for ln in data["linii"])
    if hose_m and any(ln["vid"] != "smukatelna" for ln in data["linii"]):
        used.add("shlang")
    used.update(SPLITTERS[r["patya"]] for r in data["razklonitel"])
    used.update(ln["struinik"] for ln in data["linii"] if ln["struinik"])
    used.update(ln["myasto"] for ln in data["linii"] if ln["myasto"])
    used.update(st["vid"] for st in data["stalbi"])
    if any(is_kpp(g["etiket"]) for g in data["vhodove"]) or any(is_kpp(o["etiket"]) for o in data["obekti"]):
        used.add("kpp")
    if any(is_el(o["etiket"]) for o in data["obekti"]):
        used.add("el")
    keys = [k for k in LEGEND_ORDER if k in used]
    extra = [(None, o["legenda"], o["etiket"]) for o in data["obekti"] if o["legenda"]]
    return keys, extra

SCALES = (100, 200, 250, 500, 1000, 2000, 2500, 5000, 10000, 20000)

# The sheet of a situational scheme (Приложение № 2а): the frame is the page minus its margins
# (left 20 mm, the rest 10 mm – the page margins of the .docx), in mm.
SHEET_W, SHEET_H = 267.0, 190.0
NO_BOX = (20.0, 15.0)                       # чл. 9, ал. 3 – the field for the plan's number, upper right
TITLE_BOX = (150.0, 30.0)                   # чл. 9, ал. 4 – the title block, lower right
PAD = 5.0


def draw_scene(ax, data, d, pal, s, fs, hose_m):
    """Everything inside the drawing – the same for a scheme and for the sheet of a situational scheme;
    returns the number of hoses along the lines."""
    x0, y0, x1, y1 = data["box"]
    if data["ograda"]:
        draw_fence(ax, data["ograda"], data["vhodove"], s, data["ograda_vid"])
    for g in data["vhodove"]:
        if not g["etiket"]:
            continue
        if is_kpp(g["etiket"]):
            r = 0.6 * s
            if g["horiz"]:
                cx, cy = g["x"], g["y"] + (1.0 * s if g["y"] < (y0 + y1) / 2 else -1.0 * s)
            else:
                cx, cy = g["x"] + (1.0 * s if g["x"] < (x0 + x1) / 2 else -1.0 * s), g["y"]
            draw_ring(ax, cx, cy, r, "КПП", fs - 1, pal.truck)
            continue
        bw, bh = max(2.4 * s, 0.6 * s * len(g["etiket"])), 0.85 * s
        if g["horiz"]:
            gx = g["x"] - bw / 2
            gy = g["y"] + 0.6 * s if g["y"] < (y0 + y1) / 2 else g["y"] - 0.6 * s - bh
        else:
            gx = g["x"] + 0.6 * s if g["x"] < (x0 + x1) / 2 else g["x"] - 0.6 * s - bw
            gy = g["y"] - bh / 2
        draw_label_box(ax, gx, gy, bw, bh, g["etiket"], fs)
    if data.get("fon"):                                # the cadastral map (КАИС) – faint, under everything
        f = data["fon"]
        img = plt.imread(f["png"])
        fx0, fy0, fx1, fy1 = f["ramka"]
        ax.imshow(img, extent=(fx0, fx1, fy0, fy1), origin="upper", alpha=f["alpha"], zorder=0,
                  interpolation="bilinear")
        ax.set_xlim(x0, x1)                            # imshow resets the limits – keep the drawing's
        ax.set_ylim(y0, y1)
    if data.get("imot"):                               # the parcel's boundary – thin dash-dot, its identifier at the top
        k = data["imot"]["kontur"]
        ax.add_patch(Polygon(k, closed=True, fill=False, ec=INK, lw=0.7, ls=(0, (6, 2, 1, 2)), zorder=1))
        if data["imot"]["etiket"]:
            tx, ty = max(k, key=lambda p: (p[1], -p[0]))
            ax.text(tx, ty + 0.4 * s, data["imot"]["etiket"], ha="center", va="bottom", fontsize=fs - 0.5, zorder=4,
                    bbox=dict(fc="white", ec="none", pad=0.6, alpha=0.85))
    draw_streets(ax, data["ulitsi"], fs, pal)          # the situation first – under everything else
    for z in data["bez_parkirane"]:
        draw_no_parking(ax, z, pal)
    for v in data["vodoprovod"]:
        draw_main(ax, v["tochki"], v["vid"], v["etiket"], s, fs, pal)
    for g in data["gazoprovod"]:
        draw_gas_line(ax, g["tochki"], s, fs, pal)
    for z in data["zadimyavane"]:
        draw_smoke(ax, z, s, pal)
    for b in data["sgradi"]:
        if b["kontur"]:
            ax.add_patch(Polygon(b["kontur"], closed=True, fill=False, ec=INK, lw=0.9 if b["sasedna"] else 1.8,
                                 joinstyle="miter", zorder=3))
        else:
            draw_building(ax, b["x"], b["y"], b["w"], b["h"], b["pokriv"], lw=0.9 if b["sasedna"] else 1.8)
        if b["etiket"] and b["kontur"]:                # an outline: the label at its centroid, no white box over the walls
            lx, ly = centroid(b["kontur"])
            ax.text(lx, ly, b["etiket"].replace("\\n", "\n"), ha="center", va="center", fontsize=fs + 0.5, zorder=4,
                    linespacing=1.2)
        elif b["etiket"]:
            lx, ly = label_point(b, data["pozhar"] + data["zadimyavane"])
            ax.text(lx, ly, b["etiket"].replace("\\n", "\n"), ha="center", va="center", fontsize=fs + 0.5, zorder=4,
                    linespacing=1.2, bbox=dict(fc="white", ec="none", pad=1.0, alpha=0.9))
        if b["razmeri"]:
            off = 0.75 * s
            draw_dimension(ax, (b["x"], b["y"]), (b["x"] + b["w"], b["y"]), f"{b['w']:g}", (0, -off), fs - 0.5)
            draw_dimension(ax, (b["x"] + b["w"], b["y"]), (b["x"] + b["w"], b["y"] + b["h"]), f"{b['h']:g}",
                           (off, 0), fs - 0.5)
    for r in data["razstoyaniya"]:
        draw_dimension(ax, r["ot"], r["do"], r["etiket"], (0, 0), fs - 0.5)
    for g in data["gaz_armatura"]:
        draw_gas_valve(ax, g["x"], g["y"], s, g["etiket"], fs, pal, g["ugal"])
    for o in data["obekti"]:
        draw_label_box(ax, o["x"], o["y"], o["w"], o["h"], o["etiket"], fs, pal.truck if is_el(o["etiket"]) else INK)
    for f in data["pozhar"]:
        draw_fire(ax, f, pal)
        if f["etiket"]:
            ax.text(f["x"] + f["w"] / 2, f["y"] - 0.25 * s, f["etiket"], ha="center", va="top", fontsize=fs,
                    zorder=7, bbox=dict(fc="white", ec="none", pad=0.6))
    for x, y in data["ognishte"]:
        draw_seat(ax, x, y, s, pal)
    for a, b in data["posoka"]:
        big_arrow(ax, a, b, pal, hatched=False, scale=18)
    for a, b in data["napravlenie"]:
        big_arrow(ax, a, b, pal, hatched=True, scale=18)
    hoses = 0
    for ln in data["linii"]:
        pts = chaikin(ln["tochki"]) if ln["gladka"] else ln["tochki"]
        hoses += draw_line(ax, pts, ln["vid"], s, hose_m, pal)
        _, direction = point_at(pts, length(pts))
        if ln["struinik"] or ln["myasto"]:
            draw_nozzle(ax, pts[-1], direction, ln["struinik"], s, pal, ln["myasto"])
        if ln["etiket"]:
            (ex, ey), (dx, dy) = pts[-1], direction
            ax.text(ex + dx * 0.6 * s - dy * 0.7 * s, ey + dy * 0.6 * s + dx * 0.7 * s, ln["etiket"], ha="center",
                    va="center", fontsize=fs, zorder=7, bbox=dict(fc="white", ec="none", pad=0.3))
    for r in data["razklonitel"]:
        draw_splitter(ax, r["x"], r["y"], s, r["patya"], r["ugal"], pal)
    for st in data["stalbi"]:
        draw_ladder(ax, st["ot"], st["do"], s, st["vid"])
    for w in data["vodoiztochnitsi"]:
        if w["vid"] == "vodoem":
            draw_reservoir(ax, w["x"], w["y"], s, w["etiket"], fs, pal)
        elif w["vid"] == "kran":
            draw_valve_kran(ax, w["x"], w["y"], s, w["etiket"], fs, pal)
        elif w["vid"] == "kula":
            draw_tower(ax, w["x"], w["y"], s, w["etiket"], fs, pal)
        else:
            draw_hydrant(ax, w["x"], w["y"], s, w["etiket"], fs, pal, above=w["vid"] == "nadzemen_hidrant")
    for t in data["avtomobili"]:
        draw_truck(ax, t, s, fs, pal)
        a = math.radians(t["ugal"] + 90)
        ax.text(t["x"] + math.cos(a) * 0.85 * s, t["y"] + math.sin(a) * 0.85 * s, t["id"], ha="center",
                va="center", fontsize=fs, zorder=10, bbox=dict(fc="white", ec="none", pad=0.5))
    for x, y in data["shtab"]:
        draw_staff(ax, x, y, s, fs, pal)
    for x, y in data["pbt"]:
        draw_ring(ax, x, y, 0.6 * s, "ПБТ", fs - 1, pal.truck)
    for t in data["tekst"]:
        ax.text(t["x"], t["y"], t["tekst"], ha="left", va="center", fontsize=fs, rotation=t["ugal"], zorder=9)
    # the north–south sign of the library – in the upper left corner (чл. 9, ал. 5 от Указанията Iз-2749);
    # the wind – in the legend, when there is one
    if d.get("sever", True):
        draw_kompas(ax, x0 + 0.9 * s, y1 - 2.3 * s, s, fs)
    return hoses


def legend_layout(keys, extra, hose_m):
    """The legend's entries in two columns and the height of each row (in lines)."""
    entries = [(k, textwrap.wrap(legend_text(k, hose_m), 40)) for k in keys] + \
              [("obekt", textwrap.wrap(text, 40), label) for _, text, label in extra]
    col_rows = [entries[0::2], entries[1::2]]
    row_lines = [max(len(e[1]) for e in pair if e) for pair in zip(col_rows[0], col_rows[1] + [None] * len(col_rows[0]))
                 if pair[0] is not None]
    return entries, col_rows, row_lines


def draw_legend_rows(lax, col_rows, row_lines, top, width_in, pal, fs, line_in=0.13):
    cur = top
    for r, n in enumerate(row_lines):
        cy = cur - line_in * (n - 1) / 2 - 0.03
        for col in (0, 1):
            if r < len(col_rows[col]):
                e = col_rows[col][r]
                cx = 0.3 + col * width_in / 2
                obrazets(lax, e, cx, cy, pal, fs)
                lax.text(cx + 0.42, cy, "\n".join(e[1]), fontsize=fs, va="center", linespacing=1.15)
        cur -= 0.15 + line_in * n


def render_legend(d, out_png, width_cm=WIDTH_CM, fs=7.0):
    """Only the legend („Условни знаци“) of the scheme d – for the page with the table of a situational
    scheme. Returns the number of entries (0 – nothing is written)."""
    data, _ = load(d)
    pal = Pal(bool(d.get("cvetna", True)))
    hose_m = num(d.get("shlang_m", 20) or 0, "shlang_m")
    keys, extra = legend_keys(data, hose_m)
    entries, col_rows, row_lines = legend_layout(keys, extra, hose_m)
    if not entries:
        return 0
    width_in, line_in = width_cm / 2.54, 0.13
    h = sum(0.15 + line_in * n for n in row_lines) + 0.35
    fig = plt.figure(figsize=(width_in, h), dpi=300)
    lax = fig.add_axes([0, 0, 1, 1])
    lax.set_xlim(0, width_in)
    lax.set_ylim(0, h)
    lax.set_aspect("equal")
    lax.axis("off")
    lax.text(0.15, h - 0.15, "Условни знаци:", fontsize=fs, va="center")
    draw_legend_rows(lax, col_rows, row_lines, h - 0.37, width_in, pal, fs)
    fig.savefig(out_png, dpi=300, facecolor="white")
    plt.close(fig)
    return len(entries)


def site_points(data):
    """The points of everything drawn on the site – to keep the sheet's fields clear of it."""
    pts = []
    for b in data["sgradi"]:
        pts += densify(b["kontur"] + b["kontur"][:1]) if b["kontur"] else []
    for b in data["sgradi"] + data["obekti"] + data["pozhar"] + data["zadimyavane"] + data["bez_parkirane"]:
        pts += [(b["x"], b["y"]), (b["x"] + b["w"], b["y"]), (b["x"], b["y"] + b["h"]), (b["x"] + b["w"], b["y"] + b["h"])]
    for coll in (data["avtomobili"], data["vodoiztochnitsi"], data["vhodove"], data["razklonitel"], data["gaz_armatura"]):
        pts += [(o["x"], o["y"]) for o in coll]
    for ln in data["linii"] + data["vodoprovod"] + data["gazoprovod"]:
        pts += densify(ln["tochki"])
    for u in data["ulitsi"]:
        for k in (-1, 1):
            pts += densify(offset_polyline(u["tochki"], k * u["shirina"] / 2))
    if data["ograda"]:
        pts += densify(data["ograda"] + data["ograda"][:1])
    return pts

def densify(pts, step=2.0):
    out = []
    for a, b in zip(pts, pts[1:]):
        n = max(1, int(math.dist(a, b) // step))
        out += [(a[0] + (b[0] - a[0]) * i / n, a[1] + (b[1] - a[1]) * i / n) for i in range(n)]
    return out + list(pts[-1:])

def sheet_scale(data):
    """The standard scale (1:N) and the drawing area (x, y, w, h in mm on the sheet): the largest scale at which
    the site fits on the sheet – over the whole frame when nothing falls on the number field, the compass or
    the title block, otherwise above the title block or beside it."""
    x0, y0, x1, y1 = data["box"]
    wu, hu = x1 - x0, y1 - y0
    pts = site_points(data)
    top = SHEET_H - PAD
    keep_out = [(SHEET_W - TITLE_BOX[0] - 2, 0, SHEET_W, TITLE_BOX[1] + 2),              # the title block
                (SHEET_W - NO_BOX[0] - 2, SHEET_H - NO_BOX[1] - 2, SHEET_W, SHEET_H),    # the number field
                (0, SHEET_H - 24, 17, SHEET_H)]                                         # the compass
    areas = [(PAD, PAD, SHEET_W - 2 * PAD, top - PAD, True),
             (PAD, TITLE_BOX[1] + PAD, SHEET_W - 2 * PAD, top - NO_BOX[1] - TITLE_BOX[1] - PAD, False),
             (PAD, PAD, SHEET_W - TITLE_BOX[0] - 3 * PAD, top - NO_BOX[1] - PAD, False)]
    best = None
    for ax_, ay, aw, ah, check in areas:
        need = max(wu * 1000 / aw, hu * 1000 / ah)
        for n in [v for v in SCALES if v >= need] or [math.ceil(need / 10000) * 10000]:
            w, h = wu * 1000 / n, hu * 1000 / n
            spots = [(ax_ + (aw - w) / 2, ay + (ah - h) / 2)]          # centred first, then towards the corners
            if check:
                spots += [(px, py) for py in (ay + ah - h, ay + (ah - h) / 2, ay) for px in (ax_, ax_ + (aw - w) / 2, ax_ + aw - w)]
            for px, py in spots:
                if check:
                    mm = [(px + (x - x0) * 1000 / n, py + (y - y0) * 1000 / n) for x, y in pts]
                    if any(a <= mx <= c and b <= my <= d for mx, my in mm for a, b, c, d in keep_out):
                        continue
                break
            else:
                continue
            if best is None or n < best[0]:
                best = (n, (px, py, w, h))
            break
    return best


def draw_sheet(fig, lst, scale, fs):
    """The frame, the number field and the title block of Приложение № 2а, on a figure that is the frame."""
    fax = fig.add_axes([0, 0, 1, 1])
    fax.set_xlim(0, SHEET_W)
    fax.set_ylim(0, SHEET_H)
    fax.axis("off")
    fax.set_zorder(-1)
    from matplotlib.patches import Rectangle as R
    lw = 0.9
    fax.add_patch(R((0.3, 0.3), SHEET_W - 0.6, SHEET_H - 0.6, fill=False, ec=INK, lw=lw))
    nw, nh = NO_BOX
    fax.add_patch(R((SHEET_W - nw - 0.3, SHEET_H - nh - 0.3), nw, nh, fill=False, ec=INK, lw=0.6))
    fax.text(SHEET_W - nw / 2 - 0.3, SHEET_H - 3, "№ на плана", ha="center", va="center", fontsize=fs - 2.5)
    fax.text(SHEET_W - nw / 2 - 0.3, SHEET_H - nh / 2 - 2, str(lst.get("nomer") or ""), ha="center", va="center",
             fontsize=fs + 3)
    tw, th = TITLE_BOX
    bx, by = SHEET_W - tw - 0.3, 0.3
    small = fs - 2.5
    # the grid – as in Приложение № 2а: three rows, 5 + 8 + 17 mm
    rows = [(by + 25, 5), (by + 17, 8), (by, 17)]
    fax.add_patch(R((bx, by), tw, th, fill=False, ec=INK, lw=0.6, zorder=2))
    fax.add_patch(R((bx, by), tw, th, fc="white", ec="none", zorder=1))
    for yy in (by + 17, by + 25):
        fax.plot([bx, bx + tw], [yy, yy], color=INK, lw=0.5, zorder=2)
    cells = [  # (x from, x to, row, caption, key)
        (0, 107, 0, "Собственик:", "sobstvenik"), (107, 150, 0, "Протокол рег. №", "protokol"),
        (0, 30, 1, "Изготвил:", "izgotvil"), (30, 63, 1, "Съгласувал:", "saglasuval"),
        (63, 107, 1, "Утвърдил / дата:", "utvardil"), (107, 136, 1, "Име на файла:", "fail"),
        (136, 150, 1, "Дата:", "data")]
    for a, b, r, cap, key in cells:
        y, h = rows[r]
        if a:
            fax.plot([bx + a, bx + a], [y, y + h], color=INK, lw=0.5, zorder=2)
        val = str(lst.get(key) or "")
        if r == 0:
            fax.text(bx + a + 1, y + h / 2, cap + (" " + val if val else ""), ha="left", va="center", fontsize=small, zorder=3)
        else:
            fax.text(bx + a + 1, y + h - 1.6, cap, ha="left", va="center", fontsize=small, zorder=3)
            if val:
                fax.text(bx + (a + b) / 2, y + 2.6, val, ha="center", va="center", fontsize=small + 0.8, zorder=3)
    y, h = rows[2]
    fax.plot([bx + 63, bx + 63], [y, y + h], color=INK, lw=0.5, zorder=2)
    obekt = str(lst.get("obekt") or "")
    if obekt:
        fax.text(bx + 31.5, y + h / 2, "\n".join(textwrap.wrap(obekt, 34)[:4]), ha="center", va="center",
                 fontsize=small + 0.8, linespacing=1.15, zorder=3)
    else:
        fax.text(bx + 31.5, y + h / 2, "Наименование на обекта,\nадрес, телефон", ha="center", va="center",
                 fontsize=small + 0.8, zorder=3)
    fax.text(bx + 106.5, y + h / 2, "Ситуационна схема", ha="center", va="center", fontsize=fs + 3, zorder=3)
    fax.text(bx - 3, by + 2, f"М 1:{scale}", ha="right", va="bottom", fontsize=fs)


def render(d, out_png, out_svg=None, width_cm=None, height_cm=None):
    data, warnings = load(d)
    pal = Pal(bool(d.get("cvetna", True)))
    x0, y0, x1, y1 = data["box"]
    wu, hu = x1 - x0, y1 - y0
    s = data["s"]                                      # the size of a symbol in drawing units (m)
    hose_m = num(d.get("shlang_m", 20) or 0, "shlang_m")
    lst = d.get("list")
    extra_out = {}

    if lst is not None:                                # the sheet of a situational scheme (Приложение № 2а)
        if not isinstance(lst, dict):
            bad("list: очаква се обект с полетата на антетката")
        scale, (ax_mm, ay_mm, aw_mm, ah_mm) = sheet_scale(data)
        fs = 7.0
        fig = plt.figure(figsize=(SHEET_W / 25.4, SHEET_H / 25.4), dpi=300)
        draw_sheet(fig, lst, scale, fs)
        ax = fig.add_axes([ax_mm / SHEET_W, ay_mm / SHEET_H, aw_mm / SHEET_W, ah_mm / SHEET_H])
        ax.set_xlim(x0, x1)
        ax.set_ylim(y0, y1)
        ax.set_aspect("equal")
        ax.axis("off")
        # the symbols keep their printed size whatever the scale: about 4.5 mm
        s = 4.5 * scale / 1000
        data["s"] = s
        hoses = draw_scene(ax, data, {**d, "sever": False}, pal, s, fs, hose_m)
        # the north arrow – in the upper left corner of the sheet (чл. 9, ал. 5)
        kax = fig.add_axes([0, 0, 1, 1])
        kax.set_xlim(0, SHEET_W)
        kax.set_ylim(0, SHEET_H)
        kax.axis("off")
        draw_kompas(kax, 9, SHEET_H - 13, 6, fs)
        extra_out["mashtab"] = f"1:{scale}"
        warnings += situation_gaps(data)
    else:
        width_cm = width_cm or num(d.get("shirina_cm", WIDTH_CM), "shirina_cm")
        height_cm = height_cm or num(d.get("visochina_cm", MAX_DRAW_HEIGHT_CM), "visochina_cm")
        block = bool(d.get("legenda", False))         # the legend, the scale and the wind under the drawing
        keys, extra = legend_keys(data, hose_m) if block else ([], [])
        width_in = width_cm / 2.54
        draw_h_in = min(width_in * hu / wu, height_cm / 2.54)
        draw_w_in = draw_h_in * wu / hu
        if not block:                                  # only the drawing – no white strips beside it
            width_in = draw_w_in
        fs = 7.0 * min(1.45, max(1.0, draw_w_in * 2.54 / 16.5))   # the lettering grows with the drawing
        entries, col_rows, row_lines = legend_layout(keys, extra, hose_m)
        line_in = 0.13
        legend_h_in = (sum(0.15 + line_in * n for n in row_lines) + 0.3) if entries else (0.35 if block else 0.0)
        title = str(d.get("zaglavie") or "")
        title_in = 0.3 if title else 0.0
        fig_h = draw_h_in + legend_h_in + title_in
        fig = plt.figure(figsize=(width_in, fig_h), dpi=300)
        if title:
            fig.text(0.5, 1 - title_in / 2 / fig_h, title, ha="center", va="center", fontsize=fs + 2)
        left = (width_in - draw_w_in) / 2 / width_in
        ax = fig.add_axes([left, legend_h_in / fig_h, draw_w_in / width_in, draw_h_in / fig_h])
        ax.set_xlim(x0, x1)
        ax.set_ylim(y0, y1)
        ax.set_aspect("equal")
        ax.set_xticks([])
        ax.set_yticks([])
        for sp in ax.spines.values():                  # no frame around the drawing ("ramka": true – with one)
            sp.set_visible(bool(d.get("ramka", False)))
            sp.set_linewidth(0.8)
        hoses = draw_scene(ax, data, d, pal, s, fs, hose_m)

        if block:
            lh = legend_h_in
            lax = fig.add_axes([0.0, 0.0, 1.0, lh / fig_h])
            lax.set_xlim(0, width_in)
            lax.set_ylim(0, lh)
            lax.set_aspect("equal")
            lax.axis("off")
            top = lh - 0.15
            if entries:
                lax.text(0.15, top, "Условни знаци:", fontsize=fs, va="center")
            if d.get("mashtab", True):                 # the scale bar – in the legend's title row
                step = scale_step(wu)
                bar = step / wu * draw_w_in
                bx = width_in * 0.36
                lax.text(bx, top, "Мащаб:", fontsize=fs, va="center")
                bx += 0.55
                lax.plot([bx, bx + bar], [top, top], color=INK, lw=1.2)
                for px in (bx, bx + bar / 2, bx + bar):
                    lax.plot([px, px], [top - 0.04, top + 0.04], color=INK, lw=0.9)
                lax.text(bx + bar + 0.06, top, f"{step:g} m", fontsize=fs, va="center")
            if data["vyatar"]:                         # the wind – at the right end of the title row
                wx = width_in - 1.25
                lax.text(wx, top, "Вятър:", fontsize=fs, va="center")
                draw_wind(lax, wx + 0.62, top, data["vyatar"]["ugal"], 0.15)
                if data["vyatar"]["sila"]:
                    lax.text(wx + 0.82, top, data["vyatar"]["sila"], fontsize=fs, va="center")
            draw_legend_rows(lax, col_rows, row_lines, top - 0.22, width_in, pal, fs, line_in)

    fig.savefig(out_png, dpi=300, facecolor="white")
    if out_svg:
        fig.savefig(out_svg, facecolor="white")
    plt.close(fig)
    counts = {k: len(data[k]) for k in ("sgradi", "avtomobili", "linii", "vodoiztochnitsi", "pozhar")}
    counts["razmer_m"] = [round(wu, 1), round(hu, 1)]       # the drawn area – for choosing the page orientation
    return counts, hoses, warnings, extra_out


def situation_gaps(data):
    """What чл. 7, ал. 3, т. 1 от Указанията asks of the graphic part and the scheme does not show."""
    gaps = []
    own = [b for b in data["sgradi"] if not b["sasedna"]]
    for b in own:
        name = b["etiket"].split("\n")[0] or f"({b['x']:g}, {b['y']:g})"
        missing = [t for k, t in (("etazhnost", "етажност"), ("kategoriya", "категория по пожарна опасност"),
                                  ("ogneustoychivost", "степен на огнеустойчивост")) if not b["danni"][k]]
        if missing:
            gaps.append(f"сграда „{name}“: липсва {', '.join(missing)} (чл. 7, ал. 3, т. 1, б. „б“)")
    if len(own) > 1 and not data["razstoyaniya"]:
        gaps.append("няма разстояния между сградите – \"razstoyaniya\" (б. „а“)")
    if not data["vhodove"]:
        gaps.append("няма входове – \"vhodove\" (б. „а“)")
    if not data["ulitsi"]:
        gaps.append("няма улици – \"ulitsi\" (б. „а“ и „е“)")
    if not data["vodoiztochnitsi"]:
        gaps.append("няма водоизточници, хидранти и кранове (б. „в“ и „г“)")
    if not data["vodoprovod"]:
        gaps.append("няма водопроводна мрежа – \"vodoprovod\" с вид, диаметър и налягане (б. „г“)")
    if not any(is_el(o["etiket"]) for o in data["obekti"]):
        gaps.append("няма главно електрическо табло – обект с етикет „Ел.“ (б. „з“)")
    return gaps


def main():
    ap = argparse.ArgumentParser(description="Схема за разполагане на силите и средствата")
    ap.add_argument("shema", help="JSON файл със схемата")
    ap.add_argument("-o", "--out", required=True, help="изходен .png")
    ap.add_argument("--svg", help="и .svg")
    ap.add_argument("--shirina-cm", type=float, help="ширината на картинката, cm (16.5 – A4 изправена, 25.2 – легнала)")
    ap.add_argument("--visochina-cm", type=float, help="най-голямата височина на чертежа, cm")
    a = ap.parse_args()
    try:
        with open(a.shema, encoding="utf-8") as f:
            d = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        bad(f"не мога да прочета {a.shema}: {e}")
    os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
    counts, hoses, warnings, extra = render(d, a.out, a.svg, a.shirina_cm, a.visochina_cm)
    print(json.dumps({"output": a.out, "svg": a.svg, "elementi": counts, "shlangove": hoses, **extra,
                      "preduprezhdeniya": warnings}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
