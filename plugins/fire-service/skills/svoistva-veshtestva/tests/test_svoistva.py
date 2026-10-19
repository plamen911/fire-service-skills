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
        check(bool(r["plamna"] or r["samovazpl"] or r["kgv"] or r.get("topene")), f"{where}: has at least one property")
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
    check(j[0]["citat"]["kratko"] == "ICSC 0087" and j[0]["marker"] == "[[icsc:0087]]", "--json carries the source")


def test_citiraj():
    print("позоваванията")
    t, lit, used = s.citiraj("А е 52 °C [[icsc:1561]]. Б [[chochev: прил. № 7, с. 223]], пак [[icsc:1561]].")
    check(t == "А е 52 °C (ICSC 1561). Б (Чочев, 2003, прил. № 7), пак (ICSC 1561).", "markers rendered, no page in the text")
    t, _, _ = s.citiraj("x [[korolchenko: ч. II, с. 395; korolchenko: ч. I, с. 538]].")
    check(t == "x (Корольченко, 2004).", "same source twice in one marker → once, author and year only")
    check(len(lit) == 4 and "Симеонов" in lit[0] and "ICSC 1561" in lit[2] and "Чочев" in lit[3],
          "mandatory first, then cited in order, each once")
    check(lit[-1].endswith(".") and all(x.endswith(";") for x in lit[:-1]), "punctuation of the list")
    t, lit, _ = s.citiraj("Ръчно (Чочев, 2003, прил. № 2) и [[icsc:0087; simeonov]].")
    check(t.endswith("(ICSC 0087; Симеонов, 2007)."), "several sources in one marker")
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


def test_literatura():
    print("стойностите от книги и статии")
    rows = [r for r in s.stoinosti() if r["vid"] == "литература"]
    k = s.katalog()["iztochnitsi"]
    check(len(rows) >= 10, f"{len(rows)} rows")
    for r in rows:
        check(r["iztochnik"] in k, f"{r['id']}: source „{r['iztochnik']}“ is in the catalogue")
        check(bool(r["mesto"]) and ";" not in r["mesto"] and re.search(r"(с|т|гл)\. \d", r["mesto"]) is not None,
              f"{r['id']}: page given, no „;“ („{r['mesto']}“)")
        check(bool(r["stoinost"] and r["usloviya"] and r["pokazatel"]), f"{r['id']}: value, conditions, property")
        t, lit, _ = s.citiraj("x " + s.marker(r) + ".")
        check(t == f"x ({k[r['iztochnik']]['kratko']}).", f"{r['id']}: its marker renders as author and year")
        check(any(k[r["iztochnik"]]["palno"].rstrip(";") in l for l in lit), f"{r['id']}: its source is listed")
    found = s.tarsi("дърво")
    check(found[0]["vid"] == "литература", "„дърво“ → solid wood first, not its dust")
    check(not any(r["vid"] == "прах" for r in found), "„дърво“ does not return dust samples")
    pin = {r["id"]: r for r in rows}
    check(pin["darvo-01"]["stoinost"] == "около 250 °C" and "с. 184" in pin["darvo-01"]["mesto"], "darvo-01 equals Table 5")
    check((pin["darvo-02"]["stoinost"], pin["darvo-03"]["stoinost"]) == ("300–310 °C", "350–365 °C"),
          "hardwood/softwood equal Table 5")
    kor = [r for r in rows if r["iztochnik"] == "korolchenko"]
    check(len(kor) >= 20 and all(re.fullmatch(r"ч\. II?, с\. \d+", r["mesto"]) for r in kor),
          "Корольченко: every row has its part and page")
    check(pin["kor-07"]["stoinost"].startswith("самовъзпламеняване на слой прах 180 °C") and pin["kor-07"]["mesto"] == "ч. II, с. 395",
          "сено equals ч. II, с. 395")
    check(pin["kor-08"]["stoinost"].startswith("пламна температура 205 °C"), "слънчогледово олио equals ч. II, с. 58")
    check(all(pin[f"nwcg-0{i}"]["mesto"] == "с. 208" for i in range(1, 5)), "NWCG PMS 412: Refraction is on p. 208")
    check("цветно стъкло не запалват" in pin["nwcg-02"]["stoinost"], "flat and colored glass do not ignite")
    check(any(r["iztochnik"] == "nwcg-pms412" for r in s.tarsi("стъкло")), "„стъкло“ finds the lens effect")
    check(not re.search(r"\d+\s*пъти", " ".join(r["stoinost"] for r in rows if r["iztochnik"] == "nwcg-pms412")),
          "no concentration factor – the guide gives none")
    check({r.get("iztochnik") for r in s.tarsi("олио")} >= {"korolchenko"}, "„олио“ → also Корольченко")


def test_proveri():
    print("проверката число ↔ източник")
    check(s.proveri_chisla("Дизелът е с пламна температура 52 °C [[icsc:1561]].") == [], "right number passes")
    check(len(s.proveri_chisla("Дизелът е с пламна температура 62 °C [[icsc:1561]].")) == 1, "wrong number caught")
    check(s.proveri_chisla("Сламата тлее при 310 °C [[gestis-staub:2213]].") == [], "dust record checked")
    check(s.proveri_chisla("Олиото – 321 °C [[chris:ovg]].") == [], "CHRIS °C checked")
    check(s.proveri_chisla("Сеното тлее при 204 °C [[korolchenko: ч. II, с. 395]].") == [], "book page checked")
    check(len(s.proveri_chisla("Сеното тлее при 214 °C [[korolchenko: ч. II, с. 395]].")) == 1, "wrong number on a page caught")
    check(len(s.proveri_chisla("Сеното тлее при 204 °C [[korolchenko: ч. II, с. 396]].")) == 1, "wrong page caught")
    check(s.proveri_chisla("Алуминият – 600 ÷ 660 °C [[chochev: прил. № 7, с. 223]].") == [], "no data for Чочев – not checked")
    check(s.proveri_chisla("Огнището е в ъгъла [[simeonov]].") == [], "no number – nothing to check")
    ilb = {"ilb-r": {"kratko": "ИЛБ на „Р 650“, 2024", "palno": "ИЛБ;", "stoinosti": "пламна температура 23 °C; самовъзпламеняване 245 °C"}}
    check(s.proveri_chisla("Разредителят – 23 °C [[ilb-r: раздел 9]].", ilb) == [], "ИЛБ: value from its section 9 passes")
    check(len(s.proveri_chisla("Разредителят – 32 °C [[ilb-r: раздел 9]].", ilb)) == 1, "ИЛБ: other value caught")
    ilb["ilb-r"].pop("stoinosti")
    check(s.proveri_chisla("Разредителят – 32 °C [[ilb-r: раздел 9]].", ilb) == [], "ИЛБ without stoinosti – not checked")
    # Чочев – with the tables (offline sample; live they come from the normative base through n8n)
    sample = ("## Прил. № 5 – Температура на пожара – с. 222\n| Дървесина в помещение | 100 | 1 000 |\n"
              "## Прил. № 7 – Температура на топене – с. 223\n| Алуминий | 600 ÷ 660 |\n| Олово | 232 |\n")
    s._chochev.update(loaded=True, text=sample)
    try:
        check(s.proveri_chisla("Алуминият – 600 ÷ 660 °C [[chochev: прил. № 7, с. 223]].") == [], "Чочев: right value passes")
        check(len(s.proveri_chisla("Оловото – 327 °C [[chochev: прил. № 7, с. 223]].")) == 1, "Чочев: value not in the appendix caught")
        check(s.proveri_chisla("До 1 000 °C [[chochev: прил. № 5, с. 222]].") == [], "Чочев: „1 000“ read as 1000")
        check(s.proveri_chisla("До 900 °C [[chochev: прил. № 9]].") == [], "Чочев: appendix without a table – not checked")
    finally:
        s._chochev.update(loaded=False, text=None)


def test_greshki():
    print("известните грешки в книгите")
    p = s.proveri_chisla("оловото се топи при 232 °C [[chochev: прил. № 7, с. 223]]")
    check(len(p) == 1 and "327,5 °C" in p[0], "Чочев за оловото – спира и дава вярната стойност")
    check(s.proveri_chisla("оловото се топи при 327,5 °C [[icsc:0052]]") == [], "ICSC 0052 за оловото")
    t = "## Прил. № 7 – Температура на топене – с. 223\n\n| Олово | 232 ¹ |\n\n> ¹ Грешка: 327,5 °C (ICSC 0052).\n"
    nums = s.chochev_prilozheniya(t)["7"]
    check("232" in nums and "327.5" not in nums, "a note under the table is not the book's number")


def test_chochev_fail():
    print("Чочев от файл (колега с конектора)")
    import tempfile
    os.environ["FIRE_SERVICE_NO_KEY"] = "1"
    old = dict(s._chochev)
    s._chochev.update(loaded=False, text=None)
    t = "Цинкът се топи при 419 °C [[chochev: прил. № 7, с. 223]]."
    check(s.chochev_neprovereni(t) == ["7"], "without a key – appendix 7 is reported as not checked")
    f = os.path.join(tempfile.mkdtemp(), "chochev_7.md")
    open(f, "w", encoding="utf-8").write("## Прил. № 7 – Температура на топене – с. 223\n\n| Цинк | 419 |\n")
    s.zadai_chochev(f)
    check(s.chochev_neprovereni(t) == [] and s.proveri_chisla(t) == [], "from the file – checked, 419 °C is there")
    check(len(s.proveri_chisla(t.replace("419", "420"))) == 1, "a wrong number stops")
    open(f, "w", encoding="utf-8").write("| Цинк | 419 |\n")
    try:
        s.zadai_chochev(f)
        check(False, "a file without the heading stops")
    except s.Problem:
        check(True, "a file without the heading stops")
    s._chochev.clear(); s._chochev.update(old)


def test_vreme():
    print("времето (METAR) – без мрежа")
    import datetime
    import vreme
    os.environ["FIRE_SERVICE_NO_KEY"] = "1"
    d = vreme.razchiti("LBPL 041300Z 27002KT 9999 FEW070 35/13 Q1015 RMK T03540132")
    check((d["temp"], d["orosyavane"], d["vyatar_ms"], d["vyatar_posoka"]) == (35.4, 13.2, 1.0, "западен"),
          "temperature from the RMK group, wind in m/s, direction")
    check(d["oblachnost"] == ["незначителна на 2100 m"] and d["vlazhnost"] == 26, "clouds in m, relative humidity")
    d = vreme.razchiti("LBSF 171500Z 24015G28KT 4000 -TSRA BKN040CB 22/18 Q1009")
    check(d["porivi_ms"] == 14.4 and "слаб гръмотевична буря с дъжд" in d["yavleniya"]
          and d["oblachnost"] == ["значителна на 1200 m (купесто-дъждовна)"], "gusts, thunderstorm, CB")
    check(vreme.razchiti("LBPL 040400Z 00000KT CAVOK 16/12 Q1018")["vyatar_posoka"] == "тихо", "calm")
    dni, ot, do = vreme.ot_mesto("18.07.2025–21.07.2025")
    check(len(dni) == 4 and dni[0] == datetime.date(2025, 7, 18) and ot is None, "a range of days")
    dni, ot, do = vreme.ot_mesto("04.08.2026, 16:00–19:00 ч.")
    check((dni, ot, do) == ([datetime.date(2026, 8, 4)], "16:00", "19:00"), "a day with hours")
    check(vreme.nay_blizka(43.42, 24.61)[0] == "LBPL", "Плевен → Долна Митрополия")
    lat, lon = map(float, vreme.koordinati("с. Долни Луковит").split(","))
    check(vreme.nay_blizka(lat, lon) == ("LBPL", 24), "a settlement by name → airport and distance")
    t, lit, _ = s.citiraj("при 34–36 °C и вятър 1 m/s [[metar:LBPL: 04.08.2026, 16:00–19:00 ч.]].")
    check(t == "при 34–36 °C и вятър 1 m/s (METAR LBPL, 04.08.2026).", "marker renders with the date")
    check(any("летище Долна Митрополия (LBPL)" in l and "mesonet" in l for l in lit), "the airport is listed")
    check(s.proveri_chisla("вятър 9 m/s [[metar:LBPL: 04.08.2026]]") == [], "offline – the weather is not checked")
    try:
        s.citiraj("x [[metar:XXXX: 04.08.2026]]")
        check(False, "unknown airport stops")
    except s.Problem as e:
        check("UNKNOWN_SOURCE" in str(e), "unknown airport stops")
    obs = [{**vreme.razchiti("LBPL 221000Z 24010KT 9999 SKC 33/15 Q1008"), "chas": "11:00"}]
    check({"33", "5", "5.1"} <= vreme.chisla(obs), "numbers a text may cite")


if __name__ == "__main__":
    test_greshki()
    test_vreme()
    test_chochev_fail()
    test_data()
    test_proveri()
    test_literatura()
    test_masla_prahove()
    test_lookup()
    test_citiraj()
    test_katalog()
    print("\nALL PASS" if not failures else f"\n{len(failures)} FAILED")
    sys.exit(1 if failures else 0)
