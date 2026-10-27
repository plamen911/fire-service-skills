#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
razchet_docx.py — РАЗЧЕТЪТ НА СИЛИТЕ И СРЕДСТВАТА (Приложение № 5 към Указанията Iз-2749/2010) като .docx: само
изчисленията – без бланка, дата и подпис, на една страница (A4 легнало, в две колони; шрифтът се смалява от 11 до
8 pt, докато се събере), защото се печата на гърба на листа на своята конкретна схема (чл. 7, ал. 4).

    python3 scripts/sili.py tvardi … > sili.json
    python3 scripts/razchet_docx.py sili.json --kam "/mnt/user-data/outputs/Konkretna_shema_Garderob_2et.docx" \
        --naslov "Конкретна схема № 2 – пожар в гардероба, 2 етаж" --obekt "ЦПЛР – …, гр. Плевен, ул. … № …" \
        --pomeshtenie "Гардероб, 2 етаж – 10,5 × 7,1 m"

--kam дава името на файла: Razchet_<името на конкретната схема>.docx в същата папка (иначе -o).
Отпечатва JSON {"output", "preduprezhdeniya"}.
"""
import argparse
import json
import math
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SKILLS = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(SKILLS, "plan-konspekti", "scripts"))
import blanka as B  # noqa: E402  (the common blank of the plugin)

# what each input means – the labels of the „vhodni“ of sili.py
VHODNI = [("forma", "Форма на пожара"), ("vl", "Линейна скорост на разпространение, vл"),
          ("t3", "Време до локализирането"), ("fp", "Площ на пожара, Fп"), ("a", "Ширина на фронта, a"),
          ("b", "Другата страна, b"), ("n", "Посоки на разпространение"), ("ataka", "Начин на гасене"),
          ("hg", "Дълбочина на гасене, hг"), ("i", "Необходима интензивност, Iг"), ("i_g", "Интензивност"),
          ("struinik", "Струйник"), ("zashtita", "Защита"), ("q_pa", "Пожарен автомобил"),
          ("w_pa", "Пожарен автомобил"), ("v", "Обем"), ("gaz", "Вещество"), ("pgv", "Пенообразувател")]
REZULTAT = [("plosht_na_pozhara_m2", "Площ на пожара", "m2"), ("plosht_na_gasene_m2", "Площ на гасене", "m2"),
            ("razhod_za_gasene_l_s", "Необходим разход на вода за гасене", "l/s"),
            ("razhod_za_zashtita_l_s", "Необходим разход на вода за защита", "l/s"),
            ("razhod_obshto_l_s", "Общ разход на вода", "l/s"),
            ("struinitsi_za_gasene", "Струйници за гасене", "бр."),
            ("struinitsi_za_zashtita", "Струйници за защита", "бр."),
            ("struinitsi_obshto", "Струйници общо", "бр."),
            ("razstoyanie_mezhdu_struinitsite_m", "Разстояние между струйниците", "m"),
            ("ekipi_obshto", "Екипи", "бр."), ("pozharni_avtomobili", "Пожарни автомобили", "бр.")]


def bad(msg):
    sys.stderr.write("BAD_INPUT: " + msg + "\n")
    sys.exit(2)


def num(v):
    if isinstance(v, float):
        v = round(v, 2)
        v = int(v) if v == int(v) else v
    return str(v).replace(".", ",") if isinstance(v, (int, float)) else str(v)


def dec(text):
    """„74.7 m2“ → „74,7 m2“ – the decimal comma (not in a table row number like „6.3“)."""
    return re.sub(r"(?<![\w.])(\d+)\.(\d+)(?= ?(m|l|kg|min|%|бр))", r"\1,\2", B.typo(str(text)))


def target(a):
    if a.out:
        return a.out
    if not a.kam:
        bad("дай --kam (конкретната схема, към която е разчетът) или -o")
    folder, name = os.path.split(os.path.abspath(a.kam))
    return os.path.join(folder, "Razchet_" + os.path.splitext(name)[0] + ".docx")


def valid(d):
    return isinstance(d, dict) and d.get("ok") and isinstance(d.get("stapki"), list)


# ── the written calculation – as the approved calculations and the calculator JS_ppo print it: numbered sections, in
#    each the table value („Vл = 1 (м/мин) – по Табл. № 1 от Указанията“), the formula, then the same formula with the
#    numbers put in and the result, and a result line; italic, the indices as subscripts, „*“ for multiplication
SYMBOLS = [  # (as sili.py writes it, base, subscript, superscript) – the longest first
    ("nстр.екип", "n", "стр,екип", ""), ("Nг.екипи", "N", "екип", "г"), ("Nз.екипи", "N", "екип", "з"),
    ("tд.с.", "τ", "дс", ""), ("tдв.", "τ", "дв", ""), ("tр.", "τ", "р", ""), ("tсв", "τ", "св", ""),
    ("t1", "τ", "1", ""), ("t2", "τ", "2", ""), ("t3", "τ", "3", ""), ("vл", "V", "л", ""),
    ("Fпом", "F", "пом", ""), ("Fп", "F", "п", ""), ("Fг", "F", "г", ""), ("Qоб", "Q", "об", ""),
    ("Qпа", "Q", "па", ""), ("Qг", "Q", "н", "г"), ("Qз", "Q", "н", "з"), ("qекипи", "q", "екип", ""),
    ("qстр", "q", "стр", ""), ("Iг", "I", "н", ""), ("hг", "h", "г", ""), ("lстр", "l", "стр", ""),
    ("Nекипи", "N", "екип", ""), ("Nстр", "N", "стр", ""), ("Nпа", "N", "па", ""), ("Nг", "N", "стр", "г"),
    ("Nз", "N", "стр", "з")]
UNITS = {"m2": "м²", "m": "м", "l/s": "л/с", "min": "мин.", "l": "л", "kg": "кг", "бр.": ""}
COUNTS = {"(17)": ("струйник", "струйника"), "(18)": ("струйник", "струйника"), "(20)": ("екип", "екипа"),
          "(21)": ("екип", "екипа"), "(22)": ("екип", "екипа"), "(23)": ("пожарен автомобил", "пожарни автомобила")}
LABEL_SKIP = {  # a step named as its section needs no line of its own
    **{f: "Площ на пожара" for f in ("(2)", "(3)", "(4)", "(5)", "(6)", "(7)")},
    **{f: "Площ на гасене" for f in ("(8)", "(9)", "(10)", "(11)", "(12)", "(13)")},
    "(14)": "Необходим разход на вода за гасене", "(15)": "Необходим разход на вода за гасене",
    "(17)": "Струйници за гасене", "(20)": "Екипи за гасене", "(21)": "Екипи за гасене",
    "(23)": "Пожарни автомобили"}
SECTIONS = [  # (the formulas of the section, heading, its symbol (base, sub))
    (("(1)",), "Свободно време за развитие на пожара", ("τ", "св")),
    (("(2)", "(3)", "(4)", "(5)", "(6)", "(7)", ""), "Определяне площта на пожара", ("F", "п")),
    (("(8)", "(9)", "(10)", "(11)", "(12)", "(13)"), "Определяне площта на гасене", ("F", "г")),
    (("(14)", "(15)", "(16)"), "Необходим разход на вода за гасене", ("Q", "н")),
    (("(17)", "(18)", "(19)"), "Брой струйници за гасене", ("N", "стр")),
    (("(20)", "(21)", "(22)"), "Брой екипи за гасене", ("N", "екип")),
    (("(23)",), "Брой пожарни автомобили", ("N", "па"))]


def tokens(expr):
    """„Fп = n.a.(5.vл + vл.t2)“ → [(text, None, None) | (base, sub, sup)]; the dot or „·“ between factors is „ * “."""
    out, k, plain = [], 0, ""
    while k < len(expr):
        for sym, base, sub, sup in SYMBOLS:
            if expr.startswith(sym, k) and not (k and expr[k - 1].isalpha()):
                if plain:
                    out.append((plain, None, None))
                    plain = ""
                out.append((base, sub, sup))
                k += len(sym)
                break
        else:
            ch = expr[k]
            prev, nxt = expr[k - 1:k], expr[k + 1:k + 2]
            if ch == "·" or (ch == "." and prev and (prev.isalnum() or prev == ")") and nxt
                             and (nxt.isalpha() or nxt == "(") and not (prev.isdigit() and nxt.isdigit())):
                ch = " * "
            elif ch == "π":
                ch = "3,14" if any(c.isdigit() for c in expr[k + 1:]) and "=" not in expr[:k] else "π"
            plain += ch
            k += 1
    if plain:
        out.append((plain, None, None))
    return [(re.sub(r"\s+\*\s+", " * ", t) if s is None else t, s, u) for t, s, u in out]


SHORT = [False]      # the calculation under the table of Приложение № 3б – without the notes and the source
SIZE = [11]          # pt – the size of the calculation; chosen by fit() so that it goes on one page


def write_tokens(p, parts):
    size = SIZE[0]
    for text, sub, sup in parts:
        if sub is None:
            text = re.sub(r"(?<=\d)\.(?=\d)", ",", text)
            text = re.sub(r"(?<=\d) min\b", " мин.", re.sub(r"(?<=\d) m\b", " м", text)).replace("∙", "·")
            B.run(p, text, italic=True, size=size)
            continue
        B.run(p, text, italic=True, size=size)
        if sub:
            B.run(p, sub, italic=True, size=size).font.subscript = True
        if sup:
            B.run(p, sup, italic=True, size=size).font.superscript = True


def line(doc, *chunks):
    """One line of the calculation; a chunk is a string (its symbols are found) or a list of tokens."""
    p = B.fmt(doc.add_paragraph(), B.LEFT, line=None)
    p.paragraph_format.space_after = B.Pt(1 if SIZE[0] < 11 else 2)
    for ch in chunks:
        write_tokens(p, tokens(ch) if isinstance(ch, str) else ch)
    return p


def hr(p):
    """A thin rule under the paragraph – the line before the summary."""
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    ppr = p._p.get_or_add_pPr()
    bdr = OxmlElement("w:pBdr")
    bot = OxmlElement("w:bottom")
    for k, v in (("val", "single"), ("sz", "4"), ("space", "1"), ("color", "999999")):
        bot.set(qn(f"w:{k}"), v)
    bdr.append(bot)
    ppr.append(bdr)


def heading(doc, n, text, sym):
    p = B.fmt(doc.add_paragraph(), B.LEFT, line=None, keep=True)
    p.paragraph_format.space_before, p.paragraph_format.space_after = B.Pt(SIZE[0] * 0.5), B.Pt(2)
    B.run(p, f"{n}. {text}, {sym[0]}", size=SIZE[0] + 1)
    B.run(p, sym[1], size=SIZE[0] + 1).font.subscript = True


def value_of(text):
    m = re.match(r"\s*([\d.,]+)", str(text or ""))
    return m.group(1).replace(".", ",") if m else ""


def section_of(st):
    f = st.get("formula") or ""
    for i, (forms, _, _) in enumerate(SECTIONS):
        if f in forms:
            return i
    return None


def step_lines(doc, st, res):
    name = str(st.get("ime") or "")
    expr = str(st.get("izraz") or "")
    if st.get("stoinost") is None:                     # a line of the reasoning – „Fп > Fпом – …“
        line(doc, (name[0].upper() + name[1:] + ("." if not name.endswith(".") else "")) if name else "")
        if expr:
            line(doc, expr)
        return
    lhs, _, rhs = expr.partition("=")
    extra = ""
    m = re.search(r"\s*\(([^()]*на екип)\)\s*$", rhs)
    if m:
        extra, rhs = m.group(1), rhs[:m.start()]
    form = st.get("formula") or ""
    unit = UNITS.get(st.get("merna"), st.get("merna") or "")
    val = num(st["stoinost"])
    if form in COUNTS:
        one, few = COUNTS[form]
        whole = math.ceil(round(float(st["stoinost"]), 6)) or 1
        tail = f" = {val}" + (f" → {whole}" if whole != st["stoinost"] else "") + f" {one if whole == 1 else few}"
        if form in ("(17)", "(18)") and res.get("struinik"):
            tail += f" „{res['struinik']}“"
    else:
        tail = f" = {val}" + (f" ({unit})" if unit else "")
    prefix = LABEL_SKIP.get(form, "")
    if name and form != "(1)" and not (prefix and (name == prefix or name.startswith(prefix + " ("))):
        line(doc, name[0].upper() + name[1:] + ":")
    if extra:
        line(doc, extra[0].upper() + extra[1:] + ".")
    left = lhs.strip()
    sub_ = st.get("zamestvane")
    # one line, as on the approved calculations: the formula, the numbers put in, the result
    line(doc, f"{left} = {rhs.strip()}" + (f" = {sub_}" if sub_ else "") + tail)


def write(doc, d, pomeshtenie=None, belezhki=(), zashtita=None):
    """The body of the calculation into doc (its own .docx, or a section of the plan – plan-pozharogasene), as the
    approved calculations are written. Returns the warnings."""
    warnings = []
    used = d.get("vhodni") or {}
    res = d.get("rezultat") or {}
    if pomeshtenie:
        line(doc, f"Помещение: {pomeshtenie}.")
    steps = d["stapki"]
    groups, cur = {}, None
    for st in steps:                                   # a reasoning line goes with the section before it
        s = section_of(st)
        cur = s if s is not None else (cur if cur is not None else 1)
        groups.setdefault(cur, []).append(st)
    n = 0
    for i, (forms, title_, sym) in enumerate(SECTIONS):
        if i not in groups and not (i == 1 and used.get("fp")):
            continue
        n += 1
        heading(doc, n, title_, sym)
        if i == 1:
            vl = str(used.get("vl") or "")
            if vl:
                src = " – по Табл. № 1 от Указанията" if "таблица" in vl else " (зададена)"
                line(doc, [("V", "л", "")], f" = {value_of(vl)} (м/мин){src}.")
            if used.get("fp") and i not in groups:
                line(doc, [("F", "п", "")], f" = {value_of(used['fp'])} (м²) – площта на помещението (пожарът го "
                     "обхваща цялото).")
            elif used.get("fp"):
                line(doc, [("F", "п", "")], f" = {value_of(used['fp'])} (м²) (зададена).")
        if i == 2:
            if used.get("ataka"):
                line(doc, f"Гасене {used['ataka']}; ", [("h", "г", "")], f" = {value_of(used.get('hg'))} (м).")
        if i == 3 and used.get("i"):
            src = " – по Табл. № 2 от Указанията" if "таблица" in str(used["i"]) else " (зададена)"
            line(doc, [("I", "н", "")], f" = {value_of(used['i'])} (л/с∙м²){src}.")
        if i == 4 and used.get("struinik"):
            m = re.search(r"([\d.,]+) l/s", str(used["struinik"]))
            line(doc, f"Струйник „{res.get('struinik', '')}“, ", [("q", "стр", "")],
                 f" = {m.group(1).replace('.', ',') if m else ''} (л/с).")
        if i == 6 and used.get("q_pa"):
            line(doc, [("Q", "па", "")], f" = {value_of(used['q_pa'])} (л/с) – разход на помпата.")
        for st in groups.get(i, []):
            if st.get("formula") == "(16)" and res.get("struinitsi_za_zashtita"):   # the protection (5. in the Методика)
                nz = res["struinitsi_za_zashtita"]
                qz = (res.get("razhod_obshto_l_s") or 0) - (res.get("razhod_za_gasene_l_s") or 0)
                m = re.search(r"([\d.,]+) l/s", str(used.get("struinik") or ""))
                qs = m.group(1).replace(".", ",") if m else num(qz / nz)
                line(doc, "Необходим разход на вода за защита" + (f" – {zashtita}" if zashtita else "") + ":")
                line(doc, [("Q", "н", "з")], " = ", [("N", "стр", "з")], " * ", [("q", "стр", "")],
                     f" = {nz} * {qs} = {num(qz)} (л/с)")
            step_lines(doc, st, res)
        if i == 1 and res.get("plosht_na_pozhara_m2") is not None:
            line(doc, "Площ на пожара ", [("F", "п", "")], f": {num(res['plosht_na_pozhara_m2'])} м²")
        if i == 2 and res.get("plosht_na_gasene_m2") is not None:
            line(doc, "Площ на гасене ", [("F", "г", "")], f": {num(res['plosht_na_gasene_m2'])} м²")
        if i == 3 and res.get("razhod_obshto_l_s") is not None:
            if res.get("razhod_obshto_l_s") != res.get("razhod_za_gasene_l_s"):
                line(doc, "Разход за гасене и защита ", [("Q", "об", "")], f": {num(res['razhod_obshto_l_s'])} л/с")
            else:
                line(doc, "Разход за гасене ", [("Q", "н", "")], f": {num(res['razhod_obshto_l_s'])} л/с")
        if i == 5 and res.get("ekipi_obshto"):
            k = res["ekipi_obshto"]
            line(doc, f"Личен състав = 4 * {k} = {4 * k} пожарникари")
    # the summary, set off by a rule – as in JS_ppo
    p = B.fmt(doc.add_paragraph(), B.LEFT, line=None)
    p.paragraph_format.space_before = B.Pt(6)
    hr(p)
    summary = [("Брой струйници (общо)", res.get("struinitsi_obshto")), ("Брой екипи", res.get("ekipi_obshto")),
               ("Личен състав", 4 * res["ekipi_obshto"] if res.get("ekipi_obshto") else None),
               ("Брой пожарни автомобили", res.get("pozharni_avtomobili"))]
    for label, v in summary:
        if v not in (None, ""):
            line(doc, f"{label}: {v}" + (f" „{res['struinik']}“" if label.startswith("Брой струйници") and res.get("struinik") else ""))
    if not res:
        warnings.append("разчетът няма резултат")
    if SHORT[0]:                                       # under the table of № 3б: no notes, no source – room is short
        return warnings
    notes = list(d.get("belezhki") or []) + list(belezhki or [])
    for x in notes:
        line(doc, "Бележка: " + re.sub(r"(?<!ред )(?<![\d.])(\d+)\.(\d+)(?![.\d])", r"\1,\2", B.typo(x)))
    src = d.get("iztochnik")
    p = B.para(doc, B.typo(src if isinstance(src, str) else
                           "Методика – Приложение № 5 към чл. 7, ал. 6 от Указанията за разработване на "
                           "планове за пожарогасене, рег. № Iз-2749/18.11.2010 г."),
               align=B.LEFT, indent=False, size=max(8, SIZE[0] - 2), line=None)
    p.paragraph_format.space_before = B.Pt(4)
    return warnings


def title(doc, naslov=None, obekt=None, pomeshtenie=None, short=False):
    """„Разчет на силите и средствата за гасене на пожар в <обекта>, <помещението>“ – as on the approved ones;
    short – under the table of the same sheet, where the scheme and the object are already named."""
    if short:
        B.para(doc, "Разчет на силите и средствата за гасене на пожара (Приложение № 5)", align=B.LEFT, indent=False,
               size=SIZE[0] + 1, line=None)
        return
    room = str(pomeshtenie or "").split(" – ")[0].strip()
    room = room[0].lower() + room[1:] if room else ""
    where = ", ".join(x for x in (obekt, room) if x)
    if not where and naslov and re.match(r"^Конкретна схема за гасене на пожар в\s", naslov):
        where = re.sub(r"^Конкретна схема за гасене на пожар в\s*", "", naslov)
    B.para(doc, "Разчет на силите и средствата за гасене на пожар" + (f" в {where}" if where else ""),
           align=B.LEFT, indent=False, size=SIZE[0] + 1, line=None)
    if naslov:
        B.para(doc, f"(към {naslov[0].lower() + naslov[1:]})", align=B.LEFT, indent=False, size=SIZE[0] - 1, line=None)


def back_page(sec, columns=2):
    """The back of the sheet of the specific scheme: A4 landscape as the sheet, in two columns."""
    from docx.enum.section import WD_ORIENT
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    sec.orientation = WD_ORIENT.LANDSCAPE
    sec.page_width, sec.page_height = B.Cm(29.7), B.Cm(21.0)
    sec.left_margin = sec.right_margin = B.Cm(1.5)       # the back – the binding margin is on the other side
    sec.top_margin = sec.bottom_margin = B.Cm(1.2)
    set_columns(sec, columns)


def set_columns(sec, n):
    """The number of text columns of a section. A new section copies the one before it – the columns too – so a
    section after the calculation must set 1 again (set_columns(sec, 1))."""
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    pr = sec._sectPr
    for old in pr.findall(qn("w:cols")):
        pr.remove(old)
    cols = OxmlElement("w:cols")
    cols.set(qn("w:num"), str(n))
    cols.set(qn("w:space"), str(int(1.0 * 567)))
    pr.append(cols)


COLS = [2]           # the text columns of the calculation – fit() may take 3 under the table of Приложение № 3б


def lines_needed(d, naslov, obekt, pomeshtenie, size, cols, short=False):
    """How many lines the calculation takes at this size – written into a scratch document and counted, each
    paragraph wrapped at the width of a column."""
    SIZE[0], SHORT[0] = size, short
    tmp = B.new_document()
    title(tmp, naslov, obekt, pomeshtenie, short=short)
    write(tmp, d, pomeshtenie)
    col_cm = (29.7 - 3.0 - 1.0 * (cols - 1)) / cols
    per_line = col_cm / (0.0185 * size)                           # characters in a column
    return sum(max(1, math.ceil(len(p.text) / per_line)) for p in tmp.paragraphs)


def fit(d, naslov, obekt, pomeshtenie, height_cm=21.0 - 2.4, sizes=(11, 10.5, 10, 9.5, 9, 8.5, 8), short=False):
    """The largest size – in 2 columns, else in 3 – at which the calculation goes in height_cm of a landscape A4
    page. Returns (size, columns, fits)."""
    for cols in (2, 3):
        for size in sizes:
            per_col = height_cm * 28.35 / (size * 1.16 + (1 if size < 11 else 2) + 0.6)
            if lines_needed(d, naslov, obekt, pomeshtenie, size, cols, short) <= cols * per_col - 3:
                SHORT[0] = False
                return size, cols, True
    SHORT[0] = False
    return sizes[-1], 3, False


def page(doc, d, naslov=None, obekt=None, pomeshtenie=None, belezhki=(), new_section=True, under_cm=None,
         zashtita=None):
    """The calculation on one page – the back of the sheet of its specific scheme (also a section of the plan).
    under_cm – it goes under the table of Приложение № 3б on the same back page, in the height left there
    (under_cm – how much of the page the table and its titles take): a continuous section, 9 pt at the least."""
    from docx.enum.section import WD_SECTION
    warnings = []
    if under_cm is not None:
        size, cols, ok = fit(d, naslov, obekt, pomeshtenie, height_cm=21.0 - 2.0 - under_cm,
                             sizes=(11, 10.5, 10, 9.5, 9), short=True)
        if not ok:
            warnings.append("разчетът не се събира под таблицата № 3б дори на 9 pt – провери гърба на листа")
        SIZE[0], SHORT[0] = size, True
        sec = doc.add_section(WD_SECTION.CONTINUOUS)
        set_columns(sec, cols)
        title(doc, naslov, obekt, pomeshtenie, short=True)
    else:
        size, cols, ok = fit(d, naslov, obekt, pomeshtenie)
        SIZE[0], SHORT[0] = size, False
        sec = doc.add_section(WD_SECTION.NEW_PAGE) if new_section else doc.sections[-1]
        back_page(sec, cols)
        title(doc, naslov, obekt, pomeshtenie)
    warnings += write(doc, d, pomeshtenie, belezhki, zashtita)
    SIZE[0], SHORT[0] = 11, False
    return warnings


def build(d, a, out):
    if not valid(d):
        bad("очаква се JSON-ът на sili.py (с \"ok\": true и \"stapki\")")
    doc = B.new_document()
    warnings = page(doc, d, a.naslov, a.obekt, a.pomeshtenie, a.belezhka, new_section=False, zashtita=a.zashtita)
    doc.save(out)
    B.report(out, letterhead=False)
    return {"output": out, "preduprezhdeniya": warnings}


def main():
    ap = argparse.ArgumentParser(description="Разчет на силите и средствата като .docx")
    ap.add_argument("vhod", help="JSON-ът на sili.py")
    ap.add_argument("--kam", help="конкретната схема (.docx), към която е разчетът – дава името Razchet_<…>.docx")
    ap.add_argument("-o", "--out", help="изходен .docx (вместо --kam)")
    ap.add_argument("--naslov", help="заглавието на конкретната схема")
    ap.add_argument("--obekt", help="обектът и адресът")
    ap.add_argument("--pomeshtenie", help="помещението, в което е пожарът")
    ap.add_argument("--belezhka", action="append", help="още бележка (може няколко пъти)")
    ap.add_argument("--zashtita", help="какво се защитава (напр. „стълбищната клетка“) – в реда за разхода за защита")
    a = ap.parse_args()
    try:
        d = json.load(open(a.vhod, encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        bad(f"не мога да прочета {a.vhod}: {e}")
    out = target(a)
    os.makedirs(os.path.dirname(os.path.abspath(out)) or ".", exist_ok=True)
    print(json.dumps(build(d, a, out), ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
