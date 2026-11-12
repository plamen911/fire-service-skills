#!/usr/bin/env python3
"""Tests for za_sada.py – the court-preparation note. Run from the skill folder:
    python3 tests/test_za_sada.py
The note is invented, not a real case.
"""
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "scripts"))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "_shared", "scripts"))
from za_sada import NOTE, build  # noqa: E402
from docx_common import check_document  # noqa: E402
import docx  # noqa: E402

failures = []


def ok(cond, msg):
    print(("  ok  " if cond else "  FAIL ") + msg)
    if not cond:
        failures.append(msg)


MD = """# Подготовка за разпит на вещото лице
## ЕПТЗ по ДП № 1234/2026 – стопанска постройка, тестово село, 01.10.2026

## 1. Накратко
1. Причината – **небрежност** с незагасена цигара.

## 2. На какво стъпва всеки извод
- Огнището – в южния ъгъл: снимки № 3–7 от фотоалбум рег. № R-1/2026 г.
  - локални термични поражения по гредите

Причината е установена чрез метода на отхвърлянето.

## 4. Вероятни въпроси
1. Присъствахте ли на огледа? – Не, огледът е извършен от разследващ полицай.
"""

with tempfile.TemporaryDirectory() as d:
    out = build(MD, os.path.join(d, "Za_sada_test.docx"))
    ok(os.path.exists(out), "the .docx is written")
    problems = check_document(out, letterhead=False)
    ok(problems == [], f"common rules hold (no bold, dash „–“, „№ 4“): {problems}")
    text = "\n".join(p.text for p in docx.Document(out).paragraphs)
    ok(text.splitlines()[0] == NOTE, "first line says it is an internal note")
    ok("**" not in text, "markdown emphasis is dropped")
    ok("№ 3-7" in text and " - " not in text, "dash between words „–“, ranges „-“")
    ok("небрежност" in text and "Присъствахте ли на огледа?" in text, "the content is kept")

if failures:
    print(f"\n{len(failures)} FAILED")
    sys.exit(1)
print("\nall passed")
