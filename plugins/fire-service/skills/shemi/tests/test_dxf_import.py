#!/usr/bin/env python3
"""dxf_import.py – редакцията в .dxf обратно в JSON-а. Пуска се от папката на скила:
    python3 tests/test_dxf_import.py
Обектът е измисленият от fixtures/situacionna.json, завъртян на 30°, за да се провери и обратното завъртане.
"""
import copy
import json
import math
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "scripts"))

import ezdxf  # noqa: E402
from ezdxf.addons import importer  # noqa: E402
import dxf_import  # noqa: E402

failures = []


def ok(cond, msg):
    print(("  ok  " if cond else "  FAIL ") + msg)
    if not cond:
        failures.append(msg)


def group(msp, vid, i):
    return [e for e in msp if dxf_import.tag(e) == (vid, i)]


def edit(base, out, strip=False):
    """Като човек в AutoCAD: мести хидрант и надпис, сменя текст, трие площ, добавя надпис и ограда, пипа сграда."""
    doc = ezdxf.readfile(base)
    msp = doc.modelspace()
    for e in group(msp, "vodoiztochnitsi", 0):
        e.translate(4, 3, 0)                          # 5 m
    for e in group(msp, "tekst", 0):
        if e.dxftype() == "TEXT":
            e.dxf.text = "главен вход"
    for e in group(msp, "bez_parkirane", 0):
        msp.delete_entity(e)
    pl = next(e for e in group(msp, "sgradi", 0) if e.dxftype() == "LWPOLYLINE")
    p = list(pl.get_points("xy"))
    p[0] = (p[0][0] + 2, p[0][1])
    pl.set_points(p, format="xy")
    t = msp.add_text("КПП", height=1.5, dxfattribs={"layer": "TEKST"})
    t.set_placement((20, 20))
    msp.add_lwpolyline([(0, 0), (10, 0), (10, 8)], dxfattribs={"layer": "OGRADA"})
    if strip:                                         # най-лошият редактор: без XDATA, нови handles
        for e in msp:
            if e.has_xdata(dxf_import.APPID):
                e.discard_xdata(dxf_import.APPID)
        new = ezdxf.new("R2010")
        im = importer.Importer(doc, new)
        im.import_modelspace()
        im.import_tables()
        im.finalize()
        new.saveas(out)
    else:
        doc.saveas(out)


def main():
    print("dxf_import.py – редакция в .dxf → JSON")
    d0 = json.load(open(os.path.join(HERE, "fixtures", "situacionna.json"), encoding="utf-8"))
    d0["zavartane"] = 30
    d0["sgradi"][0]["kais_id"] = "00000.0.0.1"
    d0["tekst"] = [{"x": 30, "y": 30, "tekst": "вход"}]
    tmp = tempfile.mkdtemp()
    base = dxf_import.baseline(d0, tmp)
    bdoc = ezdxf.readfile(base)
    ok(dxf_import.new_format(bdoc), "новият .dxf е с XDATA и FS_HIDRANT")
    ok(any(e.dxftype() == "INSERT" and e.dxf.name == "FS_HIDRANT" for e in bdoc.modelspace()), "хидрантът е блок")

    d, r = dxf_import.run(d0, base, base)
    ok(r["prieto"] and r["promeni"] == 0, "непипнат .dxf – без промени")

    results = []
    for strip in (False, True):
        ed = os.path.join(tmp, f"edit_{strip}.dxf")
        edit(base, ed, strip)
        d, r = dxf_import.run(d0, base, ed)
        results.append(d)
        w = "без XDATA" if strip else "с XDATA"
        h0, h1 = d0["vodoiztochnitsi"][0], d["vodoiztochnitsi"][0]
        ok(abs(math.dist((h0["x"], h0["y"]), (h1["x"], h1["y"])) - 5) < 0.05, f"{w}: хидрантът – с 5 m (и завъртян назад)")
        ok(d["tekst"][0]["tekst"] == "главен вход", f"{w}: сменен надпис")
        ok(len(d["bez_parkirane"]) == 0, f"{w}: изтрита площ без паркиране")
        ok(d["sgradi"][0]["kontur"] == d0["sgradi"][0]["kontur"] if d0["sgradi"][0].get("kontur") else
           d["sgradi"][0] == d0["sgradi"][0], f"{w}: сградата от КАИС не е пипната")
        ok(any("КАИС" in x for x in r["otkhvarleni"]), f"{w}: отказът е в отчета")
        ok(any(t["tekst"] == "КПП" for t in d["tekst"]), f"{w}: новият надпис")
        ok(len(d.get("ogradi") or []) == 1, f"{w}: линията на OGRADA е ограда")
    ok(results[0] == results[1], "с и без XDATA – един и същ резултат")

    # стар .dxf (без XDATA и без блока) не се чете
    old = ezdxf.new("R2010")
    old.modelspace().add_circle((60, 2.5), 0.5, dxfattribs={"layer": "VODA"})
    op = os.path.join(tmp, "old.dxf")
    old.saveas(op)
    d, r = dxf_import.run(d0, base, op)
    ok(d is None and not r["prieto"], "стар формат – не се приема")

    # почти всичко изтрито – не се приема
    doc = ezdxf.readfile(base)
    msp = doc.modelspace()
    for e in [e for e in msp if dxf_import.tag(e) and dxf_import.tag(e)[0] != "sgradi"]:
        msp.delete_entity(e)
    doc.header.custom_vars.append(dxf_import.APPID, "2")
    ep = os.path.join(tmp, "empty.dxf")
    doc.saveas(ep)
    d, r = dxf_import.run(copy.deepcopy(d0), base, ep)
    ok(d is None and not r["prieto"], "изтрити над 30 % – не се приема")

    print("FAILURES: " + "; ".join(failures) if failures else "ALL OK")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
