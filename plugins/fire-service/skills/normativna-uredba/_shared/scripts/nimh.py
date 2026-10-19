#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
nimh.py — месечните данни на станция на НИМХ от Месечния хидрометеорологичен бюлетин на
Националния институт по метеорология и хидрология (НИМХ) – Таблица 1 „Метеорологична справка“:
средна месечна температура и отклонение от нормата, максимална и минимална температура с датите,
месечна сума на валежа и % от нормата, максимален денонощен валеж с датата, брой дни с валеж
≥ 1 mm и ≥ 10 mm, със силен вятър (≥ 14 m/s) и с гръмотевици.

За засушаването, валежите и топлината през месеца преди пожара – не за часа на пожара
(за него е METAR, vreme.py). Бюлетинът излиза след края на месеца.

    python3 nimh.py 2025-08                          # станция Плевен
    python3 nimh.py 2025-08 --stantsiya "В. Търново"
    python3 nimh.py 2025-08 --mesto "Левски"         # най-близката станция до населеното място
    python3 nimh.py 2025-07 2025-08                  # няколко месеца подред
    python3 nimh.py 2025-08 --fail Buletin.pdf       # бюлетинът, свален другаде

Дава стойностите и маркера за позоваване в ЕПТЗ: [[nimh:2025-08: Плевен]] → „(НИМХ, бюлетин за
август 2025 г.)“; в литературата – бюлетинът с месеца. Стойностите се пишат както са в таблицата.

Грешки (на stderr, код ≠ 0): NO_NETWORK, NO_DATA, BAD_INPUT.
"""
import argparse
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
URLS = ("https://bulletins.cfd.meteo.bg/bull/Buletin_NIMH_{ym}.pdf",
        "https://bulletins.meteo.bg/bull/Buletin_NIMH_{ym}.pdf")
MESETSI = ["януари", "февруари", "март", "април", "май", "юни", "юли", "август", "септември",
           "октомври", "ноември", "декември"]
# the operational stations of Таблица 1, with their approximate coordinates
STANTSII = {
    "София": (42.65, 23.38), "Видин": (43.99, 22.87), "Монтана": (43.41, 23.23), "Враца": (43.20, 23.55),
    "Плевен": (43.41, 24.62), "В. Търново": (43.08, 25.62), "Русе": (43.85, 25.95), "Разград": (43.53, 26.52),
    "Добрич": (43.57, 27.83), "Варна": (43.20, 27.92), "Бургас": (42.50, 27.47), "Сливен": (42.68, 26.32),
    "Кърджали": (41.65, 25.37), "Пловдив": (42.15, 24.75), "Благоевград": (42.02, 23.10),
    "Сандански": (41.57, 23.28), "Кюстендил": (42.28, 22.69),
}
POLETA = [("sredna", "средна месечна температура", "°C"), ("otklonenie", "отклонение от нормата", "°C"),
          ("max", "максимална температура", "°C"), ("max_data", "на дата", ""),
          ("min", "минимална температура", "°C"), ("min_data", "на дата", ""),
          ("valezh", "месечна сума на валежа", "mm"), ("valezh_norma", "% от нормата", "%"),
          ("valezh_max", "максимален денонощен валеж", "mm"), ("valezh_max_data", "на дата", ""),
          ("dni_1mm", "дни с валеж ≥ 1 mm", ""), ("dni_10mm", "дни с валеж ≥ 10 mm", ""),
          ("dni_vyatar", "дни със силен вятър (≥ 14 m/s)", ""), ("dni_gram", "дни с гръмотевици", "")]
NUM = r"-?\d+(?:[.,]\d+)?"


class Problem(Exception):
    pass


def km(a, b):
    la1, lo1, la2, lo2 = map(math.radians, (*a, *b))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(h))


def nay_blizka(mesto):
    """The nearest station to a settlement of the РДПБЗН – Плевен area (by ЕКАТТЕ, as in vreme.py)."""
    sys.path.insert(0, HERE)
    import vreme
    try:
        lat, lon = map(float, vreme.koordinati(mesto).split(","))
    except vreme.Problem as e:
        raise Problem(str(e).replace(" – дай --blizo ШИРИНА,ДЪЛЖИНА", " – дай --stantsiya"))
    name = min(STANTSII, key=lambda s: km((lat, lon), STANTSII[s]))
    return name, round(km((lat, lon), STANTSII[name]))


def mesets(ym):
    y, m = ym.split("-")
    return f"{MESETSI[int(m) - 1]} {y} г."


def tekst_ot_pdf(path):
    if shutil.which("pdftotext"):
        r = subprocess.run(["pdftotext", "-layout", path, "-"], capture_output=True, text=True)
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout
    try:
        import pypdf
        return "\n".join(p.extract_text(extraction_mode="layout") or "" for p in pypdf.PdfReader(path).pages)
    except Exception as e:  # noqa: BLE001
        raise Problem(f"NO_DATA: PDF-ът не се чете ({e}) – нужни са pdftotext (poppler-utils) или pypdf")


def svali(ym, fail=None):
    """The text of the bulletin for the month „ГГГГ-ММ“."""
    if fail:
        return tekst_ot_pdf(fail)
    errors = []
    for u in URLS:
        url = u.format(ym=ym.replace("-", ""))
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "fire-service"}),
                                        timeout=40) as r:
                data = r.read()
            if not data.startswith(b"%PDF"):
                errors.append(f"{url}: не е PDF")
                continue
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
                f.write(data)
            try:
                return tekst_ot_pdf(f.name)
            finally:
                os.unlink(f.name)
        except urllib.error.HTTPError as e:
            errors.append(f"{url}: HTTP {e.code}")
        except Exception as e:  # noqa: BLE001
            errors.append(f"{url}: {e}")
    if errors and all("HTTP 404" in e for e in errors):
        raise Problem(f"NO_DATA: бюлетинът за {mesets(ym)} още не е публикуван или го няма ({URLS[0].format(ym=ym.replace('-', ''))})")
    raise Problem("NO_NETWORK: бюлетинът не се сваля (" + "; ".join(errors) + "). Свали PDF-а другаде "
                  f"({URLS[0].format(ym=ym.replace('-', ''))}) и пусни отново с --fail ФАЙЛ.pdf")


def red(text, stantsiya):
    """The row of the station in Таблица 1, as a dict."""
    i = text.find("Таблица 1")
    part = text[i:i + 6000] if i >= 0 else text
    name = re.escape(stantsiya).replace(r"\ ", r"\s*")
    m = re.search(rf"^\s*{name}\s+((?:{NUM}\s+){{13}}{NUM})\s*$", part, re.M)
    if not m:
        raise Problem(f"NO_DATA: в Таблица 1 няма ред за станция {stantsiya}")
    vals = m.group(1).split()
    return {k: v.replace(",", ".") for (k, _, _), v in zip(POLETA, vals)}


def marker(ym, stantsiya):
    return f"[[nimh:{ym}: {stantsiya}]]"


def main(argv=None):
    ap = argparse.ArgumentParser(description="месечните данни на станция на НИМХ от бюлетина")
    ap.add_argument("mesetsi", nargs="+", help="ГГГГ-ММ (един или няколко месеца)")
    ap.add_argument("--stantsiya", default=None, help="станция от Таблица 1 (по подразбиране Плевен)")
    ap.add_argument("--mesto", help="населено място – взима най-близката станция")
    ap.add_argument("--fail", help="бюлетинът като PDF, свален другаде (само за един месец)")
    a = ap.parse_args(argv)
    try:
        for ym in a.mesetsi:
            if not re.fullmatch(r"\d{4}-\d{2}", ym) or not 1 <= int(ym[5:]) <= 12:
                raise Problem(f"BAD_INPUT: месецът е ГГГГ-ММ, а е „{ym}“")
        st, dist = a.stantsiya or "Плевен", None
        if a.mesto and not a.stantsiya:
            st, dist = nay_blizka(a.mesto)
        if st not in STANTSII:
            raise Problem(f"BAD_INPUT: няма станция „{st}“ – станциите са: {', '.join(STANTSII)}")
        for ym in a.mesetsi:
            r = red(svali(ym, a.fail), st)
            print(f"Станция {st} на НИМХ, {mesets(ym)}" + (f" (на около {dist} km от {a.mesto})" if dist is not None else ""))
            for k, label, unit in POLETA:
                v = r[k]
                if k.endswith("_data"):
                    continue
                data = r.get(k + "_data")
                print(f"  {label}: {v}{(' ' + unit) if unit else ''}" + (f" (на {data}.)" if data else ""))
            print(f"  маркер в ЕПТЗ: {marker(ym, st)}")
    except Problem as e:
        print(str(e), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
