#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
uslovni_etazhi.py — УСЛОВНИ ЕТАЖИ за обект без одобрени чертежи: по контура на сградата от КАИС - коридор по дългата ос,
стаи от двете страни, фоайе откъм улицата и стълбище срещу него. Изходът е същият като на cdr_import.py, затова
konkretna.py и build_plan.py работят с него без промяна; "_uslovna": true маркира, че разпределението не е реално.
Контурът, площта и етажността са истински, стените, вратите и стълбището - не: планът с такива етажи е РАБОТНА ЧЕРНОВА.

    python3 scripts/uslovni_etazhi.py situacionna.json -d папка [--sgrada 56722.660.887.4] [--etazhi 4] [--zala 1]

Записва <папка>/podlozhka_et<N>.json за всеки етаж и отпечатва JSON със сградата и помещенията. --zala N: етаж N е
фоайе и зала (концертна, спортна, актова) вместо стаи. Без мрежа.
"""
import argparse
import json
import math
import os
import re
import sys

from shapely.affinity import rotate
from shapely.geometry import MultiPoint, Point, Polygon, box

BAND = 6.6            # the depth of a room, m
CORRIDOR = 2.4


def bad(msg):
    sys.stderr.write("BAD_INPUT: " + msg + "\n")
    sys.exit(2)


def biggest(g):
    return g if g.geom_type == "Polygon" else max(getattr(g, "geoms", []), key=lambda x: x.area, default=None)


def floors_of(b):
    m = re.search(r"\+\s*(\d+)", str(b.get("etazhnost") or ""))
    return int(m.group(1)) if m else 1


def own_buildings(s):
    imot = str((s.get("kais") or {}).get("imot") or "")
    rows = [b for b in s.get("sgradi") or [] if len(b.get("kontur") or []) >= 3 and not b.get("sasedna")]
    own = [b for b in rows if imot and str(b.get("kais_id") or "").startswith(imot + ".")]
    return own or rows


def main_building(s, ident=None):
    rows = own_buildings(s)
    if ident:
        rows = [b for b in rows if str(b.get("kais_id")) == ident]
        if not rows:
            bad(f"сградата {ident} я няма в схемата")
    if not rows:
        bad("в схемата няма сграда с контур")
    return max(rows, key=lambda b: floors_of(b) * Polygon(b["kontur"]).buffer(0).area)


def angle_of(poly, s):
    """The rotation that lays the long side level, the side towards the nearest named street at the bottom."""
    ring = list(poly.minimum_rotated_rectangle.exterior.coords)
    edge = max(zip(ring, ring[1:]), key=lambda e: math.dist(e[0], e[1]))
    ang = -math.degrees(math.atan2(edge[1][1] - edge[0][1], edge[1][0] - edge[0][0]))
    pts = [Point(p) for u in s.get("ulitsi") or [] if u.get("ime") for p in (u.get("kontur") or u.get("tochki") or [])]
    if pts:
        near = min(pts, key=poly.distance)
        if rotate(near, ang, origin=(0, 0)).y > rotate(poly.centroid, ang, origin=(0, 0)).y:
            ang += 180
    return (ang + 180) % 360 - 180


class Floor:
    def __init__(self, ang):
        self.ang = ang
        self.rooms = []

    def world(self, g):
        return rotate(g, -self.ang, origin=(0, 0))

    def door(self, x, y, outer=False):
        q = self.world(Point(x, y))
        return {"x": round(q.x, 2), "y": round(q.y, 2), "shirina": 1.1, "vanshen": outer}

    def add(self, ime, g, doors):
        w = biggest(self.world(g))
        x0, y0, x1, y1 = biggest(g).bounds
        c = w.centroid if w.contains(w.centroid) else w.representative_point()
        self.rooms.append({"ime": ime, "kontur": [[round(x, 2), round(y, 2)] for x, y in list(w.exterior.coords)[:-1]],
                           "plosht_m2": round(w.area, 1),
                           "razmeri_m": sorted([round(x1 - x0, 1), round(y1 - y0, 1)], reverse=True),
                           "tsentar": [round(c.x, 2), round(c.y, 2)], "otvori": doors})


def closest(cells, i):
    return min(cells, key=lambda c: abs(c[0] - i)) if cells else None


def rooms_floor(P, ang, n):
    F = Floor(ang)
    x0, y0, x1, y1 = P.bounds
    v0, depth = y0 + 0.2, y1 - y0
    u0, u1 = x0 + 0.5, x1 - 0.5
    front = min(BAND, max(3.5, depth - CORRIDOR - 0.4 if depth < 11 else BAND))
    cor0, cor1 = v0 + front, v0 + front + CORRIDOR
    back_on = depth >= 11
    count = max(2, round((u1 - u0) / BAND))
    step = (u1 - u0) / count
    def cells(lo, hi):
        out = []
        for i in range(count):
            g = biggest(box(u0 + i * step, lo, u0 + (i + 1) * step, hi).intersection(P))
            if g is not None and g.area >= 7:
                out.append((i, g, u0 + (i + 0.5) * step))
        return out
    south = cells(v0 - 1, cor0)
    north = cells(cor1, cor1 + BAND) if back_on else []
    mid = (count - 1) // 2
    foyer = closest(south, mid)
    if not foyer:
        return None
    stair = closest(north, mid) or closest([c for c in south if c is not foyer], mid)
    if not stair:
        return None
    no = 0
    for side, row, wall in (("S", south, cor0), ("N", north, cor1)):
        for c in row:
            i, g, um = c
            if c is foyer:
                F.add("Фоайе", g, [F.door(um, wall), F.door(um, v0, True)])
            elif c is stair:
                F.add("Стълбище", g, [F.door(um, wall)])
            else:
                no += 1
                F.add(f"Помещение {n}.{no}", g, [F.door(um, wall)])
    rest = biggest(box(u0, cor1 + BAND, u1, y1 + 1).intersection(P)) if back_on else None
    if rest is not None and rest.area > 12:
        no += 1
        F.add(f"Помещение {n}.{no}", rest, [F.door(rest.centroid.x, cor1 + BAND)])
    corridor = biggest(box(u0, cor0, u1, cor1).intersection(P))
    if corridor is not None:
        F.add("Коридор", corridor, [])
    return F


def hall_floor(P, ang, n):
    F = Floor(ang)
    x0, y0, x1, y1 = P.bounds
    ux = x0 + max(6.0, min(9.0, (x1 - x0) * 0.25))
    vm = (y0 + y1) / 2
    F.add("Зала", box(ux, y0 - 1, x1 + 1, y1 + 1).intersection(P), [F.door(ux, vm)])
    F.add("Фоайе", box(x0 - 1, y0 - 1, ux, y1 + 1).intersection(P), [F.door(ux, vm), F.door(x0 + 3, y0 + 0.2, True)])
    return F


def underlay(F, outline, kais, n):
    lines = [{"tochki": r["kontur"] + r["kontur"][:1], "lw_mm": 0.35, "cvyat": "#1b1918"} for r in F.rooms]
    lines.append({"tochki": outline + outline[:1], "lw_mm": 0.71, "cvyat": "#1b1918"})
    tekst = [{"x": r["tsentar"][0], "y": r["tsentar"][1], "tekst": r["ime"], "razmer": 0.9, "kray": "sreda"}
             for r in F.rooms if r["ime"] in ("Фоайе", "Стълбище")]
    return {"podlozhka": lines, "tekst": tekst, "obekti": [], "pomeshtenia": F.rooms, "zavartane": round(F.ang, 2),
            "_uslovna": True, "_etazh": n, "_m_na_mm": 1, "_mashtab_na_odobrenia": "условно", "_kais_rms_m": 0,
            "_belezhki": ["условно разпределение по контура от КАИС - стените, вратите и стълбището не са реални"],
            "_kais": {"x0": kais.get("x0"), "y0": kais.get("y0")}}


def make(s, ident=None, etazhi=None, zala=()):
    """{floor: underlay} of one building (the main one by default) and the building."""
    b = main_building(s, ident)
    poly = Polygon(b["kontur"]).buffer(0)
    ang = angle_of(poly, s)
    P = rotate(poly, ang, origin=(0, 0))
    out = {}
    for n in range(1, (etazhi or floors_of(b)) + 1):
        F = hall_floor(P, ang, n) if n in zala else rooms_floor(P, ang, n)
        if F is None:
            bad("сградата е твърде малка за условно разпределение")
        out[n] = underlay(F, b["kontur"], s.get("kais") or {}, n)
    return out, b


def main():
    ap = argparse.ArgumentParser(description="Условни етажи по контура от КАИС")
    ap.add_argument("shema", help="JSON на ситуационната схема (situacionna.json)")
    ap.add_argument("-d", "--dir", default=".")
    ap.add_argument("--sgrada", help="kais_id на сградата (иначе - главната: най-голямата застроена площ по етажи)")
    ap.add_argument("--etazhi", type=int, help="брой етажи (иначе - от етажността в КАИС)")
    ap.add_argument("--zala", type=int, action="append", default=[], help="етажът е фоайе и зала")
    a = ap.parse_args()
    with open(a.shema, encoding="utf-8") as f:
        s = json.load(f)
    res, b = make(s, a.sgrada, a.etazhi, a.zala)
    os.makedirs(a.dir, exist_ok=True)
    for n, pod in res.items():
        with open(os.path.join(a.dir, f"podlozhka_et{n}.json"), "w", encoding="utf-8") as f:
            json.dump(pod, f, ensure_ascii=False)
    print(json.dumps({"sgrada": b.get("kais_id"), "etazhi": sorted(res), "uslovna": True,
                      "pomeshtenia": {n: [r["ime"] for r in p["pomeshtenia"]] for n, p in res.items()}}, ensure_ascii=False))


if __name__ == "__main__":
    main()
