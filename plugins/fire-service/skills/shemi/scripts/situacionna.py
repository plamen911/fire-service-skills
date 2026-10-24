#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
situacionna.py — СИТУАЦИОННА СХЕМА на обект по чл. 5, ал. 2 и чл. 7, ал. 3 от Указанията за разработване на
планове за пожарогасене (рег. № Iз-2749/18.11.2010 г. на МВР) като .docx за печат – два листа A4, легнали:

  1. графична част (Приложение № 2а) – листът с рамката, полето за номера и антетката; чертае го
     scripts/shema.py (същият JSON, с "list"), знаците са от библиотеката scripts/znatsi.py;
  2. таблична част (Приложение № 2б) – таблицата като таблица на Word (попълва се и на ръка), полето за
     номера горе вдясно (чл. 9, ал. 3) и легендата с условните знаци (чл. 9, ал. 10).

По чл. 9, ал. 6 графичната част е на лицевата страна, а табличната – на гърба ѝ: печата се двустранно.

    python3 scripts/situacionna.py situacionna.json -o "/mnt/user-data/outputs/Situacionna_shema_<Обект>.docx"

situacionna.json е JSON-ът на схемата (входът – в началото на scripts/shema.py), с "list" и още:
{
  ...полетата на схемата: "sgradi" (с "etazhnost", "kategoriya", "ogneustoychivost"), "ulitsi", "vodoprovod",
     "vodoiztochnitsi", "gazoprovod", "gaz_armatura", "bez_parkirane", "razstoyaniya", "obekti" („Ел.“) ...,
  "list": {"nomer": "7", "obekt": "…", "sobstvenik": "…", "data": "24.10.2026", ...},
                                               // "izgotvil" по подразбиране – потребителят по личния ключ;
                                               // "fail" – името на .dxf файла на графичната част
                                               //   (с конектора – името от whoami); "data" – днешната дата
  "obekt_gps": "43.4125702,24.6504731",       // точката на обекта или линк към нея – тогава разстоянието и
                                               //   времето се смятат сами от службата по заповедта (marshrut.py:
                                               //   по пътищата, 1 km/min и 1 min излизане); "sluzhba": "…" – от друга служба
  "tablitsa": {
    "razstoyanie_km": 3.2,                     // от службата до обекта (иначе – от "obekt_gps")
    "vreme_min": 7,                            // времето за реагиране (иначе – излизане + движение от "obekt_gps")
    "redove": [{"natovarvane_vid": "мебели, текстил", "natovarvane_kg_m2": 25,
                "pgi_vid": "", "pgi_kolichestvo": "",            // пожарогасителни инсталации: вид и к-во гас. в-во
                "gasitelni_neobhodimi": "вода", "gasitelni_zabraneni": "",
                "rvm_vid": "", "rvm_kolichestvo": "",            // рискови вещества и материали
                "gazove_vid": "", "gazove_kolichestvo": "",
                "zashtita": "ДА"}],                              // вид защита на служителите
    "prazni_redove": 6                         // общо редове в таблицата (празните се попълват на ръка)
  },
  "legenda": true                              // легендата под таблицата (по подразбиране – да)
}

Празна клетка остава празна – стойност, която не е дадена, не се измисля.
Типографията следва _shared/conventions.md: „№ 4“, тире „–“, без получер шрифт; без шапка (бланката е
листът по Приложение № 2а).

Отпечатва JSON {"output", "grafichna", "mashtab", "redove", "preduprezhdeniya"}. Предупрежденията казват
какво от чл. 7, ал. 3 липсва в графичната и в табличната част.

Грешки (на stderr, код ≠ 0):
    BAD_INPUT: ...   — неверен JSON, липсва "sgradi" или "list"
"""
import argparse
import datetime
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "_shared", "scripts"))

import shema  # noqa: E402

from docx import Document  # noqa: E402
from docx.enum.section import WD_ORIENT, WD_SECTION  # noqa: E402
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT, WD_TABLE_ALIGNMENT  # noqa: E402
from docx.enum.text import WD_ALIGN_PARAGRAPH  # noqa: E402
from docx.oxml import OxmlElement  # noqa: E402
from docx.oxml.ns import qn  # noqa: E402
from docx.shared import Cm, Pt  # noqa: E402

try:
    from docx_common import report, typo, typo_all  # noqa: E402
except ImportError:  # pragma: no cover – the skill without _shared (development tree)
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(HERE))), "shared", "scripts"))
    from docx_common import report, typo, typo_all  # noqa: E402

FONT = "Times New Roman"
# Приложение № 2б: the columns – (key, the caption of the group, the caption under it); the group spans its columns
COLUMNS = [
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
WIDTHS_CM = [2.1, 1.9, 2.3, 1.7, 2.0, 1.8, 2.1, 2.1, 2.1, 1.9, 2.1, 1.9, 2.7]   # 26.7 cm – the frame's width
# the page: A4 landscape; the margins are where the frame of Приложение № 2а is (left 2 cm for binding)
MARGINS = dict(left=2.0, right=1.0, top=1.0, bottom=1.0)


def bad(msg):
    sys.stderr.write("BAD_INPUT: " + msg + "\n")
    sys.exit(2)


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


def cell_text(cell, text, size=9, align=WD_ALIGN_PARAGRAPH.CENTER):
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
    r.font.name, r.font.size = FONT, Pt(6)
    p2 = c.add_paragraph()
    p2.alignment = WD_ALIGN_PARAGRAPH.CENTER
    if nomer:
        r = p2.add_run(str(nomer))
        r.font.name, r.font.size = FONT, Pt(12)


def table_2b(doc, tab):
    rows = list(tab.get("redove") or [])
    if not isinstance(rows, list) or not all(isinstance(r, dict) for r in rows):
        bad("tablitsa.redove: очаква се списък от обекти")
    if rows:                                           # the distance and the time go on the first row
        rows[0] = {"razstoyanie_km": tab.get("razstoyanie_km"), "vreme_min": tab.get("vreme_min"), **rows[0]}
    elif tab.get("razstoyanie_km") is not None or tab.get("vreme_min") is not None:
        rows = [{"razstoyanie_km": tab.get("razstoyanie_km"), "vreme_min": tab.get("vreme_min")}]
    total = max(len(rows), int(tab.get("prazni_redove", 6) or 0))
    t = doc.add_table(rows=2 + total, cols=len(COLUMNS))
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    t.autofit = False
    borders(t)
    fixed_width(t, WIDTHS_CM)
    # the two header rows: a group over its columns; a column without a caption under it spans both rows
    i = 0
    while i < len(COLUMNS):
        j = i
        while j + 1 < len(COLUMNS) and COLUMNS[j + 1][1] == COLUMNS[i][1]:
            j += 1
        top = t.cell(0, i).merge(t.cell(0, j)) if j > i else t.cell(0, i)
        cell_text(top, COLUMNS[i][1])
        for k in range(i, j + 1):
            cell_text(t.cell(1, k), COLUMNS[k][2])
        if j == i and not COLUMNS[i][2]:
            t.cell(0, i).merge(t.cell(1, i))
            cell_text(t.cell(0, i), COLUMNS[i][1])
        i = j + 1
    row_height(t.rows[0], 1.3)
    row_height(t.rows[1], 0.8)
    for r, data in enumerate(rows + [{}] * (total - len(rows))):
        row = t.rows[2 + r]
        row_height(row, 1.0)
        for c, (key, _, _) in enumerate(COLUMNS):
            cell_text(row.cells[c], fmt(data.get(key)), 9)
    return len(rows)


def table_gaps(tab):
    gaps = []
    if tab.get("razstoyanie_km") in (None, ""):
        gaps.append("таблична част: няма разстояние до обекта – \"razstoyanie_km\" (чл. 7, ал. 3, т. 2, б. „а“)")
    if tab.get("vreme_min") in (None, ""):
        gaps.append("таблична част: няма време за реагиране – \"vreme_min\" (б. „б“)")
    rows = tab.get("redove") or []
    for key, what, letter in (("natovarvane_vid", "горимото натоварване", "в"),
                              ("gasitelni_neobhodimi", "необходимите гасителни вещества", "д"),
                              ("zashtita", "вида защита на служителите", "з")):
        if not any(str(r.get(key) or "").strip() for r in rows):
            gaps.append(f"таблична част: няма {what} (б. „{letter}“)")
    return gaps


def own_name():
    """Име и фамилия на потребителя по личния му ключ (списъкът на служителите – _shared/profile.md);
    None, когато ключ няма (тогава "izgotvil" се подава от whoami на конектора)."""
    script = os.path.join(os.path.dirname(HERE), "_shared", "scripts", "sluzhiteli.py")
    if not os.path.exists(script):
        script = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(HERE))), "shared", "scripts", "sluzhiteli.py")
    try:
        r = subprocess.run([sys.executable, script, "--profil"], capture_output=True, text=True, timeout=90)
        return (json.loads(r.stdout).get("profil") or {}).get("ime") if r.returncode == 0 else None
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return None


def route_to(target, ot=None):
    """Distance and travel time from the responsible service (marshrut.py); None when it cannot be computed."""
    script = os.path.join(os.path.dirname(HERE), "_shared", "scripts", "marshrut.py")
    if not os.path.exists(script):
        script = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(HERE))), "shared", "scripts", "marshrut.py")
    cmd = [sys.executable, script, "--link" if "://" in target else "--do", target] + (["--ot", ot] if ot else [])
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        return json.loads(r.stdout) if r.returncode == 0 else None
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return None


def build(d, out):
    if not isinstance(d, dict):
        bad("очаква се JSON обект")
    if not isinstance(d.get("list"), dict):
        bad("липсва \"list\" – полетата на антетката (поне \"obekt\")")
    tab = d.get("tablitsa") or {}
    if not isinstance(tab, dict):
        bad("tablitsa: очаква се обект")
    lst = d["list"]
    gaps = []
    if not str(lst.get("izgotvil") or "").strip():         # „Изготвил“ – потребителят по ключа
        name = own_name()
        if name:
            lst["izgotvil"] = name
        else:
            gaps.append("„Изготвил“ е празно – подай \"list.izgotvil\" (името от whoami на конектора)")
    target = str(d.get("obekt_gps") or "").strip()
    marshrut = None
    if target and (tab.get("razstoyanie_km") in (None, "") or tab.get("vreme_min") in (None, "")):
        marshrut = route_to(target, d.get("sluzhba"))     # the table's distance and time – from the service
        if marshrut:
            if tab.get("razstoyanie_km") in (None, ""):
                tab["razstoyanie_km"] = round(marshrut["razstoyanie_km"], 1)
            if tab.get("vreme_min") in (None, ""):
                tab["vreme_min"] = marshrut["vreme_min"]
        else:
            gaps.append("разстоянието и времето не се изчислиха (marshrut.py) – пусни го отделно и ги подай в \"tablitsa\"")
    if not str(lst.get("data") or "").strip():
        lst["data"] = datetime.date.today().strftime("%d.%m.%Y")
    base = os.path.splitext(out)[0]
    png = base + "_grafichna.png"
    dxf = base + ".dxf"                                # the graphic part for AutoCAD / CorelDRAW
    if not str(lst.get("fail") or "").strip():         # „Име на файла“ – the drawing's own file
        lst["fail"] = os.path.basename(dxf)
    _, _, warnings, extra = shema.render(d, png, out_dxf=dxf)

    doc = Document()
    st = doc.styles["Normal"]
    st.font.name, st.font.size = FONT, Pt(10)
    st.element.rPr.rFonts.set(qn("w:eastAsia"), FONT)
    page(doc.sections[0])
    # 1. the graphic part – the whole framed sheet
    p = para(doc)
    p.add_run().add_picture(png, width=Cm(26.6))
    # 2. the table part – on a new landscape page (the back of the sheet)
    sec = doc.add_section(WD_SECTION.NEW_PAGE)
    page(sec)
    number_box(doc, lst.get("nomer"))
    para(doc, "Ситуационна схема – таблична част", 12, WD_ALIGN_PARAGRAPH.CENTER)
    if lst.get("obekt"):
        para(doc, str(lst["obekt"]), 10, WD_ALIGN_PARAGRAPH.CENTER, after=6)
    n = table_2b(doc, tab)
    if d.get("legenda", True):
        leg = base + "_legenda.png"
        if shema.render_legend(d, leg, width_cm=20.0):
            para(doc, "", after=4)
            q = para(doc)
            q.add_run().add_picture(leg, width=Cm(20.0))
    typo_all(doc)
    doc.save(out)
    report(out, letterhead=False)
    return {"output": out, "grafichna": png, "dxf": extra.get("dxf"), "mashtab": extra.get("mashtab"), "redove": n,
            "izgotvil": lst.get("izgotvil") or None, "marshrut": marshrut,
            "preduprezhdeniya": warnings + gaps + table_gaps(tab)}


def main():
    ap = argparse.ArgumentParser(description="Ситуационна схема на обект (Приложения № 2а и № 2б към Iз-2749)")
    ap.add_argument("data", help="JSON на схемата с \"list\" и \"tablitsa\"")
    ap.add_argument("-o", "--out", required=True, help="изходен .docx")
    a = ap.parse_args()
    try:
        with open(a.data, encoding="utf-8") as f:
            d = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        bad(f"не мога да прочета {a.data}: {e}")
    os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
    print(json.dumps(build(d, a.out), ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
