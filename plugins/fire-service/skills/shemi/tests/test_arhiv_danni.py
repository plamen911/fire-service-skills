#!/usr/bin/env python3
"""scripts/arhiv_danni.py: данните от характеристиката на стар план. Run: python3 tests/test_arhiv_danni.py"""
import os
import sys

SKILL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(SKILL, "scripts"))
from arhiv_danni import extract, keywords  # noqa: E402

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

for e in errors:
    print("  FAIL", e)
print("FAILURES" if errors else "OK – arhiv_danni")
sys.exit(1 if errors else 0)
