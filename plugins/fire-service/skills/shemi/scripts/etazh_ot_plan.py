#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
etazh_ot_plan.py — ЕТАЖ ОТ ЕВАКУАЦИОНЕН ПЛАН (снимка): обект без одобрени чертежи (.cdr), но с евакуационен план на
стената. Помещенията, вратите и таблата се разчитат от снимката в пиксели (Claude ги чете от картинката), а мащабът,
положението и посоката идват от контура на сградата в КАИС: външният контур на плана се напасва към него в най-добрата
от 8-те ориентации (4 завъртания × огледално) – планът на стената често е обърнат. Изходът е същият като на
cdr_import.py и uslovni_etazhi.py, затова konkretna.py, plan_avto.py и build_plan.py работят с него без промяна.
Разпределението е приблизително (до около метър) - по-добро от условните етажи, но не е одобрен чертеж.

    python3 scripts/etazh_ot_plan.py etazh.json --kais situacionna.json -o podlozhka_et1.json [--sgrada 56722.1.2.3]

etazh.json – в пиксели на снимката (x надясно, y надолу):
    {"etazh": 1,
     "snimka": "IMG_2352.jpg",                                   // само за бележката
     "kontur_px": [[483, 468], [1722, 468], …],                  // външният контур на сградата на плана
     "pomeshtenia": [{"ime": "Търговска зала", "kratko": "Зала",  // "kratko" - надписът на схемата (по желание)
                      "kontur_px": [[620, 690], …],
                      "vrati": [{"x": 1640, "y": 555, "shirina": 1.8, "vanshen": false}]}],
     "tabla": [[498, 527]],                                      // ел. таблата
     "orientatsiya": null}                                       // по желание: {"zavartane": 0|90|180|270, "ogledalno": false}

Отпечатва JSON: ориентацията, съвпадението с КАИС (IoU), площите на помещенията. IoU под 0,85 - контурът на плана
не е разчетен добре или сградата е друга: провери, преди да ползваш етажа.
"""
import argparse
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from shapely.affinity import rotate  # noqa: E402
from shapely.geometry import Point, Polygon  # noqa: E402
from uslovni_etazhi import angle_of, biggest, main_building  # noqa: E402

MIN_IOU = 0.85
LABEL_M2 = 40          # rooms smaller than this get no label – the names would overlap


def bad(msg):
    sys.stderr.write("BAD_INPUT: " + msg + "\n")
    sys.exit(2)


def orientations():
    """The 8 ways a wall plan may lie: (degrees, mirrored)."""
    return [(r, m) for m in (False, True) for r in (0, 90, 180, 270)]


def unit(pts, box, rot, mirror):
    """Pixel points → the unit square of the plan's outline, turned by `rot` and mirrored; y up."""
    x0, y0, x1, y1 = box
    out = []
    for x, y in pts:
        u, v = (x - x0) / (x1 - x0), 1 - (y - y0) / (y1 - y0)       # y of the picture points down
        if mirror:
            u = 1 - u
        for _ in range(rot // 90):                                   # 90° counter-clockwise inside the square
            u, v = 1 - v, u
        out.append((u, v))
    return out


def to_local(pts, box, rot, mirror, L):
    lx0, ly0, lx1, ly1 = L
    return [(lx0 + u * (lx1 - lx0), ly0 + v * (ly1 - ly0)) for u, v in unit(pts, box, rot, mirror)]


def iou(a, b):
    a, b = a.buffer(0), b.buffer(0)
    u = a.union(b).area
    return a.intersection(b).area / u if u else 0.0


def build(e, s, ident=None):
    b = main_building(s, ident)
    poly = Polygon(b["kontur"]).buffer(0)
    ang = angle_of(poly, s)
    P = rotate(poly, ang, origin=(0, 0))                             # the building with its long side level
    L = P.bounds
    out_px = e.get("kontur_px") or []
    if len(out_px) < 3:
        bad("kontur_px: външният контур на плана - поне 3 точки")
    xs, ys = [p[0] for p in out_px], [p[1] for p in out_px]
    box = (min(xs), min(ys), max(xs), max(ys))
    if box[2] - box[0] < 10 or box[3] - box[1] < 10:
        bad("kontur_px е твърде малък")
    forced = e.get("orientatsiya")
    cands = [(int(forced.get("zavartane", 0)) % 360, bool(forced.get("ogledalno")))] if forced else orientations()
    scored = sorted(((iou(Polygon(to_local(out_px, box, r, m, L)), P), r, m) for r, m in cands), reverse=True)
    score, rot, mirror = scored[0]

    def world(pts):
        g = Polygon(to_local(pts, box, rot, mirror, L)) if len(pts) > 2 else None
        return rotate(g, -ang, origin=(0, 0)) if g is not None else None

    def wpoint(x, y):
        q = rotate(Point(to_local([(x, y)], box, rot, mirror, L)[0]), -ang, origin=(0, 0))
        return round(q.x, 2), round(q.y, 2)

    lines, rooms, tekst = [], [], []
    for i, r in enumerate(e.get("pomeshtenia") or []):
        ime = str(r.get("ime") or "").strip()
        if not ime or len(r.get("kontur_px") or []) < 3:
            bad(f"pomeshtenia[{i}]: нужни са ime и kontur_px")
        w = biggest(world(r["kontur_px"]).buffer(0))
        ring = [[round(x, 2), round(y, 2)] for x, y in list(w.exterior.coords)[:-1]]
        lines.append({"tochki": ring + ring[:1], "lw_mm": 0.35, "cvyat": "#1b1918"})
        lx0, ly0, lx1, ly1 = Polygon(to_local(r["kontur_px"], box, rot, mirror, L)).bounds
        dims = sorted([round(lx1 - lx0, 1), round(ly1 - ly0, 1)], reverse=True)
        c = w.centroid if w.contains(w.centroid) else w.representative_point()
        doors = []
        for v in r.get("vrati") or []:
            x, y = wpoint(v["x"], v["y"])
            doors.append({"x": x, "y": y, "shirina": float(v.get("shirina") or 1.1), "vanshen": bool(v.get("vanshen"))})
        rooms.append({"ime": ime, "kontur": ring, "plosht_m2": round(w.area, 1), "razmeri_m": dims,
                      "tsentar": [round(c.x, 2), round(c.y, 2)], "otvori": doors})
        if w.area >= LABEL_M2:
            tekst.append({"x": round(c.x, 2), "y": round(c.y, 2), "tekst": str(r.get("kratko") or ime),
                          "razmer": 0.9, "kray": "sreda"})
    if not rooms:
        bad("pomeshtenia: няма нито едно помещение")
    lines.append({"tochki": b["kontur"] + b["kontur"][:1], "lw_mm": 0.71, "cvyat": "#1b1918"})
    obekti = []
    for x, y in e.get("tabla") or []:
        wx, wy = wpoint(x, y)
        obekti.append({"x": round(wx - 1.5, 2), "y": round(wy - 1, 2), "w": 3, "h": 2, "etiket": "Ел."})
    total = round(sum(r["plosht_m2"] for r in rooms), 1)
    notes = [f"разпределението е по евакуационния план{(' (' + e['snimka'] + ')') if e.get('snimka') else ''}, "
             f"мащабирано по контура от КАИС (съвпадение {score:.2f}); стените и вратите - приблизително"]
    if score < MIN_IOU:
        notes.append(f"съвпадението с КАИС е само {score:.2f} - провери контура на плана и сградата")
    kais = s.get("kais") or {}
    pod = {"podlozhka": lines, "tekst": tekst, "obekti": obekti, "pomeshtenia": rooms, "zavartane": round(ang, 2),
           "_etazh": int(e.get("etazh") or 1), "_m_na_mm": 1,
           "_mashtab_na_odobrenia": "по евакуационния план (снимка), вързан с контура от КАИС",
           "_kais_rms_m": round((1 - score) * math.sqrt(P.area), 1), "_belezhki": notes,
           "_kais": {"x0": kais.get("x0"), "y0": kais.get("y0")}}
    info = {"sgrada": b.get("kais_id"), "orientatsiya": {"zavartane": rot, "ogledalno": mirror},
            "savpadenie_kais": round(score, 3), "plosht_m2": total, "plosht_kais_m2": round(poly.area, 1),
            "pomeshtenia": {r["ime"]: r["plosht_m2"] for r in rooms},
            "preduprezhdeniya": [n for n in notes[1:]]}
    return pod, info


def main():
    ap = argparse.ArgumentParser(description="Етаж от евакуационен план (снимка), вързан с КАИС")
    ap.add_argument("etazh", help="JSON с помещенията в пиксели на снимката (виж началото на файла)")
    ap.add_argument("--kais", required=True, help="JSON на ситуационната схема (situacionna.json) - контурът от КАИС")
    ap.add_argument("--sgrada", help="kais_id на сградата (иначе - главната)")
    ap.add_argument("-o", "--out", required=True)
    a = ap.parse_args()
    with open(a.etazh, encoding="utf-8") as f:
        e = json.load(f)
    with open(a.kais, encoding="utf-8") as f:
        s = json.load(f)
    pod, info = build(e, s, a.sgrada)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(pod, f, ensure_ascii=False)
    print(json.dumps(info, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
