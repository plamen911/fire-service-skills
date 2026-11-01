#!/usr/bin/env python3
"""scripts/dopalni.py: попълва непитаното, не пипа даденото, не гадае входа. Run: python3 tests/test_dopalni.py"""
import copy
import json
import os
import sys

SKILL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(SKILL, "scripts"))
from dopalni import dopalni  # noqa: E402

errors = []


def ok(cond, what):
    if not cond:
        errors.append(what)


# измислен театър: правоъгълен имот 40 × 30, главна сграда 30 × 20 (3 ет., 1900 m² по „КАИС“), улица по южния ръб
base = {
    "kais": {"x0": 428000, "y0": 4808800},
    "list": {"obekt": "Театър „Примерен“"},
    "teren_tochki": [[10, 10], [50, 10], [50, 40], [10, 40]],
    "sgradi": [{"kontur": [[15, 15], [45, 15], [45, 35], [15, 35]], "etiket": "Сграда за култура и изкуство",
                "kais_id": "00000.1.1.1", "etazhnost": "+3"}],
    "ulitsi": [{"kontur": [[0, 0], [60, 0], [60, 10], [0, 10]], "ime": "ул. „Примерна“"}],
    "ortofoto_tochki": [{"n": 1, "x": 10, "y": 40}, {"n": 2, "x": 30, "y": 10}],
    "formulyar": {"gaz": "не", "pgi": "няма", "vhod_kola": ["от ул. „Примерна“"]},
    "arhiv": False,                                   # без стария план – тестът не ходи в Drive
}
kais = {"imot": {"sobstvenost": "Общинска публична"},
        "sgradi": [{"id": "00000.1.1.1", "predn": "Сграда за култура и изкуство", "etazhi": 3, "zastroena_m2": 1900}]}

d = copy.deepcopy(base)
r = dopalni(d, kais)
s = d["sgradi"][0]
ok(s.get("kategoriya") == "Ф2.1", "театър → Ф2.1")
ok(s.get("ogneustoychivost") == "II", "Ф2.1, 3 ет., 1900 m² → II ст. (III допуска до 1000 m²)")
ok(d.get("obekt_gps", "").count(",") == 1, "obekt_gps от центъра на имота")
ok(len(d.get("prohodi") or []) == 1 and d["prohodi"][0]["y"] in (10, 10.0), "имотът опира в улицата → вход на ръба ѝ")
ok(any(o.get("etiket") == "Ел." for o in d.get("obekti") or []), "главното ел. табло")
ok(d["list"].get("sobstvenik") == "общинска публична собственост (КАИС)", "собственикът – видът по КАИС")
row = d["tablitsa"]["redove"][0]
ok(row.get("natovarvane_kg_m2") == "≈ 17" and row.get("gazove_vid") == "няма" and row.get("pgi_vid") == "няма",
   "таблицата – натоварване, газ и ПГИ по формуляра")
ok(not r["ne_e_popalneno"], "нищо не остава за питане")

# второ пускане – нищо ново, а „прието“ остава цялото
n_proh = len(d["prohodi"])
r2 = dopalni(d, kais)
ok(len(d["prohodi"]) == n_proh and r2["prieto"] == r["prieto"], "идемпотентно")

# даденото не се пипа
d = copy.deepcopy(base)
d["sgradi"][0].update({"kategoriya": "Ф2.2", "ogneustoychivost": "I"})
d["list"]["sobstvenik"] = "Община Примерно"
dopalni(d, kais)
ok(d["sgradi"][0]["kategoriya"] == "Ф2.2" and d["sgradi"][0]["ogneustoychivost"] == "I", "категорията не се пипа")
ok(d["list"]["sobstvenik"] == "Община Примерно", "собственикът не се пипа")

# улицата е през съседен имот и номер няма – не се гадае
d = copy.deepcopy(base)
d["ulitsi"] = [{"kontur": [[0, -40], [60, -40], [60, -30], [0, -30]], "ime": "ул. „Примерна“"}]
r = dopalni(d, kais)
ok(not d.get("prohodi") and any("portali" in x for x in r["ne_e_popalneno"]), "далечна улица без номер → питай portali")

# с номер на точката – там
d["formulyar"]["portali"] = ["точка 1"]
r = dopalni(d, kais)
ok(d.get("prohodi") and (d["prohodi"][0]["x"], d["prohodi"][0]["y"]) == (10, 40), "вход при точка 1")

# Ф5 – по дейността, не се гадае
d = copy.deepcopy(base)
d["list"]["obekt"] = "Цех за мебели"
d["sgradi"][0]["etiket"] = "Промишлена сграда"
k5 = copy.deepcopy(kais)
k5["sgradi"][0]["predn"] = "Промишлена сграда"
r = dopalni(d, k5)
ok(not d["sgradi"][0].get("kategoriya") and r["ne_e_popalneno"], "Ф5 → по normativna-uredba, без гадаене")

# старият план попълва липсващото без въпрос, с годината си; отговорът на потребителя не се пипа
d = copy.deepcopy(base)
d.pop("arhiv")
d["formulyar"] = {"vhod_kola": ["от ул. „Примерна“"], "pgi": "спринклерна – вода"}
d["vodoprovod"] = [{"tochki": [[0, 5], [60, 5]], "diametar": "70/80", "natisk": "3–5"}]
d["arhiv_danni"] = {"namereno": True, "godina": 2007, "iztochnik": "по план от 2007 г.", "star": True,
                    "danni": {"etazhi": 4, "ogneustoychivost": "I", "el_tablo": "Главното ел. табло е до портиера.",
                              "vodoprovod_mm": 125, "hidranti": 7, "vpk": 15, "vodoem_m3": 5.0, "vodna_zavesa": True,
                              "apii": True}}
r = dopalni(d, kais)
txt = " ".join(r["prieto"])
ok(d["sgradi"][0]["ogneustoychivost"] == "I", "огнеустойчивостта – от плана, не минимумът по табл. 4")
ok(d["formulyar"].get("etazhi") == "сутерен или тавански етаж" and "4 по план от 2007 г." in txt, "4 етажа по плана срещу 3 в КАИС")
ok(d["formulyar"].get("el_tablo", "").startswith("Главното ел. табло"), "ел. таблото – от плана, без въпрос")
ok(d["vodoprovod"][0]["diametar"] == 125 and "Ø 125 mm, 7 ПХ" in txt and "70/80" not in txt, "водопроводът – Ø 125 от плана")
ok(d["formulyar"]["pgi"] == "спринклерна – вода" and "спринклер няма" in txt, "отговорът за ПГИ остава, разминаването се казва")
ok("да се провери на място" in txt, "план отпреди 2010 г. – ориентир")
ok(not r["ne_e_popalneno"], "нищо за питане")

for e in errors:
    print("  FAIL", e)
print("FAILURES" if errors else "OK – dopalni")
sys.exit(1 if errors else 0)
