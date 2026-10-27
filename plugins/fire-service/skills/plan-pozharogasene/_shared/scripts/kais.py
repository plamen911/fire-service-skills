#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
kais.py — кадастралната карта на АГКК (КАИС, kais.cadastre.bg) за ситуационните схеми и плановете за
пожарогасене: поземленият имот и сградите в него с точните им контури (КС2005, в метри), предназначение,
брой етажи и застроена площ, и кадастралната карта около тях като фон.

Данните идват от публичната карта на КАИС (без вход, без собственици) през n8n с личния ключ – КАИС не се
пита от тук. Без ключ скриптът спира с `NO_KEY`; тогава данните (без фона) идват от инструмента `kais`
на конектора Fire Service.

    python3 _shared/scripts/kais.py obekt --lat 43.41257 --lon 24.65047 -o kais.json
    python3 _shared/scripts/kais.py obekt --link "https://www.google.com/maps/place/…/@43.41257,24.65047,17z" -o kais.json
    python3 _shared/scripts/kais.py obekt --id 56722.27.446 -o kais.json --shema shema.json [--voda] [--radius 40]
    python3 _shared/scripts/kais.py tarsi "Плевен ул. Васил Левски 1"
    python3 _shared/scripts/kais.py mesto "Ларго метанстанция" --masto Плевен

obekt – имотът в точката (или по идентификатора) и всички сгради в него. Записва:
  kais.json         – отговорът: "imot", "sgradi" (контури в КС2005), "ulitsi" (OpenStreetMap), "ramka";
  --shema ФАЙЛ      – готово начало на JSON за scripts/shema.py на скила shemi (и situacionna.py), в знаците и
                      цветовете на Приложение № 6 и чл. 9, ал. 9: терен около имота, сградите като "kontur" в
                      метри с предназначението и етажността, границата на имота ("imot" – щрих-пунктир с
                      идентификатора, в легендата), улиците с имената им (от OpenStreetMap) и "kais" (началото в
                      КС2005). Допълва се: входове, ограда, водопровод, ел. табло, категория …;
  --voda            – и точните водоизточници (проверени на място или от ВиК) в терена – а ако там няма, най-
                      близкият, като теренът се разширява до него – с разстоянието от сградата до него
                      (от voda.py – трябва личен ключ); хидрант на над 60 m извън терена – надпис на ръба
                      откъм него (вид, разстояние, посока, адрес) вместо разширяване (--hidrant-v-terena);
  --radius N        – колко метра около имота да обхване теренът (30–300, по подразбиране 40);
  --bez-granitsa    – без границата на поземления имот;
  --vodoprovod D    – с --voda: водопроводът по улицата на хидранта с диаметър D (по подразбиране 70/80 – когато
                      няма данни от ВиК; „не“ – без него); --natisk – налягането, bar (по подразбиране 3–5).
                      Имената на ж.к. и кварталите наблизо – от OpenStreetMap;
  --fon             – и кадастралната карта около имота като блед фон (kais_fon.png до kais.json) – за
                      работа и сверка; не е по Приложение № 2а, затова не е по подразбиране.
mesto – обект по ИМЕ (магазин, бензиностанция, фирма): кандидатите с име, адрес и точка (Google Places, после
  OpenStreetMap – само в област Плевен); избраният – към obekt --lat/--lon. Без браузър и без Google Maps.
tarsi – какво намира търсачката на картата по идентификатор или адрес. В промишлените зони много имоти са
записани само с местността (м. „…“), без улица и номер – тогава търси по точка.

Отпечатва JSON с кратко резюме: имотът, сградите (предназначение, етажи, застроена площ, размери),
файловете и бележките.

Грешки (на stderr, код ≠ 0):
    NO_KEY / KEY_REJECTED   — няма личен ключ / n8n не го приема
    BAD_INPUT: …            — неверни координати или идентификатор
    NOT_FOUND: …            — в точката няма имот / идентификаторът не е в КАИС
    KAIS_UNAVAILABLE: …     — КАИС не отговаря или е сменил картата си
"""
import argparse
import base64
import datetime
import json
import math
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import api_config  # noqa: E402

CONFIG_FIELD = "kais_url"
EXACT = ("проверена", "вик")       # the water sources whose coordinates are exact (voda.py)
SMALL_M = 8.0                     # a building narrower than this is drawn without a name and dimensions
MAX_RAZSTOYANIE_M = 80.0          # the neighbours farther than this get no distance line
MAX_SASEDI = 12                   # the bordering parcels read for their buildings (one КАИС call each)


# ── КС2005 (EPSG:7801) ⇄ WGS84 – Lambert conformal conic, 2SP, GRS80 (the same as the n8n node) ────────────────
_A, _F = 6378137.0, 1 / 298.257222101
_E = math.sqrt(2 * _F - _F * _F)
_D = math.pi / 180
_P1, _P2, _P0, _L0 = 42 * _D, (43 + 20 / 60) * _D, 42.66787568333333 * _D, 25.5 * _D
_X0, _Y0 = 500000.0, 4725824.3591


DALECH_HIDRANT_M = 60     # a hydrant farther than this outside the terrain gets a pointer, not a bigger terrain

def _m(p):
    return math.cos(p) / math.sqrt(1 - _E * _E * math.sin(p) ** 2)


def _t(p):
    return math.tan(math.pi / 4 - p / 2) / ((1 - _E * math.sin(p)) / (1 + _E * math.sin(p))) ** (_E / 2)


_N = (math.log(_m(_P1)) - math.log(_m(_P2))) / (math.log(_t(_P1)) - math.log(_t(_P2)))
_FF = _m(_P1) / (_N * _t(_P1) ** _N)
_R0 = _A * _FF * _t(_P0) ** _N


def wgs_to_kc(lat, lon):
    """WGS84 (ETRS89) → КС2005 (x east, y north), metres."""
    r = _A * _FF * _t(lat * _D) ** _N
    th = _N * (lon * _D - _L0)
    return _X0 + r * math.sin(th), _Y0 + _R0 - r * math.cos(th)


def kc_to_wgs(x, y):
    dx, dy = x - _X0, _R0 - (y - _Y0)
    r = math.copysign(math.hypot(dx, dy), _N)
    tt = (r / (_A * _FF)) ** (1 / _N)
    th = math.atan2(dx, dy)
    p = math.pi / 2 - 2 * math.atan(tt)
    for _ in range(10):
        p = math.pi / 2 - 2 * math.atan(tt * ((1 - _E * math.sin(p)) / (1 + _E * math.sin(p))) ** (_E / 2))
    return p / _D, (th / _N + _L0) / _D


def fail(code, msg, rc=2):
    sys.stderr.write(f"{code}: {msg}\n")
    sys.exit(rc)


def call(body):
    cfg = api_config.load()
    if not cfg.get(CONFIG_FIELD):
        fail("N8N_UNAVAILABLE", f"в incident_api.json няма {CONFIG_FIELD}", 3)
    try:
        return api_config.post(CONFIG_FIELD, body, timeout=120)
    except urllib.error.HTTPError as e:
        try:
            msg = json.loads(e.read()).get("error", "")
        except ValueError:
            msg = ""
        msg = msg.split(" [line")[0] or f"HTTP {e.code}"
        code, _, rest = msg.partition(": ")
        if code in ("BAD_REQUEST", "NOT_FOUND", "KAIS_UNAVAILABLE"):
            fail("BAD_INPUT" if code == "BAD_REQUEST" else code, rest, 2 if code != "KAIS_UNAVAILABLE" else 3)
        fail("N8N_ERROR", msg, 3)
    except (urllib.error.URLError, OSError) as e:
        fail("N8N_UNAVAILABLE", f"n8n не отговаря: {e}", 3)


# ── geometry helpers ─────────────────────────────────────────────────────────────────────────────────────────
def area(ring):
    return abs(sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(ring, ring[1:] + ring[:1]))) / 2


def dims(ring):
    """Length and width of the smallest rectangle around the outline, in any direction (the walls' lengths)."""
    best = None
    pts = ring[:-1] if ring and ring[0] == ring[-1] else ring
    for a, b in zip(pts, pts[1:] + pts[:1]):
        ang = math.atan2(b[1] - a[1], b[0] - a[0])
        c, s = math.cos(ang), math.sin(ang)
        us = [p[0] * c + p[1] * s for p in pts]
        vs = [-p[0] * s + p[1] * c for p in pts]
        w, h = max(us) - min(us), max(vs) - min(vs)
        if best is None or w * h < best[0]:
            best = (w * h, max(w, h), min(w, h))
    return (round(best[1], 1), round(best[2], 1)) if best else (None, None)


def length(pts):
    return sum(math.dist(a, b) for a, b in zip(pts, pts[1:]))


def clip_polyline(pts, x0, y0, x1, y1):
    """The pieces of a polyline inside the rectangle (Liang–Barsky on every segment)."""
    pieces, cur = [], []
    for a, b in zip(pts, pts[1:]):
        dx, dy = b[0] - a[0], b[1] - a[1]
        t0, t1, ok = 0.0, 1.0, True
        for p, q in ((-dx, a[0] - x0), (dx, x1 - a[0]), (-dy, a[1] - y0), (dy, y1 - a[1])):
            if p == 0:
                if q < 0:
                    ok = False
                    break
                continue
            t = q / p
            if p < 0:
                t0 = max(t0, t)
            else:
                t1 = min(t1, t)
        if not ok or t0 > t1:
            if cur:
                pieces.append(cur)
                cur = []
            continue
        pa = (a[0] + t0 * dx, a[1] + t0 * dy)
        pb = (a[0] + t1 * dx, a[1] + t1 * dy)
        if not cur:
            cur = [pa]
        elif math.dist(cur[-1], pa) > 1e-6:
            pieces.append(cur)
            cur = [pa]
        cur.append(pb)
        if t1 < 1.0:
            pieces.append(cur)
            cur = []
    if cur:
        pieces.append(cur)
    return pieces


def dist_seg(p, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    if dx == dy == 0:
        return math.dist(p, a)
    t = max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / (dx * dx + dy * dy)))
    return math.dist(p, (a[0] + t * dx, a[1] + t * dy))


def densify(pts, step):
    """The polyline with points at most step metres apart (the corners kept)."""
    out = [tuple(pts[0])]
    for a, b in zip(pts, pts[1:]):
        n = max(1, int(math.ceil(math.dist(a, b) / step)))
        out += [(a[0] + (b[0] - a[0]) * i / n, a[1] + (b[1] - a[1]) * i / n) for i in range(1, n + 1)]
    return out


def point_in(p, ring):
    """Is the point inside the polygon (ray casting)?"""
    c = False
    for (xi, yi), (xj, yj) in zip(ring, ring[-1:] + ring[:-1]):
        if (yi > p[1]) != (yj > p[1]) and p[0] < (xj - xi) * (p[1] - yi) / (yj - yi) + xi:
            c = not c
    return c


def nearest_on(p, a, b):
    """The point of segment a–b nearest to p."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    L2 = dx * dx + dy * dy
    t = 0.0 if not L2 else max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / L2))
    return (a[0] + t * dx, a[1] + t * dy)


def simplify(pts, tol):
    """Douglas–Peucker on an open polyline – the small notches of a cadastral boundary go, the real bends stay."""
    if len(pts) < 3:
        return list(pts)
    d, i = max((dist_seg(pts[k], pts[0], pts[-1]), k) for k in range(1, len(pts) - 1))
    if d <= tol:
        return [pts[0], pts[-1]]
    return simplify(pts[:i + 1], tol)[:-1] + simplify(pts[i:], tol)


def cross_lines(a, b, c, d):
    """The crossing of the lines a–b and c–d (None when they are parallel)."""
    den = (a[0] - b[0]) * (c[1] - d[1]) - (a[1] - b[1]) * (c[0] - d[0])
    if abs(den) < 1e-9:
        return None
    t = ((a[0] - c[0]) * (c[1] - d[1]) - (a[1] - c[1]) * (c[0] - d[0])) / den
    return (a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1]))


def segments_cross(ring):
    """Does the closed ring cross itself?"""
    n = len(ring)
    segs = [(ring[i], ring[(i + 1) % n]) for i in range(n)]
    def ccw(a, b, c):
        return (c[1] - a[1]) * (b[0] - a[0]) - (b[1] - a[1]) * (c[0] - a[0])
    for i in range(n):
        for j in range(i + 2, n):
            if i == 0 and j == n - 1:
                continue
            (a, b), (c, d) = segs[i], segs[j]
            if ccw(a, b, c) * ccw(a, b, d) < 0 and ccw(c, d, a) * ccw(c, d, b) < 0:
                return True
    return False


def fence_set_back(fence, street_rings, d, tol=1.0, near=1.0):
    """The fence moved d metres into the parcel along the street parcels it borders – a sidewalk between the
    street's edge and the fence. Returns (new fence, number of edges moved) or (None, 0) when nothing borders a
    street or the result would cross itself."""
    n = len(fence)
    signed = sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(fence, fence[1:] + fence[:1])) / 2
    inward = 1 if signed > 0 else -1                   # left of the direction for a counter-clockwise ring
    edges = [(fence[i], fence[(i + 1) % n]) for i in range(n)]
    def on_street(e):
        m = ((e[0][0] + e[1][0]) / 2, (e[0][1] + e[1][1]) / 2)
        return any(min(dist_seg(m, p, q) for p, q in zip(r, r[1:] + r[:1])) <= near for r in street_rings)
    flag = [on_street(e) for e in edges]
    if not any(flag):
        return None, 0
    if all(flag):                                      # walled in by streets on every side
        start = 0
    else:
        start = next(i for i in range(n) if flag[i] and not flag[i - 1])
    out, moved, i = [], 0, start
    order = [(start + k) % n for k in range(n)]
    runs, cur = [], []
    for k in order:
        if flag[k]:
            cur.append(k)
        elif cur:
            runs.append(cur)
            cur = []
    if cur:
        runs.append(cur)
    new = [list(p) for p in fence]
    replace = {}                                       # first vertex index of a run -> (last vertex index, new points)
    for run in runs:
        verts = [fence[run[0]]] + [fence[(k + 1) % n] for k in run]
        verts = simplify(verts, tol)
        segs = []
        for a, b in zip(verts, verts[1:]):
            L = math.dist(a, b)
            if L < 1e-6:
                continue
            nx, ny = -(b[1] - a[1]) / L * inward * d, (b[0] - a[0]) / L * inward * d
            segs.append(((a[0] + nx, a[1] + ny), (b[0] + nx, b[1] + ny)))
        if not segs:
            continue
        pts = []
        prev_e = edges[(run[0] - 1) % n]
        next_e = edges[(run[-1] + 1) % n]
        if len(runs) == 1 and len(run) == n:
            pts.append(cross_lines(*segs[-1], *segs[0]) or segs[0][0])
        else:
            pts.append(cross_lines(*prev_e, *segs[0]) or segs[0][0])
        for s1, s2 in zip(segs, segs[1:]):
            pts.append(cross_lines(*s1, *s2) or s1[1])
        if not (len(runs) == 1 and len(run) == n):
            pts.append(cross_lines(*segs[-1], *next_e) or segs[-1][1])
        replace[run[0]] = ((run[-1] + 1) % n, pts)
        moved += len(run)
    if len(runs) == 1 and len(runs[0]) == n:
        ring = [[round(x, 2), round(y, 2)] for x, y in replace[runs[0][0]][1]]
    else:
        ring, k, seen = [], start, 0
        while seen < n:
            if k in replace:
                last, pts = replace[k]
                ring += [[round(x, 2), round(y, 2)] for x, y in pts]
                steps = (last - k) % n
                k, seen = (last + 1) % n, seen + steps + 1
            else:
                ring.append(new[k])
                k, seen = (k + 1) % n, seen + 1
    if len(ring) < 3 or segments_cross(ring):
        return None, 0
    return ring, moved


# ── the orthophoto of КАИС (МЗХ, published by АГКК) – working material for the entrances, never on the sheet ──────
ORTO_LEVEL = 11                   # 0,132 m a pixel; level 10 (0,265 m) when the frame is large
ORTO_MAX_TILES = 64
ORTO_ZNAK_M = 10.0                # a numbered point on the fence every this many metres
# the tile scheme of the orthophoto services of АГКК (ArcGIS ImageServer, КС2005, 256 px) – the same for all editions
ORTO_INFO = {"origin": [-36179500.0, 48335300.0], "tile": 256,
             "lods": [[8, 1.3229193125052918], [9, 0.5291677250021167], [10, 0.26458386250105836],
                      [11, 0.13229193125052918]]}
ORTO_SLOEVE = ["2025", "2022"]   # 2023–2025 and 2020–2022, newest first; n8n knows the service of each


def orto_tiles(x0, y0, x1, y1, info):
    """The tiles (row, col) of the tile scheme that cover the frame, at the finest level that stays under
    ORTO_MAX_TILES; info = {"origin": [x, y], "lods": [[level, resolution], …], "tile": 256}."""
    ox, oy = info["origin"]
    for level, res in sorted(info["lods"], key=lambda l: -l[0]):
        if level > ORTO_LEVEL:
            continue
        span = info.get("tile", 256) * res
        c0, c1 = int((x0 - ox) // span), int((x1 - ox) // span)
        r0, r1 = int((oy - y1) // span), int((oy - y0) // span)
        if (c1 - c0 + 1) * (r1 - r0 + 1) <= ORTO_MAX_TILES:
            return level, res, [(r, c) for r in range(r0, r1 + 1) for c in range(c0, c1 + 1)]
    return None, None, []


def orto_picture(res, x0, y0, x1, y1, png, rings=(), buildings=(), fence=None, step=ORTO_ZNAK_M):
    """Stitches the tiles from n8n into one picture of the frame and draws on it the parcel, the buildings
    and numbered points along the fence (every `step` m) – so an entrance seen on the photo is named by its
    number. Returns the numbered points in КС2005 [(n, x, y)]."""
    import io
    from PIL import Image, ImageDraw, ImageFont
    ox, oy = res["origin"]
    rsl, size = res["res"], res.get("tile", 256)
    span = size * rsl
    tiles = res.get("tiles") or []
    if res.get("png_base64"):                          # stitched by n8n: one picture from tile (r0, c0)
        big = Image.open(io.BytesIO(base64.b64decode(res["png_base64"]))).convert("RGB")
        r_min, c_min = res["r0"], res["c0"]
    elif tiles:                                        # the tiles themselves – stitched here
        r_min, c_min = min(t["r"] for t in tiles), min(t["c"] for t in tiles)
        W = (max(t["c"] for t in tiles) - c_min + 1) * size
        H = (max(t["r"] for t in tiles) - r_min + 1) * size
        big = Image.new("RGB", (W, H), (255, 255, 255))
        for t in tiles:
            try:
                im = Image.open(io.BytesIO(base64.b64decode(t["b64"]))).convert("RGB")
            except Exception:
                continue
            big.paste(im, ((t["c"] - c_min) * size, (t["r"] - r_min) * size))
    else:
        return None
    gx0, gy1 = ox + c_min * span, oy - r_min * span                  # the top-left corner of the mosaic
    def px(x, y):
        return ((x - gx0) / rsl, (gy1 - y) / rsl)
    a, b = px(x0, y1)
    c, d = px(x1, y0)
    pic = big.crop((int(a), int(b), int(c), int(d)))
    dx, dy = int(a), int(b)
    pic.save(os.path.splitext(png)[0] + "_chisto.png")    # the photo itself, without marks – for orto_zeleno()
    def pp(x, y):
        u, v = px(x, y)
        return (u - dx, v - dy)
    draw = ImageDraw.Draw(pic)
    w_ = max(2, int(pic.width / 400))
    for ring in rings:
        draw.line([pp(*p) for p in ring + ring[:1]], fill=(0, 200, 255), width=w_ + 1)
    for ring in buildings:
        draw.line([pp(*p) for p in ring + ring[:1]], fill=(255, 210, 0), width=w_)
    marks = []
    if fence:
        try:
            font = ImageFont.truetype("DejaVuSans-Bold.ttf", max(14, int(pic.width / 45)))
        except OSError:
            font = ImageFont.load_default()
        ring = fence + fence[:1]
        pts = densify(ring, 0.5)
        n, acc, last = 1, 0.0, pts[0]
        marks.append((n, last[0], last[1]))
        for q in pts[1:]:
            acc += math.dist(last, q)
            last = q
            if acc >= step and math.dist(q, pts[0]) > step / 2:     # not again on the first point
                n, acc = n + 1, 0.0
                marks.append((n, q[0], q[1]))
        r_ = max(4, w_ * 2)
        for n, x, y in marks:
            u, v = pp(x, y)
            draw.ellipse((u - r_, v - r_, u + r_, v + r_), fill=(255, 40, 40), outline=(255, 255, 255))
            draw.text((u + r_ + 2, v - r_ - 2), str(n), fill=(255, 255, 255), font=font,
                      stroke_width=3, stroke_fill=(0, 0, 0))
    pic.save(png)
    return marks


_OSM = {}


def osm_map(x0, y0, x1, y1):
    """The OpenStreetMap data of the frame (КС2005) – (xml root, "") or (None, error text); fetched once per frame."""
    import xml.etree.ElementTree as ET
    key = (round(x0), round(y0), round(x1), round(y1))
    if key in _OSM:
        return _OSM[key]
    corners = [kc_to_wgs(x, y) for x, y in ((x0, y0), (x1, y0), (x0, y1), (x1, y1))]
    la = [c[0] for c in corners]
    lo = [c[1] for c in corners]
    url = (f"https://api.openstreetmap.org/api/0.6/map?bbox={min(lo):.6f},{min(la):.6f},{max(lo):.6f},{max(la):.6f}")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "fire-service/kais"})
        with urllib.request.urlopen(req, timeout=60) as r:
            _OSM[key] = (ET.fromstring(r.read()), "")
    except (urllib.error.URLError, OSError, ET.ParseError) as e:
        _OSM[key] = (None, f"{e}")
    return _OSM[key]


def osm_grass(x0, y0, x1, y1):
    """The grass areas (landuse=grass/meadow, leisure=park, village_green) in the frame, as rings in КС2005 –
    from the OpenStreetMap API ([], error text) on failure."""
    root, err = osm_map(x0, y0, x1, y1)
    if root is None:
        return [], err
    nodes = {n.get("id"): (float(n.get("lat")), float(n.get("lon"))) for n in root.iter("node")}
    out = []
    for w in root.iter("way"):
        tags = {t.get("k"): t.get("v") for t in w.iter("tag")}
        if not (tags.get("landuse") in ("grass", "meadow", "village_green") or tags.get("leisure") == "park"):
            continue
        refs = [nd.get("ref") for nd in w.iter("nd")]
        if len(refs) < 4 or refs[0] != refs[-1] or not all(r_ in nodes for r_ in refs):
            continue
        out.append([list(wgs_to_kc(*nodes[r_])) for r_ in refs[:-1]])
    return out, ""


# the paving round a building (m): no lawn is drawn closer to a wall – the sidewalk under the crowns is not seen
TROTOAR_SGRADA_M = 2.0

# the width an alley is drawn with (m) – OpenStreetMap seldom gives it
PATH_WIDTH = {"footway": 2.5, "path": 2.0, "pedestrian": 4.0, "cycleway": 2.0, "service": 4.0, "living_street": 5.0}


def orto_zeleno(png, x0, y0, x1, y1, inside=None, cell=0.5, minus=None):
    """The green of the orthophoto (grass, trees) as rings in КС2005 – what is not green (the alleys, the paved areas
    round the buildings, the roofs) stays out, so that the paths people and the vehicles use show between them.
    `png` is the clean photo of the frame x0..x1, y0..y1 (orto_picture … _chisto.png); `inside` – a shapely geometry
    the result is cut to. Approximate: a path under the crowns of the trees is not seen."""
    import numpy as np
    from PIL import Image
    from shapely.geometry import box, Polygon as _Pa
    from shapely.ops import unary_union
    im = np.asarray(Image.open(png).convert("RGB")).astype(float)
    H, W = im.shape[:2]
    sx, sy = (x1 - x0) / W, (y1 - y0) / H
    k = max(1, int(round(cell / sx)))
    h_, w_ = H // k, W // k
    im = im[:h_ * k, :w_ * k].reshape(h_, k, w_, k, 3).mean(axis=(1, 3))
    r, g, b = im[..., 0], im[..., 1], im[..., 2]
    green = (2 * g - r - b > 14) & (g > r)             # the excess green – grass and the crowns of trees
    shade = (r + g + b) / 3 < 62                        # the shadow of a tree – on grass more often than not
    # grey – paving, a plaza (measured on the photo: paving spread ≤ 10, lawn 20–30 – also the dry lawn)
    paved = ((im.max(axis=2) - im.min(axis=2)) < 14) & ((r + g + b) / 3 > 105) & (2 * g - r - b < 12)
    def cells_of(mask):
        return unary_union([box(x0 + j * k * sx, y1 - (i + 1) * k * sy, x0 + (j + 1) * k * sx, y1 - i * k * sy)
                            for i, j in zip(*np.nonzero(mask))])
    # the green and the shadows, closed over the small gaps (a shadow, a bench), then the paving taken out:
    #   what is left is the lawn as one sees it – with the alleys and the plaza between the pieces
    g_ = cells_of(green | (shade & ~paved)).buffer(1.2).buffer(-1.5).buffer(0.3)
    pv = cells_of(paved)
    if not pv.is_empty:
        g_ = g_.difference(pv.buffer(0.4).buffer(-0.8).buffer(0.4))          # only real paved areas, not a speck
    if minus is not None and not minus.is_empty:       # the alleys of OpenStreetMap (under the crowns too), buildings
        g_ = g_.difference(minus)
    g_ = g_.buffer(0.3).buffer(-0.6).buffer(0.3).simplify(0.4)
    if inside is not None:
        g_ = g_.intersection(inside)
    out = []
    for part in getattr(g_, "geoms", [g_]):
        if part.geom_type != "Polygon" or part.area < 6:
            continue
        holes = []
        for h in part.interiors:                        # a hole is kept only where it is paved (a path, a plaza) –
            hp = _Pa(h.coords)                          #   a dry or shaded patch of the lawn stays lawn
            if hp.area > 2 and (pv.is_empty is False) and hp.intersection(pv).area > 0.5 * hp.area:
                holes.append([list(p) for p in h.coords][:-1])
            elif minus is not None and hp.area > 2 and hp.intersection(minus).area > 0.3 * hp.area:
                holes.append([list(p) for p in h.coords][:-1])
        out.append({"kontur": [list(p) for p in part.exterior.coords][:-1], "otvori": holes})
    return out


def osm_paths(x0, y0, x1, y1):
    """The alleys and paths (highway=footway/path/pedestrian/cycleway/service/living_street) in the frame – the ways
    through the grass and round the buildings that people and the vehicles use; КАИС does not have them. As axes in
    КС2005 with a width – ([{"tochki", "shirina", "vid"}], "") or ([], error text)."""
    root, err = osm_map(x0, y0, x1, y1)
    if root is None:
        return [], err
    nodes = {n.get("id"): (float(n.get("lat")), float(n.get("lon"))) for n in root.iter("node")}
    out = []
    for w in root.iter("way"):
        tags = {t.get("k"): t.get("v") for t in w.iter("tag")}
        hw = tags.get("highway")
        refs = [nd.get("ref") for nd in w.iter("nd")]
        if hw not in PATH_WIDTH or len(refs) < 2 or not all(r_ in nodes for r_ in refs) or tags.get("area") == "yes":
            continue
        try:
            width = float(str(tags.get("width", "")).replace(",", ".").split()[0])
        except (ValueError, IndexError):
            width = PATH_WIDTH[hw]
        out.append({"tochki": [list(wgs_to_kc(*nodes[r_])) for r_ in refs], "shirina": width, "vid": hw})
    return out, ""


# the width a waterway is drawn with when OpenStreetMap gives none (m) – the sign „Река, канал“ of Приложение № 6
WATERWAY_WIDTH = {"river": 10.0, "canal": 6.0, "stream": 4.0, "ditch": 2.0, "drain": 2.0}


def osm_water(x0, y0, x1, y1):
    """The rivers, canals and streams (waterway=*, not in a tunnel) as axes in КС2005 with name and width, and the
    lakes and ponds (natural=water) as rings – ({"reki": [...], "ezera": [...]}, "") or (None, error text)."""
    root, err = osm_map(x0, y0, x1, y1)
    if root is None:
        return None, err
    nodes = {n.get("id"): (float(n.get("lat")), float(n.get("lon"))) for n in root.iter("node")}
    reki, ezera = [], []
    for w in root.iter("way"):
        tags = {t.get("k"): t.get("v") for t in w.iter("tag")}
        refs = [nd.get("ref") for nd in w.iter("nd")]
        if not all(r_ in nodes for r_ in refs) or len(refs) < 2:
            continue
        pts = [list(wgs_to_kc(*nodes[r_])) for r_ in refs]
        wt = tags.get("waterway")
        if wt in WATERWAY_WIDTH and tags.get("tunnel") not in ("yes", "culvert") and tags.get("layer", "0")[:1] != "-":
            try:
                width = float(str(tags.get("width", "")).replace(",", ".").split()[0])
            except (ValueError, IndexError):
                width = WATERWAY_WIDTH[wt]
            name = tags.get("name:bg") or tags.get("name") or ""
            reki.append({"tochki": pts, "shirina": round(min(max(width, 1.5), 40.0), 1),
                         "ime": ("р. " + name) if name and wt == "river" or (name and wt == "stream") else name})
        elif tags.get("natural") == "water" and tags.get("water") not in ("river", "canal", "stream") \
                and refs[0] == refs[-1] and len(refs) >= 4:
            ezera.append({"kontur": pts[:-1], "ime": tags.get("name:bg") or tags.get("name") or ""})
    joined = {}                                         # one river is often several ways – join them by name and ends
    for r in reki:
        joined.setdefault((r["ime"], r["shirina"]), []).append(r["tochki"])
    out = []
    for (name, width), parts in joined.items():
        parts = [list(p) for p in parts]
        while parts:
            line = parts.pop(0)
            grew = True
            while grew:
                grew = False
                for i, q in enumerate(parts):
                    if math.dist(line[-1], q[0]) < 0.5:
                        line += q[1:]
                    elif math.dist(line[0], q[-1]) < 0.5:
                        line = q[:-1] + line
                    elif math.dist(line[-1], q[-1]) < 0.5:
                        line += q[::-1][1:]
                    elif math.dist(line[0], q[0]) < 0.5:
                        line = q[::-1][:-1] + line
                    else:
                        continue
                    parts.pop(i)
                    grew = True
                    break
            out.append({"tochki": line, "shirina": width, "ime": name})
    return {"reki": out, "ezera": ezera}, ""


def street_name(name, ulitsa=True):
    """„бул. Русе“ → „бул. „Русе““ – the plugin's typography for street names; a street name without its kind
    („Иван Миндиликов“, as КАИС and OpenStreetMap often give it) gets „ул.“ in front: „ул. „Иван Миндиликов““.
    ulitsa=False – a place (ж.к., квартал): the name stays as it is."""
    name = name.strip()
    if not name:
        return name
    m = re.match(r"^(ул\.|бул\.|пл\.|ж\.к\.|кв\.)\s*(.+)$", name)
    if not m:
        if not ulitsa or re.match(r"^(ул|бул|пл|площад|улица|булевард|път|шосе|АМ|автомагистрала)\b", name, re.I) \
                or re.match(r"^[IVX]+-\d", name) or re.search(r"\b(зона|квартал|парк|местност)\b", name, re.I):
            return name
        core = name.strip('"“”„')
        return "ул. „" + core + "“"
    if m.group(2).startswith("„"):
        return name
    core = m.group(2).strip('"“”')
    return m.group(1) + " „" + core + "“"


def local(ring, x0, y0):
    pts = [[round(p[0] - x0, 2), round(p[1] - y0, 2)] for p in ring]
    if len(pts) > 1 and pts[0] == pts[-1]:
        pts = pts[:-1]
    return pts


def label(s):
    """„Промишлена сграда“ – the purpose as КАИС gives it, first letter capital."""
    p = (s.get("predn") or "Сграда").strip()
    return p[:1].upper() + p[1:]


# ── commands ─────────────────────────────────────────────────────────────────────────────────────────────────
def point_of(a):
    if a.link:
        import marshrut  # noqa: E402  (follows short links, reads !3d…!4d…, q=…, @lat,lon)
        return marshrut.from_link(a.link)
    if a.lat is not None and a.lon is not None:
        return a.lat, a.lon
    return None


def water(lat, lon, radius_m):
    """The exact water sources within radius_m of the point – via voda.py (personal key)."""
    script = os.path.join(HERE, "voda.py")
    r = subprocess.run([sys.executable, script, "blizo", "--lat", f"{lat:.7f}", "--lon", f"{lon:.7f}", "--broi", "25",
                        "--radius-m", str(int(radius_m)), "--json"], capture_output=True, text=True, timeout=180)
    if r.returncode != 0:
        return None, (r.stderr or r.stdout).strip().splitlines()[-1:] or ["voda.py не отговори"]
    try:
        return json.loads(r.stdout).get("vodoiztochnitsi", []), []
    except ValueError:
        return None, ["voda.py върна неочакван отговор"]


def cmd_obekt(a):
    body = {"action": "obekt", "fon": bool(a.fon), "radius_m": a.radius}
    p = point_of(a)
    if a.id:
        body["id"] = a.id.strip()
    elif p:
        body["lat"], body["lon"] = p
    else:
        fail("BAD_INPUT", "дай --id, или --lat и --lon, или --link")
    res = call(body)
    out = os.path.abspath(a.out)
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    fon_png = None
    fon = res.pop("fon", None)
    if fon and fon.get("png_base64") and a.fon:
        fon_png = os.path.splitext(out)[0] + "_fon.png"
        with open(fon_png, "wb") as f:
            f.write(base64.b64decode(fon["png_base64"]))
        res["fon"] = {k: v for k, v in fon.items() if k != "png_base64"} | {"png": fon_png}
    res["data_na_spravkata"] = datetime.date.today().strftime("%d.%m.%Y")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)

    imot, sgradi = res["imot"], res.get("sgradi") or []
    notes = list(res.get("zabelezhki") or [])
    summary = {
        "imot": {k: imot.get(k) for k in ("id", "adres", "ntp", "plosht_m2", "teritoriya", "sobstvenost") if imot.get(k)},
        "sgradi": [], "kais_json": out, "fon": fon_png,
    }
    for s in sgradi:
        d = dims(s.get("kontur") or [])
        summary["sgradi"].append({"id": s["id"], "predn": s.get("predn"), "etazhi": s.get("etazhi"),
                                  "zastroena_m2": s.get("zastroena_m2"), "razmeri_m": list(d) if d[0] else None})

    if a.shema:
        fx0, fy0, fx1, fy1 = res["ramka"]["bbox"]          # the picture: a square around the parcel
        ring = imot.get("kontur") or []
        r = res["ramka"].get("radius_m", a.radius)
        # the terrain: the parcel's own extent plus the radius – a rectangle, so the sheet's scale stays large
        bx0 = math.floor(min(p[0] for p in ring) - r) if ring else fx0
        by0 = math.floor(min(p[1] for p in ring) - r) if ring else fy0
        bx1 = math.ceil(max(p[0] for p in ring) + r) if ring else fx1
        by1 = math.ceil(max(p[1] for p in ring) + r) if ring else fy1

        # the water sources (exact ones only): those in the terrain, and the nearest one even outside it – the
        # scheme must show where the water is (чл. 7, ал. 3, т. 1, б. „в“ и „г“), so the terrain grows to it
        hydrants, far_hydrant = [], None
        if a.voda:
            clat, clon = kc_to_wgs((bx0 + bx1) / 2, (by0 + by1) / 2)
            rows, errs = water(clat, clon, max(400.0, math.hypot(bx1 - bx0, by1 - by0) / 2))
            if rows is None:
                notes.append("Водоизточниците не се взеха: " + "; ".join(errs))
            else:
                exact = []
                for row in rows:
                    if row.get("tochnost") in EXACT:
                        x, y = wgs_to_kc(float(row["lat"]), float(row["lon"]))
                        exact.append((x, y, row))
                inside = [h for h in exact if bx0 <= h[0] <= bx1 and by0 <= h[1] <= by1]
                hydrants = inside or exact[:1]
                if not inside and exact and not a.hidrant_v_terena:
                    hx_, hy_ = exact[0][0], exact[0][1]
                    out_m = math.hypot(max(bx0 - hx_, 0, hx_ - bx1), max(by0 - hy_, 0, hy_ - by1))
                    if out_m > DALECH_HIDRANT_M:       # growing the terrain that far shrinks the object to nothing –
                        far_hydrant, hydrants = exact[0], []   #   a pointer on the terrain's edge instead
                for x, y, _ in hydrants:
                    bx0, by0 = min(bx0, math.floor(x - 10)), min(by0, math.floor(y - 10))
                    bx1, by1 = max(bx1, math.ceil(x + 10)), max(by1, math.ceil(y + 10))
                if not exact:
                    notes.append("Няма водоизточници с точни координати до 400 m – виж vodoiztochnitsi за по-далечните.")
                elif far_hydrant:
                    notes.append("Най-близкият хидрант е далеч извън терена – "
                                 "теренът не е разширен до него (обектът щеше да стане нечетим); на ръба на терена откъм "
                                 "хидранта е надпис с вида, разстоянието, посоката и адреса му, а водопроводът (по улицата на "
                                 "хидранта) остава извън листа. `--hidrant-v-terena` – теренът да се разшири до него.")
                elif not inside:
                    notes.append(f"В имота и около него няма хидрант – начертан е най-близкият ({round(exact[0][2].get('razstoyanie_m', 0))} m "
                                 "по права линия), теренът е разширен до него.")
        w, h = bx1 - bx0, by1 - by0
        sh = {
            "teren": [w, h],
            "kais": {"x0": bx0, "y0": by0, "imot": imot["id"], "data": res["data_na_spravkata"]},
            "sgradi": [],
        }
        if ring:                                       # the turned, cut terrain keeps the whole parcel ("zavartane")
            sh["teren_tochki"] = local(ring, bx0, by0)
        if a.granitsa and not a.bez_granitsa:          # the parcel's boundary only on request – by default not drawn
            sh["imot"] = {"kontur": local(ring, bx0, by0), "etiket": f"ПИ {imot['id']}"}
        if a.ograda and ring:                          # a fenced parcel: the boundary is the fence (as at ЗИТА)
            sh["ograda"] = local(ring, bx0, by0)
            if a.ograda != "da":
                sh["ograda_vid"] = a.ograda
        if fon_png and a.fon:
            sh["fon"] = {"png": fon_png, "ramka": [fx0 - bx0, fy0 - by0, fx1 - bx0, fy1 - by0]}
        for s in sgradi:
            if not s.get("kontur"):
                continue
            b = {"kontur": local(s["kontur"], bx0, by0), "etiket": label(s), "kais_id": s["id"]}
            if (dims(s["kontur"])[1] or 0) < SMALL_M:      # an annex: no name and no dimension lines over its neighbour
                b["etiket"], b["razmeri"], b["kratko"] = "", False, True
            if s.get("etazhi"):
                b["etazhnost"] = f"+{s['etazhi']}"
            sh["sgradi"].append(b)
        # the neighbouring buildings (чл. 7, ал. 3, т. 1, б. „е“): the buildings of the parcels that border the
        # object, from КАИС as well – thin outlines with their floors; those wholly outside the terrain stay out
        if not a.bez_sasedni:
            street_ids = {r.get("id") for r in res.get("ulitsi_kais") or []}
            seen, near, failed = {s["id"] for s in sgradi}, [], 0
            for pid in [i for i in imot.get("sasedi") or [] if i not in street_ids][:MAX_SASEDI]:
                try:
                    nb = call({"action": "obekt", "id": pid, "fon": False, "radius_m": 30})
                except SystemExit:
                    failed += 1
                    continue
                for s in nb.get("sgradi") or []:
                    k = s.get("kontur") or []
                    if s.get("id") in seen or not k or (dims(k)[1] or 0) < SMALL_M:
                        continue
                    if not any(bx0 <= x <= bx1 and by0 <= y <= by1 for x, y in densify(k + k[:1], 2.0)):
                        continue
                    seen.add(s["id"])
                    b = {"kontur": local(k, bx0, by0), "etiket": label(s), "kais_id": s["id"], "sasedna": True}
                    if s.get("etazhi"):
                        b["etazhnost"] = f"+{s['etazhi']}"
                    sh["sgradi"].append(b)
                    near.append({"id": s["id"], "predn": s.get("predn"), "etazhi": s.get("etazhi"),
                                 "zastroena_m2": s.get("zastroena_m2")})
            summary["sasedni"] = near
            if near:
                notes.append("Съседните сгради са от граничещите имоти в КАИС с предназначението им; името на обекта в тях "
                             "(магазин, фирма) кадастърът няма – допиши го в етикета, ако се знае.")
            if failed:
                notes.append(f"{failed} от граничещите имоти не се прочетоха от КАИС – сградите им липсват.")

        if any(s.get("etazhi") for s in sgradi):
            notes.append("Етажността е „брой етажи“ от КАИС (надземните); сутерен, тавански етаж, категорията и "
                         "огнеустойчивостта не са в кадастъра – провери ги на място или в документацията на обекта.")

        # the streets: the street parcels of КАИС (exact outlines); their names – from OpenStreetMap, which also
        # gives what КАИС lacks (a street that runs over no street parcel). The two are never drawn over each other.
        roads = [r for r in res.get("ulitsi_kais") or [] if r.get("kontur")]
        osm = res.get("ulitsi") or []
        streets, names_used = [], set()

        def named_piece(ways):
            """(name, middle, angle) of the longest piece inside the terrain of the named ways given."""
            best = None
            for u in ways:
                if not u.get("ime"):
                    continue
                for piece in clip_polyline(u.get("tochki") or [], bx0, by0, bx1, by1):
                    for a_, b_ in zip(piece, piece[1:]):
                        d = math.dist(a_, b_)
                        if best is None or d > best[0]:
                            best = (d, u["ime"], a_, b_)
            if not best:
                return None
            _, name, a_, b_ = best
            return (street_name(name), [round((a_[0] + b_[0]) / 2 - bx0, 1), round((a_[1] + b_[1]) / 2 - by0, 1)],
                    round(math.degrees(math.atan2(b_[1] - a_[1], b_[0] - a_[0])), 1))

        for r in roads:
            st = {"kontur": local(r["kontur"], bx0, by0), "otvori": [local(h, bx0, by0) for h in (r.get("otvori") or [])],
                  "ime": "", "kais_id": r["id"]}
            tag = named_piece([u for u in osm if u.get("kais") == r["id"]])
            if tag and tag[0] not in names_used:
                st["ime"], st["ime_pos"], st["ime_ugal"] = tag
                names_used.add(tag[0])
            elif tag:
                st["ime_ulitsa"] = tag[0]              # the same street – its name may go here if it fits better
            streets.append(st)
        rings = [r["kontur"] for r in roads]
        complement = []
        for u in osm:
            if u.get("kais"):
                continue
            for piece in clip_polyline(u.get("tochki") or [], bx0, by0, bx1, by1):
                # only the parts of the line that lie outside every street parcel – what КАИС does not have
                piece = densify(piece, 2.0)
                part = []
                for a_, b_ in zip(piece, piece[1:]):
                    mid = ((a_[0] + b_[0]) / 2, (a_[1] + b_[1]) / 2)
                    if any(point_in(mid, ring) for ring in rings):
                        if len(part) > 1:
                            complement.append((u, part))
                        part = []
                        continue
                    part = part + [b_] if part else [a_, b_]
                if len(part) > 1:
                    complement.append((u, part))
        inner_dropped = 0
        if ring and not a.s_vatreshni:                 # unnamed roads inside the parcel – driveways and parking aisles of
            kept = []                                  #   an asphalt yard, not streets: left out (with a note)
            for u, part in complement:
                inside = sum(point_in(p_, ring) for p_ in part) / len(part)
                if not u.get("ime") and inside >= 0.5:
                    inner_dropped += 1
                    continue
                kept.append((u, part))
            complement = kept
        if inner_dropped:
            notes.append(f"{inner_dropped} пътя без име от OpenStreetMap вътре в имота не са начертани – алеи и паркинг "
                         "на асфалтиран плац (`--s-vatreshni` ги връща); надпиши плаца, напр. „асфалтиран плац с паркинг“.")
        for u, part in complement:
            if length(part) > 3:
                name = street_name(u.get("ime") or "")
                streets.append({"tochki": [[round(x - bx0, 1), round(y - by0, 1)] for x, y in part],
                                "shirina": u.get("shirina") or 6, "ime": "" if name in names_used else name, "_len": length(part)})
                if name:
                    streets[-1]["ime_ulitsa"] = name   # every piece knows its street: the name goes where it fits
        for name in {st["ime"] for st in streets if "tochki" in st and st["ime"]}:
            same = [st for st in streets if "tochki" in st and st["ime"] == name]
            longest = max(same, key=lambda st: st["_len"])
            for st in same:
                if st is not longest:
                    st["ime"] = ""
        for st in streets:
            st.pop("_len", None)
        if streets:
            sh["ulitsi"] = streets
            summary["ulitsi"] = {
                "ot_kais": [{"id": st["kais_id"], "ime": st["ime"] or None} for st in streets if "kontur" in st],
                "ot_osm": sorted({st["ime"] or "(без име)" for st in streets if "tochki" in st}),
            }
            if any("tochki" in st for st in streets):
                notes.append("Улиците са по поземлените имоти от КАИС; там, където в кадастъра няма имот за улица, са "
                             "допълнени от OpenStreetMap (осови линии, приблизителни). Имената са от OpenStreetMap.")
            else:
                notes.append("Улиците са по поземлените имоти от КАИС; имената им – от OpenStreetMap.")
        elif "ulitsi" in res or "ulitsi_kais" in res:
            notes.append("Около обекта няма улици нито в КАИС, нито в OpenStreetMap – начертай ги на ръка.")

        # the sidewalk (--trotoar): the fence set back from the edge of the street parcels it borders, so the
        # sidewalk shows between the street and the fence (approved on ДГ „Снежанка“, Плевен)
        if a.trotoar and sh.get("ograda"):
            want = [w_.strip().lower() for w_ in a.trotoar_ulitsa or [] if w_.strip()]
            st_rings = [st["kontur"] for st in streets if "kontur" in st
                        and (not want or any(w_ in (st.get("ime") or "").lower() or w_ == st.get("kais_id") for w_ in want))]
            fence, moved = fence_set_back(sh["ograda"], st_rings, a.trotoar)
            if fence:
                sh["ograda"] = fence
                summary["trotoar_m"] = a.trotoar
                notes.append(f"Оградата е отместена на {a.trotoar:g} m навътре от ръба на улицата ({moved} страни) – "
                             "тротоарът се вижда между тях; ширината е приета – провери я. Порталите (`vhodove`) се "
                             "слагат върху новата ограда, а `prohodi` – на ръба на улицата.")
            else:
                notes.append("--trotoar: оградата не граничи с улица от КАИС (или отместването би я пресякло) – "
                             "оставена е по границата на имота.")

        # the orthophoto (--ortofoto): where the entrances, the gates and the yard are – the photo of МЗХ from
        # КАИС, in КС2005 like everything here; numbered points on the fence name an entrance seen on it
        orto_trevni = None
        if a.ortofoto:
            ring_l = sh.get("ograda") or (local(ring, bx0, by0) if ring else [])
            pts_kc = [(p[0] + bx0, p[1] + by0) for p in ring_l] or [(p[0], p[1]) for s in sgradi for p in s.get("kontur") or []]
            if pts_kc:
                m_ = 15.0
                ox0, oy0 = min(p[0] for p in pts_kc) - m_, min(p[1] for p in pts_kc) - m_
                ox1, oy1 = max(p[0] for p in pts_kc) + m_, max(p[1] for p in pts_kc) + m_
                level, rsl, tl = orto_tiles(ox0, oy0, ox1, oy1, ORTO_INFO)
                sloeve = ORTO_SLOEVE if a.ortofoto == "nai-novo" else [a.ortofoto]
                o = None
                for sloi in sloeve:                    # the newest edition that covers the place
                    try:
                        o = call({"action": "ortofoto", "sloi": sloi, "level": level, "tiles": [[r, c] for r, c in tl],
                                  "stitch": True})
                    except SystemExit:
                        o = None
                    got = o.get("broi", len(o.get("tiles") or [])) if o else 0
                    if o and (o.get("png_base64") or o.get("tiles")) and got >= len(tl) * 0.8:
                        o.update({"origin": ORTO_INFO["origin"], "res": rsl, "tile": ORTO_INFO["tile"],
                                  "godina": o.get("godina") or sloi})
                        break
                    o = None
                if o:
                    png = os.path.splitext(os.path.abspath(a.shema))[0] + "_ortofoto.png"
                    marks = orto_picture(o, ox0, oy0, ox1, oy1, png,
                                         rings=[ring] if ring else [],
                                         buildings=[s["kontur"] for s in sgradi if s.get("kontur")],
                                         fence=pts_kc if ring_l else None)
                    if a.trevni_ortofoto:              # the grass from the photo – the alleys between it are seen
                        from shapely.geometry import Polygon as _P, box as _box
                        frame_ = _box(ox0, oy0, ox1, oy1)
                        from shapely.ops import unary_union as _uu
                        from shapely.geometry import LineString as _LSz
                        # the buildings with the paving round them (a sidewalk ~2 m – the crowns of the trees hide it)
                        cut = [_P(s["kontur"]).buffer(TROTOAR_SGRADA_M) for s in sgradi
                               if s.get("kontur") and len(s["kontur"]) >= 3]
                        if a.pateki:                   # the alleys – also where the crowns of the trees hide them
                            pths, _e = osm_paths(ox0, oy0, ox1, oy1)
                            cut += [_LSz(p_["tochki"]).buffer(p_["shirina"] / 2 + 0.3) for p_ in pths
                                    if len(p_["tochki"]) >= 2]
                        zel = orto_zeleno(os.path.splitext(png)[0] + "_chisto.png", ox0, oy0, ox1, oy1, inside=frame_,
                                          minus=_uu(cut) if cut else None)
                        orto_trevni = (frame_, [{"kontur": local(z["kontur"], bx0, by0),
                                                 "otvori": [local(h_, bx0, by0) for h_ in z["otvori"]]} for z in zel])
                        notes.append("Тревните площи около обекта са от ортофотото (зеленото на снимката) – алеите и "
                                     "настилките между тях са това, което не е зелено; приблизително (пътека под "
                                     "короните на дърветата не се вижда).")
                    summary["ortofoto"] = {"png": png, "godina": o.get("godina"), "pikseli_m": o.get("res"),
                                           "ramka_kc": [round(ox0, 2), round(oy0, 2), round(ox1, 2), round(oy1, 2)],
                                           "tochki": [{"n": n, "x": round(x - bx0, 2), "y": round(y - by0, 2)}
                                                      for n, x, y in marks or []]}
                    notes.append(f"Ортофото {o.get('godina') or ''} (МЗХ, от КАИС): {png} – работна снимка за входовете и "
                                 "порталите, не влиза в листа по Приложение № 2а. Номерираните точки по оградата са в "
                                 "`ortofoto.tochki` (координатите на схемата) – вход при точка N е `vhodove` там.")
                else:
                    notes.append("Ортофотото не се взе от КАИС" + (f": {o.get('error')}" if o and o.get('error') else "")
                                 + " – входовете се питат (формулярът).")

        # the named places nearby (ж.к. „…“, квартал) – from OpenStreetMap: inside the terrain at their point, a
        # place outside it (up to 400 m) at the edge of the terrain on its side
        cx, cy = (bx0 + bx1) / 2, (by0 + by1) / 2
        texts = []
        for m_ in sorted(res.get("mesta") or [], key=lambda m_: math.dist(m_["tochka"], (cx, cy))):
            px, py = m_["tochka"]
            dist_out = math.hypot(max(bx0 - px, 0, px - bx1), max(by0 - py, 0, py - by1))
            if dist_out > 400 or len(texts) >= 2:
                continue
            m = 12.0
            if dist_out > 0:                           # on the edge of the terrain, on the place's side
                dx, dy = px - cx, py - cy
                k = min((((bx1 - m) - cx) / dx if dx > 0 else ((bx0 + m) - cx) / dx) if dx else 1e9,
                        (((by1 - m) - cy) / dy if dy > 0 else ((by0 + m) - cy) / dy) if dy else 1e9)
                px, py = cx + dx * k, cy + dy * k
            texts.append({"x": round(px - bx0, 1), "y": round(py - by0, 1), "tekst": street_name(m_["ime"], ulitsa=False),
                          "osm": True})
        if texts:
            sh["tekst"] = texts
            summary["mesta"] = [t["tekst"] for t in texts]
        if far_hydrant:                                # the far hydrant: a pointer on the terrain's edge, on its side
            hx_, hy_, row = far_hydrant
            dx, dy = hx_ - cx, hy_ - cy
            m = 15.0
            k = min((((bx1 - m) - cx) / dx if dx > 0 else ((bx0 + m) - cx) / dx) if dx else 1e9,
                    (((by1 - m) - cy) / dy if dy > 0 else ((by0 + m) - cy) / dy) if dy else 1e9)
            px, py = cx + dx * k, cy + dy * k
            corners = [p for s_ in sgradi for p in (s_.get("kontur") or [])] or [(cx, cy)]
            dist_m = round(min(math.dist(p, (hx_, hy_)) for p in corners))
            posoki = ["на изток", "на североизток", "на север", "на северозапад", "на запад", "на югозапад", "на юг",
                      "на югоизток"]
            posoka = posoki[round(math.degrees(math.atan2(dy, dx)) / 45) % 8]
            vid = "ПХ " + row["diametar"] if row.get("diametar") else ("водоем" if row.get("vid") == "водоем" else "ПХ")
            kade = ", ".join(x for x in (("ул. „" + row["ulitsa"] + "“") if row.get("ulitsa") else "",
                                         row.get("orientir") or "") if x)
            sh.setdefault("tekst", []).append({"x": round(px - bx0, 1), "y": round(py - by0, 1),
                                               "tekst": f"{vid} – {dist_m} m {posoka}" + (f",\n{kade}" if kade else ""),
                                               "kray": "desen" if dx > 0 else "lyav"})   # the text runs inwards
            summary["dalechen_hidrant"] = {"m": dist_m, "posoka": posoka, "voda_id": row.get("id")}

        if hydrants:
            sh["vodoiztochnitsi"] = []
            for x, y, row in hydrants:
                vid = ("nadzemen_hidrant" if row.get("tip") == "надземен" else "hidrant") if row.get("vid") == "хидрант" else (
                    "vodoem" if row.get("vid") == "водоем" else "hidrant")
                sh["vodoiztochnitsi"].append({"vid": vid, "x": round(x - bx0, 1), "y": round(y - by0, 1),
                                              "etiket": "ПХ " + row["diametar"] if row.get("diametar") else "ПХ",
                                              "voda_id": row.get("id")})
            # the distance from the nearest corner of a building to the nearest water source (б. „а“)
            corners = [(p[0] - bx0, p[1] - by0) for s in sgradi for p in (s.get("kontur") or [])]
            if corners:
                hx, hy = sh["vodoiztochnitsi"][0]["x"], sh["vodoiztochnitsi"][0]["y"]
                c = min(corners, key=lambda p: math.dist(p, (hx, hy)))
                sh.setdefault("razstoyaniya", []).append({"ot": [round(c[0], 1), round(c[1], 1)], "do": [hx, hy]})
                summary["do_vodoiztochnika_m"] = round(math.dist(c, (hx, hy)))
            summary["vodoiztochnitsi"] = len(hydrants)
            # the water main: along the street of the nearest hydrant (its centre line from OpenStreetMap), with the
            # diameter given – or 70/80 by default, the size of the city's hydrants, when nothing else is known
            if a.vodoprovod and a.vodoprovod != "не":
                hx, hy = hydrants[0][0], hydrants[0][1]
                best = None
                for u in osm:
                    for piece in clip_polyline(u.get("tochki") or [], bx0, by0, bx1, by1):
                        if len(piece) < 2:
                            continue
                        d = min(dist_seg((hx, hy), a_, b_) for a_, b_ in zip(piece, piece[1:]))
                        if best is None or d < best[0]:
                            best = (d, piece)
                if best and best[0] < 30:
                    line = best[1]
                    if rings:                          # in the street parcels only – the OSM line is approximate
                        pieces, cur = [], []
                        for a_, b_ in zip(line, line[1:]):
                            mid = ((a_[0] + b_[0]) / 2, (a_[1] + b_[1]) / 2)
                            if any(point_in(mid, ring) for ring in rings):
                                cur = cur + [b_] if cur else [a_, b_]
                            elif cur:
                                pieces.append(cur)
                                cur = []
                        if cur:
                            pieces.append(cur)
                        if pieces:
                            line = min(pieces, key=lambda pc: min(dist_seg((hx, hy), p_, q_) for p_, q_ in zip(pc, pc[1:])))
                    sh["vodoprovod"] = [{"tochki": [[round(x - bx0, 1), round(y - by0, 1)] for x, y in line],
                                         "vid": "skluchena", "diametar": a.vodoprovod, "natisk": a.natisk}]
                    summary["vodoprovod"] = a.vodoprovod
                    notes.append(f"Водопроводът е приет по улицата на хидранта, Ø {a.vodoprovod}, налягане {a.natisk} bar "
                                 "(няма данни от ВиК) – провери вида (сключена или тупикова), диаметъра и налягането.")
        # the distances between the object's buildings and the neighbouring ones (б. „а“) – the nearest points
        own = [b["kontur"] for b in sh["sgradi"] if not b.get("sasedna") and not b.get("kratko")]
        for b in [b for b in sh["sgradi"] if b.get("sasedna")]:
            best = None
            for k in own:
                for P_, Q_ in ((k, b["kontur"]), (b["kontur"], k)):
                    for p_ in P_:
                        for a_, b_ in zip(Q_, Q_[1:] + Q_[:1]):
                            q_ = nearest_on(p_, a_, b_)
                            d_ = math.dist(p_, q_)
                            if best is None or d_ < best[0]:
                                best = (d_, p_, q_) if P_ is k else (d_, q_, p_)
            if best and 1.0 < best[0] <= MAX_RAZSTOYANIE_M:
                sh.setdefault("razstoyaniya", []).append({"ot": [round(best[1][0], 2), round(best[1][1], 2)],
                                                          "do": [round(best[2][0], 2), round(best[2][1], 2)]})
        # the grass areas (чл. 9, ал. 9, т. 5) – КАИС has none: from OpenStreetMap, straight from its API
        if not a.bez_trevni:
            grass, err = osm_grass(bx0, by0, bx1, by1)
            if grass:
                sh["trevni"] = [{"kontur": local(k, bx0, by0)} for k in grass]
                if orto_trevni:                         # round the object – the grass of the photo (--trevni-ortofoto)
                    from shapely.geometry import Polygon as _P2
                    from shapely.affinity import translate as _tr
                    fr_ = _tr(orto_trevni[0], -bx0, -by0)
                    pieces = []
                    for t in sh["trevni"]:
                        rest = _P2(t["kontur"]).buffer(0).difference(fr_)
                        pieces += [{"kontur": [list(p) for p in q.exterior.coords][:-1],
                                    "otvori": [[list(p) for p in h.coords][:-1] for h in q.interiors]}
                                   for q in getattr(rest, "geoms", [rest]) if q.geom_type == "Polygon" and q.area > 6]
                    sh["trevni"] = pieces + orto_trevni[1]
                summary["trevni"] = len(grass)
                notes.append("Тревните площи са от OpenStreetMap (приблизителни). Ако някоя излиза на платното между два "
                             "имота на улици, запълни празнината с улица-площ без ръб (shemi).")
            elif err:
                notes.append("Тревните площи не се взеха от OpenStreetMap: " + err)
            else:                                      # OSM has nothing here – the sheet would show the object in a void
                notes.append("OpenStreetMap няма тревни площи в рамката – нанеси ги от ортофотото като `trevni` "
                             "(приблизително) и го кажи в чата; без тях обектът „виси“ в празно поле (shemi).")
        # the alleys and paths through the grass and round the buildings – from OpenStreetMap, like the grass; drawn
        #   as narrow roads (кафяв, чл. 9, ал. 9, т. 4), so that one sees where people walk and the vehicles drive in
        if a.pateki:
            paths, err = osm_paths(bx0, by0, bx1, by1)
            for pth in paths:
                for piece in clip_polyline(local(pth["tochki"], bx0, by0), 0, 0, bx1 - bx0, by1 - by0):
                    if length(piece) > 3:
                        sh.setdefault("ulitsi", []).append({"tochki": [[round(x, 1), round(y, 1)] for x, y in piece],
                                                            "shirina": pth["shirina"], "ime": "", "pateka": True})
            summary["pateki"] = len(paths)
            if paths:
                notes.append("Алеите и пътеките са от OpenStreetMap (осите – приблизителни, ширината – приета по вида им).")
            elif err:
                notes.append("Алеите не се взеха от OpenStreetMap: " + err)
        # rivers, canals, lakes (Приложение № 6, „Река, канал“, „Езеро, микроязовир“) – КАИС has no names for them and
        #   the water parcels are not always there: from OpenStreetMap, like the grass
        if not a.bez_reki:
            vodi, err = osm_water(bx0, by0, bx1, by1)
            if vodi and (vodi["reki"] or vodi["ezera"]):
                fx0, fy0, fx1, fy1 = bx0 - 200, by0 - 200, bx1 + 200, by1 + 200      # keep what reaches the frame
                def near(pts):
                    return any(fx0 <= p[0] <= fx1 and fy0 <= p[1] <= fy1 for p in pts)
                def trim(pts):                          # only the part near the frame (one point past it each way)
                    keep = [i for i, p in enumerate(pts) if fx0 <= p[0] <= fx1 and fy0 <= p[1] <= fy1]
                    return pts[max(keep[0] - 1, 0):keep[-1] + 2] if keep else pts
                reki = [dict(r, tochki=local(trim(r["tochki"]), bx0, by0)) for r in vodi["reki"] if near(r["tochki"])]
                ezera = [dict(e, kontur=local(e["kontur"], bx0, by0)) for e in vodi["ezera"] if near(e["kontur"])]
                if reki:
                    sh["reki"] = reki
                    summary["reki"] = [r["ime"] or "(без име)" for r in reki]
                if ezera:
                    sh["ezera"] = ezera
                    summary["ezera"] = len(ezera)
                if reki or ezera:
                    notes.append("Реките и езерата са от OpenStreetMap – оста и ширината са приблизителни (ширина по "
                                 "подразбиране: река 10 m, канал 6 m, поток 4 m); провери ги и името (shemi).")
            elif err:
                notes.append("Реките не се взеха от OpenStreetMap: " + err)
        # the sign of a river (Приложение № 6) stands on its own – no grass dots inside it: the water and its banks are
        #   taken out of the grass areas (the photo sees the green banks, OSM's parks run across the river); and grass
        #   never lies on a street or on the river's parcel in КАИС (the strip between the brown lines)
        if sh.get("trevni") and (sh.get("reki") or sh.get("ezera") or any(u.get("kontur") for u in sh.get("ulitsi", []))):
            from shapely.geometry import LineString as _L3, Polygon as _P3
            from shapely.ops import unary_union as _u3
            ul_ = _u3([_P3(u["kontur"]).buffer(0) for u in sh.get("ulitsi", []) if len(u.get("kontur") or []) >= 3])

            def koridor(r):                             # the river and its banks – up to the nearest brown line (a
                ax_ = _L3(r["tochki"])                  #   street parcel) on each side, at most 10 m out
                band = ax_.buffer(r.get("shirina", 10.0) / 2 + 1.5, cap_style=2)
                wide = ax_.buffer(10.0, cap_style=2).difference(ul_)
                parts = [q for q in getattr(wide, "geoms", [wide]) if q.intersects(ax_)]
                return _u3([band] + parts)
            voda_ = _u3([koridor(r) for r in sh.get("reki", []) if len(r["tochki"]) >= 2] +
                        [_P3(e["kontur"]).buffer(1.5) for e in sh.get("ezera", []) if len(e["kontur"]) >= 3] +
                        [_P3(u["kontur"]).buffer(0) for u in sh.get("ulitsi", []) if len(u.get("kontur") or []) >= 3])
            dry = []
            for t in sh["trevni"]:
                g0 = _P3(t["kontur"], [h for h in (t.get("otvori") or []) if len(h) >= 3]).buffer(0)
                if not g0.intersects(voda_) or g0.intersection(voda_).area < 0.5:
                    dry.append(t)                        # untouched – kept as it is
                    continue
                g = g0.difference(voda_)
                dry += [{"kontur": [[round(x, 2), round(y, 2)] for x, y in q.exterior.coords][:-1],
                         "otvori": [[[round(x, 2), round(y, 2)] for x, y in h.coords][:-1] for h in q.interiors]}
                        for q in getattr(g, "geoms", [g]) if q.geom_type == "Polygon" and q.area > 4]
            sh["trevni"] = dry
        with open(a.shema, "w", encoding="utf-8") as f:
            json.dump(sh, f, ensure_ascii=False, indent=1)
        summary["shema"] = os.path.abspath(a.shema)
        summary["teren_m"] = [w, h]
    summary["zaiavki_kais"] = res.get("zaiavki_kais")
    summary["iztochnik"] = res.get("istochnik")
    if notes:
        summary["zabelezhki"] = notes
    print(json.dumps(summary, ensure_ascii=False, indent=1))


def cmd_tarsi(a):
    res = call({"action": "tarsi", "tekst": a.tekst})
    print(json.dumps(res, ensure_ascii=False, indent=1))


def cmd_mesto(a):
    """An object by its NAME (a shop, a fuel station, a firm) → candidate points, through n8n: Google Places, then
    OpenStreetMap, only inside област Плевен. Never a browser. The chosen candidate goes to obekt --lat/--lon; the
    registry keeps the КАИС point and identifier, not Google's point."""
    body = {"action": "mesto", "tekst": a.tekst}
    if a.masto:
        body["masto"] = a.masto
    print(json.dumps(call(body), ensure_ascii=False, indent=1))


def main():
    ap = argparse.ArgumentParser(description="Кадастралната карта (КАИС) за ситуационни схеми и планове")
    sub = ap.add_subparsers(dest="cmd", required=True)
    o = sub.add_parser("obekt", help="имотът и сградите му – по точка или идентификатор")
    o.add_argument("--id", help="кадастрален идентификатор: 56722.27.446 (имот) или 56722.27.446.1 (сграда)")
    o.add_argument("--lat", type=float)
    o.add_argument("--lon", type=float)
    o.add_argument("--link", help="линк от Google Maps (и кратък) или „ширина,дължина“")
    o.add_argument("--radius", type=int, default=40, help="метри около имота (30–300, по подразбиране 40)")
    o.add_argument("--fon", action="store_true",
                   help="и картинката на кадастралната карта като блед фон (не по Приложение № 2а – за работа и сверка)")
    o.add_argument("--granitsa", action="store_true",
                   help="с --shema: и границата на поземления имот (по подразбиране не се чертае)")
    o.add_argument("--bez-granitsa", action="store_true", help=argparse.SUPPRESS)   # the old default – kept for old calls
    o.add_argument("--ograda", nargs="?", const="da", default=None,
                   help="с --shema: имотът е ограден – границата му се чертае като ограда (вид: zhelezobetonna, "
                        "kamenna, metalna, darvena, bodliva; без вид – пунктир „Ограда“)")
    o.add_argument("--trotoar", type=float, default=0,
                   help="с --ograda: оградата откъм улиците се отмества толкова метра навътре – тротоарът се вижда "
                        "между ръба на улицата и оградата (напр. 2.5)")
    o.add_argument("--trotoar-ulitsa", action="append",
                   help="с --trotoar: само откъм тази улица (име или част от него, или идентификатор от КАИС); "
                        "може няколко пъти – без него откъм всички улици")
    o.add_argument("--ortofoto", nargs="?", const="nai-novo", default=None,
                   help="с --shema: и ортофотото на имота от КАИС (МЗХ) с границата, сградите и номерирани точки по "
                        "оградата – за входовете и порталите (*_ortofoto.png); издание: 2025 (2023–2025) или 2022 (2020–2022) – "
                        "по подразбиране най-новото с покритие")
    o.add_argument("--s-vatreshni", action="store_true",
                   help="с --shema: и пътищата без име от OpenStreetMap вътре в имота (по подразбиране – не)")
    o.add_argument("--bez-trevni", action="store_true", help="с --shema: без тревните площи от OpenStreetMap")
    o.add_argument("--trevni-ortofoto", action="store_true",
                   help="с --ortofoto: тревните площи около обекта – от зеленото на ортофотото (алеите между тях се виждат)")
    o.add_argument("--pateki", action="store_true",
                   help="с --shema: и алеите и пътеките от OpenStreetMap (през тревните площи и около сградите)")
    o.add_argument("--bez-reki", action="store_true", help="с --shema: без реките, каналите и езерата от OpenStreetMap")
    o.add_argument("--hidrant-v-terena", action="store_true",
                   help=f"с --voda: теренът да се разшири до най-близкия хидрант и когато е на над {60} m извън него "
                        "(по подразбиране – надпис на ръба на терена откъм хидранта)")
    o.add_argument("--vodoprovod", default="70/80",
                   help="с --voda: диаметърът на водопровода по улицата на хидранта (по подразбиране 70/80; „не“ – без него)")
    o.add_argument("--natisk", default="3–5",
                   help="налягането във водопровода, bar (по подразбиране 3–5 – когато няма данни от ВиК)")
    o.add_argument("-o", "--out", default="kais.json", help="изходен JSON (фонът – до него, *_fon.png)")
    o.add_argument("--shema", help="и начало на JSON за shema.py / situacionna.py")
    o.add_argument("--voda", action="store_true", help="с --shema: и точните водоизточници в рамката")
    o.add_argument("--bez-sasedni", action="store_true",
                   help="с --shema: без сградите в граничещите имоти (по подразбиране са в схемата – б. „е“)")
    t = sub.add_parser("tarsi", help="търсачката на картата")
    t.add_argument("tekst")
    m = sub.add_parser("mesto", help="обект по ИМЕ (магазин, бензиностанция, фирма) – кандидати с точка, без браузър")
    m.add_argument("tekst", help="името, напр. „Ларго метанстанция“")
    m.add_argument("--masto", help="населеното място, напр. Плевен")
    a = ap.parse_args()
    if a.cmd == "obekt" and a.link and "," in a.link and "://" not in a.link:
        try:
            a.lat, a.lon = (float(v) for v in a.link.split(",", 1))
            a.link = None
        except ValueError:
            fail("BAD_INPUT", f"„{a.link}“ не е „ширина,дължина“")
    {"obekt": cmd_obekt, "tarsi": cmd_tarsi, "mesto": cmd_mesto}[a.cmd](a)


if __name__ == "__main__":
    main()
