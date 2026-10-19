#!/usr/bin/env python3
"""Tests for pregled.py – the mechanical part of the independent review. Run from the skill folder:
    python3 tests/test_pregled.py
The reports are invented, not real cases.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "scripts"))
from pregled import check  # noqa: E402

failures = []


def ok(cond, msg):
    print(("  ok  " if cond else "  FAIL ") + msg)
    if not cond:
        failures.append(msg)


META = {"zm_no": "123/2026", "dp_no": "1234/2026"}
QUESTIONS = ["Каква е причината за пожара?", "Къде се е намирало огнището?"]

GOOD = """# ЕКСПЕРТНО ПОЖАРО-ТЕХНИЧЕСКО ЗАКЛЮЧЕНИЕ

## I. Обстоятелства по делото.

На 01.10.2026 г. в 14:20 ч. в ОЦ е получен сигнал за пожар в стопанска постройка в тестово село.

## II. Поставени въпроси пред експерта.

1. Каква е причината за пожара?
2. Къде се е намирало огнището?

## III. Пожаро-техническо изследване.

### Отговор на въпрос № 1:

**А). Злонамерено внесен външен източник.**

Няма множество изолирани огнища. Версията отпада.

**Б). Късо съединение.**

Постройката няма ел. инсталация. Версията отпада.

**В). Действие на природни сили.**

Няма гръмотевична дейност. Версията отпада.

**Г). Самозапалване.**

Няма порест материал с натрупване на топлина. Версията отпада.

**Д). Небрежност – незагасена цигара.**

Тази версия се подкрепя от следните обстоятелства: присъствие на пушач малко преди пожара.

**Обобщен отговор на въпрос № 1:**

Най-вероятната причина е небрежност с незагасена цигара; огнището е в северния ъгъл.

---

### Отговор на въпрос № 2:

Огнището е в северния ъгъл на постройката (виж отговора на въпрос № 1).
"""
MATERIALS = "Телефонограма: сигнал 01.10.2026 г., 14:20 ч., стопанска постройка."

print("a clean report")
r = check(GOOD, META, QUESTIONS, MATERIALS)
ok(r["ok"] and not r["za_proverka"], f"no findings: {r['greshki'] + r['za_proverka']}")

print("rules")
bad = GOOD.replace("Каква е причината за пожара?\n2.", "Каква е причината?\n2.")
r = check(bad, META, QUESTIONS)
ok(any("дословно" in g for g in r["greshki"]), "a question not verbatim")
r = check(GOOD.replace("### Отговор на въпрос № 2:", "### Отговор на въпрос № 3:"), META)
ok(any("по ред" in g for g in r["greshki"]), "answers out of order")
r = check(GOOD.replace("**Г). Самозапалване.**\n\nНяма порест материал с натрупване на топлина. Версията отпада.\n\n", ""), META)
ok(any("Г)" in g for g in r["greshki"]), "a missing standard version")
r = check(GOOD.replace("Постройката няма ел. инсталация. Версията отпада.", "Постройката няма ел. инсталация."), META)
ok(any("Б)" in z for z in r["za_proverka"]), "a version without a verdict")
r = check(GOOD.replace("Най-вероятната причина е небрежност", "Причината е късо съединение, а не небрежност"), META)
ok(any("късо съединение" in z for z in r["za_proverka"]), "the summary names a rejected version")
r = check(GOOD + "\nОглед на местопроизшествието от вещото лице не е извършен.\n", META)
ok(any("оглед" in g for g in r["greshki"]), "„оглед … не е извършен“")
# the same thing with the words in the other order – a real eval run wrote exactly this
r = check(GOOD + "\nТъй като не е извършен и описан оглед, версията не може да бъде изключена.\n", META)
ok(any("оглед" in g for g in r["greshki"]), "„не е извършен … оглед“")
r = check(GOOD + "\nВ материалите по делото няма представен протокол за оглед.\n", META)
ok(r["ok"], "the allowed wording about a missing протокол за оглед is not flagged")
r = check(GOOD + "\nПожарът е резултат от палеж.\n", META)
ok(any("злонамерено внесен" in g for g in r["greshki"]), "„палеж“ instead of „злонамерено внесен външен източник“")
r = check(GOOD + "\nНе може да се изключи умисъл.\n", META)
ok(any("злонамерено внесен" in g for g in r["greshki"]), "„умисъл“ instead of „злонамерено внесен външен източник“")
r = check(GOOD + "\nДеянието е по чл. 330 от НК.\n", META)
ok(any("НК" in g for g in r["greshki"]), "a legal qualification")
r = check(GOOD + "\nПо данни на Иван Георгиев Дъбов.\n", META)
ok(any("три имена" in g for g in r["greshki"]), "three names")
r = check(GOOD + "\nТелефон " + "08" + "88 123 456.\n", META)   # split so the public check does not flag it
ok(any("телефон" in g for g in r["greshki"]), "a phone number")
r = check(GOOD + "\nПо ЗМ № 123/2025.\n", META)
ok(any("ЗМ № 123/2025" in g for g in r["greshki"]), "a ЗМ number different from meta")
r = check(GOOD.replace("14:20", "14:50"), META, None, MATERIALS)
ok(any("14:50" in z for z in r["za_proverka"]), "a time not in the materials")
r = check(GOOD.replace("Обстоятелства по делото.\n\n", "Обстоятелства по делото.\n\n" + "Дълъг текст. " * 200), META)
ok(any("раздел I" in g for g in r["greshki"]), "section I too long")

if failures:
    print(f"\n{len(failures)} FAILED")
    sys.exit(1)
print("\nall passed")
