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

### Изследване на въпрос № 1:

След запознаването с предоставените материали могат да бъдат изградени и разгледани следните версии:

- Действие на природни сили;
- Късо съединение;
- Самозапалване;
- Злонамерено внесен външен огнеизточник;
- Небрежност – незагасена цигара.

**А). Действие на природни сили.**

Няма гръмотевична дейност. Извод: Версията отпада.

**Б). Късо съединение.**

Постройката няма ел. инсталация. Извод: Версията отпада.

**В). Самозапалване.**

Няма порест материал с натрупване на топлина. Извод: Версията отпада.

**Г). Злонамерено внесен външен огнеизточник.**

Няма множество изолирани огнища. Извод: Версията отпада.

**Д). Небрежност – незагасена цигара.**

Тази версия се подкрепя от следните обстоятелства: присъствие на пушач малко преди пожара.

**Обобщен отговор на първи въпрос:**

Най-вероятната причина е небрежност с незагасена цигара; огнището е в северния ъгъл.

---

### Изследване на въпрос № 2:

Огнището е в северния ъгъл на постройката (виж изследването на въпрос № 1).

## IV. Общи изводи от проведеното изследване на поставените въпроси.

### Отговор на първи въпрос: Каква е причината за пожара?

Най-вероятната причина е небрежност с незагасена цигара.

### Отговор на втори въпрос: Къде се е намирало огнището?

В северния ъгъл на постройката.
"""
MATERIALS = "Телефонограма: сигнал 01.10.2026 г., 14:20 ч., стопанска постройка."

print("a clean report")
r = check(GOOD, META, QUESTIONS, MATERIALS)
ok(r["ok"] and not r["za_proverka"], f"no findings: {r['greshki'] + r['za_proverka']}")

print("rules")
moved = GOOD.replace("**А). Действие на природни сили.**\n\nНяма гръмотевична дейност. Извод: Версията отпада.\n\n", "")
moved = moved.replace("**Обобщен отговор на първи въпрос:**", "**Е). Действие на природни сили.**\n\nНяма гръмотевична дейност. Извод: Версията отпада.\n\n**Обобщен отговор на първи въпрос:**")
r = check(moved, META)
ok(any("най-малко към най-вероятната" in z for z in r["za_proverka"]), "a rejected version after the probable one")
i4 = GOOD.index("## IV.")
r = check(GOOD[:i4], META)
ok(any("Общи изводи" in g for g in r["greshki"]), "no section IV")
r = check(GOOD.replace("Отговор на втори въпрос", "Отговор на трети въпрос"), META)
ok(any("по ред" in g for g in r["greshki"]), "ordinals in section IV out of order")
r = check(GOOD.replace("**Обобщен отговор на първи въпрос:**", "**Заключение:**"), META)
ok(any("Обобщен отговор" in g for g in r["greshki"]), "research of question 1 without „Обобщен отговор“")

r = check(GOOD.replace("**Обобщен отговор на първи въпрос:**", "**Извод:**"), META)
ok(not r["greshki"] and any("Обобщен отговор" in z for z in r["za_proverka"]),
   "a second „Извод:“ after the versions is accepted but flagged")

r = check(GOOD.replace("следните версии:", "следните версии, подредени от най-малко вероятната към най-вероятната:"), META)
ok(any("вътрешно правило" in g for g in r["greshki"]), "the internal ordering rule written in the document is an error")

r = check(GOOD.replace("- Действие на природни сили;\n- Късо съединение;", "А) Действие на природни сили;\nБ) Късо съединение;"), META)
ok(any("с тирета" in z for z in r["za_proverka"]), "letters in the list before the version headings are flagged")

r = check(GOOD.replace("в тестово село.", "в тестово село. От протокола не личи да са иззети веществени доказателства."), META)
ok(any("– няма." in g for g in r["greshki"]), "„не личи да са иззети“ is an error")
r = check(GOOD + "\nЧасовете на ликвидиране не са отразени в материалите.\n", META)
ok(any("попитай експерта" in z for z in r["za_proverka"]), "times written off as missing")
bad = GOOD.replace("Каква е причината за пожара?\n2.", "Каква е причината?\n2.")
r = check(bad, META, QUESTIONS)
ok(any("дословно" in g for g in r["greshki"]), "a question not verbatim")
r = check(GOOD.replace("### Изследване на въпрос № 2:", "### Изследване на въпрос № 3:"), META)
ok(any("по ред" in g for g in r["greshki"]), "answers out of order")
r = check(GOOD.replace("**В). Самозапалване.**\n\nНяма порест материал с натрупване на топлина. Извод: Версията отпада.\n\n", ""), META)
ok(not any("стандартните версии" in g for g in r["greshki"]), "самозапалване is not required")
r = check(GOOD.replace("**Б). Късо съединение.**\n\nПостройката няма ел. инсталация. Извод: Версията отпада.\n\n", ""), META)
ok(any("късо съединение" in g for g in r["greshki"]), "a missing standard version")
r = check(GOOD + "\nВъзможно е подпалване.\n", META)
ok(any("злонамерено внесен" in g for g in r["greshki"]), "„подпалване“ is arson wording too")
for word in ("Обвиняемият прави самопризнания.", "Деецът е избягал.", "Има заповед за защита."):
    r = check(GOOD + "\n" + word + "\n", META)
    ok(not r["ok"], f"„{word}“ is flagged")
r = check(GOOD.replace("Постройката няма ел. инсталация. Извод: Версията отпада.", "Постройката няма ел. инсталация."), META)
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
ok(any("злонамерено внесен" in g for g in r["greshki"]), "„палеж“ instead of „злонамерено внесен външен огнеизточник“")
r = check(GOOD.replace("2. Къде се е намирало огнището?", "2. Касае ли се за умишлени действия?"), META)
ok(not any("злонамерено внесен" in g for g in r["greshki"]), "a question quoted verbatim in section II may say „умишлени действия“")
r = check(GOOD.replace("2. Къде се е намирало огнището?", "2. Касае ли се за умисъл?").replace(
    "Отговор на втори въпрос: Къде се е намирало огнището?", "Отговор на втори въпрос: Касае ли се за умисъл?"), META)
ok(not any("злонамерено внесен" in g for g in r["greshki"]), "the question repeated in section IV may say „умисъл“")
r = check(GOOD + "\nНе може да се изключи умисъл.\n", META)
ok(any("злонамерено внесен" in g for g in r["greshki"]), "„умисъл“ instead of „злонамерено внесен външен огнеизточник“")
r = check(GOOD.replace("1. Каква е причината за пожара?", "1. Каква е причината за пожара по чл. 330 от НК?").replace(
    "Отговор на първи въпрос: Каква е причината за пожара?", "Отговор на първи въпрос: Каква е причината за пожара по чл. 330 от НК?"), META)
ok(not any("НК" in g for g in r["greshki"]), "a question quoting НК is not a legal qualification")
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
