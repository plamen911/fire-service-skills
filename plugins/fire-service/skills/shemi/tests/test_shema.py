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
    test_minimal_and_colour()
    test_warnings()
    test_bad_input()
    test_label_avoids_fire()
    print("FAILURES: " + "; ".join(failures) if failures else "ALL OK")
    sys.exit(1 if failures else 0)
