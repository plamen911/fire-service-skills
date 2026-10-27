#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
razchet_docx.py — РАЗЧЕТЪТ НА СИЛИТЕ И СРЕДСТВАТА като .docx на бланката на РДПБЗН – Плевен: изходните
данни, стъпките по Методиката (Приложение № 5 към Указанията Iз-2749/2010) с номера на формулата, резултатът,
бележките и подписът. Към всяка конкретна схема (чл. 7, ал. 4) – свой разчет, по чл. 7, ал. 6 приложен към плана.

    python3 scripts/sili.py tvardi … > sili.json
    python3 scripts/razchet_docx.py sili.json --kam "/mnt/user-data/outputs/Konkretna_shema_Garderob_2et.docx" \
        --naslov "Конкретна схема № 2 – пожар в гардероба, 2 етаж" --obekt "ЦПЛР – …, гр. Плевен, ул. … № …" \
        --izgotvil "Инспектор в РСПБЗН – Плевен" --ime "Име Фамилия" --data 27.10.2026

--kam дава името на файла: Razchet_<името на конкретната схема>.docx в същата папка (иначе -o).
Отпечатва JSON {"output", "preduprezhdeniya"}.
"""
import argparse
import json
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


def write(doc, d, pomeshtenie=None, belezhki=()):
    """The body of the calculation – the inputs, the steps, the result, the notes and the source – into doc
    (its own .docx, or a section of the plan, plan-pozharogasene). Returns the warnings."""
    warnings = []
    B.para(doc, "1. Изходни данни", indent=False)
    used = dict(d.get("vhodni") or {})
    rows = []
    for key, label in VHODNI:
        if key in used:
            rows.append([label, dec(used.pop(key))])
    rows += [[k, dec(v)] for k, v in used.items()]      # anything sili.py adds later
    if pomeshtenie:
        rows.insert(0, ["Помещение", pomeshtenie])
    rows.insert(0, ["Вид на горимите вещества", str(d.get("vid") or "")])
    B.grid(doc, ["Величина", "Стойност"], rows, [6.5, 10.0], align=B.LEFT)
    B.blank(doc)

    B.para(doc, "2. Изчисление по Методиката", indent=False)
    steps = [[str(i), s.get("ime", ""), s.get("formula", ""), B.typo(s.get("izraz", "")),
              num(s.get("stoinost", "")), s.get("merna", "")] for i, s in enumerate(d["stapki"], 1)]
    B.grid(doc, ["№", "Величина", "Формула", "Израз", "Стойност", "Мярка"], steps,
           [0.8, 4.6, 2.2, 4.9, 2.1, 1.9], align=B.LEFT)
    B.blank(doc)

    B.para(doc, "3. Резултат", indent=False)
    res = d.get("rezultat") or {}
    rows = [[label, num(res[k]), unit] for k, label, unit in REZULTAT if res.get(k) not in (None, 0, "")]
    if res.get("struinik"):
        rows.insert(next((i for i, r in enumerate(rows) if r[0] == "Струйници общо"), len(rows)),
                    ["Вид на струйниците", f"„{res['struinik']}“", ""])
    B.grid(doc, ["Необходими сили и средства", "Стойност", "Мярка"], rows, [10.0, 3.5, 3.0], align=B.LEFT)
    if not rows:
        warnings.append("разчетът няма резултат")
    B.blank(doc)

    notes = list(d.get("belezhki") or []) + list(belezhki or [])
    n = 4
    if notes:
        B.para(doc, f"{n}. Бележки", indent=False)
        for x in notes:
            B.para(doc, "– " + re.sub(r"(?<!ред )(?<![\d.])(\d+)\.(\d+)(?![.\d])", r"\1,\2", B.typo(x)))
        B.blank(doc)
        n += 1
    src = d.get("iztochnik")
    B.para(doc, f"{n}. Източник", indent=False)
    B.para(doc, B.typo(src if isinstance(src, str) else
                       "Методика за изчисляване на необходимите сили и средства за гасене на пожари – Приложение № 5 "
                       "към чл. 7, ал. 6 от Указанията за разработване на планове за пожарогасене, рег. № Iз-2749/18.11.2010 г."))
    return warnings


def title(doc, naslov=None, obekt=None):
    B.title(doc, "РАЗЧЕТ", ["на силите и средствата за гасене на пожар"] +
            ([f"към {naslov[0].lower() + naslov[1:]}"] if naslov else []) + ([obekt] if obekt else []))


def build(d, a, out):
    if not valid(d):
        bad("очаква се JSON-ът на sili.py (с \"ok\": true и \"stapki\")")
    doc = B.new_document()
    B.letterhead(doc, a.zveno)
    title(doc, a.naslov, a.obekt)
    warnings = write(doc, d, a.pomeshtenie, a.belezhka)
    B.blank(doc, 2)
    B.signature(doc, a.data, a.izgotvil, a.ime)
    if not a.ime:
        warnings.append("няма име на изготвилия – оставено е място")
    doc.save(out)
    B.report(out)
    return {"output": out, "preduprezhdeniya": warnings}


def main():
    ap = argparse.ArgumentParser(description="Разчет на силите и средствата като .docx")
    ap.add_argument("vhod", help="JSON-ът на sili.py")
    ap.add_argument("--kam", help="конкретната схема (.docx), към която е разчетът – дава името Razchet_<…>.docx")
    ap.add_argument("-o", "--out", help="изходен .docx (вместо --kam)")
    ap.add_argument("--naslov", help="заглавието на конкретната схема")
    ap.add_argument("--obekt", help="обектът и адресът")
    ap.add_argument("--pomeshtenie", help="помещението, в което е пожарът")
    ap.add_argument("--zveno", help="ред под бланката, напр. РСПБЗН – Плевен")
    ap.add_argument("--izgotvil", action="append", default=[], help="длъжността на изготвилия (по ред)")
    ap.add_argument("--ime", help="името на изготвилия")
    ap.add_argument("--data", help="дата, напр. 27.10.2026")
    ap.add_argument("--belezhka", action="append", help="още бележка (може няколко пъти)")
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
