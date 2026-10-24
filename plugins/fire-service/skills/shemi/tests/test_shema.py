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
                 "С-150/5", "Т-100/4", "ПК-1", "1 подз. ет., 2 ет. · Ф1.1 · II ст."):
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
    head = " ".join(c.text for c in t.rows[0].cells)
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
    print("shema.py – the floors as „N ет.“")
    check(shema.floors_text("+3") == "3 ет.", "„+3“ → „3 ет.“")
    check(shema.floors_text("-1 +2 +Т") == "1 подз. ет., 2 ет., тав. ет.", "basement, floors and attic")
    check(shema.floors_text("3 ет.") == "3 ет." and shema.floors_text("") == "", "other text stays as it is")


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


if __name__ == "__main__":
    test_fixture()
    test_defaults()
    test_minimal_and_colour()
    test_warnings()
    test_bad_input()
    test_label_avoids_fire()
    test_floors_text()
    test_outline_building()
    test_kais_fields()
    test_dxf()
    test_situacionna_sheet()
    test_situacionna_docx()
    test_library()
    print("FAILURES: " + "; ".join(failures) if failures else "ALL OK")
    sys.exit(1 if failures else 0)
