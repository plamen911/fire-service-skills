#!/usr/bin/env python3
"""Tests for vhodyasht.py (deadlines, routing, the partial data files, the calendar). Run from the skill folder:
    python3 tests/test_vhodyasht.py
The data is invented; the tests never touch the network.
"""
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
SCRIPT = os.path.join(SKILL, "scripts", "vhodyasht.py")
os.environ["FIRE_SERVICE_NO_KEY"] = "1"
sys.path.insert(0, os.path.join(SKILL, "scripts"))

import datetime  # noqa: E402
from vhodyasht import compute_deadline, two_names, number_part, build_ics  # noqa: E402

failures = []


def check(cond, msg):
    print(("  ok  " if cond else "  FAIL ") + msg)
    if not cond:
        failures.append(msg)


def run(data, dnes="2026-10-18"):
    d = tempfile.mkdtemp()
    p = os.path.join(d, "data.json")
    json.dump(data, open(p, "w", encoding="utf-8"), ensure_ascii=False)
    r = subprocess.run([sys.executable, SCRIPT, "obraboti", p, "--out-dir", os.path.join(d, "out"), "--dnes", dnes],
                       capture_output=True, text=True)
    res = json.loads(r.stdout)
    return res, os.path.join(d, "out")


D = datetime.date
print("deadlines")
r = compute_deadline(D(2026, 10, 16), dni=7)            # Fri + 7 = Fri 23.10
check(r["data"] == "2026-10-23", f"7 days from Friday → {r['data']}")
r = compute_deadline(D(2026, 10, 17), dni=7)            # Sat + 7 = Sat 24.10 → Mon 26.10
check(r["data"] == "2026-10-26" and r.get("premestena_ot"), f"ending on Saturday moves to Monday → {r['data']}")
r = compute_deadline(D(2026, 12, 17), dni=7)            # 24.12 Thu holiday, 25, 26 – 26 is Sat, 27 Sun, 28 Mon moved day off
check(r["data"] == "2026-12-29", f"Christmas and the moved day off are skipped → {r['data']}")
r = compute_deadline(D(2026, 1, 31), mesetsi=1)         # no 31 Feb → 28 Feb (Sat) → Mon 2 Mar
check(r["data"] == "2026-03-02", f"one month from 31 January → {r['data']}")
r = compute_deadline(D(2026, 2, 27), dni=4)             # 3 March is a holiday (Tue) → 4 March
check(r["data"] == "2026-03-04", f"3 March holiday is skipped → {r['data']}")
r = compute_deadline(D(2026, 10, 16), rabotni_dni=5)    # Fri + 5 working days = Fri 23.10
check(r["data"] == "2026-10-23", f"5 working days → {r['data']}")
r = compute_deadline(None, do=D(2026, 11, 14))          # explicit Saturday stays, with a warning
check(r["data"] == "2026-11-14" and "neraboten" in r, "an explicit date on Saturday is kept and flagged")

print("names and numbers")
check(two_names("Иван Георгиев Дъбов") == "Иван Дъбов", "three names → name and surname")
check(two_names("И. Дъбов") == "И. Дъбов", "initials stay")
check(number_part("ЗМ № 123/2026 г.") == "123/2026", "ЗМ number is extracted")
check(number_part("№ 1234р-56789") == "1234р-56789", "registration number is extracted")

print("постановление за СПТЕ")
res, out = run({
    "vid": "postanovlenie_spte",
    "izprashtach": {"institutsiya": "Първо РУ - Плевен", "dlazhnost": "разследващ полицай", "ime": "Иван Георгиев Дъбов"},
    "reg_no": "1234р-56789", "data_dokument": "15.10.2026", "data_poluchavane": "2026-10-16",
    "zm_no": "ЗМ № 123/2026", "zm_opis": "Първо РУ – Плевен", "dp_no": "1234/2026", "prokuratura": "РП – Плевен",
    "proizshestvie": {"data": "2026-10-01", "masto": "с. Примерно", "obekt": "къща"},
    "vaprosi": ["Къде се намира огнището?", "Каква е причината за пожара?"],
    "srok": {"mesetsi": 1}})
check(res["ok"] and res["skil"] == "eptz", "routed to eptz")
meta = json.load(open(os.path.join(out, "eptz_meta.chast.json"), encoding="utf-8"))
check(meta["zm_no"] == "123/2026" and meta["dp_no"] == "1234/2026", "ЗМ and ДП numbers in meta")
check(meta["postanovlenie_no"] == "1234р-56789" and meta["postanovlenie_date"] == "15.10.2026 г.", "постановление number and date")
check(meta["naznachil"] == "разследващ полицай Иван Дъбов при Първо РУ – Плевен", f"naznachil: {meta['naznachil']}")
check(meta.get("rp_grad") == "Плевен" and "prokuratura" not in meta, "РП – Плевен → rp_grad")
check(res["srok"]["data"] == "2026-11-16", f"one month from receipt → {res['srok']['data']}")
check(res["lipsva"] == [], f"nothing missing: {res['lipsva']}")
ics = open(os.path.join(out, "kalendar.ics"), encoding="utf-8", newline="").read()
check("DTSTART;VALUE=DATE:20261116" in ics and ics.count("BEGIN:VALARM") == 2, "calendar: all-day event with two reminders")
check(all(len(l.encode("utf-8")) <= 75 for l in ics.split("\r\n")), "calendar lines are folded")

print("писмо с искане на документи")
res, out = run({
    "vid": "iskane_dokumenti",
    "izprashtach": {"institutsiya": "Първо РУ – Плевен", "dlazhnost": "разследващ полицай", "ime": "Иван Дъбов"},
    "reg_no": "1234р-56789", "data_dokument": "2026-10-15",
    "proizshestvie": {"data": "2026-10-01", "masto": "с. Примерно"}, "srok": {"dni": 7}})
pismo = json.load(open(os.path.join(out, "pismo.chast.json"), encoding="utf-8"))
check(res["skil"] == "udostovereniya-pozhari", "routed to udostovereniya-pozhari")
check(pismo["addressee"] == ["НАЧАЛНИКА НА", "ПЪРВО РУ – ПЛЕВЕН"], f"addressee {pismo['addressee']}")
check(pismo["reference"] == "На Ваш рег. № 1234р-56789/15.10.2026 г.", "reference line")
check(pismo["attention"] == "Разследващ полицай Иван Дъбов", "attention line")
check(res["srok"]["data"] == "2026-10-22" and res["preduprezhdeniya"], "counted from the document date, with a warning")

print("призовка")
res, out = run({"vid": "prizovka", "izprashtach": {"institutsiya": "Районен съд – Плевен"}, "reg_no": "1234р-56789",
                "data_dokument": "2026-10-10",
                "zasedanie": {"data": "20.11.2026", "chas": "10:30", "sad": "Районен съд – Плевен", "zala": "5"}})
ics = open(os.path.join(out, "kalendar.ics"), encoding="utf-8", newline="").read()
check("DTSTART;TZID=Europe/Sofia:20261120T103000" in ics and "BEGIN:VTIMEZONE" in ics, "hearing as a timed event")
check(res["skil"] is None and "зала 5" in res["rezyume"], "no follow-up skill; the summary has the hall")

print("липсващи полета")
res, _ = run({"vid": "postanovlenie_spte", "izprashtach": {"institutsiya": "Първо РУ – Плевен"}})
check("№ на ЗМ" in res["lipsva"] and "въпросите към вещото лице" in res["lipsva"], f"missing listed: {res['lipsva']}")

print("unknown kind")
d = tempfile.mkdtemp()
p = os.path.join(d, "x.json")
json.dump({"vid": "nesto"}, open(p, "w"))
r = subprocess.run([sys.executable, SCRIPT, "obraboti", p, "--out-dir", d], capture_output=True, text=True)
check(r.returncode == 1 and '"ok": false' in r.stdout, "an unknown kind is refused")

check(build_ics([]).startswith("BEGIN:VCALENDAR"), "empty calendar is valid")

if failures:
    print(f"\n{len(failures)} FAILED")
    sys.exit(1)
print("\nall passed")
