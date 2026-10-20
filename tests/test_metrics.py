#!/usr/bin/env python3
"""The online half of the evals: one metrics event per n8n call – and never any of the data.

Nothing here reaches n8n: a small HTTP server on 127.0.0.1 plays the endpoint and the metrics webhook.
Also checks evals/regresiya.py against a made-up eval result.
Run from the repository root:  python3 tests/test_metrics.py
"""
import http.server
import json
import os
import sys
import tempfile
import threading

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHARED = os.path.join(ROOT, "plugins", "fire-service", "shared", "scripts")
EVALS = os.path.join(ROOT, "plugins", "fire-service", "evals")
os.environ.pop("FIRE_SERVICE_NO_KEY", None)
os.environ.pop("FIRE_SERVICE_KEY", None)
os.environ.pop("FIRE_SERVICE_NO_METRICS", None)
sys.path.insert(0, SHARED)
sys.path.insert(0, EVALS)
import api_config  # noqa: E402
import regresiya  # noqa: E402

failures = []
received = []   # (path, body)


def check(ok, what):
    print(("✓ " if ok else "✗ ") + what)
    if not ok:
        failures.append(what)


class Stub(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])) or b"{}")
        received.append((self.path, body))
        if self.path == "/broken":
            self.send_response(500)
            self.end_headers()
            return
        out = json.dumps({"ok": True, "echo": "Иван Дъбов, ул. Тестова 1"}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(out)


def metrics():
    return [b for p, b in received if p == "/metrics"]


def test_events(base):
    cfg = {"key": "stub-key", "key_source": "test", "header": "X-Api-Key",
           "staff_url": base + "data", "broken_url": base + "broken"}

    api_config._cache["cfg"] = dict(cfg)
    received.clear()
    api_config.post("staff_url", {"action": "find", "name": "Иван Дъбов"})
    check(not metrics(), "no metrics_url in the config → no event is sent")

    api_config._cache["cfg"] = dict(cfg, metrics_url=base + "metrics")
    received.clear()
    api_config.post("staff_url", {"action": "find", "name": "Иван Дъбов", "address": "ул. Тестова 1"})
    ev = metrics()
    check(len(ev) == 1, "one call → one metrics event")
    e = ev[0] if ev else {}
    check(e.get("endpoint") == "staff_url" and e.get("action") == "find" and e.get("outcome") == "ok",
          "the event names the endpoint, the action and the outcome")
    check(isinstance(e.get("ms"), int) and e["ms"] >= 0, "the event carries the duration in ms")
    text = json.dumps(e, ensure_ascii=False)
    check("Дъбов" not in text and "Тестова" not in text, "the request body and the answer never reach the event")
    check(set(e) == {"event", "skill", "script", "endpoint", "action", "kind", "ms", "outcome", "version"},
          "the event has exactly the documented fields")

    received.clear()
    try:
        api_config.post("broken_url", {"action": "get"})
        check(False, "an HTTP 500 is raised to the caller")
    except Exception:
        check(True, "an HTTP 500 is raised to the caller")
    ev = metrics()
    check(len(ev) == 1 and ev[0].get("outcome") == "http_500", "a failed call is reported as http_500")

    api_config._cache["cfg"] = dict(cfg, metrics_url="http://127.0.0.1:9/")
    received.clear()
    ok = api_config.post("staff_url", {"action": "find"})
    check(ok.get("ok") is True, "an unreachable metrics webhook never breaks the skill")

    api_config._cache["cfg"] = dict(cfg, metrics_url=base + "metrics")
    received.clear()
    api_config.post("metrics_url", {"op": "export", "dni": 7})
    check(len(metrics()) == 1 and metrics()[0].get("op") == "export",
          "a call to the metrics endpoint itself is not measured (no event about the event)")

    os.environ["FIRE_SERVICE_NO_METRICS"] = "1"
    received.clear()
    api_config.post("staff_url", {"action": "find"})
    check(not metrics(), "FIRE_SERVICE_NO_METRICS=1 switches the events off")
    os.environ.pop("FIRE_SERVICE_NO_METRICS")


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
    rows = [{"time": "2026-10-20T08:00:00Z", "skill": "spravka-prichina", "endpoint": "url", "action": "",
             "ms": 800, "outcome": "ok", "version": "2.27.1"},
            {"time": "2026-10-20T08:01:00Z", "skill": "spravka-prichina", "endpoint": "url", "action": "",
             "ms": 4000, "outcome": "timeout", "version": "2.27.1"},
            {"time": "2026-10-20T08:02:00Z", "skill": "", "endpoint": "staff_url", "action": "",
             "ms": 300, "outcome": "ok", "version": "2.27.1"}]
    text = metrics_report.report(rows)
    check("spravka-prichina · url" in text and "50%" in text and "timeout" in text,
          "the report groups by skill and call and shows the error share and outcome")
    check("инструмент · staff_url" in text, "a call from a repository tool (no skill) is labelled as a tool")
    real = metrics_report.from_n8n
    metrics_report.from_n8n = lambda days: rows
    try:
        check(metrics_report.main(["--dni", "7"]) == 0, "without a file the report reads the events from n8n")
    finally:
        metrics_report.from_n8n = real


def main():
    srv = http.server.HTTPServer(("127.0.0.1", 0), Stub)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_address[1]}/"
    api_config.RETRY_PAUSE = 0
    try:
        test_events(base)
        test_regresiya()
        test_report()
    finally:
        srv.shutdown()
    if failures:
        print(f"\n{len(failures)} failed")
        return 1
    print("\nall passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
