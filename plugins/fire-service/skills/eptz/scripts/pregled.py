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

# Arson wording: checked outside the „Поставени въпроси“ section, where the questions are quoted verbatim from the постановление.
ARSON = (r"\bпалеж|\bумис[ъл]|\bумишлен", "вместо „палеж“, „умисъл“ и „умишлени действия“ се пише „злонамерено внесен външен огнеизточник“")

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
# a version heading is bold („**А). Късо съединение.**“); the plain list of the versions before them is not
VERSION = re.compile(r"^\s*\*\*([А-Я])\)\.?\s*(.+?)\*\*\s*$", re.M)
# the standard versions – by topic, since the letters follow the order from the least to the most probable
STANDARD = [("злонамерено внесен външен огнеизточник", r"злонамерен|внесен"), ("късо съединение", r"късо съединение|електр"),
            ("природни сили", r"природни|мълния"), ("самозапалване", r"самозапал"), ("небрежност", r"небрежност")]
ORDINAL = ["първи", "втори", "трети", "четвърти", "пети", "шести", "седми", "осми", "девети", "десети",
           "единадесети", "дванадесети"]
RESEARCH = r"(?:Изследване на|Отговор на) въпрос №\s*"
SECTION_VI_MAX = 3800  # ≈ one page – the general conclusions are short answers, not the research again
NO_TIMES = re.compile(r"час(ът|овете)[а-я ,]{0,40}(не са|не е|няма)[а-я ]{0,15}(отразен|посочен|данни)|няма (точни )?час", re.I)
VERDICT = re.compile(r"отпада|не може да бъде (изключена|отхвърлена)|подкрепя|приема се|потвържда|най-вероятн|малко вероятн|установена|има вероятност", re.I)


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
    sec4 = section(text, r"^##\s*IV\.\s*Общи изводи", r"^##\s")
    research = text if sec4 is None else text[:text.find(sec4)]
    answers = [int(n) for n in re.findall(rf"^###\s*{RESEARCH}(\d+)", research, re.M)]
    if sec2 is None:
        greshki.append("няма раздел „II. Поставени въпроси пред експерта.“")
    if not answers:
        greshki.append("няма нито едно „Изследване на въпрос № N“")
    elif answers != list(range(1, len(answers) + 1)):
        greshki.append(f"отговорите не са по ред 1…N: {answers}")
    if listed and answers and len(listed) != len(answers):
        greshki.append(f"въпросите в раздел II са {len(listed)}, а изследванията – {len(answers)}")
    if sec4 is None:
        greshki.append("няма раздел „## IV. Общи изводи от проведеното изследване на поставените въпроси.“ – "
                       "всеки въпрос се повтаря дословно с кратък отговор")
    else:
        heads = re.findall(r"^###\s*Отговор на ([а-я]+) въпрос\s*:?\s*(.*)$", sec4, re.M)
        got = [h[0] for h in heads]
        if got != ORDINAL[:len(got)]:
            greshki.append("в общите изводи отговорите трябва да са „Отговор на първи въпрос: …“, „… втори …“ – по ред: "
                           + ", ".join(got))
        if listed and len(heads) != len(listed):
            greshki.append(f"въпросите в раздел II са {len(listed)}, а отговорите в общите изводи – {len(heads)}")
        for i, ((_, q), l) in enumerate(zip(heads, listed), 1):
            if norm(q) != norm(l):
                za_proverka.append(f"в общите изводи въпрос № {i} не е повторен дословно: „{q[:80]}“")
        n4 = len(re.sub(r"\s+", " ", sec4).strip())
        if n4 > SECTION_VI_MAX:
            za_proverka.append(f"общите изводи са {n4} знака – около страница е достатъчно (~{SECTION_VI_MAX}); "
                               "там са кратките отговори, не изследването отново")
    if vaprosi:
        if len(vaprosi) != len(listed):
            greshki.append(f"в постановлението въпросите са {len(vaprosi)}, в раздел II – {len(listed)}")
        for i, (q, l) in enumerate(zip(vaprosi, listed), 1):
            if norm(q) != norm(l):
                greshki.append(f"въпрос № {i} не е дословно като в постановлението: „{l[:80]}“")

    # ── versions in answer 1 ──
    # the versions stand in the research of the question about the cause – usually № 1, but not always
    parts = [(int(mm.group(1)), section(research, rf"^###\s*{RESEARCH}{mm.group(1)}\s*:?", r"^###\s|^---\s*$|^##\s"))
             for mm in re.finditer(rf"^###\s*{RESEARCH}(\d+)", research, re.M)]
    with_versions = [(n, p) for n, p in parts if p and VERSION.search(p)]
    q_cause, ans1 = with_versions[0] if with_versions else (1, dict(parts).get(1))
    if ans1 is not None:
        found = {}
        for m in VERSION.finditer(ans1):
            found[m.group(1)] = m.group(2).strip().rstrip(".")
        titles = " | ".join(found.values()).lower()
        missing = [name for name, rx in STANDARD if not re.search(rx, titles)]
        if missing:
            greshki.append(f"в изследването на въпрос № {q_cause} липсват стандартните версии: " + ", ".join(missing))
        letters = list(found)
        if letters and letters != [chr(ord("А") + i) for i in range(len(letters))]:
            za_proverka.append("буквите на версиите не са по ред А), Б), В)…: " + ", ".join(letters))
        blocks = re.split(r"^\s*\*\*[А-Я]\)\.?.*\*\*\s*$", ans1, flags=re.M)[1:]
        rejected = []
        for letter, body in zip(letters, blocks):
            body = re.split(r"Обобщен отговор|^\s*\*\*Извод[^\n]*\*\*\s*$", body, flags=re.M)[0]
            if not VERDICT.search(body):
                za_proverka.append(f"версия {letter}) „{found[letter]}“ няма ясен извод (отпада / не може да бъде изключена / подкрепя се)")
            if re.search(r"Версията отпада|версията отпада", body):
                rejected.append(letter)
        # the order – from the least to the most probable: the rejected versions come first
        kept = [l for l in letters if l not in rejected]
        if kept and rejected and max(letters.index(l) for l in rejected) > min(letters.index(l) for l in kept):
            za_proverka.append("версиите трябва да са от най-малко към най-вероятната – отхвърлената версия "
                               + ", ".join(f"{l})" for l in rejected if letters.index(l) > min(letters.index(k) for k in kept))
                               + " е след версия, която не отпада")
        summary = section(ans1, r"^\s*\*\*(?:Извод|Обобщен отговор)[^\n]*\*\*\s*$", r"^---\s*$|^###\s")
        if summary is None:
            greshki.append(f"изследването на въпрос № {q_cause} не завършва с „**Извод:**“")
        else:
            s = norm(summary)
            for letter in rejected:
                key = " ".join(norm(found[letter]).split("–")[0].split()[:2])
                if key and key in s:
                    za_proverka.append(f"изводът споменава „{key}“, а версия {letter}) е отхвърлена – провери дали не си противоречат")
            if len(rejected) == len(letters) and letters:
                za_proverka.append("всички версии отпадат, а изводът трябва да назове причина или да каже, че тя не може да се установи")

    # ── the times of localisation and liquidation are asked for, not written off as missing ──
    m = NO_TIMES.search(text)
    if m:
        za_proverka.append(f"„{m.group(0)[:60]}“ – попитай експерта за часовете (локализиране, ликвидиране) от "
                           "телефонограмата, преди да пишеш, че ги няма")

    # ── section I length ──
    sec1 = section(text, r"^##\s*I\.", r"^##\s")
    if sec1 is not None:
        n = len(re.sub(r"\s+", " ", sec1).strip())
        if n > SECTION_I_MAX:
            greshki.append(f"раздел I е {n} знака – най-много половин страница (~{SECTION_I_MAX})")

    # ── forbidden wording – outside the questions, which are quoted verbatim (in section II and in the
    #    headings of section IV) ──
    bez_q = re.sub(r"(?ms)^[#*\[\s]*[IVX]+\.\s*Поставени въпроси.*?(?=^[#*\[\s]*[IVX]+\.\s)", "", text)
    bez_q = re.sub(r"(?m)^###\s*Отговор на [а-я]+ въпрос.*$", "", bez_q)
    for rx, msg in FORBIDDEN:
        m = re.search(rx, bez_q, re.I)
        if m:
            greshki.append(f"{msg}: „{m.group(0)[:60]}“")
    bez_vaprosi = re.sub(r"(?ms)^[#*\[\s]*[IVX]+\.\s*Поставени въпроси.*?(?=^[#*\[\s]*[IVX]+\.\s)", "", text)
    # the general conclusions repeat each question verbatim in its heading
    bez_vaprosi = re.sub(r"(?m)^###\s*Отговор на [а-я]+ въпрос.*$", "", bez_vaprosi)
    m = re.search(ARSON[0], bez_vaprosi, re.I)
    if m:
        greshki.append(f"{ARSON[1]}: „{m.group(0)[:60]}“")

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
    result = check(content, meta, vaprosi, materiali)
    # the model reliably acts on script output; the semantic review was skipped in half the eval runs
    # when only SKILL.md asked for it
    result["sledva"] = (
        "Това е само механичният преглед. СЛЕДВА смисловият – задължителен, не се пропуска: подагент "
        "(Agent/Task) с подсказката от references/pregled.md и само пътищата до report.md, meta.json, "
        "въпросите и материалите; без такъв инструмент – отделна стъпка само върху файловете. Поправи "
        "веднага: извод, написан като факт; факт или подробност без източник в материалите (напр. "
        "„затворен капак“, „сухи греди“); думи, приписани на човек, който не ги е казал; версия, "
        "отхвърлена само с „няма данни“.")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
