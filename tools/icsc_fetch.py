#!/usr/bin/env python3
"""
icsc_fetch.py — сваля Международните карти за химична безопасност (ICSC, ILO/WHO) за веществата
от tools/icsc_karti.csv и записва стойностите им в plugins/fire-service/shared/svoistva/stoinosti.csv.

Стойностите не се пишат на ръка – всяка идва от картата, точно както е в нея, заедно с номера,
версията на картата, адреса и датата, на която е сверена. Така всяко число в таблицата може да се
провери от всеки, който отвори адреса.

    python3 tools/icsc_fetch.py                 # сваля картите и обновява таблицата
    python3 tools/icsc_fetch.py --cache DIR     # пази/чете свалените страници в DIR
    python3 tools/icsc_fetch.py --check         # само сверява таблицата с картите; код 1 при разлика

Ново вещество: добави ред в tools/icsc_karti.csv (номер на картата, име, синоними, агрегатно
състояние) и пусни скрипта. Ползва мрежата – не се пуска от CI.
"""
import argparse
import csv
import datetime
import html
import os
import re
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KARTI = os.path.join(ROOT, "tools", "icsc_karti.csv")
OUT = os.path.join(ROOT, "plugins", "fire-service", "shared", "svoistva", "stoinosti.csv")
URL = "https://chemicalsafety.ilo.org/dyn/icsc/showcard.display?p_lang=en&p_card_id={id}&p_version=2"
COLUMNS = ["kluch", "ime", "sinonimi", "ime_en", "cas", "sastoyanie", "plamna", "plamna_metod",
           "samovazpl", "kgv", "vgv", "kipene", "topene", "otn_platnost_pari", "karta_versiya", "url", "proveren"]
MONTHS = {"January": "януари", "February": "февруари", "March": "март", "April": "април", "May": "май",
          "June": "юни", "July": "юли", "August": "август", "September": "септември",
          "October": "октомври", "November": "ноември", "December": "декември"}
# Labels of the "Physical & chemical information" block, in the order the card prints them
NEXT = r"(?= (?:Boiling point|Melting point|Relative|Solubility|Vapour pressure|Flash point|" \
       r"Auto-ignition|Explosive limits|Octanol|Viscosity|Density|Decomposes|EXPOSURE|Sublimation|" \
       r"Henry|Minimum ignition)|$)"


def fetch(card, cache):
    path = os.path.join(cache, f"{card}.html") if cache else None
    if path and os.path.exists(path):
        return open(path, encoding="utf-8").read()
    req = urllib.request.Request(URL.format(id=card), headers={"User-Agent": "fire-service-skills"})
    text = urllib.request.urlopen(req, timeout=60).read().decode("utf-8", "replace")
    if path:
        os.makedirs(cache, exist_ok=True)
        open(path, "w", encoding="utf-8").write(text)
    return text


def field(flat, label):
    m = re.search(re.escape(label) + r": (.*?)" + NEXT, flat)
    return m.group(1).strip() if m else ""


def temp(raw):
    """'52°C c.c.' -> ('52', 'з.т.'); '<-21°C' -> ('<-21', ''); 'Flammable gas' -> ('', '')."""
    raw = raw.replace("\xa0", " ").strip()
    method = "з.т." if "c.c." in raw else "о.т." if "o.c." in raw else ""
    m = re.match(r"^([<>~]?\s*-?\d+(?:\.\d+)?(?:\s*-\s*-?\d+(?:\.\d+)?)?)\s*°C", raw)
    if not m:
        return "", ""
    return re.sub(r"\s+", "", m.group(1)), method


def parse(card, text):
    title = re.search(r"<title>ICSC \d+ -\s*([^<]*)", text)
    body = re.sub(r"<script.*?</script>|<style.*?</style>", "", text, flags=re.S)
    # only real tags are stripped: the card writes "<-21°C" with a bare "<"
    flat = html.unescape(re.sub(r"<[a-zA-Z/!][^>]*>", " ", body))
    flat = re.sub(r"\s+", " ", flat)
    ver = re.search(r"ICSC\s*:\s*" + card + r"\s*\(\s*([A-Za-z]+)\s+(\d{4})\s*\)", flat)
    cas = re.search(r"CAS #: ([0-9-]+)", flat)
    lim = field(flat, "Explosive limits, vol% in air")
    lm = re.match(r"^(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)", lim)
    plamna, metod = temp(field(flat, "Flash point"))
    kip, _ = temp(field(flat, "Boiling point"))
    top, _ = temp(field(flat, "Melting point"))
    sam, _ = temp(field(flat, "Auto-ignition temperature"))
    if not (title and ver):
        raise SystemExit(f"ICSC {card}: страницата не прилича на карта – провери адреса")
    return {"ime_en": title.group(1).strip(), "cas": cas.group(1) if cas else "",
            "plamna": plamna, "plamna_metod": metod, "samovazpl": sam,
            "kgv": lm.group(1) if lm else "", "vgv": lm.group(2) if lm else "", "kipene": kip, "topene": top,
            "otn_platnost_pari": re.sub(r"\s+", "", field(flat, "Relative vapour density (air = 1)")),
            "karta_versiya": f"{MONTHS[ver.group(1)]} {ver.group(2)} г.", "url": URL.format(id=card)}


def build(cache, today):
    rows = []
    for k in csv.DictReader(open(KARTI, encoding="utf-8")):
        card = k["icsc"].zfill(4)
        d = parse(card, fetch(card, cache))
        rows.append({"kluch": f"icsc:{card}", "ime": k["ime"], "sinonimi": k["sinonimi"],
                     "sastoyanie": k["sastoyanie"], "proveren": today, **d})
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", help="папка за свалените страници")
    ap.add_argument("--check", action="store_true", help="само сверява таблицата с картите")
    a = ap.parse_args()
    today = datetime.date.today().isoformat()
    rows = build(a.cache, today)
    if a.check:
        old = {r["kluch"]: r for r in csv.DictReader(open(OUT, encoding="utf-8"))}
        diff = 0
        for r in rows:
            o = old.get(r["kluch"], {})
            for c in COLUMNS:
                if c not in ("proveren",) and o.get(c, "") != r[c]:
                    diff += 1
                    print(f"✗ {r['kluch']} {c}: в таблицата „{o.get(c, '')}“, в картата „{r[c]}“")
        print("✅ таблицата съвпада с картите" if not diff else f"{diff} разлики")
        sys.exit(1 if diff else 0)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(rows)
    print(f"✅ {len(rows)} вещества → {os.path.relpath(OUT, ROOT)}")


if __name__ == "__main__":
    main()
