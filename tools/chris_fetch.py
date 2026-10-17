#!/usr/bin/env python3
"""
chris_fetch.py — сваля картите CHRIS (Chemical Hazards Response Information System на Бреговата охрана
на САЩ, публикувани от NOAA в CAMEO Chemicals) за маслата от tools/chris_karti.csv и записва
стойностите им в plugins/fire-service/shared/svoistva/chris.csv.

Картите дават температурите във °F. Таблицата пази стойността точно както е в картата (колона
`izhodni`) и до нея превода в °C, закръглен до градус: °C = (°F − 32) × 5/9.

    python3 tools/chris_fetch.py                # сваля картите и обновява таблицата
    python3 tools/chris_fetch.py --cache DIR    # пази/чете свалените PDF в DIR
    python3 tools/chris_fetch.py --check        # само сверява таблицата с картите; код 1 при разлика

Иска `pdftotext` (poppler-utils). Ползва мрежата – не се пуска от CI.
"""
import argparse
import csv
import datetime
import os
import re
import subprocess
import sys
import tempfile
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KARTI = os.path.join(ROOT, "tools", "chris_karti.csv")
OUT = os.path.join(ROOT, "plugins", "fire-service", "shared", "svoistva", "chris.csv")
URL = "https://cameochemicals.noaa.gov/chris/{kod}.pdf"
COLUMNS = ["kluch", "ime", "sinonimi", "ime_en", "cas", "sastoyanie", "plamna", "plamna_metod",
           "samovazpl", "kgv", "vgv", "kipene", "otn_platnost_pari", "izhodni", "karta_versiya", "url", "proveren"]
MONTHS = {"JANUARY": "януари", "FEBRUARY": "февруари", "MARCH": "март", "APRIL": "април", "MAY": "май",
          "JUNE": "юни", "JULY": "юли", "AUGUST": "август", "SEPTEMBER": "септември",
          "OCTOBER": "октомври", "NOVEMBER": "ноември", "DECEMBER": "декември"}


def pdf_text(kod, cache):
    path = os.path.join(cache, f"{kod}.pdf") if cache else os.path.join(tempfile.mkdtemp(), f"{kod}.pdf")
    if not (cache and os.path.exists(path)):
        if cache:
            os.makedirs(cache, exist_ok=True)
        req = urllib.request.Request(URL.format(kod=kod), headers={"User-Agent": "fire-service-skills"})
        open(path, "wb").write(urllib.request.urlopen(req, timeout=60).read())
    return subprocess.run(["pdftotext", "-layout", path, "-"], capture_output=True, text=True, check=True).stdout


def f2c(f):
    return str(round((float(f) - 32) * 5 / 9))


def parse(kod, text):
    name = re.search(r"OILS, [A-Z]+: [A-Z][A-Z ]*[A-Z]", text)
    ver = re.search(r"\b(JANUARY|FEBRUARY|MARCH|APRIL|MAY|JUNE|JULY|AUGUST|SEPTEMBER|OCTOBER|NOVEMBER|DECEMBER) (\d{4})\b", text)
    fp = re.search(r"4\.1 Flash Point: ?(\d+)\s*°F\s*(O\.C\.|C\.C\.)?", text)
    ait = re.search(r"4\.7 Auto Ignition Temperature: ?(\d+)\s*°F", text)
    if not (name and ver):
        raise SystemExit(f"CHRIS {kod}: файлът не прилича на карта – провери адреса")
    izh = []
    if fp:
        izh.append(f"Flash Point: {fp.group(1)}°F {fp.group(2) or ''}".strip())
    if ait:
        izh.append(f"Auto Ignition Temperature: {ait.group(1)}°F")
    return {"ime_en": name.group(0), "cas": "", "sastoyanie": "течност",
            "plamna": f2c(fp.group(1)) if fp else "",
            "plamna_metod": {"C.C.": "з.т.", "O.C.": "о.т."}.get(fp.group(2) or "", "") if fp else "",
            "samovazpl": f2c(ait.group(1)) if ait else "", "kgv": "", "vgv": "", "kipene": "",
            "otn_platnost_pari": "", "izhodni": "; ".join(izh),
            "karta_versiya": f"{MONTHS[ver.group(1)]} {ver.group(2)} г.", "url": URL.format(kod=kod)}


def build(cache, today):
    rows = []
    for k in csv.DictReader(open(KARTI, encoding="utf-8")):
        d = parse(k["kod"], pdf_text(k["kod"], cache))
        rows.append({"kluch": f"chris:{k['kod'].lower()}", "ime": k["ime"], "sinonimi": k["sinonimi"],
                     "proveren": today, **d})
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", help="папка за свалените PDF")
    ap.add_argument("--check", action="store_true", help="само сверява таблицата с картите")
    a = ap.parse_args()
    rows = build(a.cache, datetime.date.today().isoformat())
    if a.check:
        old = {r["kluch"]: r for r in csv.DictReader(open(OUT, encoding="utf-8"))}
        diff = [f"✗ {r['kluch']} {c}: „{old.get(r['kluch'], {}).get(c, '')}“ ≠ „{r[c]}“"
                for r in rows for c in COLUMNS if c != "proveren" and old.get(r["kluch"], {}).get(c, "") != r[c]]
        print("\n".join(diff) or "✅ таблицата съвпада с картите")
        sys.exit(1 if diff else 0)
    with open(OUT, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(rows)
    print(f"✅ {len(rows)} масла → {os.path.relpath(OUT, ROOT)}")


if __name__ == "__main__":
    main()
