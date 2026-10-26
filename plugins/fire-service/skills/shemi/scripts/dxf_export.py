#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
dxf_export.py — схемата като DXF (AutoCAD 2010, R2018 съвместим) за редакция в AutoCAD или CorelDRAW.

Вика се от shema.py (--dxf) и от situacionna.py – не самостоятелно. Чертежът е в метри (1 единица = 1 m),
в истинския мащаб; със "kais" (схема от кадастъра) координатите са в КС2005 – същите като в кадастъра, така че
чертежът ляга точно върху кадастрална карта, вмъкната в AutoCAD. Листът на ситуационна схема (рамка, поле за
номера, антетка по Приложение № 2а) е в същото пространство, в мащаба на схемата – печата се направо 1:N.

Слоеве (цветовете – по чл. 9, ал. 9 от Указанията Iз-2749):
  SGRADI (черно) · RAZMERI · IMOT (щрих-пунктир) · ULITSI (кафяво) · VODA (синьо: водоизточници, водопровод,
  шлангови линии) · GAZ (жълто) · BEZ_PARKIRANE (оранжево) · TREVNI (зелено) · OGRADA · POZHAR (червено: пожар, огнище, автомобили,
  направления) · TEKST · LIST (рамката и антетката) · SEVER (посоките)
Знаците са опростени (кръг с кръст за хидрант, правоъгълник за автомобил …) – точните им рисунки са в .png;
в DXF-а са на правилното място и с надписа си, за да се редактират.
"""
import math

try:
    import ezdxf
    from ezdxf import colors as dxfcolors
except ImportError:  # pragma: no cover
    ezdxf = None

BROWN = (139, 90, 43)
LAYERS = {  # name: (ACI colour, true colour or None, linetype)
    "SGRADI": (7, None, "CONTINUOUS"), "RAZMERI": (7, None, "CONTINUOUS"), "IMOT": (7, None, "DASHDOT"),
    "ULITSI": (30, BROWN, "CONTINUOUS"), "VODA": (5, None, "CONTINUOUS"), "GAZ": (2, None, "CONTINUOUS"),
    "BEZ_PARKIRANE": (30, (255, 140, 0), "CONTINUOUS"), "TREVNI": (3, (46, 139, 58), "CONTINUOUS"), "OGRADA": (7, None, "DASHED"), "POZHAR": (1, None, "CONTINUOUS"),
    "TEKST": (7, None, "CONTINUOUS"), "LIST": (7, None, "CONTINUOUS"), "SEVER": (7, None, "CONTINUOUS"),
}
FONT = "arial.ttf"            # a TrueType font with Cyrillic – AutoCAD and CorelDRAW both have it


def available():
    return ezdxf is not None


def _clip(a, b, box):
    """The part of segment a–b inside the box (Liang–Barsky), or None."""
    x0, y0, x1, y1 = box
    dx, dy = b[0] - a[0], b[1] - a[1]
    t0, t1 = 0.0, 1.0
    for p, q in ((-dx, a[0] - x0), (dx, x1 - a[0]), (-dy, a[1] - y0), (dy, y1 - a[1])):
        if p == 0:
            if q < 0:
                return None
            continue
        t = q / p
        if p < 0:
            t0 = max(t0, t)
        else:
            t1 = min(t1, t)
    if t0 > t1:
        return None
    return (a[0] + t0 * dx, a[1] + t0 * dy), (a[0] + t1 * dx, a[1] + t1 * dy)


def _minus(a, b, holes):
    """The pieces of segment a–b outside every rectangle in holes (the sheet's fields)."""
    pieces = [(a, b)]
    for h in holes:
        out = []
        for p, q in pieces:
            c = _clip(p, q, h)
            if not c:
                out.append((p, q))
                continue
            dx, dy = q[0] - p[0], q[1] - p[1]
            L2 = dx * dx + dy * dy or 1.0
            t = lambda r: ((r[0] - p[0]) * dx + (r[1] - p[1]) * dy) / L2   # noqa: E731
            t0, t1 = sorted((t(c[0]), t(c[1])))
            if t0 > 1e-9:
                out.append((p, (p[0] + t0 * dx, p[1] + t0 * dy)))
            if t1 < 1 - 1e-9:
                out.append(((p[0] + t1 * dx, p[1] + t1 * dy), q))
        pieces = out
    return pieces


def _split_at(a, b, verts):
    """Segment a–b cut at the vertices of other outlines lying on it (within 1 cm) – so that a shared stretch of a
    longer edge becomes an edge of its own."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    L2 = dx * dx + dy * dy
    if L2 == 0:
        return []
    ts = []
    for v in verts:
        t = ((v[0] - a[0]) * dx + (v[1] - a[1]) * dy) / L2
        if 1e-6 < t < 1 - 1e-6 and math.dist(v, (a[0] + t * dx, a[1] + t * dy)) < 0.01:
            ts.append(t)
    pts = [a] + [(a[0] + t * dx, a[1] + t * dy) for t in sorted(set(ts))] + [b]
    return list(zip(pts, pts[1:]))


def _split_hidden(a, b, hidden):
    """Segment a–b cut at the ends of the hidden pieces that lie on it – so only the hidden part is dropped."""
    from shema import dist_to_segment
    cuts = [0.0, 1.0]
    dx, dy = b[0] - a[0], b[1] - a[1]
    L2 = dx * dx + dy * dy or 1.0
    for p_, q_ in hidden:
        for r in (p_, q_):
            if dist_to_segment(r, a, b) < 0.3:
                cuts.append(min(1.0, max(0.0, ((r[0] - a[0]) * dx + (r[1] - a[1]) * dy) / L2)))
    cuts = sorted(set(cuts))
    pt_ = lambda t: (a[0] + t * dx, a[1] + t * dy)   # noqa: E731
    return [(pt_(t0), pt_(t1)) for t0, t1 in zip(cuts, cuts[1:]) if t1 - t0 > 1e-6]


def _shared_edges_removed(rings):
    """The edges of the street parcels without those two parcels share – the outline of the streets as one area."""
    key = lambda p: (round(p[0], 2), round(p[1], 2))  # noqa: E731
    count, edges = {}, []
    for i, r in enumerate(rings):
        others = [v for j, o in enumerate(rings) if j != i for v in o]
        pts = list(r) + [r[0]]
        for a, b in (seg for a0, b0 in zip(pts, pts[1:]) for seg in _split_at(a0, b0, others)):
            k = tuple(sorted((key(a), key(b))))
            count[k] = count.get(k, 0) + 1
            edges.append((k, a, b))
    return [(a, b) for k, a, b in edges if count[k] == 1]


def write(data, d, out, s, sheet=None):
    """data – the loaded scheme (shema.load), d – the input JSON, s – the symbol size (m);
    sheet – {"scale": N, "x_mm", "y_mm", "list": {...}} for the sheet of a situational scheme."""
    if ezdxf is None:
        raise RuntimeError("NO_EZDXF: pip install ezdxf")
    doc = ezdxf.new("R2010", setup=True)
    doc.header["$INSUNITS"] = 6                      # metres
    doc.header["$MEASUREMENT"] = 1
    doc.styles.add("BG", font=FONT)
    for name, (aci, rgb, lt) in LAYERS.items():
        layer = doc.layers.add(name, color=aci, linetype=lt if lt in doc.linetypes else "CONTINUOUS")
        if rgb:
            layer.rgb = rgb
    msp = doc.modelspace()
    k = d.get("kais") or {}
    ox, oy = float(k.get("x0", 0) or 0), float(k.get("y0", 0) or 0)
    P = lambda p: (p[0] + ox, p[1] + oy)            # noqa: E731
    scale = sheet["scale"] if sheet else None
    th = (2.5 * scale / 1000) if scale else max(0.6 * s, 0.5)   # text height: 2.5 mm on paper at 1:N
    if "DASHDOT" in doc.linetypes:
        doc.header["$LTSCALE"] = (scale / 1000 * 2) if scale else max(s / 2, 0.5)

    def text(x, y, t, layer="TEKST", h=None, rot=0.0, align="MIDDLE_CENTER", color=None):
        if not t:
            return
        lines = str(t).replace("\\n", "\n").split("\n")
        hh = h or th
        for i, line in enumerate(lines):
            dy = (len(lines) - 1) / 2 * hh * 1.4 - i * hh * 1.4
            ent = msp.add_text(line, height=hh, rotation=rot, dxfattribs={"layer": layer, "style": "BG"})
            ent.set_placement(P((x - math.sin(math.radians(rot)) * dy, y + math.cos(math.radians(rot)) * dy)),
                              align=ezdxf.enums.TextEntityAlignment[align])
            if color is not None:
                ent.dxf.color = color

    def poly(pts, layer, closed=False, width=None):
        msp.add_lwpolyline([P(p) for p in pts], close=closed, dxfattribs={"layer": layer, **({"const_width": width} if width else {})})

    # streets: the parcels as one area (shared edges dropped), the bands as their two edges
    rings = []
    for u in data["ulitsi"]:
        if "kontur" in u and not u.get("bez_ruba"):
            rings.append(u["kontur"])
            rings += list(u.get("otvori") or [])
    box = data["box"]                                  # the streets run off the drawing – cut at its edge
    holes = []                                         # … and under the sheet's fields, as on the picture
    if sheet:
        from shema import SHEET_W, SHEET_H, NO_BOX, TITLE_BOX
        n_ = sheet["scale"] / 1000.0
        sx_, sy_ = box[0] - sheet["x_mm"] * n_, box[1] - sheet["y_mm"] * n_
        for a_, b_, c_, d_ in ((SHEET_W - TITLE_BOX[0], 0, SHEET_W, TITLE_BOX[1]),
                               (SHEET_W - NO_BOX[0], SHEET_H - NO_BOX[1], SHEET_W, SHEET_H), (0, SHEET_H - 24, 17, SHEET_H)):
            holes.append((sx_ + a_ * n_, sy_ + b_ * n_, sx_ + c_ * n_, sy_ + d_ * n_))

    for g in data.get("prohodi") or []:               # the entrances from the street – gaps in its edge
        r_ = g["shirina"] / 2
        holes.append((g["x"] - r_, g["y"] - r_, g["x"] + r_, g["y"] + r_))

    hidden = [seg for ln in data.get("ulitsi_skrij") or [] for seg in zip(ln, ln[1:])]

    def on_hidden(p, q):
        from shema import dist_to_segment
        m = ((p[0] + q[0]) / 2, (p[1] + q[1]) / 2)
        return any(dist_to_segment(m, a_, b_) < 0.3 and dist_to_segment(p, a_, b_) < 0.3 and
                   dist_to_segment(q, a_, b_) < 0.3 for a_, b_ in hidden)

    def visible(p):                                   # a street name: inside the drawing, not under a field of the sheet
        return box[0] <= p[0] <= box[2] and box[1] <= p[1] <= box[3] and \
            not any(h[0] <= p[0] <= h[2] and h[1] <= p[1] <= h[3] for h in holes)

    def street_line(a, b):
        c = _clip(a, b, box)
        if c:
            for p, q in _minus(c[0], c[1], holes):
                for p2, q2 in _split_hidden(p, q, hidden):
                    if not on_hidden(p2, q2):
                        msp.add_line(P(p2), P(q2), dxfattribs={"layer": "ULITSI"})
    for a, b in _shared_edges_removed(rings):
        street_line(a, b)
    from shema import chaikin   # noqa: E402
    for ln in data.get("ulitsi_rab") or []:           # the street edges drawn by hand
        pts_ = chaikin(ln) if len(ln) > 2 else ln
        for a, b in zip(pts_, pts_[1:]):
            street_line(a, b)
    from shema import offset_polyline   # noqa: E402  (the same offsets as the drawing)
    for u in data["ulitsi"]:
        if "kontur" in u:
            if u["ime"] and u.get("ime_pos") and visible(u["ime_pos"]):
                from znatsi import readable
                text(u["ime_pos"][0], u["ime_pos"][1], u["ime"], rot=readable(u.get("ime_ugal") or 0))
            continue
        for side in (-1, 1):
            if (side, u.get("bez_ruba")) in ((1, "lyav"), (-1, "desen")):
                continue                               # the edge left out
            edge = offset_polyline(u["tochki"], side * u["shirina"] / 2)
            for a, b in zip(edge, edge[1:]):
                street_line(a, b)
        a, b = max(zip(u["tochki"], u["tochki"][1:]), key=lambda ab: math.dist(*ab))
        if u["ime"] and visible(((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)):
            from znatsi import readable
            text((a[0] + b[0]) / 2, (a[1] + b[1]) / 2, u["ime"],
                 rot=readable(math.degrees(math.atan2(b[1] - a[1], b[0] - a[0]))))
    if data.get("imot"):
        poly(data["imot"]["kontur"], "IMOT", closed=True)
        from shema import building_outlines
        from znatsi import parcel_label_pos
        lab = data["imot"]["etiket"]
        pos = parcel_label_pos(data["imot"]["kontur"], 0.65 * th * len(lab), 1.1 * th, building_outlines(data))
        if pos is None:                                # nowhere inside – above the top point, as before
            tx, ty = max(data["imot"]["kontur"], key=lambda p: (p[1], -p[0]))
            pos = (tx, ty + 0.8 * th)
        text(pos[0], pos[1], lab, layer="IMOT", h=th * 0.9)
    if data["ograda"]:
        poly(data["ograda"], "OGRADA", closed=True)
    for k in data.get("trevni") or []:                # grass areas – green outlines, cut at the drawing's edge
        for a_, b_ in zip(k, k[1:] + k[:1]):
            c_ = _clip(a_, b_, data["box"])
            if c_:
                msp.add_line(P(c_[0]), P(c_[1]), dxfattribs={"layer": "TREVNI"})
    for z in data["bez_parkirane"]:
        poly([(z["x"], z["y"]), (z["x"] + z["w"], z["y"]), (z["x"] + z["w"], z["y"] + z["h"]), (z["x"], z["y"] + z["h"])],
             "BEZ_PARKIRANE", closed=True)

    # buildings: the outline, the name and floors, the overall dimensions
    from shema import centroid   # noqa: E402
    for b in data["sgradi"]:
        pts = b["kontur"] or [(b["x"], b["y"]), (b["x"] + b["w"], b["y"]), (b["x"] + b["w"], b["y"] + b["h"]), (b["x"], b["y"] + b["h"])]
        poly(pts, "SGRADI", closed=True, width=None)
        cx, cy = centroid(pts) if b["kontur"] else (b["x"] + b["w"] / 2, b["y"] + b["h"] / 2)
        text(cx, cy, b["etiket"], layer="SGRADI")
        if b["razmeri"]:
            from shema import wall_dimensions   # noqa: E402
            off = max(1.2 * s, 2 * th)
            for a_, b_, _txt, (ox_, oy_) in wall_dimensions(b, off):
                dim = msp.add_aligned_dim(p1=P(a_), p2=P(b_), distance=math.hypot(ox_, oy_) * (
                                              1 if (b_[0] - a_[0]) * oy_ - (b_[1] - a_[1]) * ox_ > 0 else -1),
                                          dimstyle="EZDXF",
                                          override={"dimtxt": th, "dimasz": th * 0.8, "dimexo": th * 0.3, "dimlfac": 1,
                                                    "dimdec": 2},
                                          dxfattribs={"layer": "RAZMERI"})
                dim.render()
    for o in data["obekti"]:
        poly([(o["x"], o["y"]), (o["x"] + o["w"], o["y"]), (o["x"] + o["w"], o["y"] + o["h"]), (o["x"], o["y"] + o["h"])],
             "SGRADI", closed=True)
        text(o["x"] + o["w"] / 2, o["y"] + o["h"] / 2, o["etiket"], layer="SGRADI", h=th * 0.8)
    for r in data["razstoyaniya"]:
        msp.add_line(P(r["ot"]), P(r["do"]), dxfattribs={"layer": "RAZMERI"})
        mx, my = (r["ot"][0] + r["do"][0]) / 2, (r["ot"][1] + r["do"][1]) / 2
        from znatsi import readable
        text(mx, my + 0.7 * th, r["etiket"], layer="RAZMERI",
             rot=readable(math.degrees(math.atan2(r["do"][1] - r["ot"][1], r["do"][0] - r["ot"][0]))))

    # water: sources, the main, the hose lines
    for w in data["vodoiztochnitsi"]:
        r = 0.45 * s
        msp.add_circle(P((w["x"], w["y"])), r, dxfattribs={"layer": "VODA"})
        msp.add_line(P((w["x"] - r, w["y"])), P((w["x"] + r, w["y"])), dxfattribs={"layer": "VODA"})
        msp.add_line(P((w["x"], w["y"] - r)), P((w["x"], w["y"] + r)), dxfattribs={"layer": "VODA"})
        text(w["x"] + r * 1.3, w["y"], w["etiket"], layer="VODA", align="MIDDLE_LEFT")
    for v in data["vodoprovod"]:
        poly(v["tochki"], "VODA")
        if v["etiket"]:
            a, b = max(zip(v["tochki"], v["tochki"][1:]), key=lambda ab: math.dist(*ab))
            from znatsi import readable
            text((a[0] + b[0]) / 2, (a[1] + b[1]) / 2 + 0.8 * th, v["etiket"], layer="VODA",
                 rot=readable(math.degrees(math.atan2(b[1] - a[1], b[0] - a[0]))))
    for ln in data["linii"]:
        poly(ln["tochki"], "VODA")
    for g in data["gazoprovod"]:
        poly(g["tochki"], "GAZ")
    for g in data["gaz_armatura"]:
        msp.add_circle(P((g["x"], g["y"])), 0.35 * s, dxfattribs={"layer": "GAZ"})
        text(g["x"], g["y"] + 0.6 * s, g["etiket"], layer="GAZ")

    # fire, trucks and the rest of the forces
    for f in data["pozhar"] + data["zadimyavane"]:
        poly([(f["x"], f["y"]), (f["x"] + f["w"], f["y"]), (f["x"] + f["w"], f["y"] + f["h"]), (f["x"], f["y"] + f["h"])],
             "POZHAR", closed=True)
    for f in data["pozhar"]:
        hatch = msp.add_hatch(color=1, dxfattribs={"layer": "POZHAR"})
        hatch.set_pattern_fill("ANSI37", scale=max(s / 4, 0.2))
        hatch.paths.add_polyline_path([P((f["x"], f["y"])), P((f["x"] + f["w"], f["y"])), P((f["x"] + f["w"], f["y"] + f["h"])),
                                       P((f["x"], f["y"] + f["h"]))], is_closed=True)
        text(f["x"] + f["w"] / 2, f["y"] + f["h"] / 2, f["etiket"], layer="POZHAR")
    for t in data["avtomobili"]:
        L, W, a = 1.7 * s, 0.75 * s, math.radians(t["ugal"])
        c, si = math.cos(a), math.sin(a)
        pts = [(t["x"] + c * dx - si * dy, t["y"] + si * dx + c * dy) for dx, dy in
               ((-L / 2, -W / 2), (L / 2, -W / 2), (L / 2 + 0.3 * W, 0), (L / 2, W / 2), (-L / 2, W / 2))]
        poly(pts, "POZHAR", closed=True)
        text(t["x"], t["y"] - W, t["id"], layer="POZHAR")
    for a, b in data["posoka"] + data["napravlenie"]:
        msp.add_line(P(a), P(b), dxfattribs={"layer": "POZHAR"})
    for g in data["vhodove"]:
        text(g["x"], g["y"], g["etiket"])
    for t in data["tekst"]:
        text(t["x"], t["y"], t["tekst"], rot=t["ugal"],                # the same end as on the picture
             align="MIDDLE_RIGHT" if t.get("kray") == "desen" else "MIDDLE_LEFT")

    # the sheet (Приложение № 2а) in model space, at the scheme's scale
    x0, y0, x1, y1 = data["box"]
    if sheet:
        from shema import SHEET_W, SHEET_H, NO_BOX, TITLE_BOX
        n = scale / 1000.0
        sx, sy = x0 - sheet["x_mm"] * n, y0 - sheet["y_mm"] * n      # the sheet's lower left corner (m)
        M = lambda mx, my: (sx + mx * n, sy + my * n)                 # noqa: E731
        def rect(ax_, ay_, w_, h_):
            msp.add_lwpolyline([P(M(ax_, ay_)), P(M(ax_ + w_, ay_)), P(M(ax_ + w_, ay_ + h_)), P(M(ax_, ay_ + h_))],
                               close=True, dxfattribs={"layer": "LIST"})
        def ltext(mx, my, t, h_mm, align="MIDDLE_CENTER"):
            if t:
                ent = msp.add_text(t, height=h_mm * n, dxfattribs={"layer": "LIST", "style": "BG"})
                ent.set_placement(P(M(mx, my)), align=ezdxf.enums.TextEntityAlignment[align])
        rect(0, 0, SHEET_W, SHEET_H)
        nw, nh = NO_BOX
        rect(SHEET_W - nw, SHEET_H - nh, nw, nh)
        ltext(SHEET_W - nw / 2, SHEET_H - 3, "№ на плана", 1.6)
        lst = sheet.get("list") or {}
        ltext(SHEET_W - nw / 2, SHEET_H - nh / 2 - 2, str(lst.get("nomer") or ""), 3.5)
        tw, tht = TITLE_BOX
        bx = SHEET_W - tw
        rect(bx, 0, tw, tht)
        for yy in (17, 25):
            msp.add_line(P(M(bx, yy)), P(M(bx + tw, yy)), dxfattribs={"layer": "LIST"})
        cells = [(0, 107, 25, 5, "Собственик:", "sobstvenik"), (107, 150, 25, 5, "Протокол рег. №", "protokol"),
                 (0, 30, 17, 8, "Изготвил:", "izgotvil"), (30, 63, 17, 8, "Съгласувал:", "saglasuval"),
                 (63, 107, 17, 8, "Утвърдил / дата:", "utvardil"), (107, 136, 17, 8, "Име на файла:", "fail"),
                 (136, 150, 17, 8, "Дата:", "data")]
        for a_, b_, y_, h_, cap, key in cells:
            if a_:
                msp.add_line(P(M(bx + a_, y_)), P(M(bx + a_, y_ + h_)), dxfattribs={"layer": "LIST"})
            val = str(lst.get(key) or "")
            if y_ == 25:
                ltext(bx + a_ + 1, y_ + h_ / 2, cap + (" " + val if val else ""), 1.6, "MIDDLE_LEFT")
            else:
                ltext(bx + a_ + 1, y_ + h_ - 1.6, cap, 1.6, "MIDDLE_LEFT")
                ltext(bx + (a_ + b_) / 2, y_ + 2.6, val, min(1.9, (b_ - a_ - 2) / (max(len(val), 1) * 0.62)))
        msp.add_line(P(M(bx + 63, 0)), P(M(bx + 63, 17)), dxfattribs={"layer": "LIST"})
        import textwrap
        obekt = str(lst.get("obekt") or "Наименование на обекта, адрес, телефон")
        for i, line in enumerate(textwrap.wrap(obekt, 34)[:4]):
            ltext(bx + 31.5, 8.5 + (1.5 - i) * 2.6, line, 1.9)
        ltext(bx + 106.5, 8.5, "Ситуационна схема", 3.5)
        ltext(bx - 3, 2, f"М 1:{scale}", 2.5, "BOTTOM_RIGHT")
        kx, ky = M(9, SHEET_H - 13)
    else:
        kx, ky = x0 + 1.5 * s, y1 - 2.5 * s
        n = s / 6
    # the north arrow – upper left; turned with the drawing ("zavartane")
    L = 6 * n if sheet else 2 * s
    t_n = math.radians(float(d.get("_sever_ugal", 90)) - 90)
    K = lambda dx, dy: P((kx + dx * math.cos(t_n) - dy * math.sin(t_n), ky + dx * math.sin(t_n) + dy * math.cos(t_n)))  # noqa: E731
    msp.add_lwpolyline([K(0, L / 2), K(L / 6, 0), K(0, -L / 2), K(-L / 6, 0)],
                       close=True, dxfattribs={"layer": "SEVER"})
    hatch = msp.add_hatch(color=7, dxfattribs={"layer": "SEVER"})
    hatch.paths.add_polyline_path([K(0, L / 2), K(L / 6, 0), K(-L / 6, 0)], is_closed=True)
    for t_, dy in (("С", L / 2 + L * 0.25), ("Ю", -L / 2 - L * 0.25)):
        ent = msp.add_text(t_, height=L * 0.22, dxfattribs={"layer": "SEVER", "style": "BG"})
        ent.set_placement(K(0, dy), align=ezdxf.enums.TextEntityAlignment.MIDDLE_CENTER)
    doc.saveas(out)
    return out
