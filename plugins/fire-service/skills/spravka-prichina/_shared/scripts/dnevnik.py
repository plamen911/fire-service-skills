#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
dnevnik.py — дневникът на ползването: един ред за всяко изготвено ЕПТЗ, записан през n8n в
таблицата в Google Sheets „fire-service – дневник на ЕПТЗ“ (папка fire-service/_admin в Drive). Без текста на заключението, без
имена на свидетели и пострадали, без имената на файловете и без координати от снимките – само
данни, по които администраторът вижда как се ползва плъгинът и какво да подобри:

- кога (дата и час, местно време), кой експерт, по кое дело, какво, колко страници, каква сума;
- как са подадени материалите: снимки, PDF файлове и страници (от тях сканирани – без текстов
  слой), други файлове, текст в чата; общият обем в MB и средната резолюция на снимките;
- с какво са заснети или сканирани: марка и модел на телефона от EXIF на снимките, програмата,
  създала PDF файла (напр. скенерът на iPhone, Adobe Scan, CamScanner);
- колко минути са минали от качването на материалите до сметката;
- средата: версия на плъгина, къде работи скриптът (claude.ai, Claude Code, компютър), моделът,
  устройството на потребителя, ако е известно, режимът (скрипт или конектор), находките от прегледа.

    python3 _shared/scripts/dnevnik.py eptz --ekspert "Иван Петров" --zm "430/2026" \\
        --dp "6082/2026" --obekt "овощна градина" --prichina "суха трева – изпускателна система" \\
        --stranitsi 9 --suma 170.29 --materiali /mnt/user-data/uploads/* \\
        --model "Claude Opus 5.5" --ustroystvo "телефон" --nahodki 3

`--materiali` брои сам по файловете, които потребителят е качил. Без достъп до файловете –
`--snimki`, `--pdf`, `--pdf-stranitsi`, `--skanirani`, `--drugi` на ръка; `--tekst`, когато
данните по делото са написани в чата.

Записва всеки с личен ключ; чете таблицата само администраторът (в Drive). Пуска се веднъж,
след като сметката е готова. Повторен запис за същото ЗМ, експерт и дата обновява реда (и брои
корекциите), не добавя нов.

Дневникът никога не спира работата: при грешка скриптът пише предупреждение на stderr
(DNEVNIK_SKIPPED: …) и завършва с код 0. `--dry-run` само отпечатва реда.
"""
import argparse
import datetime
import glob
import json
import os
import platform
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import api_config  # noqa: E402  (addresses of n8n and the personal key)

KINDS = ("eptz",)
IMG = {".jpg", ".jpeg", ".png", ".heic", ".heif", ".webp", ".gif", ".bmp", ".tif", ".tiff"}


def plugin_version():
    """The plugin version from plugin.json, when the skill sits inside the plugin."""
    for up in ("../..", "../../..", "../../../.."):
        p = os.path.normpath(os.path.join(HERE, up, ".claude-plugin", "plugin.json"))
        if os.path.exists(p):
            try:
                return json.load(open(p, encoding="utf-8")).get("version", "")
            except ValueError:
                return ""
    return ""


def local_now():
    """Date and time in Europe/Sofia (the users' time), whatever the sandbox clock zone is."""
    try:
        from zoneinfo import ZoneInfo
        return datetime.datetime.now(ZoneInfo("Europe/Sofia"))
    except Exception:  # noqa: BLE001
        return datetime.datetime.now()


def sreda():
    """Where the script runs – told by the environment, never by the user."""
    e = os.environ
    entry = e.get("CLAUDE_CODE_ENTRYPOINT", "")
    if e.get("CLAUDECODE") or entry:
        where = "Claude Code" + (f" ({entry})" if entry else "")
        if e.get("CLAUDE_CODE_REMOTE") == "true":
            where += ", облак"
    elif os.path.isdir("/mnt/user-data"):
        where = "claude.ai (пясъчник)"
    else:
        where = "скрипт"
    osname = {"Darwin": "macOS", "Windows": "Windows", "Linux": "Linux"}.get(platform.system(), platform.system())
    return f"{where}; {osname}"


def pdf_info(path):
    """(pages, scanned pages, producer) of a PDF; a page with almost no text counts as scanned."""
    n, prod = 0, ""
    try:
        out = subprocess.run(["pdfinfo", path], capture_output=True, text=True, timeout=30).stdout
        for line in out.splitlines():
            k, _, v = line.partition(":")
            if k == "Pages":
                n = int(v.strip())
            elif k in ("Producer", "Creator") and v.strip() and not prod:
                prod = v.strip()
    except Exception:  # noqa: BLE001
        try:
            import pypdf
            rd = pypdf.PdfReader(path)
            n = len(rd.pages)
            meta = rd.metadata or {}
            prod = str(meta.get("/Producer") or meta.get("/Creator") or "")
        except Exception:  # noqa: BLE001
            return 0, 0, ""
    try:
        txt = subprocess.run(["pdftotext", "-layout", path, "-"], capture_output=True, text=True,
                             timeout=120).stdout
        pages = txt.split("\f")[:n]
        skan = sum(1 for p in pages if len(p.strip()) < 30) + max(0, n - len(pages))
    except Exception:  # noqa: BLE001
        skan = n
    return n, skan, prod[:60]


def image_info(path):
    """(megapixels, "Make Model") of a photo; GPS and dates are never read."""
    try:
        from PIL import Image
        try:
            import pillow_heif  # noqa: F401
            pillow_heif.register_heif_opener()
        except Exception:  # noqa: BLE001
            pass
        with Image.open(path) as im:
            mp = im.size[0] * im.size[1] / 1e6
            ex = im.getexif() or {}
            make, model = str(ex.get(271, "")).strip(), str(ex.get(272, "")).strip()
        cam = model if make and model.lower().startswith(make.lower()) else f"{make} {model}".strip()
        return mp, cam[:40]
    except Exception:  # noqa: BLE001
        return None, ""


def count_materials(paths):
    """What the user uploaded: counts, size, resolution, capture devices, scanner apps, upload time."""
    c = {"snimki": 0, "pdf": 0, "pdf_stranitsi": 0, "skanirani": 0, "drugi": 0}
    files = []
    for p in paths:
        files += [f for f in glob.glob(os.path.join(p, "**", "*"), recursive=True)
                  if os.path.isfile(f)] if os.path.isdir(p) else [p]
    files = [f for f in files if os.path.isfile(f)]
    size, mps, kameri, programi = 0, [], {}, {}
    for f in files:
        size += os.path.getsize(f)
        ext = os.path.splitext(f)[1].lower()
        if ext in IMG:
            c["snimki"] += 1
            mp, cam = image_info(f)
            if mp:
                mps.append(mp)
            if cam:
                kameri[cam] = kameri.get(cam, 0) + 1
        elif ext == ".pdf":
            n, skan, prod = pdf_info(f)
            c["pdf"] += 1
            c["pdf_stranitsi"] += n
            c["skanirani"] += skan
            if prod:
                programi[prod] = programi.get(prod, 0) + 1
        else:
            c["drugi"] += 1
    oldest = min((os.path.getmtime(f) for f in files), default=None)
    extra = {
        "obem_mb": round(size / 1e6, 1) if files else "",
        "rezolyutsiya_mp": round(sum(mps) / len(mps), 1) if mps else "",
        "kamera": ", ".join(f"{k} ×{v}" for k, v in sorted(kameri.items(), key=lambda x: -x[1]))[:120],
        "pdf_programa": ", ".join(f"{k} ×{v}" for k, v in sorted(programi.items(), key=lambda x: -x[1]))[:120],
        "minuti": round((time.time() - oldest) / 60) if oldest else "",
    }
    return c, extra


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
    if a.materiali:
        c, extra = count_materials(a.materiali)
    else:
        c = {"snimki": 0, "pdf": 0, "pdf_stranitsi": 0, "skanirani": 0, "drugi": 0}
        extra = {"obem_mb": "", "rezolyutsiya_mp": "", "kamera": "", "pdf_programa": "", "minuti": ""}
    for k in c:  # numbers given by hand win over the counted ones
        v = getattr(a, k)
        if v is not None:
            if v < 0:
                sys.exit(f"BAD_INPUT: --{k.replace('_', '-')} не може да е отрицателно")
            c[k] = v
    if a.minuti is not None:
        extra["minuti"] = a.minuti
    now = local_now()
    return {
        "vid": a.vid,
        "data": a.data or now.date().isoformat(),
        "chas": now.strftime("%H:%M"),
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
        **extra,
        "nahodki": a.nahodki,
        "model": (a.model or "").strip(),
        "ustroystvo": (a.ustroystvo or "").strip(),
        "sreda": sreda(),
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
    ap.add_argument("--minuti", type=int, help="минути от качването до сметката (иначе по файловете)")
    ap.add_argument("--nahodki", type=int, help="находки от двата прегледа преди предаването")
    ap.add_argument("--model", help="моделът, с който работиш, напр. Claude Opus 5.5")
    ap.add_argument("--ustroystvo", help="телефон, таблет или компютър – ако е известно от разговора")
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
