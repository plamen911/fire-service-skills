#!/usr/bin/env python3
"""The evals tooling: evals/regresiya.py against made-up eval results, and the metrics report.

The metrics themselves are written in n8n (node "Log call"); nothing here reaches the network.
Run from the repository root:  python3 tests/test_metrics.py
"""
import json
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EVALS = os.path.join(ROOT, "plugins", "fire-service", "evals")
sys.path.insert(0, EVALS)
import regresiya  # noqa: E402

failures = []


def check(ok, what):
    print(("✓ " if ok else "✗ ") + what)
    if not ok:
        failures.append(what)


def result(rates, cost=0.1):
    """A made-up `claude plugin eval --json` result: {case: [passed, …]}."""
    cases = []
    for name, runs in rates.items():
        cases.append({"name": name, "arms": {"with": [
            {"passed": p, "costUsd": cost, "judgeCostUsd": 0, "durationSeconds": 20, "turns": 4, "error": None}
            for p in runs]}})
    return {"startedAt": "2026-10-19T20:00:00Z", "costUsd": cost * sum(len(r) for r in rates.values()),
            "durationSeconds": 60, "suite": {"plugins": [{"version": "9.9.9"}]}, "cases": cases}


def test_regresiya():
    with tempfile.TemporaryDirectory() as d:
        regresiya.BASELINE = os.path.join(d, "baseline.json")
        regresiya.HISTORY = os.path.join(d, "istoriya.csv")

        def run(rates, *args, cost=0.1):
            path = os.path.join(d, "r.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump(result(rates, cost), f)
            return regresiya.main([path, *args])

        check(run({"a": [1, 1, 1], "b": [1, 1, 0]}, "--obnovi") == 0, "--obnovi accepts the first run as the baseline")
        check(run({"a": [1, 1, 1], "b": [1, 1, 0]}) == 0, "the same result → no regression")
        check(run({"a": [1, 1, 0], "b": [1, 1, 0]}) == 0, "one more failed run in three is within the tolerance")
        check(run({"a": [1, 0, 0], "b": [1, 1, 0]}) == 1, "two more failed runs in three → regression")
        check(run({"a": [1, 1, 1]}) == 0, "a baseline case that was not run is only noted")
        check(run({"a": [1, 1, 1], "b": [1, 1, 1], "c": [0, 0, 0]}) == 0, "a new case is only noted")
        with open(regresiya.HISTORY, encoding="utf-8") as f:
            rows = f.read().strip().splitlines()
        check(len(rows) == 1 + 6 and rows[0].startswith("data,versiya"), "every run is appended to the history")


def test_report():
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    import metrics_report
    rows = [{"time": "2026-10-20T08:00:00Z", "route": "incidents", "action": "", "ms": 800, "outcome": "ok", "via": "script"},
            {"time": "2026-10-20T08:01:00Z", "route": "incidents", "action": "", "ms": 4000, "outcome": "error", "via": "script"},
            {"time": "2026-10-20T08:02:00Z", "route": "mcp", "action": "staff", "ms": 300, "outcome": "ok", "via": "connector"}]
    text = metrics_report.report(rows)
    check("script · incidents" in text and "50%" in text and "error" in text,
          "the report groups by source and call and shows the error share and outcome")
    check("connector · mcp/staff" in text and "connector (1)" in text, "connector calls are reported the same way")
    real = metrics_report.from_n8n
    metrics_report.from_n8n = lambda days: rows
    try:
        check(metrics_report.main(["--dni", "7"]) == 0, "without a file the report reads the rows from n8n")
    finally:
        metrics_report.from_n8n = real


def main():
    test_regresiya()
    test_report()
    if failures:
        print(f"\n{len(failures)} failed")
        return 1
    print("\nall passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
