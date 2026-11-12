#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
za_sada.py — the expert's court-preparation note (references/za_sada.md) as a plain .docx.

The note is internal: it is not filed with the case, so it has no letterhead and no signature – only a line
at the top saying so. The common typography applies (no bold, the dash „-“, „№ 4“).

    python3 scripts/za_sada.py za_sada.md -o "/mnt/user-data/outputs/Za_sada_....docx"

The .md is simple: „# Заглавие“, „## Раздел“, paragraphs, „- “ bullets and „1. “ numbered lines.
Markdown emphasis (**…**, *…*) is dropped – the documents have no bold.
"""
import argparse
import os
import re
import sys

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Cm, Pt

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "_shared", "scripts"))
from docx_common import report, typo, typo_all  # noqa: E402  (the common typography rules and the final check)

NOTE = "Вътрешна бележка за вещото лице – не се прилага по делото"
FONT = "Times New Roman"


def clean(text):
    return typo(re.sub(r"\*\*|__|(?<!\w)\*(?!\s)|(?<!\s)\*(?!\w)", "", text).strip())


def para(doc, text, size=12, align=None, underline=False, space_before=0, indent=None, style=None):
    p = doc.add_paragraph(style=style)
    run = p.add_run(clean(text))
    run.font.name = FONT
    run.font.size = Pt(size)
    run.underline = underline
    pf = p.paragraph_format
    pf.space_before = Pt(space_before)
    pf.space_after = Pt(4)
    if align is not None:
        p.alignment = align
    if indent is not None:
        pf.left_indent = Cm(indent)
    return p


def build(md, out):
    doc = Document()
    for s in doc.sections:
        s.top_margin = s.bottom_margin = Cm(2)
        s.left_margin = Cm(2.5)
        s.right_margin = Cm(1.5)
    normal = doc.styles["Normal"]
    normal.font.name = FONT
    normal.font.size = Pt(12)

    para(doc, NOTE, size=10, align=WD_ALIGN_PARAGRAPH.RIGHT)
    for line in md.splitlines():
        s = line.rstrip()
        if not s.strip():
            continue
        if s.startswith("# "):
            para(doc, s[2:], size=14, align=WD_ALIGN_PARAGRAPH.CENTER, space_before=6)
        elif s.startswith("## ") or s.startswith("### "):
            para(doc, s.lstrip("#").strip(), underline=True, space_before=8)
        elif re.match(r"^\s*[-–]\s+", s):
            para(doc, "- " + re.sub(r"^\s*[-–]\s+", "", s), indent=0.75 if s.startswith(" ") else 0.5)
        elif re.match(r"^\s*\d+\.\s+", s):
            para(doc, s.strip(), indent=0.5)
        else:
            p = para(doc, s.strip(), align=WD_ALIGN_PARAGRAPH.JUSTIFY)
            p.paragraph_format.first_line_indent = Cm(1)
    typo_all(doc)
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    doc.save(out)
    report(out, letterhead=False)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description="бележката за съда като .docx")
    ap.add_argument("md")
    ap.add_argument("-o", "--out", required=True)
    a = ap.parse_args(argv)
    print(build(open(a.md, encoding="utf-8").read(), a.out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
