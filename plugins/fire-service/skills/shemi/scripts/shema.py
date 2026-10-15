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
  "sgradi": [{"x": 10, "y": 55, "w": 36, "h": 22, "etiket": "Склад\\nет. 1",
              "razmeri": true, "pokriv": "dvuskaten"}],  // "dvuskaten" чертае билото; "plosak" – нищо
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
  водоизточници – vodoem (пожарен водоем, "etiket" – обемът в m³), hidrant (подземен), nadzemen_hidrant
  линии       – glavna (главна, Ø 75 mm), malka (работна, Ø 52 mm), smukatelna (без чертички)
  струйници ("struinik" на линия) – malak, glaven, lafeten, penostruinik, prahov;
                "myasto": pokriv / etazh / maze – струйник на покрив, в етаж, в мазе („п“, „е“, „м“)
  стълби      – sglobna, razdvizhna (разтегателна), shturmova, palka

Струйникът е в края на линията, по посоката на последния ѝ участък. Чертичките по линиите (по една на
всеки "shlang_m" метра) показват броя на шланговете – те са от учебника по оперативна тактика, не от
Приложение № 6 (там знакът „Шланг“ е навит шланг – спирала).

Отпечатва JSON {"output", "svg", "elementi", "shlangove", "preduprezhdeniya"}. "shlangove" е броят
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

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from znatsi import (FENCES, INK, LEGEND_ORDER, LINE_KINDS, NOZZLES, PLACES, SPLITTERS, TRUCKS, LADDERS,  # noqa: E402,F401
                    WATER, Pal, chaikin, draw_building, draw_dimension, draw_fence, draw_fire, draw_hydrant,
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
                           "tekst", "vhodove")}
    out["ograda"] = None
    out["vyatar"] = None
    out["ograda_vid"] = d.get("ograda_vid") or None
    if out["ograda_vid"] not in (None, *FENCES):
        bad(f"ograda_vid: {', '.join(FENCES)}")
    for i, b in enumerate(items(d, "sgradi")):
        r = rect(b, f"sgradi[{i}]")
        if b.get("pokriv") not in (None, "", "plosak", "dvuskaten"):
            bad(f"sgradi[{i}].pokriv: „dvuskaten“ или „plosak“")
        out["sgradi"].append({**r, "etiket": str(b.get("etiket") or ""), "razmeri": b.get("razmeri", True),
                              "pokriv": b.get("pokriv")})
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
    for i, w in enumerate(items(d, "vodoiztochnitsi")):
        kind = w.get("vid") or "hidrant"
        if kind not in WATER:
            bad(f"vodoiztochnitsi[{i}].vid: {', '.join(WATER)}")
        out["vodoiztochnitsi"].append({"vid": kind, "x": num(w.get("x"), f"vodoiztochnitsi[{i}].x"),
                                       "y": num(w.get("y"), f"vodoiztochnitsi[{i}].y"), "etiket": str(w.get("etiket") or "")})
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
    if not out["sgradi"]:
        bad("няма нито една сграда в \"sgradi\"")

    # the extent of the drawing
    xs, ys = [], []
    for b in out["sgradi"] + out["obekti"] + out["pozhar"] + out["zadimyavane"]:
        xs += [b["x"], b["x"] + b["w"]]
        ys += [b["y"], b["y"] + b["h"]]
    for coll in (out["avtomobili"], out["vodoiztochnitsi"], out["vhodove"], out["razklonitel"]):
        xs += [o["x"] for o in coll]
        ys += [o["y"] for o in coll]
    for p in out["ognishte"] + out["shtab"] + out["pbt"]:
        xs.append(p[0])
        ys.append(p[1])
    for ln in out["linii"]:
        xs += [p[0] for p in ln["tochki"]]
        ys += [p[1] for p in ln["tochki"]]
    for a, b in out["posoka"] + out["napravlenie"] + [(s["ot"], s["do"]) for s in out["stalbi"]]:
        xs += [a[0], b[0]]
        ys += [a[1], b[1]]
    if out["ograda"]:
        xs += [p[0] for p in out["ograda"]]
        ys += [p[1] for p in out["ograda"]]
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

def render(d, out_png, out_svg=None, width_cm=None, height_cm=None):
    data, warnings = load(d)
    pal = Pal(bool(d.get("cvetna", True)))
    width_cm = width_cm or num(d.get("shirina_cm", WIDTH_CM), "shirina_cm")
    height_cm = height_cm or num(d.get("visochina_cm", MAX_DRAW_HEIGHT_CM), "visochina_cm")
    block = bool(d.get("legenda", False))             # the legend, the scale and the wind under the drawing
    x0, y0, x1, y1 = data["box"]
    wu, hu = x1 - x0, y1 - y0
    s = data["s"]                                      # the size of a symbol in drawing units (m)
    hose_m = num(d.get("shlang_m", 20) or 0, "shlang_m")
    keys, extra = legend_keys(data, hose_m) if block else ([], [])

    width_in = width_cm / 2.54
    draw_h_in = min(width_in * hu / wu, height_cm / 2.54)
    draw_w_in = draw_h_in * wu / hu
    if not block:                                      # only the drawing – no white strips beside it
        width_in = draw_w_in
    fs = 7.0 * min(1.45, max(1.0, draw_w_in * 2.54 / 16.5))   # the lettering grows with the drawing
    # the legend: two columns, long names wrapped
    entries = [(k, textwrap.wrap(legend_text(k, hose_m), 40)) for k in keys] + \
              [("obekt", textwrap.wrap(text, 40), label) for _, text, label in extra]
    col_rows = [entries[0::2], entries[1::2]]
    row_lines = [max(len(e[1]) for e in pair if e) for pair in zip(col_rows[0], col_rows[1] + [None] * len(col_rows[0]))
                 if pair[0] is not None]
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
    for sp in ax.spines.values():                      # no frame around the drawing ("ramka": true – with one)
        sp.set_visible(bool(d.get("ramka", False)))
        sp.set_linewidth(0.8)

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
    for z in data["zadimyavane"]:
        draw_smoke(ax, z, s, pal)
    for b in data["sgradi"]:
        draw_building(ax, b["x"], b["y"], b["w"], b["h"], b["pokriv"])
        if b["etiket"]:
            lx, ly = label_point(b, data["pozhar"] + data["zadimyavane"])
            ax.text(lx, ly, b["etiket"].replace("\\n", "\n"), ha="center", va="center", fontsize=fs + 0.5, zorder=4,
                    linespacing=1.2, bbox=dict(fc="white", ec="none", pad=1.0, alpha=0.9))
        if b["razmeri"]:
            off = 0.75 * s
            draw_dimension(ax, (b["x"], b["y"]), (b["x"] + b["w"], b["y"]), f"{b['w']:g}", (0, -off), fs - 0.5)
            draw_dimension(ax, (b["x"] + b["w"], b["y"]), (b["x"] + b["w"], b["y"] + b["h"]), f"{b['h']:g}",
                           (off, 0), fs - 0.5)
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
        if d.get("mashtab", True):                     # the scale bar – in the legend's title row
            step = scale_step(wu)
            bar = step / wu * draw_w_in
            bx = width_in * 0.36
            lax.text(bx, top, "Мащаб:", fontsize=fs, va="center")
            bx += 0.55
            lax.plot([bx, bx + bar], [top, top], color=INK, lw=1.2)
            for px in (bx, bx + bar / 2, bx + bar):
                lax.plot([px, px], [top - 0.04, top + 0.04], color=INK, lw=0.9)
            lax.text(bx + bar + 0.06, top, f"{step:g} m", fontsize=fs, va="center")
        if data["vyatar"]:                             # the wind – at the right end of the title row
            wx = width_in - 1.25
            lax.text(wx, top, "Вятър:", fontsize=fs, va="center")
            draw_wind(lax, wx + 0.62, top, data["vyatar"]["ugal"], 0.15)
            if data["vyatar"]["sila"]:
                lax.text(wx + 0.82, top, data["vyatar"]["sila"], fontsize=fs, va="center")
        cur = top - 0.22
        for r, n in enumerate(row_lines):
            cy = cur - line_in * (n - 1) / 2 - 0.03
            for col in (0, 1):
                if r < len(col_rows[col]):
                    e = col_rows[col][r]
                    cx = 0.3 + col * width_in / 2
                    obrazets(lax, e, cx, cy, pal, fs)
                    lax.text(cx + 0.42, cy, "\n".join(e[1]), fontsize=fs, va="center", linespacing=1.15)
            cur -= 0.15 + line_in * n

    fig.savefig(out_png, dpi=300, facecolor="white")
    if out_svg:
        fig.savefig(out_svg, facecolor="white")
    plt.close(fig)
    counts = {k: len(data[k]) for k in ("sgradi", "avtomobili", "linii", "vodoiztochnitsi", "pozhar")}
    counts["razmer_m"] = [round(wu, 1), round(hu, 1)]       # the drawn area – for choosing the page orientation
    return counts, hoses, warnings

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
    counts, hoses, warnings = render(d, a.out, a.svg, a.shirina_cm, a.visochina_cm)
    print(json.dumps({"output": a.out, "svg": a.svg, "elementi": counts, "shlangove": hoses,
                      "preduprezhdeniya": warnings}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
