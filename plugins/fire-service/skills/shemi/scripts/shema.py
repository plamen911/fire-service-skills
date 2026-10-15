#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
shema.py — чертае СХЕМА за разполагане на силите и средствата (за ПТЗ, план за пожарогасене,
справка, експертиза) като .png (и по желание .svg): сгради с размери, ограда и входове, пожар,
задимяване, огнище, посока на разпространение, главно направление, пожарните автомобили,
водоизточниците, шланговите линии с шланговете, разклонителите и струйниците, стълбите, щаба,
поста по безопасност, вятъра, севера, мащаба и легенда само с използваните знаци.

Наименованията на знаците в легендата са от Приложение № 6, част Б („Условни знаци, използвани при
разработка на планове за пожарогасене“) към Указанията за разработване на планове за пожарогасене,
рег. № Iз-2749/18.11.2010 г. на МВР. Формите са приближени по наименованията – рисунките на знаците
не са в текстовата нормативна база. По подразбиране схемата е черно-бяла (за печат); с "cvetna": true
пожарът, огнището и посоката на разпространение са в червено, водата и задимяването – в синьо, както
изисква приложението.

    python3 scripts/shema.py shema.json -o shema.png [--svg shema.svg]

Координатите са в метри: x – на изток (надясно), y – на север (нагоре), началото е долният ляв ъгъл
на терена. Сградите са правоъгълници, успоредни на осите. Ъглите са в градуси: 0 – изток, 90 – север.
Задължително е само "sgradi" (поне една сграда); всичко останало е по желание.

{
  "zaglavie": "",                               // надпис над схемата в картинката (обикновено празно –
                                                //   заглавието е в документа)
  "teren": [120, 90],                           // ширина и височина на чертежа, m (иначе – по елементите)
  "ograda": [[2, 2], [118, 2], [118, 88], [2, 88]],          // затворена ограда, точките по реда
  "vhodove": [{"x": 60, "y": 2, "shirina": 8, "etiket": "КПП"}],    // отвор в оградата + надпис
  "sgradi": [{"x": 10, "y": 55, "w": 36, "h": 22, "etiket": "Склад\\nет. 1",
              "razmeri": true, "pokriv": "dvuskaten"}],  // "dvuskaten" чертае билото; "plosak" – нищо
  "obekti": [{"x": 3, "y": 58, "w": 4, "h": 3, "etiket": "Ел"}],    // малки обекти в рамка; „Ел“ влиза в
                                                //   легендата като „Електрическо табло“; "legenda": "…" – друг текст
  "pozhar": [{"x": 34, "y": 60, "w": 12, "h": 12, "etiket": "≈ 140 m²", "na_otkrito": false}],
  "zadimyavane": [{"x": 10, "y": 55, "w": 24, "h": 22}],            // зона на задимяване
  "ognishte": [{"x": 40, "y": 66}],                                 // огнище на пожара
  "posoka": [{"ot": [34, 66], "do": [26, 66]}],                     // посока на разпространение
  "napravlenie": [{"ot": [52, 44], "do": [46, 56]}],                // главно направление за действие
  "avtomobili": [{"id": "I ПА", "x": 60, "y": 40, "ugal": 90, "vid": "pa"}],
  "vodoiztochnitsi": [{"vid": "vodoem", "x": 85, "y": 20, "etiket": "120 m³"},
                      {"vid": "hidrant", "x": 70, "y": 8, "etiket": "ПХ № 3"}],
  "linii": [{"tochki": [[60, 44], [52, 52], [46, 60]], "vid": "glavna"},
            {"tochki": [[46, 60], [40, 58], [36, 62]], "vid": "malka", "struinik": "malak", "etiket": "п"},
            {"tochki": [[84, 20], [64, 38]], "vid": "smukatelna"}],
  "razklonitel": [{"x": 46, "y": 60, "patya": 3}],                 // 2, 3 (по подразбиране) или 4 пътя
  "stalbi": [{"ot": [40, 54], "do": [40, 58], "vid": "sglobna"}],
  "shtab": [{"x": 66, "y": 44}],                                    // място за разположение на щаба
  "pbt": [{"x": 56, "y": 30}],                                      // пост по безопасност на труда
  "vyatar": {"ugal": 200, "sila": "5 m/s"},                         // накъде духа и скоростта – под схемата
  "tekst": [{"x": 5, "y": 5, "tekst": "ул. „Христо Ботев“", "ugal": 0}],
  "shlang_m": 20,                               // дължина на един шланг – чертичка на всеки толкова метра
  "cvetna": false, "sever": true, "mashtab": true, "legenda": true
}

Видове (стойности на "vid"):
  автомобили  – pa (пожарен автомобил), pa_lafeten, avtostalba, avtopodemnik, shtaben, adz,
                spasitelen, shlangov, vodonoska
  водоизточници – vodoem (пожарен водоем), hidrant (подземен), nadzemen_hidrant
  линии       – glavna (главна, Ø 75 mm), malka (работна, Ø 52 mm), smukatelna (без чертички)
  струйници ("struinik" на линия) – malak, glaven, lafeten, penostruinik
  стълби      – sglobna, razdvizhna (разтегателна), shturmova, palka

Пожарът се чертае като кръстосано защриховано място с флагче; "na_otkrito": true – пожар на открита
площадка (без флагче). Струйникът е в края на линията, по посоката на последния ѝ участък; "etiket"
на линията се пише до струйника („п“ – на покрива, „е“ – в етажа, „м“ – в мазето).

Отпечатва JSON {"output", "svg", "elementi", "shlangove", "preduprezhdeniya"}. "shlangove" е броят
шлангове по линиите (по чертичките). Предупрежденията казват, ако нещо излиза извън терена, линия не
започва до автомобил, разклонител, водоизточник или друга линия, или входът не е върху оградата.

Грешки (на stderr, код ≠ 0):
    BAD_INPUT: ...    — липсва поле, непознат вид, неверни координати
    NO_MATPLOTLIB     — няма matplotlib: pip install matplotlib
"""
import argparse
import json
import math
import os
import sys
import textwrap

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Circle, FancyArrowPatch, FancyBboxPatch, Polygon, Rectangle
except ImportError:  # pragma: no cover
    sys.stderr.write("NO_MATPLOTLIB: pip install matplotlib\n")
    sys.exit(3)

matplotlib.rcParams["font.family"] = "DejaVu Sans"   # ships with matplotlib – the same look everywhere
matplotlib.rcParams["hatch.linewidth"] = 0.6
matplotlib.rcParams["svg.fonttype"] = "none"

INK = "black"
WIDTH_CM = 16.5            # the text width of an A4 document with the plugin's margins
MAX_DRAW_HEIGHT_CM = 17.0
LINE_KINDS = {"glavna": 1.9, "malka": 1.1, "smukatelna": 2.6}
NOZZLES = ("malak", "glaven", "lafeten", "penostruinik")
WATER = ("vodoem", "hidrant", "nadzemen_hidrant")
TRUCKS = {"pa": "", "pa_lafeten": "", "avtostalba": "АС", "avtopodemnik": "АП", "shtaben": "Щ", "adz": "АДЗ",
          "spasitelen": "АСД", "shlangov": "Ш", "vodonoska": "В"}
LADDERS = ("sglobna", "razdvizhna", "shturmova", "palka")
SPLITTERS = {2: "dvupaten", 3: "tripaten", 4: "chetiripaten"}

# The names of the symbols – Приложение № 6, част Б, към Указанията рег. № Iз-2749/2010 г.
LEGEND_TEXT = {
    "sgrada": "Сграда (размерите – в m)",
    "ograda": "Ограда",
    "pozhar": "Пожар в сграда",
    "pozhar_otkrito": "Пожар на открита площадка",
    "zadimyavane": "Зона на задимяване",
    "ognishte": "Огнище на пожара",
    "posoka": "Посока на разпространение на пожара",
    "napravlenie": "Главно направление за действие на силите и средствата",
    "vyatar": "Посока и сила на вятъра",
    "pa": "Пожарен автомобил",
    "pa_lafeten": "Пожарен автомобил с лафетен струйник",
    "avtostalba": "Пожарна автомеханична стълба",
    "avtopodemnik": "Пожарен автоподемник",
    "shtaben": "Щабен автомобил",
    "adz": "Автомобил за дихателна защита",
    "spasitelen": "Автомобил за спасителна дейност",
    "shlangov": "Шлангов автомобил",
    "vodonoska": "Водоноска",
    "vodoem": "Пожарен водоем",
    "hidrant": "Подземен хидрант",
    "nadzemen_hidrant": "Надземен хидрант",
    "glavna": "Главна шлангова линия (Ø 75 mm)",
    "malka": "Работна шлангова линия (Ø 52 mm)",
    "smukatelna": "Смукателна линия",
    "shlang": "Шланг",
    "dvupaten": "Двупътен разклонител",
    "tripaten": "Трипътен разклонител",
    "chetiripaten": "Четирипътен разклонител",
    "malak": "Малък струйник с използване на вода",
    "glaven": "Главен струйник с използване на вода",
    "lafeten": "Лафетен струйник с използване на вода",
    "penostruinik": "Пеноструйник",
    "sglobna": "Стълба сглобна",
    "razdvizhna": "Стълба разтегателна",
    "shturmova": "Стълба щурмова",
    "palka": "Стълба палка",
    "shtab": "Място за разположение на щаба",
    "pbt": "Пост по безопасност на труда",
    "kpp": "Контролнопропусквателен пункт",
    "el": "Електрическо табло",
}
LEGEND_ORDER = ["sgrada", "ograda", "pozhar", "pozhar_otkrito", "zadimyavane", "ognishte", "posoka", "napravlenie",
                "vyatar", *TRUCKS, *WATER, "glavna", "malka", "smukatelna", "shlang", "dvupaten", "tripaten",
                "chetiripaten", *NOZZLES, *LADDERS, "shtab", "pbt", "kpp", "el"]


class Pal:
    """The colours: black and white for printing, or the colours that Приложение № 6 asks for."""

    def __init__(self, colour):
        self.fire = "#d0021b" if colour else INK
        self.water = "#1f5fbf" if colour else INK
        self.smoke = "#1f5fbf" if colour else "#555555"


def bad(msg):
    sys.stderr.write("BAD_INPUT: " + msg + "\n")
    sys.exit(2)


def num(v, what):
    try:
        f = float(v)
    except (TypeError, ValueError):
        bad(f"{what}: очаква се число, а е {v!r}")
    if math.isnan(f) or math.isinf(f):
        bad(f"{what}: очаква се число, а е {v!r}")
    return f


def pt(p, what):
    if not isinstance(p, (list, tuple)) or len(p) != 2:
        bad(f"{what}: очаква се [x, y], а е {p!r}")
    return num(p[0], what), num(p[1], what)


def rect(item, what, w_default=None, h_default=None):
    w = num(item.get("w", w_default), f"{what}.w")
    h = num(item.get("h", h_default), f"{what}.h")
    if w <= 0 or h <= 0:
        bad(f"{what}: ширината и височината трябва да са положителни")
    return {"x": num(item.get("x"), f"{what}.x"), "y": num(item.get("y"), f"{what}.y"), "w": w, "h": h}


def items(d, key):
    v = d.get(key) or []
    if isinstance(v, dict):
        v = [v]
    if not isinstance(v, list) or not all(isinstance(i, dict) for i in v):
        bad(f"{key}: очаква се списък от обекти")
    return v


# ---------------------------------------------------------------- geometry

def chaikin(points, rounds=3):
    """Smooths a polyline (keeps the end points) – the hose lines are drawn as soft curves."""
    pts = list(points)
    for _ in range(rounds if len(pts) > 2 else 0):
        new = [pts[0]]
        for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
            new += [(0.75 * x0 + 0.25 * x1, 0.75 * y0 + 0.25 * y1), (0.25 * x0 + 0.75 * x1, 0.25 * y0 + 0.75 * y1)]
        new.append(pts[-1])
        pts = new
    return pts


def length(pts):
    return sum(math.dist(a, b) for a, b in zip(pts, pts[1:]))


def point_at(pts, dist):
    """The point and the unit direction at a distance along the polyline."""
    for a, b in zip(pts, pts[1:]):
        seg = math.dist(a, b)
        if seg and dist <= seg:
            t = dist / seg
            return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t), ((b[0] - a[0]) / seg, (b[1] - a[1]) / seg)
        dist -= seg
    a, b = pts[-2], pts[-1]
    seg = math.dist(a, b) or 1.0
    return b, ((b[0] - a[0]) / seg, (b[1] - a[1]) / seg)


def dist_to_segment(p, a, b):
    (px, py), (ax_, ay), (bx, by) = p, a, b
    dx, dy = bx - ax_, by - ay
    if dx == dy == 0:
        return math.dist(p, a)
    t = max(0, min(1, ((px - ax_) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    return math.dist(p, (ax_ + t * dx, ay + t * dy))


def overlap(a0, a1, b0, b1):
    return min(a1, b1) - max(a0, b0) > 0


def label_point(b, fires):
    """The centre of the building's label – in the biggest part of the building that no fire covers,
    so that the hatching does not hide the name."""
    cx, cy = b["x"] + b["w"] / 2, b["y"] + b["h"] / 2
    inside = [f for f in fires if overlap(b["x"], b["x"] + b["w"], f["x"], f["x"] + f["w"])
              and overlap(b["y"], b["y"] + b["h"], f["y"], f["y"] + f["h"])]
    if not inside:
        return cx, cy
    horiz = b["w"] >= b["h"]                           # look for a free strip along the longer side
    lo, hi = (b["x"], b["x"] + b["w"]) if horiz else (b["y"], b["y"] + b["h"])
    cuts = sorted((max(lo, f["x"] if horiz else f["y"]), min(hi, (f["x"] + f["w"]) if horiz else (f["y"] + f["h"])))
                  for f in inside)
    gaps, cur = [], lo
    for c0, c1 in cuts:
        if c0 > cur:
            gaps.append((cur, c0))
        cur = max(cur, c1)
    if cur < hi:
        gaps.append((cur, hi))
    if not gaps:
        return cx, cy
    g0, g1 = max(gaps, key=lambda g: g[1] - g[0])
    return ((g0 + g1) / 2, cy) if horiz else (cx, (g0 + g1) / 2)


def rotate(x, y, angle, pts):
    a = math.radians(angle)
    return [(x + px * math.cos(a) - py * math.sin(a), y + px * math.sin(a) + py * math.cos(a)) for px, py in pts]


def readable(angle):
    """A text angle that is never upside down."""
    a = angle % 360
    return a - 180 if 90 < a <= 270 else a


# ---------------------------------------------------------------- symbols (s = symbol size in drawing units)

def draw_building(ax, x, y, w, h, roof=None, lw=1.8):
    ax.add_patch(Rectangle((x, y), w, h, fill=False, ec=INK, lw=lw, zorder=3))
    if roof != "dvuskaten":
        return
    if w >= h:                                         # the ridge along the longer side, hips to the corners
        r0, r1 = (x + h / 2, y + h / 2), (x + w - h / 2, y + h / 2)
        pairs = (((x, y), r0), ((x, y + h), r0), ((x + w, y), r1), ((x + w, y + h), r1))
    else:
        r0, r1 = (x + w / 2, y + w / 2), (x + w / 2, y + h - w / 2)
        pairs = (((x, y), r0), ((x + w, y), r0), ((x, y + h), r1), ((x + w, y + h), r1))
    for c, r in pairs:
        ax.plot([c[0], r[0]], [c[1], r[1]], color=INK, lw=0.6, zorder=3)
    ax.plot([r0[0], r1[0]], [r0[1], r1[1]], color=INK, lw=0.6, zorder=3)


def draw_dimension(ax, a, b, text, off, fs):
    """A dimension line parallel to a–b, moved by off (a vector), with arrows and the value."""
    (x0, y0), (x1, y1) = a, b
    ox, oy = off
    for (px, py) in (a, b):                            # extension lines
        ax.plot([px, px + ox * 1.15], [py, py + oy * 1.15], color=INK, lw=0.4, zorder=2)
    ax.annotate("", (x0 + ox, y0 + oy), (x1 + ox, y1 + oy),
                arrowprops=dict(arrowstyle="<->", lw=0.5, color=INK, shrinkA=0, shrinkB=0), zorder=2)
    mx, my = (x0 + x1) / 2 + ox, (y0 + y1) / 2 + oy
    rot = 90 if abs(x1 - x0) < abs(y1 - y0) else 0
    ax.text(mx, my, text, ha="center", va="center", fontsize=fs, rotation=rot, zorder=4,
            bbox=dict(fc="white", ec="none", pad=0.6))


def draw_fire(ax, f, s, pal):
    ax.add_patch(Rectangle((f["x"], f["y"]), f["w"], f["h"], fill=False, hatch="xxxx", ec=pal.fire, lw=1.0, zorder=3))
    if not f["na_otkrito"]:
        draw_flag(ax, f["x"] + f["w"] / 2, f["y"] + f["h"] / 2, s, pal)


def draw_flag(ax, x, y, s, pal):
    ax.plot([x, x], [y - 0.35 * s, y + 0.55 * s], color=INK, lw=1.2, zorder=6)
    ax.add_patch(Polygon([(x, y + 0.55 * s), (x + 0.5 * s, y + 0.38 * s), (x, y + 0.21 * s)],
                         closed=True, fc=pal.fire if pal.fire != INK else "white", ec=INK, lw=1.0, zorder=6))


def draw_smoke(ax, z, s, pal):
    """A zone of smoke: a dashed outline filled with wavy lines."""
    x, y, w, h = z["x"], z["y"], z["w"], z["h"]
    clip = Rectangle((x, y), w, h, fill=False, ec=pal.smoke, lw=0.7, ls=(0, (3, 2)), zorder=2.6)
    ax.add_patch(clip)
    step = max(0.45 * s, 0.6)
    amp, wave = 0.12 * s, 0.9 * s
    yy = y + step / 2
    while yy < y + h:
        xs = [x + i * wave / 12 for i in range(int(w / (wave / 12)) + 2)]
        ys = [yy + amp * math.sin(2 * math.pi * (px - x) / wave) for px in xs]
        line, = ax.plot(xs, ys, color=pal.smoke, lw=0.5, zorder=2.5)
        line.set_clip_path(clip)
        yy += step


def draw_seat(ax, x, y, s, pal):
    """The seat of the fire: a filled circle in a ring."""
    ax.add_patch(Circle((x, y), 0.32 * s, fc="white", ec=pal.fire, lw=1.1, zorder=7))
    ax.add_patch(Circle((x, y), 0.17 * s, fc=pal.fire, ec=pal.fire, zorder=7))


def draw_spread(ax, a, b, pal, scale=16):
    ax.add_patch(FancyArrowPatch(a, b, arrowstyle="simple,head_length=0.9,head_width=0.9,tail_width=0.35",
                                 mutation_scale=scale, fc=pal.fire, ec=pal.fire, zorder=7))


def draw_main_direction(ax, a, b, scale=16):
    """The main direction of the attack: a hollow wide arrow."""
    ax.add_patch(FancyArrowPatch(a, b, arrowstyle="fancy,head_length=0.8,head_width=0.9,tail_width=0.5",
                                 mutation_scale=scale, fc="white", ec=INK, lw=1.1, zorder=7))


def draw_truck(ax, t, s, fs):
    """Fire engine: a long body with a pointed front; the pump at the rear. A plain engine has a dark bar
    inside, the special vehicles carry their letters instead."""
    x, y, angle, kind = t["x"], t["y"], t["ugal"], t["vid"]
    L, W = 1.6 * s, 0.55 * s
    body = [(-L / 2, -W / 2), (L / 2 - 0.25 * s, -W / 2), (L / 2, 0), (L / 2 - 0.25 * s, W / 2), (-L / 2, W / 2)]
    pump = [(-L / 2 - 0.22 * s, -0.11 * s), (-L / 2, -0.11 * s), (-L / 2, 0.11 * s), (-L / 2 - 0.22 * s, 0.11 * s)]
    ax.add_patch(Polygon(rotate(x, y, angle, body), closed=True, fc="white", ec=INK, lw=1.1, zorder=8))
    ax.add_patch(Polygon(rotate(x, y, angle, pump), closed=True, fc="white", ec=INK, lw=0.9, zorder=8))
    letters = TRUCKS[kind]
    if letters:
        cx, cy = rotate(x, y, angle, [(-0.1 * s, 0)])[0]
        ax.text(cx, cy, letters, ha="center", va="center", fontsize=fs - 1.5, rotation=readable(angle), zorder=9)
    else:
        bar = [(-L / 2 + 0.12 * s, -W / 4), (L / 2 - 0.4 * s, -W / 4), (L / 2 - 0.4 * s, W / 4), (-L / 2 + 0.12 * s, W / 4)]
        ax.add_patch(Polygon(rotate(x, y, angle, bar), closed=True, fc="#555555", ec=INK, lw=0.6, zorder=9))
    if kind == "pa_lafeten":                            # the monitor on the roof, pointing forward
        a, b = rotate(x, y, angle, [(0, 0), (L / 2 + 0.45 * s, 0)])
        ax.annotate("", b, a, arrowprops=dict(arrowstyle="-|>,head_length=0.5,head_width=0.3", lw=1.1, color=INK,
                                              fc=INK, shrinkA=0, shrinkB=0), zorder=10)


def draw_reservoir(ax, x, y, s, label, fs, pal):
    w, h = 2.4 * s, 0.95 * s
    ax.add_patch(Rectangle((x - w / 2, y - h / 2), w, h, fc="white", ec=pal.water, lw=1.1, zorder=8))
    ax.add_patch(Rectangle((x - w / 2 + 0.1 * s, y - h / 2 + 0.1 * s), w - 0.2 * s, h - 0.2 * s,
                           fill=False, ec=pal.water, lw=0.4, zorder=8))
    if label:
        ax.text(x, y, label, ha="center", va="center", fontsize=fs, zorder=9)


def draw_hydrant(ax, x, y, s, label, fs, pal, above=False):
    """Underground hydrant – a circle with a cross; above-ground – a circle with a stem."""
    ax.add_patch(Circle((x, y), 0.32 * s, fc="white", ec=pal.water, lw=1.1, zorder=8))
    if above:
        ax.plot([x, x], [y - 0.32 * s, y + 0.55 * s], color=pal.water, lw=1.1, zorder=9)
        ax.plot([x - 0.18 * s, x + 0.18 * s], [y + 0.55 * s, y + 0.55 * s], color=pal.water, lw=1.1, zorder=9)
    else:
        ax.plot([x - 0.2 * s, x + 0.2 * s], [y, y], color=pal.water, lw=0.8, zorder=9)
        ax.plot([x, x], [y - 0.2 * s, y + 0.2 * s], color=pal.water, lw=0.8, zorder=9)
    if label:
        ax.text(x + 0.45 * s, y, label, ha="left", va="center", fontsize=fs, zorder=9,
                bbox=dict(fc="white", ec="none", pad=0.4))


def draw_line(ax, pts, kind, s, hose_m):
    """A hose line with a short cross tick at every hose length; returns the number of hoses."""
    xs, ys = zip(*pts)
    ax.plot(xs, ys, color=INK, lw=LINE_KINDS[kind], solid_capstyle="round", zorder=5)
    if kind == "smukatelna" or not hose_m:
        return 0
    total = length(pts)
    n = int(total // hose_m)
    for i in range(1, n + 1):
        if total - i * hose_m < 0.3 * s:              # no tick right on the nozzle or the splitter
            continue
        (px, py), (dx, dy) = point_at(pts, i * hose_m)
        nx, ny = -dy, dx
        k = 0.24 * s
        ax.plot([px - nx * k, px + nx * k], [py - ny * k, py + ny * k], color=INK, lw=0.9, zorder=5)
    return max(1, math.ceil(total / hose_m - 0.25))


def draw_nozzle(ax, end, direction, kind, s):
    (x, y), (dx, dy) = end, direction
    tip = (x + dx * 0.6 * s, y + dy * 0.6 * s)
    if kind == "malak":
        style, lw = "->,head_length=0.5,head_width=0.3", 1.1
    else:
        style, lw = "-|>,head_length=0.6,head_width=0.35", 1.4
    ax.annotate("", tip, (x, y), arrowprops=dict(arrowstyle=style, lw=lw, color=INK, fc=INK, shrinkA=0, shrinkB=0),
                zorder=6)
    q = 0.14 * s
    if kind == "lafeten":
        ax.add_patch(Rectangle((x - q, y - q), 2 * q, 2 * q, fc=INK, ec=INK, zorder=6))
    elif kind == "penostruinik":
        ax.add_patch(Circle((x, y), q, fc="white", ec=INK, lw=1.0, zorder=6))
    elif kind == "glaven":
        nx, ny = -dy * q, dx * q
        ax.plot([x - nx, x + nx], [y - ny, y + ny], color=INK, lw=1.2, zorder=6)


def draw_splitter(ax, x, y, s, ways):
    """A splitter: the stem and one branch less than the ways."""
    k = 0.3 * s
    ax.plot([x, x], [y - k, y], color=INK, lw=1.1, zorder=7)
    outs = {2: [0], 3: [-35, 35], 4: [-50, 0, 50]}[ways]
    for a in outs:
        r = math.radians(90 + a)
        ax.plot([x, x + math.cos(r) * k], [y, y + math.sin(r) * k], color=INK, lw=1.1, zorder=7)
    ax.add_patch(Circle((x, y), 0.07 * s, fc=INK, ec=INK, zorder=7))


def draw_ladder(ax, a, b, s, kind):
    (x0, y0), (x1, y1) = a, b
    d = math.dist(a, b) or 1.0
    ux, uy = (x1 - x0) / d, (y1 - y0) / d
    half = 0.24 * s
    nx, ny = -uy * half, ux * half
    for sgn in (-1, 1):
        ax.plot([x0 + sgn * nx, x1 + sgn * nx], [y0 + sgn * ny, y1 + sgn * ny], color=INK, lw=1.0, zorder=6)
    steps = max(3, int(d / (0.3 * s)))
    for i in range(steps + 1):
        px, py = x0 + (x1 - x0) * i / steps, y0 + (y1 - y0) * i / steps
        ax.plot([px - nx, px + nx], [py - ny, py + ny], color=INK, lw=0.8, zorder=6)
    if kind == "shturmova":                             # the hook at the top
        ax.plot([x1 + nx, x1 + nx + ux * 0.25 * s - nx * 0.6], [y1 + ny, y1 + ny + uy * 0.25 * s - ny * 0.6],
                color=INK, lw=1.0, zorder=6)
    elif kind == "razdvizhna":                          # the second flight beside the first
        ax.plot([x0 + 2 * nx, x1 + 2 * nx], [y0 + 2 * ny, y1 + 2 * ny], color=INK, lw=0.7, zorder=6)


def draw_fence(ax, pts, gates, s):
    closed = list(pts) + [pts[0]]
    xs, ys = zip(*closed)
    ax.plot(xs, ys, color=INK, lw=1.0, ls=(0, (1.2, 1.2)), zorder=1)
    for g in gates:
        gx, gy, gw = g["x"], g["y"], g["shirina"]
        horiz = g["horiz"]
        a = (gx - gw / 2, gy) if horiz else (gx, gy - gw / 2)
        b = (gx + gw / 2, gy) if horiz else (gx, gy + gw / 2)
        ax.plot([a[0], b[0]], [a[1], b[1]], color="white", lw=4, zorder=1.5)
        for p in (a, b):                              # the gate posts
            k = 0.3 * s
            ax.plot([p[0] - (0 if horiz else k), p[0] + (0 if horiz else k)],
                    [p[1] - (k if horiz else 0), p[1] + (k if horiz else 0)], color=INK, lw=1.2, zorder=2)


def draw_label_box(ax, x, y, w, h, text, fs, rounded=False):
    if rounded:
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle=f"round,pad=0,rounding_size={min(w, h) / 2}",
                                    fc="white", ec=INK, lw=0.9, zorder=8))
    else:
        ax.add_patch(Rectangle((x, y), w, h, fc="white", ec=INK, lw=0.9, zorder=8))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fs, zorder=9)


def draw_staff(ax, x, y, s, fs):
    """The place of the staff: a flag with „Щ“."""
    ax.plot([x, x], [y, y + 1.1 * s], color=INK, lw=1.2, zorder=8)
    ax.add_patch(Rectangle((x, y + 0.5 * s), 0.75 * s, 0.6 * s, fc="white", ec=INK, lw=1.0, zorder=8))
    ax.text(x + 0.375 * s, y + 0.8 * s, "Щ", ha="center", va="center", fontsize=fs, zorder=9)


def draw_north(ax, x, y, s, fs):
    ax.annotate("", (x, y + 1.0 * s), (x, y),
                arrowprops=dict(arrowstyle="-|>,head_length=0.8,head_width=0.4", lw=1.0, color=INK, fc=INK), zorder=9)
    ax.text(x, y + 1.15 * s, "С", ha="center", va="bottom", fontsize=fs, zorder=9)


def draw_wind(ax, x, y, angle, force, s, fs):
    """The wind: an arrow along the direction it blows to, with feathers at the tail, and the speed."""
    a = math.radians(angle)
    ux, uy = math.cos(a), math.sin(a)
    tail = (x - ux * 0.7 * s, y - uy * 0.7 * s)
    head = (x + ux * 0.7 * s, y + uy * 0.7 * s)
    ax.annotate("", head, tail, arrowprops=dict(arrowstyle="-|>,head_length=0.6,head_width=0.3", lw=1.0,
                                                color=INK, fc=INK, shrinkA=0, shrinkB=0), zorder=9)
    for k in (0.0, 0.22):                              # two feathers
        fx, fy = tail[0] + ux * k * s, tail[1] + uy * k * s
        ax.plot([fx, fx - math.cos(a - 0.7) * 0.3 * s], [fy, fy - math.sin(a - 0.7) * 0.3 * s], color=INK, lw=0.9, zorder=9)
    if force:
        ax.text(x, y - 0.95 * s, force, ha="center", va="top", fontsize=fs - 0.5, zorder=9)


def scale_step(units):
    raw = units / 5
    return next((v for v in (1, 2, 5, 10, 20, 25, 50, 100, 200, 500, 1000) if v >= raw), 1000)


# ---------------------------------------------------------------- input

def load(d):
    warnings = []
    if not isinstance(d, dict):
        bad("схемата трябва да е JSON обект")
    out = {k: [] for k in ("sgradi", "obekti", "pozhar", "zadimyavane", "ognishte", "posoka", "napravlenie",
                           "avtomobili", "vodoiztochnitsi", "linii", "razklonitel", "stalbi", "shtab", "pbt",
                           "tekst", "vhodove")}
    out["ograda"] = None
    out["vyatar"] = None
    for i, b in enumerate(items(d, "sgradi")):
        r = rect(b, f"sgradi[{i}]")
        if b.get("pokriv") not in (None, "", "plosak", "dvuskaten"):
            bad(f"sgradi[{i}].pokriv: „dvuskaten“ или „plosak“")
        out["sgradi"].append({**r, "etiket": str(b.get("etiket") or ""), "razmeri": b.get("razmeri", True),
                              "pokriv": b.get("pokriv")})
    for i, b in enumerate(items(d, "obekti")):
        out["obekti"].append({**rect(b, f"obekti[{i}]", 5, 3), "etiket": str(b.get("etiket") or ""),
                              "legenda": str(b.get("legenda") or "")})
    for i, f in enumerate(items(d, "pozhar")):
        out["pozhar"].append({**rect(f, f"pozhar[{i}]"), "etiket": str(f.get("etiket") or ""),
                              "na_otkrito": bool(f.get("na_otkrito", False))})
    for i, z in enumerate(items(d, "zadimyavane")):
        out["zadimyavane"].append(rect(z, f"zadimyavane[{i}]"))
    for i, o in enumerate(items(d, "ognishte")):
        out["ognishte"].append((num(o.get("x"), f"ognishte[{i}].x"), num(o.get("y"), f"ognishte[{i}].y")))
    for key in ("posoka", "napravlenie"):
        for i, a in enumerate(items(d, key)):
            out[key].append((pt(a.get("ot"), f"{key}[{i}].ot"), pt(a.get("do"), f"{key}[{i}].do")))
    for i, t in enumerate(items(d, "avtomobili")):
        kind = t.get("vid") or "pa"
        if kind not in TRUCKS:
            bad(f"avtomobili[{i}].vid: {', '.join(TRUCKS)}")
        out["avtomobili"].append({"id": str(t.get("id") or f"{i + 1} ПА"), "vid": kind,
                                  "x": num(t.get("x"), f"avtomobili[{i}].x"), "y": num(t.get("y"), f"avtomobili[{i}].y"),
                                  "ugal": num(t.get("ugal", 0), f"avtomobili[{i}].ugal")})
    for i, w in enumerate(items(d, "vodoiztochnitsi")):
        kind = w.get("vid") or "hidrant"
        if kind not in WATER:
            bad(f"vodoiztochnitsi[{i}].vid: {', '.join(WATER)}")
        out["vodoiztochnitsi"].append({"vid": kind, "x": num(w.get("x"), f"vodoiztochnitsi[{i}].x"),
                                       "y": num(w.get("y"), f"vodoiztochnitsi[{i}].y"), "etiket": str(w.get("etiket") or "")})
    for i, ln in enumerate(items(d, "linii")):
        kind = ln.get("vid") or "malka"
        if kind not in LINE_KINDS:
            bad(f"linii[{i}].vid: {', '.join(LINE_KINDS)}")
        pts = [pt(p, f"linii[{i}].tochki") for p in (ln.get("tochki") or [])]
        if len(pts) < 2:
            bad(f"linii[{i}].tochki: трябват поне две точки")
        nozzle = ln.get("struinik")
        if nozzle not in (None, "", *NOZZLES):
            bad(f"linii[{i}].struinik: {', '.join(NOZZLES)}")
        out["linii"].append({"tochki": pts, "vid": kind, "struinik": nozzle or None,
                             "etiket": str(ln.get("etiket") or ""), "gladka": ln.get("gladka", True)})
    for i, r in enumerate(items(d, "razklonitel")):
        ways = int(num(r.get("patya", 3), f"razklonitel[{i}].patya"))
        if ways not in SPLITTERS:
            bad(f"razklonitel[{i}].patya: 2, 3 или 4")
        out["razklonitel"].append((num(r.get("x"), f"razklonitel[{i}].x"), num(r.get("y"), f"razklonitel[{i}].y"), ways))
    for i, st in enumerate(items(d, "stalbi")):
        kind = st.get("vid") or "sglobna"
        if kind not in LADDERS:
            bad(f"stalbi[{i}].vid: {', '.join(LADDERS)}")
        out["stalbi"].append({"ot": pt(st.get("ot"), f"stalbi[{i}].ot"), "do": pt(st.get("do"), f"stalbi[{i}].do"),
                              "vid": kind})
    for key in ("shtab", "pbt"):
        for i, o in enumerate(items(d, key)):
            out[key].append((num(o.get("x"), f"{key}[{i}].x"), num(o.get("y"), f"{key}[{i}].y")))
    for i, t in enumerate(items(d, "tekst")):
        out["tekst"].append({"x": num(t.get("x"), f"tekst[{i}].x"), "y": num(t.get("y"), f"tekst[{i}].y"),
                             "tekst": str(t.get("tekst") or ""), "ugal": num(t.get("ugal", 0), f"tekst[{i}].ugal")})
    if d.get("ograda"):
        out["ograda"] = [pt(p, "ograda") for p in d["ograda"]]
        if len(out["ograda"]) < 3:
            bad("ograda: трябват поне три точки")
    for i, g in enumerate(items(d, "vhodove")):
        out["vhodove"].append({"x": num(g.get("x"), f"vhodove[{i}].x"), "y": num(g.get("y"), f"vhodove[{i}].y"),
                               "shirina": num(g.get("shirina", 6), f"vhodove[{i}].shirina"),
                               "etiket": str(g.get("etiket") or ""), "horiz": True})
    if d.get("vyatar"):
        v = d["vyatar"]
        if not isinstance(v, dict):
            bad("vyatar: очаква се обект {\"ugal\", \"sila\"}")
        out["vyatar"] = {"ugal": num(v.get("ugal"), "vyatar.ugal"), "sila": str(v.get("sila") or "")}
    if not out["sgradi"]:
        bad("няма нито една сграда в \"sgradi\"")

    # the extent of the drawing
    xs, ys = [], []
    for b in out["sgradi"] + out["obekti"] + out["pozhar"] + out["zadimyavane"]:
        xs += [b["x"], b["x"] + b["w"]]
        ys += [b["y"], b["y"] + b["h"]]
    for coll in (out["avtomobili"], out["vodoiztochnitsi"], out["vhodove"]):
        xs += [o["x"] for o in coll]
        ys += [o["y"] for o in coll]
    for p in out["ognishte"] + [r[:2] for r in out["razklonitel"]] + out["shtab"] + out["pbt"]:
        xs.append(p[0])
        ys.append(p[1])
    for ln in out["linii"]:
        xs += [p[0] for p in ln["tochki"]]
        ys += [p[1] for p in ln["tochki"]]
    for a, b in out["posoka"] + out["napravlenie"] + [(s["ot"], s["do"]) for s in out["stalbi"]]:
        xs += [a[0], b[0]]
        ys += [a[1], b[1]]
    if out["ograda"]:
        xs += [p[0] for p in out["ograda"]]
        ys += [p[1] for p in out["ograda"]]
    if d.get("teren"):
        tw, th = pt(d["teren"], "teren")
        if tw <= 0 or th <= 0:
            bad("teren: ширината и височината трябва да са положителни")
        x0, y0, x1, y1 = 0.0, 0.0, tw, th
        if min(xs) < 0 or min(ys) < 0 or max(xs) > tw or max(ys) > th:
            warnings.append("има елементи извън терена – провери координатите или увеличи \"teren\"")
            x0, y0, x1, y1 = min(x0, min(xs)), min(y0, min(ys)), max(x1, max(xs)), max(y1, max(ys))
    else:
        pad = 0.08 * max(max(xs) - min(xs), max(ys) - min(ys), 10)
        x0, y0, x1, y1 = min(xs) - pad, min(ys) - pad, max(xs) + pad, max(ys) + pad
    out["box"] = (x0, y0, x1, y1)
    out["s"] = symbol_size(x1 - x0, y1 - y0)

    # the gates sit on the fence – find the side each one is on
    if out["vhodove"] and out["ograda"]:
        sides = list(zip(out["ograda"], out["ograda"][1:] + out["ograda"][:1]))
        for g in out["vhodove"]:
            best = min(sides, key=lambda sd: dist_to_segment((g["x"], g["y"]), *sd))
            g["horiz"] = abs(best[1][0] - best[0][0]) >= abs(best[1][1] - best[0][1])
            if dist_to_segment((g["x"], g["y"]), *best) > 2:
                warnings.append(f"входът „{g['etiket'] or g['x']}“ не е върху оградата")

    # every hose line must start at a fire engine, a splitter, a water source or the end of another line
    anchors = [(t["x"], t["y"]) for t in out["avtomobili"]] + [r[:2] for r in out["razklonitel"]] + \
              [(w["x"], w["y"]) for w in out["vodoiztochnitsi"]]
    for i, ln in enumerate(out["linii"]):
        others = [p for j, o in enumerate(out["linii"]) if j != i for p in (o["tochki"][0], o["tochki"][-1])]
        start = ln["tochki"][0]
        near = min((math.dist(start, a) for a in anchors + others), default=1e9)
        if near > max(3.5, 1.3 * out["s"]):
            warnings.append(f"линия № {i + 1} ({ln['vid']}) не започва до автомобил, разклонител, водоизточник "
                            f"или друга линия (най-близо е на {near:.0f} m)")
    for i, ln in enumerate(out["linii"]):
        if ln["vid"] == "smukatelna" and ln["struinik"]:
            warnings.append(f"линия № {i + 1} е смукателна, а има струйник – струйникът е пропуснат")
            ln["struinik"] = None
    return out, warnings


def symbol_size(wu, hu):
    """The size of a symbol (a fire engine is 1.6 of it long) in drawing units – about 4.5 % of the drawing."""
    return min(0.045 * max(wu, hu), 0.11 * min(wu, hu) + 0.02 * max(wu, hu))


def legend_keys(data, d, hose_m):
    used = {"sgrada"}
    if data["ograda"]:
        used.add("ograda")
    used.update("pozhar_otkrito" if f["na_otkrito"] else "pozhar" for f in data["pozhar"])
    for key in ("zadimyavane", "ognishte", "posoka", "napravlenie", "shtab", "pbt"):
        if data[key]:
            used.add(key)
    if data["vyatar"]:
        used.add("vyatar")
    used.update(t["vid"] for t in data["avtomobili"])
    used.update(w["vid"] for w in data["vodoiztochnitsi"])
    used.update(ln["vid"] for ln in data["linii"])
    if hose_m and any(ln["vid"] != "smukatelna" for ln in data["linii"]):
        used.add("shlang")
    used.update(SPLITTERS[r[2]] for r in data["razklonitel"])
    used.update(ln["struinik"] for ln in data["linii"] if ln["struinik"])
    used.update(st["vid"] for st in data["stalbi"])
    if any(g["etiket"].strip().upper() == "КПП" for g in data["vhodove"]) or \
            any(o["etiket"].strip().upper() == "КПП" for o in data["obekti"]):
        used.add("kpp")
    if any(o["etiket"].strip().lower() in ("ел", "ел.", "ел. табло") for o in data["obekti"]):
        used.add("el")
    keys = [k for k in LEGEND_ORDER if k in used]
    extra = [(None, o["legenda"], o["etiket"]) for o in data["obekti"] if o["legenda"]]
    return keys, extra


# ---------------------------------------------------------------- drawing

def render(d, out_png, out_svg=None):
    data, warnings = load(d)
    pal = Pal(bool(d.get("cvetna", False)))
    x0, y0, x1, y1 = data["box"]
    wu, hu = x1 - x0, y1 - y0
    s = data["s"]                                      # the size of a symbol in drawing units (m)
    hose_m = num(d.get("shlang_m", 20) or 0, "shlang_m")
    keys, extra = legend_keys(data, d, hose_m) if d.get("legenda", True) else ([], [])

    width_in = WIDTH_CM / 2.54
    draw_h_in = min(width_in * hu / wu, MAX_DRAW_HEIGHT_CM / 2.54)
    draw_w_in = draw_h_in * wu / hu
    fs = 7.0
    # the legend: two columns, long names wrapped
    entries = [(k, textwrap.wrap(LEGEND_TEXT[k], 40)) for k in keys] + \
              [("obekt", textwrap.wrap(text, 40), label) for _, text, label in extra]
    col_rows = [entries[0::2], entries[1::2]]
    row_lines = [max(len(e[1]) for e in pair if e) for pair in zip(col_rows[0], col_rows[1] + [None] * len(col_rows[0]))
                 if pair[0] is not None]
    line_in = 0.13
    legend_h_in = (sum(0.12 + line_in * n for n in row_lines) + 0.3) if entries else 0.0
    title = str(d.get("zaglavie") or "")
    title_in = 0.3 if title else 0.0
    fig_h = draw_h_in + legend_h_in + title_in
    fig = plt.figure(figsize=(width_in, fig_h), dpi=300)
    if title:
        fig.text(0.5, 1 - title_in / 2 / fig_h, title, ha="center", va="center", fontsize=fs + 2)
    left = (width_in - draw_w_in) / 2 / width_in
    ax = fig.add_axes([left, legend_h_in / fig_h, draw_w_in / width_in, draw_h_in / fig_h])
    ax.set_xlim(x0, x1)
    ax.set_ylim(y0, y1)
    ax.set_aspect("equal")
    ax.set_xticks([])
    ax.set_yticks([])
    for sp in ax.spines.values():
        sp.set_linewidth(0.8)

    if data["ograda"]:
        draw_fence(ax, data["ograda"], data["vhodove"], s)
    for g in data["vhodove"]:
        if g["etiket"]:
            bw, bh = max(2.4 * s, 0.6 * s * len(g["etiket"])), 0.85 * s
            if g["horiz"]:
                gx = g["x"] - bw / 2
                gy = g["y"] + 0.6 * s if g["y"] < (y0 + y1) / 2 else g["y"] - 0.6 * s - bh
            else:
                gx = g["x"] + 0.6 * s if g["x"] < (x0 + x1) / 2 else g["x"] - 0.6 * s - bw
                gy = g["y"] - bh / 2
            draw_label_box(ax, gx, gy, bw, bh, g["etiket"], fs)
    for z in data["zadimyavane"]:
        draw_smoke(ax, z, s, pal)
    for b in data["sgradi"]:
        draw_building(ax, b["x"], b["y"], b["w"], b["h"], b["pokriv"])
        if b["etiket"]:
            lx, ly = label_point(b, data["pozhar"] + data["zadimyavane"])
            ax.text(lx, ly, b["etiket"].replace("\\n", "\n"), ha="center", va="center", fontsize=fs + 0.5, zorder=4,
                    linespacing=1.2, bbox=dict(fc="white", ec="none", pad=1.0, alpha=0.9))
        if b["razmeri"]:
            off = 0.75 * s
            draw_dimension(ax, (b["x"], b["y"]), (b["x"] + b["w"], b["y"]), f"{b['w']:g}", (0, -off), fs - 0.5)
            draw_dimension(ax, (b["x"] + b["w"], b["y"]), (b["x"] + b["w"], b["y"] + b["h"]), f"{b['h']:g}",
                           (off, 0), fs - 0.5)
    for o in data["obekti"]:
        draw_label_box(ax, o["x"], o["y"], o["w"], o["h"], o["etiket"], fs)
    for f in data["pozhar"]:
        draw_fire(ax, f, s, pal)
        if f["etiket"]:
            ax.text(f["x"] + f["w"] / 2, f["y"] - 0.25 * s, f["etiket"], ha="center", va="top", fontsize=fs,
                    zorder=7, bbox=dict(fc="white", ec="none", pad=0.6))
    for x, y in data["ognishte"]:
        draw_seat(ax, x, y, s, pal)
    for a, b in data["posoka"]:
        draw_spread(ax, a, b, pal)
    for a, b in data["napravlenie"]:
        draw_main_direction(ax, a, b)
    hoses = 0
    for ln in data["linii"]:
        pts = chaikin(ln["tochki"]) if ln["gladka"] else ln["tochki"]
        hoses += draw_line(ax, pts, ln["vid"], s, hose_m)
        _, direction = point_at(pts, length(pts))
        if ln["struinik"]:
            draw_nozzle(ax, pts[-1], direction, ln["struinik"], s)
        if ln["etiket"]:
            (ex, ey), (dx, dy) = pts[-1], direction
            ax.text(ex + dx * 0.3 * s - dy * 0.6 * s, ey + dy * 0.3 * s + dx * 0.6 * s, ln["etiket"], ha="center",
                    va="center", fontsize=fs, zorder=7, bbox=dict(fc="white", ec="none", pad=0.3))
    for x, y, ways in data["razklonitel"]:
        draw_splitter(ax, x, y, s, ways)
    for st in data["stalbi"]:
        draw_ladder(ax, st["ot"], st["do"], s, st["vid"])
    for w in data["vodoiztochnitsi"]:
        if w["vid"] == "vodoem":
            draw_reservoir(ax, w["x"], w["y"], s, w["etiket"], fs, pal)
        else:
            draw_hydrant(ax, w["x"], w["y"], s, w["etiket"], fs, pal, above=w["vid"] == "nadzemen_hidrant")
    for t in data["avtomobili"]:
        draw_truck(ax, t, s, fs)
        a = math.radians(t["ugal"] + 90)
        ax.text(t["x"] + math.cos(a) * 0.8 * s, t["y"] + math.sin(a) * 0.8 * s, t["id"], ha="center",
                va="center", fontsize=fs, zorder=10, bbox=dict(fc="white", ec="none", pad=0.5))
    for x, y in data["shtab"]:
        draw_staff(ax, x, y, s, fs)
    for x, y in data["pbt"]:
        draw_label_box(ax, x - 0.9 * s, y - 0.35 * s, 1.8 * s, 0.7 * s, "ПБТ", fs - 0.5, rounded=True)
    for t in data["tekst"]:
        ax.text(t["x"], t["y"], t["tekst"], ha="left", va="center", fontsize=fs, rotation=t["ugal"], zorder=9)
    # the north – in the upper left corner (чл. 9, ал. 5 от Указанията Iз-2749); the wind – under the drawing
    if d.get("sever", True):
        draw_north(ax, x0 + 0.9 * s, y1 - 2.4 * s, s, fs)

    if entries or d.get("mashtab", True) or data["vyatar"]:
        lax = fig.add_axes([0.0, 0.0, 1.0, max(legend_h_in, 0.35) / fig_h])
        lh = max(legend_h_in, 0.35)
        lax.set_xlim(0, width_in)
        lax.set_ylim(0, lh)
        lax.axis("off")
        top = lh - 0.15
        if entries:
            lax.text(0.15, top, "Условни знаци:", fontsize=fs, va="center")
        if d.get("mashtab", True):                     # the scale bar – in the legend's title row
            step = scale_step(wu)
            bar = step / wu * draw_w_in
            bx = width_in * 0.36
            lax.text(bx, top, "Мащаб:", fontsize=fs, va="center")
            bx += 0.55
            lax.plot([bx, bx + bar], [top, top], color=INK, lw=1.2)
            for px in (bx, bx + bar / 2, bx + bar):
                lax.plot([px, px], [top - 0.04, top + 0.04], color=INK, lw=0.9)
            lax.text(bx + bar + 0.06, top, f"{step:g} m", fontsize=fs, va="center")
        if data["vyatar"]:                             # the wind – at the right end of the title row
            wx = width_in - 1.25
            lax.text(wx, top, "Вятър:", fontsize=fs, va="center")
            draw_wind(lax, wx + 0.62, top, data["vyatar"]["ugal"], "", 0.2, fs)
            if data["vyatar"]["sila"]:
                lax.text(wx + 0.82, top, data["vyatar"]["sila"], fontsize=fs, va="center")
        cur = top - 0.2
        for r, n in enumerate(row_lines):
            cy = cur - line_in * (n - 1) / 2 - 0.02
            for col in (0, 1):
                if r < len(col_rows[col]):
                    e = col_rows[col][r]
                    cx = 0.3 + col * width_in / 2
                    legend_symbol(lax, e, cx, cy, pal, fs)
                    lax.text(cx + 0.42, cy, "\n".join(e[1]), fontsize=fs, va="center", linespacing=1.15)
            cur -= 0.12 + line_in * n

    fig.savefig(out_png, dpi=300, facecolor="white")
    if out_svg:
        fig.savefig(out_svg, facecolor="white")
    plt.close(fig)
    counts = {k: len(data[k]) for k in ("sgradi", "avtomobili", "linii", "vodoiztochnitsi", "pozhar")}
    return counts, hoses, warnings


def legend_symbol(ax, entry, x, y, pal, fs):
    """One symbol of the legend; the legend axes are in inches, a symbol is about 0.32 in wide."""
    key = entry[0]
    w, k = 0.16, 0.05
    if key == "sgrada":
        ax.add_patch(Rectangle((x - w, y - k), 2 * w, 2 * k, fill=False, ec=INK, lw=1.5))
    elif key == "ograda":
        ax.plot([x - w, x + w], [y, y], color=INK, lw=1.0, ls=(0, (1.2, 1.2)))
    elif key in ("pozhar", "pozhar_otkrito"):
        ax.add_patch(Rectangle((x - w, y - k), 2 * w, 2 * k, fill=False, hatch="xxxx", ec=pal.fire, lw=0.9))
        if key == "pozhar":
            ax.plot([x, x], [y - k, y + 1.6 * k], color=INK, lw=1.0)
            ax.add_patch(Polygon([(x, y + 1.6 * k), (x + 0.06, y + 1.2 * k), (x, y + 0.8 * k)], closed=True,
                                 fc=pal.fire if pal.fire != INK else "white", ec=INK, lw=0.8))
    elif key == "zadimyavane":
        ax.add_patch(Rectangle((x - w, y - k), 2 * w, 2 * k, fill=False, ec=pal.smoke, lw=0.6, ls=(0, (3, 2))))
        for dy in (-0.022, 0.022):
            xs = [x - w + i * 2 * w / 30 for i in range(31)]
            ax.plot(xs, [y + dy + 0.012 * math.sin(i / 30 * 4 * math.pi) for i in range(31)], color=pal.smoke, lw=0.5)
    elif key == "ognishte":
        ax.add_patch(Circle((x, y), 0.045, fc="white", ec=pal.fire, lw=1.0))
        ax.add_patch(Circle((x, y), 0.024, fc=pal.fire, ec=pal.fire))
    elif key == "posoka":
        draw_spread(ax, (x - w, y), (x + w, y), pal, scale=9)
    elif key == "napravlenie":
        draw_main_direction(ax, (x - w, y), (x + w, y), scale=9)
    elif key == "vyatar":
        draw_wind(ax, x, y, 0, "", 0.2, fs)
    elif key in TRUCKS:
        draw_truck(ax, {"x": x, "y": y, "ugal": 0, "vid": key}, 0.2, fs)
    elif key == "vodoem":
        ax.add_patch(Rectangle((x - w, y - k), 2 * w, 2 * k, fc="white", ec=pal.water, lw=1.0))
        ax.add_patch(Rectangle((x - w + 0.02, y - k + 0.015), 2 * w - 0.04, 2 * k - 0.03, fill=False, ec=pal.water, lw=0.4))
    elif key in ("hidrant", "nadzemen_hidrant"):
        draw_hydrant(ax, x, y - (0.03 if key == "nadzemen_hidrant" else 0), 0.17, "", fs, pal,
                     above=key == "nadzemen_hidrant")
    elif key in LINE_KINDS:
        ax.plot([x - w, x + w], [y, y], color=INK, lw=LINE_KINDS[key])
    elif key == "shlang":
        ax.plot([x - w, x + w], [y, y], color=INK, lw=1.1)
        ax.plot([x, x], [y - 0.045, y + 0.045], color=INK, lw=0.9)
    elif key in ("dvupaten", "tripaten", "chetiripaten"):
        draw_splitter(ax, x, y - 0.02, 0.22, {"dvupaten": 2, "tripaten": 3, "chetiripaten": 4}[key])
    elif key in NOZZLES:
        ax.plot([x - w, x - 0.02], [y, y], color=INK, lw=1.1)
        draw_nozzle(ax, (x - 0.02, y), (1, 0), key, 0.22)
    elif key in LADDERS:
        draw_ladder(ax, (x - w, y), (x + w, y), 0.2, key)
    elif key == "shtab":
        draw_staff(ax, x - 0.07, y - 0.1, 0.18, fs - 1)
    elif key == "pbt":
        draw_label_box(ax, x - w, y - 0.06, 2 * w, 0.12, "ПБТ", fs - 1, rounded=True)
    elif key == "kpp":
        draw_label_box(ax, x - w, y - 0.06, 2 * w, 0.12, "КПП", fs - 1)
    elif key == "el":
        draw_label_box(ax, x - 0.1, y - 0.06, 0.2, 0.12, "Ел", fs - 1)
    elif key == "obekt":
        draw_label_box(ax, x - w, y - 0.06, 2 * w, 0.12, entry[2], fs - 1)


def main():
    ap = argparse.ArgumentParser(description="Схема за разполагане на силите и средствата")
    ap.add_argument("shema", help="JSON файл със схемата")
    ap.add_argument("-o", "--out", required=True, help="изходен .png")
    ap.add_argument("--svg", help="и .svg")
    a = ap.parse_args()
    try:
        with open(a.shema, encoding="utf-8") as f:
            d = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        bad(f"не мога да прочета {a.shema}: {e}")
    os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
    counts, hoses, warnings = render(d, a.out, a.svg)
    print(json.dumps({"output": a.out, "svg": a.svg, "elementi": counts, "shlangove": hoses,
                      "preduprezhdeniya": warnings}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
