#!/usr/bin/env python3
"""Tests for ukazaniya.py (preparing a ruling, finding candidates, duplicate and supersede checks). Run from
the skill folder:
    python3 tests/test_ukazaniya.py
The letters are invented; the tests never touch the network.
"""
import json
import os
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
SCRIPT = os.path.join(SKILL, "scripts", "ukazaniya.py")
os.environ["FIRE_SERVICE_NO_KEY"] = "1"
ROOT = os.path.abspath(os.path.join(SKILL, "..", "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "tools"))

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


TEXT = ("Във връзка с постъпили запитвания Ви уведомяваме, че при оказване на съдействие на екипите на ЦСМП и на "
        "органите на МВР служителите на ГДПБЗН не следва да бъдат задължавани да пренасят починали лица, "
        "освен когато това е необходимо за извършване на спасителни дейности или за освобождаване на лицето.")
BASE = {"izdatel": "ГДПБЗН", "vid": "писмо", "reg_no": "1234р-56789", "data": "2026-10-15",
        "tema": "Пренасяне на починали лица при съдействие на ЦСМП",
        "vapros": "Може ли служителите да бъдат задължавани да пренасят починали лица при съдействие на ЦСМП?",
        "otgovor": "Не следва, освен при спасителни дейности или за освобождаване на лицето.",
        "tekst": TEXT, "keywords": ["починали", "ЦСМП", "съдействие", "пренасяне"]}

d = tempfile.mkdtemp()
out = os.path.join(d, "ukaz")


def prepare(data, sub):
    p = os.path.join(d, sub + ".json")
    json.dump(data, open(p, "w", encoding="utf-8"), ensure_ascii=False)
    return run("podgotvi", p, "-o", os.path.join(d, sub))


print("podgotvi")
r = prepare(BASE, "nov")
ok(r["ok"] and r["name"] == "GDPBZN_Ukazanie_1234r-56789-Prenasyane-Pochinali-Litsa-Sadeystvie-TsSMP_2026-10.md",
   f"file name: {r.get('name')}")
new = r["file"]
text = open(new, encoding="utf-8").read()
ok("tier: C" in text and "ТОВА НЕ Е НОРМАТИВЕН АКТ" in text and "## Текст" in text, "front matter and body")
try:
    from kb_lint import NAME_RX, split_front_matter  # the rules of the base
    fm, body, err = split_front_matter(text)
    ok(NAME_RX.match(r["name"]) and err is None and fm["tier"] == "C" and isinstance(fm["keywords"], list),
       "passes the base's name and front-matter rules")
    ok(all(fm.get(k) for k in ("title", "issuer", "act_type", "in_force", "text_source")), "required fields are filled")
except ImportError:
    print("  (kb_lint not importable – skipped)")
r = prepare({**BASE, "tekst": ""}, "prazen")
ok(not r["ok"] and "tekst" in r.get("error", ""), "a ruling without text is refused")

print("sravni")
r = prepare({**BASE, "data": "2026-10-15"}, "dubl")      # the same letter, written again
res = run("sravni", new, r["file"])
ok(res["reshenie"] == "dublikat", f"same registration number → duplicate ({res['reshenie']})")

older = {**BASE, "reg_no": "947р-0000", "data": "2024-03-01",
         "tekst": "Служителите оказват съдействие при пренасяне на починали лица по искане на ЦСМП, когато "
                  "няма друга възможност, като се спазват мерките за безопасност и хигиена при работа с тях."}
r_old = prepare(older, "star")
res = run("sravni", new, r_old["file"])
ok(res["reshenie"] == "zapishi_i_zameni" and res["zameni"] == [r_old["file"]], f"newer on the same question replaces the older ({res['reshenie']})")
res = run("sravni", r_old["file"], new)
ok(res["reshenie"] == "po_staro", f"an older letter against a newer one ({res['reshenie']})")

other = {**BASE, "reg_no": "1983р-15019", "tema": "Работа с газоанализатор при пожари в сутерени",
         "vapros": "Как се проверява концентрацията на газ в сутерен?", "keywords": ["газоанализатор", "сутерен"],
         "otgovor": "С калибриран уред, преди влизане.", "tekst": "Измерването с газоанализатор се извършва " * 8}
r_other = prepare(other, "drugo")
res = run("sravni", new, r_other["file"])
ok(res["reshenie"] == "zapishi", f"a different question → save ({res['reshenie']})")

print("zameni")
res = run("zameni", r_old["file"], "--s", "tier-c/" + os.path.basename(new), "-o", os.path.join(d, "zam"))
t = open(res["file"], encoding="utf-8").read()
ok("in_force: \"не\"" in t and "superseded_by: \"tier-c/" in t and "## Текст" in t, "the old one is marked as replaced")
ok(t.count("in_force:") == 1, "in_force is replaced, not duplicated")

print("kandidati")
listing = os.path.join(d, "listing.json")
json.dump({"files": [
    {"path": "tier-c/" + os.path.basename(r_old["file"]), "id": "a"},
    {"path": "tier-c/GDPBZN_Ukazanie_Gazoanalizator-Suterenni_2025-01.md", "id": "b"},
    {"path": "tier-a/GDPBZN_Ordinance_Pozharogasitelnata-Deynost_2026.md", "id": "c"},
    {"path": "указания-и-писма/починали лица ЦСМП.md", "id": "d"},
]}, open(listing, "w", encoding="utf-8"), ensure_ascii=False)
res = run("kandidati", new, "--listing", listing)
paths = [k["path"] for k in res["kandidati"]]
ok(paths and paths[0].endswith(os.path.basename(r_old["file"])) or "указания-и-писма/починали лица ЦСМП.md" in paths[:2],
   f"the same question comes first: {paths}")
ok(not any(p.startswith("tier-a/") for p in paths), "acts are not candidates")
ok(not any("Gazoanalizator" in p for p in paths), f"another question is not a candidate: {paths}")

res = run("kandidati", new)
ok(not res["ok"] and "NO_KEY" in res.get("error", ""), "without a key and without --listing → NO_KEY")

if failures:
    print(f"\n{len(failures)} FAILED")
    sys.exit(1)
print("\nall passed")
