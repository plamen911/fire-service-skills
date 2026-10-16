#!/usr/bin/env python3
"""Tests for _shared/scripts/svoistva.py and the data in _shared/svoistva/. Run from the skill folder:
    python3 tests/test_svoistva.py
No network: the values are checked against what is in the table, and a few are pinned to the cards."""
import csv
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
SCRIPT = os.path.join(SKILL, "_shared", "scripts", "svoistva.py")
sys.path.insert(0, os.path.dirname(SCRIPT))
import svoistva as s  # noqa: E402

failures = []


def check(cond, msg):
    print(("  ok  " if cond else "  FAIL ") + msg)
    if not cond:
        failures.append(msg)


def run(*args):
    return subprocess.run([sys.executable, SCRIPT, *args], capture_output=True, text=True)


def test_data():
    print("данните")
    rows = [r for r in s.stoinosti() if r["kluch"].startswith("icsc:")]
    check(len(rows) >= 25, f"table has the substances ({len(rows)})")
    keys = [r["kluch"] for r in rows]
    check(len(keys) == len(set(keys)), "keys are unique")
    num = re.compile(r"^[<>~]?-?\d+(\.\d+)?(-{1,2}\d+(\.\d+)?)?$")
    for r in rows:
        where = r["kluch"]
        check(re.fullmatch(r"icsc:\d{4}", r["kluch"]) is not None, f"{where}: key format")
        check(r["url"].endswith(f"p_card_id={r['kluch'][5:]}&p_version=2"), f"{where}: url points to its own card")
        check(re.fullmatch(r"\d{4}-\d{2}-\d{2}", r["proveren"]) is not None, f"{where}: date it was checked")
        check(re.fullmatch(r"[а-я]+ \d{4} г\.", r["karta_versiya"]) is not None, f"{where}: card version")
        check(r["plamna_metod"] in ("", "з.т.", "о.т."), f"{where}: flash point method")
        check(r["sastoyanie"] in ("течност", "газ", "твърдо вещество"), f"{where}: state")
        for c in ("plamna", "samovazpl", "kgv", "vgv", "kipene"):
            check(not r[c] or num.match(r[c]) is not None, f"{where}: {c} „{r[c]}“ is a number or range")
        check(bool(r["plamna"] or r["samovazpl"] or r["kgv"]), f"{where}: has at least one fire property")
    # pinned to the cards (ICSC, checked by hand against chemicalsafety.ilo.org)
    pin = {"icsc:1561": ("52", "з.т.", "254-285", "0.6", "6.5"), "icsc:1400": ("<-21", "", "~250", "1.3", "7.1"),
           "icsc:0087": ("-18", "з.т.", "465", "2.2", "13"), "icsc:0319": ("-104", "", "450", "2.1", "9.5")}
    by = {r["kluch"]: r for r in rows}
    for k, v in pin.items():
        r = by.get(k, {})
        check((r.get("plamna"), r.get("plamna_metod"), r.get("samovazpl"), r.get("kgv"), r.get("vgv")) == v,
              f"{k} equals its card")


def test_lookup():
    print("търсенето")
    names = lambda q: [r["ime"] for r in s.tarsi(q)]  # noqa: E731
    check(names("нафта") == ["дизелово гориво"], "colloquial name → diesel")
    check(names("Дизел") == ["дизелово гориво"], "case does not matter")
    check(sorted(names("пропан-бутан")) == ["бутан", "пропан"], "propane-butane → both gases")
    check(names("67-64-1") == ["ацетон"], "CAS")
    check(names("1561") == ["дизелово гориво"], "card number")
    check(len(names("ксилен")) == 3, "xylene → the three isomers")
    try:
        s.tarsi("битумна хидроизолация")
        check(False, "no value for an unknown substance")
    except s.Problem as e:
        check(str(e).startswith("NOT_FOUND") and "по памет" in str(e), "unknown substance → NOT_FOUND, not a guess")
    f = s.formatirai(s.tarsi("бензин")[0])
    check(f["plamna"] == "под -21 °C" and f["samovazpl"] == "около 250 °C", "„<“ and „~“ in words")
    check(f["granitsi"] == "1,3–7,1 % (об.)", "decimal comma, en dash in ranges")
    check(s.formatirai(s.tarsi("нафта")[0])["plamna"] == "52 °C, затворен тигел", "method written out")
    check(s.formatirai(s.tarsi("водород")[0])["plamna"] == "няма – горим газ", "flammable gas has no flash point")
    r = run("нафта")
    check(r.returncode == 0 and "[[icsc:1561]]" in r.stdout and "сверена на" in r.stdout, "CLI gives marker and literature line")
    r = run("битумна хидроизолация")
    check(r.returncode == 2 and "NOT_FOUND" in r.stderr, "CLI: NOT_FOUND with exit code 2")
    r = run("--iztochnitsi")
    check(r.returncode == 0 and "chochev" in r.stdout and "винаги" in r.stdout, "CLI lists the source keys")
    j = json.loads(run("ацетон", "--json").stdout)
    check(j[0]["iztochnik"]["kratko"] == "ICSC 0087", "--json carries the source")


def test_citiraj():
    print("позоваванията")
    t, lit, used = s.citiraj("А е 52 °C [[icsc:1561]]. Б [[chochev: прил. № 7, с. 223]], пак [[icsc:1561]].")
    check(t == "А е 52 °C (ICSC 1561). Б (Чочев, 2003, прил. № 7, с. 223), пак (ICSC 1561).", "markers rendered")
    check(len(lit) == 4 and "Симеонов" in lit[0] and "ICSC 1561" in lit[2] and "Чочев" in lit[3],
          "mandatory first, then cited in order, each once")
    check(lit[-1].endswith(".") and all(x.endswith(";") for x in lit[:-1]), "punctuation of the list")
    t, lit, _ = s.citiraj("Ръчно (Чочев, 2003, прил. № 2) и [[icsc:0087; simeonov]].")
    check(t.endswith("(ICSC 0087; Симеонов, 2023)."), "several sources in one marker")
    check(any("Чочев" in x for x in lit), "a hand-typed reference is listed too")
    for bad, why in (("[[nqma]]", "unknown key"), ("[[icsc:9999]]", "card not in the table"),
                     ("(ICSC 9999)", "hand-typed unknown card")):
        try:
            s.citiraj(f"x {bad}.")
            check(False, f"{why} stops")
        except s.Problem:
            check(True, f"{why} stops")
    _, lit, _ = s.citiraj("x", dop_literatura=["„Методическо ръководство за установяване на причините за "
                                               "възникване на пожари”, НПИПАБ – НСПБЗН – МВР, гр. София, 2007 г.;"])
    check(len(lit) == 2, "an extra line that repeats a listed source is dropped")
    check(s.bez_iztochnik("Пожарът е 900 °C. Пламната е 52 °C [[icsc:1561]].") == ["Пожарът е 900 °C."],
          "a temperature without a marker is reported")


def test_katalog():
    print("каталогът")
    k = s.katalog()
    for key, v in k["iztochnitsi"].items():
        check(re.fullmatch(r"[a-z0-9][a-z0-9-]*", key) is not None, f"{key}: key format")
        check(bool(v.get("kratko")) and v.get("palno", "").endswith(";"), f"{key}: short and full form")
    check([x for x, v in k["iztochnitsi"].items() if v.get("vinagi")] == ["simeonov", "metodichesko-rakovodstvo"],
          "mandatory sources: Симеонов and the Методическо ръководство")
    for p, sh in k["_shabloni"].items():
        with open(os.path.join(SKILL, "_shared", "svoistva", sh["tablitsa"]), encoding="utf-8") as f:
            header = next(csv.reader(f))
        for field in re.findall(r"\{(\w+)\}", sh["palno"] + sh["kratko"]):
            check(field in header or field == "id", f"{p}: template field „{field}“ exists")


def test_masla_prahove():
    print("маслата (CHRIS) и праховете (GESTIS-STAUB-EX)")
    rows = s.stoinosti()
    keys = [r["kluch"] for r in rows]
    check(len(keys) == len(set(keys)), "keys unique across all tables")
    masla = [r for r in rows if r["kluch"].startswith("chris:")]
    prahove = [r for r in rows if r["kluch"].startswith("gestis-staub:")]
    check(len(masla) >= 8 and len(prahove) >= 30, f"{len(masla)} oils, {len(prahove)} dust samples")
    for r in masla:
        for c, label in (("plamna", "Flash Point"), ("samovazpl", "Auto Ignition Temperature")):
            m = re.search(re.escape(label) + r": (\d+)°F", r["izhodni"])
            check(bool(m) == bool(r[c]), f"{r['kluch']}: {c} present exactly when the card has it")
            if m:
                check(r[c] == str(round((int(m.group(1)) - 32) * 5 / 9)), f"{r['kluch']}: {c} = °F from the card in °C")
        check(r["url"].endswith(r["kluch"][6:].upper() + ".pdf"), f"{r['kluch']}: url points to its own card")
    for r in prahove:
        check(r["url"].endswith(f"nr={r['kluch'][13:]}&lang=e"), f"{r['kluch']}: url points to its own record")
        check(r["zapalvane_metod"] in ("G-G", "BAM", ""), f"{r['kluch']}: method")
        check(bool(r["zapalvane_oblak"] or r["tleene_sloy"]), f"{r['kluch']}: has a temperature")
        check(not r["tleene_sloy"] or re.fullmatch(r"\d+|n\.g\.u\. ?\d+|melts", r["tleene_sloy"]) is not None,
              f"{r['kluch']}: smouldering „{r['tleene_sloy']}“ is a known form")
    by = {r["kluch"]: r for r in rows}
    check((by["chris:osb"]["plamna"], by["chris:osb"]["plamna_metod"], by["chris:osb"]["izhodni"]) ==
          ("282", "з.т.", "Flash Point: 540°F C.C.; Auto Ignition Temperature: 833°F"), "chris:osb equals its card")
    check((by["gestis-staub:2213"]["zapalvane_oblak"], by["gestis-staub:2213"]["tleene_sloy"]) == ("470", "310"),
          "gestis-staub:2213 (straw) equals its record")
    f = s.formatirai(by["chris:ols"])
    check(f["plamna"] == "279 °C, открит тигел (535 °F в картата)", "oil: °C, method and the °F of the card")
    check(s.formatirai(by["gestis-staub:2092"])["tleene_sloy"] == "не тлее до 450 °C", "„n.g.u.“ in words")
    check(s.formatirai(by["gestis-staub:357"])["tleene_sloy"].startswith("топи се"), "„melts“ in words")
    check(len(s.tarsi("слама")) == 2 and all(r["vid"] == "прах" for r in s.tarsi("слама")), "straw → both samples")
    check({r["ime"] for r in s.tarsi("олио")} >= {"растително олио (общо)", "соево олио"}, "„олио“ → the oils")
    t, lit, _ = s.citiraj("Слама [[gestis-staub:2213]], олио [[chris:ovg]].")
    check(t == "Слама (GESTIS-STAUB-EX, № 2213), олио (CHRIS OVG).", "dust and oil markers rendered")
    check("staubex.ifa.dguv.de/explokomp.aspx?nr=2213" in lit[2] and "chris/OVG.pdf" in lit[3], "their literature lines")
    _, lit, _ = s.citiraj("Ръчно (CHRIS OSB) и (GESTIS-STAUB-EX, № 2176).")
    check(len(lit) == 4, "hand-typed CHRIS and GESTIS references are listed")


if __name__ == "__main__":
    test_data()
    test_masla_prahove()
    test_lookup()
    test_citiraj()
    test_katalog()
    print("\nALL PASS" if not failures else f"\n{len(failures)} FAILED")
    sys.exit(1 if failures else 0)
