#!/usr/bin/env python3
"""
vreme.py — времето по часове за деня на пожара от официалните метеорологични съобщения:
- SYNOP на синоптичните станции на НИМХ (Плевен, Ловеч, Оряхово, Свищов, Лом, Велико Търново) – на 3 часа,
  от международния обмен на СМО, архив OGIMET;
- METAR на летищата в България (Долна Митрополия, Горна Оряховица …) – на час, архив на Iowa Environmental
  Mesonet (Iowa State University).
С --mesto/--blizo скриптът взима най-близката станция, която има съобщения в прозореца; ако няма – следващата
по разстояние (в „propusnati“ е защо е пропусната всяка по-близка). Съобщенията се разчитат на български:
температура, точка на оросяване, относителна влажност, вятър (посока, скорост и пориви в m/s), видимост,
облачност, явления (гръмотевична дейност, валежи), налягане. Часовете са местни (Europe/Sofia).

    python3 vreme.py --mesto "Долни Луковит" 2026-07-11 --ot 15:00 --do 16:00   # най-близката станция с данни
    python3 vreme.py --blizo 43.42,24.61 2026-08-04       # по координати
    python3 vreme.py LBPL 2026-08-04                      # конкретно летище (ICAO) – целият ден
    python3 vreme.py 15528 2026-10-26 --ot 16:00 --do 19:00   # конкретна синоптична станция (WMO)
    python3 vreme.py --mesto Плевен 2025-07-18 2025-07-21 # по дни: температури, вятър, валежи + бюлетина на НИМХ
    python3 vreme.py LBPL 2026-08-04 --fail metar.csv     # съобщенията, свалени другаде (WebFetch)
    python3 vreme.py --stantsii                           # станциите

Отпечатва JSON: станцията и разстоянието до мястото, съобщенията по часове (с оригиналния текст),
обобщение за прозореца и маркера за позоваване в ЕПТЗ: [[synop:15528: 26.10.2026, 16:00–19:00 ч.]]
(„(НИМХ, ст. Плевен, 26.10.2026)“) или [[metar:LBPL: 04.08.2026, 16:00–19:00 ч.]] („(METAR LBPL, 04.08.2026)“).
С две дати добавя и месечната справка от бюлетина на НИМХ (Таблица 1 – средна и максимална температура,
валеж и % от нормата, дни със силен вятър и с гръмотевици) за най-близката станция в бюлетина:
маркер [[nimh-buletin: 07.2025, Плевен]] („(Бюлетин на НИМХ, 07.2025)“).
Ако мрежата е спряна, адресът за --fail е в грешката: свали го с WebFetch и подай файла.

Грешки (на stderr, код ≠ 0): NO_NETWORK, NO_DATA, BAD_INPUT.
"""
import argparse
import csv
import datetime
import io
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Europe/Sofia")
URL = ("https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py?station={icao}&data=metar"
       "&year1={a.year}&month1={a.month}&day1={a.day}&year2={b.year}&month2={b.month}&day2={b.day}"
       "&tz=Etc/UTC&format=onlycomma")
ARHIV = "https://mesonet.agron.iastate.edu/request/download.phtml?network=BG__ASOS"
# ICAO: (летище, ширина, дължина) – летищата в архива на IEM, мрежа BG__ASOS
STANTSII = {
    "LBPL": ("Долна Митрополия", 43.4514, 24.5028),
    "LBGO": ("Горна Оряховица", 43.1514, 25.7129),
    "LBSF": ("София", 42.6955, 23.4158),
    "LBPD": ("Пловдив", 42.1333, 24.8),
    "LBPG": ("Граф Игнатиево", 42.2904, 24.714),
    "LBWN": ("Варна", 43.2, 27.9167),
    "LBBG": ("Бургас", 42.5, 27.4833),
    "LBIA": ("Ямбол", 42.455, 26.352),
    "LBWB": ("Балчик", 43.4238, 28.1813),
}
# WMO: (синоптична станция на НИМХ, ширина, дължина) – съобщенията SYNOP от международния обмен, архив OGIMET
SINOPTICHNI = {
    "15528": ("Плевен", 43.3997, 24.6000),
    "15525": ("Ловеч", 43.1497, 24.6997),
    "15514": ("Оряхово", 43.6831, 23.9667),
    "15533": ("Свищов", 43.6167, 25.3500),
    "15511": ("Лом", 43.8167, 23.2500),
    "15530": ("Велико Търново", 43.0831, 25.6497),
}
URL_SYNOP = ("https://www.ogimet.com/cgi-bin/getsynop?block={wmo}&begin={a:%Y%m%d}0000&end={b:%Y%m%d}2359")
# станциите в Таблица 1 на месечния бюлетин на НИМХ, близо до района
BULETIN_STANTSII = {"Плевен": (43.3997, 24.6000), "Враца": (43.2000, 23.5500), "В. Търново": (43.0831, 25.6497),
                    "Русе": (43.8500, 25.9500)}
URL_BULETIN = "https://bulletins.meteo.bg/bull/Buletin_NIMH_{g:04d}{m:02d}.pdf"
MAX_KM = 80  # по-далечна станция не описва времето на мястото
POSOKI = ["северен", "североизточен", "източен", "югоизточен", "южен", "югозападен", "западен", "северозападен"]
OBLATSI = {"FEW": "незначителна", "SCT": "разкъсана", "BKN": "значителна", "OVC": "плътна"}
YAVLENIYA = {"TS": "гръмотевична дейност", "RA": "дъжд", "SHRA": "превалявания от дъжд", "TSRA": "гръмотевична буря с дъжд",
             "DZ": "ръмеж", "SN": "сняг", "SHSN": "превалявания от сняг", "GR": "градушка", "GS": "суграшица",
             "BR": "мъгла (видимост над 1 km)", "FG": "мъгла", "HZ": "мараня", "FU": "дим", "DU": "прах",
             "SQ": "шквал", "VCTS": "гръмотевична дейност в околността", "VCSH": "превалявания в околността"}
KT = 0.514444


class Problem(Exception):
    pass


def km(a, b):
    la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(h))


def nay_blizka(lat, lon):
    icao = min(STANTSII, key=lambda k: km((lat, lon), STANTSII[k][1:]))
    return icao, round(km((lat, lon), STANTSII[icao][1:]))


def vid(st):
    """„SYNOP“ for a WMO index (5 digits), „METAR“ for an ICAO code."""
    return "SYNOP" if str(st).isdigit() else "METAR"


def ime(st):
    return (SINOPTICHNI if vid(st) == "SYNOP" else STANTSII)[st][0]


def opisanie(st):
    if vid(st) == "SYNOP":
        return f"синоптична станция {ime(st)} на НИМХ (WMO {st})"
    return f"летище {ime(st)} ({st})"


def kandidati(lat, lon, max_km=MAX_KM):
    """All stations (SYNOP and METAR) within max_km, nearest first: [(code, km), …]."""
    vse = [(k, v[1], v[2]) for k, v in SINOPTICHNI.items()] + [(k, v[1], v[2]) for k, v in STANTSII.items()]
    out = sorted(((k, round(km((lat, lon), (la, lo)))) for k, la, lo in vse), key=lambda x: x[1])
    blizki = [x for x in out if x[1] <= max_km]
    return blizki or out[:1]


def koordinati(ime):
    """„ШИРИНА,ДЪЛЖИНА“ of a settlement in the РДПБЗН – Плевен area (raioni/koordinati_pleven.csv)."""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "raioni", "koordinati_pleven.csv")
    ime_n = re.sub(r"^(с|гр)\.\s*", "", ime.strip(), flags=re.I).lower()
    with open(path, encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(l for l in f if not l.startswith("#")) if r["naseleno_masto"].lower() == ime_n]
    if not rows:
        raise Problem(f"BAD_INPUT: „{ime}“ не е в района на РДПБЗН – Плевен – дай --blizo ШИРИНА,ДЪЛЖИНА")
    if len({r["obshtina"] for r in rows}) > 1:
        raise Problem(f"BAD_INPUT: „{ime}“ има в няколко общини ({', '.join(sorted({r['obshtina'] for r in rows}))}) – дай --blizo")
    return f"{rows[0]['lat']},{rows[0]['lng']}"


def ms(kt):
    """kt → m/s, to one decimal."""
    return round(int(kt) * KT, 1)


def _t(x):
    return -int(x[1:]) if x.startswith("M") else int(x)


def razchiti(metar):
    """One METAR → dict with the decoded values (Bulgarian)."""
    body = metar.split(" RMK ")[0]
    d = {"vyatar_posoka": "", "vyatar_ms": None, "porivi_ms": None, "vidimost": "", "oblachnost": [],
         "yavleniya": [], "temp": None, "orosyavane": None, "vlazhnost": None, "nalyagane": None}
    for tok in body.split()[2:]:
        if m := re.fullmatch(r"(\d{3}|VRB)(\d{2,3})(?:G(\d{2,3}))?KT", tok):
            d["vyatar_ms"] = ms(m.group(2))
            d["porivi_ms"] = ms(m.group(3)) if m.group(3) else None
            d["vyatar_posoka"] = ("тихо" if m.group(2) == "00" and m.group(1) == "000" else "с променлива посока"
                                  if m.group(1) == "VRB" else POSOKI[round(int(m.group(1)) / 45) % 8])
        elif tok == "CAVOK":
            d["vidimost"] = "над 10 km"
            d["oblachnost"].append("без облаци под 1500 m")
        elif re.fullmatch(r"\d{4}", tok):
            d["vidimost"] = "над 10 km" if tok == "9999" else f"{int(tok)} m"
        elif m := re.fullmatch(r"(FEW|SCT|BKN|OVC)(\d{3})(CB|TCU)?", tok):
            d["oblachnost"].append(f"{OBLATSI[m.group(1)]} на {int(m.group(2)) * 30} m"
                                   + (" (купесто-дъждовна)" if m.group(3) == "CB" else " (мощна купеста)" if m.group(3) else ""))
        elif tok in ("SKC", "NSC", "CLR", "NCD"):
            d["oblachnost"].append("без облачност" if tok in ("SKC", "CLR") else "без значима облачност")
        elif m := re.fullmatch(r"([-+]?)((?:VC)?(?:SH|TS)?(?:RA|DZ|SN|GR|GS)?|BR|FG|HZ|FU|DU|SQ|TS|VCTS|VCSH)", tok):
            if m.group(2):
                ime = YAVLENIYA.get(m.group(2), m.group(2))
                d["yavleniya"].append({"-": "слаб ", "+": "силен "}.get(m.group(1), "") + ime)
        elif m := re.fullmatch(r"(M?\d{2})/(M?\d{2})", tok):
            d["temp"], d["orosyavane"] = _t(m.group(1)), _t(m.group(2))
        elif m := re.fullmatch(r"Q(\d{4})", tok):
            d["nalyagane"] = int(m.group(1))
    if m := re.search(r"\bT([01])(\d{3})([01])(\d{3})\b", metar):  # the precise temperature in RMK
        d["temp"] = (-1 if m.group(1) == "1" else 1) * int(m.group(2)) / 10
        d["orosyavane"] = (-1 if m.group(3) == "1" else 1) * int(m.group(4)) / 10
    if d["temp"] is not None and d["orosyavane"] is not None:
        e = lambda t: math.exp(17.625 * t / (243.04 + t))  # noqa: E731 – Magnus
        d["vlazhnost"] = round(100 * e(d["orosyavane"]) / e(d["temp"]))
    return d


def svali(st, den, fail=None):
    """The decoded observations of a station (ICAO → METAR, WMO → SYNOP) for the local day."""
    return svali_synop(st, den, fail) if vid(st) == "SYNOP" else svali_metar(st, den, fail)


def svali_metar(icao, den, fail=None):
    """The METAR lines for the local day (UTC day before and after, to cover the local hours)."""
    a, b = den - datetime.timedelta(days=1), den + datetime.timedelta(days=1)
    url = URL.format(icao=icao, a=a, b=b)
    if fail:
        text = open(fail, encoding="utf-8").read()
    else:
        cache = os.path.join(tempfile.gettempdir(), f"fire-service-metar-{icao}-{den}.csv")
        if os.path.exists(cache):
            text = open(cache, encoding="utf-8").read()
        else:
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "fire-service-skills"})
                text = urllib.request.urlopen(req, timeout=60).read().decode("utf-8", "replace")
            except Exception as e:  # noqa: BLE001
                raise Problem(f"NO_NETWORK: архивът не отговаря ({e}). Свали {url} с WebFetch, запиши го във файл "
                              f"и пусни отново с --fail ФАЙЛ")
            if den < datetime.date.today() - datetime.timedelta(days=1):
                open(cache, "w", encoding="utf-8").write(text)
    out = []
    for r in csv.DictReader(io.StringIO(text)):
        if not r.get("metar") or r.get("station") != icao:
            continue
        utc = datetime.datetime.strptime(r["valid"], "%Y-%m-%d %H:%M").replace(tzinfo=datetime.timezone.utc)
        mestno = utc.astimezone(TZ)
        if mestno.date() == den:
            out.append({"chas": mestno.strftime("%H:%M"), "metar": r["metar"].strip(), **razchiti(r["metar"])})
    return out, url


WW = [((0, 3), ""), ((4, 4), "дим"), ((5, 5), "мараня"), ((6, 9), "прах във въздуха"),
      ((10, 10), "мъгла (видимост над 1 km)"), ((11, 12), "приземна мъгла"), ((13, 13), "светкавици без гръм"),
      ((14, 16), "валеж в околността"), ((17, 17), "гръмотевична дейност без валеж"), ((18, 18), "шквал"),
      ((19, 19), "смерч"), ((20, 20), "ръмеж през последния час"), ((21, 21), "дъжд през последния час"),
      ((22, 22), "сняг през последния час"), ((23, 24), "дъжд и сняг през последния час"),
      ((25, 25), "превалявания от дъжд през последния час"), ((26, 26), "превалявания от сняг през последния час"),
      ((27, 27), "градушка през последния час"), ((28, 28), "мъгла през последния час"),
      ((29, 29), "гръмотевична буря през последния час"), ((30, 39), "прашна или снежна буря"),
      ((40, 49), "мъгла"), ((50, 55), "ръмеж"), ((56, 57), "преохладен ръмеж"), ((58, 59), "ръмеж и дъжд"),
      ((60, 61), "слаб дъжд"), ((62, 63), "умерен дъжд"), ((64, 65), "силен дъжд"), ((66, 67), "преохладен дъжд"),
      ((68, 69), "дъжд и сняг"), ((70, 79), "сняг"), ((80, 80), "слаби превалявания от дъжд"),
      ((81, 82), "превалявания от дъжд"), ((83, 84), "превалявания от дъжд и сняг"), ((85, 86), "превалявания от сняг"),
      ((87, 88), "суграшица"), ((89, 90), "градушка"), ((91, 94), "гръмотевична буря през последния час, сега валеж"),
      ((95, 97), "гръмотевична буря"), ((98, 98), "гръмотевична буря с прашна буря"),
      ((99, 99), "гръмотевична буря с градушка")]
W_MINALO = {3: "прашна или снежна буря", 4: "мъгла", 5: "ръмеж", 6: "дъжд", 7: "сняг", 8: "превалявания",
            9: "гръмотевична буря"}
OKTI = {0: "ясно", 1: "незначителна", 2: "незначителна", 3: "разкъсана", 4: "разкъсана", 5: "значителна",
        6: "значителна", 7: "значителна", 8: "плътна", 9: "небето не се вижда"}


def _ww(code):
    return next((txt for (a, b), txt in WW if a <= code <= b), "")


def _sn_t(g):
    """„1snTTT“ → °C (one decimal) or None."""
    if "/" in g[2:5] or g[1] not in "01":
        return None
    return (-1 if g[1] == "1" else 1) * int(g[2:5]) / 10


def _vidimost(vv):
    if not vv.isdigit():
        return ""
    v = int(vv)
    if v <= 50:
        return "под 100 m" if v == 0 else f"{v * 100} m" if v < 10 else f"{v / 10:g} km"
    if 56 <= v <= 80:
        return f"{v - 50} km"
    if 81 <= v <= 88:
        return f"{30 + (v - 80) * 5} km"
    return "над 70 km" if v == 89 else ""


def razchiti_synop(synop):
    """One SYNOP (FM 12, „AAXX YYGGi IIiii …“) → dict with the decoded values (Bulgarian), the same keys as razchiti()."""
    d = {"vyatar_posoka": "", "vyatar_ms": None, "porivi_ms": None, "vidimost": "", "oblachnost": [],
         "yavleniya": [], "temp": None, "orosyavane": None, "vlazhnost": None, "nalyagane": None, "valezh": ""}
    tok = synop.replace("=", " ").split()
    if "AAXX" not in tok:
        return d
    i = tok.index("AAXX")
    yyggi, rest = tok[i + 1], tok[i + 3:]
    vazli = yyggi[4:5] in ("3", "4")
    sec1, sec3 = rest, []
    if "333" in rest:
        sec1, sec3 = rest[:rest.index("333")], rest[rest.index("333") + 1:]
    sec3 = sec3[:sec3.index("555")] if "555" in sec3 else sec3
    if len(sec1) < 2:
        return d
    irixhvv, nddff = sec1[0], sec1[1]
    d["vidimost"] = _vidimost(irixhvv[3:5])
    n, dd, ff = nddff[0], nddff[1:3], nddff[3:5]
    grupi = sec1[2:]
    if ff == "99" and grupi and grupi[0].startswith("00"):
        ff, grupi = grupi[0][2:5], grupi[1:]
    skorost = lambda x: round(int(x) * KT, 1) if vazli else float(int(x))  # noqa: E731
    if ff.isdigit():
        d["vyatar_ms"] = skorost(ff)
    if dd.isdigit():
        d["vyatar_posoka"] = ("тихо" if dd == "00" and (not ff.isdigit() or int(ff) == 0) else
                              "с променлива посока" if dd == "99" else POSOKI[round(int(dd) * 10 / 45) % 8])
    if n.isdigit():
        d["oblachnost"].append(f"{OKTI[int(n)]} ({n}/8)" if int(n) < 9 else OKTI[9])
    for g in grupi:
        if len(g) != 5:
            continue
        if g[0] == "1":
            d["temp"] = _sn_t(g)
        elif g[0] == "2":
            if g[1] == "9" and g[2:].isdigit():
                d["vlazhnost"] = int(g[2:])
            else:
                d["orosyavane"] = _sn_t(g)
        elif g[0] == "4" and g[1:].isdigit():
            p = int(g[1:]) / 10
            d["nalyagane"] = round(p + 1000 if p < 100 else p)
        elif g[0] == "6" and g[1:4].isdigit():
            rrr, tr = int(g[1:4]), g[4]
            mm = 0 if rrr == 0 else "следи" if rrr == 990 else (rrr - 990) / 10 if rrr > 990 else rrr
            chasa = {"1": 6, "2": 12, "3": 18, "4": 24, "5": 1, "6": 2, "7": 3, "8": 9, "9": 15}.get(tr)
            d["valezh"] = ("без валеж" if mm == 0 else f"{mm} mm" if mm != "следи" else "следи от валеж") + \
                          (f" за {chasa} ч." if chasa else "")
        elif g[0] == "7":
            if g[1:3].isdigit() and (txt := _ww(int(g[1:3]))):
                d["yavleniya"].append(txt)
            minalo = sorted({W_MINALO[int(c)] for c in g[3:5] if c.isdigit() and int(c) in W_MINALO})
            d["yavleniya"] += [f"{x} в предходните часове" for x in minalo]
        elif g[0] == "8" and g[3:4] == "9":
            d["oblachnost"].append("купесто-дъждовна (Cb)")
    for g in sec3:
        if len(g) == 5 and g[:3] in ("910", "911") and g[3:].isdigit():
            d["porivi_ms"] = max(d["porivi_ms"] or 0, skorost(g[3:]))
    if d["temp"] is not None and d["orosyavane"] is not None and d["vlazhnost"] is None:
        e = lambda t: math.exp(17.625 * t / (243.04 + t))  # noqa: E731 – Magnus
        d["vlazhnost"] = round(100 * e(d["orosyavane"]) / e(d["temp"]))
    return d


def svali_synop(wmo, den, fail=None):
    """The SYNOP of a НИМХ station for the local day, from the OGIMET archive."""
    a, b = den - datetime.timedelta(days=1), den
    url = URL_SYNOP.format(wmo=wmo, a=a, b=b)
    if fail:
        text = open(fail, encoding="utf-8").read()
    else:
        cache = os.path.join(tempfile.gettempdir(), f"fire-service-synop-{wmo}-{den}.csv")
        if os.path.exists(cache):
            text = open(cache, encoding="utf-8").read()
        else:
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "fire-service-skills"})
                text = urllib.request.urlopen(req, timeout=60).read().decode("utf-8", "replace")
            except Exception as e:  # noqa: BLE001
                raise Problem(f"NO_NETWORK: OGIMET не отговаря ({e}). Свали {url} с WebFetch, запиши го във файл "
                              f"и пусни отново с --fail ФАЙЛ")
            if re.search(r"(?i)sorry|quota|limit exceeded", text) and wmo not in text:
                raise Problem("NO_NETWORK: OGIMET отказа заявката (лимит на заявките) – опитай след минута")
            if wmo in text and den < datetime.date.today() - datetime.timedelta(days=1):
                open(cache, "w", encoding="utf-8").write(text)
    out = []
    for line in text.splitlines():
        c = line.split(",", 6)
        if len(c) < 7 or c[0] != wmo:
            continue
        utc = datetime.datetime(*map(int, c[1:6]), tzinfo=datetime.timezone.utc)
        mestno = utc.astimezone(TZ)
        if mestno.date() == den:
            out.append({"chas": mestno.strftime("%H:%M"), "synop": c[6].strip(), **razchiti_synop(c[6])})
    return out, url


def izberi(lat, lon, den, ot=None, do=None, fail=None):
    """The nearest station that has observations in the window: (code, km, obs, window, skipped).
    A nearer station without data (no report, archive gap, no network) is skipped – with the reason."""
    propusnati = []
    for st, razst in kandidati(lat, lon):
        try:
            obs, url = svali(st, den, fail if fail and vid(st) == "METAR" else None)
        except Problem as e:
            propusnati.append({"stantsiya": opisanie(st), "razstoyanie_km": razst, "prichina": str(e)[:200]})
            continue
        win = prozorets(obs, ot, do, SHIRINA[vid(st)])
        if win:
            return st, razst, obs, win, url, propusnati
        propusnati.append({"stantsiya": opisanie(st), "razstoyanie_km": razst,
                           "prichina": "няма съобщения в прозореца" if obs else "няма съобщения за деня"})
    raise Problem(f"NO_DATA: нито една станция до {MAX_KM} km няма съобщения за {den:%d.%m.%Y}: "
                  + "; ".join(f"{p['stantsiya']} – {p['prichina']}" for p in propusnati))


def _chislo(x):
    try:
        return float(x)
    except ValueError:
        return None


def buletin(st_ime, godina, mesets, papka=None):
    """Row of Таблица 1 („Метеорологична справка“) of the monthly NIMH bulletin for a station."""
    if not shutil.which("pdftotext"):
        raise Problem("NO_TOOL: няма pdftotext (poppler-utils) – бюлетинът не може да се прочете")
    url = URL_BULETIN.format(g=godina, m=mesets)
    papka = papka or tempfile.gettempdir()
    pdf = os.path.join(papka, f"fire-service-nimh-{godina:04d}{mesets:02d}.pdf")
    if not os.path.exists(pdf):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "fire-service-skills"})
            data = urllib.request.urlopen(req, timeout=90).read()
        except Exception as e:  # noqa: BLE001
            raise Problem(f"NO_NETWORK: бюлетинът {url} не се сваля ({str(e)[:80]}) – може още да не е издаден")
        if not data.startswith(b"%PDF"):
            raise Problem(f"NO_DATA: бюлетинът за {mesets:02d}.{godina} още не е издаден ({url})")
        open(pdf, "wb").write(data)
    text = subprocess.run(["pdftotext", "-layout", pdf, "-"], capture_output=True, text=True).stdout
    start = text.find("Таблица 1")
    ime_rx = re.escape(st_ime).replace(r"\ ", r"\s*").replace(r"\.", r"\.\s*")
    m = re.search(rf"(?m)^\s*{ime_rx}\s+((?:-?\d+(?:\.\d+)?\s+){{12,}}-?\d+(?:\.\d+)?)\s*$", text[max(start, 0):])
    if not m:
        raise Problem(f"NO_DATA: в бюлетина за {mesets:02d}.{godina} няма ред за {st_ime} в Таблица 1 "
                      "(таблицата може да е картинка)")
    n = m.group(1).split()
    gram = n[-1]
    return {"mesets": f"{mesets:02d}.{godina}", "stantsiya": st_ime,
            "temp_sredna_c": _chislo(n[0]), "otklonenie_ot_normata_c": _chislo(n[1]),
            "temp_maks_c": _chislo(n[2]), "temp_maks_data": int(float(n[3])),
            "temp_min_c": _chislo(n[4]), "temp_min_data": int(float(n[5])),
            "valezh_mm": _chislo(n[6]), "valezh_pct_ot_normata": _chislo(n[7]),
            "valezh_maks_mm": _chislo(n[8]), "valezh_maks_data": int(float(n[9])),
            "dni_valezh_1mm": int(float(n[10])), "dni_valezh_10mm": int(float(n[11])),
            "dni_vyatar_14ms": int(float(n[12])), "dni_gramotevitsi": int(float(gram)),
            "marker": f"[[nimh-buletin: {mesets:02d}.{godina}, {st_ime}]]", "url": url}


def buletin_stantsiya(lat, lon):
    return min(BULETIN_STANTSII, key=lambda k: km((lat, lon), BULETIN_STANTSII[k]))


def buletin_chisla(mesto):
    """Every number the bulletin row gives, for the marker place „07.2025, Плевен“ (None offline)."""
    m = re.search(r"(\d{2})\.(\d{4})\s*,\s*(.+)$", (mesto or "").strip())
    if not m:
        return None
    r = buletin(m.group(3).strip(), int(m.group(2)), int(m.group(1)))
    out = set()
    for k, v in r.items():
        if isinstance(v, (int, float)):
            out |= {str(v).rstrip("0").rstrip(".") if isinstance(v, float) else str(v), str(round(v))}
    return out


def _chas(s):
    return datetime.datetime.strptime(s, "%H:%M").time() if s else None


SHIRINA = {"METAR": 60, "SYNOP": 150}  # minutes on each side: METAR is hourly, SYNOP every 3 hours


def prozorets(obs, ot=None, do=None, shirina=60):
    """The observations in the window, widened on each side (an hour for METAR, 2½ h for SYNOP)."""
    if not (ot or do):
        return obs
    def mins(t): return t.hour * 60 + t.minute
    lo = mins(_chas(ot)) - shirina if ot else -1
    hi = mins(_chas(do)) + shirina if do else 24 * 60
    return [o for o in obs if lo <= mins(_chas(o["chas"])) <= hi]


def obobshtenie(obs):
    if not obs:
        return {}
    ts = [o["temp"] for o in obs if o["temp"] is not None]
    vs = [o["vyatar_ms"] for o in obs if o["vyatar_ms"] is not None]
    pos = [o["vyatar_posoka"] for o in obs if o["vyatar_posoka"] not in ("", "тихо")]
    yav = sorted({y for o in obs for y in o["yavleniya"]})
    ob = sorted({c for o in obs for c in o["oblachnost"]})
    return {"temp_c": [round(min(ts)), round(max(ts))] if ts else None,
            "vyatar_ms": [min(vs), max(vs)] if vs else None,
            "porivi_ms": max((o["porivi_ms"] for o in obs if o["porivi_ms"]), default=None),
            "preobladavasht_vyatar": max(set(pos), key=pos.count) if pos else "тихо",
            "vlazhnost_pct": [min(hs), max(hs)] if (hs := [o["vlazhnost"] for o in obs if o["vlazhnost"] is not None]) else None,
            "yavleniya": yav or ["без валежи и без гръмотевична дейност"],
            "oblachnost": ob,
            **({"valezh": vz} if (vz := [f"{o['chas']} ч.: {o['valezh']}" for o in obs if o.get("valezh")]) else {})}


def chisla(obs):
    """Every number a text may cite from these observations: °C rounded and to one decimal, m/s to
    one decimal, rounded and to a half, %."""
    out = set()
    for o in obs:
        for t in (o["temp"], o["orosyavane"]):
            if t is not None:
                out |= {str(round(t)), str(t).rstrip("0").rstrip(".") if isinstance(t, float) else str(t),
                        str(abs(round(t)))}
        for v in (o["vyatar_ms"], o["porivi_ms"]):
            if v is not None:
                out |= {str(round(v)), str(v).rstrip("0").rstrip("."), str(round(v * 2) / 2).rstrip("0").rstrip(".")}
        if o["vlazhnost"] is not None:
            out.add(str(o["vlazhnost"]))
    return out


def marker(st, den, ot=None, do=None, krai=None):
    pref = vid(st).lower()
    if krai and krai != den:
        return f"[[{pref}:{st}: {den:%d.%m.%Y}–{krai:%d.%m.%Y}]]"
    mesto = den.strftime("%d.%m.%Y") + (f", {ot}–{do} ч." if ot and do else f", {ot or do} ч." if ot or do else "")
    return f"[[{pref}:{st}: {mesto}]]"


def ot_mesto(mesto):
    """([days], from, to) from the marker place „04.08.2026, 16:00–19:00 ч.“ or a range of days
    „18.07.2025–21.07.2025“."""
    ds = [datetime.date(int(y), int(mo), int(d)) for d, mo, y in re.findall(r"(\d{2})\.(\d{2})\.(\d{4})", mesto or "")]
    if not ds:
        return [], None, None
    dni = [ds[0] + datetime.timedelta(days=i) for i in range((ds[-1] - ds[0]).days + 1)] if len(ds) > 1 else ds[:1]
    h = re.findall(r"\b(\d{1,2}:\d{2})\b", mesto)
    return dni, (h[0] if h else None), (h[1] if len(h) > 1 else h[0] if h else None)


def _den(s):
    return datetime.date.fromisoformat(s) if "-" in s else datetime.datetime.strptime(s, "%d.%m.%Y").date()


def _vse():
    out = {k: {"vid": "SYNOP", "ime": v[0], "lat": v[1], "lon": v[2]} for k, v in SINOPTICHNI.items()}
    out.update({k: {"vid": "METAR", "ime": v[0], "lat": v[1], "lon": v[2]} for k, v in STANTSII.items()})
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("args", nargs="*", help="[СТАНЦИЯ – ICAO или WMO] ДАТА [ДО_ДАТА] (ГГГГ-ММ-ДД или ДД.ММ.ГГГГ); "
                                            "с две дати – обобщение по дни и бюлетина на НИМХ")
    ap.add_argument("--blizo", help="ШИРИНА,ДЪЛЖИНА на мястото – взима най-близката станция с данни")
    ap.add_argument("--mesto", help="населено място от района на РДПБЗН – Плевен (по ЕКАТТЕ) – вместо --blizo")
    ap.add_argument("--ot", help="от час (ЧЧ:ММ, местно време)")
    ap.add_argument("--do", help="до час (ЧЧ:ММ, местно време)")
    ap.add_argument("--fail", help="съобщенията, свалени другаде (CSV от архива)")
    ap.add_argument("--stantsii", action="store_true", help="станциите")
    a = ap.parse_args()
    try:
        if a.stantsii:
            print(json.dumps(_vse(), ensure_ascii=False, indent=1))
            return
        args = list(a.args)
        lat = lon = st = None
        if a.mesto:
            a.blizo = koordinati(a.mesto)
        if args and (args[0].upper() in STANTSII or args[0] in SINOPTICHNI):
            st = args.pop(0).upper()
        elif a.blizo:
            lat, lon = (float(x) for x in a.blizo.split(","))
        else:
            raise Problem("BAD_INPUT: дай станция (ICAO, напр. LBPL, или WMO, напр. 15528), --mesto или --blizo ШИРИНА,ДЪЛЖИНА")
        if not args:
            raise Problem("BAD_INPUT: липсва датата")
        if st and a.blizo:
            lat, lon = (float(x) for x in a.blizo.split(","))
        den = _den(args[0])
        if len(args) > 1:
            krai = _den(args[1])
            dni, izbrani = [], set()
            for i in range((krai - den).days + 1):
                d = den + datetime.timedelta(days=i)
                if st:
                    obs, _ = svali(st, d)
                    s_den = st
                else:
                    try:
                        s_den, _, obs, _, _, _ = izberi(lat, lon, d)
                    except Problem:
                        dni.append({"data": d.strftime("%d.%m.%Y"), "nyama": "няма съобщения до " f"{MAX_KM} km"})
                        continue
                izbrani.add(s_den)
                dni.append({"data": d.strftime("%d.%m.%Y"), "stantsiya": opisanie(s_den), **obobshtenie(obs)})
            out = {"dni": dni, "markeri": [marker(s, den, krai=krai) for s in sorted(izbrani)]}
            if lat is None and st:
                lat, lon = (SINOPTICHNI if vid(st) == "SYNOP" else STANTSII)[st][1:]
            b_st = buletin_stantsiya(lat, lon)
            mesetsi, d = [], den.replace(day=1)
            while d <= krai:
                mesetsi.append((d.year, d.month))
                d = (d + datetime.timedelta(days=32)).replace(day=1)
            out["buletin_nimh"] = []
            for g, m in mesetsi:
                try:
                    out["buletin_nimh"].append(buletin(b_st, g, m))
                except Problem as e:
                    out["buletin_nimh"].append({"mesets": f"{m:02d}.{g}", "stantsiya": b_st, "nyama": str(e)[:200]})
            print(json.dumps(out, ensure_ascii=False, indent=1))
            return
        if st:
            obs, url = svali(st, den, a.fail)
            if not obs:
                raise Problem(f"NO_DATA: няма съобщения от {opisanie(st)} за {den:%d.%m.%Y} – пусни с --mesto, "
                              "за да се вземе следващата станция")
            win = prozorets(obs, a.ot, a.do, SHIRINA[vid(st)])
            razst, propusnati = (round(km((lat, lon), (SINOPTICHNI if vid(st) == "SYNOP" else STANTSII)[st][1:]))
                                 if lat is not None else None), []
        else:
            st, razst, obs, win, url, propusnati = izberi(lat, lon, den, a.ot, a.do, a.fail)
        print(json.dumps({"stantsiya": opisanie(st), "vid": vid(st), "razstoyanie_km": razst,
                          "data": den.strftime("%d.%m.%Y"), "prozorets": [a.ot, a.do] if (a.ot or a.do) else None,
                          "obobshtenie": obobshtenie(win), "marker": marker(st, den, a.ot, a.do),
                          "propusnati": propusnati or None,
                          "nablyudeniya": win if (a.ot or a.do) else obs, "url": url},
                         ensure_ascii=False, indent=1))
    except Problem as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
