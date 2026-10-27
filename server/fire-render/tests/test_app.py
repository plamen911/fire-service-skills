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
