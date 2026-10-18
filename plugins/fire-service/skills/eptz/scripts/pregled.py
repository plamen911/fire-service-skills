#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pregled.py — механичната част от независимия преглед на готовото ЕПТЗ (references/pregled.md).

Проверява текста на заключението (report.md) срещу meta.json, въпросите от постановлението и
материалите по делото. Не поправя нищо – връща находки. Смисловия преглед (противоречия между
фактите и изводите, версии без основание) прави отделен преглед по references/pregled.md.

    python3 scripts/pregled.py --content report.md --meta meta.json \
        [--vaprosi vaprosi.json] [--materiali case_ingest.md …]

--vaprosi   JSON списък с въпросите от постановлението – сверява се дали раздел II ги дава дословно и дали всеки има отговор.
--materiali текстът на материалите (case_ingest.md от ingest_case_folder.py, или файл с
            разчетеното) – датите и часовете в заключението трябва да ги има там или в meta.json.

Изход – JSON: {"ok", "greshki": [...], "za_proverka": [...], "statistika": {...}}.
„greshki“ са нарушения на правилата на скила – поправи ги и изгради документа наново.
„za_proverka“ са места, които експертът трябва да погледне; не са непременно грешни.
"""
import argparse
import json
import re
import sys
import unicodedata

SECTION_I_MAX = 1900  # characters ≈ half a page in the template (Times New Roman 12, 1.15)

FORBIDDEN = [
    (r"оглед[а-я ]{0,40}не е извършен|не е (бил )?извършен[а-я ]{0,40}оглед", "„оглед … не е извършен“ звучи като пропуск на вещото лице – пиши „В материалите по делото няма представен протокол за оглед …“"),
    (r"поради липсата? на оглед", "„поради липсата на оглед“ – пиши „Поради липсата на протокол за оглед в материалите …“"),
    (r"правна(та)? квалификация", "абзац за правната квалификация не се пише"),
    (r"извън (моята )?компетентност", "абзац, че нещо е извън компетентността на експерта, не се пише"),
    (r"\bчл\.\s*\d+[а-я]?\s*(,\s*ал\.\s*\d+\s*)?(от\s*)?НК\b|\bНаказателния кодекс", "правни квалификации по НК не се правят"),
    (r"\bзаподозр", "заподозрени не се споменават – анализират се физическите факти"),
    (r"\bизвършител", "извършители не се споменават"),
    (r"\bпризна(ва|л|ние|ния)", "признания и показания на заподозрени не се преразказват"),
    (r"\bвиновн", "вина не се определя в ЕПТЗ"),
    (r"ЧЕРНОВА", "в документа няма надпис „ЧЕРНОВА“"),
    (r"изкуствен интелект|\bAI\b|Claude", "в документа няма бележки за изкуствен интелект"),
    (r"\[Източник\s*:", "маркерите „[Източник: …]“ са само за чата"),
    (r"\{[^}\n]{3,}\}", "останал плейсхолдър от шаблона"),
]
NAME3 = re.compile(r"\b([А-Я][а-я]+) ([А-Я][а-я]+(?:ов|ев|ин|ски|ова|ева|ина|ска)) ([А-Я][а-я]+(?:ов|ев|ин|ски|ова|ева|ина|ска))\b")
EGN = re.compile(r"(?<!\d)\d{10}(?!\d)")
PHONE = re.compile(r"(?<![\d/])(?:\+359|0)\s?8[7-9]\d[\s-]?\d{3}[\s-]?\d{3}(?!\d)")
DATE = re.compile(r"(?<!\d)(\d{1,2})\.(\d{1,2})\.(\d{4})(?!\d)")
TIME = re.compile(r"(?<![\d.,])([01]?\d|2[0-3])[:.,]([0-5]\d)\s*(?:ч\b|часа)")
VERSION = re.compile(r"^\s*(?:\*\*)?([А-Я])\)\.?\s*(.+?)(?:\*\*)?\s*$", re.M)
STANDARD = ["А", "Б", "В", "Г", "Д"]
VERDICT = re.compile(r"отпада|не може да бъде (изключена|отхвърлена)|подкрепя|приема се|потвържда|най-вероятн|установена", re.I)


def norm(text):
    t = unicodedata.normalize("NFC", text or "").lower()
    t = re.sub(r"[„“”\"'`«»*_]", "", t)
    t = re.sub(r"\s+", " ", t)
    return t.strip(" .;:")


def section(text, start_rx, end_rx):
    m = re.search(start_rx, text, re.M)
    if not m:
        return None
    rest = text[m.end():]
    e = re.search(end_rx, rest, re.M)
    return rest[:e.start()] if e else rest


def plain(md):
    return re.sub(r"\[\[[^\]]*\]\]", "", re.sub(r"<!--.*?-->", "", md, flags=re.S))


def dates_of(text):
    return {f"{int(d):02d}.{int(m):02d}.{y}" for d, m, y in DATE.findall(text)}


def times_of(text):
    return {f"{int(h):02d}:{mi}" for h, mi in TIME.findall(text)} | \
           {f"{int(h):02d}:{mi}" for h, mi in re.findall(r"(?<![\d.,])([01]?\d|2[0-3]):([0-5]\d)(?!\d)", text)}


def check(content, meta, vaprosi=None, materiali=""):
    greshki, za_proverka = [], []
    text = plain(content)

    # ── structure: questions and answers ──
    sec2 = section(text, r"^##\s*II\.", r"^##\s")
    listed = [q.strip() for q in re.findall(r"^\s*\d+[.)]\s+(.+)$", sec2 or "", re.M)]
    answers = [int(n) for n in re.findall(r"^###\s*Отговор на въпрос №\s*(\d+)", text, re.M)]
    if sec2 is None:
        greshki.append("няма раздел „II. Поставени въпроси пред експерта.“")
    if not answers:
        greshki.append("няма нито един „Отговор на въпрос № N“")
    elif answers != list(range(1, len(answers) + 1)):
        greshki.append(f"отговорите не са по ред 1…N: {answers}")
    if listed and answers and len(listed) != len(answers):
        greshki.append(f"въпросите в раздел II са {len(listed)}, а отговорите – {len(answers)}")
    if vaprosi:
        if len(vaprosi) != len(listed):
            greshki.append(f"в постановлението въпросите са {len(vaprosi)}, в раздел II – {len(listed)}")
        for i, (q, l) in enumerate(zip(vaprosi, listed), 1):
            if norm(q) != norm(l):
                greshki.append(f"въпрос № {i} не е дословно като в постановлението: „{l[:80]}“")

    # ── versions in answer 1 ──
    ans1 = section(text, r"^###\s*Отговор на въпрос №\s*1\s*:?", r"^###\s|^---\s*$")
    if ans1 is not None:
        found = {}
        for m in VERSION.finditer(ans1):
            found[m.group(1)] = m.group(2).strip().rstrip(".")
        missing = [l for l in STANDARD if l not in found]
        if missing:
            greshki.append("в отговора на въпрос № 1 липсват стандартните версии " + ", ".join(f"{l})" for l in missing)
                           + " (А – умишлени, Б – късо съединение, В – природни сили, Г – самозапалване, Д – небрежност)")
        letters = list(found)
        blocks = re.split(r"^\s*(?:\*\*)?[А-Я]\)\.?.*$", ans1, flags=re.M)[1:]
        rejected = []
        for letter, body in zip(letters, blocks):
            body = body.split("Обобщен отговор")[0]
            if not VERDICT.search(body):
                za_proverka.append(f"версия {letter}) „{found[letter]}“ няма ясен извод (отпада / не може да бъде изключена / подкрепя се)")
            if re.search(r"Версията отпада", body):
                rejected.append(letter)
        summary = section(text, r"Обобщен отговор на въпрос №\s*1", r"^---\s*$|^###\s")
        if summary is None:
            greshki.append("няма „Обобщен отговор на въпрос № 1“")
        else:
            s = norm(summary)
            for letter in rejected:
                key = " ".join(norm(found[letter]).split("–")[0].split()[:2])
                if key and key in s:
                    za_proverka.append(f"обобщеният отговор споменава „{key}“, а версия {letter}) е отхвърлена – провери дали не си противоречат")
            if len(rejected) == len(letters) and letters:
                za_proverka.append("всички версии отпадат, а обобщеният отговор трябва да назове причина или да каже, че тя не може да се установи")

    # ── section I length ──
    sec1 = section(text, r"^##\s*I\.", r"^##\s")
    if sec1 is not None:
        n = len(re.sub(r"\s+", " ", sec1).strip())
        if n > SECTION_I_MAX:
            greshki.append(f"раздел I е {n} знака – най-много половин страница (~{SECTION_I_MAX})")

    # ── forbidden wording ──
    for rx, msg in FORBIDDEN:
        m = re.search(rx, text, re.I)
        if m:
            greshki.append(f"{msg}: „{m.group(0)[:60]}“")

    # ── personal data ──
    for m in NAME3.finditer(text):
        greshki.append(f"три имена – пиши само име и фамилия: „{m.group(0)}“")
    for m in EGN.finditer(text):
        greshki.append(f"10-цифрено число (ЕГН?) – не се пише: „{m.group(0)}“")
    for m in PHONE.finditer(text):
        greshki.append(f"телефонен номер – не се пише: „{m.group(0)}“")

    # ── numbers of the case agree with meta ──
    for label, key in (("ЗМ", "zm_no"), ("ДП", "dp_no")):
        want = (meta.get(key) or "").replace(" ", "")
        for got in re.findall(rf"{label}\s*№\s*([\d/]+)", text):
            if want and got.rstrip("/") != want:
                greshki.append(f"{label} № {got} в текста, а в meta.json е {meta.get(key)}")

    # ── dates and times must come from the materials ──
    if materiali:
        known = materiali + " " + json.dumps(meta, ensure_ascii=False)
        kd, kt = dates_of(known), times_of(known)
        for d in sorted(dates_of(text) - kd):
            za_proverka.append(f"датата {d} я няма в материалите – провери откъде е")
        for t in sorted(times_of(text) - kt):
            za_proverka.append(f"часът {t} го няма в материалите – провери откъде е")

    stat = {"vaprosi": len(listed), "otgovori": len(answers), "razdel_I_znaka": len(re.sub(r"\s+", " ", sec1 or "").strip())}
    return {"ok": not greshki, "greshki": greshki, "za_proverka": za_proverka, "statistika": stat}


def main(argv=None):
    ap = argparse.ArgumentParser(description="механичният преглед на ЕПТЗ")
    ap.add_argument("--content", required=True)
    ap.add_argument("--meta", required=True)
    ap.add_argument("--vaprosi")
    ap.add_argument("--materiali", nargs="*", default=[])
    a = ap.parse_args(argv)
    content = open(a.content, encoding="utf-8").read()
    meta = json.load(open(a.meta, encoding="utf-8"))
    vaprosi = json.load(open(a.vaprosi, encoding="utf-8")) if a.vaprosi else None
    if isinstance(vaprosi, dict):
        vaprosi = vaprosi.get("vaprosi")
    materiali = "\n".join(open(p, encoding="utf-8", errors="ignore").read() for p in a.materiali)
    print(json.dumps(check(content, meta, vaprosi, materiali), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
