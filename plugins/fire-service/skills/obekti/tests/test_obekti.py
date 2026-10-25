#!/usr/bin/env python3
"""Тестове за obekti.py в режим „конектор“ (--store) върху измислени обекти – без мрежа.
Истинският регистър е в Google Drive зад n8n и не се пипа тук."""
import json
import os
import subprocess
import sys
import tempfile

SKILL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OBEKTI = os.path.join(SKILL, "_shared", "scripts", "obekti.py")
ENV = {k: v for k, v in os.environ.items() if not k.startswith("FIRE_SERVICE_")}
ENV["FIRE_SERVICE_NO_KEY"] = "1"
TMP = tempfile.mkdtemp()
INDEX = """id,ime,predishni_imena,naseleno_masto,adres,lat,lon,kadastar,eik,sluzhba,papka_id,papka,sazdaden,promenen,promenil,belezhka
OB-0001,Магазин А,,Примерно,ул. Липа 2,43.100000,24.100000,99999.1.10,,,F1,"OB-0001 Магазин А – ул. Липа № 2, Примерно",2026-01-01,2026-01-01,Тест,
OB-0002,Магазин А,,Примерно,ул. Бор 118,43.110000,24.120000,,,,F2,"OB-0002 Магазин А – ул. Бор № 118, Примерно",2026-01-01,2026-01-01,Тест,
OB-0003,Ново Име,Старо Име (до 2020),Примерно,бул. Дъб 20,43.120000,24.140000,,,,F3,"OB-0003 Ново Име",2026-01-01,2026-01-01,Тест,
"""
os.makedirs(os.path.join(TMP, "root"))
with open(os.path.join(TMP, "root", "obekti.csv"), "w", encoding="utf-8") as f:
    f.write(INDEX)
checks = 0


def run(*args):
    return subprocess.run([sys.executable, OBEKTI, "--json", "--store", TMP, "--avtor", "Тест", *args],
                          capture_output=True, text=True, env=ENV)


def out(*args):
    r = run(*args)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def ok(cond, msg):
    global checks
    assert cond, msg
    checks += 1


# the name alone is not enough – two objects share it
r = out("tarsi", "Магазин А")
ok(r["nameren"] is None and r["dvusmisleno"] and len(r["kandidati"]) == 2, "name only → ask which")
# the address decides, even with a typo and without the quotes
r = out("tarsi", "--ime", "Магазин А", "--adres", "ул. Липъ 2", "--masto", "Примерно")
ok(r["nameren"] and r["nameren"]["id"] == "OB-0001", "address with a typo matches")
# a third shop of the same chain elsewhere is a new object
r = out("tarsi", "--ime", "Магазин А", "--adres", "ул. Явор 5", "--masto", "Примерно")
ok(r["nameren"] is None and not r["dvusmisleno"], "same name, other address → new object")
# coordinates within 60 m, the cadastral id, the old name
ok(out("tarsi", "--lat", "43.1003", "--lon", "24.1002")["nameren"]["id"] == "OB-0001", "point")
ok(out("tarsi", "--kadastar", "99999.1.10.1")["nameren"]["id"] == "OB-0001", "building id within the parcel")
r = out("tarsi", "Старо Име")
ok(r["kandidati"][0]["id"] == "OB-0003" and "старо" in r["kandidati"][0]["savpada_po"][0], "old name")

# a duplicate is refused; a new object first asks for its folder
r = run("nov", "--ime", "Магазин А", "--masto", "Примерно", "--adres", "ул. Липа 2")
ok(r.returncode == 1 and "EXISTS" in r.stderr, "duplicate refused")
r = run("nov", "--ime", "Склад Б", "--masto", "Примерно", "--adres", "ул. Явор 5")
ok(r.returncode == 1 and "NEED_MKDIR" in r.stderr, "folder first")
r = out("nov", "--ime", "Склад Б", "--masto", "Примерно", "--adres", "ул. Явор 5", "--papka-id", "F4")
ok(r["nov"]["id"] == "OB-0004" and [s["name"] for s in r["kachi"]] == ["obekti.csv", "history.md"], "new object")

# documents: fixed names, the same content is not written twice
docs = []
for name, body in (("Situacionna_X.docx", b"d"), ("Situacionna_X.dxf", b"x"), ("Situacionna_X_grafichna.png", b"p")):
    p = os.path.join(TMP, name)
    with open(p, "wb") as f:
        f.write(body)
    docs.append(p)
r = out("zapishi", "OB-0004", "--vid", "situacionna_shema", *docs)
ok([s["name"] for s in r["kachi"]][:3] == ["situacionna_shema.docx", "situacionna_shema.dxf",
                                           "situacionna_shema_grafichna.png"], "fixed names")
r = out("zapishi", "OB-0004", "--vid", "situacionna_shema", docs[0])
ok(r["zapisani"] == [] and r["bez_promyana"] == ["situacionna_shema.docx"] and "kachi" not in r, "unchanged skipped")
ok(run("zapishi", "OB-0004", "--vid", "nyakakva", docs[0]).returncode == 1, "unknown kind refused")
r = out("zapishi", "OB-0004", "--vid", "operativna_kartichka", docs[0])
ok(r["bez_promyana"] == ["situacionna_shema.docx"], "оперативна картичка = ситуационна схема")
r = out("pokazhi", "OB-0004")
ok(list(r["dokumenti"]) == ["situacionna_shema"] and len(r["dokumenti"]["situacionna_shema"]["failove"]) == 3, "one document")

# photos: the same picture once
os.makedirs(os.path.join(TMP, "F4", "snimki"))
r = out("snimka", "OB-0004", docs[2], "--opisanie", "главен вход", "--snimki-id", "F4/snimki", "--data", "2026-01-02")
ok(r["zapisani"] == ["2026-01-02_glaven_vhod.png"], "photo name")
ok(out("snimka", "OB-0004", docs[2], "--snimki-id", "F4/snimki")["dubliki"], "duplicate photo")

# a new name keeps the old one for searching; changes go to the history
r = out("preimenuvai", "OB-0004", "--ime", "Склад В", "--ot", "2026")
ok(r["obekt"]["predishni_imena"].startswith("Склад Б (до 2026)") and r["kachi"][0]["action"] == "rename", "rename")
ok(out("tarsi", "Склад Б")["kandidati"][0]["id"] == "OB-0004", "found by the old name")
out("promeni", "OB-0004", "eik=123456789")
h = out("istoriya", "OB-0004")["istoriya"]
ok(h.count("\n- ") == 5 and "eik: – → 123456789" in h and "Тест" in h, "history lines")

print(f"OK – {checks} проверки")
