#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
dxf_import.py — редакцията на ситуационна схема в .dxf (AutoCAD, LibreCAD, онлайн редактор) обратно в JSON-а ѝ,
за да се изградят наново .docx, .png и .dxf (situacionna.py) – без да се чертае отначало.

    python3 scripts/dxf_import.py situacionna_shema.json redaktiran.dxf -o nov.json [--baza bazov.dxf]

situacionna_shema.json – входът на схемата (в регистъра на обектите – до .dxf-а); redaktiran.dxf – .dxf-ът след
редакцията; --baza – .dxf-ът, както го е записал плъгинът (по подразбиране се чертае наново от JSON-а – съвпада 1:1).

Какво се пренася (обектите се разпознават по XDATA "FIRESVC" от dxf_export.py; ако редакторът я е изтрил – по
непипнатата геометрия и после по най-близкия обект на същия слой и от същия вид):
  - преместени водоизточници, надписи, обекти („Ел.“), площи без паркиране, тревни площи – с тях тръгват площта без
    паркиране около хидранта и краят на разстоянието при него; нова трасе на водопровода и разстоянията;
  - сменен текст на надпис, на водоизточник (атрибутът ETIKET) и на обект;
  - изтрити обекти;
  - нови: надпис (TEXT/MTEXT) → "tekst"; линия – по слоя, на който е начертана: OGRADA → "ogradi", ULITSI →
    "ulitsi_rab", VODA → "vodoprovod", затворена на TREVNI → "trevni", на BEZ_PARKIRANE → "bez_parkirane",
    на SGRADI → "sgradi" (не от КАИС).
Какво не се пренася (и се казва в отчета): контурите на сградите от КАИС (КАИС е с предимство), улиците, имотът и
реките (идват от КАИС и OpenStreetMap), антетката (от "list"), завъртането на надписите, линия на друг слой.

Предпазители: .dxf от стария формат (преди 2.108.0 – без XDATA и без блока FS_HIDRANT) не се чете – хидрантите му
са кръгове и биха изглеждали изтрити; ако изглеждат изтрити над 30 % от обектите, редакцията не се приема (чужд или
сбъркан файл). Тогава "prieto": false и JSON-ът не се записва.

Отпечатва отчета (JSON): "prieto", "promeni" (брой), "belezhka" (един ред за историята на обекта) и списъците
"premesteni", "promeneni_tekstove", "iztriti", "dobaveni", "otkhvarleni", "nepreneseni".
Грешки (stderr, код ≠ 0): NO_EZDXF, BAD_INPUT: …, NOT_ACCEPTED: … (тогава отчетът е на stdout).
"""
import argparse
import copy
import json
import math
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import shema  # noqa: E402
import dxf_export  # noqa: E402

APPID = dxf_export.APPID
EPS = 0.05                     # m – по-малко е „не е местено“
NEAR_M = 30.0                  # m – до толкова се търси преместен обект без XDATA
LINKED_M = 5.0                 # m – площта без паркиране на хидранта (центърът ѝ до толкова от него)
MAX_DELETED = 0.30             # над толкова „изтрити“ – редакцията не се приема
SHEET_LAYERS = ("LIST", "SEVER")
NAMES = {"sgradi": "сграда", "tekst": "надпис", "vodoiztochnitsi": "водоизточник", "razstoyaniya": "разстояние",
         "vodoprovod": "водопровод", "obekti": "обект", "bez_parkirane": "площ без паркиране", "trevni": "тревна площ"}
POINT_LIKE = ("tekst", "vodoiztochnitsi", "obekti", "bez_parkirane")


def bad(code, msg):
    print(f"{code}: {msg}", file=sys.stderr)
    sys.exit(2)


# ---------- the geometry of one DXF entity ----------
def pts(e):
    t = e.dxftype()
    try:
        if t == "LINE":
            return [tuple(e.dxf.start)[:2], tuple(e.dxf.end)[:2]]
        if t == "LWPOLYLINE":
            return [tuple(p[:2]) for p in e.get_points("xy")]
        if t == "POLYLINE":
            return [tuple(v.dxf.location)[:2] for v in e.vertices]
        if t in ("CIRCLE", "ARC"):
            c = e.dxf.center
            return [(c.x, c.y)]
        if t in ("TEXT", "ATTRIB"):
            p = e.dxf.align_point if e.dxf.get("halign", 0) or e.dxf.get("valign", 0) else e.dxf.insert
            return [tuple(p)[:2]]
        if t in ("MTEXT", "INSERT"):
            return [tuple(e.dxf.insert)[:2]]
    except Exception:          # noqa: BLE001 – an entity without the attribute
        pass
    return []


def txt(e):
    t = e.dxftype()
    if t in ("TEXT", "ATTRIB"):
        return e.dxf.text
    if t == "MTEXT":
        return e.plain_text()
    if t == "INSERT":
        return "|".join(a.dxf.text for a in e.attribs)
    return None


def sig(e):
    """The signature of an entity – the same if it was not touched (layer, type, rounded geometry, text)."""
    r = lambda p: (round(p[0], 2), round(p[1], 2))  # noqa: E731
    ps = [r(p) for p in pts(e)]
    if e.dxftype() == "LINE":
        ps = sorted(ps)
    return (e.dxftype(), e.dxf.layer.upper(), tuple(ps), txt(e))


def centroid(ents):
    allp = [p for e in ents for p in pts(e)]
    if not allp:
        return None
    return (sum(p[0] for p in allp) / len(allp), sum(p[1] for p in allp) / len(allp))


def tag(e):
    try:
        if e.has_xdata(APPID):
            x = e.get_xdata(APPID)
            return (str(x[0].value), int(x[1].value))
    except Exception:          # noqa: BLE001 – broken XDATA from a foreign editor
        pass
    return None


def new_format(doc):
    """Written by dxf_export.py 2.108.0 or later: the header variable, any XDATA or the block FS_HIDRANT."""
    if any(k == APPID for k, _ in doc.header.custom_vars):
        return True
    if "FS_HIDRANT" in doc.blocks:
        return True
    return any(tag(e) for e in doc.modelspace())


def baseline(d0, folder):
    """The .dxf as the plugin writes it for d0 – the same steps as situacionna.build, without the .docx."""
    d = copy.deepcopy(d0)
    for k in ("fon", "podlozhka"):
        d.pop(k, None)
    if isinstance(d.get("list"), dict) and not str(d["list"].get("fail") or "").strip():
        d["list"]["fail"] = "baza.dxf"
    out = os.path.join(folder, "baza.dxf")
    shema.render(d, os.path.join(folder, "baza.png"), out_dxf=out)
    if not os.path.isfile(out):
        bad("NO_EZDXF", "pip install ezdxf")
    return out


def run(d0, base_dxf, edit_dxf):
    import ezdxf
    d = copy.deepcopy(d0)
    try:
        edoc = ezdxf.readfile(edit_dxf)
    except Exception as ex:    # noqa: BLE001
        bad("BAD_INPUT", f"{edit_dxf} не се чете като DXF ({ex})")
    rep = {"prieto": True, "promeni": 0, "belezhka": "", "razpoznati_po": {"xdata": 0, "nepipnati": 0, "blizost": 0},
           "premesteni": [], "promeneni_tekstove": [], "iztriti": [], "dobaveni": [], "otkhvarleni": [],
           "nepreneseni": []}
    if not new_format(edoc):
        rep["prieto"] = False
        rep["belezhka"] = ("файлът е от стария формат (преди 2.108.0) – изгради схемата наново и редактирай новия .dxf")
        return None, rep
    base = ezdxf.readfile(base_dxf).modelspace()
    edit = edoc.modelspace()

    groups = {}                                       # (key, index) → the entities of the base
    for e in base:
        t = tag(e)
        if t:
            groups.setdefault(t, []).append(e)
    owner = {e.dxf.handle: t for t, es in groups.items() for e in es}
    base_sig = {}
    for e in base:
        base_sig.setdefault(sig(e), []).append(e)

    # 1) the XDATA, 2) the untouched geometry
    found, rest, used = {}, [], set()
    for e in edit:
        t = tag(e)
        if t and t in groups:
            found.setdefault(t, []).append(e)
            rep["razpoznati_po"]["xdata"] += 1
            continue
        cand = [b for b in base_sig.get(sig(e), []) if b.dxf.handle not in used]
        if cand:
            b = cand[0]
            used.add(b.dxf.handle)
            if b.dxf.handle in owner:
                found.setdefault(owner[b.dxf.handle], []).append(e)
                rep["razpoznati_po"]["nepipnati"] += 1
            continue                                  # untouched and without meaning (a street, the frame …)
        rest.append(e)

    # 3) the parts still missing – the nearest entity of the same type on the same layer
    for key, bents in groups.items():
        have = [(e.dxftype(), e.dxf.layer.upper()) for e in found.get(key, [])]
        want = []
        for b in bents:
            tl = (b.dxftype(), b.dxf.layer.upper())
            if tl in have:
                have.remove(tl)
            else:
                want.append((tl, b))
        if not want:
            continue
        pick = []
        for tl, b0 in want:
            c0 = centroid([b0]) or centroid(bents)
            cs = [e for e in rest if (e.dxftype(), e.dxf.layer.upper()) == tl and e not in pick]
            if not cs or c0 is None:
                continue

            def score(e, c0=c0, b0=b0):
                s_ = math.dist(centroid([e]) or c0, c0)
                return s_ - 50 if txt(b0) and txt(e) == txt(b0) else s_   # the same text – almost surely it
            e = min(cs, key=score)
            if score(e) < NEAR_M:
                pick.append(e)
        if pick and (key in found or len(pick) >= max(1, len(want) // 2)):
            found.setdefault(key, []).extend(pick)
            for e in pick:
                rest.remove(e)
            rep["razpoznati_po"]["blizost"] += len(pick)

    # the drawing is turned ("zavartane") – a shift on the drawing → a shift in the JSON
    o_ = shema.v_teren(d0, 0, 0)

    def J(dx, dy):
        p = shema.v_teren(d0, dx, dy)
        return p[0] - o_[0], p[1] - o_[1]

    def T(p):
        return shema.v_teren(d0, p[0], p[1])

    def label(vid, i):
        el = (d0.get(vid) or [None] * (i + 1))[i] if i < len(d0.get(vid) or []) else None
        nm = (el.get("etiket") or el.get("tekst") or "") if isinstance(el, dict) else ""
        return f"{NAMES.get(vid, vid)} № {i + 1}" + (f" „{nm}“" if nm else "")

    removed, moved = [], set()
    order = sorted(groups, key=lambda k: (k[0] == "vodoiztochnitsi", k))   # the hydrants last – they pull others
    for key in order:
        vid, i = key
        if i >= len(d.get(vid) or []):
            continue
        el, ime = d[vid][i], label(vid, i)
        kais = vid == "sgradi" and bool(el.get("kais_id"))
        a, b = groups[key], found.get(key)
        if not b:
            if kais:
                rep["otkhvarleni"].append(f"{ime}: изтрита в .dxf – сградата е от КАИС, остава")
            else:
                removed.append(key)
                rep["iztriti"].append(ime)
            continue
        ca, cb = centroid(a), centroid(b)
        ta = [txt(e) for e in a if txt(e)]
        tb = [txt(e) for e in b if txt(e)]
        if kais:
            ga = sorted(p for e in a if e.dxftype() == "LWPOLYLINE" for p in pts(e))
            gb = sorted(p for e in b if e.dxftype() == "LWPOLYLINE" for p in pts(e))
            if len(ga) != len(gb) or any(math.dist(p, q) > EPS for p, q in zip(ga, gb)):
                rep["otkhvarleni"].append(f"{ime}: контурът е променен – сградата е от КАИС (КАИС е с предимство), "
                                          f"остава")
            continue
        if ta != tb and tb and vid in ("tekst", "vodoiztochnitsi", "obekti"):
            new = "\n".join(t for t in tb if t is not None)
            el["tekst" if vid == "tekst" else "etiket"] = new
            rep["promeneni_tekstove"].append(f"{ime} → „{new}“")
        if not (ca and cb and math.dist(ca, cb) > EPS):
            continue
        dx, dy = J(cb[0] - ca[0], cb[1] - ca[1])
        moved.add(key)
        m = round(math.hypot(cb[0] - ca[0], cb[1] - ca[1]), 1)
        if vid in POINT_LIKE:
            if "x" not in el:
                rep["nepreneseni"].append(f"{ime}: даден е с lat/lon – преместването не се пренася")
                continue
            hx, hy = el["x"], el["y"]
            el["x"], el["y"] = round(hx + dx, 2), round(hy + dy, 2)
            extra = ""
            if vid == "vodoiztochnitsi":
                if el.get("voda_id"):
                    extra = f" (точката в регистъра на водоизточниците – {el['voda_id']} – не е пипана)"
                for zi, z in enumerate(d0.get("bez_parkirane") or []):        # its no-parking area goes with it
                    if ("bez_parkirane", zi) in moved or ("bez_parkirane", zi) in removed:
                        continue
                    if math.dist((z["x"] + z["w"] / 2, z["y"] + z["h"] / 2), (hx, hy)) < LINKED_M:
                        d["bez_parkirane"][zi]["x"] = round(z["x"] + dx, 2)
                        d["bez_parkirane"][zi]["y"] = round(z["y"] + dy, 2)
                        moved.add(("bez_parkirane", zi))
                        rep["premesteni"].append(f"площ без паркиране № {zi + 1}: заедно с хидранта")
                for ri, r in enumerate(d0.get("razstoyaniya") or []):         # … and the end of a distance at it
                    if ("razstoyaniya", ri) in moved:
                        continue
                    for end_ in ("ot", "do"):
                        if math.dist(r[end_], (hx, hy)) < 1.0:
                            d["razstoyaniya"][ri][end_] = [round(r[end_][0] + dx, 2), round(r[end_][1] + dy, 2)]
                            rep["premesteni"].append(f"разстояние № {ri + 1}: краят при хидранта")
                rep["nepreneseni"].append(f"{ime}: водопроводът до него не се пренасочва – провери го")
            rep["premesteni"].append(f"{ime}: с {m} m{extra}")
        elif vid in ("vodoprovod", "razstoyaniya"):
            pl = next((e for e in b if e.dxftype() in ("LWPOLYLINE", "LINE")), None)
            new_pts = [[round(x, 2), round(y, 2)] for x, y in map(T, pts(pl))] if pl is not None else []
            if vid == "vodoprovod" and len(new_pts) > 1:
                el["tochki"] = new_pts
            elif vid == "razstoyaniya" and len(new_pts) == 2:
                el["ot"], el["do"] = new_pts
            rep["premesteni"].append(f"{ime}: нова трасе")
        elif vid == "trevni":
            el["kontur"] = [[round(p[0] + dx, 2), round(p[1] + dy, 2)] for p in el["kontur"]]
            rep["premesteni"].append(f"{ime}: цялата площ, с {m} m")

    # 4) the new entities, by the layer they are drawn on
    for e in rest:
        t, lay = e.dxftype(), e.dxf.layer.upper()
        if lay in SHEET_LAYERS:                       # the sheet (frame, title block) comes from "list"
            continue
        if t in ("TEXT", "MTEXT") and (txt(e) or "").strip():
            p = T(pts(e)[0])
            d.setdefault("tekst", []).append({"x": round(p[0], 2), "y": round(p[1], 2), "tekst": txt(e).strip(),
                                              "kray": "sreda"})
            rep["dobaveni"].append(f"надпис „{txt(e).strip()}“")
        elif t in ("LINE", "LWPOLYLINE", "POLYLINE"):
            closed = t in ("LWPOLYLINE", "POLYLINE") and e.closed
            P_ = [[round(x, 2), round(y, 2)] for x, y in map(T, pts(e))]
            if lay in ("OGRADA", "OGRADA_DRUGA"):
                d.setdefault("ogradi", []).append({"tochki": P_, "zatvorena": closed})
                rep["dobaveni"].append(f"ограда ({len(P_)} точки)")
            elif lay == "ULITSI":
                d.setdefault("ulitsi_rab", []).append(P_)
                rep["dobaveni"].append(f"ръб на улица ({len(P_)} точки)")
            elif lay == "VODA":
                d.setdefault("vodoprovod", []).append({"tochki": P_, "vid": "skluchena"})
                rep["dobaveni"].append(f"водопровод ({len(P_)} точки) – провери диаметъра и налягането")
            elif lay == "TREVNI" and closed:
                d.setdefault("trevni", []).append({"kontur": P_})
                rep["dobaveni"].append("тревна площ")
            elif lay == "BEZ_PARKIRANE" and closed:
                xs, ys = [p[0] for p in P_], [p[1] for p in P_]
                d.setdefault("bez_parkirane", []).append({"x": min(xs), "y": min(ys), "w": round(max(xs) - min(xs), 2),
                                                          "h": round(max(ys) - min(ys), 2)})
                rep["dobaveni"].append("площ без паркиране")
            elif lay == "SGRADI" and closed:
                d.setdefault("sgradi", []).append({"kontur": P_, "etiket": "", "sasedna": True})
                rep["dobaveni"].append("сграда (не е от КАИС – допиши надписа)")
            else:
                rep["nepreneseni"].append(f"линия на слой {e.dxf.layer} – начертай я на слоя на вида (OGRADA, ULITSI, "
                                          f"VODA, TREVNI, BEZ_PARKIRANE, SGRADI)")
        elif t not in ("ATTRIB", "HATCH", "DIMENSION"):
            rep["nepreneseni"].append(f"нов обект {t} на слой {e.dxf.layer}")

    # 5) the base entities without meaning that changed (streets, parcel, rivers) – drawn from the data
    gone = {}
    for e in base:
        lay = e.dxf.layer.upper()
        if e.dxf.handle not in used and e.dxf.handle not in owner and lay not in SHEET_LAYERS:
            gone[lay] = gone.get(lay, 0) + 1
    for lay, n in sorted(gone.items()):
        rep["nepreneseni"].append(f"слой {lay}: {n} обекта са променени или изтрити – тази част идва от КАИС / "
                                  f"OpenStreetMap и не се пренася")

    for vid, i in sorted(removed, key=lambda k: -k[1]):
        del d[vid][i]

    rep["promeni"] = sum(len(rep[k]) for k in ("premesteni", "promeneni_tekstove", "iztriti", "dobaveni"))
    if groups and len(removed) > MAX_DELETED * len(groups):
        rep["prieto"] = False
        rep["belezhka"] = (f"изглеждат изтрити {len(removed)} от {len(groups)} обекта – вероятно е чужд или сбъркан "
                           f"файл; редакцията не е приета")
        return None, rep
    parts = []
    for k, w in (("premesteni", "преместени"), ("promeneni_tekstove", "сменени надписи"), ("iztriti", "изтрити"),
                 ("dobaveni", "добавени")):
        if rep[k]:
            parts.append(f"{w} {len(rep[k])}")
    if rep["otkhvarleni"]:
        parts.append(f"отхвърлени {len(rep['otkhvarleni'])} (КАИС)")
    rep["belezhka"] = "редакция в .dxf: " + (", ".join(parts) if parts else "без промени")
    return d, rep


def main():
    ap = argparse.ArgumentParser(description="редактиран .dxf на ситуационна схема → нов JSON")
    ap.add_argument("json", help="JSON-ът на схемата (situacionna_shema.json)")
    ap.add_argument("dxf", help="редактираният .dxf")
    ap.add_argument("-o", "--out", required=True, help="новият JSON")
    ap.add_argument("--baza", help=".dxf-ът, както го е записал плъгинът (иначе се чертае наново от JSON-а)")
    a = ap.parse_args()
    if not dxf_export.available():
        bad("NO_EZDXF", "pip install ezdxf")
    try:
        d0 = json.load(open(a.json, encoding="utf-8"))
    except (OSError, ValueError) as ex:
        bad("BAD_INPUT", f"{a.json}: {ex}")
    base = a.baza or baseline(d0, tempfile.mkdtemp(prefix="dxf_baza_"))
    d, rep = run(d0, base, a.dxf)
    print(json.dumps(rep, ensure_ascii=False, indent=1))
    if not rep["prieto"]:
        print("NOT_ACCEPTED: " + rep["belezhka"], file=sys.stderr)
        sys.exit(3)
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
