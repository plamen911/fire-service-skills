#!/usr/bin/env python3
"""
gestis_staub_fetch.py — сваля записите от базата GESTIS-STAUB-EX (горимост и взривни характеристики
на прахове; IFA към DGUV, Германия) от tools/gestis_staub_zapisi.csv и записва стойностите им в
plugins/fire-service/shared/svoistva/prahove.csv.

Всеки запис е една измерена проба прах – с едрината и влажността ѝ. Стойностите се пазят точно както
са в записа: температура на запалване на облак прах (метод G-G – Годберт-Грийнуолд, или BAM),
температура на тлеене на слой 5 mm („n.g.u. 450“ – не тлее до 450 °C; „melts“ – топи се), долна
граница на взривяемост (g/m³).

    python3 tools/gestis_staub_fetch.py               # сваля записите и обновява таблицата
    python3 tools/gestis_staub_fetch.py --cache DIR   # пази/чете свалените страници в DIR
    python3 tools/gestis_staub_fetch.py --check       # само сверява таблицата със записите; код 1 при разлика

Нов запис: намери номера му в https://staubex.ifa.dguv.de/explosuche.aspx?lang=e, добави ред в
tools/gestis_staub_zapisi.csv и пусни скрипта. Ползва мрежата – не се пуска от CI.
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
ZAPISI = os.path.join(ROOT, "tools", "gestis_staub_zapisi.csv")
OUT = os.path.join(ROOT, "plugins", "fire-service", "shared", "svoistva", "prahove.csv")
URL = "https://staubex.ifa.dguv.de/explokomp.aspx?nr={nr}&lang=e"
COLUMNS = ["kluch", "ime", "sinonimi", "ime_en", "mediana_um", "vlazhnost", "zapalvane_oblak",
           "zapalvane_metod", "tleene_sloy", "dgv", "url", "proveren"]


def fetch(nr, cache):
    path = os.path.join(cache, f"{nr}.htm") if cache else None
    if path and os.path.exists(path):
        return open(path, encoding="utf-8").read()
    req = urllib.request.Request(URL.format(nr=nr), headers={"User-Agent": "fire-service-skills"})
    text = urllib.request.urlopen(req, timeout=90).read().decode("utf-8", "replace")
    if path:
        os.makedirs(cache, exist_ok=True)
        open(path, "w", encoding="utf-8").write(text)
    return text


def cells(t):
    return [re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", c))).strip()
            for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", t, re.S)]


def parse(nr, text):
    text = re.sub(r"<script.*?</script>|<style.*?</style>", "", text, flags=re.S)
    name = re.search(r"Detailed information on:(.*?)\(\s*(?:<[^>]+>\s*)*" + nr + r"\b", text, re.S)
    if not name:
        raise SystemExit(f"GESTIS-STAUB-EX {nr}: страницата не прилича на запис – провери номера")
    rows = {}
    for r in re.findall(r"<tr[^>]*>(.*?)</tr>", text, re.S):
        c = cells(r)
        if len(c) >= 2 and c[0]:
            rows[c[0]] = c[1:]
    ig_key = next((k for k in rows if k.startswith("Ignition Temperature")), None)
    ig = rows.get(ig_key, [])
    # the sample the ignition temperature was measured on gives the fineness and moisture
    col = next((i for i, v in enumerate(ig) if v), None)

    def val(label, i=None):
        vs = rows.get(label, [])
        if i is not None and i < len(vs) and vs[i]:
            return vs[i]
        return next((v for v in vs if v), "")

    return {"ime_en": re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", name.group(1)))).strip(" ("),
            "mediana_um": val("Median Value [μm]", col), "vlazhnost": val("Moisture Content [% by weight]", col),
            "zapalvane_oblak": ig[col] if col is not None else "",
            "zapalvane_metod": ("G-G" if "G-G" in ig_key else "BAM" if "BAM" in ig_key else "") if col is not None else "",
            "tleene_sloy": val("Glowing Temperature [°C]"), "dgv": val("Lower Ex-Limit [g/m3]"),
            "url": URL.format(nr=nr)}


def build(cache, today):
    rows = []
    for z in csv.DictReader(open(ZAPISI, encoding="utf-8")):
        d = parse(z["nr"], fetch(z["nr"], cache))
        if not (d["zapalvane_oblak"] or d["tleene_sloy"]):
            raise SystemExit(f"GESTIS-STAUB-EX {z['nr']}: записът няма температура на запалване или тлеене")
        rows.append({"kluch": f"gestis-staub:{z['nr']}", "ime": z["ime"], "sinonimi": z["sinonimi"],
                     "proveren": today, **d})
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", help="папка за свалените страници")
    ap.add_argument("--check", action="store_true", help="само сверява таблицата със записите")
    a = ap.parse_args()
    rows = build(a.cache, datetime.date.today().isoformat())
    if a.check:
        old = {r["kluch"]: r for r in csv.DictReader(open(OUT, encoding="utf-8"))}
        diff = [f"✗ {r['kluch']} {c}: „{old.get(r['kluch'], {}).get(c, '')}“ ≠ „{r[c]}“"
                for r in rows for c in COLUMNS if c != "proveren" and old.get(r["kluch"], {}).get(c, "") != r[c]]
        print("\n".join(diff) or "✅ таблицата съвпада със записите")
        sys.exit(1 if diff else 0)
    with open(OUT, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(rows)
    print(f"✅ {len(rows)} проби прах → {os.path.relpath(OUT, ROOT)}")


if __name__ == "__main__":
    main()
