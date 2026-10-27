#!/usr/bin/env python3
"""Tests for fire-render without the network: the JSON operations, the outline and zapishi with a stand-in
obekti.py (the real register is never touched)."""
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TMP = tempfile.mkdtemp()
os.environ["DATA_DIR"] = os.path.join(TMP, "sesii")
os.environ["REPO_DIR"] = os.path.join(TMP, "repo")
FAKE = os.path.join(TMP, "obekti.py")
with open(FAKE, "w") as f:
    f.write("import json, os, sys\nargs = sys.argv[1:]\n"
            "print(json.dumps({'nov': {'id': 'OB-9999'}} if 'nov' in args else "
            "{'args': args, 'avtor': os.environ.get('FIRE_SERVICE_AVTOR')}))\n")
os.environ["OBEKTI_SCRIPT"] = FAKE
sys.path.insert(0, os.path.dirname(HERE))
import app  # noqa: E402

app.pull = lambda: None
checks = 0


def ok(cond, msg):
    global checks
    assert cond, msg
    checks += 1


data = {"sgradi": [{"etiket": "Склад", "kontur": [[0, 0], [1, 1]]}], "teren_tochki": [[1, 2], [3, 4]], "kais": {"imot": "1.2.3"}}
done = app.apply_ops(data, [
    {"op": "set", "pat": "/list/obekt", "stoynost": "Склад А"},
    {"op": "add", "pat": "/vhodove/-", "stoynost": {"x": 1, "y": 2}},
    {"op": "merge", "pat": "/sgradi/0", "stoynost": {"etazhnost": "+1"}},
    {"op": "set", "pat": "/sgradi/0/etiket", "stoynost": "Склад за мебели"},
])
ok(len(done) == 4 and data["list"]["obekt"] == "Склад А" and data["vhodove"] == [{"x": 1, "y": 2}], "set/add create")
ok(data["sgradi"][0]["etazhnost"] == "+1" and data["sgradi"][0]["etiket"] == "Склад за мебели", "merge/set")
app.apply_ops(data, [{"op": "remove", "pat": "/vhodove/0"}])
ok(data["vhodove"] == [], "remove")
for bad in ([{"op": "set", "pat": "sgradi"}], [{"op": "drop", "pat": "/x"}], [{"op": "remove", "pat": "/sgradi/9"}], []):
    try:
        app.apply_ops(data, bad)
        ok(False, f"accepted {bad}")
    except app.Problem:
        ok(True, "refused")
o = app.outline(data)
ok(o["sgradi"] == ["[0] etiket: Склад за мебели"] and "2 стойности" in o["teren_tochki"], "outline")

sid, path = app.session(None, new=True)
app.save(path, data)
ok(app.a_pokazhi({"sesiya": sid, "pat": "/sgradi/0/etiket"})["stoynost"] == "Склад за мебели", "pokazhi")
try:
    app.a_zapishi({"sesiya": sid, "obekt": "OB-0001"})
    ok(False, "zapishi before chertai")
except app.Problem as e:
    ok("chertai" in str(e), "zapishi needs a drawing")
for x in (".docx", ".dxf", "_grafichna.png"):
    open(os.path.join(path, "out", app.VID + x), "wb").close()
r = app.a_zapishi({"sesiya": sid, "obekt": "OB-0001", "klient": "Иван Петров"})
ok(r["zapisano"] and r["otgovor"]["avtor"] == "Иван Петров" and "OB-0001" in r["otgovor"]["args"], "zapishi existing")
r = app.a_zapishi({"sesiya": sid, "nov": {"ime": "Склад А", "masto": "Плевен", "adres": "ул. Х 1"}, "klient": "И П"})
ok(r["obekt"] == "OB-9999" and r["nov_obekt"], "zapishi new object")
try:
    app.session("../etc", False)
    ok(False, "path in session id")
except app.Problem:
    ok(True, "session id checked")
# the form: compact questions with the streets as options, answers recorded with their "deistvie"
app.FORMULYAR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(HERE))), "plugins", "fire-service",
                             "skills", "shemi", "references", "formulyar.json")
qd = {"ulitsi": [{"ime": "ул. „Първа“"}, {"ime": "ул. „Втора“"}, {"ime": "ул. „Първа“"}], "formulyar": {"pgi": "няма"}}
qs = {q["id"]: q for e in app.questions(qd) for q in e["vaprosi"]}
ok("pgi" not in qs and "gaz" in qs and "deistvie" not in qs["gaz"], "questions: open ones, no deistvie")
ok(qs["vhod_kola"]["opcii"] == ["от ул. „Първа“", "от ул. „Втора“", "не личи – ще кажа къде"], "vhod_kola streets")
d = app.answers(qd, {"gaz": "не", "vhod_kola": ["от ул. „Първа“"]})
ok(qd["formulyar"]["gaz"] == "не" and list(d["gaz"]) == ["не"], "answer → its deistvie only")
ok("*" in d["vhod_kola"], "street answer → the template for any choice")
for bad in ({}, {"nyama": "x"}):
    try:
        app.answers(qd, bad)
        ok(False, f"answers accepted {bad}")
    except app.Problem:
        ok(True, "answers refused")
sid2, path2 = app.session(None, new=True)
app.save(path2, {"list": {}})
r = app.a_promeni({"sesiya": sid2, "operacii": [{"op": "formulyar", "stoynost": {"gaz": "не"}}]})
ok(r["napraveno"] == [] and "gaz" in r["deistvie"] and app.load(path2)["formulyar"] == {"gaz": "не"}, "promeni formulyar")
drawn = []
real_chertai, app.a_chertai = app.a_chertai, lambda b: drawn.append(b["sesiya"]) or {"mashtab": "1:500"}
r = app.a_promeni({"sesiya": sid2, "operacii": [{"op": "set", "pat": "/list/obekt", "stoynost": "Х"}, {"op": "chertai"}]})
ok(drawn == [sid2] and r["mashtab"] == "1:500" and r["napraveno"] == ["set /list/obekt"], "promeni + chertai in one call")
app.a_chertai = real_chertai
# zapishi takes the object nachalo found (meta) and returns the links
app.meta(path2, obekt="OB-0042")
for x in (".docx", ".dxf", "_grafichna.png"):
    open(os.path.join(path2, "out", app.VID + x), "wb").close()
r = app.a_zapishi({"sesiya": sid2})
ok(r["obekt"] == "OB-0042" and "OB-0042" in r["otgovor"]["args"] and "failove" in r, "zapishi uses the found object")
ok(app.in_register({}) is None, "no point – no lookup")

# the plan: a session of its own (plan.json), the rooms of a floor, the variant's checks, zapishi of every sheet
ok(set(app.ACTIONS) == set(app.HANDLERS), "every action has a handler")
try:
    app.plan_session(sid2)
    ok(False, "a scheme session is not a plan session")
except app.Problem as e:
    ok(e.code == "NOT_FOUND", "plan session needs plan.json")
psid, ppath = app.session(None, new=True)
pod = {"pomeshtenia": [{"ime": "Склад", "plosht_m2": 40, "razmeri_m": [8, 5], "tsentar": [0, 0]},
                       {"ime": "Склад", "plosht_m2": 20, "razmeri_m": [5, 4], "tsentar": [30, 0]},
                       {"ime": "Офис", "tsentar": [28, 1]}, {"ime": ""}]}
app.jsave(ppath, "podlozhka_et1.json", pod)
app.jsave(ppath, "plan.json", {"fail": "Plan_pozharogasene_Test", "varianti": [], "danni": []})
ok(app.floors(ppath) == [1] and [r["ime"] for r in app.rooms(pod)] == ["Склад", "Склад", "Офис"], "floors and rooms")
ok(app.room_in(pod, "склад", "Офис")["plosht_m2"] == 20, "two rooms of one name – the one next to blizo")
for b, why in (({"sesiya": psid, "etazh": 2}, "no floor"), ({"sesiya": psid, "etazh": 1, "pomeshtenie": "Склад"}, "no vhod"),
               ({"sesiya": psid, "etazh": 1, "pomeshtenie": "Няма", "vhod": "Офис", "hidrant": "1", "ime": "x",
                 "ogneustoychivost": "II"}, "no room")):
    try:
        app.a_plan_variant(b)
        ok(False, f"plan_variant accepts {why}")
    except app.Problem as e:
        ok(e.code == "BAD_INPUT", f"plan_variant: {why}")
r = app.a_plan_promeni({"sesiya": psid, "operacii": [{"op": "set", "pat": "/danni", "stoynost": [["Подстъпи.", "Асфалт."]]}]})
ok(r["plan"]["danni"] == ["Подстъпи."], "plan_promeni")
try:
    app.a_plan_zapishi({"sesiya": psid})
    ok(False, "plan_zapishi before plan_sglobi")
except app.Problem as e:
    ok("plan_sglobi" in str(e), "plan_zapishi needs the built plan")
app.jsave(ppath, "situacionna.json", {"list": {}})
plan = app.jload(ppath, "plan.json")
plan["varianti"] = [{"fail": "Konkretna_shema_Sklad_1et", "konkretna": {"list": {}}}]
app.jsave(ppath, "plan.json", plan)
app.meta(ppath, obekt="OB-0042", novi_podlozhki=[1])
out = os.path.join(ppath, "out_plan")
os.makedirs(out)
for x in ("Plan_pozharogasene_Test.docx", "Konkretna_shema_Sklad_1et.docx", "Konkretna_shema_Sklad_1et.dxf",
          "Konkretna_shema_Sklad_1et_grafichna.png", "Razchet_Konkretna_shema_Sklad_1et.docx"):
    open(os.path.join(out, x), "wb").close()
calls = []
real_obekti, app.obekti = app.obekti, lambda *a, **k: calls.append(a) or {}
r = app.a_plan_zapishi({"sesiya": psid, "klient": "И П"})
app.obekti = real_obekti
vids = [c[c.index("--vid") + 1] for c in calls if c[0] == "zapishi"]
ok(vids == ["plan_za_pozharogasene", "shema_sklad_1et", "shema_podlozhka_et1"], f"plan_zapishi vids {vids}")
ok(any(f.endswith("Razchet_Konkretna_shema_Sklad_1et.docx") for f in calls[1]), "the calculation goes with its scheme")
whole = app.jload(out, "Plan_pozharogasene_Test.json")
ok(whole["situacionna"] == {"list": {}}, "the plan JSON kept in the register is whole")

# /vreme – the input is checked before vreme.py is run (no network here)
for bad, why in (({"data": "x"}, "date"), ({"data": "2026-10-26", "mesto": "--rm"}, "mesto as an option"),
                 ({"data": "2026-10-26"}, "no place"), ({"data": "2026-10-26", "stantsiya": "15528", "ot": "25;rm"}, "hour"),
                 ({"data": "2026-10-26", "stantsiya": "15528; ls"}, "station")):
    try:
        app.a_vreme(bad)
        ok(False, f"vreme accepts a bad {why}")
    except app.Problem as e:
        ok(e.code == "BAD_INPUT", f"vreme rejects a bad {why}")

print(f"OK – {checks} проверки")
