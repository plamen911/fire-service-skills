#!/usr/bin/env python3
"""Tests for diktovka.py – checking the answers taken from a dictation and what is left to ask. Run from the
skill folder:
    python3 tests/test_diktovka.py
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(SKILL, "scripts"))
from diktovka import check  # noqa: E402

F = json.load(open(os.path.join(SKILL, "references", "formulyar.json"), encoding="utf-8"))
failures = []


def ok(cond, msg):
    print(("  ok  " if cond else "  FAIL ") + msg)
    if not cond:
        failures.append(msg)


print("a dictation about a car")
r = check({"form": "mps", "prichina": "01", "utochnenie": "ел. инсталация в двигателния отсек",
           "otgovori": {"polojenie": ["паркиран"], "gorivo": "Дизел", "ognishte": ["двигателен отсек"],
                        "gasene": ["водачът с пожарогасител"], "sasedni": ["няма"]},
           "zapis": {"place": "двигател", "reason": "късо съединение-01"}}, F)
ok(r["ok"] and r["prieti"]["gorivo"] == ["дизел"], "options are matched regardless of case")
ok(set(r["ostavat"]) == {"akumulator", "zastrahovka", "stepen", "priznaci"}, f"only the unanswered remain: {r['ostavat']}")
ok(len(r["ekrani"]) == 1 and r["ekrani"][0][0]["options"][0].endswith("(най-често)"), "one screen, most frequent first")
ok(r["ekrani"][0][1]["options"][0].startswith("не е известно"), "a question's default goes first")

print("record and cause")
r = check({"form": "mps", "otgovori": {}, "zapis": {"reason": "късо съединение-01", "place": "двигател"}}, F)
ok(r["prichina"] == "01" and "ognishte" not in r["ostavat"], "cause and seat of fire from the record are not asked")
ok(r["ostavat"][0] == "utochnenie", "the detail of the cause is asked first")
r = check({"form": "postroika", "prichina": "01", "otgovori": {}}, F)
ok(r["prieti"].get("el_instalacia") == ["има"] and "el_instalacia" not in r["ostavat"], "by_cause answers itself")
r = check({"form": "postroika", "otgovori": {}, "zapis": {"place": "барака"}}, F)
ok("ognishte" in r["ostavat"] and r["ostavat"][0] == "prichina", "an ignored place is asked; no cause → asked first")

print("errors and contradictions")
r = check({"form": "mps", "prichina": "01", "otgovori": {"gorivo": ["газ"]}}, F)
ok(not r["ok"] and "Друго" in r["greshki"][0], "a value that is not an option")
r = check({"form": "mps", "prichina": "01", "otgovori": {"gorivo": ["бензин", "дизел"]}}, F)
ok(not r["ok"], "two answers to a single-choice question")
r = check({"form": "mps", "prichina": "01", "otgovori": {"sasedni": ["няма", "сграда"]}}, F)
ok(not r["ok"], "„няма“ together with something else")
r = check({"form": "mps", "prichina": "01", "otgovori": {"ognishte": ["купе"]}, "zapis": {"place": "двигател"}}, F)
ok(r["ok"] and r["protivorechiya"], "the dictation contradicts the record → flagged, the dictation wins")
r = check({"form": "sgrada", "prichina": "04", "otgovori": {"plosht": ["35"], "ognishte": ["Друго: мазето"]}}, F)
ok(r["prieti"]["plosht"] == ["около 35 кв. м"] and r["prieti"]["ognishte"] == ["Друго: мазето"], "a number and a free answer")
r = check({"form": "mps", "prichina": "77", "otgovori": {}}, F)
ok(not r["ok"], "an unknown cause code")

if failures:
    print(f"\n{len(failures)} FAILED")
    sys.exit(1)
print("\nall passed")
