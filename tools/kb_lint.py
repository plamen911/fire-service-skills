#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
kb_lint.py — проверява нормативната база (Fire Safety Regulatory Documents) по правилата в
tools/kb_schema.md и генерира машинния каталог index.json и блока с броевете в индекса.

Работи върху копие на базата в папка (сваля се с `python3 tools/admin.py regs pull ПАПКА`):

    python3 tools/kb_lint.py ПАПКА               # проверка; код 1 при грешка
    python3 tools/kb_lint.py ПАПКА --catalog     # и записва ПАПКА/index.json и броевете в индекса
    python3 tools/kb_lint.py ПАПКА --json        # находките като JSON

Броевете в заглавката на индекса и index.json се генерират от файловете – не се пишат на ръка.
Така индексът, каталогът и самите файлове не могат да се разминат: проверката пада, ако
блокът в индекса или index.json не съвпадат с генерираното.
"""
import argparse
import glob
import json
import os
import re
import sys

import yaml

TIERS = {"tier-a": "A", "tier-a-repealed": "A-REPEALED", "tier-b": "B", "tier-c": "C"}
OTHER_FOLDERS = {"указания-и-писма"}          # written by the Zen assistant; outside the schema
IN_FORCE = ["да", "не", "отменен", "остарял", "непроверен", "неприложимо"]
REQUIRED = ["title", "tier", "issuer", "act_type", "in_force", "text_source", "keywords"]
REQUIRED_A = ["act_id", "subject", "articles", "in_force_source"]
REQUIRED_B = ["subject"]
MAX_TITLE = 300
MIN_WORDS = 30
NAME_RX = re.compile(
    r"^(?P<issuer>[A-Za-z0-9-]+)_(?P<type>[A-Za-z-]+)_(?P<topic>.+?)"
    r"_(?P<year>\d{4}(?:-\d{2})?|UNKNOWN)"
    r"(?:_ed(?P<ed>\d{4}-\d{2}-\d{2}|[0-9a-f]{8}))?"
    r"(?P<suffix>(?:_[A-Za-z0-9-]+)*)\.(?:md|json)$")
EDITION_DATE_RX = re.compile(r"^(\d{4}(-\d{2}(-\d{2})?)?|UNKNOWN)$")
ARTICLES_RX = re.compile(r"^(\d+)-(\d+)$")
HEADING_RX = re.compile(r"^#{1,6}\s*Чл\.\s*(\d+)([а-я]?)\s*\.?\s*$", re.M)
INDEX_PATH_RX = re.compile(r"`((?:tier-a|tier-a-repealed|tier-b|tier-c)/[^`]*?)`")
MAP_REF_RX = re.compile(r"`(_MAP_[^`]+?\.md)`")
TEXT_EXT = (".md", ".json", ".csv", ".txt")
COUNTS_BEGIN = "<!-- AUTO-COUNTS"
COUNTS_END = "<!-- /AUTO-COUNTS -->"


def split_front_matter(text):
    """(dict or None, body, error) for a Markdown file with optional YAML front matter."""
    if not text.startswith("---\n"):
        return None, text, None
    m = re.match(r"^---\n(.*?)\n---\n?", text, re.S)
    if not m:
        return None, text, "front matter без затварящ ред ---"
    try:
        data = yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError as e:
        return None, text[m.end():], f"front matter не е валиден YAML: {str(e).splitlines()[0]}"
    if not isinstance(data, dict):
        return None, text[m.end():], "front matter не е речник"
    return data, text[m.end():], None


def status(fm):
    """in_force as text – YAML reads a bare yes/no/true as a boolean."""
    v = (fm or {}).get("in_force")
    if isinstance(v, bool):
        return "yes" if v else "no"
    return None if v is None else str(v)


def words(body):
    """Words of the body, without the blockquote notes added at ingestion."""
    lines = [ln for ln in body.splitlines() if not ln.lstrip().startswith(">")]
    return len(re.findall(r"\w+", "\n".join(lines)))


def load(root):
    files = []
    for path in sorted(glob.glob(os.path.join(root, "**", "*"), recursive=True)):
        if os.path.isdir(path):
            continue
        rel = os.path.relpath(path, root).replace(os.sep, "/")
        if rel == "listing.json" or rel.startswith("."):
            continue
        folder = rel.split("/")[0] if "/" in rel else ""
        rec = {"path": rel, "folder": folder, "name": os.path.basename(rel), "bytes": os.path.getsize(path)}
        if rel.endswith(".md"):
            with open(path, encoding="utf-8") as f:
                text = f.read()
            fm, body, err = split_front_matter(text)
            rec.update(fm=fm, body=body, fm_error=err, words=words(body))
        files.append(rec)
    # files the server does not hand out as text (PDF originals) are known only from the listing that
    # `admin.py regs pull` saves next to the copy; text files count only when they are on disk
    listing = os.path.join(root, "listing.json")
    if os.path.exists(listing):
        have = {f["path"] for f in files}
        with open(listing, encoding="utf-8") as fh:
            for item in json.load(fh):
                if item["path"] not in have and not item["name"].lower().endswith(TEXT_EXT):
                    files.append({"path": item["path"], "folder": item.get("folder", ""), "name": item["name"],
                                  "bytes": int(item.get("size") or 0), "remote_only": True})
        files.sort(key=lambda f: f["path"])
    return files


def index_file(files):
    idx = [f for f in files if f["folder"] == "" and f["name"].startswith("_INDEX_") and f["name"].endswith(".md")]
    return idx


def map_target(rec):
    m = re.search(r"\*\*Файл:\*\*\s*`(tier-a/[^`]+?\.md)`", rec.get("body", ""))
    return m.group(1) if m else None


def build_catalog(files):
    maps = {}
    for f in files:
        if f["folder"] == "" and f["name"].startswith("_MAP_"):
            target = map_target(f)
            if target:
                maps[target] = f["name"]
    out = []
    for f in files:
        if f["folder"] not in TIERS:
            continue
        fm = f.get("fm") or {}
        out.append({
            "path": f["path"], "tier": fm.get("tier", TIERS[f["folder"]]),
            "title": fm.get("title"), "act_id": fm.get("act_id"), "act_type": fm.get("act_type"),
            "issuer": fm.get("issuer"), "in_force": status(fm), "in_force_note": fm.get("in_force_note"),
            "edition_date": None if fm.get("edition_date") is None else str(fm.get("edition_date")),
            "superseded_by": fm.get("superseded_by"), "subject": fm.get("subject"),
            "keywords": fm.get("keywords") or [], "articles": None if fm.get("articles") is None else str(fm.get("articles")),
            "map": maps.get(f["path"]), "bytes": f["bytes"],
        })
    return {"generated_by": "tools/kb_lint.py --catalog", "files": out}


def counts(files):
    tier_a = [f for f in files if f["folder"] == "tier-a" and f["path"].endswith(".md") and f.get("fm")]
    current = [f for f in tier_a if status(f["fm"]) != "не"]
    acts = {f["fm"].get("act_id") for f in tier_a}
    by_status = {}
    for f in current:
        st = status(f["fm"])
        by_status[st] = by_status.get(st, 0) + 1
    articles = sum(len(set(HEADING_RX.findall(f["body"]))) for f in current)
    pdf_a = sum(1 for f in files if f["folder"] == "tier-a" and f["path"].endswith(".pdf"))
    return {
        "acts": len(acts), "files_md": len(tier_a), "superseded": len(tier_a) - len(current), "pdf": pdf_a,
        "status": by_status, "articles": articles,
        "repealed": sum(1 for f in files if f["folder"] == "tier-a-repealed" and f["path"].endswith(".md")),
        "tier_b": sum(1 for f in files if f["folder"] == "tier-b"),
        "tier_c": sum(1 for f in files if f["folder"] == "tier-c"),
        "maps": sum(1 for f in files if f["folder"] == "" and f["name"].startswith("_MAP_")),
    }


def counts_block(c):
    status = ", ".join(f"{n} `{k}`" for k, n in sorted(c["status"].items(), key=lambda x: (-x[1], x[0])))
    return "\n".join([
        f"{COUNTS_BEGIN} – генерира се с `python3 tools/kb_lint.py ПАПКА --catalog`; не се редактира на ръка -->",
        f"- Действащи актове (tier-a): {c['acts']} акта в {c['files_md']} текстови файла (.md), от тях "
        f"{c['superseded']} заменени редакции; {c['pdf']} PDF оригинала",
        f"- Актуалност на действащите редакции: {status}",
        f"- Адресируеми члена в действащите редакции (заглавия „## Чл. N“): {c['articles']}",
        f"- Отменени актове (tier-a-repealed): {c['repealed']}",
        f"- tier-b: {c['tier_b']} файла · tier-c: {c['tier_c']} файла · секционни карти: {c['maps']}",
        f"- Машинният каталог на всички файлове е `index.json` в корена.",
        COUNTS_END,
    ])


def check(root, files):
    errors, warnings = [], []
    E = lambda p, m: errors.append((p, m))      # noqa: E731
    W = lambda p, m: warnings.append((p, m))    # noqa: E731
    paths = {f["path"] for f in files}

    idx = index_file(files)
    if len(idx) != 1:
        E("(корен)", f"трябва да има точно един _INDEX_*.md, има {len(idx)}: {[f['name'] for f in idx]}")
    index = idx[0] if idx else None

    for f in files:
        p, folder = f["path"], f["folder"]
        if folder == "":
            if not re.match(r"^(_INDEX_|_MAP_|_READING_MAP_).+\.md$|^index\.json$", f["name"]):
                W(p, "непознат файл в корена")
            continue
        if folder in OTHER_FOLDERS:
            continue
        if folder not in TIERS:
            E(p, f"папката „{folder}“ не е част от базата")
            continue
        if p.endswith(".pdf"):
            continue
        if not f["name"].isascii() or not NAME_RX.match(f["name"]):
            E(p, "името не следва правилото Издател_Вид_Тема_Година[_edГГГГ-ММ-ДД][_Наставка].md")
        if not p.endswith(".md") or f.get("remote_only"):
            continue
        fm = f.get("fm")
        if f.get("fm_error"):
            E(p, f["fm_error"])
            continue
        if fm is None:
            E(p, "няма front matter")
            continue
        tier = TIERS[folder]
        need = REQUIRED + (REQUIRED_A if tier in ("A", "A-REPEALED") else REQUIRED_B if tier == "B" else [])
        for k in need:
            v = fm.get(k)
            if v is None or (isinstance(v, str) and not v.strip()):
                E(p, f"липсва поле {k}")
        if fm.get("tier") not in (None, tier):
            E(p, f"tier: {fm.get('tier')!r}, а папката е за {tier}")
        if status(fm) not in IN_FORCE:
            E(p, f"in_force: {status(fm)!r} – допустими са {', '.join(IN_FORCE)}")
        if not isinstance(fm.get("keywords", []), list):
            E(p, "keywords трябва да е списък")
        elif tier in ("A", "A-REPEALED") and not fm.get("keywords"):
            E(p, "keywords е празен")
        title = str(fm.get("title") or "")
        if len(title) > MAX_TITLE or "\n" in title:
            E(p, f"title е {len(title)} знака – най-много {MAX_TITLE}, на един ред (текстът е в тялото)")
        ed = fm.get("edition_date")
        if ed not in (None, "") and not EDITION_DATE_RX.match(str(ed)):
            E(p, f"edition_date: {ed!r} – ГГГГ-ММ-ДД, ГГГГ-ММ, ГГГГ или UNKNOWN")
        sup = fm.get("superseded_by")
        if sup and sup not in paths:
            E(p, f"superseded_by сочи несъществуващ файл: {sup}")
        if tier == "A" and status(fm) == "не" and not sup:
            E(p, "заменена редакция без superseded_by")
        if tier == "A" and status(fm) == "отменен":
            E(p, "отменен акт стои в tier-a – мястото му е tier-a-repealed")
        if tier == "A-REPEALED":
            if status(fm) != "отменен":
                E(p, "в tier-a-repealed in_force трябва да е „отменен“")
            if not fm.get("repealed_by"):
                E(p, "липсва repealed_by")
        if f["words"] < MIN_WORDS:
            E(p, f"тялото има {f['words']} думи – файл без текст (само заглавие) не се държи в базата")
        m = ARTICLES_RX.match(str(fm.get("articles") or ""))
        if tier in ("A", "A-REPEALED") and m:
            lo, hi = int(m.group(1)), int(m.group(2))
            have = {int(n) for n, _ in HEADING_RX.findall(f["body"])}
            missing = [n for n in range(lo, hi + 1) if n not in have]
            if missing:
                E(p, f"articles {lo}-{hi}, но липсват заглавия „## Чл. N“ за {missing[:10]}"
                     f"{' …' if len(missing) > 10 else ''}")

    # maps
    for f in files:
        if f["folder"] == "" and f["name"].startswith("_MAP_"):
            target = map_target(f)
            if not target:
                E(f["path"], "картата няма ред „**Файл:** `tier-a/…`“")
            elif target not in paths:
                E(f["path"], f"картата сочи несъществуващ файл: {target}")
            if index and f["name"] not in index["body"]:
                E(f["path"], "картата не е в указателя на индекса")

    # index references and coverage
    if index:
        body = index["body"]
        m = re.search(r"_(\d{4}-\d{2}-\d{2})([a-z]+)\.md$", index["name"])
        if not m:
            E(index["path"], "името на индекса трябва да завършва на _ГГГГ-ММ-ДД<редакция>.md")
        elif f"(редакция {m.group(2)})" not in body:
            E(index["path"], f"заглавката не казва „(редакция {m.group(2)})“ като името на файла")
        for ref in sorted(set(INDEX_PATH_RX.findall(body))):
            if "…" in ref or "..." in ref:
                E(index["path"], f"съкратен път в индекса: {ref}")
            elif ref.endswith("/"):
                continue
            elif ref not in paths:
                E(index["path"], f"индексът сочи несъществуващ файл: {ref}")
        for ref in sorted(set(MAP_REF_RX.findall(body))):
            if "*" in ref:
                continue
            if not any(f["name"] == ref for f in files if f["folder"] == ""):
                E(index["path"], f"индексът сочи несъществуваща карта: {ref}")
        for f in files:
            if f["folder"] in ("tier-a", "tier-a-repealed") and f["path"].endswith(".md") and f["path"] not in body:
                E(f["path"], "файлът не е описан в индекса (пълният път липсва)")
        block = re.search(re.escape(COUNTS_BEGIN) + r".*?" + re.escape(COUNTS_END), body, re.S)
        expected = counts_block(counts(files))
        if not block:
            E(index["path"], "липсва блокът с броевете (AUTO-COUNTS)")
        elif block.group(0) != expected:
            E(index["path"], "броевете в индекса не съвпадат с файловете – пусни kb_lint.py --catalog")

    catalog_path = os.path.join(root, "index.json")
    if not os.path.exists(catalog_path):
        E("index.json", "липсва – пусни kb_lint.py --catalog")
    else:
        with open(catalog_path, encoding="utf-8") as fh:
            try:
                have = json.load(fh)
            except ValueError:
                have = None
        if have != build_catalog(files):
            E("index.json", "не съвпада с файловете – пусни kb_lint.py --catalog")
    return errors, warnings


def write_catalog(root, files):
    files = [f for f in files if f["path"] != "index.json"]
    cat = build_catalog(files)
    with open(os.path.join(root, "index.json"), "w", encoding="utf-8") as fh:
        json.dump(cat, fh, ensure_ascii=False, indent=1)
        fh.write("\n")
    idx = index_file(files)
    if len(idx) == 1:
        path = os.path.join(root, idx[0]["path"])
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        block = counts_block(counts(files))
        rx = re.compile(re.escape(COUNTS_BEGIN) + r".*?" + re.escape(COUNTS_END), re.S)
        if rx.search(text):
            text = rx.sub(lambda _: block, text, count=1)
        else:
            sys.exit("BAD_STATE: в индекса няма блок AUTO-COUNTS – добави ред „<!-- AUTO-COUNTS -->“ и "
                     "„<!-- /AUTO-COUNTS -->“ там, където трябва да са броевете")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
    return cat


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("folder")
    ap.add_argument("--catalog", action="store_true", help="записва index.json и броевете в индекса")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    if a.catalog:
        write_catalog(a.folder, load(a.folder))
    files = load(a.folder)
    errors, warnings = check(a.folder, [f for f in files if f["path"] != "index.json"])
    if a.json:
        print(json.dumps({"errors": errors, "warnings": warnings}, ensure_ascii=False, indent=1))
    else:
        for p, m in warnings:
            print(f"WARN  {p}: {m}")
        for p, m in errors:
            print(f"ERROR {p}: {m}")
        print(f"KB_LINT: {len(errors)} грешки, {len(warnings)} предупреждения, {len(files)} файла")
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
