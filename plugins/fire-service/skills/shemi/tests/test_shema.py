#!/usr/bin/env python3
"""Smoke tests for shema.py. Run from the skill folder:
    python3 tests/test_shema.py
"""
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
SCRIPT = os.path.join(SKILL, "scripts", "shema.py")
FIXTURE = os.path.join(HERE, "fixtures", "shema.json")   # an invented site, not a real one
sys.path.insert(0, os.path.join(SKILL, "scripts"))

import shema  # noqa: E402

failures = []


def check(cond, msg):
    print(("  ok  " if cond else "  FAIL ") + msg)
    if not cond:
        failures.append(msg)


def run(data, *extra):
    tmp = tempfile.mkdtemp()
    src = os.path.join(tmp, "in.json")
    with open(src, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    out = os.path.join(tmp, "out.png")
    r = subprocess.run([sys.executable, SCRIPT, src, "-o", out, *extra], capture_output=True, text=True)
    return r, out


def test_fixture():
    print("shema.py – the full test site")
    data = json.load(open(FIXTURE, encoding="utf-8"))
    data["legenda"] = True                               # the legend only on request
    r, out = run(data, "--svg", os.path.join(tempfile.mkdtemp(), "out.svg"))
    check(r.returncode == 0, "renders without an error" + (": " + r.stderr[:200] if r.returncode else ""))
    if r.returncode:
        return
    res = json.loads(r.stdout)
    check(os.path.getsize(out) > 50_000, "the .png is written")
    check(res["preduprezhdeniya"] == [], f"no warnings for a consistent site: {res['preduprezhdeniya']}")
    check(res["elementi"]["avtomobili"] == 3 and res["elementi"]["linii"] == 5, "counts the engines and the lines")
    check(res["shlangove"] >= 4, f"counts the hoses along the lines ({res['shlangove']})")
    svg = open(res["svg"], encoding="utf-8").read()
    for name in ("Пожар в сграда", "Пожарна автомеханична стълба", "Трипътен разклонител",
                 "Място за разположение на щаба", "Контролнопропусквателен пункт", "Електрическо табло",
                 "Вятър:", "Мащаб:", "Зона на задимяване"):
        check(name in svg, f"the legend names „{name}“ (Приложение № 6 към Iз-2749)")
    check("Пожарен водоем" in svg and "Надземен хидрант" not in svg, "only the symbols in use go into the legend")
    check(">С<" in svg.replace(" ", "") or "С</text>" in svg, "the north–south sign is on the scheme")


def test_library():
    print("znatsi.py – the library of symbols")
    import znatsi
    out = os.path.join(tempfile.mkdtemp(), "katalog.svg")
    n = znatsi.katalog(out, colour=True)
    check(n == len(znatsi.LEGEND_ORDER) + len(znatsi.KATALOG_EXTRA), f"the catalogue draws every symbol ({n})")
    svg = open(out, encoding="utf-8").read()
    for name in ("Пожарен автомобил с лафетен струйник", "Стълба палка", "Огнище на пожара", "Посоките – север (С) и юг (Ю)"):
        check(name in svg, f"the catalogue names „{name}“")
    check(all(k in znatsi.LEGEND_TEXT for k in znatsi.LEGEND_ORDER), "every symbol in the order has a name")
    import shema as sh
    check(sh.draw_truck is znatsi.draw_truck and sh.obrazets is znatsi.obrazets, "the scheme draws with the library itself")


def test_defaults():
    print("shema.py – by default: in colour, nothing under the drawing")
    data = json.load(open(FIXTURE, encoding="utf-8"))
    tmp = tempfile.mkdtemp()
    r, _ = run(data, "--svg", os.path.join(tmp, "d.svg"), "--shirina-cm", "25.2", "--visochina-cm", "14.7")
    check(r.returncode == 0, "renders at the landscape width")
    if r.returncode:
        return
    svg = open(os.path.join(tmp, "d.svg"), encoding="utf-8").read()
    for word in ("Условни знаци", "Мащаб", "Вятър"):
        check(word not in svg, f"no „{word}“ under the drawing")
    check("#d0021b" in svg.lower() and "#1f4fd8" in svg.lower(), "red and blue as in Приложение № 6")
    import re
    w = float(re.search(r'<svg[^>]*width="([0-9.]+)pt"', svg).group(1)) / 72 * 2.54
    h = float(re.search(r'<svg[^>]*height="([0-9.]+)pt"', svg).group(1)) / 72 * 2.54
    check(abs(h - 14.7) < 0.05 and w <= 25.25, f"the drawing fills the height it is given, no white strips ({w:.1f} × {h:.1f} cm)")


def test_minimal_and_colour():
    print("shema.py – one building, colour")
    r, out = run({"sgradi": [{"x": 0, "y": 0, "w": 20, "h": 10}], "cvetna": True,
                  "pozhar": [{"x": 2, "y": 2, "w": 5, "h": 5, "na_otkrito": True}]})
    check(r.returncode == 0 and os.path.exists(out), "a single building is enough")


def test_warnings():
    print("shema.py – warnings")
    data = {"teren": [50, 40], "sgradi": [{"x": 5, "y": 5, "w": 10, "h": 10}],
            "avtomobili": [{"x": 30, "y": 20}],
            "linii": [{"tochki": [[45, 35], [40, 30]], "vid": "malka", "struinik": "malak"},
                      {"tochki": [[30, 20], [20, 20]], "vid": "smukatelna", "struinik": "malak"}],
            "ograda": [[1, 1], [49, 1], [49, 39], [1, 39]], "vhodove": [{"x": 25, "y": 20, "etiket": "КПП"}]}
    r, _ = run(data)
    w = json.loads(r.stdout)["preduprezhdeniya"] if r.returncode == 0 else []
    check(any("линия № 1" in x for x in w), "a line that starts nowhere is reported")
    check(any("смукателна" in x for x in w), "a nozzle on a suction line is dropped and reported")
    check(any("входът" in x for x in w), "a gate away from the fence is reported")


def test_bad_input():
    print("shema.py – bad input")
    for data, what in (({}, "no buildings"), ({"sgradi": [{"x": 0, "y": 0, "w": -3, "h": 2}]}, "a negative width"),
                       ({"sgradi": [{"x": 0, "y": 0, "w": 3, "h": 2}], "avtomobili": [{"x": 1, "y": 1, "vid": "tank"}]},
                        "an unknown vehicle"),
                       ({"sgradi": [{"x": 0, "y": 0, "w": 3, "h": 2}], "razklonitel": [{"x": 1, "y": 1, "patya": 5}]},
                        "a five-way splitter")):
        r, _ = run(data)
        check(r.returncode == 2 and "BAD_INPUT" in r.stderr, f"{what} → BAD_INPUT")


def test_situacionna_sheet():
    print("shema.py – the sheet of a situational scheme (Приложение № 2а)")
    data = json.load(open(os.path.join(HERE, "fixtures", "situacionna.json"), encoding="utf-8"))
    svg = os.path.join(tempfile.mkdtemp(), "s.svg")
    r, out = run(data, "--svg", svg)
    check(r.returncode == 0, "renders the sheet" + (": " + r.stderr[:200] if r.returncode else ""))
    if r.returncode:
        return
    res = json.loads(r.stdout)
    check(res["mashtab"] == "1:500", f"a standard scale that fits ({res['mashtab']})")
    check(res["preduprezhdeniya"] == [], f"a complete situation gives no warnings: {res['preduprezhdeniya']}")
    text = open(svg, encoding="utf-8").read()
    for name in ("Ситуационна схема", "№ на плана", "Собственик:", "Утвърдил / дата:", "М 1:500",
                 "С-150/5", "Т-100/4", "ПК-1", "-1 +2 · Ф1.1 · II ст."):
        check(name in text, f"the sheet shows „{name}“")
    for colour in ("#8b5a2b", "#d9a400", "#f28c00"):
        check(colour in text.lower(), f"the colour {colour} of чл. 9, ал. 9")
    bare = {"sgradi": [{"x": 0, "y": 0, "w": 20, "h": 10, "etiket": "Склад"}], "list": {}}
    r, _ = run(bare)
    w = json.loads(r.stdout)["preduprezhdeniya"] if r.returncode == 0 else []
    for what in ("етажност", "водопроводна мрежа", "улици", "електрическо табло", "водоизточници"):
        check(any(what in x for x in w), f"a bare sheet reports the missing „{what}“")
    r, _ = run({"sgradi": [{"x": 0, "y": 0, "w": 20, "h": 10}]})
    check(r.returncode == 0 and "етажност" not in r.stdout, "an ordinary scheme does not ask for the situation")


def test_situacionna_docx():
    print("situacionna.py – the .docx (Приложения № 2а и № 2б)")
    out = os.path.join(tempfile.mkdtemp(), "s.docx")
    r = subprocess.run([sys.executable, os.path.join(SKILL, "scripts", "situacionna.py"),
                        os.path.join(HERE, "fixtures", "situacionna.json"), "-o", out], capture_output=True, text=True)
    check(r.returncode == 0, "builds the document" + (": " + r.stderr[:300] if r.returncode else ""))
    if r.returncode:
        return
    check("DOC_CHECK" not in r.stderr, f"passes the common check (no bold, „–“, „№ 4“): {r.stderr[:200]}")
    from docx import Document
    doc = Document(out)
    check(len(doc.sections) == 2 and all(s.page_width > s.page_height for s in doc.sections),
          "two landscape pages – the graphic and the table part")
    t = doc.tables[-1]
    head = " ".join(c.text for c in t.rows[0].cells).replace("\u00ad", "")   # soft hyphens – invisible
    for name in ("Разстояние до обекта", "ГОРИМО НАТОВАРВАНЕ", "РИСКОВИ ВЕЩЕСТВА И МАТЕРИАЛИ", "Вид защита на служителите"):
        check(name in head, f"the table has „{name}“ (Приложение № 2б)")
    check(len(t.columns) == 13 and len(t.rows) >= 8, f"13 columns and room to write by hand ({len(t.rows)} rows)")
    check(t.rows[2].cells[0].text == "3,2" and t.rows[2].cells[1].text == "7", "the distance and the time on the first row")
    res = json.loads(r.stdout)
    check(res["preduprezhdeniya"] == [], f"no gaps for the complete example: {res['preduprezhdeniya']}")
    check(res["dxf"] and res["dxf"].endswith("s.dxf") and os.path.exists(res["dxf"]), "the graphic part also as .dxf beside it")
    fx = json.load(open(os.path.join(HERE, "fixtures", "situacionna.json"), encoding="utf-8"))
    if not fx["list"].get("fail"):
        import ezdxf
        texts = [e.dxf.text for e in ezdxf.readfile(res["dxf"]).modelspace().query("TEXT")]
        check("s.dxf" in texts, "„Име на файла“ in the title block is the .dxf's name")


def test_outline_building():
    print("shema.py – a building of any shape (kontur) and merged streets")
    data = {"sgradi": [{"kontur": [[0, 15], [41, 14], [53, 3], [43, -7], [34, 0], [1, 0]], "etiket": "Цех"}],
            "ulitsi": [{"tochki": [[-10, 25], [60, 25]], "shirina": 8, "ime": "бул. „Примерен“"},
                       {"tochki": [[30, 25], [30, 16]], "shirina": 5}]}
    svg = os.path.join(tempfile.mkdtemp(), "k.svg")
    r, _ = run(data, "--svg", svg)
    check(r.returncode == 0, "draws an outline" + (": " + r.stderr[:200] if r.returncode else ""))
    if r.returncode:
        return
    text = open(svg, encoding="utf-8").read()
    check(">53<" in text.replace(" ", "") or "53</text>" in text, "the overall length of the outline is dimensioned")
    x, y = shema.centroid([[0, 0], [10, 0], [10, 10], [0, 10]])
    check(abs(x - 5) < 1e-9 and abs(y - 5) < 1e-9, "the label goes to the centroid")
    r, _ = run({"sgradi": [{"kontur": [[0, 0], [1, 1]]}]})
    check(r.returncode == 2 and "kontur" in r.stderr, "an outline of two points → BAD_INPUT")


def test_floors_text():
    print("shema.py – the floors as чл. 8 writes them („-1 +2 +Т“)")
    check(shema.floors_text("+3") == "+3" and shema.floors_text("3") == "+3", "„+3“, „3“ → „+3“")
    check(shema.floors_text("3 ет.") == "+3", "„3 ет.“ → „+3“")
    check(shema.floors_text("-1 +2 +Т") == "-1 +2 +Т", "basement, floors and attic stay as чл. 8 writes them")
    check(shema.floors_text("1 подз. ет., 2 ет., тав. ет.") == "-1 +2 +Т", "the long form → чл. 8")
    check(shema.floors_text("") == "" and shema.floors_text("партер") == "партер", "other text stays as it is")

def test_label_avoids_fire():
    print("shema.py – the building's name is not under the fire")
    b = {"x": 0, "y": 0, "w": 40, "h": 10}
    x, _ = shema.label_point(b, [{"x": 25, "y": 0, "w": 15, "h": 10}])
    check(x < 25, f"the label moves to the free part ({x:.1f} m)")
    check(shema.label_point(b, []) == (20, 5), "without a fire – in the middle")


def test_kais_fields():
    print("shema.py – the cadastral background, the parcel and a hydrant by КС2005")
    import matplotlib.pyplot as mplt
    tmp = tempfile.mkdtemp()
    fon = os.path.join(tmp, "fon.png")
    mplt.imsave(fon, [[[0.9, 0.8, 0.6, 1.0]] * 4] * 4)
    x0, y0 = 431100.0, 4808800.0           # an origin in КС2005 – the hydrant's point is computed from it
    data = {"teren": [120, 90], "kais": {"x0": x0, "y0": y0},
            "imot": {"kontur": [[20, 20], [100, 20], [100, 70], [20, 70]], "etiket": "ПИ 99999.10.20"},
            "fon": {"png": fon, "ramka": [-20, -20, 140, 110]},
            "sgradi": [{"kontur": [[30, 30], [60, 30], [60, 45], [30, 45]], "etiket": "Склад", "etazhnost": "+1"}],
            "vodoiztochnitsi": [{"vid": "hidrant", "lat": 43.4125702, "lon": 24.6504731, "etiket": "ПХ"}]}
    r, out = run(data)
    check(r.returncode == 0 and os.path.exists(out), "draws with the background and the parcel" + (": " + r.stderr[:200] if r.returncode else ""))
    loaded, _ = shema.load(data)
    h = loaded["vodoiztochnitsi"][0]
    check(abs(h["x"] - 94.011) < 0.01 and abs(h["y"] - 97.561) < 0.01, "lat/lon with \"kais\" → metres in КС2005 from the origin")
    check(loaded["imot"]["etiket"] == "ПИ 99999.10.20" and loaded["fon"]["alpha"] == 0.35, "the parcel and the picture are kept")
    r, _ = run({**data, "fon": {"png": os.path.join(tmp, "missing.png"), "ramka": [0, 0, 1, 1]}})
    check(r.returncode == 0 and "фонът" in r.stdout, "a missing picture is a warning, not an error")
    r, _ = run({**data, "fon": {"png": fon}})
    check(r.returncode == 2 and "fon" in r.stderr, "a picture without its frame → BAD_INPUT")


def test_parcel_label():
    print("znatsi.py – the parcel's identifier inside the parcel, clear of the buildings")
    import znatsi
    kontur = [[0, 0], [100, 0], [100, 60], [40, 60], [40, 80], [0, 80]]
    bld = [[10, 55], [35, 55], [35, 78], [10, 78]]
    pos = znatsi.parcel_label_pos(kontur, 20, 3, [bld])
    check(pos is not None and znatsi._inside(pos, kontur), f"inside the parcel: {pos}")
    if pos:
        x, y = pos
        clear = not (x + 10 > 10 and x - 10 < 35 and y + 1.5 > 55 and y - 1.5 < 78)
        check(clear and y > 40, f"near the top and clear of the building: {pos}")
    check(znatsi.parcel_label_pos([[0, 0], [5, 0], [5, 5], [0, 5]], 20, 3) is None, "too small a parcel → None (above it)")


def test_dxf():
    print("shema.py – the DXF for AutoCAD / CorelDRAW")
    import ezdxf
    tmp = tempfile.mkdtemp()
    data = {"teren": [120, 90], "kais": {"x0": 431100.0, "y0": 4808800.0},
            "sgradi": [{"kontur": [[30, 30], [60, 30], [60, 45], [30, 45]], "etiket": "Склад", "etazhnost": "+1"}],
            "imot": {"kontur": [[20, 20], [100, 20], [100, 70], [20, 70]], "etiket": "ПИ 99999.10.20"},
            "ulitsi": [{"kontur": [[0, 75], [120, 75], [120, 88], [0, 88]], "ime": "бул. „Примерен“", "ime_pos": [60, 81]},
                       {"kontur": [[50, 0], [58, 0], [58, 75], [50, 75]]},
                       {"tochki": [[-10, 10], [130, 10]], "shirina": 6}],
            "vodoiztochnitsi": [{"vid": "hidrant", "x": 10, "y": 80, "etiket": "ПХ 70/80"}],
            "vodoprovod": [{"tochki": [[0, 80], [120, 80]], "diametar": "70/80"}]}
    r, out = run(data)
    dxf = os.path.splitext(out)[0] + ".dxf"
    check(r.returncode == 0 and os.path.exists(dxf), "a DXF is written beside the picture by default")
    doc = ezdxf.readfile(dxf)
    layers = {lay.dxf.name for lay in doc.layers}
    check({"SGRADI", "ULITSI", "VODA", "IMOT", "RAZMERI", "SEVER"} <= layers, "the layers by kind")
    check(doc.header["$INSUNITS"] == 6, "in metres")
    msp = doc.modelspace()
    xs = [v[0] for e in msp.query("LWPOLYLINE[layer=='SGRADI']") for v in e.get_points("xy")]
    check(xs and min(xs) == 431130.0, "with \"kais\" in КС2005 – the building lies where it is in the cadastre")
    lines = [((e.dxf.start.x, e.dxf.start.y), (e.dxf.end.x, e.dxf.end.y)) for e in msp.query("LINE[layer=='ULITSI']")]
    shared = [ln for ln in lines if abs(ln[0][1] - 4808875.0) < 1e-6 and abs(ln[1][1] - 4808875.0) < 1e-6
              and min(ln[0][0], ln[1][0]) >= 431150.0 - 1e-6 and max(ln[0][0], ln[1][0]) <= 431158.0 + 1e-6]
    check(not shared, "where two street parcels touch, there is no line between them")
    check(all(431100.0 - 1e-6 <= x <= 431220.0 + 1e-6 for ln in lines for x in (ln[0][0], ln[1][0])),
          "the streets are cut at the drawing's edge")
    texts = [e.dxf.text for e in msp.query("TEXT")]
    check("бул. „Примерен“" in texts and "ПХ 70/80" in texts and "С-70/80" in texts, "the names and labels as text")
    loaded, _ = shema.load({**data, "vodoprovod": [{"tochki": [[0, 80], [120, 80]], "diametar": "70/80", "natisk": "3–5"}]})
    check(loaded["vodoprovod"][0]["etiket"] == "С-70/80/3–5", "a size and a pressure range as written: С-70/80/3–5")
    loaded, _ = shema.load({**data, "vodoprovod": [{"tochki": [[0, 80], [120, 80]], "diametar": 150, "natisk": 0.5}]})
    check(loaded["vodoprovod"][0]["etiket"] == "С-150/5", "numbers: mm and MPa → bar")
    dims = [[e.dxf.text for e in doc.blocks.get(d.dxf.geometry) if e.dxftype() in ("MTEXT", "TEXT")] for d in msp.query("DIMENSION")]
    check(["30.00"] in dims or ["30"] in dims, f"dimensions in metres: {dims}")
    r, out = run(data, "--bez-dxf")
    check(not os.path.exists(os.path.splitext(out)[0] + ".dxf"), "--bez-dxf – none")


def test_rotation_and_wall_dims():
    print("shema.py – \"zavartane\" and dimensions along the walls (an invented building at 40°)")
    import math
    c, sn = math.cos(math.radians(40)), math.sin(math.radians(40))
    rect = [(0, 0), (60, 0), (60, 25), (0, 25)]
    k = [[round(50 + x * c - y * sn, 2), round(20 + x * sn + y * c, 2)] for x, y in rect]
    base = {"sgradi": [{"kontur": k, "etiket": "Склад"}],
            "vodoiztochnitsi": [{"vid": "hidrant", "x": 120, "y": 30}],
            "tekst": [{"x": 300, "y": 300, "tekst": "далеч"}]}
    dims = shema.wall_dimensions(shema.load(base)[0]["sgradi"][0], 1.0)
    check(sorted(t for _, _, t, _ in dims) == ["25", "60"], f"the walls, not the axes: {[t for _, _, t, _ in dims]}")
    d = shema.zavarti({**base, "zavartane": "avto"})
    check(abs(d["_zavartane"] + 40) < 0.2 and abs(d["_sever_ugal"] - 50) < 0.2,
          f"avto lays the long wall horizontally (turn {d['_zavartane']}°, north at {d['_sever_ugal']}°)")
    ys = sorted(round(p[1], 1) for p in d["sgradi"][0]["kontur"])
    check(ys[0] == ys[1] and ys[2] == ys[3], "the building is parallel to the axes after the turn")
    check(all(0 <= p[0] <= d["teren"][0] and 0 <= p[1] <= d["teren"][1] for p in d["sgradi"][0]["kontur"]),
          "the terrain is cut round the object")
    check(d["tekst"] == [], "a label left outside the cut terrain is dropped")
    check("zavartane" not in shema.zavarti(base), "without \"zavartane\" nothing changes")
    loaded = shema.load({**base, "prohodi": [{"x": 10, "y": 5, "shirina": 6}]})[0]
    check(loaded["prohodi"] == [{"x": 10.0, "y": 5.0, "shirina": 6.0, "ramena": 6.0}], "an entrance from the street is read")
    # the street edges put right by themselves (ulitsi_avto.py)
    street = {"kontur": [[0, 0], [100, 0], [100, 8], [0, 8]], "ime": "ул. „Примерна“"}
    one = shema.load({"teren": [100, 60], "sgradi": [{"x": 30, "y": 20, "w": 20, "h": 10}], "ulitsi": [street],
                      "prohodi": [{"x": 40, "y": 8, "shirina": 8}]})[0]
    arms = one["ulitsi_rab"]
    check(len(arms) == 2 and all(abs(a[0][1] - 8) < 0.01 and a[1][1] > a[0][1] + 5 for a in arms),
          f"an entrance from the street gets two arms inwards: {arms}")
    none = shema.load({"teren": [100, 60], "sgradi": [{"x": 30, "y": 20, "w": 20, "h": 10}], "ulitsi": [street],
                       "prohodi": [{"x": 40, "y": 8, "shirina": 8, "ramena": 0}]})[0]
    check(none["ulitsi_rab"] == [], "\"ramena\": 0 – no arms")
    cross = shema.load({"teren": [100, 60], "sgradi": [{"x": 30, "y": 30, "w": 20, "h": 10}],
                        "ulitsi": [{"kontur": [[0, 10], [40, 10], [40, 18], [0, 18]], "ime": ""},
                                   {"tochki": [[44, 9], [44, 19]], "shirina": 7, "ime": ""}]})[0]
    check(any(abs(a[0] - 40) < 0.01 and abs(b[0] - 40) < 0.01 for a, b in cross["ulitsi_skrij"]),
          f"the cross-cut of a cadastral street into a road of OpenStreetMap is hidden: {cross['ulitsi_skrij']}")
    check(cross["ulitsi"][1].get("bez_ruba") == "desen" or cross["ulitsi"][1].get("bez_ruba") == "lyav",
          "the inner edge of the OpenStreetMap road at the junction is left out")
    plain = shema.load({"teren": [100, 60], "sgradi": [{"x": 30, "y": 30, "w": 20, "h": 10}], "avto_ulitsi": False,
                        "ulitsi": [street], "prohodi": [{"x": 40, "y": 8, "shirina": 8}]})[0]
    check(plain["ulitsi_rab"] == [], "\"avto_ulitsi\": false – nothing added")
    # a street along the frame shows both its edges
    grown = shema.whole_streets({"ulitsi": [{"kontur": [[-50, 50], [150, 50], [150, 70], [-50, 70]]}]}, 0, 0, 100, 60)
    check(abs(grown[3] - 73) < 0.01, f"the terrain reaches the other edge of the street: {grown}")
    far = shema.whole_streets({"ulitsi": [{"kontur": [[-50, 50], [150, 50], [150, 130], [-50, 130]]}]}, 0, 0, 100, 60)
    check(far == (0, 0, 100, 60), "not when the other edge is far away")
    d2 = shema.zavarti({**base, "zavartane": "avto", "prohodi": [{"x": 50, "y": 20}]})
    check(0 <= d2["prohodi"][0]["x"] <= d2["teren"][0], "the entrance turns and shifts with the drawing")
    fixed = shema.load({**base, "ulitsi_skrij": [[[0, 0], [5, 0]]], "ulitsi_rab": [[[0, 0], [2, 3], [5, 5]]]})[0]
    check(len(fixed["ulitsi_skrij"]) == 1 and len(fixed["ulitsi_rab"][0]) == 3, "street-edge corrections are read")
    r, out = run({**base, "ulitsi": [{"tochki": [[0, -5], [150, -5]], "shirina": 8}],
                  "ulitsi_skrij": [[[20, -1], [30, -1]]], "ulitsi_rab": [[[20, -1], [25, 2], [30, -1]]]})
    check(r.returncode == 0, "draws the street-edge corrections" + (": " + r.stderr[:200] if r.returncode else ""))
    one = shema.load({**base, "ulitsi": [{"tochki": [[0, -5], [50, -5]], "shirina": 7, "bez_ruba": "desen"}]})[0]
    check(one["ulitsi"][0]["bez_ruba"] == "desen", "a band without one edge is read")
    r, out = run({**base, "ulitsi": [{"tochki": [[0, -5], [150, -5]], "shirina": 7, "bez_ruba": "lyav"}]})
    check(r.returncode == 0, "draws a band without one edge" + (": " + r.stderr[:200] if r.returncode else ""))
    grass = shema.load({**base, "trevni": [{"kontur": [[0, 0], [10, 0], [10, 5]]}]})[0]
    check(len(grass["trevni"]) == 1, "a grass area is read")
    r, out = run({**base, "trevni": [{"kontur": [[0, 0], [10, 0], [10, 5]]}], "legenda": True,
                  "zavartane": 30})
    check(r.returncode == 0, "draws grass areas" + (": " + r.stderr[:200] if r.returncode else ""))
    fill = shema.load({**base, "ulitsi": [{"kontur": [[0, 0], [10, 0], [10, 5]], "bez_ruba": True}]})[0]
    check(fill["ulitsi"][0]["bez_ruba"] is True, "a carriageway area without an edge is read")
    r, out = run({**base, "ulitsi": [{"kontur": [[0, 0], [10, 0], [10, 5]], "bez_ruba": True}],
                  "trevni": [{"kontur": [[0, 0], [12, 0], [12, 6]]}]})
    check(r.returncode == 0, "draws a carriageway area without an edge" + (": " + r.stderr[:200] if r.returncode else ""))
    r, out = run({**base, "zavartane": 30})
    check(r.returncode == 0, "renders a turned scheme" + (": " + r.stderr[:200] if r.returncode else ""))


def test_water_signs():
    print("shema.py – the water signs of Приложение № 6 (река, езеро, подстъп, мост)")
    base = {"sgradi": [{"x": 0, "y": 0, "w": 10, "h": 6}], "teren": [80, 60], "legenda": True}
    water = {"reki": [{"tochki": [[0, 30], [40, 34], [80, 30]], "shirina": 5, "ime": "р. Примерна",
                       "barazhi": [[60, 32]]}],
             "ezera": [{"kontur": [[10, 40], [30, 42], [28, 55], [12, 52]], "ime": "Езеро"}],
             "podstapi": [{"x": 50, "y": 24, "ugal": 90}],
             "mostove": [{"x": 30, "y": 33, "ugal": 5, "shirina": 5}]}
    data, warn = shema.load({**base, **water})
    check(len(data["reki"]) == 1 and data["reki"][0]["shirina"] == 5 and data["reki"][0]["barazhi"] == [(60.0, 32.0)],
          "a river is read with its width and barrage")
    check(len(data["ezera"]) == 1 and len(data["podstapi"]) == 1 and len(data["mostove"]) == 1,
          "a lake, an access place and a bridge are read")
    keys = shema.legend_keys(data, 20)[0]
    check(all(k in keys for k in ("reka", "ezero", "podstap", "most_voda")), f"the legend has the water signs: {keys}")
    tmp = tempfile.mkdtemp()
    src, out = os.path.join(tmp, "in.json"), os.path.join(tmp, "out.svg")
    json.dump({**base, **water}, open(src, "w", encoding="utf-8"), ensure_ascii=False)
    r = subprocess.run([sys.executable, SCRIPT, src, "-o", os.path.join(tmp, "out.png"), "--svg", out],
                       capture_output=True, text=True)
    check(r.returncode == 0, "draws the water signs" + (": " + r.stderr[:200] if r.returncode else ""))
    if not r.returncode:
        svg = open(out, encoding="utf-8").read()
        for name in ("Река, канал", "Езеро, микроязовир", "Подстъп до водоизточник", "Мост, от който"):
            check(name in svg, f"the legend names „{name}“")
    import znatsi
    lines = znatsi.river_lines([(0, 0), (40, 0)], 4, 3.0)
    check(len(lines) == 4 and all(abs(p[1]) == 2 for p in lines[0] + lines[1]),
          "a river: two straight banks at half the width")
    check(all(abs(p[1]) > 2 for p in lines[2] + lines[3]), "and the wavy lines outside them, never inside the water")
    r, out = run({**base, **water, "zavartane": 25})
    check(r.returncode == 0, "the water signs turn with the scheme" + (": " + r.stderr[:200] if r.returncode else ""))
    try:
        shema.load({**base, "reki": [{"tochki": [[0, 0]]}]})
        refused = False
    except SystemExit:
        refused = True
    check(refused, "a river with one point is refused")


def test_street_names_inside():
    print("znatsi.py / kais.py – the street name with „ул.“, inside the street between its lines")
    sys.path.insert(0, os.path.join(SKILL, "_shared", "scripts"))
    from kais import street_name
    check(street_name("Иван Миндиликов") == "ул. „Иван Миндиликов“", "„ул.“ in front of a bare street name")
    check(street_name("бул. Русе") == "бул. „Русе“", "a boulevard keeps its kind")
    check(street_name("Дружба 3", ulitsa=False) == "Дружба 3", "a place name gets no „ул.“")
    import znatsi
    street = [(0, 0), (60, 0), (60, 8), (0, 8)]                     # an 8 m wide street, 60 m long
    fit = znatsi.fit_street_label(street, "ул. „Примерна“", (30, 20), 0, 7, 3.78, (0, -20, 60, 40))
    check(fit is not None and 0 < fit[0][1] < 8, f"a name given outside goes inside the street: {fit}")
    narrow = [(0, 0), (60, 0), (60, 1), (0, 1)]
    check(znatsi.fit_street_label(narrow, "ул. „Примерна“", (30, 0.5), 0, 7, 3.78, (0, -20, 60, 40)) is None,
          "no place in a street too narrow for the name")
    pipe = [[(0, 4), (60, 4)]]
    fit = znatsi.fit_street_label([(0, 0), (60, 0), (60, 12), (0, 12)], "ул. „Примерна“", (30, 4), 0, 7, 3.78,
                                  (0, -20, 60, 40), obstacles=pipe)
    check(fit is not None and abs(fit[0][1] - 4) > 2, f"the name moves off the water main in the street: {fit}")


def test_naves():
    data = {"teren": [60, 40], "sgradi": [{"x": 5, "y": 5, "w": 10, "h": 8, "etiket": "Магазин", "etazhnost": "+1"},
                                          {"x": 25, "y": 5, "w": 10, "h": 20, "etiket": "Навес над\\nколонките",
                                           "naves": True, "kategoriya": "Ф5А"}]}
    loaded, _ = shema.load(data)
    shop, naves = loaded["sgradi"]
    check(shema.building_lw(naves) == shema.building_lw(shop) / 2, "a canopy is drawn half as thick as a building")
    gaps = shema.situation_gaps(loaded)
    check(not any("Навес" in g for g in gaps), f"no floors / fire resistance asked of a canopy: {gaps}")
    no_cat = shema.load({**data, "sgradi": [data["sgradi"][0], {**data["sgradi"][1], "kategoriya": ""}]})[0]
    check(any("Навес над колонките" in g and "категория" in g and "етажност" not in g
              for g in shema.situation_gaps(no_cat)), "a canopy still asks for its category, under its whole label")
    r, _ = run(data)
    check(r.returncode == 0, f"renders a scheme with a canopy: {r.stderr}")


if __name__ == "__main__":
    test_naves()
    test_street_names_inside()
    test_water_signs()
    test_fixture()
    test_defaults()
    test_minimal_and_colour()
    test_warnings()
    test_bad_input()
    test_label_avoids_fire()
    test_floors_text()
    test_outline_building()
    test_kais_fields()
    test_parcel_label()
    test_dxf()
    test_situacionna_sheet()
    test_situacionna_docx()
    test_library()
    test_rotation_and_wall_dims()
    print("FAILURES: " + "; ".join(failures) if failures else "ALL OK")
    sys.exit(1 if failures else 0)
