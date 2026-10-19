#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
regresiya.py — проверка за регресия на evals: сравнява едно пускане на `claude plugin eval` с
последната приета база (`evals/baseline.json`) и записва пускането в историята (`evals/istoriya.csv`).

Пада (код 1), когато случай от базата:
  - има по-нисък дял успешни опити от базата с повече от допуска (по подразбиране 0,34 – т.е. един
    от три опита повече е паднал), или
  - е завършил с грешка, която е провалила опита (краят на ходовете на кратките случаи не е грешка).
Липсващ случай само се отбелязва.
Нов случай (няма го в базата) само се отбелязва. По-добър резултат също – базата не се вдига сама.

    claude plugin eval . --tag regresiya --ablation none --trust-plugin --no-publish \
        --allow-tools Bash -j 4 --json evals/results/posledno.json
    python3 evals/regresiya.py evals/results/posledno.json            # сравнява и записва в историята
    python3 evals/regresiya.py evals/results/posledno.json --obnovi   # приема пускането за нова база

Цената, времето и броят ходове на случай се пазят в историята, за да се вижда дали промяна в скил
ги е вдигнала – не само дали е паднала проверка.
"""
import argparse
import csv
import datetime
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BASELINE = os.path.join(HERE, "baseline.json")
HISTORY = os.path.join(HERE, "istoriya.csv")
HISTORY_FIELDS = ["data", "versiya", "sluchai", "uspeshni_opiti", "opiti", "dyal", "regresii",
                  "cena_usd", "sekundi", "obhvat"]


def summarize(result):
    """{case name: {"passRate", "runs", "errors", "cost", "seconds", "turns"}} from an eval result JSON."""
    out = {}
    for case in result.get("cases", []):
        runs = (case.get("arms") or {}).get("with") or []
        n = len(runs)
        passed = sum(1 for r in runs if r.get("passed"))
        # "Reached maximum number of turns" is how the short routing cases end by design – not an error.
        errors = sum(1 for r in runs if r.get("error") and "maximum number of turns" not in r["error"]
                     and not r.get("passed"))
        out[case["name"]] = {
            "passRate": round(passed / n, 3) if n else 0.0,
            "runs": n,
            "errors": errors,
            "cost": round(sum((r.get("costUsd") or 0) + (r.get("judgeCostUsd") or 0) for r in runs), 4),
            "seconds": round(sum(r.get("durationSeconds") or 0 for r in runs) / n, 1) if n else 0.0,
            "turns": round(sum(r.get("turns") or 0 for r in runs) / n, 1) if n else 0.0,
        }
    return out


def plugin_version(result):
    plugins = (result.get("suite") or {}).get("plugins") or []
    return plugins[0].get("version", "?") if plugins else "?"


def compare(base, now, tolerance):
    """(regressions, notes) — lists of human-readable lines."""
    regressions, notes = [], []
    for name, b in sorted(base.items()):
        n = now.get(name)
        if n is None:
            notes.append(f"  –  {name}: не е пускан този път")
            continue
        if n["errors"]:
            regressions.append(f"  ✗  {name}: {n['errors']} опит(а) с грешка")
        elif n["passRate"] < b["passRate"] - tolerance:
            regressions.append(f"  ✗  {name}: {b['passRate']:.2f} → {n['passRate']:.2f}")
        elif n["passRate"] > b["passRate"]:
            notes.append(f"  ↑  {name}: {b['passRate']:.2f} → {n['passRate']:.2f}")
        if b.get("cost") and n["runs"] and b.get("runs"):
            per_run_base, per_run_now = b["cost"] / b["runs"], n["cost"] / n["runs"]
            if per_run_base and per_run_now > 1.5 * per_run_base:
                notes.append(f"  $  {name}: цена на опит {per_run_base:.3f} → {per_run_now:.3f} USD")
    for name in sorted(set(now) - set(base)):
        notes.append(f"  +  {name}: нов случай ({now[name]['passRate']:.2f}) – не е в базата")
    return regressions, notes


def append_history(result, now, regressions, scope):
    runs = sum(c["runs"] for c in now.values())
    passed = sum(round(c["passRate"] * c["runs"]) for c in now.values())
    row = {
        "data": (result.get("startedAt") or datetime.datetime.utcnow().isoformat())[:16].replace("T", " "),
        "versiya": plugin_version(result),
        "sluchai": len(now),
        "uspeshni_opiti": passed,
        "opiti": runs,
        "dyal": f"{passed / runs:.3f}" if runs else "0",
        "regresii": len(regressions),
        "cena_usd": f"{result.get('costUsd') or 0:.2f}",
        "sekundi": result.get("durationSeconds") or 0,
        "obhvat": scope,
    }
    new = not os.path.exists(HISTORY)
    with open(HISTORY, "a", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=HISTORY_FIELDS)
        if new:
            w.writeheader()
        w.writerow(row)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Compare an eval run with the baseline")
    ap.add_argument("result", help="JSON written by `claude plugin eval --json <file>`")
    ap.add_argument("--obnovi", action="store_true", help="accept this run as the new baseline")
    ap.add_argument("--dopusk", type=float, default=0.34,
                    help="allowed drop in pass rate per case (default 0.34 = one run in three)")
    ap.add_argument("--bez-istoriya", action="store_true", help="do not append to istoriya.csv")
    a = ap.parse_args(argv)

    with open(a.result, encoding="utf-8") as f:
        result = json.load(f)
    now = summarize(result)
    if not now:
        sys.exit("В резултата няма случаи – пусни `claude plugin eval` с --json.")
    scope = (result.get("suite") or {}).get("caseFilter") or "regresiya"

    if a.obnovi:
        data = {"versiya": plugin_version(result), "data": (result.get("startedAt") or "")[:10],
                "sluchai": now}
        with open(BASELINE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2, sort_keys=True)
            f.write("\n")
        if not a.bez_istoriya:
            append_history(result, now, [], scope)
        print(f"Базата е обновена: {len(now)} случая, версия {data['versiya']}.")
        return 0

    if not os.path.exists(BASELINE):
        sys.exit("Няма evals/baseline.json – първото пускане се приема с --obnovi.")
    with open(BASELINE, encoding="utf-8") as f:
        base = json.load(f)["sluchai"]

    regressions, notes = compare(base, now, a.dopusk)
    if not a.bez_istoriya:
        append_history(result, now, regressions, scope)

    total_runs = sum(c["runs"] for c in now.values())
    total_passed = sum(round(c["passRate"] * c["runs"]) for c in now.values())
    print(f"Версия {plugin_version(result)}: {total_passed}/{total_runs} успешни опита в {len(now)} случая, "
          f"{result.get('costUsd') or 0:.2f} USD, {result.get('durationSeconds') or 0} с.")
    for line in notes:
        print(line)
    if regressions:
        print("РЕГРЕСИЯ:")
        for line in regressions:
            print(line)
        return 1
    print("Без регресия спрямо базата.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
