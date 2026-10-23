#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
dnevnik.py — дневникът на ползването: един ред за всяко изготвено ЕПТЗ, записан през n8n в
таблицата „fire-service – дневник на ЕПТЗ“ в Google Drive. Без текста на заключението, без
имена на свидетели и пострадали – само кога, кой експерт, по кое дело, какво, колко страници,
каква сума и КАК са подадени материалите по делото: колко снимки, колко PDF файла с колко
страници (от тях сканирани – без текстов слой), други файлове и дали има текст, написан в чата.
По тях администраторът преценява изразходваните токени и кой как подава материалите.

    python3 _shared/scripts/dnevnik.py eptz --ekspert "Иван Петров" --zm "430/2026" \
        --dp "6082/2026" --obekt "овощна градина" --prichina "суха трева – изпускателна система" \
        --stranitsi 9 --suma 170.29 --materiali /mnt/user-data/uploads/*

`--materiali` брои сам по файловете, които потребителят е качил: снимките (jpg, png, heic…),
PDF файловете и страниците им (`pdfinfo`), сканираните страници (без текст при `pdftotext`) и
другите файлове. Без достъп до файловете – `--snimki`, `--pdf`, `--pdf-stranitsi`,
`--skanirani`, `--drugi` на ръка; `--tekst`, когато данните по делото са написани в чата.

Записва всеки с личен ключ; чете таблицата само администраторът (в Drive). Пуска се веднъж,
след като сметката е готова. Повторен запис за същото ЗМ, експерт и дата обновява реда, не
добавя нов – затова при корекции може да се пусне отново.

Дневникът никога не спира работата: при грешка скриптът пише предупреждение на stderr
(DNEVNIK_SKIPPED: …) и завършва с код 0. `--dry-run` само отпечатва реда.
"""
import argparse
import datetime
import json
import glob
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import api_config  # noqa: E402  (addresses of n8n and the personal key)

KINDS = ("eptz",)


def plugin_version():
    """The plugin version from plugin.json, when the skill sits inside the plugin."""
    for up in ("../../..", "../../../.."):
        p = os.path.normpath(os.path.join(HERE, up, ".claude-plugin", "plugin.json"))
        if os.path.exists(p):
            try:
                return json.load(open(p, encoding="utf-8")).get("version", "")
            except ValueError:
                return ""
    return ""


IMG = {".jpg", ".jpeg", ".png", ".heic", ".heif", ".webp", ".gif", ".bmp", ".tif", ".tiff"}


def pdf_pages(path):
    """(pages, scanned pages) of a PDF; a page with almost no extractable text counts as scanned."""
    try:
        out = subprocess.run(["pdfinfo", path], capture_output=True, text=True, timeout=30).stdout
        n = int(next(l.split(":")[1] for l in out.splitlines() if l.startswith("Pages:")))
    except Exception:  # noqa: BLE001
        try:
            import pypdf
            n = len(pypdf.PdfReader(path).pages)
        except Exception:  # noqa: BLE001
            return 0, 0
    try:
        txt = subprocess.run(["pdftotext", "-layout", path, "-"], capture_output=True, text=True,
                             timeout=120).stdout
        pages = txt.split("\f")[:n]
        skan = sum(1 for p in pages if len(p.strip()) < 30) + max(0, n - len(pages))
    except Exception:  # noqa: BLE001
        skan = n
    return n, skan


def count_materials(paths):
    """Counts of what the user uploaded – photos, PDFs and their (scanned) pages, other files."""
    c = {"snimki": 0, "pdf": 0, "pdf_stranitsi": 0, "skanirani": 0, "drugi": 0}
    files = []
    for p in paths:
        files += [f for f in glob.glob(os.path.join(p, "**", "*"), recursive=True)
                  if os.path.isfile(f)] if os.path.isdir(p) else [p]
    for f in files:
        ext = os.path.splitext(f)[1].lower()
        if ext in IMG:
            c["snimki"] += 1
        elif ext == ".pdf":
            n, skan = pdf_pages(f)
            c["pdf"] += 1
            c["pdf_stranitsi"] += n
            c["skanirani"] += skan
        else:
            c["drugi"] += 1
    return c


def nachin(c, tekst):
    """How the case materials were given, in one short label."""
    parts = []
    if c["snimki"]:
        parts.append("снимки")
    if c["pdf"]:
        if c["skanirani"] and c["skanirani"] >= c["pdf_stranitsi"]:
            parts.append("сканиран PDF")
        elif c["skanirani"]:
            parts.append("PDF (част сканиран)")
        else:
            parts.append("PDF с текст")
    if c["drugi"]:
        parts.append("други файлове")
    if tekst:
        parts.append("текст в чата")
    return " + ".join(parts) or "няма"


def row(a):
    if a.stranitsi is not None and a.stranitsi < 1:
        sys.exit("BAD_INPUT: --stranitsi трябва да е положително число")
    c = count_materials(a.materiali) if a.materiali else {"snimki": 0, "pdf": 0, "pdf_stranitsi": 0,
                                                          "skanirani": 0, "drugi": 0}
    for k in c:  # numbers given by hand win over the counted ones
        v = getattr(a, k)
        if v is not None:
            if v < 0:
                sys.exit(f"BAD_INPUT: --{k.replace('_', '-')} не може да е отрицателно")
            c[k] = v
    return {
        "vid": a.vid,
        "data": a.data or datetime.date.today().isoformat(),
        "ekspert": a.ekspert.strip(),
        "zm": a.zm.strip(),
        "dp": (a.dp or "").strip(),
        "obekt": (a.obekt or "").strip(),
        "prichina": (a.prichina or "").strip(),
        "stranitsi": a.stranitsi,
        "suma_eur": a.suma,
        "nachin": nachin(c, a.tekst),
        "snimki": c["snimki"],
        "pdf": c["pdf"],
        "pdf_stranitsi": c["pdf_stranitsi"],
        "skanirani": c["skanirani"],
        "drugi": c["drugi"],
        "izobrazheniya": c["snimki"] + c["pdf_stranitsi"],
        "tekst_v_chata": bool(a.tekst),
        "via": "script",
        "versiya": plugin_version(),
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("vid", choices=KINDS)
    ap.add_argument("--ekspert", required=True, help="име и фамилия на експерта")
    ap.add_argument("--zm", required=True, help="номер на ЗМ, напр. 430/2026")
    ap.add_argument("--dp", help="номер на ДП")
    ap.add_argument("--obekt", help="тип обект, както в индекса на образците")
    ap.add_argument("--prichina", help="установената причина накратко")
    ap.add_argument("--stranitsi", type=int, help="страници на заключението")
    ap.add_argument("--suma", type=float, help="сумата по сметката в EUR")
    ap.add_argument("--materiali", nargs="*", help="качените файлове (или папка) – броят се сами")
    ap.add_argument("--snimki", type=int, help="качени снимки (на ръка, ако няма --materiali)")
    ap.add_argument("--pdf", type=int, help="качени PDF файлове")
    ap.add_argument("--pdf-stranitsi", dest="pdf_stranitsi", type=int, help="страници в PDF файловете")
    ap.add_argument("--skanirani", type=int, help="от тях сканирани страници (без текст)")
    ap.add_argument("--drugi", type=int, help="други качени файлове")
    ap.add_argument("--tekst", action="store_true", help="данните по делото са написани в чата")
    ap.add_argument("--data", help="ГГГГ-ММ-ДД; по подразбиране днес")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    r = row(a)
    if a.dry_run:
        print(json.dumps(r, ensure_ascii=False))
        return
    try:
        res = api_config.post("dnevnik_url", {"op": "zapis", "row": r}, timeout=30)
    except SystemExit as e:  # NO_KEY / KEY_REJECTED / missing address – logging must not stop the work
        print(f"DNEVNIK_SKIPPED: {e.code}", file=sys.stderr)
        return
    except Exception as e:  # noqa: BLE001
        print(f"DNEVNIK_SKIPPED: {str(e)[:200]}", file=sys.stderr)
        return
    print(json.dumps({"ok": bool(res.get("ok", True)), "red": res.get("red")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
