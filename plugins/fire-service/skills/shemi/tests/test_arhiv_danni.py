#!/usr/bin/env python3
"""scripts/arhiv_danni.py: данните от характеристиката на стар план. Run: python3 tests/test_arhiv_danni.py"""
import os
import sys

SKILL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(SKILL, "scripts"))
from arhiv_danni import extract, keywords, variants  # noqa: E402

errors = []


def ok(cond, what):
    if not cond:
        errors.append(what)


# измислен обект – текстът е като в старите характеристики (получер, кирилско „І“, „ел. табло“ в изречението)
TEXT = ("**ХАРАКТЕРИСТИКА НА ОБЕКТА**\n\nЧиталище “Примерно” се помещава в 3-етажна сграда от ІІ-ра степен на "
        "пожароустойчивост с обща застроена площ 900 кв.м. Главното ел. табло се намира в стая до служебния вход. "
        "Има 6 бр. Вътрешни пожарни кранове, водоем – 10 куб.м. и 4 бр. ПХ на водопровод Ф 100 мм. Сградата е "
        "оборудвана с АПИИ. Обектът не е газифициран.")
d, why = extract(TEXT)
ok(d.get("etazhi") == 3, "3-етажна → 3")
ok(d.get("ogneustoychivost") == "II", "„ІІ-ра степен на пожароустойчивост“ (кирилско І) → II")
ok(d.get("el_tablo", "").startswith("Главното ел. табло се намира"), "ел. таблото – цялото изречение, не до „ел.“")
ok(d.get("vpk") == 6 and d.get("hidranti") == 4 and d.get("vodoprovod_mm") == 100 and d.get("vodoem_m3") == 10,
   "ВПК, ПХ, водопровод, водоем")
ok(d.get("apii") is True and d.get("gaz") == "не", "АПИИ; „не е газифициран“ → газ не")
ok("sprinkler" not in d and "vodna_zavesa" not in d, "което не е казано – липсва")
ok(extract("")[0] == {}, "празен текст – нищо")
ok(keywords("Театър „Примерно Име“") == ["Име"], "търси се по последната дума от името в кавичките")

RAZ = ("Разчет на силите и средствата за гасене на пожар в Читалище “Примерно” – сцена\n\n*V<sub>л</sub> = 1 м/мин*\n\n"
       "*Секторна форма на развитие*\n\n*Приемам, че гори цялата сцена*\n\n*Гасене по периметър*\n\n"
       "*J<sub>н</sub><sup>г</sup> = 0,2 л/с.м<sup>2</sup>*\n\n"
       "\\(Q = 2\\text{.}5\\text{.}(\\text{20},5 + \\text{10},5 - 2\\text{.}5)\\text{.}0,2\\)\n\n"
       "Разчет на силите и средствата за гасене на пожар в Читалище “Примерно” – зала\n\n*Гасене по фронт*\n")
v = variants(RAZ)
ok([x["ime"] for x in v] == ["сцена", "зала"], "вариантите – по помещението след „–“")
ok(v[0].get("vl_m_min") == 1 and v[0].get("i_l_s_m2") == 0.2 and v[0].get("forma") == "sektor"
   and v[0].get("ataka") == "perimetar" and (v[0].get("a_m"), v[0].get("b_m"), v[0].get("h_m")) == (20.5, 10.5, 5),
   "Vл, Iн, форма, атака и размерите от формулата")
ok(v[0].get("priemam") == "Приемам, че гори цялата сцена" and v[1].get("ataka") == "front", "какво се приема; по фронт")

for e in errors:
    print("  FAIL", e)
print("FAILURES" if errors else "OK – arhiv_danni")
sys.exit(1 if errors else 0)
