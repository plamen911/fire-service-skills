#!/usr/bin/env python3
"""references/formulyar.json: every question is consistent. Run: python3 tests/test_formulyar.py"""
import json
import os
import sys

SKILL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
f = json.load(open(os.path.join(SKILL, "references", "formulyar.json"), encoding="utf-8"))
errors, ids = [], []
for sc in f["screens"]:
    if not 1 <= len(sc["questions"]) <= 4:
        errors.append(f"{sc['title']}: 1–4 въпроса на екран (AskUserQuestion)")
    for q in sc["questions"]:
        ids.append(q["id"])
        if not 2 <= len(q["options"]) <= 4:
            errors.append(f"{q['id']}: 2–4 опции (AskUserQuestion)")
        if len(q["label"]) > 12:
            errors.append(f"{q['id']}: label над 12 знака")
        if not (q.get("always") or q.get("kogato")):
            errors.append(f"{q['id']}: нито always, нито kogato")
        d = q.get("deistvie") or {}
        if not q.get("dinamichni") and set(d) != set(q["options"]):
            errors.append(f"{q['id']}: deistvie не покрива точно опциите")
if len(ids) != len(set(ids)):
    errors.append("повтарящ се id")
if not {"gaz", "pgi"} <= set(ids):
    errors.append("газ и ПГИ трябва да са във формуляра")
for e in errors:
    print("  FAIL", e)
print("FAILURES" if errors else f"OK – {len(ids)} въпроса")
sys.exit(1 if errors else 0)
