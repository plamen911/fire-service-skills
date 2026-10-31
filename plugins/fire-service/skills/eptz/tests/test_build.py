#!/usr/bin/env python3
"""Smoke tests for build_eptz_docx.py and build_smetka.py. Run from the skill folder:
    python3 tests/test_build.py
"""
import glob
import json
import os
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)

# the tests never touch the network: no key, and an invented staff list instead of the real one
os.environ["FIRE_SERVICE_NO_KEY"] = "1"
os.environ["FIRE_SERVICE_STAFF_CSV"] = os.path.abspath(os.path.join(SKILL, "..", "..", "..", "..", "tests", "fixtures", "staff.csv"))
sys.path.insert(0, os.path.join(SKILL, "scripts"))

from docx import Document  # noqa: E402
import openpyxl  # noqa: E402
from build_smetka import amount_words, apply_defaults, compute, words  # noqa: E402

FIXTURE = os.path.join(HERE, "fixtures", "sample_report.md")  # synthetic, not a real case
failures = []


def check(cond, msg):
    print(("  ok  " if cond else "  FAIL ") + msg)
    if not cond:
        failures.append(msg)


def doc_text(path):
    d = Document(path)
    parts = [p.text for p in d.paragraphs]
    for t in d.tables:
        for row in t.rows:
            parts += [c.text for c in row.cells]
    for s in d.sections:
        parts += [p.text for p in s.footer.paragraphs]
    return "\n".join(parts)


def build(content, meta, out, final=False):
    cmd = [sys.executable, os.path.join(SKILL, "scripts", "build_eptz_docx.py"),
           "--content", content, "--meta", meta, "--out", out]
    if final:
        cmd.append("--final")
    r = subprocess.run(cmd, check=True, capture_output=True, text=True)
    check("DOC_CHECK" not in r.stderr, "the finished ЕПТЗ keeps the common rules (no bold, letterhead, „–“, „№ “)"
          + (": " + r.stderr.strip()[:200] if "DOC_CHECK" in r.stderr else ""))


def test_eptz():
    print("build_eptz_docx.py")
    tmp = tempfile.mkdtemp()
    content = FIXTURE
    meta = {
        "zm_no": "123/2025", "zm_opis": "Първо РУ – Плевен", "dp_no": "1234/2025",
        "rp_grad": "Плевен", "prokuratura": "ОП – Плевен",
        "postanovlenie_no": "1234р-56789", "postanovlenie_date": "03.09.2026 г.",
        "naznachil": "разследващ полицай Тест Тестов", "expert_name": "Иван Дъбов", "expert_rank": "инспектор", "izgotvil_position": "инспектор IV ст.",
        "expert_position": "инспектор IV ст. в група ОЦ към РДПБЗН – Плевен",
        "izgotvil_date": "21.09.2026 г.", "copies": ["деловодство", "Първо РУ – Плевен"],
    }
    mp = os.path.join(tmp, "meta.json")
    json.dump(meta, open(mp, "w", encoding="utf-8"), ensure_ascii=False)

    draft, final = os.path.join(tmp, "draft.docx"), os.path.join(tmp, "final.docx")
    build(content, mp, draft)
    build(content, mp, final, final=True)
    t_d, t_f = doc_text(draft), doc_text(final)

    for h in ["I. Основание", "II. Представен", "III. Обстоятелства", "IV. Поставени", "V. Пожаро-техническо изследване",
              "VI. Общи изводи"]:
        check(h in t_f, f"section '{h}' present")
    check("Изследване на въпрос № 3" in t_f and "Отговор на трети въпрос" in t_f, "all 3 research parts and answers present")
    check(t_f.index("Изследване на въпрос № 3") < t_f.index("VI. Общи изводи") < t_f.index("Отговор на първи въпрос"),
          "the research comes before the general conclusions")
    check("1. Отговор на първи въпрос" in t_f and "3. Отговор на трети въпрос" in t_f, "the answers in VI are numbered")
    check(t_f.count("Вещото лице запазва правото си") == 1, "the reservation of the expert is there once")
    check("ЧЕРНОВА" not in t_d, "no ЧЕРНОВА notice without --final")
    check("ЧЕРНОВА" not in t_f, "no ЧЕРНОВА notice with --final")
    check(t_d == t_f, "--final changes nothing")
    check("ОП – Плевен" in t_f, "prokuratura override used")
    check("по описа на РП -" not in t_f, "no hardcoded РП when prokuratura is set")
    check("**" not in t_f, "no markdown bold left")
    check("[Източник" not in t_f, "citation markers stripped")
    check("1234/2025" in t_f and "123/2025" in t_f, "ДП/ЗМ numbers filled")
    check("Екз. № 2 – Първо РУ – Плевен" in t_f, "copies filled")

    # without prokuratura → РП – Плевен
    meta.pop("prokuratura")
    json.dump(meta, open(mp, "w", encoding="utf-8"), ensure_ascii=False)
    out = os.path.join(tmp, "rp.docx")
    build(content, mp, out, final=True)
    check("по описа на РП – Плевен" in doc_text(out), "default РП – {rp_grad}")
    nc = os.path.join(tmp, "no.md")
    open(nc, "w", encoding="utf-8").write(open(FIXTURE, encoding="utf-8").read().replace(
        "## I. Обстоятелства по делото.\n", "## I. Обстоятелства по делото.\n\nКонтейнерът е на ул. „Климент Охридски“ №4.\n", 1))
    build(nc, mp, out)
    t_no = doc_text(out)
    check("Охридски“ № 4." in t_no and "№4" not in t_no, "№ followed by a space")
    check("—" not in t_no and " - " not in t_no, "only en dash as a dash")
    check_literatura(tmp, mp)

    # a court case (гражданско дело) instead of ЗМ/ДП with a постановление
    sad = {k: v for k, v in meta.items() if k not in ("zm_no", "zm_opis", "dp_no", "rp_grad", "postanovlenie_no",
                                                      "postanovlenie_date", "naznachil")}
    sad.update({"delo_vid": "гражданско дело", "delo_no": "1111/2026", "sad": "Районен съд – Плевен",
                "sastav": "III граждански състав",
                "akt": "определение от открито съдебно заседание на 01.10.2026 г. (протокол рег. № 22/02.10.2026 г.)",
                "pismo": "писмо изх. № 333/05.10.2026 г. на Районен съд – Плевен", "vazlozheno_na": "РСПБЗН – Плевен",
                "predstaven_material": ["Препис от искова молба"]})
    sp = os.path.join(tmp, "sad.json")
    json.dump(sad, open(sp, "w", encoding="utf-8"), ensure_ascii=False)
    out = os.path.join(tmp, "sad.docx")
    build(content, sp, out, final=True)
    t_s = doc_text(out)
    check("Определение от открито съдебно заседание на 01.10.2026 г. (протокол рег. № 22/02.10.2026 г.) по гражданско дело "
          "№ 1111/2026 г. по описа на Районен съд – Плевен, III граждански състав" in t_s, "court case: основание")
    check("възложено на РСПБЗН – Плевен, и писмо изх. № 333/05.10.2026 г." in t_s, "court case: възложено на + писмо")
    check("Материали по гражданско дело № 1111/2026 г. по описа на Районен съд – Плевен, както следва:" in t_s,
          "court case: материали")
    check("ЗМ №" not in t_s and "постановление" not in t_s.lower() and "[...]" not in t_s and "досъдебното" not in t_s, "court case: no ЗМ/ДП/постановление")
    check("назначена с определение от открито съдебно заседание" in t_s and "г.." not in t_s, "court case: title sentence")
    check("по ГПК" in t_s and "НПК" not in t_s, "civil case: ГПК instead of НПК")


def literatura(path):
    """The numbered paragraphs after „Използвана литература“."""
    d = Document(path)
    return [p.text for p in d.paragraphs if p._p.find(".//" + p._p.tag.replace("}p", "}numPr")) is not None
            and p.style.name.replace(" ", "").lower() in ("bodytextindent3",)]


def check_literatura(tmp, mp):
    print("позоваванията [[…]] и литературата")
    src = open(FIXTURE, encoding="utf-8").read()
    text = src.replace("### Изследване на въпрос № 1:\n",
                       "### Изследване на въпрос № 1:\n\nПламната температура на дизеловото гориво е 52 °C "
                       "[[icsc:1561]], а алуминиевите сплави се топят при 600 ÷ 660 °C "
                       "[[chochev: прил. № 7, с. 223]]. Бензинът [[icsc:1400]] и пак дизелът [[icsc:1561]].\n", 1)
    check(text != src, "fixture has an answer to put the citations in")
    md = os.path.join(tmp, "lit.md")
    open(md, "w", encoding="utf-8").write(text)
    out = os.path.join(tmp, "lit.docx")
    build(md, mp, out)
    t = doc_text(out)
    check("52 °C (ICSC 1561)" in t, "[[icsc:1561]] → (ICSC 1561)")
    check("(Чочев, 2003, прил. № 7)" in t and "с. 223" not in t, "[[chochev: …]] → (Чочев, 2003, прил. № 7), no page in the text")
    check("[[" not in t, "no marker left")
    lit = literatura(out)
    check(len(lit) == 5, f"literature: 2 mandatory + 3 cited, each once (got {len(lit)})")
    check(lit and "Симеонов" in lit[0] and "Методическо ръководство" in lit[1], "mandatory sources first")
    check(len(lit) == 5 and "ICSC 1561" in lit[2] and "Чочев" in lit[3] and "ICSC 1400" in lit[4],
          "cited sources in the order of the first citation")
    check(lit and all(x.endswith(";") for x in lit[:-1]) and lit[-1].endswith("."), "„;“ between, „.“ at the end")
    check(not any("Справочник за пожарната опасност" in x for x in lit), "an uncited book is not listed")

    # a requirement of Наредба № 8121з-647 is cited by its article in the text and listed
    open(md, "w", encoding="utf-8").write(text.replace("### Изследване на въпрос № 2:\n",
        "### Изследване на въпрос № 2:\n\nДървата са били на по-малко от 0,5 m от печката "
        "[[naredba-8121z-647: чл. 40, ал. 1, т. 10]].\n", 1))
    build(md, mp, out)
    t = doc_text(out)
    check("(Наредба № 8121з-647/2014, чл. 40, ал. 1, т. 10)" in t, "[[naredba-8121z-647: …]] → the article in the text")
    check(any("8121з-647 от 1 октомври 2014" in x for x in literatura(out)), "the ordinance in the literature")

    # an unknown source stops the build instead of listing a book nobody cited
    open(md, "w", encoding="utf-8").write(text.replace("[[icsc:1400]]", "[[babrauskaz]]"))
    r = subprocess.run([sys.executable, os.path.join(SKILL, "scripts", "build_eptz_docx.py"),
                        "--content", md, "--meta", mp, "--out", out], capture_output=True, text=True)
    check(r.returncode != 0 and "babrauskas" in (r.stderr + r.stdout), "unknown key stops the build and suggests the right one")

    # a temperature without a marker is reported (a warning, the document is still built)
    open(md, "w", encoding="utf-8").write(text.replace("### Изследване на въпрос № 2:\n",
                                                       "### Изследване на въпрос № 2:\n\nГорещият газ е около 777 °C.\n", 1))
    r = subprocess.run([sys.executable, os.path.join(SKILL, "scripts", "build_eptz_docx.py"),
                        "--content", md, "--meta", mp, "--out", out], capture_output=True, text=True)
    check(r.returncode == 0 and "777 °C" in r.stdout and "⚠" in r.stdout, "a number without a source is warned about")

    # a number that the cited place does not give stops the build
    open(md, "w", encoding="utf-8").write(text.replace("52 °C", "62 °C", 1))
    r = subprocess.run([sys.executable, os.path.join(SKILL, "scripts", "build_eptz_docx.py"),
                        "--content", md, "--meta", mp, "--out", out], capture_output=True, text=True)
    check(r.returncode != 0 and "62" in (r.stderr + r.stdout), "a wrong number next to [[icsc:1561]] stops the build")

    # every [[…]] in the reference files gives a number its source really has
    sys.path.insert(0, os.path.join(SKILL, "_shared", "scripts"))
    import svoistva  # noqa: E402
    for f in sorted(glob.glob(os.path.join(SKILL, "references", "technical_reference", "*.md"))):
        t = open(f, encoding="utf-8").read()
        bad = svoistva.proveri_chisla(t)
        check(not bad, f"{os.path.basename(f)}: its markers match their sources" + (f" {bad}" if bad else ""))
        try:
            svoistva.citiraj(t)
            check(True, f"{os.path.basename(f)}: every marker is a known source")
        except svoistva.Problem as e:
            check(False, f"{os.path.basename(f)}: {e}")

    # a per-case source (ИЛБ) from meta.json
    meta = json.load(open(mp, encoding="utf-8"))
    meta["dop_iztochnitsi"] = {"ilb-razreditel": {"kratko": "ИЛБ на „Разредител 650“, 2024",
                                                  "palno": "Информационен лист за безопасност на „Разредител 650“, версия 3.0 от 12.01.2024 г.;"}}
    mp2 = os.path.join(tmp, "meta2.json")
    json.dump(meta, open(mp2, "w", encoding="utf-8"), ensure_ascii=False)
    open(md, "w", encoding="utf-8").write(text.replace("[[icsc:1400]]", "[[ilb-razreditel: раздел 9]]"))
    build(md, mp2, out)
    check("(ИЛБ на „Разредител 650“, 2024, раздел 9)" in doc_text(out), "per-case source rendered")
    check(any("Разредител 650" in x for x in literatura(out)), "per-case source listed")


def test_smetka():
    print("build_smetka.py")
    check(words(21) == "двадесет и едно", "21 in words")
    check(words(125) == "сто двадесет и пет", "125 in words")
    check(words(1005) == "хиляда и пет", "1005 in words")
    check(words(2021) == "две хиляди двадесет и едно", "2021 in words")
    check(amount_words(97.61) == "Деветдесет и седем евро и шестдесет и един евроцента.", "97.61 EUR in words")
    check(amount_words(1.01) == "Едно евро и един евроцент.", "1.01 EUR in words")
    d = {"hours": 4, "a4_bw": 6, "ogled": False}
    check(compute(d) == 97.61, f"total for 4 h + 6 sheets = 97.61 (got {compute(d)})")
    dd = apply_defaults({"pages": 6, "copies": 2})
    check(dd["hours"] == 4 and dd["a4_bw"] == 6, "pages 6, copies 2 → 4 h, 6 sheets (client's copy only)")
    check(apply_defaults({"pages": 6, "hours": 5})["hours"] == 5, "explicit hours win")
    check(apply_defaults({"pages": 6, "hours": None})["hours"] == 4, "hours: null → taken from the pages")
    check(apply_defaults({"pages": "6", "copies": "2"})["a4_bw"] == 6, "numbers given as text are accepted")
    for bad, why in (({}, "neither pages nor hours"), ({"hours": 0}, "zero hours"), ({"hours": "много"}, "hours is not a number")):
        try:
            apply_defaults(bad)
            check(False, f"{why} → refused")
        except SystemExit as e:
            check(str(e).startswith("BAD_INPUT"), f"{why} → BAD_INPUT, no сметка for 0 hours")
    import openpyxl
    import build_smetka
    ws = openpyxl.load_workbook(build_smetka.TEMPLATE).active
    formula = str(ws["E11"].value).lstrip("=").replace("%", "/100")
    check(re.fullmatch(r"[0-9.*/ ]+", formula) and abs(eval(formula) - build_smetka.RATE) < 1e-9,  # noqa: S307
          "the hourly rate in the script equals the formula in the template (E11)")
    tmp = tempfile.mkdtemp()
    data = dict(d, naznachil="разследващ полицай Тест", pri="Първо РУ – Плевен",
                delo_no="1234/2025", po_opisa_na="РП – Плевен", izvarshena_ot="Иван Дъбов", expert_title="инспектор", izgotvil_short="И. Дъбов",
                expert_position="инспектор IV ст. в група ОЦ към РДПБЗН – Плевен",
                date="21.09.2026")
    dp = os.path.join(tmp, "s.json")
    json.dump(data, open(dp, "w", encoding="utf-8"), ensure_ascii=False)
    out = os.path.join(tmp, "s.xlsx")
    subprocess.run([sys.executable, os.path.join(SKILL, "scripts", "build_smetka.py"), dp, "-o", out],
                   check=True, capture_output=True)
    ws = openpyxl.load_workbook(out).active
    check("1234/2025" in ws["A7"].value and "Първо РУ – Плевен" in ws["A7"].value, "A7 filled")
    check(ws["D11"].value == 4 and ws["D16"].value == 6 and ws["D19"].value == 0, "quantities filled")
    check("Деветдесет и седем евро" in ws["A30"].value, "total in words written")
    yellow = [c.coordinate for r in ws.iter_rows() for c in r
              if c.fill is not None and c.fill.fill_type and str(c.fill.fgColor.rgb).upper() == "FFFFFF00"]
    check(not yellow, f"yellow fill cleared {yellow}")
    check("извършена от инспектор Иван Дъбов – инспектор IV ст. в група ОЦ" in ws["A7"].value,
          "expert title and position from the profile")
    check(ws["A43"].value == "/ инспектор И. Дъбов /", "„Изготвил“")
    check(ws["D44"].value == "КОМИСАР" and ws["D45"].value.strip() == "Стоян Кестенов", "director from the staff list")
    wr = openpyxl.load_workbook(out, rich_text=True).active
    head = [str(x) for x in "".join(str(p) for p in wr["A2"].value).split("\n")]
    check(head == ["МИНИСТЕРСТВО НА ВЪТРЕШНИТЕ РАБОТИ",
                   "ГЛАВНА ДИРЕКЦИЯ „ПОЖАРНА БЕЗОПАСНОСТ И ЗАЩИТА НА НАСЕЛЕНИЕТО”",
                   "РЕГИОНАЛНА ДИРЕКЦИЯ „ПОЖАРНА БЕЗОПАСНОСТ И ЗАЩИТА НА НАСЕЛЕНИЕТО” – ПЛЕВЕН"],
          "the header is text in A2 as in the original form, three lines")
    check(not wr._images, "no header picture")
    check(build_smetka.natural_height(ws) <= 842 - 20, f"one A4 page at 100 % too – without „fit to page“ "
          f"(Google Sheets, Numbers): {build_smetka.natural_height(ws):.0f} pt of 842")
    check(ws.sheet_properties.pageSetUpPr.fitToPage and ws.page_setup.fitToHeight == 1, "„fit to one page“ kept")
    bold = {c.coordinate for r in wr.iter_rows() for c in r if c.font is not None and c.font.b}
    check({"B9", "B10", "B27", "F27"} <= bold, "bold kept as in the original form (the сметка is the exception)")
    iban = [p for p in wr["A31"].value if "BG96" in str(p)]
    check(iban and iban[0].font.b, "IBAN in bold as in the original form")

    other = dict(data, izvarshena_ot="Георги Малинов", expert_title="старши пожарникар",
                 expert_position="старши пожарникар в РСПБЗН – Левски", izgotvil_short="Г. Малинов")
    json.dump(other, open(dp, "w", encoding="utf-8"), ensure_ascii=False)
    subprocess.run([sys.executable, os.path.join(SKILL, "scripts", "build_smetka.py"), dp, "-o", out],
                   check=True, capture_output=True)
    ws = openpyxl.load_workbook(out).active
    check("извършена от старши пожарникар Георги Малинов – старши пожарникар в РСПБЗН – Левски"
          in ws["A7"].value, "another expert's title and position in A7")
    check("РДПБЗН – Плевен" not in ws["A7"].value and "инспектор IV" not in ws["A7"].value,
          "no default position left for another expert")
    check(ws["A43"].value == "/ старши пожарникар Г. Малинов /", "another expert under „Изготвил“")


def test_nachalo():
    print("nachalo.py – една команда в началото")
    r = subprocess.run([sys.executable, os.path.join(SKILL, "scripts", "nachalo.py"), "--data", "2026-07-11",
                        "--mesto", "Луковит"], capture_output=True, text=True, cwd=tempfile.gettempdir())
    check(r.returncode == 0, "runs from any folder")
    d = json.loads(r.stdout)
    check(d["papka"] == SKILL, "gives the skill folder")
    check(d["profil"] and d["profil"].get("ime") if isinstance(d["profil"], dict) else "ГРЕШКА" in d["profil"],
          "profile from the staff list (or its error)")
    check(all(k in d for k in ("proizshestviya", "obraztsi", "etalon")), "a missing part never stops the rest")
    skill = open(os.path.join(SKILL, "SKILL.md"), encoding="utf-8").read()
    check("scripts/nachalo.py --data" in skill, "SKILL.md starts with nachalo.py")


def test_bez_klyuch():
    """A colleague with the connector only (no personal key, no test switch): the Чочев check is
    skipped, the build does not stop with NO_KEY. Found by evals/eptz – api_config sys.exit()s and
    `except Exception` does not catch SystemExit."""
    code = (
        "import sys; sys.path.insert(0, 'scripts'); sys.path.insert(0, '_shared/scripts')\n"
        "import api_config; api_config._key_skill_files = lambda: []\n"
        "api_config.load()['key'] = ''\n"
        "import svoistva\n"
        "print('OK' if svoistva._chochev_tekst() is None else 'TEXT')\n"
    )
    env = {k: v for k, v in os.environ.items() if k not in ("FIRE_SERVICE_NO_KEY", "FIRE_SERVICE_KEY")}
    env["TMPDIR"] = tempfile.mkdtemp()   # no cached Чочев from an earlier run
    r = subprocess.run([sys.executable, "-c", code], cwd=SKILL, env=env, capture_output=True, text=True)
    check(r.returncode == 0 and r.stdout.strip() == "OK", "no key: the Чочев check is skipped, no NO_KEY exit"
          + ("" if r.returncode == 0 else " – " + (r.stderr.strip().splitlines() or [""])[-1]))


if __name__ == "__main__":
    test_bez_klyuch()
    test_nachalo()
    test_eptz()
    test_smetka()
    print("\nALL PASS" if not failures else f"\n{len(failures)} FAILED")
    sys.exit(1 if failures else 0)
