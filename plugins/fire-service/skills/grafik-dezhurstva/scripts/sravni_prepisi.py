#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sravni_prepisi.py — compares two independent readings of the same duty schedule (reading.json format,
references/reading.md) cell by cell, so that the second reading can be checked by a script and not by eye.

    python3 scripts/sravni_prepisi.py reading.json reading2.json

Rows are paired by `nomer` when both readings have it, otherwise by position (plus `ot_red`).
Output (JSON): {"sapadat": bool, "redove": N, "razliki": [{"red", "ime", "ime_2", "kod", "samo_v_1",
"samo_v_2"}]} – `ime_2` only when the two readings spell the name differently, `kod` "*" for a row
missing from one of the readings. Exit code 0 when the readings match, 1 when they differ.
"""
import json
import re
import sys


def days(value):
    """[3, 7] or "5-9, 12" → {3, 5, 6, 7, 8, 9, 12}."""
    if isinstance(value, list):
        return {int(d) for d in value}
    out = set()
    for part in re.split(r"[,\s]+", str(value or "").strip()):
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-", 1)
            out.update(range(int(a), int(b) + 1))
        else:
            out.add(int(part))
    return out


def rows(reading):
    """{row key: (name, {code: set of days})}."""
    redove = reading.get("redove") or []
    use_nomer = bool(redove) and all("nomer" in r for r in redove)
    start = int(reading.get("ot_red") or 1)
    out = {}
    for i, r in enumerate(redove):
        key = int(r["nomer"]) if use_nomer else start + i
        out[key] = (r.get("ime", ""), {k: days(v) for k, v in (r.get("dni") or {}).items()})
    return out


def norm(name):
    return " ".join(str(name).split()).lower()


def compare(a, b):
    ra, rb = rows(a), rows(b)
    diffs = []
    for key in sorted(set(ra) | set(rb)):
        if key not in ra or key not in rb:
            name = (ra.get(key) or rb.get(key))[0]
            diffs.append({"red": key, "ime": name, "kod": "*",
                          "samo_v_1": key in ra, "samo_v_2": key in rb})
            continue
        (n1, d1), (n2, d2) = ra[key], rb[key]
        name_diff = norm(n1) != norm(n2)
        row_diffs = []
        for code in sorted(set(d1) | set(d2)):
            only1, only2 = sorted(d1.get(code, set()) - d2.get(code, set())), \
                sorted(d2.get(code, set()) - d1.get(code, set()))
            if only1 or only2:
                row_diffs.append({"red": key, "ime": n1, "kod": code, "samo_v_1": only1, "samo_v_2": only2})
        if name_diff and not row_diffs:
            row_diffs.append({"red": key, "ime": n1, "kod": "", "samo_v_1": [], "samo_v_2": []})
        for d in row_diffs:
            if name_diff:
                d["ime_2"] = n2
        diffs.extend(row_diffs)
    return {"sapadat": not diffs, "redove": len(set(ra) | set(rb)), "razliki": diffs}


def main():
    if len(sys.argv) != 3:
        sys.exit("usage: sravni_prepisi.py reading.json reading2.json")
    readings = []
    for path in sys.argv[1:]:
        with open(path, encoding="utf-8") as f:
            readings.append(json.load(f))
    result = compare(*readings)
    print(json.dumps(result, ensure_ascii=False, indent=1))
    sys.exit(0 if result["sapadat"] else 1)


if __name__ == "__main__":
    main()
