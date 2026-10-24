#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
znatsi.py — БИБЛИОТЕКАТА С УСЛОВНИТЕ ЗНАЦИ на схемите на плъгина fire-service. Всеки знак се чертае
само оттук – в схемата, в легендата ѝ и в каталога – за да са схемите на всички скилове еднакви.

Знаците и наименованията им са по Приложение № 6 към Указанията за разработване на планове за
пожарогасене, рег. № Iз-2749/18.11.2010 г. на МВР – част А (III: хидранти) и част Б („Условни
знаци, използвани при разработка на планове за пожарогасене“), по рисунките в приложенията (PDF на
МВР). Свои знаци на библиотеката (няма ги в приложението): сграда с размери, смукателна линия,
чертичката за шланг по линията и знакът за посоките – север и юг (draw_kompas).

Цветове (Pal): по подразбиране черно-бяло за печат; с цвят – както в приложението и по чл. 9, ал. 9 от
Указанията: автомобилите, пожарът, огнището, направленията и ел. таблата в червено; линиите,
струйниците, разклонителите, водоизточниците, водопроводната мрежа и крановете в синьо; улиците и
пътищата в кафяво; газопроводите и спирателната им арматура в жълто; площите, неразрешени за
паркиране – в оранжево.

Знаците на ситуационната схема (чл. 7, ал. 3 от Указанията): сключена и тупикова водопроводна мрежа,
пожарен кран, водонапорна кула, газопровод, улица (знакът „Шосе“) – по Приложение № 6; спирателната
арматура на газопровода и площта, неразрешена за паркиране, нямат знак в приложението – начертани
са по чл. 9, ал. 9 – 10 (цвят и легенда).

Всеки знак е функция draw_…(ax, …, s, …, pal), където s е размерът на знака в единиците на чертежа
(пожарният автомобил е около 1,7 s дълъг). obrazets(ax, (ключ, …), x, y, pal, fs) чертае малкото копие
за легендата по ключа от LEGEND_TEXT.

Каталог на всички знаци (за преглед и за сверка с приложението):

    python3 scripts/znatsi.py -o znatsi.png [--cvetna]

Друг скил ползва библиотеката така:

    sys.path.insert(0, os.path.join(<папката на skills>, "shemi", "scripts"))
    import znatsi as Z
    pal = Z.Pal(colour=False)
    Z.draw_truck(ax, {"x": 10, "y": 5, "ugal": 90, "vid": "pa"}, s=2.0, fs=7, pal=pal)
"""
import argparse
import math
import os
import sys
import textwrap

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Circle, FancyArrowPatch, PathPatch, Polygon, Rectangle, Wedge
    from matplotlib.path import Path as MPath
except ImportError:  # pragma: no cover
    sys.stderr.write("NO_MATPLOTLIB: pip install matplotlib\n")
    sys.exit(3)

matplotlib.rcParams["font.family"] = "DejaVu Sans"   # ships with matplotlib – the same look everywhere

matplotlib.rcParams["hatch.linewidth"] = 0.6

matplotlib.rcParams["svg.fonttype"] = "none"

INK = "black"

LINE_KINDS = {"glavna": 1.9, "malka": 1.1, "smukatelna": 2.6}

NOZZLES = ("malak", "glaven", "lafeten", "penostruinik", "prahov")

PLACES = {"pokriv": "п", "etazh": "е", "maze": "м"}

WATER = ("vodoem", "hidrant", "nadzemen_hidrant", "kran", "kula")

NETWORKS = {"skluchena": "С", "tupikova": "Т"}     # the letter of the water main's label „С-150/5“

SITUATION = ("imot", "ulitsa", "bez_parkirane", *NETWORKS, "gazoprovod", "gaz_armatura")
PARCEL_LS = (0, (6, 2, 1, 2))                       # the parcel's boundary: dash-dot (not a sign of Приложение № 6 –
                                                    #   drawn per чл. 9, ал. 9–10 and named in the legend)

TRUCKS = {"pa": ("", False, True), "pa_lafeten": ("", True, True), "pas": ("ПАС", False, False),
          "shlangov": ("Ш", False, False), "aerodrumen": ("А", True, False), "pena_prah": ("ПП", True, False),
          "prah": ("П", True, False), "adz": ("АДЗ", False, False), "spasitelen": ("АСД", False, False),
          "avtostalba": ("", False, False), "avtopodemnik": ("", False, False), "shtaben": ("Щ", False, False),
          "vodonoska": ("", False, True)}

LADDERS = ("sglobna", "razdvizhna", "shturmova", "palka")

SPLITTERS = {2: "dvupaten", 3: "tripaten", 4: "chetiripaten"}

FENCES = ("zhelezobetonna", "kamenna", "metalna", "darvena", "bodliva")

LEGEND_TEXT = {
    "sgrada": "Сграда (размерите – в m)",
    "ograda": "Ограда",
    "zhelezobetonna": "Железобетонна ограда",
    "kamenna": "Каменна ограда",
    "metalna": "Метална ограда",
    "darvena": "Дървена ограда",
    "bodliva": "Ограда от бодлива тел",
    "pozhar": "Пожар в сграда",
    "pozhar_otkrito": "Пожар на открита площадка",
    "zadimyavane": "Зона на задимяване",
    "ognishte": "Огнище на пожара",
    "posoka": "Посока на разпространение на пожара",
    "napravlenie": "Главно направление за действие на силите и средствата",
    "vyatar": "Посока и сила на вятъра",
    "pa": "Пожарен автомобил",
    "pa_lafeten": "Пожарен автомобил с лафетен струйник",
    "pas": "Пожарна автопомпена станция",
    "shlangov": "Шлангов автомобил",
    "aerodrumen": "Пожарен аеродрумен автомобил",
    "pena_prah": "Пожарен автомобил за гасене с пяна и прах",
    "prah": "Пожарен автомобил за гасене с прах",
    "adz": "Автомобил за дихателна защита",
    "spasitelen": "Автомобил за спасителна дейност",
    "avtostalba": "Пожарна автомеханична стълба",
    "avtopodemnik": "Пожарен автоподемник",
    "shtaben": "Щабен автомобил",
    "vodonoska": "Водоноска, бензиновоз",
    "vodoem": "Пожарен водоем (обемът – в m³)",
    "hidrant": "Подземен хидрант",
    "nadzemen_hidrant": "Надземен хидрант",
    "kran": "Пожарен кран (№)",
    "kula": "Водонапорна кула",
    "imot": "Граница на поземлен имот (кадастрална карта)",
    "ulitsa": "Улица, път",
    "bez_parkirane": "Площ, неразрешена за паркиране на автомобили",
    "skluchena": "Сключена водопроводна мрежа (С – диаметър, mm / налягане, bar)",
    "tupikova": "Тупикова водопроводна мрежа (Т – диаметър, mm / налягане, bar)",
    "gazoprovod": "Газопровод",
    "gaz_armatura": "Спирателна арматура на газопровода",
    "glavna": "Главна шлангова линия (Ø 75 mm)",
    "malka": "Работна шлангова линия (Ø 52 mm)",
    "smukatelna": "Смукателна линия",
    "shlang": "Чертичка по линията – един шланг ({m:g} m)",
    "dvupaten": "Двупътен разклонител",
    "tripaten": "Трипътен разклонител",
    "chetiripaten": "Четирипътен разклонител",
    "malak": "Малък струйник с използване на вода",
    "glaven": "Главен струйник с използване на вода",
    "lafeten": "Лафетен струйник с използване на вода",
    "penostruinik": "Пеноструйник",
    "prahov": "Прахов струйник",
    "pokriv": "Струйник на покрив",
    "etazh": "Струйник в етаж",
    "maze": "Струйник в мазе",
    "sglobna": "Стълба сглобна",
    "razdvizhna": "Стълба разтегателна",
    "shturmova": "Стълба щурмова",
    "palka": "Стълба палка",
    "shtab": "Място за разположение на щаба",
    "pbt": "Пост по безопасност на труда",
    "kpp": "Контролнопропусквателен пункт",
    "el": "Електрическо табло",
}

LEGEND_ORDER = ["sgrada", "ograda", *FENCES, *SITUATION, "pozhar", "pozhar_otkrito", "zadimyavane", "ognishte", "posoka",
                "napravlenie", "vyatar", *TRUCKS, *WATER, "glavna", "malka", "smukatelna", "shlang", "dvupaten",
                "tripaten", "chetiripaten", *NOZZLES, *PLACES, *LADDERS, "shtab", "pbt", "kpp", "el"]


class Pal:
    """The colours: black and white for printing, or the colours of Приложение № 6."""

    def __init__(self, colour):
        red, blue = "#d0021b", "#1f4fd8"
        self.fire = red if colour else INK
        self.truck = red if colour else INK
        self.hose = blue if colour else INK
        self.water = blue if colour else INK
        self.smoke = blue if colour else "#555555"
        self.road = "#8b5a2b" if colour else INK        # чл. 9, ал. 9: кафяв – улици и пътища
        self.gas = "#d9a400" if colour else INK         # жълт – инсталации и арматура за горими газове
        self.parking = "#f28c00" if colour else "#555555"   # оранжев – площи, неразрешени за паркиране

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

def rotate(x, y, angle, pts):
    a = math.radians(angle)
    return [(x + px * math.cos(a) - py * math.sin(a), y + px * math.sin(a) + py * math.cos(a)) for px, py in pts]

def readable(angle):
    """A text angle that is never upside down."""
    a = angle % 360
    return a - 180 if 90 < a <= 270 else a

def seg(ax, a, b, color, lw, z=6, **kw):
    ax.plot([a[0], b[0]], [a[1], b[1]], color=color, lw=lw, zorder=z, solid_capstyle="butt", **kw)

def stadium(cx, cy, length_, height):
    """A rounded box (the tank inside a fire engine) as a polygon, centred on (cx, cy), along x."""
    r = height / 2
    pts = []
    for i in range(13):
        a = math.pi / 2 + math.pi * i / 12
        pts.append((cx - length_ / 2 + r + r * math.cos(a), cy + r * math.sin(a)))
    for i in range(13):
        a = -math.pi / 2 + math.pi * i / 12
        pts.append((cx + length_ / 2 - r + r * math.cos(a), cy + r * math.sin(a)))
    return pts

def chevron(ax, tip, d, size, color, lw, z=6):
    """An open arrowhead „>“ with its tip at tip, pointing along d."""
    (tx, ty), (dx, dy) = tip, d
    nx, ny = -dy, dx
    for sgn in (-1, 1):
        seg(ax, tip, (tx - dx * size + nx * size * 0.38 * sgn, ty - dy * size + ny * size * 0.38 * sgn), color, lw, z)

def solid_head(ax, tip, d, size, color, z=6):
    (tx, ty), (dx, dy) = tip, d
    nx, ny = -dy, dx
    bx, by = tx - dx * size, ty - dy * size
    ax.add_patch(Polygon([(tx, ty), (bx + nx * size * 0.4, by + ny * size * 0.4), (bx - nx * size * 0.4, by - ny * size * 0.4)],
                         closed=True, fc=color, ec=color, lw=0.5, zorder=z))

def caret(ax, at, d, size, color, z=6):
    """The small „Λ“ under a monitor (lafeten)."""
    (x, y), (dx, dy) = at, d
    nx, ny = -dy, dx
    for sgn in (-1, 1):
        seg(ax, (x, y), (x - nx * size + dx * size * 0.35 * sgn, y - ny * size + dy * size * 0.35 * sgn), color, 0.8, z)

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

def draw_fire(ax, f, pal):
    """Fire in a building – crossed hatching; on an open area – a denser hatching in a frame."""
    if f["na_otkrito"]:
        ax.add_patch(Rectangle((f["x"], f["y"]), f["w"], f["h"], fill=False, hatch="xxxxxx", ec=pal.fire, lw=0, zorder=3))
        ax.add_patch(Rectangle((f["x"], f["y"]), f["w"], f["h"], fill=False, ec=INK, lw=0.9, zorder=3.1))
    else:
        ax.add_patch(Rectangle((f["x"], f["y"]), f["w"], f["h"], fill=False, hatch="xxxx", ec=pal.fire, lw=0.6, zorder=3))

def draw_seat(ax, x, y, s, pal):
    """The seat of the fire: a filled flag on a pole (red in colour)."""
    ax.plot([x, x], [y, y + 1.1 * s], color=pal.fire, lw=1.0, zorder=7)
    ax.add_patch(Circle((x, y), 0.05 * s, fc=pal.fire, ec=pal.fire, zorder=7))
    ax.add_patch(Rectangle((x, y + 0.6 * s), 0.8 * s, 0.5 * s, fc=pal.fire, ec=pal.fire, lw=0.6, zorder=7))

def draw_smoke(ax, z, s, pal):
    """A zone of smoke: a thin frame with small upright „S“ waves."""
    x, y, w, h = z["x"], z["y"], z["w"], z["h"]
    frame = Rectangle((x, y), w, h, fill=False, ec=INK, lw=0.5, zorder=2.6)
    ax.add_patch(frame)
    dx, dy, hh, amp = 0.55 * s, 1.0 * s, 0.32 * s, 0.09 * s
    row = y + dy / 2
    while row < y + h - hh / 2:
        col = x + dx / 2
        while col < x + w:
            ys = [row - hh + 2 * hh * i / 16 for i in range(17)]
            xs = [col + amp * math.sin(math.pi * 2 * i / 16) for i in range(17)]
            line, = ax.plot(xs, ys, color=pal.smoke, lw=0.6, zorder=2.5)
            line.set_clip_path(frame)
            col += dx
        row += dy

def big_arrow(ax, a, b, pal, hatched, scale):
    """The spread of the fire (an outlined arrow) and the main direction (the same, hatched)."""
    p = FancyArrowPatch(a, b, arrowstyle="fancy,head_length=0.9,head_width=0.9,tail_width=0.45",
                        mutation_scale=scale, fc="white", ec=pal.fire, lw=1.0, zorder=7,
                        hatch="xxxx" if hatched else None)
    ax.add_patch(p)

def draw_truck(ax, t, s, fs, pal):
    """A fire engine as in Приложение № 6: the body, the cab in front (a trapezium), and inside – the tank
    (a rounded box) or the letters of the special vehicle; a monitor on the roof for the „lafeten“ kinds."""
    x, y, angle, kind = t["x"], t["y"], t["ugal"], t["vid"]
    letters, monitor, tank = TRUCKS[kind]
    c = pal.truck
    L, W = 1.35 * s, 0.6 * s
    R = lambda pts: rotate(x, y, angle, pts)  # noqa: E731
    body = [(-L / 2, -W / 2), (L / 2, -W / 2), (L / 2, W / 2), (-L / 2, W / 2)]
    ax.add_patch(Polygon(R(body), closed=True, fc="white", ec=c, lw=1.0, zorder=8))
    if kind != "avtostalba":
        cab = [(L / 2, -0.32 * W), (L / 2 + 0.38 * s, -0.24 * W), (L / 2 + 0.38 * s, 0.24 * W), (L / 2, 0.32 * W)]
        ax.add_patch(Polygon(R(cab), closed=True, fc="white", ec=c, lw=0.9, zorder=8))
    if tank:
        ax.add_patch(Polygon(R(stadium(0, 0, L - 0.16 * s, W - 0.16 * s)), closed=True, fill=False, ec=c, lw=0.8, zorder=9))
    if kind == "vodonoska":
        a, b = R([(-0.12 * L, -W / 2), (0.22 * L, W / 2)])
        seg(ax, a, b, c, 0.8, 9)
    if kind == "avtostalba":                           # the ladder over the body, reaching past the front
        for yy in (-0.22 * W, 0.22 * W):
            a, b = R([(-L / 2, yy), (L / 2 + 0.55 * s, yy)])
            seg(ax, a, b, c, 0.8, 9)
        steps = 7
        for i in range(steps + 1):
            xx = -L / 2 + (L + 0.55 * s) * i / steps
            a, b = R([(xx, -0.22 * W), (xx, 0.22 * W)])
            seg(ax, a, b, c, 0.7, 9)
    if kind == "avtopodemnik":                         # the boom: two lines fanning out past the front
        for sgn in (-1, 1):
            a, b = R([(-L / 2, 0.05 * W * sgn), (L / 2 + 0.5 * s, 0.75 * W * sgn)])
            seg(ax, a, b, c, 0.7, 9)
    if letters:
        cx, cy = R([(0, 0)])[0]
        ax.text(cx, cy, letters, ha="center", va="center", fontsize=fs - (2 if len(letters) > 2 else 1),
                rotation=readable(angle), color=c, zorder=10)
    if monitor:                                        # the line over the roof with an arrow forward
        a, b = R([(-L / 2, W / 2 + 0.12 * s), (L / 2 + 0.45 * s, W / 2 + 0.24 * s)])
        seg(ax, a, b, c, 0.8, 10)
        d = ((b[0] - a[0]) / math.dist(a, b), (b[1] - a[1]) / math.dist(a, b))
        solid_head(ax, b, d, 0.16 * s, c, 10)
        m = R([(0, W / 2 + 0.18 * s)])[0]
        caret(ax, m, d, 0.12 * s, c, 10)

def draw_reservoir(ax, x, y, s, label, fs, pal):
    w, h = 2.2 * s, 0.9 * s
    ax.add_patch(Rectangle((x - w / 2, y - h / 2), w, h, fc="white", ec=pal.water, lw=1.0, zorder=8))
    if label:
        ax.text(x, y, label, ha="center", va="center", fontsize=fs, color=pal.water, zorder=9)

def draw_hydrant(ax, x, y, s, label, fs, pal, above=False):
    """A hydrant on the water main (dash-dot): underground – an arrow from below up to the main;
    above ground – a thick upright with an arrow up and a crossbar with arrows to both sides."""
    c = pal.water
    ax.plot([x - 0.9 * s, x + 0.9 * s], [y, y], color=c, lw=1.0, ls=(0, (6, 2, 1, 2)), zorder=8)
    if above:
        ax.plot([x, x], [y - 0.35 * s, y + 0.75 * s], color=c, lw=1.6, zorder=9)
        solid_head(ax, (x, y + 0.95 * s), (0, 1), 0.22 * s, c, 9)
        ax.plot([x - 0.3 * s, x + 0.3 * s], [y + 0.45 * s, y + 0.45 * s], color=c, lw=1.6, zorder=9)
        solid_head(ax, (x - 0.45 * s, y + 0.45 * s), (-1, 0), 0.16 * s, c, 9)
        solid_head(ax, (x + 0.45 * s, y + 0.45 * s), (1, 0), 0.16 * s, c, 9)
    else:
        ax.plot([x, x], [y - 1.0 * s, y - 0.15 * s], color=c, lw=0.9, zorder=9)
        solid_head(ax, (x, y), (0, 1), 0.16 * s, c, 9)
    if label:                                          # текстът към хидрантите – син (чл. 9, ал. 9, т. 2)
        ax.text(x + 1.0 * s, y + 0.25 * s, label, ha="left", va="center", fontsize=fs, color=c, zorder=9,
                bbox=dict(fc="white", ec="none", pad=0.4))

def offset_polyline(pts, d):
    """The polyline moved sideways by d (to the left of its direction), with mitred corners."""
    out = []
    n = len(pts)
    for i in range(n):
        dirs = []
        for a, b in ((pts[i - 1], pts[i]) if i > 0 else (None, None), (pts[i], pts[i + 1]) if i < n - 1 else (None, None)):
            if a is None:
                continue
            L = math.dist(a, b) or 1.0
            dirs.append(((b[0] - a[0]) / L, (b[1] - a[1]) / L))
        nx = sum(-dy for _, dy in dirs)
        ny = sum(dx for dx, _ in dirs)
        L = math.hypot(nx, ny) or 1.0
        nx, ny = nx / L, ny / L
        cos = max(0.3, nx * -dirs[0][1] + ny * dirs[0][0])    # the mitre grows at a sharp corner
        out.append((pts[i][0] + nx * d / cos, pts[i][1] + ny * d / cos))
    return out

def label_on_line(ax, pts, text, fs, color, z=7):
    """A label in the middle of the longest straight part of a polyline, along it, never upside down."""
    a, b = max(zip(pts, pts[1:]), key=lambda ab: math.dist(*ab))
    ang = math.degrees(math.atan2(b[1] - a[1], b[0] - a[0]))
    ax.text((a[0] + b[0]) / 2, (a[1] + b[1]) / 2, text, ha="center", va="center", fontsize=fs, color=color,
            rotation=readable(ang), rotation_mode="anchor", zorder=z, bbox=dict(fc="white", ec="none", pad=0.4))

def draw_street(ax, pts, width, name, fs, pal):
    """A street or road – the sign „Шосе“: two parallel lines (brown), the name between them."""
    for sgn in (-1, 1):
        xs, ys = zip(*offset_polyline(pts, sgn * width / 2))
        ax.plot(xs, ys, color=pal.road, lw=0.9, zorder=1.2, solid_joinstyle="miter")
    if name:
        a, b = max(zip(pts, pts[1:]), key=lambda ab: math.dist(*ab))
        ang = math.degrees(math.atan2(b[1] - a[1], b[0] - a[0]))
        ax.text((a[0] + b[0]) / 2, (a[1] + b[1]) / 2, name, ha="center", va="center", fontsize=fs, color=INK,
                rotation=readable(ang), rotation_mode="anchor", zorder=1.3)

def draw_streets(ax, streets, fs, pal):
    """All streets at once, so that the junctions merge: a street along a line is a brown band with a white core
    of its width (the edges are the two lines of the sign „Шосе“); a street as an area (its cadastral parcel,
    "kontur") is its outline in brown – drawn twice, wide brown then white over it, so that where two street
    parcels touch, the line between them disappears and only the outer edge stays. The names last.
    streets – [{"tochki", "shirina", "ime"} | {"kontur", "otvori", "ime", "ime_pos", "ime_ugal"}]."""
    if not streets:
        return
    t = ax.transData
    pt_per_m = (t.transform((1, 0))[0] - t.transform((0, 0))[0]) * 72 / ax.figure.dpi
    edge = 0.9                                         # the line of the sign, pt
    for z, extra, colour in ((1.2, edge * 2, pal.road), (1.25, 0, "white")):
        for u in streets:
            if "kontur" in u:
                rings = [u["kontur"]] + list(u.get("otvori") or [])
                if extra:
                    for r in rings:
                        ax.add_patch(Polygon(r, closed=True, fill=False, ec=colour, lw=extra, zorder=z, joinstyle="round"))
                else:
                    path = MPath.make_compound_path(*[MPath(list(r) + [r[0]], closed=True) for r in rings])
                    ax.add_patch(PathPatch(path, fc="white", ec="none", lw=0, zorder=z))
                continue
            xs, ys = zip(*u["tochki"])
            ax.plot(xs, ys, color=colour, lw=max(u["shirina"] * pt_per_m + extra, 0.5), zorder=z,
                    solid_capstyle="butt", solid_joinstyle="round")
    for u in streets:
        if not u["ime"]:
            continue
        if "kontur" in u:
            if u.get("ime_pos"):
                ax.text(u["ime_pos"][0], u["ime_pos"][1], u["ime"], ha="center", va="center", fontsize=fs, color=INK,
                        rotation=readable(u.get("ime_ugal") or 0), rotation_mode="anchor", zorder=1.3)
            continue
        a, b = max(zip(u["tochki"], u["tochki"][1:]), key=lambda ab: math.dist(*ab))
        ang = math.degrees(math.atan2(b[1] - a[1], b[0] - a[0]))
        ax.text((a[0] + b[0]) / 2, (a[1] + b[1]) / 2, u["ime"], ha="center", va="center", fontsize=fs, color=INK,
                rotation=readable(ang), rotation_mode="anchor", zorder=1.3)

def draw_parcel(ax, kontur, label, s, fs):
    """The boundary of the cadastral parcel – thin dash-dot black, its identifier at the top point."""
    ax.add_patch(Polygon(kontur, closed=True, fill=False, ec=INK, lw=0.7, ls=PARCEL_LS, zorder=1.35))
    if label:
        tx, ty = max(kontur, key=lambda p: (p[1], -p[0]))
        ax.text(tx, ty + 0.4 * s, label, ha="center", va="bottom", fontsize=fs - 0.5, zorder=4,
                bbox=dict(fc="white", ec="none", pad=0.6, alpha=0.85))

def draw_no_parking(ax, r, pal):
    """An area where parking is not allowed – orange frame and hatching (чл. 9, ал. 9, т. 7)."""
    ax.add_patch(Rectangle((r["x"], r["y"]), r["w"], r["h"], fill=False, hatch="////", ec=pal.parking, lw=0.8,
                           zorder=1.5))

def draw_main(ax, pts, kind, label, s, fs, pal):
    """A water main as in Приложение № 6: a blue dash-dot line, the label „С-150/5“ (сключена) or
    „Т-100/4“ (тупикова) – the letter, the diameter in mm and the pressure in bar – along it."""
    xs, ys = zip(*pts)
    ax.plot(xs, ys, color=pal.water, lw=1.1, ls=(0, (8, 2, 1, 2)), zorder=4.5)
    if label:
        label_on_line(ax, pts, label, fs - 0.5, pal.water, 4.6)

def draw_valve_kran(ax, x, y, s, label, fs, pal):
    """A fire cock (пожарен кран) as in Приложение № 6: a stem with a short bar on top and a circle,
    its lower half filled; the number beside it („ПК-4“)."""
    c, r = pal.water, 0.32 * s
    ax.plot([x, x], [y + r, y + 1.1 * s], color=c, lw=0.9, zorder=9)
    ax.plot([x - 0.3 * s, x + 0.3 * s], [y + 1.1 * s, y + 1.1 * s], color=c, lw=0.9, zorder=9)
    ax.add_patch(Circle((x, y), r, fc="white", ec=c, lw=0.9, zorder=9))
    ax.add_patch(Wedge((x, y), r, 180, 360, fc=c, ec=c, lw=0.9, zorder=9.1))
    if label:
        ax.text(x + 0.55 * s, y + 0.5 * s, label, ha="left", va="center", fontsize=fs, color=c, zorder=9,
                bbox=dict(fc="white", ec="none", pad=0.4))

def draw_tower(ax, x, y, s, label, fs, pal):
    """A water tower (водонапорна кула): two circles, blue."""
    c = pal.water
    ax.add_patch(Circle((x, y), 0.55 * s, fc="white", ec=c, lw=0.9, zorder=8))
    ax.add_patch(Circle((x, y), 0.38 * s, fill=False, ec=c, lw=0.9, zorder=8))
    if label:
        ax.text(x + 0.75 * s, y, label, ha="left", va="center", fontsize=fs, color=c, zorder=9,
                bbox=dict(fc="white", ec="none", pad=0.4))

def draw_gas_line(ax, pts, s, fs, pal):
    """A gas pipeline as in Приложение № 6: a line broken by the letter „Г“ (yellow, чл. 9, ал. 9, т. 6) –
    one upright „Г“ in the middle of every straight part long enough for it, never on a corner."""
    xs, ys = zip(*pts)
    ax.plot(xs, ys, color=pal.gas, lw=1.2, zorder=4.4)
    for a, b in zip(pts, pts[1:]):
        L = math.dist(a, b)
        if L < 2.5 * s:
            continue
        n = max(1, int(L // (8 * s)))
        for i in range(n):
            t = (i + 0.5) / n
            ax.text(a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, "Г", ha="center", va="center",
                    fontsize=fs, color=pal.gas, zorder=4.6, bbox=dict(fc="white", ec="none", pad=0.3))

def draw_gas_valve(ax, x, y, s, label, fs, pal, angle=0):
    """A shut-off valve of the gas network: two triangles tip to tip (the usual valve sign – чл. 9, ал. 10),
    yellow; the label beside it."""
    a, h = 0.45 * s, 0.28 * s
    for sgn in (-1, 1):
        ax.add_patch(Polygon(rotate(x, y, angle, [(0, 0), (sgn * a, h), (sgn * a, -h)]), closed=True,
                             fc=pal.gas, ec=INK if pal.gas == INK else pal.gas, lw=0.7, zorder=9))
    if label:
        ax.text(x + 0.65 * s, y + 0.35 * s, label, ha="left", va="center", fontsize=fs, zorder=9,
                bbox=dict(fc="white", ec="none", pad=0.4))


def draw_line(ax, pts, kind, s, hose_m, pal):
    """A hose line with a short cross tick at every hose length; returns the number of hoses."""
    xs, ys = zip(*pts)
    ax.plot(xs, ys, color=pal.hose, lw=LINE_KINDS[kind], solid_capstyle="round", zorder=5)
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
        ax.plot([px - nx * k, px + nx * k], [py - ny * k, py + ny * k], color=pal.hose, lw=0.9, zorder=5)
    return max(1, math.ceil(total / hose_m - 0.25))

def draw_nozzle(ax, end, d, kind, s, pal, place=None):
    """A branch pipe as in Приложение № 6: the coupling (a bar across), the stem and the head –
    open „>“ (small), filled ▶ (main), ▶ with „Λ“ (monitor), „> >“ (foam), „o >“ (powder);
    „п“, „е“, „м“ on the stem for a branch on the roof, on a floor, in the basement."""
    c = pal.hose
    (x, y), (dx, dy) = end, d
    nx, ny = -dy, dx
    tip = (x + dx * 1.1 * s, y + dy * 1.1 * s)
    seg(ax, (x - nx * 0.22 * s, y - ny * 0.22 * s), (x + nx * 0.22 * s, y + ny * 0.22 * s), c, 1.0)
    seg(ax, (x, y), tip, c, 0.9)
    h = 0.38 * s
    if kind in ("malak", None):
        chevron(ax, tip, d, h, c, 0.9)
    elif kind in ("glaven", "lafeten"):
        solid_head(ax, tip, d, h, c)
        if kind == "lafeten":
            caret(ax, (x + dx * 0.3 * s, y + dy * 0.3 * s), d, 0.16 * s, c)
    elif kind == "penostruinik":
        chevron(ax, tip, d, h * 0.8, c, 0.9)
        chevron(ax, (tip[0] - dx * 0.45 * s, tip[1] - dy * 0.45 * s), d, h * 0.8, c, 0.9)
    elif kind == "prahov":
        chevron(ax, tip, d, h * 0.8, c, 0.9)
        ax.add_patch(Circle((x + dx * 0.55 * s, y + dy * 0.55 * s), 0.1 * s, fc="white", ec=c, lw=0.9, zorder=6.5))
    if place:
        lx, ly = x + dx * 0.32 * s, y + dy * 0.32 * s
        ax.text(lx, ly, PLACES[place], ha="center", va="center", fontsize=6, color=c, zorder=7,
                bbox=dict(fc="white", ec="none", pad=0.2))
        mx, my = x + dx * 0.58 * s, y + dy * 0.58 * s
        seg(ax, (mx - nx * 0.1 * s, my - ny * 0.1 * s), (mx + nx * 0.1 * s, my + ny * 0.1 * s), c, 0.8)

def draw_splitter(ax, x, y, s, ways, angle, pal):
    """A splitter as in Приложение № 6, the inlet coming along angle: two-way – a „Y“; three-way – a „Y“
    with the straight outlet; four-way – a comb of four outlets. Every end has a coupling bar."""
    c = pal.hose
    R = lambda pts: rotate(x, y, angle, pts)  # noqa: E731
    k = 0.5 * s

    def leg(a, b):
        a, b = R([a, b])
        seg(ax, a, b, c, 1.0, 7)
        dx, dy = (b[0] - a[0]) / (math.dist(a, b) or 1), (b[1] - a[1]) / (math.dist(a, b) or 1)
        seg(ax, (b[0] - dy * 0.1 * s, b[1] + dx * 0.1 * s), (b[0] + dy * 0.1 * s, b[1] - dx * 0.1 * s), c, 0.9, 7)

    a0, b0 = R([(-k, 0), (0, 0)])                      # the inlet with its coupling
    seg(ax, a0, b0, c, 1.0, 7)
    if ways == 4:
        a, b = R([(0, -0.45 * k), (0, 0.45 * k)])
        seg(ax, a, b, c, 1.0, 7)
        for yy in (-0.45, -0.15, 0.15, 0.45):
            leg((0, yy * k), (0.6 * k, yy * k))
    else:
        for sgn in (-1, 1):
            leg((0, 0), (0.6 * k, 0.6 * k * sgn))
        if ways == 3:
            leg((0, 0), (0.8 * k, 0))

def draw_ladder(ax, a, b, s, kind):
    (x0, y0), (x1, y1) = a, b
    d = math.dist(a, b) or 1.0
    ux, uy = (x1 - x0) / d, (y1 - y0) / d
    half = 0.2 * s

    def rails(p0, p1, hw, rungs=True, diag=False):
        nx, ny = -uy * hw, ux * hw
        for sgn in (-1, 1):
            seg(ax, (p0[0] + sgn * nx, p0[1] + sgn * ny), (p1[0] + sgn * nx, p1[1] + sgn * ny), INK, 0.9)
        dd = math.dist(p0, p1)
        steps = max(3, int(dd / (0.3 * s)))
        for i in range(steps + 1):
            px, py = p0[0] + (p1[0] - p0[0]) * i / steps, p0[1] + (p1[1] - p0[1]) * i / steps
            if diag:
                if i < steps:
                    seg(ax, (px - nx, py - ny), (px + ux * 0.25 * s + nx, py + uy * 0.25 * s + ny), INK, 0.7)
            elif rungs:
                seg(ax, (px - nx, py - ny), (px + nx, py + ny), INK, 0.7)

    if kind == "razdvizhna":                           # a wide part and the narrower extension
        m = (x0 + (x1 - x0) * 0.55, y0 + (y1 - y0) * 0.55)
        rails(a, m, half * 1.4)
        rails(m, b, half * 0.55)
    elif kind == "palka":
        rails(a, b, half, diag=True)
    else:
        rails(a, b, half)
        if kind == "shturmova":                        # the hook at the top
            hx, hy = x1 + ux * 0.35 * s, y1 + uy * 0.35 * s
            seg(ax, (x1, y1), (hx, hy), INK, 0.9)
            seg(ax, (hx, hy), (hx + uy * 0.25 * s, hy - ux * 0.25 * s), INK, 0.9)

def fence_marks(ax, pts, kind, s):
    """The marks along a fence of a given kind (Приложение № 6): filled squares, open squares, filled
    circles, comb teeth or crosses at every ~1.5 symbols."""
    closed = list(pts) + [pts[0]]
    step, k = 1.3 * s, 0.1 * s
    for a, b in zip(closed, closed[1:]):
        d = math.dist(a, b)
        if not d:
            continue
        ux, uy = (b[0] - a[0]) / d, (b[1] - a[1]) / d
        n = max(1, int(d // step))
        for i in range(n):
            t = (i + 0.5) * d / n
            px, py = a[0] + ux * t, a[1] + uy * t
            if kind == "zhelezobetonna":
                ax.add_patch(Rectangle((px - k, py - k), 2 * k, 2 * k, fc=INK, ec=INK, zorder=1.6))
            elif kind == "kamenna":
                ax.add_patch(Rectangle((px - k, py - k), 2 * k, 2 * k, fc="white", ec=INK, lw=0.7, zorder=1.6))
            elif kind == "metalna":
                ax.add_patch(Circle((px, py), k, fc=INK, ec=INK, zorder=1.6))
            elif kind == "darvena":
                seg(ax, (px, py), (px + uy * 2 * k, py - ux * 2 * k), INK, 0.8, 1.6)
            elif kind == "bodliva":
                for sg in (-1, 1):
                    seg(ax, (px - k * (ux + sg * uy), py - k * (uy - sg * ux)),
                        (px + k * (ux + sg * uy), py + k * (uy - sg * ux)), INK, 0.7, 1.6)

def draw_fence(ax, pts, gates, s, kind=None):
    closed = list(pts) + [pts[0]]
    xs, ys = zip(*closed)
    if kind:
        ax.plot(xs, ys, color=INK, lw=0.8, zorder=1)
        fence_marks(ax, pts, kind, s)
    else:
        ax.plot(xs, ys, color=INK, lw=1.0, ls=(0, (1.2, 1.2)), zorder=1)
    for g in gates:
        gx, gy, gw = g["x"], g["y"], g["shirina"]
        horiz = g["horiz"]
        a = (gx - gw / 2, gy) if horiz else (gx, gy - gw / 2)
        b = (gx + gw / 2, gy) if horiz else (gx, gy + gw / 2)
        ax.plot([a[0], b[0]], [a[1], b[1]], color="white", lw=6, zorder=1.8)
        for p in (a, b):                              # the gate posts
            k = 0.3 * s
            ax.plot([p[0] - (0 if horiz else k), p[0] + (0 if horiz else k)],
                    [p[1] - (k if horiz else 0), p[1] + (k if horiz else 0)], color=INK, lw=1.2, zorder=2)

def draw_label_box(ax, x, y, w, h, text, fs, color=INK):
    ax.add_patch(Rectangle((x, y), w, h, fc="white", ec=color, lw=0.9, zorder=8))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fs, color=color, zorder=9)

def draw_ring(ax, x, y, r, text, fs, color):
    """ПБТ, КПП, ГДЗЗ – the letters in a circle."""
    ax.add_patch(Circle((x, y), r, fc="white", ec=INK, lw=0.9, zorder=8))
    ax.text(x, y, text, ha="center", va="center", fontsize=fs, color=color, zorder=9)

def draw_staff(ax, x, y, s, fs, pal):
    """The place of the staff: a pole on a small triangle with a flag „Щ“ at the top."""
    c = pal.truck
    ax.add_patch(Polygon([(x - 0.14 * s, y), (x + 0.14 * s, y), (x, y + 0.25 * s)], closed=True,
                         fc="white", ec=INK, lw=0.8, zorder=8))
    ax.plot([x, x], [y + 0.25 * s, y + 1.2 * s], color=c, lw=1.0, zorder=8)
    ax.add_patch(Rectangle((x, y + 0.75 * s), 1.0 * s, 0.45 * s, fc="white", ec=c, lw=0.9, zorder=8))
    ax.text(x + 0.5 * s, y + 0.975 * s, "Щ", ha="center", va="center", fontsize=fs - 1, color=c, zorder=9)

def draw_wind(ax, x, y, angle, s):
    """The wind: an arrow along the direction it blows to, with fletching at the tail."""
    a = math.radians(angle)
    d = (math.cos(a), math.sin(a))
    tail = (x - d[0] * 0.8 * s, y - d[1] * 0.8 * s)
    head = (x + d[0] * 0.8 * s, y + d[1] * 0.8 * s)
    seg(ax, tail, head, INK, 0.9, 9)
    chevron(ax, head, d, 0.3 * s, INK, 0.9, 9)
    for k in (0.0, 0.17, 0.34):                        # the fletching – three „>“ at the tail
        chevron(ax, (tail[0] + d[0] * (k + 0.2) * s, tail[1] + d[1] * (k + 0.2) * s), d, 0.22 * s, INK, 0.8, 9)

def is_kpp(text):
    return text.strip().upper() == "КПП"

def is_el(text):
    return text.strip().lower() in ("ел", "ел.", "ел. табло")

def legend_text(key, hose_m):
    return LEGEND_TEXT[key].format(m=hose_m or 20)


def obrazets(ax, entry, x, y, pal, fs):
    """One symbol of the legend; the legend axes are in inches (equal aspect), a symbol is about 0.34 in wide."""
    key = entry[0]
    w, k, s = 0.17, 0.055, 0.2
    if key == "sgrada":
        ax.add_patch(Rectangle((x - w, y - k), 2 * w, 2 * k, fill=False, ec=INK, lw=1.5))
    elif key == "ograda":
        ax.plot([x - w, x + w], [y, y], color=INK, lw=1.0, ls=(0, (1.2, 1.2)))
    elif key in FENCES:
        ax.plot([x - w, x + w], [y, y], color=INK, lw=0.8)
        fence_marks(ax, [(x - w, y), (x + w, y)], key, 0.11)
    elif key in ("pozhar", "pozhar_otkrito"):
        draw_fire(ax, {"x": x - w, "y": y - k, "w": 2 * w, "h": 2 * k, "na_otkrito": key == "pozhar_otkrito"}, pal)
    elif key == "zadimyavane":
        draw_smoke(ax, {"x": x - w, "y": y - k, "w": 2 * w, "h": 2 * k}, 0.13, pal)
    elif key == "ognishte":
        draw_seat(ax, x - 0.04, y - 0.08, 0.15, pal)
    elif key in ("posoka", "napravlenie"):
        big_arrow(ax, (x - w, y), (x + w, y), pal, hatched=key == "napravlenie", scale=10)
    elif key == "vyatar":
        draw_wind(ax, x, y, 0, 0.17)
    elif key in TRUCKS:
        draw_truck(ax, {"x": x - 0.03, "y": y, "ugal": 0, "vid": key}, s, fs, pal)
    elif key == "vodoem":
        draw_reservoir(ax, x, y, 0.15, "", fs, pal)
    elif key == "kran":
        draw_valve_kran(ax, x, y - 0.06, 0.11, "", fs, pal)
    elif key == "kula":
        draw_tower(ax, x, y, 0.14, "", fs, pal)
    elif key == "imot":
        ax.plot([x - w, x + w], [y, y], color=INK, lw=0.7, ls=PARCEL_LS)
    elif key == "ulitsa":
        draw_street(ax, [(x - w, y), (x + w, y)], 0.1, "", fs, pal)
    elif key == "bez_parkirane":
        draw_no_parking(ax, {"x": x - w, "y": y - k, "w": 2 * w, "h": 2 * k}, pal)
    elif key in NETWORKS:
        draw_main(ax, [(x - w, y), (x + w, y)], key, "", 0.2, fs, pal)
        ax.text(x, y + 0.06, NETWORKS[key] + "-150/5" if key == "skluchena" else NETWORKS[key] + "-100/4",
                ha="center", va="bottom", fontsize=fs - 2, color=pal.water)
    elif key == "gazoprovod":
        ax.plot([x - w, x + w], [y, y], color=pal.gas, lw=1.2)
        ax.text(x, y, "Г", ha="center", va="center", fontsize=fs - 1, color=pal.gas, bbox=dict(fc="white", ec="none", pad=0.1))
    elif key == "gaz_armatura":
        draw_gas_valve(ax, x, y, 0.14, "", fs, pal)
    elif key in ("hidrant", "nadzemen_hidrant"):
        draw_hydrant(ax, x, y - (0.03 if key == "nadzemen_hidrant" else -0.05), 0.12, "", fs, pal,
                     above=key == "nadzemen_hidrant")
    elif key in LINE_KINDS:
        ax.plot([x - w, x + w], [y, y], color=pal.hose, lw=LINE_KINDS[key])
    elif key == "shlang":
        ax.plot([x - w, x + w], [y, y], color=pal.hose, lw=1.1)
        ax.plot([x, x], [y - 0.045, y + 0.045], color=pal.hose, lw=0.9)
    elif key in ("dvupaten", "tripaten", "chetiripaten"):
        draw_splitter(ax, x - 0.02, y, 0.26, {"dvupaten": 2, "tripaten": 3, "chetiripaten": 4}[key], 0, pal)
    elif key in NOZZLES:
        draw_nozzle(ax, (x - w, y), (1, 0), key, 0.3, pal)
    elif key in PLACES:
        draw_nozzle(ax, (x - w, y), (1, 0), "malak", 0.3, pal, key)
    elif key in LADDERS:
        draw_ladder(ax, (x - w, y), (x + w, y), 0.22, key)
    elif key == "shtab":
        draw_staff(ax, x - 0.07, y - 0.11, 0.18, fs, pal)
    elif key == "pbt":
        draw_ring(ax, x, y, 0.08, "ПБТ", fs - 2.5, pal.truck)
    elif key == "kpp":
        draw_ring(ax, x, y, 0.08, "КПП", fs - 2.5, pal.truck)
    elif key == "el":
        draw_label_box(ax, x - 0.1, y - 0.06, 0.2, 0.12, "Ел.", fs - 1, pal.truck)
    elif key == "obekt":
        draw_label_box(ax, x - w, y - 0.06, 2 * w, 0.12, entry[2], fs - 1)


def draw_kompas(ax, x, y, s, fs, ugal=90):
    """The cardinal directions – a compass needle along north–south: the northern half filled, the
    southern half open, „С“ beyond the north tip and „Ю“ beyond the south tip. (x, y) is the centre;
    ugal is where north points on the drawing (90 – up, as on every scheme of the plugin)."""
    L, W = 1.0 * s, 0.22 * s
    R = lambda pts: rotate(x, y, ugal - 90, pts)  # noqa: E731
    ax.add_patch(Polygon(R([(0, L), (-W, 0), (W, 0)]), closed=True, fc=INK, ec=INK, lw=0.8, zorder=9))
    ax.add_patch(Polygon(R([(0, -L), (-W, 0), (W, 0)]), closed=True, fc="white", ec=INK, lw=0.8, zorder=9))
    ax.add_patch(Circle((x, y), 0.07 * s, fc="white", ec=INK, lw=0.8, zorder=10))
    (nx, ny), (sx, sy) = R([(0, L + 0.35 * s), (0, -L - 0.35 * s)])
    ax.text(nx, ny, "С", ha="center", va="center", fontsize=fs, zorder=10)
    ax.text(sx, sy, "Ю", ha="center", va="center", fontsize=fs, zorder=10)


# ---------------------------------------------------------------- the catalogue

KATALOG_EXTRA = [("kompas", "Посоките – север (С) и юг (Ю)")]


def katalog(out, colour=False, fs=7.0):
    """A sheet with every symbol of the library and its name – two columns, A4 text width."""
    pal = Pal(colour)
    keys = [k for k in LEGEND_ORDER] + [k for k, _ in KATALOG_EXTRA]
    names = dict(LEGEND_TEXT, **dict(KATALOG_EXTRA))
    entries = [(k, textwrap.wrap(names[k].format(m=20), 40)) for k in keys]
    cols = [entries[0::2], entries[1::2]]
    width_in, line_in = 16.5 / 2.54, 0.13
    rows = [max(len(e[1]) for e in pair if e) for pair in zip(cols[0], cols[1] + [None] * len(cols[0]))
            if pair[0] is not None]
    h = sum(0.2 + line_in * n for n in rows) + 0.5
    fig = plt.figure(figsize=(width_in, h), dpi=200)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, width_in)
    ax.set_ylim(0, h)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.text(0.15, h - 0.22, "Условни знаци на схемите – Приложение № 6 към Указанията Iз-2749", fontsize=fs + 1, va="center")
    cur = h - 0.55
    for r, n in enumerate(rows):
        cy = cur - line_in * (n - 1) / 2
        for c in (0, 1):
            if r < len(cols[c]):
                e = cols[c][r]
                cx = 0.3 + c * width_in / 2
                if e[0] == "kompas":
                    draw_kompas(ax, cx, cy, 0.1, fs - 1.5)
                else:
                    obrazets(ax, e, cx, cy, pal, fs)
                ax.text(cx + 0.42, cy, "\n".join(e[1]), fontsize=fs, va="center", linespacing=1.15)
        cur -= 0.2 + line_in * n
    fig.savefig(out, dpi=200, facecolor="white")
    plt.close(fig)
    return len(keys)


def main():
    ap = argparse.ArgumentParser(description="Каталог на условните знаци")
    ap.add_argument("-o", "--out", required=True, help="изходен .png или .svg")
    ap.add_argument("--cvetna", action="store_true", help="в цветовете на Приложение № 6")
    a = ap.parse_args()
    os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
    n = katalog(a.out, a.cvetna)
    print(f'{{"output": "{a.out}", "znatsi": {n}}}')


if __name__ == "__main__":
    main()
