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
    check('width="714' in svg or 'width="714.' in svg, "the drawing is as wide as the landscape text (25.2 cm)")


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


def test_label_avoids_fire():
    print("shema.py – the building's name is not under the fire")
    b = {"x": 0, "y": 0, "w": 40, "h": 10}
    x, _ = shema.label_point(b, [{"x": 25, "y": 0, "w": 15, "h": 10}])
    check(x < 25, f"the label moves to the free part ({x:.1f} m)")
    check(shema.label_point(b, []) == (20, 5), "without a fire – in the middle")


if __name__ == "__main__":
    test_fixture()
    test_defaults()
    test_minimal_and_colour()
    test_warnings()
    test_bad_input()
    test_label_avoids_fire()
    test_library()
    print("FAILURES: " + "; ".join(failures) if failures else "ALL OK")
    sys.exit(1 if failures else 0)
