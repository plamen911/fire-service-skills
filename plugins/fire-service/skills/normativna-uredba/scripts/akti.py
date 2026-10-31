#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
akti.py — внос на цял документ (заповед, правила, инструкция, наредба …) в нормативната база: от
разчетения текст (сканирани страници, снимки, PDF) до готов файл по правилата на базата
(tools/kb_schema.md), с проверка на членовете, търсене на същия акт в базата и добавяне на
следващи страници към вече записан файл.

    python3 scripts/akti.py podgotvi data.json -o akt                  # → akt/MVR_Order_Iz-1775_…_2010.md
    python3 scripts/akti.py proveri akt/ФАЙЛ.md                        # членове, полета, несигурни места
    python3 scripts/akti.py kandidati akt/ФАЙЛ.md [--listing listing.json]
    python3 scripts/akti.py sravni akt/ФАЙЛ.md regs/tier-c_….md        # дубликат / продължение / друго
    python3 scripts/akti.py dopalni regs/tier-c_….md chast.md -o akt [--palen | --nepalen "…"]
    python3 scripts/akti.py zapis akt/ФАЙЛ.md                          # само администраторът

data.json:
{
  "izdatel": "МВР",                    // МВР | ГДПБЗН | РДПБЗН – Плевен | МС | НС | …
  "vid": "заповед",                    // заповед | правила | инструкция | наредба | указания | методика | закон | …
  "nomer": "Iз-1775",                  // номерът на акта ("" – ако няма)
  "data": "2010-08-05",                // датата на акта (ГГГГ-ММ-ДД или ДД.ММ.ГГГГ)
  "zaglavie": "утвърждаване на Правила за безопасност и здраве при работа на органите за „Пожарна безопасност и спасяване“",
  "tema_lat": "Pravila-Bezopasnost-Zdrave-Rabota-Organite-PBS",     // по желание – иначе от заглавието
  "tier": "c",                         // c (по подразбиране: вътрешни заповеди, правила, писма) | a (действащ акт от ДВ)
  "in_force": "непроверен",            // да | не | отменен | остарял | непроверен | неприложимо
  "in_force_note": "вътрешен акт от 2010 г. …",
  "subject": "Безопасност и здраве при работа на служителите от ПБС – …",
  "keywords": ["ЗБУТ", "лостове за спускане"],
  "iztochnik": "OCR на скан (снимки с телефон), сверен с изображенията на страниците",
  "source_file": "Scanned_Document_2_5.pdf + Scanned_Document_3.pdf",
  "act_id": "Iz-1775",                 // по желание – иначе от номера
  "nepalen": "Наличните страници свършват с чл. 115 (стр. 24); следващите не са сканирани.",   // по желание
  "chasti": ["part1.md", "part2.md"]   // текстът – части в реда на страниците (път спрямо data.json)
}

Текстът на всяка част: `# Глава … — …` / `# Раздел …` за главите и разделите, `## Чл. N` за всеки член
(текстът без „Чл. N.“), алинеите „(1) …“ и точките „1. …“ на отделни редове; `[?]` след несигурна дума,
`[нечетливо]`, `[ръкописно: …]`, `[щемпел: …]`, `[подпис]`, `[печат]`. Част, която не започва със
заглавие (`#`), продължава последния абзац на предишната – така страница, скъсана по средата на
изречението, се слепва сама.

Всяка команда отпечатва JSON. proveri връща "greshki" (файлът не се записва, докато ги има) и
"preduprezhdeniya" (да се кажат на потребителя). sravni връща "reshenie": "dublikat" (вече е в базата),
"prodalzhenie" (новото продължава записания файл – dopalni), "nova_redaktsiya" (същият акт, друга дата),
"chast" (новото е част от записания – нищо ново), "razlichen".
"""
import argparse
import datetime
import difflib
import hashlib
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "_shared", "scripts"))
from ukazaniya import fail, out, parse_date, slug, split, translit, typo, yaml_str  # noqa: E402

ISSUERS = {"мвр": "MVR", "гдпбзн": "GDPBZN", "рдпбзн": "RDPBZN-Pleven", "мс": "MS", "министерски съвет": "MS",
           "нс": "NS", "народно събрание": "NS", "мтсп": "MTSP", "мррб": "MRRB", "одмвр": "ODMVR"}
TYPES = {"заповед": "Order", "правила": "Rules", "инструкция": "Instruction", "наредба": "Ordinance",
         "указания": "Guidelines", "методика": "Methodology", "закон": "Law", "правилник": "Regulation",
         "писмо": "Letter", "процедура": "Procedure", "план": "Plan", "класификатор": "Classifier"}
TIERS = {"a": ("A", "tier-a", "regs-a"), "c": ("C", "tier-c", "regs-c")}
IN_FORCE = {"да", "не", "отменен", "остарял", "непроверен", "неприложимо"}
ART = re.compile(r"^## Чл\. (\d+)([а-я]?)\s*$", re.M)
LOOSE_ART = re.compile(r"^(?:Чл|ЧЛ)\s*[.,]\s*\d+", re.M)
UNSURE = re.compile(r"\[\?\]|\[нечетливо\]")
NEPALEN = "> Непълен документ: "
OLD_PAGES_NOTE = re.compile(r"^> (Непълен документ: |Наличните страници)")
NEW_PARA = re.compile(r"^(\(\d+\)|\d+\.\s|[а-я]\)\s|§\s*\d+)")


# ── text ────────────────────────────────────────────────────────────────────

def join_parts(texts):
    """Joins the parts in page order. A part that starts with a heading or a new paragraph – „(4)“, „1.“,
    „а)“, „§ 1.“ – starts a new paragraph; any other part continues the last paragraph of the previous one
    (a page cut in the middle of a sentence)."""
    body = ""
    for t in texts:
        t = t.strip()
        if not t:
            continue
        if not body:
            body = t
        elif t.startswith("#") or NEW_PARA.match(t):
            body = body.rstrip() + "\n\n" + t
        else:
            body = body.rstrip() + " " + t
    return body + "\n"


def articles_of(body):
    found = [(int(n), s) for n, s in ART.findall(body)]
    nums = [n for n, _ in found]
    plain = sorted(set(nums))
    dup = sorted({f"{n}{s}" for n, s in found if found.count((n, s)) > 1})
    order = [f"{a}→{b}" for a, b in zip(nums, nums[1:]) if b < a]
    gaps = [n for n in range(plain[0], plain[-1] + 1) if n not in plain] if plain else []
    return {"ot": plain[0] if plain else None, "do": plain[-1] if plain else None, "broi": len(found),
            "lipsvat": gaps, "povtoreni": dup, "razbarkani": order}


def articles_field(info):
    if not info["broi"]:
        return "без членове"
    if not info["lipsvat"]:
        return f"{info['ot']}-{info['do']}"
    return f"{info['ot']}-{info['do']}, без " + ", ".join(map(str, info["lipsvat"]))


def note(d, tier):
    lines = []
    src = (d.get("iztochnik") or "").lower()
    if "ocr" in src or "скан" in src or "снимк" in src:
        lines.append("> ⚠ Транскрипция на скан – меродавен е оригиналът. " + typo(d.get("iztochnik", "")) + ".")
        lines.append("> Знаци: `[?]` – несигурно разчетена дума; `[нечетливо]`; `[ръкописно: …]`, `[щемпел: …]`, "
                     "`[подпис]`, `[печат]` – ръкописни вписвания, щемпели, подписи и печати. Грешките на оригинала са "
                     "запазени.")
    if tier == "C" and str(d.get("vid", "")).lower() not in ("наредба", "закон", "правилник"):
        lines.append("> Вътрешен документ – не е обнародван в ДВ; при цитиране се казва, че актуалността му не е "
                     "проверена извън МВР.")
    if d.get("nepalen"):
        lines.append(NEPALEN + typo(d["nepalen"]))
    return lines


# ── commands ────────────────────────────────────────────────────────────────

def cmd_podgotvi(a):
    try:
        d = json.load(open(a.data, encoding="utf-8"))
    except (OSError, ValueError) as e:
        fail(f"{a.data}: {e}")
    missing = [k for k in ("izdatel", "vid", "data", "zaglavie", "iztochnik", "chasti") if not d.get(k)]
    if missing:
        fail("липсват полета: " + ", ".join(missing))
    tier_key = str(d.get("tier", "c")).lower()
    if tier_key not in TIERS:
        fail("tier е a или c")
    tier, folder, _ = TIERS[tier_key]
    in_force = d.get("in_force", "непроверен")
    if in_force not in IN_FORCE:
        fail(f"in_force е едно от: {', '.join(sorted(IN_FORCE))}")
    date = parse_date(d["data"])
    base = os.path.dirname(os.path.abspath(a.data))
    texts = []
    for p in d["chasti"]:
        path = p if os.path.isabs(p) else os.path.join(base, p)
        try:
            texts.append(open(path, encoding="utf-8").read())
        except OSError as e:
            fail(f"{p}: {e}")
    body = join_parts(texts)
    info = articles_of(body)

    issuer = next((v for k, v in ISSUERS.items() if d["izdatel"].lower().startswith(k)), slug(d["izdatel"], 2) or "UNKNOWN")
    vid = d["vid"].lower()
    kind = next((v for k, v in TYPES.items() if vid.startswith(k)), slug(d["vid"], 1) or "Document")
    nomer = typo(d.get("nomer", ""))
    nomer_lat = translit(nomer).replace(" ", "").replace("№", "")
    tema = d.get("tema_lat") or slug(d["zaglavie"])
    name = "_".join(x for x in (issuer, kind, re.sub(r"[^A-Za-z0-9-]", "", nomer_lat), tema, f"{date:%Y}") if x) + ".md"

    title = f"{d['vid'][:1].upper()}{d['vid'][1:]}" + (f" № {nomer}" if nomer else "") + \
            f"/{date:%d.%m.%Y} г. на {d['izdatel']} – {typo(d['zaglavie'])}"
    kws = list(dict.fromkeys(k for k in d.get("keywords", []) + ([nomer] if nomer else []) if k))
    fm = ["---",
          f"title: {yaml_str(title[:300])}",
          f"tier: {tier}",
          f"issuer: {yaml_str(d['izdatel'])}",
          f"act_type: {yaml_str(d['vid'])}",
          f"act_number: {yaml_str(nomer)}",
          f"act_id: {yaml_str(d.get('act_id') or nomer_lat or tema)}",
          f"edition_date: '{date:%Y-%m-%d}'",
          f"in_force: {in_force}"]
    if d.get("in_force_note"):
        fm.append(f"in_force_note: {yaml_str(typo(d['in_force_note']))}")
    if tier == "A":
        fm.append(f"in_force_source: {yaml_str(d.get('in_force_source') or 'не е проверен – ' + datetime.date.today().strftime('%d.%m.%Y'))}")
    fm += [f"text_source: {yaml_str(typo(d['iztochnik']) + ' – въведен ' + datetime.date.today().strftime('%d.%m.%Y') + ' г.')}",
           f"subject: {yaml_str(typo(d.get('subject') or d['zaglavie']))}",
           f"keywords: {json.dumps(kws, ensure_ascii=False)}",
           f"articles: {yaml_str(articles_field(info))}"]
    if info["lipsvat"]:
        fm.append(f"articles_missing: {yaml_str(', '.join(map(str, info['lipsvat'])))}")
    if d.get("source_file"):
        fm.append(f"source_file: {yaml_str(d['source_file'])}")
    fm.append("---")
    text = "\n".join(fm) + "\n\n" + "\n".join(note(d, tier)) + "\n\n" + body
    os.makedirs(a.out, exist_ok=True)
    path = os.path.join(a.out, name)
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(text)
    res = check(text, name)
    out({"ok": True, "file": path, "name": name, "path": f"{folder}/{name}", "chlenove": res["chlenove"],
         "greshki": res["greshki"], "preduprezhdeniya": res["preduprezhdeniya"], "nesigurni": res["nesigurni"]})
    return 0


def check(text, name):
    fm, body = split(text)
    err, warn = [], []
    tier = str(fm.get("tier", ""))
    if tier not in ("A", "C"):
        err.append("tier е A или C")
    for k in ("title", "issuer", "act_type", "in_force", "text_source", "keywords"):
        if fm.get(k) in (None, ""):
            err.append(f"липсва {k}")
    if tier == "A":
        for k in ("act_id", "subject", "articles", "in_force_source"):
            if not fm.get(k):
                err.append(f"липсва {k} (задължително за tier A)")
        if not fm.get("keywords"):
            err.append("keywords е празно (задължително за tier A)")
    if fm.get("in_force") and fm["in_force"] not in IN_FORCE:
        err.append(f"in_force „{fm['in_force']}“ не е позволена стойност")
    if len(str(fm.get("title", ""))) > 300:
        err.append("title е над 300 знака")
    if not re.fullmatch(r"[A-Za-z0-9-]+(_[A-Za-z0-9-]+)+\.md", name):
        err.append(f"името „{name}“ – само латиница, цифри, „-“ и „_“")
    if len(re.findall(r"\w+", body)) < 30:
        err.append("тялото е под 30 думи – базата не държи файл без текст")
    info = articles_of(body)
    if info["povtoreni"]:
        err.append("повторени членове: " + ", ".join(info["povtoreni"]))
    if info["razbarkani"]:
        err.append("членовете не са поред: " + ", ".join(info["razbarkani"]))
    if info["lipsvat"]:
        warn.append("липсват членове: " + ", ".join(map(str, info["lipsvat"])) +
                    " – провери страниците; ако ги няма в оригинала, остават (articles_missing)")
    if info["broi"] and fm.get("articles") and str(fm["articles"]) != articles_field(info):
        warn.append(f"articles „{fm['articles']}“ не съвпада с намерените „{articles_field(info)}“")
    loose = LOOSE_ART.findall(body)
    if loose:
        warn.append(f"{len(loose)} реда започват с „Чл. N“ без заглавие „## Чл. N“ – напр. „{loose[0]}“")
    unsure = len(UNSURE.findall(re.sub(r"^>.*$", "", body, flags=re.M)))   # the legend in the note is not a mark
    if unsure:
        warn.append(f"{unsure} несигурни места ([?], [нечетливо]) – кажи ги на потребителя")
    return {"greshki": err, "preduprezhdeniya": warn, "chlenove": info, "nesigurni": unsure}


def load(path):
    try:
        return open(path, encoding="utf-8").read()
    except OSError as e:
        fail(f"{path}: {e}")


def base_name(path):
    n = os.path.basename(path)
    return re.sub(r"^tier-[a-z-]+_", "", n)   # regs.py get saves as regs/tier-c_ИМЕ.md


def cmd_proveri(a):
    res = check(load(a.file), base_name(a.file))
    out({"ok": not res["greshki"], **res})
    return 0 if not res["greshki"] else 1


def number_of(fm):
    n = str(fm.get("act_number") or "")
    return re.sub(r"[^a-z0-9]", "", translit(n).lower())


def cmd_kandidati(a):
    fm, body = split(load(a.file))
    num = number_of(fm)
    title_words = {w[:6] for w in re.findall(r"[a-z]{4,}", translit(str(fm.get("title", ""))).lower())}
    if a.listing:
        try:
            data = json.load(open(a.listing, encoding="utf-8"))
        except (OSError, ValueError) as e:
            fail(f"{a.listing}: {e}")
        files = data.get("files", data) if isinstance(data, dict) else data
    else:
        import api_config
        if not api_config.has_key():
            fail("няма личен ключ – с конектора запиши отговора на regs_list във файл и го подай с --listing", "NO_KEY")
        try:
            files = api_config.post("regs_url", {"action": "list"}).get("files", [])
        except SystemExit:
            raise
        except Exception as e:  # noqa: BLE001
            fail(f"{type(e).__name__}: {e}"[:300], "N8N_UNAVAILABLE")
    rows = []
    for f in files:
        path = f.get("path") or f.get("name") or ""
        if not path.startswith("tier-") or not path.endswith(".md"):
            continue
        name = os.path.basename(path).lower()
        flat = re.sub(r"[^a-z0-9]", "", name)
        num_hit = len(num) >= 4 and num in flat
        nw = {w[:6] for w in re.findall(r"[a-z]{4,}", name)}
        overlap = len(title_words & nw) / max(1, min(len(title_words), len(nw)))
        if num_hit or overlap >= a.prag:
            rows.append({"path": path, "id": f.get("id"), "sashtiyat_nomer": num_hit, "obshti_dumi": round(overlap, 2)})
    rows.sort(key=lambda r: (not r["sashtiyat_nomer"], -r["obshti_dumi"]))
    out({"ok": True, "kandidati": rows[:a.broi],
         "sledva": "няма кандидати → zapis; иначе свали всеки (regs.py get ПЪТ) и го подай на sravni"})
    return 0


def plain(body):
    return re.sub(r"\s+", " ", re.sub(r"^>.*$", "", body, flags=re.M)).strip().lower()


def cmd_sravni(a):
    new_fm, new_body = split(load(a.novo))
    old_fm, old_body = split(load(a.staro))
    ni, oi = articles_of(new_body), articles_of(old_body)
    same_num = number_of(new_fm) and number_of(new_fm) == number_of(old_fm)
    nd, od = str(new_fm.get("edition_date", "")), str(old_fm.get("edition_date", ""))
    new_set = {int(n) for n, _ in ART.findall(new_body)}
    old_set = {int(n) for n, _ in ART.findall(old_body)}
    sim = difflib.SequenceMatcher(None, plain(new_body)[:20000], plain(old_body)[:20000]).ratio()
    if same_num and nd and od and nd[:10] != od[:10]:
        r, why = "nova_redaktsiya", f"същият номер, друга дата ({od} → {nd})"
    elif new_set and old_set and min(new_set) > max(old_set) - 1 and min(new_set) <= max(old_set) + 1:
        r, why = "prodalzhenie", f"записаният свършва с чл. {max(old_set)}, новото започва от чл. {min(new_set)}"
    elif new_set and old_set and new_set <= old_set:
        r, why = ("dublikat" if new_set == old_set else "chast"), f"членовете на новото ({ni['ot']}–{ni['do']}) вече са в записания ({oi['ot']}–{oi['do']}); текстът съвпада на {sim:.0%}"
    elif sim >= 0.85:
        r, why = "dublikat", f"текстът съвпада на {sim:.0%}"
    elif same_num and new_set - old_set:
        r, why = "prodalzhenie", f"същият номер; новите членове: {', '.join(map(str, sorted(new_set - old_set)[:10]))}"
    else:
        r, why = "razlichen", f"текстът съвпада на {sim:.0%}"
    out({"ok": True, "reshenie": r, "zashto": why, "novo": {"ot": ni["ot"], "do": ni["do"]},
         "zapisano": {"ot": oi["ot"], "do": oi["do"]},
         "sledva": {"dublikat": "вече е в базата – не записвай, кажи кой файл е",
                    "chast": "нищо ново – не записвай",
                    "prodalzhenie": "dopalni ЗАПИСАНИЯ НОВОТО -o akt, после proveri и zapis",
                    "nova_redaktsiya": "покажи двете дати и питай: нов файл с _edГГГГ-ММ-ДД или замяна",
                    "razlichen": "друг документ – zapis"}[r]})
    return 0


def cmd_dopalni(a):
    old = load(a.staro)
    m = re.match(r"^---\n.*?\n---\n?", old, re.S)
    if not m:
        fail("записаният файл няма front matter")
    head, body = old[:m.end()], old[m.end():]
    part = load(a.chast)
    _, part_body = split(part)            # a part may come with or without front matter
    part_body = re.sub(r"^(>.*\n)+\n?", "", part_body.lstrip("\n"))
    notes = re.match(r"^\s*((?:>.*\n)+)", body)
    note_block = notes.group(1) if notes else ""
    rest = body[notes.end():] if notes else body
    if a.palen or a.nepalen:   # the old "pages end at …" note goes; --nepalen writes the new one
        note_block = "".join(l for l in note_block.splitlines(True) if not OLD_PAGES_NOTE.match(l))
    if a.nepalen:
        note_block += NEPALEN + typo(a.nepalen) + "\n"
    joined = join_parts([rest, part_body])
    info = articles_of(joined)
    fields = {"articles": articles_field(info)}
    text = head + ("\n" + note_block if note_block else "") + "\n" + joined
    from ukazaniya import set_fields
    text = set_fields(text, fields)
    if not info["lipsvat"] and re.search(r"^articles_missing:", text, re.M):
        text = re.sub(r"^articles_missing:.*\n", "", text, count=1, flags=re.M)
    elif info["lipsvat"]:
        text = set_fields(text, {"articles_missing": ", ".join(map(str, info["lipsvat"]))})
    os.makedirs(a.out, exist_ok=True)
    path = os.path.join(a.out, base_name(a.staro))
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(text)
    res = check(text, os.path.basename(path))
    out({"ok": True, "file": path, "chlenove": res["chlenove"], "greshki": res["greshki"],
         "preduprezhdeniya": res["preduprezhdeniya"],
         "sledva": "zapis ФАЙЛ – същото име, файлът в базата се заменя на място"})
    return 0


def cmd_zapis(a):
    import api_config
    text = load(a.file)
    name = base_name(a.file)
    res = check(text, name)
    if res["greshki"]:
        fail("файлът има грешки – " + "; ".join(res["greshki"]))
    fm, _ = split(text)
    tier = str(fm.get("tier"))
    key = "a" if tier == "A" else "c"
    _, folder, kind = TIERS[key]
    try:
        r = api_config.post("samples_url", {"action": "put", "kind": kind, "name": name, "text": text,
                                            "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest()}, timeout=180)
    except SystemExit:
        raise
    except Exception as e:  # noqa: BLE001
        msg = str(e)
        if "403" in msg or "FORBIDDEN" in msg:
            fail("само администраторът записва в нормативната база", "FORBIDDEN")
        fail(f"{type(e).__name__}: {e}"[:300], "N8N_UNAVAILABLE")
    after = ("index.json и броевете в индекса се обновяват при следващия kb_lint.py --catalog; дотогава файлът се "
             f"намира с regs.py list --folder {folder} и regs.py get")
    if tier == "A":
        after += ". Акт в tier-a трябва да е описан и в индекса (_INDEX_…) – направи го от компютъра с tools/admin.py"
    out({"ok": True, "path": f"{folder}/{name}", "link": (r or {}).get("link"),
         "preduprezhdeniya": res["preduprezhdeniya"], "belezhka": after})
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="Внос на цял документ в нормативната база")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("podgotvi"); p.add_argument("data"); p.add_argument("-o", "--out", default="akt")
    p.set_defaults(fn=cmd_podgotvi)
    p = sub.add_parser("proveri"); p.add_argument("file"); p.set_defaults(fn=cmd_proveri)
    p = sub.add_parser("kandidati"); p.add_argument("file"); p.add_argument("--listing")
    p.add_argument("--prag", type=float, default=0.6); p.add_argument("--broi", type=int, default=8)
    p.set_defaults(fn=cmd_kandidati)
    p = sub.add_parser("sravni"); p.add_argument("novo"); p.add_argument("staro"); p.set_defaults(fn=cmd_sravni)
    p = sub.add_parser("dopalni"); p.add_argument("staro"); p.add_argument("chast")
    p.add_argument("-o", "--out", default="akt"); p.add_argument("--palen", action="store_true",
                                                                 help="документът вече е пълен – махни бележката за липсващите страници")
    p.add_argument("--nepalen", help="новата бележка докъде стигат наличните страници (заменя старата)")
    p.set_defaults(fn=cmd_dopalni)
    p = sub.add_parser("zapis"); p.add_argument("file"); p.set_defaults(fn=cmd_zapis)
    a = ap.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
