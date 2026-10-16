#!/usr/bin/env python3
"""
vreme.py — времето по часове за деня на пожара от метеорологичните съобщения (METAR) на летищата
в България, от архива на Iowa Environmental Mesonet (Iowa State University). Съобщенията се
разчитат на български: температура, точка на оросяване, относителна влажност, вятър (посока,
скорост и пориви в m/s), видимост, облачност, явления (гръмотевична дейност, валежи), налягане.
Часовете са местни (Europe/Sofia).

    python3 vreme.py LBPL 2026-08-04                      # целият ден
    python3 vreme.py LBPL 2026-08-04 --ot 16:00 --do 19:00
    python3 vreme.py --blizo 43.42,24.61 2026-08-04       # най-близкото летище до мястото
    python3 vreme.py LBPL 2026-08-04 --fail metar.csv     # съобщенията, свалени другаде (WebFetch)
    python3 vreme.py LBPL 2025-07-18 2025-07-21           # по дни: температури, вятър, валежи
    python3 vreme.py --stantsii                           # летищата

Отпечатва JSON: летището и разстоянието до мястото, съобщенията по часове (с оригиналния текст),
обобщение за прозореца и маркера за позоваване в ЕПТЗ: [[metar:LBPL: 04.08.2026, 16:00–19:00 ч.]].
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


def svali(icao, den, fail=None):
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


def _chas(s):
    return datetime.datetime.strptime(s, "%H:%M").time() if s else None


def prozorets(obs, ot=None, do=None):
    """The observations in the window, widened by an hour on each side (METAR is hourly)."""
    if not (ot or do):
        return obs
    def mins(t): return t.hour * 60 + t.minute
    lo = mins(_chas(ot)) - 60 if ot else -1
    hi = mins(_chas(do)) + 60 if do else 24 * 60
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
            "vlazhnost_pct": [min(o["vlazhnost"] for o in obs if o["vlazhnost"] is not None),
                              max(o["vlazhnost"] for o in obs if o["vlazhnost"] is not None)],
            "yavleniya": yav or ["без валежи и без гръмотевична дейност"],
            "oblachnost": ob}


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


def marker(icao, den, ot=None, do=None, krai=None):
    if krai and krai != den:
        return f"[[metar:{icao}: {den:%d.%m.%Y}–{krai:%d.%m.%Y}]]"
    mesto = den.strftime("%d.%m.%Y") + (f", {ot}–{do} ч." if ot and do else f", {ot or do} ч." if ot or do else "")
    return f"[[metar:{icao}: {mesto}]]"


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


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("args", nargs="*", help="[ICAO] ДАТА [ДО_ДАТА] (ГГГГ-ММ-ДД или ДД.ММ.ГГГГ); с две дати – обобщение по дни")
    ap.add_argument("--blizo", help="ШИРИНА,ДЪЛЖИНА на мястото – взима най-близкото летище")
    ap.add_argument("--ot", help="от час (ЧЧ:ММ, местно време)")
    ap.add_argument("--do", help="до час (ЧЧ:ММ, местно време)")
    ap.add_argument("--fail", help="CSV от архива, свален другаде")
    ap.add_argument("--stantsii", action="store_true", help="летищата")
    a = ap.parse_args()
    try:
        if a.stantsii:
            print(json.dumps({k: {"ime": v[0], "lat": v[1], "lon": v[2]} for k, v in STANTSII.items()},
                             ensure_ascii=False, indent=1))
            return
        args = list(a.args)
        razst = None
        if a.blizo:
            lat, lon = (float(x) for x in a.blizo.split(","))
            icao, razst = nay_blizka(lat, lon)
        elif args and args[0].upper() in STANTSII:
            icao = args.pop(0).upper()
        else:
            raise Problem("BAD_INPUT: дай летище (ICAO, напр. LBPL) или --blizo ШИРИНА,ДЪЛЖИНА")
        if not args:
            raise Problem("BAD_INPUT: липсва датата")
        den = _den(args[0])
        if len(args) > 1:
            krai = _den(args[1])
            dni = []
            for i in range((krai - den).days + 1):
                d = den + datetime.timedelta(days=i)
                obs, _ = svali(icao, d)
                dni.append({"data": d.strftime("%d.%m.%Y"), **obobshtenie(obs)})
            print(json.dumps({"letishte": f"{STANTSII[icao][0]} ({icao})", "razstoyanie_km": razst,
                              "dni": dni, "marker": marker(icao, den, krai=krai)}, ensure_ascii=False, indent=1))
            return
        obs, url = svali(icao, den, a.fail)
        if not obs:
            raise Problem(f"NO_DATA: няма съобщения от {icao} за {den:%d.%m.%Y} – опитай съседното летище (--stantsii)")
        win = prozorets(obs, a.ot, a.do)
        print(json.dumps({"letishte": f"{STANTSII[icao][0]} ({icao})", "razstoyanie_km": razst,
                          "data": den.strftime("%d.%m.%Y"), "prozorets": [a.ot, a.do] if (a.ot or a.do) else None,
                          "obobshtenie": obobshtenie(win), "marker": marker(icao, den, a.ot, a.do),
                          "nablyudeniya": win if (a.ot or a.do) else obs, "url": url},
                         ensure_ascii=False, indent=1))
    except Problem as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
