#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
metrics_report.py — онлайн показателите на плъгина: какво става с истинските извиквания към n8n.

Чете събитията, които скриптовете пращат на `metrics_url` (по едно на извикване – виж
`shared/scripts/api_config.py`, `metrics_event`), записани от n8n като CSV или JSON Lines, и дава
по скил и по извикване: брой, дял грешки, медиана и 95-и персентил на времето, и кои версии на
плъгина са ползвани. Данни от делата в събитията няма – само име на скил, извикване, време и изход.

    python3 tools/metrics_report.py sabitiya.csv            # всички събития
    python3 tools/metrics_report.py sabitiya.csv --dni 7    # само последните 7 дни (ако има колона "time")

Колони (CSV) или ключове (JSONL): skill, script, endpoint, action, kind, ms, outcome, version и по
желание time (ISO дата и час, слага я n8n при записа).
"""
import argparse
import csv
import datetime
import json
import os
import sys
from collections import defaultdict


def read_events(path):
    with open(path, encoding="utf-8") as f:
        text = f.read()
    if os.path.splitext(path)[1].lower() in (".jsonl", ".json") or text.lstrip().startswith("{"):
        return [json.loads(line) for line in text.splitlines() if line.strip()]
    return list(csv.DictReader(text.splitlines()))


def percentile(values, p):
    if not values:
        return 0
    values = sorted(values)
    k = max(0, min(len(values) - 1, round(p / 100 * (len(values) - 1))))
    return values[k]


def since(events, days):
    if not days:
        return events
    limit = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=days)
    kept = []
    for e in events:
        t = str(e.get("time") or "")
        try:
            when = datetime.datetime.fromisoformat(t.replace("Z", "+00:00"))
            if when.tzinfo is None:
                when = when.replace(tzinfo=datetime.timezone.utc)
        except ValueError:
            continue
        if when >= limit:
            kept.append(e)
    return kept


def report(events):
    groups = defaultdict(list)
    for e in events:
        label = f"{e.get('skill') or '?'} · {e.get('endpoint') or '?'}" + (f"/{e['action']}" if e.get("action") else "")
        groups[label].append(e)
    rows = []
    for label, evs in groups.items():
        ms = [int(float(e.get("ms") or 0)) for e in evs]
        bad = [e for e in evs if (e.get("outcome") or "ok") != "ok"]
        rows.append((label, len(evs), len(bad) / len(evs), percentile(ms, 50), percentile(ms, 95),
                     sorted({str(e.get("outcome")) for e in bad})))
    rows.sort(key=lambda r: (-r[2], -r[1]))
    width = max([len(r[0]) for r in rows] + [10])
    lines = [f"{'извикване'.ljust(width)}  брой  грешки  медиана  p95   изходи при грешка"]
    for label, n, err, p50, p95, outcomes in rows:
        lines.append(f"{label.ljust(width)}  {n:4d}  {err:6.0%}  {p50:5d} ms {p95:5d} ms  {', '.join(outcomes)}")
    versions = defaultdict(int)
    for e in events:
        versions[str(e.get("version") or "?")] += 1
    lines.append("")
    lines.append("Версии: " + ", ".join(f"{v} ({n})" for v, n in sorted(versions.items(), reverse=True)))
    total_bad = sum(1 for e in events if (e.get("outcome") or "ok") != "ok")
    lines.append(f"Общо: {len(events)} извиквания, {total_bad / len(events):.1%} с грешка.")
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Summarise the plugin's metrics events")
    ap.add_argument("events", help="CSV or JSON Lines export of the metrics events")
    ap.add_argument("--dni", type=int, default=0, help="only the last N days (needs a 'time' column)")
    a = ap.parse_args(argv)
    events = since(read_events(a.events), a.dni)
    if not events:
        sys.exit("Няма събития за този период.")
    print(report(events))
    return 0


if __name__ == "__main__":
    sys.exit(main())
