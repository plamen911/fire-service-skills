#!/usr/bin/env python3
"""Tests for etazh_ot_plan.py – a floor from a photo of an evacuation plan, fitted to the cadastre outline.
Run from the skill folder:
    python3 tests/test_etazh_ot_plan.py
An invented building, not a real one.
"""
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(SKILL, "scripts"))

from etazh_ot_plan import build  # noqa: E402

failures = []


def check(cond, msg):
    print(("  ok  " if cond else "  FAIL ") + msg)
    if not cond:
        failures.append(msg)


def site(angle_deg=30.0):
    """An L-shaped shop, 60 x 30 m with a 10 x 10 m wing cut out of one corner, turned by `angle_deg`."""
    a = math.radians(angle_deg)
    local = [(0, 0), (60, 0), (60, 30), (10, 30), (10, 20), (0, 20)]
    ring = [[round(100 + x * math.cos(a) - y * math.sin(a), 3), round(100 + x * math.sin(a) + y * math.cos(a), 3)]
            for x, y in local]
    return {"kais": {"x0": 400000, "y0": 4800000, "imot": "1.2.3"},
            "sgradi": [{"kais_id": "1.2.3.1", "etiket": "Магазин", "etazhnost": "+1", "kontur": ring}],
            "ulitsi": []}


def plan(mirror=False, turn=0):
    """The same shop on a photo: 10 px per metre, y down; the wall plan may be mirrored or turned."""
    def px(x, y):                                       # metres of the plan → pixels of the photo
        X, Y = 50 + x * 10, 50 + (30 - y) * 10
        if mirror:
            X = 50 + 600 - (X - 50)
        for _ in range(turn // 90):
            X, Y = Y, 50 + 600 - (X - 50)
        return [X, Y]
    out = [(0, 0), (60, 0), (60, 30), (10, 30), (10, 20), (0, 20)]
    hall = [(10, 0), (60, 0), (60, 30), (10, 30)]
    store = [(0, 0), (10, 0), (10, 20), (0, 20)]
    return {"etazh": 1, "kontur_px": [px(*p) for p in out],
            "pomeshtenia": [{"ime": "Търговска зала", "kontur_px": [px(*p) for p in hall],
                             "vrati": [{"x": px(35, 0)[0], "y": px(35, 0)[1], "shirina": 2, "vanshen": True}]},
                            {"ime": "Склад", "kontur_px": [px(*p) for p in store],
                             "vrati": [{"x": px(10, 10)[0], "y": px(10, 10)[1]}]}],
            "tabla": [px(2, 2)]}


def test_fit():
    print("fit to the cadastre outline")
    pod, info = build(plan(), site())
    check(info["savpadenie_kais"] > 0.98, f"plan fits the outline (IoU {info['savpadenie_kais']})")
    areas = info["pomeshtenia"]
    check(abs(areas["Търговска зала"] - 1500) < 15, f"hall 50 x 30 = 1500 m² ({areas['Търговска зала']})")
    check(abs(areas["Склад"] - 200) < 5, f"store 10 x 20 = 200 m² ({areas['Склад']})")
    hall = pod["pomeshtenia"][0]
    check(hall["razmeri_m"][0] > 49 and hall["razmeri_m"][1] > 29, f"hall dimensions {hall['razmeri_m']}")
    check(hall["otvori"][0]["vanshen"] is True, "outer door kept")
    check(pod["obekti"] and pod["obekti"][0]["etiket"] == "Ел.", "electrical panel")
    check(not pod.get("_uslovna"), "not a conditional floor")
    for key in ("podlozhka", "tekst", "pomeshtenia", "zavartane", "_etazh", "_kais"):
        check(key in pod, f"output has {key} (same as cdr_import.py / uslovni_etazhi.py)")


def test_orientations():
    print("a mirrored or turned wall plan is laid the right way")
    ref, _ = build(plan(), site())
    for mirror, turn in ((True, 0), (False, 180), (False, 90), (True, 270)):
        pod, info = build(plan(mirror, turn), site())
        a = ref["pomeshtenia"][1]["tsentar"]
        b = pod["pomeshtenia"][1]["tsentar"]
        check(math.dist(a, b) < 1.0 and info["savpadenie_kais"] > 0.98,
              f"mirror={mirror} turn={turn}: the store lands in the same place ({math.dist(a, b):.2f} m)")


def test_bad_outline():
    print("a plan that does not fit is reported")
    e = plan()
    e["kontur_px"] = [[50, 350], [650, 350], [350, 50]]                    # a triangle – not this building
    _, info = build(e, site())
    check(info["savpadenie_kais"] < 0.85 and info["preduprezhdeniya"], "low fit gives a warning")


if __name__ == "__main__":
    test_fit()
    test_orientations()
    test_bad_outline()
    print("\nFAILED: " + "; ".join(failures) if failures else "\nall ok")
    sys.exit(1 if failures else 0)
