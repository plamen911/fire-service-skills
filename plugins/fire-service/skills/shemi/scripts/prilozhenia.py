#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
prilozhenia.py — the table parts of a fire-fighting plan as Word tables, by the forms of the Указания
Iз-2749/2010 – one place for all of them: Приложение № 2б (ситуационна схема, чл. 7, ал. 3, т. 2), № 3б
(конкретна схема, чл. 7, ал. 4, т. 2) and № 4 (бланка за отчитане на произшествията и занятията, чл. 7, ал. 5).
The page (A4 landscape, the margins of the frame of Приложение № 2а / № 3а), the field for the plan's number
(чл. 9, ал. 3) and the table with its two header rows. Imported by situacionna.py, konkretna_docx.py and the
plan-pozharogasene skill; not run on its own. No bold (_shared/conventions.md).
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "_shared", "scripts"))

from docx.enum.section import WD_ORIENT  # noqa: E402
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT, WD_TABLE_ALIGNMENT  # noqa: E402
from docx.enum.text import WD_ALIGN_PARAGRAPH  # noqa: E402
from docx.oxml import OxmlElement  # noqa: E402
from docx.oxml.ns import qn  # noqa: E402
from docx.shared import Cm, Pt  # noqa: E402

try:
    from docx_common import typo  # noqa: E402
except ImportError:  # pragma: no cover – the skill without _shared (development tree)
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(HERE))), "shared", "scripts"))
    from docx_common import typo  # noqa: E402

FONT = "Times New Roman"
# the columns of each form – (key, the caption of the group, the caption under it); a group spans its columns,
#   a column with no caption under it spans both header rows
COLUMNS_2B = [
    ("razstoyanie_km", "Разстояние до обекта", "km"),
    ("vreme_min", "Време за реагиране", "min"),
    ("natovarvane_vid", "ГОРИМО НАТОВАРВАНЕ", "вид"),
    ("natovarvane_kg_m2", "ГОРИМО НАТОВАРВАНЕ", "к-во в kg/m²"),
    ("pgi_vid", "ПОЖАРОГАСИТЕЛНИ ИНСТАЛАЦИИ", "вид гас. в-во"),
    ("pgi_kolichestvo", "ПОЖАРОГАСИТЕЛНИ ИНСТАЛАЦИИ", "к-во гас. в-во"),
    ("gasitelni_neobhodimi", "ГАСИТЕЛНИ ВЕЩЕСТВА", "необходими"),
    ("gasitelni_zabraneni", "ГАСИТЕЛНИ ВЕЩЕСТВА", "забранени"),
    ("rvm_vid", "РИСКОВИ ВЕЩЕСТВА И МАТЕРИАЛИ", "вид"),
    ("rvm_kolichestvo", "РИСКОВИ ВЕЩЕСТВА И МАТЕРИАЛИ", "количество"),
    ("gazove_vid", "ГОРИМИ ГАЗОВЕ", "вид"),
    ("gazove_kolichestvo", "ГОРИМИ ГАЗОВЕ", "количество"),
    ("zashtita", "Вид защита на служителите", ""),
]
WIDTHS_2B = [2.1, 1.9, 2.3, 1.7, 2.0, 1.8, 2.1, 2.1, 2.1, 1.9, 2.1, 1.9, 2.7]   # 26.7 cm – the frame's width
COLUMNS_3B = [
    ("kategoriya", "Категория по пожарна опасност", ""),
    ("ogneustoychivost", "Степен на огнеустойчивост", ""),
    ("natovarvane_vid", "ОСНОВНО ГОРИМО НАТОВАРВАНЕ", "вид"),
    ("natovarvane_kg_m2", "ОСНОВНО ГОРИМО НАТОВАРВАНЕ", "количество (kg/m²)"),
    ("pgi_vid", "ПГИ", "вид гас. вещество"),
    ("pgi_kolichestvo", "ПГИ", "количество гас. вещество"),
    ("vl_m_min", "Линейна скорост (m/min)", ""),
    ("plamna_c", "Пламна температура (t° на възплам.) (°C)", ""),
    ("gasitelni_neobhodimi", "Гасителни вещества", "необходими"),
    ("gasitelni_zabraneni", "Гасителни вещества", "забранени"),
    ("zashtita", "Вид защита на служителите", ""),
    ("rvm_vid", "Рискови вещества и материали", "вид"),
    ("rvm_kolichestvo", "Рискови вещества и материали", "количество"),
    ("rvm_razresheni", "Рискови вещества и материали", "разрешени гас. вещества за неутрализиране"),
    ("rvm_zabraneni", "Рискови вещества и материали", "забранени гас. вещества за неутрализиране"),
    ("drugi", "Други данни", ""),
]
WIDTHS_3B = [1.6, 1.4, 2.4, 1.4, 1.6, 1.4, 1.3, 1.4, 1.7, 1.9, 1.9, 1.5, 1.3, 1.7, 1.7, 2.5]   # 26.7 cm
COLUMNS_4 = [
    ("nomer", "№ по ред", ""),
    ("data", "Дата", ""),
    ("proizshestvie", "Произшествие или занятие", ""),
    ("zabelezhki", "Констатирани несъответствия или други забележки, които следва да бъдат отразени в плана", ""),
    ("podpis", "Фамилия, подпис на РОД или ръководителя на занятието", ""),
]
WIDTHS_4 = [1.7, 2.6, 6.4, 10.0, 6.0]                    # 26.7 cm
# the page: A4 landscape; the margins are where the frame of Приложение № 2а is (left 2 cm for binding)
MARGINS = dict(left=2.0, right=1.0, top=1.0, bottom=1.0)


def fmt(v):
    if v is None:
        return ""
    if isinstance(v, float):
        return f"{v:g}".replace(".", ",")
    return str(v)


def page(sec):
    sec.orientation = WD_ORIENT.LANDSCAPE
    sec.page_width, sec.page_height = Cm(29.7), Cm(21.0)
    sec.left_margin, sec.right_margin = Cm(MARGINS["left"]), Cm(MARGINS["right"])
    sec.top_margin, sec.bottom_margin = Cm(MARGINS["top"]), Cm(MARGINS["bottom"])
    sec.header_distance = sec.footer_distance = Cm(0.5)


def para(doc_or_cell, text="", size=10, align=None, after=0):
    p = doc_or_cell.add_paragraph()
    pf = p.paragraph_format
    pf.space_before, pf.space_after, pf.line_spacing = Pt(0), Pt(after), 1.0
    if align is not None:
        p.alignment = align
    if text:
        r = p.add_run(typo(text))
        r.font.name, r.font.size = FONT, Pt(size)
        r._element.rPr.rFonts.set(qn("w:eastAsia"), FONT)
    return p


VOWELS = set("аъоуеиюяэыaeiouАЪОУЕИЮЯ")
CHAR_CM = 0.021       # the width of a Cyrillic letter of Times New Roman, per pt, with room to spare (0,21 cm at 10 pt)


def soft_hyphens(text, width_cm, size):
    """A word longer than its column gets soft hyphens (shown only where Word or LibreOffice breaks the line)
    between syllables (V-CV, VC-CV: „ог-неус-той-чи-вост“) – instead of a break anywhere in the word."""
    fit = max(3, int((width_cm - 0.3) / (CHAR_CM * size)))
    out = []
    for word in str(text).split(" "):
        m = re.fullmatch(r"(\W*)(\w+)(\W*)", word)
        if not (m and len(word) > fit and m.group(2).isalpha()):
            out.append(word)
            continue
        pre, w, post = m.groups()
        if True:
            r = ""
            for i, ch in enumerate(w):
                r += ch
                nxt = w[i + 1:i + 3]
                if 1 <= i < len(w) - 2 and len(nxt) == 2 and (
                        (ch in VOWELS and nxt[0] not in VOWELS and nxt[1] in VOWELS)            # по-жар
                        or (ch not in VOWELS and w[i - 1] in VOWELS and nxt[0] not in VOWELS     # пожар-на
                            and nxt[0] != "й" and nxt[1] in VOWELS and i < len(w) - 3)):
                    r += "\u00ad"
            w = r
        out.append(pre + w + post)
    return " ".join(out)


def cell_text(cell, text, size=10, align=WD_ALIGN_PARAGRAPH.CENTER):
    if text and cell.width:
        text = soft_hyphens(text, cell.width.cm, size)
    cell.text = ""
    p = cell.paragraphs[0]
    p.alignment = align
    p.paragraph_format.space_before = p.paragraph_format.space_after = Pt(0)
    if text:
        r = p.add_run(typo(text))
        r.font.name, r.font.size = FONT, Pt(size)
    cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER


def borders(table):
    tbl = table._tbl
    pr = tbl.tblPr
    b = OxmlElement("w:tblBorders")
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        e = OxmlElement(f"w:{edge}")
        e.set(qn("w:val"), "single")
        e.set(qn("w:sz"), "6")
        e.set(qn("w:color"), "000000")
        b.append(e)
    pr.append(b)


def fixed_width(table, widths_cm):
    """A fixed layout with the given column widths – Word and LibreOffice both keep them."""
    pr = table._tbl.tblPr
    w = OxmlElement("w:tblW")
    w.set(qn("w:w"), str(int(sum(widths_cm) * 567)))
    w.set(qn("w:type"), "dxa")
    pr.append(w)
    lay = OxmlElement("w:tblLayout")
    lay.set(qn("w:type"), "fixed")
    pr.append(lay)
    grid = table._tbl.tblGrid
    for col, cm in zip(grid.findall(qn("w:gridCol")), widths_cm):
        col.set(qn("w:w"), str(int(cm * 567)))
    for row in table.rows:
        for cell, cm in zip(row.cells, widths_cm):
            cell.width = Cm(cm)


def row_height(row, cm, exact=False):
    trPr = row._tr.get_or_add_trPr()
    h = OxmlElement("w:trHeight")
    h.set(qn("w:val"), str(int(cm * 567)))
    h.set(qn("w:hRule"), "exact" if exact else "atLeast")
    trPr.append(h)


def number_box(doc, nomer):
    """The field for the plan's number – 20 × 15 mm in the upper right corner (чл. 9, ал. 3)."""
    t = doc.add_table(rows=1, cols=1)
    t.alignment = WD_TABLE_ALIGNMENT.RIGHT
    borders(t)
    fixed_width(t, [2.0])
    c = t.cell(0, 0)
    row_height(t.rows[0], 1.5, exact=True)
    c.text = ""
    p = c.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run("№ на плана")
    r.font.name, r.font.size = FONT, Pt(8)
    p2 = c.add_paragraph()
    p2.alignment = WD_ALIGN_PARAGRAPH.CENTER
    if nomer:
        r = p2.add_run(str(nomer))
        r.font.name, r.font.size = FONT, Pt(12)


TABLE_PT = 10        # one readable size for every cell of the forms (Приложения № 2б, 3б, 4) – headers included


def table(doc, columns, widths, rows, total, numbered=False, row_cm=1.0, size=TABLE_PT):
    """A table of a form: the two header rows (a group over its columns), the given rows, then empty rows up to
    `total` (filled in by hand); `numbered` – a row with the column numbers under the header (Приложение № 4)."""
    head = 3 if numbered else 2
    t = doc.add_table(rows=head + total, cols=len(columns))
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    t.autofit = False
    borders(t)
    fixed_width(t, widths)
    i = 0
    while i < len(columns):
        j = i
        while j + 1 < len(columns) and columns[j + 1][1] == columns[i][1]:
            j += 1
        top = t.cell(0, i).merge(t.cell(0, j)) if j > i else t.cell(0, i)
        cell_text(top, columns[i][1], TABLE_PT)
        for k in range(i, j + 1):
            cell_text(t.cell(1, k), columns[k][2], TABLE_PT)
        if j == i and not columns[i][2]:
            t.cell(0, i).merge(t.cell(1, i))
            cell_text(t.cell(0, i), columns[i][1], TABLE_PT)
        i = j + 1
    row_height(t.rows[0], 1.3)
    row_height(t.rows[1], 0.8)
    if numbered:
        for k in range(len(columns)):
            cell_text(t.cell(2, k), str(k + 1), TABLE_PT)
    for r, data in enumerate(list(rows) + [{}] * (total - len(rows))):
        row = t.rows[head + r]
        row_height(row, row_cm)
        for c, (key, _, _) in enumerate(columns):
            cell_text(row.cells[c], fmt(data.get(key)), size)
    return t


def table_2b(doc, tab):
    """Приложение № 2б – the distance and the time go on the first row."""
    rows = list(tab.get("redove") or [])
    if not isinstance(rows, list) or not all(isinstance(r, dict) for r in rows):
        raise ValueError("tablitsa.redove: очаква се списък от обекти")
    if rows:
        rows[0] = {"razstoyanie_km": tab.get("razstoyanie_km"), "vreme_min": tab.get("vreme_min"), **rows[0]}
    elif tab.get("razstoyanie_km") is not None or tab.get("vreme_min") is not None:
        rows = [{"razstoyanie_km": tab.get("razstoyanie_km"), "vreme_min": tab.get("vreme_min")}]
    total = max(len(rows), int(tab.get("prazni_redove", 6) or 0))
    table(doc, COLUMNS_2B, WIDTHS_2B, rows, total)
    return len(rows)


def table_3b(doc, tab):
    """Приложение № 3б – one row per hazard of the room (the main fire load first)."""
    rows = list(tab.get("redove") or [])
    if not all(isinstance(r, dict) for r in rows):
        raise ValueError("tablitsa_3b.redove: очаква се списък от обекти")
    total = max(len(rows), int(tab.get("prazni_redove", 4) or 0))
    table(doc, COLUMNS_3B, WIDTHS_3B, rows, total)
    return len(rows)


def table_4(doc, redove=None, broi=14):
    """Приложение № 4 – the form for the incidents and the exercises; filled in by hand by the РМ or the head
    of the exercise, so it comes out empty (or with the rows already given)."""
    rows = list(redove or [])
    table(doc, COLUMNS_4, WIDTHS_4, rows, max(len(rows), broi), numbered=True, row_cm=0.9)
    return len(rows)
