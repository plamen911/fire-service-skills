#!/usr/bin/env python3
"""Tests for akti.py (a whole document into the regulations base: preparing, checking the articles, finding
the same act, appending the next pages). Run from the skill folder:
    python3 tests/test_akti.py
The texts are invented; the tests never touch the network.
"""
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
SCRIPT = os.path.join(SKILL, "scripts", "akti.py")
os.environ["FIRE_SERVICE_NO_KEY"] = "1"

failures = []


def ok(cond, msg):
    print(("  ok  " if cond else "  FAIL ") + msg)
    if not cond:
        failures.append(msg)


def run(*args):
    r = subprocess.run([sys.executable, SCRIPT, *args], capture_output=True, text=True)
    try:
        return json.loads(r.stdout)
    except ValueError:
        return {"ok": False, "raw": r.stdout + r.stderr}


def write(path, text):
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return path


def art(n, text="Служителите спазват изискванията за безопасност при работа с пожарната техника и оборудването."):
    return f"## Чл. {n}\n\n{text}\n\n"


d = tempfile.mkdtemp()
P1 = "ЗАПОВЕД\n\n# Глава първа — ОСНОВНИ ПОЛОЖЕНИЯ\n\n" + "".join(art(n) for n in range(1, 4)) + \
     "## Чл. 4\n\nЛостовете за спускане се проверяват ежедневно от началника на"
P2 = "дежурната смяна чрез визуален оглед.\n\n" + "".join(art(n) for n in range(5, 7))
P3 = "".join(art(n) for n in range(7, 10))
write(os.path.join(d, "p1.md"), P1)
write(os.path.join(d, "p2.md"), P2)
write(os.path.join(d, "p3.md"), P3)
DATA = {"izdatel": "МВР", "vid": "заповед", "nomer": "Iз-1234", "data": "05.08.2010",
        "zaglavie": "утвърждаване на Правила за безопасност при работа", "tier": "c", "in_force": "непроверен",
        "keywords": ["безопасност"], "iztochnik": "OCR на скан, сверен с изображенията на страниците",
        "nepalen": "Наличните страници свършват с чл. 6.", "chasti": ["p1.md", "p2.md"]}
data = write(os.path.join(d, "data.json"), json.dumps(DATA, ensure_ascii=False))

print("podgotvi")
r = run("podgotvi", data, "-o", os.path.join(d, "akt"))
ok(r.get("ok") and r["name"] == "MVR_Order_Iz-1234_Utvarzhdavane-Pravila-Bezopasnost-Rabota_2010.md", f"name: {r.get('name')}")
ok(r.get("path", "").startswith("tier-c/"), "tier c → tier-c/")
ok(r["chlenove"]["ot"] == 1 and r["chlenove"]["do"] == 6 and not r["chlenove"]["lipsvat"], "articles 1–6, none missing")
f1 = r["file"]
text = open(f1, encoding="utf-8").read()
ok("началника на дежурната смяна чрез визуален оглед" in text, "a page cut mid-sentence is joined")
ok('articles: "1-6"' in text and "tier: C" in text and "edition_date: '2010-08-05'" in text, "front matter fields")
ok("> Непълен документ:" in text and "Транскрипция на скан" in text, "notes under the front matter")
ok(not r["greshki"], "no errors")

print("proveri")
bad = write(os.path.join(d, "MVR_Order_X_Test_2010.md"), text.replace("## Чл. 5", "## Чл. 3").replace("## Чл. 6", "Чл. 6."))
r = run("proveri", bad)
ok(not r["ok"] and any("повторени" in e for e in r["greshki"]), "duplicated article is an error")
ok(any("не са поред" in e for e in r["greshki"]), "out-of-order articles are an error")
ok(any("без заглавие" in w for w in r["preduprezhdeniya"]), "a loose „Чл. N.“ line is flagged")
gap = write(os.path.join(d, "MVR_Order_Y_Test_2010.md"), text.replace("## Чл. 5", "## Чл. 8").replace("## Чл. 6", "## Чл. 9"))
r = run("proveri", gap)
ok(any("липсват членове: 5, 6, 7" in w for w in r["preduprezhdeniya"]), "gaps are reported")
unsure = write(os.path.join(d, "MVR_Order_Z_Test_2010.md"), text.replace("визуален оглед", "визуален[?] оглед"))
r = run("proveri", unsure)
ok(r["ok"] and r["nesigurni"] == 1, "[?] counted, still ok")

print("kandidati")
listing = write(os.path.join(d, "listing.json"), json.dumps({"files": [
    {"path": "tier-c/MVR_Order_Iz-1234_Utvarzhdavane-Pravila-Bezopasnost-Rabota_2010.md", "id": "1"},
    {"path": "tier-a/MVR_Rules_Organizatsiya-Dihatelna-Zashtita_2015.md", "id": "2"},
    {"path": "assets/MVR_Order_Iz-1234_fig01.png", "id": "3"}]}))
r = run("kandidati", f1, "--listing", listing)
ok(r["ok"] and [c["path"] for c in r["kandidati"]] == ["tier-c/MVR_Order_Iz-1234_Utvarzhdavane-Pravila-Bezopasnost-Rabota_2010.md"],
   f"same number found, others not: {r.get('kandidati')}")

print("sravni")
r = run("sravni", f1, f1)
ok(r["reshenie"] == "dublikat", "the same file is a duplicate")
p3 = os.path.join(d, "p3.md")
r = run("sravni", p3, f1)
ok(r["reshenie"] == "prodalzhenie", f"articles 7–9 continue 1–6: {r.get('reshenie')}")
r = run("sravni", os.path.join(d, "p2.md"), f1)
ok(r["reshenie"] in ("chast", "dublikat"), f"a part already in the base: {r.get('reshenie')}")

print("dopalni")
r = run("dopalni", f1, p3, "-o", os.path.join(d, "out"), "--palen")
ok(r["ok"] and r["chlenove"]["do"] == 9 and not r["greshki"], "articles 1–9 after appending")
t2 = open(r["file"], encoding="utf-8").read()
ok('articles: "1-9"' in t2, "articles field updated")
ok("> Непълен документ:" not in t2 and "Транскрипция на скан" in t2, "--palen drops only the incomplete note")
ok(os.path.basename(r["file"]) == os.path.basename(f1), "same name – replaced in place")

r = run("dopalni", f1, p3, "-o", os.path.join(d, "out2"), "--nepalen", "Страниците свършват с чл. 9.")
t3 = open(r["file"], encoding="utf-8").read()
ok(t3.count("> Непълен документ:") == 1 and "свършват с чл. 9." in t3 and "свършват с чл. 6." not in t3,
   "--nepalen replaces the incomplete note")
p4 = write(os.path.join(d, "p4.md"), "(2) Втората алинея на последния член започва нова страница.\n\n" + art(10))
r = run("dopalni", r["file"], p4, "-o", os.path.join(d, "out3"))
t4 = open(r["file"], encoding="utf-8").read()
ok("\n\n(2) Втората алинея" in t4, "a page starting with „(2)“ is a new paragraph, not glued")

print("zapis")
r = run("zapis", bad)
ok(not r["ok"] and "грешки" in r.get("error", ""), "a file with errors is not saved")

print()
print("FAILED: %d" % len(failures) if failures else "all ok")
sys.exit(1 if failures else 0)
