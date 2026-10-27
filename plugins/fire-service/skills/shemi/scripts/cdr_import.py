#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
cdr_import.py — взима одобрен чертеж на етаж (CorelDRAW .cdr, .svg или .pdf) като ВЕКТОРНА ПОДЛОЖКА за
scripts/shema.py: стените, белите маски, с които са изрязани отворите, знаците на вратите (единични и
двукрили) и прозорците, стълбищата и имената на помещенията – точно както са в чертежа, без прерисуване.
Чертежът се връзва с контура на сградата от КАИС (_shared/scripts/kais.py … --shema), така че хидрантите,
улиците и всичко от ситуационната схема застават на истинските си места спрямо етажа.

    python3 scripts/cdr_import.py PG_obekt-Hor.cdr --kais shema.json --sgrada 56722.659.850.1 -o etazh1.json

Какво отпада (то се чертае наново от shema.py със знаците от znatsi.py): рамката и антетката на листа, знакът
за посоките, пожарът и надписите за него (Fп, Iн, Qнг), автомобилите, хидрантите и линиите (червено и синьо),
котите и стрелките им. Посоките са от стрелката „север“. С --kais мащабът и положението са от контура на
сградата в КАИС – той е с предимство пред котите на стария чертеж: етажът се завърта по главната стена на
сградата в КАИС и се разпъва до нейните размери по двете оси. Без --kais – мащабът е от котите, в метри по
листа. Втори етаж на същата сграда – с --kato (същата основа, същата връзка с КАИС).

Изход – JSON:
{"podlozhka": [...],                       // за shema.py, полето "podlozhka"
 "tekst": [...],                            // имената на помещенията, на местата им в чертежа
 "obekti": [...],                           // ел. таблата („ел“ в чертежа) – „Ел.“ (чл. 7, ал. 4, т. 1, б. „з“)
 "pomeshtenia": [{"ime", "kontur", "plosht_m2", "razmeri_m", "tsentar"}],   // за пожара и разчета (sili-i-sredstva)
 "zavartane": N,                            // за shema.py – чертежът се обръща както е одобреният (север натам)
 "_m_na_mm": …, "_kais_rms_m": …, "_belezhki": [...]}
"""
import argparse
import json
import math
import os
import re
import statistics
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from shema import main_wall_angle  # noqa: E402

NARROW, WIDE = 0.45, 0.6   # the width of a letter in the font of the drawings and in the library's font, of its size
PX = 25.4 / 96          # svgelements gives the shapes in CSS px; LibreOffice writes 1/100 mm in the viewBox
BLACK, WHITE = ("#1b1918", "#000000", "#1a1919", "#1d1d1b"), ("#ffffff",)
DROP_TEXT = re.compile(r"(гр\.?\s*огн|^F[пг]?\b|^I[нг]?\b|^Q|l/s|m2|м2|^\d+([.,]\d+)?$|^С-$|^ПХ$|РСПБЗН|^П$)", re.I)


def to_svg(path):
    if path.lower().endswith(".svg"):
        return path
    out = tempfile.mkdtemp(prefix="cdr_")
    subprocess.run(["soffice", "--headless", "--convert-to", "svg", "--outdir", out, path], check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=180)
    svg = os.path.join(out, os.path.splitext(os.path.basename(path))[0] + ".svg")
    if not os.path.exists(svg):
        sys.exit("BAD_INPUT: чертежът не се отвори (soffice)")
    return svg


def parse(svg_path):
    from svgelements import SVG, Shape, Text, Path, Move, Close, Line
    shapes, texts = [], []
    for e in SVG.parse(svg_path, reify=True).elements():
        if isinstance(e, Text):
            t = (e.text or "").strip()
            if t:
                texts.append({"t": t, "x": e.x / 100, "y": e.y / 100, "fs": (e.font_size or 300) / 100,
                              "c": str(e.fill).lower()})
        elif isinstance(e, Shape):
            subs, cur = [], []
            for seg in Path(e).segments():
                if isinstance(seg, Move):
                    if len(cur) > 1:
                        subs.append(cur)
                    cur = [(seg.end.x * PX, seg.end.y * PX)]
                elif isinstance(seg, Close):
                    if cur:
                        subs.append(cur + [cur[0]])
                    cur = []
                elif isinstance(seg, Line):
                    cur.append((seg.end.x * PX, seg.end.y * PX))
                else:
                    cur += [(seg.point(k / 8).x * PX, seg.point(k / 8).y * PX) for k in range(1, 9)]
            if len(cur) > 1:
                subs.append(cur)
            if subs:
                stroke = str(e.stroke).lower() if e.stroke is not None else "none"
                shapes.append({"subs": subs, "s": stroke, "w": (e.stroke_width or 0) * PX if stroke != "none" else 0,
                               "f": str(e.fill).lower() if e.fill is not None else "none"})
    return shapes, texts


def bbox(pts):
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    return min(xs), min(ys), max(xs), max(ys)


def main():
    ap = argparse.ArgumentParser(description="Одобрен чертеж на етаж като векторна подложка за shema.py")
    ap.add_argument("chertezh")
    ap.add_argument("--kais", help="shema.json от kais.py obekt --shema (контурите в метри)")
    ap.add_argument("--sgrada", help="кадастралният идентификатор на сградата (kais_id)")
    ap.add_argument("--kato", help="вземи връзката с КАИС от друг етаж на същата сграда (JSON от cdr_import.py) – "
                                   "етажите са начертани на една основа")
    ap.add_argument("-o", "--out", required=True)
    a = ap.parse_args()
    shapes, texts = parse(to_svg(a.chertezh))
    notes = []

    page_w = max(p[0] for s in shapes for sub in s["subs"] for p in sub)
    # the title block and the frame of the sheet – out
    own = next((t for t in texts if t["t"].startswith("Собственик")), None)
    tb = (own["x"] - 2, own["y"] - 6) if own else (page_w * 0.6, 1e9)
    def in_title(b):
        return b[0] >= tb[0] - 1 and b[1] >= tb[1] - 1
    def is_frame(b):
        return b[2] - b[0] > 0.6 * page_w or b[3] - b[1] > 0.6 * page_w * 0.7

    walls = [s for s in shapes if s["s"] in BLACK and s["w"] > 0.6]          # the thick lines of the walls
    wb = bbox([p for s in walls for sub in s["subs"] for p in sub if not is_frame(bbox(sub))])
    arrows = [bbox(sub) for s in shapes if s["s"] == "none" and s["f"] in BLACK for sub in s["subs"]]
    arrow_c = [((b[0] + b[2]) / 2, (b[1] + b[3]) / 2) for b in arrows]
    near_arrow = lambda p: any(math.dist(p, c) < 3.0 for c in arrow_c)       # noqa: E731

    # the scale: each number of a dimension against the length of its dimension line (between the arrows)
    dims = []
    for s in shapes:
        if s["s"] in BLACK and s["w"] < 0.3:
            for sub in s["subs"]:
                if near_arrow(sub[0]) and near_arrow(sub[-1]):
                    dims.append((sub[0], sub[-1]))
    ratios = []
    for t in texts:
        m = re.fullmatch(r"(\d+(?:[.,]\d+)?)", t["t"])
        if m and not in_title((t["x"], t["y"])):
            v = float(m.group(1).replace(",", "."))
            near = min(dims, key=lambda d_: math.dist(((d_[0][0] + d_[1][0]) / 2, (d_[0][1] + d_[1][1]) / 2),
                                                        (t["x"], t["y"])), default=None)
            if near and math.dist(*near) > 5:
                ratios.append(v / math.dist(*near))
    if not ratios:
        sys.exit("BAD_INPUT: в чертежа няма коти – мащабът не се определя")
    k = statistics.median(ratios)
    if max(ratios) - min(ratios) > 0.08 * k:
        notes.append(f"котите дават различен мащаб ({min(ratios):.4f}–{max(ratios):.4f} m/mm) – взета е медианата")

    # north: the compass arrow – its tip is the point farthest from its centre
    comp = [s for s in shapes if s["f"] not in ("none",) + WHITE + BLACK[1:] and s["s"] == "none"]
    comp = [sub for s in shapes if s["f"] == "#000200" for sub in s["subs"]] or \
           [sub for s in shapes if s["s"] == "#000200" for sub in s["subs"]]
    if comp:
        pts = [p for sub in comp for p in sub]
        c = (sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts))
        tip = max(pts, key=lambda p: math.dist(p, c))
        north_page = math.degrees(math.atan2(-(tip[1] - c[1]), tip[0] - c[0]))      # 0 – to the right, 90 – up
        north_page = round(north_page / 90) * 90 if abs(north_page - round(north_page / 90) * 90) < 12 else north_page
    else:
        north_page = 90
        notes.append("няма стрелка „север“ – прието е, че северът е нагоре")
    rot = 90 - north_page           # turns the sheet so that its north points up – the frame of КАИС

    keep = []
    for s in shapes:
        if s["s"] == "none" and s["f"] == "none":
            continue
        for sub in s["subs"]:
            b = bbox(sub)
            if is_frame(b) or in_title(b) or b[2] < wb[0] - 3 or b[0] > wb[2] + 3 or b[3] < wb[1] - 3 or b[1] > wb[3] + 3:
                continue
            if s["s"] in BLACK:
                if s["w"] < 0.6 and (near_arrow(sub[0]) or near_arrow(sub[-1])):
                    continue                            # a dimension line
                if s["w"] >= 0.3 and len(sub) == 2 and (near_arrow(sub[0]) or near_arrow(sub[-1])):
                    continue                            # its extension tick
                keep.append({"tochki": sub, "lw_mm": round(s["w"], 3), "cvyat": "#1b1918"})
            elif s["s"] == "none" and s["f"] in WHITE and len(sub) >= 4:
                keep.append({"tochki": sub, "plaska": True})
            elif s["s"] in WHITE:
                keep.append({"tochki": sub, "lw_mm": round(s["w"], 3), "cvyat": "#ffffff"})

    # sheet (mm, y down) → metres with north up
    c_, s_ = math.cos(math.radians(rot)), math.sin(math.radians(rot))
    def M(p, k=k):                                      # k is fixed here – the scale of the sheet, from its dimensions
        x, y = p[0] * k, -p[1] * k
        return (x * c_ - y * s_, x * s_ + y * c_)

    tr = lambda p: M(p)                                                   # noqa: E731
    rms = None
    b = None
    if a.kato:                                          # the same building, another floor – the same fit
        pr = json.load(open(a.kato))["_preobrazuvane"]
        rot, k = pr["rot"], pr["k_dims"]
        c_, s_ = math.cos(math.radians(rot)), math.sin(math.radians(rot))

        def M(p, k=k):                                   # the sheet of the other floor – its scale and its north
            x, y = p[0] * k, -p[1] * k
            return (x * c_ - y * s_, x * s_ + y * c_)
        import numpy as np
        L_, sc_, tc_, T_ = np.array(pr["L"]), pr["sc"], pr["tc"], pr["T"]
        def tr(p):
            x, y = M(p)
            v = L_ @ np.array([x - sc_[0], y - sc_[1]]) + np.array(tc_) + np.array(T_)
            return (float(v[0]), float(v[1]))
        _FIT.update(pr["fit"])
        rms = pr.get("rms")
        k = pr["k"]
        notes.append(f"връзката с КАИС е от {os.path.basename(a.kato)} – същата основа")
        if a.kais and a.sgrada:
            b = next((g for g in json.load(open(a.kais)).get("sgradi", []) if g.get("kais_id") == a.sgrada), None)
    elif a.kais and a.sgrada:
        d = json.load(open(a.kais))
        b = next((g for g in d.get("sgradi", []) if g.get("kais_id") == a.sgrada), None)
        if not b:
            sys.exit(f"BAD_INPUT: сградата {a.sgrada} я няма в {a.kais}")
        others = [g["kontur"] for g in d.get("sgradi", []) if not g.get("sasedna") and g is not b]   # the annexes
        # every line of the walls – also the thin ones of the window walls on the facades, which carry the outline
        # КАИС has the priority: only the OUTER outline of the floor (its facades, with the window walls) is fitted
        #   onto the outline of the building – the inner walls and the annexes drawn beside it do not pull the scale
        tr, rms = fit_kais(outline_points(keep, M), b["kontur"], M)
        _FIT["k_dims"] = k
        k *= _FIT["scale"]
        sx_, sy_ = (v_ * k / _FIT["scale"] for v_ in _FIT["scales"])
        notes.append(f"мащабът е от контура в КАИС: по едната страна 1:{round(sx_ * 1000)}, по другата 1:{round(sy_ * 1000)}; "
                     f"котите на чертежа дават "
                     f"{min(ratios):.3f}–{max(ratios):.3f} m/mm – одобреният чертеж не е в мащаб")
        notes = [n for n in notes if not n.startswith("котите дават")]
        if rms > 1.0:
            notes.append(f"чертежът се разминава с контура от КАИС средно с {rms:.1f} m – провери етажа и сградата")

    out = {"podlozhka": [], "tekst": [], "obekti": [], "pomeshtenia": []}
    if b is not None:                                   # the ladders of the old scenario (thin, slanting, outside the
        from matplotlib.path import Path as _MP          #   building) are forces, not the building – they go
        kd = json.load(open(a.kais)) if a.kais else {}
        bld = [_MP(b["kontur"])] + [_MP(g["kontur"]) for g in kd.get("sgradi", []) if not g.get("sasedna")]
        def slanted_outside(e):
            if e.get("plaska") or e.get("lw_mm", 0) >= 0.3:
                return False
            q = [tr(p) for p in e["tochki"]]
            ins = sum(1 for p in q if any(pth.contains_point(p) for pth in bld))
            if ins > 0.6 * len(q):
                return False
            angs = [math.degrees(math.atan2(y2 - y1, x2 - x1)) % 90 for (x1, y1), (x2, y2) in zip(e["tochki"], e["tochki"][1:])
                    if math.hypot(x2 - x1, y2 - y1) > 0.2]
            return bool(angs) and all(4 < v < 86 for v in angs)
        keep = [e for e in keep if not slanted_outside(e)]
    from shapely.geometry import Point as _Pt, Polygon as _Pg0
    bld_ = _Pg0(b["kontur"]).buffer(0) if b is not None else None
    vanshni = 0
    for e in keep:
        e = dict(e)
        e["tochki"] = [[round(q[0], 3), round(q[1], 3)] for q in map(tr, e["tochki"])]
        if bld_ is not None and not e.get("plaska") and e.get("lw_mm", 0) > 0.6:
            # КАИС has the priority: a wall of the old drawing that lies outside the building in КАИС (an annex or a
            #   neighbour drawn by hand, out of place) is left out – the buildings round it come from КАИС
            far = sum(1 for q in e["tochki"] if bld_.exterior.distance(_Pt(q)) > 1.0 and not bld_.contains(_Pt(q)))
            if far > 0.5 * len(e["tochki"]):
                vanshni += 1
                continue
        out["podlozhka"].append(e)
    if vanshni:
        notes.append(f"{vanshni} стени от чертежа са извън сградата в КАИС и отпадат (съседните сгради са от КАИС).")

    # the rooms – the spaces closed by the walls; their names – the texts inside them
    from shapely.geometry import LineString, Point, Polygon
    from shapely.ops import unary_union
    wl = unary_union([LineString([tr(q) for q in e["tochki"]]).buffer(0.12)
                      for e in keep if e.get("lw_mm", 0) > 0.6 and not e.get("plaska")])
    rooms = [Polygon(h) for g in getattr(wl, "geoms", [wl]) for h in g.interiors if Polygon(h).area > 2]

    lines = []
    for t in texts:
        if t["c"] not in BLACK or in_title((t["x"], t["y"])) or DROP_TEXT.search(t["t"]):
            if t["t"].lower() in ("ел", "ел.") or "табло" in t["t"].lower():
                x, y = tr((t["x"] + 0.4 * t["fs"], t["y"] - 0.35 * t["fs"]))
                out["obekti"].append({"x": round(x - 0.6, 2), "y": round(y - 0.4, 2), "w": 1.2, "h": 0.8, "etiket": "Ел."})
            continue
        if not (wb[0] - 3 <= t["x"] <= wb[2] + 3 and wb[1] - 3 <= t["y"] <= wb[3] + 3):
            continue
        lines.append(t)
    for t in lines:                                     # a text keeps its place and its size on the sheet
        # the drawings are in a narrow font (Arial Narrow, ≈ 0.45 of the size per letter); the library's font is wider
        #   (≈ 0.6) – the text is centred where it was and made smaller, so that it keeps its width and its room
        x, y = tr((t["x"] + 0.5 * NARROW * t["fs"] * len(t["t"]), t["y"] - 0.35 * t["fs"]))
        out["tekst"].append({"x": round(x, 2), "y": round(y, 2), "tekst": t["t"],
                             "razmer": round(t["fs"] * 72 / 25.4 / 7 * NARROW / WIDE, 2), "kray": "sreda", "_red": t["y"]})
    for r in rooms:                                    # a name of two lines („Съблекалня“ / „мъже“) – joined
        inside = sorted([t for t in out["tekst"] if r.contains(Point(t["x"], t["y"]))], key=lambda t: t["_red"])
        ime = " ".join(t["tekst"].rstrip("-") if t["tekst"].endswith("-") else t["tekst"] for t in inside)
        ime = re.sub(r"-\s+", "", ime).strip()
        mr = r.minimum_rotated_rectangle
        cs = list(mr.exterior.coords)
        sides = sorted([math.dist(cs[0], cs[1]), math.dist(cs[1], cs[2])], reverse=True)
        out["pomeshtenia"].append({"ime": ime, "kontur": [[round(x, 2), round(y, 2)] for x, y in r.exterior.coords],
                                   "plosht_m2": round(r.area + 0.12 * r.length, 1),          # to the middle of the walls
                                   "razmeri_m": [round(sides[0] + 0.24, 1), round(sides[1] + 0.24, 1)],
                                   "tsentar": [round(r.centroid.x, 2), round(r.centroid.y, 2)]})
    # the openings of each room – the white masks on its walls: on the outline of the building – windows (and
    #   outer doors), inside – doors; konkretna.py puts the nozzle in front of a door, never in the fire
    from shapely.geometry import Polygon as _Pg
    outer = LineString(list(b["kontur"]) + [b["kontur"][0]]) if b else None
    masks = []
    for e in out["podlozhka"]:
        if e.get("plaska") and len(e["tochki"]) >= 4:
            g = _Pg(e["tochki"])
            if g.is_valid and 0.05 < g.area < 12:
                mr = g.minimum_rotated_rectangle.exterior.coords
                masks.append((g.centroid, max(math.dist(mr[0], mr[1]), math.dist(mr[1], mr[2]))))
    for p_, r in zip(out["pomeshtenia"], rooms):
        ring_ = r.exterior
        p_["otvori"] = [{"x": round(c.x, 2), "y": round(c.y, 2), "shirina": round(w, 2),
                         "vanshen": bool(outer is not None and outer.distance(c) < 1.0)}
                        for c, w in masks if ring_.distance(c) < 0.45 and w > 0.6]
    # the drawing is turned back as on the approved sheet – north where it was
    main_angle = main_wall_angle([tuple(q) for q in max(out["pomeshtenia"], key=lambda p_: p_["plosht_m2"])["kontur"]]) \
        if out["pomeshtenia"] else 0.0
    out["zavartane"] = round(-(90 - north_page) - (tr_angle(tr) if a.kais else 0.0), 2)
    for t in out["tekst"]:
        t.pop("_red", None)
    if "L" in _FIT:
        out["_preobrazuvane"] = {"rot": rot, "k_dims": _FIT.get("k_dims", k), "k": k, "L": _FIT["L"], "sc": _FIT["sc"],
                                 "tc": _FIT["tc"], "T": _FIT["T"], "rms": rms,
                                 "fit": {kk: _FIT[kk] for kk in ("ang", "scale", "scales", "cover")}}
    if a.kais:                                         # the frame of КАИС the floor is in – konkretna.py moves any
        kk_ = json.load(open(a.kais)).get("kais") or {}   #   other scheme JSON of the object (e.g. the situational one) to it
        out["_kais"] = {"x0": kk_.get("x0"), "y0": kk_.get("y0")}
    out["_m_na_mm"] = round(k, 5)
    out["_mashtab_na_odobrenia"] = f"1:{round(k * 1000)}"
    out["_kais_rms_m"] = None if rms is None else round(rms, 2)
    out["_belezhki"] = notes
    json.dump(out, open(a.out, "w"), ensure_ascii=False, indent=1)
    print(json.dumps({k_: v for k_, v in out.items() if k_.startswith("_") or k_ == "zavartane"} |
                     {"podlozhka": len(out["podlozhka"]), "tekst": len(out["tekst"]), "obekti": len(out["obekti"]),
                      "pomeshtenia": [(p_["ime"], p_["plosht_m2"], p_["razmeri_m"]) for p_ in out["pomeshtenia"]]},
                     ensure_ascii=False, indent=1))


def fit_kais(src_pts, kontur, M):
    """КАИС has the priority: the floor is turned along the main wall of the building in КАИС and stretched, along
    each axis of the building, to its extent in КАИС (an old drawing is rarely to scale, nor equally along both
    sides). Returns (transform, rms m – how far the outline of the floor lies from the outline in КАИС)."""
    import numpy as np
    from scipy.spatial import cKDTree
    th = math.radians(main_wall_angle([tuple(p) for p in kontur]))
    while th > math.pi / 4:
        th -= math.pi / 2
    while th < -math.pi / 4:
        th += math.pi / 2
    U = np.array([[math.cos(th), math.sin(th)], [-math.sin(th), math.cos(th)]])   # world → building axes
    P = np.array(src_pts)                                # the floor is drawn square to its sheet – its own axes
    K = np.array(kontur) @ U.T                           # the building in КАИС, in its axes
    p0, p1, k0, k1 = P.min(0), P.max(0), K.min(0), K.max(0)
    S = (k1 - k0) / (p1 - p0)
    A = U.T @ np.diag(S)                                 # turned onto the building and stretched to it: q = A p + T
    T = U.T @ (k0 - S * p0)
    ring = np.array(densify(list(kontur) + [kontur[0]], 0.2))
    Q = np.array(src_pts) @ A.T + T
    d_ = cKDTree(ring).query(Q)[0]
    rms = float(np.sqrt((d_ ** 2).mean()))
    sv = np.linalg.svd(A, compute_uv=False)
    _FIT.update(ang=math.degrees(th), scale=float(S.mean()), scales=[float(v) for v in S], cover=None,
                L=A.tolist(), sc=[0.0, 0.0], tc=[0.0, 0.0], T=[float(v) for v in T], k_dims=None)

    def tr(p):
        v = A @ np.array(M(p)) + T
        return (float(v[0]), float(v[1]))
    return tr, rms


def outline_points(keep, M):
    """Points along the outer outline of the floor – of its rooms (the spaces closed by the walls), joined: a line
    drawn beside the building (an annex, a fence) closes no room and stays out."""
    from shapely.geometry import LineString, Polygon
    from shapely.ops import unary_union
    w = unary_union([LineString([M(p) for p in e["tochki"]]).buffer(0.15)
                     for e in keep if not e.get("plaska") and e.get("lw_mm", 0) > 0.6])
    holes = [Polygon(h) for g in getattr(w, "geoms", [w]) for h in g.interiors]
    holes = [h for h in holes if h.area > 3 and h.area / (h.minimum_rotated_rectangle.area or 1) > 0.5]
    floor = unary_union([h.buffer(0.5) for h in holes]).buffer(-0.2)
    part = max(getattr(floor, "geoms", [floor]), key=lambda x: x.area)
    return densify(list(part.exterior.coords), 0.4)


def densify(pts, step=0.8):
    out = []
    for p, q in zip(pts, pts[1:]):
        n = max(1, int(math.dist(p, q) / step))
        out += [(p[0] + (q[0] - p[0]) * i / n, p[1] + (q[1] - p[1]) * i / n) for i in range(n)]
    return out + [pts[-1]]


_FIT = {}


def tr_angle(_tr):
    return _FIT.get("ang", 0.0)


if __name__ == "__main__":
    main()
