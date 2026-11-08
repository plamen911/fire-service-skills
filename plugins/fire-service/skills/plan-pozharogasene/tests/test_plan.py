#!/usr/bin/env python3
"""build_plan.py on a made-up object: the plan and the sheets on their own, the gaps it reports."""
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
SKILLS = os.path.dirname(SKILL)
FIX = os.path.join(SKILLS, "shemi", "tests", "fixtures", "situacionna.json")


def run(args, cwd=None):
    p = subprocess.run([sys.executable, *args], capture_output=True, text=True, cwd=cwd)
    assert p.returncode == 0, p.stderr[-1500:]
    return json.loads(p.stdout)


def uslovni_test():
    """Conditional floors from a parcel's building: the rooms a concrete scheme needs, marked as conditional."""
    sys.path.insert(0, os.path.join(SKILL, "scripts"))
    sys.path.insert(0, os.path.join(os.path.dirname(SKILL), "shemi", "scripts"))
    import plan_avto as A
    import uslovni_etazhi as U
    s = {"kais": {"imot": "1.2.3", "x0": 10, "y0": 20},
         "ulitsi": [{"ime": "ул. А", "tochki": [[0, -10], [60, -10]]}],
         "sgradi": [{"kais_id": "1.2.3.1", "etazhnost": "+3", "kontur": [[0, 0], [40, 0], [40, 16], [0, 16]]},
                    {"kais_id": "1.2.3.2", "etazhnost": "+1", "kontur": [[0, 30], [10, 30], [10, 40], [0, 40]]}]}
    pods, b = U.make(s)
    assert b["kais_id"] == "1.2.3.1" and sorted(pods) == [1, 2, 3], pods.keys()
    p = pods[3]
    names = [r["ime"] for r in p["pomeshtenia"]]
    assert p["_uslovna"] and {"Фоайе", "Стълбище", "Коридор"} <= set(names), names
    foyer = next(r for r in p["pomeshtenia"] if r["ime"] == "Фоайе")
    assert foyer["tsentar"][1] < 8 and any(o["vanshen"] for o in foyer["otvori"]), "the foyer faces the street"
    assert all(not o["vanshen"] for r in p["pomeshtenia"] if r["ime"].startswith("Помещение") for o in r["otvori"])
    assert p["_kais"] == {"x0": 10, "y0": 20}
    far, near = A.pick(p, "kray"), A.pick(p, "do_stalbishte")
    stair = next(r for r in p["pomeshtenia"] if r["ime"] == "Стълбище")["tsentar"]
    d = lambda r: abs(r["tsentar"][0] - stair[0]) + abs(r["tsentar"][1] - stair[1])   # noqa: E731
    assert d(far) > d(near), (far["ime"], near["ime"])
    hall, _ = U.make(s, "1.2.3.1", 1, (1,))
    assert [r["ime"] for r in hall[1]["pomeshtenia"]] == ["Зала", "Фоайе"]
    v = A.default_variants(pods, "1", "6.3", "мебели")
    assert [x["etazh"] for x in v] == [3, 1] and A.vid_of("НУИ „Х“", "")[3] == "Ф4.1"
    assert A.latin("НУИ „Панайот“") == "nui_panayot"
    print("  ok  uslovni etazhi")


def plan_danni_test():
    """plan_danni.py with the scripts replaced: all sources at once, no second call for what the register has."""
    sys.path.insert(0, os.path.join(SKILL, "scripts"))
    import argparse
    import plan_danni as P
    calls = []

    def fake(script, args, cwd=None, timeout=240):
        name = os.path.basename(script)
        calls.append((name, args))
        if name == "obekti.py" and "tarsi" in args:
            return {"nameren": None, "kandidati": []}, None
        if name == "arhiv_danni.py":
            return {"namereno": True, "varianti": [{"ime": "сутерен"}]}, None
        if name == "kais.py":
            json.dump({"sgradi": []}, open(os.path.join(cwd, "shema.json"), "w"))
            return {"imot": {"id": "1.2.3"}, "sgradi": []}, None
        if name == "dopalni.py":
            return {"prieto": ["x"], "ne_e_popalneno": []}, None
        return {"marshrut": {"razstoyanie_km": 1}}, None
    P.call = fake
    with tempfile.TemporaryDirectory() as d:
        a = argparse.Namespace(ime="Обект", id="", adres="", masto="Плевен", kadastar="1.2.3", lat=None, lon=None,
                               izgotvil="", dir=d)
        r = P.collect(a)
        names = [c[0] for c in calls]
        assert r["marshrut"] and r["prieto"] == ["x"] and r["arhiv"]["namereno"], r
        assert "fetch_incidents.py" not in names and "kais.py" in names, names
        assert [c for c in calls if c[0] == "arhiv_danni.py"][0][1] == ["Обект"], "only the name"
        assert os.path.isfile(os.path.join(d, "plan_danni.json"))
    print("  ok  plan_danni – one call")


def main():
    from docx import Document
    with tempfile.TemporaryDirectory() as d:
        s = run([os.path.join(SKILLS, "sili-i-sredstva", "scripts", "sili.py"), "tvardi", "--forma", "pravoagalnik",
                 "--fp", "40", "--a", "8", "--b", "5", "--vl-red", "1", "--i-red", "6.3", "--ataka", "front1",
                 "--struinik", "В", "--q-pa", "40"])
        sit = json.load(open(FIX, encoding="utf-8"))
        k = json.loads(json.dumps(sit))
        k["list"]["naslov"] = "Конкретна схема за гасене на пожар в склад на 1 ет."
        k["tablitsa_3b"] = {"redove": [{"kategoriya": "Ф5.2", "ogneustoychivost": "III", "natovarvane_vid": "дърво",
                                        "vl_m_min": "1,5", "gasitelni_neobhodimi": "вода", "zashtita": "ВДА"}]}
        plan = {"fail": "Plan_pozharogasene_Test", "godina": 2026, "obekt": "Склад „Тест“", "adres": "с. Тестово",
                "utvarzhdava": {"lines": ["ДИРЕКТОР НА РДПБЗН – ПЛЕВЕН"], "name": "Име Фамилия"},
                "danni": [["Разположение на сградите.", "Една сграда."], ["Подстъпи.", "Асфалт."]],
                "situacionna": sit,
                "varianti": [{"ime": "пожар в склада", "fail": "Konkretna_shema_Sklad_1et", "konkretna": k, "sili": s,
                              "pomeshtenie": "Склад – 8 × 5 m",
                              "reshenie": [["Място на пожара.", "Складът."], ["Схема на подаване.", "I ПА – пред входа."]]}],
                "izgotvil": {"lines": ["инспектор"], "name": "Тест Тестов", "data": "27.10.2026"}}
        src = os.path.join(d, "plan.json")
        json.dump(plan, open(src, "w", encoding="utf-8"), ensure_ascii=False)
        r = run([os.path.join(SKILL, "scripts", "build_plan.py"), src, "-d", d])
        names = {os.path.basename(f) for f in r["failove"]}
        assert {"Situacionna_shema_Test.docx", "Konkretna_shema_Sklad_1et.docx", "Konkretna_shema_Sklad_1et.dxf",
                "Razchet_Konkretna_shema_Sklad_1et.docx"} <= names, names
        assert os.path.basename(r["plan"]) == "Plan_pozharogasene_Test.docx"
        doc = Document(r["plan"])
        text = "\n".join(p.text for p in doc.paragraphs)
        cells = "\n".join(c.text for t in doc.tables for row in t.rows for c in row.cells)
        assert "Брой струйници (общо)" in text and "Nстр" in text, "the written calculation"
        for want in ("П Л А Н", "1. ДАННИ ЗА ОБЕКТА", "ВАРИАНТ № 1", "По разчета (Приложение № 5)", "Приложение № 3б",
                     "Приложение № 4"):
            assert want in text, want
        for want in ("Ф5.2", "Произшествие или занятие"):
            assert want in cells, (want, [l for l in cells.splitlines() if "Площ" in l or "(1" in l][:10])
        assert any("т. 7" in w for w in r["preduprezhdeniya"]), r["preduprezhdeniya"]    # „вероятни опасности“ missing
        assert len(doc.sections) >= 8, len(doc.sections)
        from docx.oxml.ns import qn
        cols = [(s._sectPr.find(qn("w:cols")).get(qn("w:num")) if s._sectPr.find(qn("w:cols")) is not None else "1")
                for s in doc.sections]
        assert cols.count("2") == 1 and cols[-1] == "1", cols      # only the calculation is in two columns
        print("  ok  plan, the sheets on their own and the gaps")
    plan_danni_test()
    uslovni_test()
    print("OK plan-pozharogasene")


if __name__ == "__main__":
    main()
