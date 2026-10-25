#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ulitsi_avto.py — ръбовете на улиците, оправени автоматично (по образеца на ситуационната схема в регистъра):

1. Краят на кадастрален имот на улица, начертан през платното – страна на имота, зад която (на няколко метра) е
   улица от OpenStreetMap – не се чертае (става като "ulitsi_skrij").
2. Където така ръбът остава прекъснат, двата свободни края се свързват с плавна дъга по посоката на ръбовете
   (като "ulitsi_rab") – дъгата на кръстовището е непрекъсната.
3. Ръбът на улица от OpenStreetMap, който гледа към кадастрална улица (вътрешният ръб на кръстовището), не се
   чертае (като "bez_ruba").
4. Вход от улицата ("prohodi") без отвор в ограда до него получава две къси рамена навътре към обекта, от
   краищата на прекъсването – за да се вижда, че там се влиза ("ramena": метри, 0 – без рамена; по подразбиране 6).

Работи върху данните на shema.load() (в координатите на чертежа). "avto_ulitsi": false в JSON-а го изключва.
Ръчните поправки ("ulitsi_skrij", "ulitsi_rab", "bez_ruba") остават и се прилагат и тогава.
"""
import math

PROBE_M = 6.0          # how far beyond a cadastral edge an OpenStreetMap street must start for the edge to be inner
BAND_PROBE_M = 8.0     # how far beyond a band's edge a cadastral street must be for the band edge to be inner
SHARE = 0.6            # the share of the samples that must agree
JOIN_MAX_M = 30.0      # the farthest two free ends of a street edge are joined
ARM_M = 6.0            # the arms of an entrance from the street


def _dseg(p, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    L2 = dx * dx + dy * dy
    t = 0.0 if not L2 else max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / L2))
    return math.dist(p, (a[0] + t * dx, a[1] + t * dy))


def _dline(p, pts):
    return min(_dseg(p, a, b) for a, b in zip(pts, pts[1:]))


def _inside(p, poly):
    x, y = p
    res = False
    for (x1, y1), (x2, y2) in zip(poly, poly[1:] + poly[:1]):
        if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
            res = not res
    return res


def _area(poly):
    return sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(poly, poly[1:] + poly[:1])) / 2


def _offset(pts, d):
    """The polyline moved sideways by d (to the left of its direction)."""
    out = []
    for i, p in enumerate(pts):
        a, b = pts[max(i - 1, 0)], pts[min(i + 1, len(pts) - 1)]
        L = math.dist(a, b) or 1.0
        out.append((p[0] - (b[1] - a[1]) / L * d, p[1] + (b[0] - a[0]) / L * d))
    return out


def _samples(a, b, step=2.0):
    n = max(2, int(math.dist(a, b) / step))
    return [(a[0] + (b[0] - a[0]) * i / n, a[1] + (b[1] - a[1]) * i / n) for i in range(1, n)]


def _in_band(p, bands):
    return any(_dline(p, u["tochki"]) < u["shirina"] / 2 for u in bands)


def _in_parcel(p, parcels):
    return any(_inside(p, u["kontur"]) for u in parcels)


def _in_grass(p, grass):
    return any(_inside(p, g) for g in grass)


def _turn(p, q, r):
    """How much the line p–q–r turns at q, in degrees (0 – straight on)."""
    a1 = math.atan2(q[1] - p[1], q[0] - p[0])
    a2 = math.atan2(r[1] - q[1], r[0] - q[0])
    d = abs(math.degrees(a2 - a1)) % 360
    return min(d, 360 - d)


def _bezier(p0, c, p1, n=14):
    return [((1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * c[0] + t * t * p1[0],
             (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * c[1] + t * t * p1[1]) for t in (i / n for i in range(n + 1))]


def _ray_meet(p, u, q, v):
    """Where the rays p + s·u and q + t·v meet (s, t > 0), or None."""
    det = u[0] * (-v[1]) - u[1] * (-v[0])
    if abs(det) < 1e-9:
        return None
    dx, dy = q[0] - p[0], q[1] - p[1]
    s = (dx * (-v[1]) - dy * (-v[0])) / det
    t = (u[0] * dy - u[1] * dx) / det
    return (p[0] + s * u[0], p[1] + s * u[1]) if s > 0 and t > 0 else None


def popravi(data, box=None):
    """Adds to data the automatic street-edge corrections (in place); returns a short list of what was done."""
    bands = [u for u in data["ulitsi"] if "tochki" in u]
    parcels = [u for u in data["ulitsi"] if "kontur" in u and not u.get("bez_ruba")]
    grass = list(data.get("trevni") or [])
    done = []

    def in_box(p):
        return box is None or (box[0] - 1 <= p[0] <= box[2] + 1 and box[1] - 1 <= p[1] <= box[3] + 1)

    # 1. the cross-cuts of cadastral street parcels into a street of OpenStreetMap
    hidden = set()
    if bands:
        for pi, u in enumerate(parcels):
            k = u["kontur"]
            ccw = _area(k) > 0
            for ei, (a, b) in enumerate(zip(k, k[1:] + k[:1])):
                L = math.dist(a, b)
                if L < 1.0:
                    continue
                nx, ny = ((b[1] - a[1]) / L, -(b[0] - a[0]) / L) if ccw else (-(b[1] - a[1]) / L, (b[0] - a[0]) / L)
                pts = [p for p in _samples(a, b) if in_box(p)]
                if not pts:
                    continue
                hits = 0
                for p in pts:
                    for r in (1.0, 2.0, 3.5, 5.0, PROBE_M):
                        q = (p[0] + nx * r, p[1] + ny * r)
                        if _in_grass(q, grass):
                            break
                        if _in_band(q, bands):
                            hits += 1
                            break
                if hits / len(pts) >= SHARE:
                    hidden.add((pi, ei))
                    data["ulitsi_skrij"].append([tuple(a), tuple(b)])
        if hidden:
            done.append(f"скрити {len(hidden)} напречни края на кадастрални улици")

    # 2. the free ends left by it, joined with a smooth arc
    ends = []
    for pi, u in enumerate(parcels):
        k = u["kontur"]
        n = len(k)
        for vi in range(n):
            before, after = ((pi, (vi - 1) % n) in hidden), ((pi, vi) in hidden)
            if before == after:
                continue
            # the visible edge comes into the vertex – its direction, carried on past the vertex
            prev = k[(vi - 1) % n] if not before else k[(vi + 1) % n]
            v = k[vi]
            L = math.dist(prev, v) or 1.0
            if in_box(v):
                ends.append({"p": tuple(v), "dir": ((v[0] - prev[0]) / L, (v[1] - prev[1]) / L), "parcel": pi})
    used = set()
    pairs = sorted(((math.dist(a["p"], b["p"]), i, j) for i, a in enumerate(ends) for j, b in enumerate(ends)
                    if i < j and 0.5 < math.dist(a["p"], b["p"]) <= JOIN_MAX_M), key=lambda x: x[0])
    for _, i, j in pairs:
        if i in used or j in used:
            continue
        a, b = ends[i], ends[j]
        c = _ray_meet(a["p"], a["dir"], b["p"], b["dir"])
        if c is None or math.dist(c, a["p"]) > JOIN_MAX_M or math.dist(c, b["p"]) > JOIN_MAX_M:
            continue
        data["ulitsi_rab"].append(_bezier(a["p"], c, b["p"]))
        used |= {i, j}
    if used:
        done.append(f"затворени {len(used) // 2} прекъснати ръба на улици")

    # 3. a band's edge that faces a cadastral street is an inner edge of the junction
    joins = [ln for ln in data["ulitsi_rab"]]
    for u in bands:
        if u.get("bez_ruba"):
            continue
        votes = {}
        for side, sgn in (("lyav", 1), ("desen", -1)):
            edge = _offset(u["tochki"], sgn * u["shirina"] / 2)
            pts = []                                   # samples of that edge, each with its outward normal
            for a, b in zip(edge, edge[1:]):
                L = math.dist(a, b) or 1.0
                nx, ny = -(b[1] - a[1]) / L * sgn, (b[0] - a[0]) / L * sgn     # left of the direction for "lyav"
                pts += [(p, nx, ny) for p in _samples(a, b) if in_box(p)]
            if len(pts) < 3:
                continue
            hits = 0
            for p, nx, ny in pts:
                for r in (1.0, 2.5, 4.0, 6.0, BAND_PROBE_M):
                    z = (p[0] + nx * r, p[1] + ny * r)
                    if _in_grass(z, grass):
                        break
                    if _in_parcel(z, parcels) or any(_dline(z, ln) < 1.0 for ln in joins):
                        hits += 1
                        break
            votes[side] = hits / len(pts)
        inner = [s for s, v in votes.items() if v >= SHARE]
        if len(inner) == 1:
            u["bez_ruba"] = inner[0]
            done.append(f"вътрешният ръб на „{u['ime'] or 'улица от OpenStreetMap'}“ не се чертае")

    # 4. the arms of an entrance from the street
    gates = [(g["x"], g["y"], g["shirina"]) for g in data.get("vhodove") or []]
    edges = []                                       # (a, b, the turn at a in degrees, the turn at b)
    for u in parcels:
        k = u["kontur"]
        n = len(k)
        for i in range(n):
            a, b = k[i], k[(i + 1) % n]
            edges.append((a, b, _turn(k[i - 1], a, b), _turn(a, b, k[(i + 2) % n])))
    for u in bands:
        for sgn in (1, -1):
            e = _offset(u["tochki"], sgn * u["shirina"] / 2)
            edges += [(a, b, 0.0, 0.0) for a, b in zip(e, e[1:])]
    arms = 0
    for g in data["prohodi"]:
        length = g.get("ramena", ARM_M)
        p = (g["x"], g["y"])
        if not length or not edges or any(math.dist(p, (x, y)) <= max(w, g["shirina"]) for x, y, w in gates):
            continue
        a, b, ta, tb = min(edges, key=lambda e: _dseg(p, e[0], e[1]))
        if _dseg(p, a, b) > 2.5:
            continue
        L = math.dist(a, b) or 1.0
        tx, ty = (b[0] - a[0]) / L, (b[1] - a[1]) / L
        h = g["shirina"] / 2
        cuts = [(p[0] + tx * h * s_, p[1] + ty * h * s_) for s_ in (1, -1)]
        # the edge already turns in at both ends of the gap (a drive drawn by the cadastre) – no arms needed
        if all(min((math.dist(c, a), ta), (math.dist(c, b), tb))[0] <= 1.5 and
               min((math.dist(c, a), ta), (math.dist(c, b), tb))[1] >= 45 for c in cuts):
            continue
        side = None
        for sgn in (1, -1):
            nx, ny = -ty * sgn, tx * sgn
            q = (p[0] + nx * 2.0, p[1] + ny * 2.0)
            if not _in_parcel(q, parcels) and not _in_band(q, bands):
                side = (nx, ny)
                break
        if side is None:
            continue
        for s0 in cuts:
            data["ulitsi_rab"].append([s0, (s0[0] + side[0] * length, s0[1] + side[1] * length)])
        arms += 1
    if arms:
        done.append(f"рамена на {arms} входа от улицата")
    return done
