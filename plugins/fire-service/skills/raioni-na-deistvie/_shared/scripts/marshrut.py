#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
marshrut.py — маршрутът на пожарните автомобили от службата до обект в района на РДПБЗН – Плевен:
разстоянието по пътищата, времето за движение (tдв. от Методиката към Указанията Iз-2749, Прил. № 5).

    python3 _shared/scripts/marshrut.py --do 43.4125702,24.6504731                 # службата – по заповедта
    python3 _shared/scripts/marshrut.py --link "https://www.google.com/maps/place/…/@43.41,24.65,17z"
    python3 _shared/scripts/marshrut.py --do 43.4125702,24.6504731 --ot Сторгозия   # от друга служба
    python3 _shared/scripts/marshrut.py --masto Биволаре                           # до центъра на селото
    python3 _shared/scripts/marshrut.py --sluzhbi                                  # адресите и координатите
    python3 _shared/scripts/marshrut.py --do … --fail route.json                   # маршрутът, свален с WebFetch

Откъде тръгват автомобилите: `_shared/raioni/sluzhbi_pleven.csv` – адресът и координатите на всяка
РСПБЗН и УПБЗН. Коя служба (или участък – УПБЗН, когато мястото е в района му) – по Заповед № 8121з-208/16.02.2026 г. (koya_sluzhba.py) за населеното място,
в което е обектът (най-близкото по координати, ако е дадена само точка); без личен ключ – най-близката
служба по права линия, с бележка. `--ot` задава службата изрично.

Маршрутът е по пътищата от OpenStreetMap (OSRM – routing.openstreetmap.de, резервно router.project-osrm.org).
Времето за движение е разстоянието, разделено на средната скорост на пожарните автомобили – 1 km/min,
приета от администратора на 24.10.2026 г. (в Указанията Iз-2749 и в базата няма норматив; `--skorost`
задава друга). Времето на OSRM е за лек автомобил в нормално движение – дава се само за сравнение.
„Времето за реагиране“ по § 1, т. 4 от Указанията е от приемането на съобщението до пристигането:
скриптът го смята като 1 min от приемането на сигнала до излизането на автомобилите (сигнал в 10:00 –
излизане в 10:01; дадено от администратора на 24.10.2026 г.; `--izlizane` задава друго) плюс времето
за движение.

Отпечатва JSON: "ot" (службата, адрес, координати, как е избрана), "do", "razstoyanie_km" (по пътищата),
"prava_km", "skorost_km_min", "vreme_dvizhenie_min" (с един знак), "izlizane_min", "vreme_reagirane_min"
(излизане + движение), "vreme_min" (времето за реагиране, закръглено нагоре – за таблицата),
"osrm_min", "prez" (улиците по маршрута), "belezhki".

Грешки (на stderr, код ≠ 0): BAD_INPUT, NOT_FOUND, NO_NETWORK (адресът за WebFetch е в грешката).
"""
import argparse
import csv
import io
import json
import math
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
SHARED = os.path.dirname(HERE)
SLUZHBI = os.path.join(SHARED, "raioni", "sluzhbi_pleven.csv")
MESTA = os.path.join(SHARED, "raioni", "koordinati_pleven.csv")
SKOROST = 1.0          # km/min – приета от администратора (24.10.2026); в Iз-2749 норматив няма
IZLIZANE = 1.0         # min – от приемането на сигнала до излизането на автомобилите (администраторът, 24.10.2026)
ROUTERS = ("https://routing.openstreetmap.de/routed-car/route/v1/driving/{a};{b}?overview=false&steps=true",
           "https://router.project-osrm.org/route/v1/driving/{a};{b}?overview=false&steps=true")


def bad(msg, code="BAD_INPUT", rc=2):
    sys.stderr.write(f"{code}: {msg}\n")
    sys.exit(rc)


def read_csv(path):
    with open(path, encoding="utf-8") as f:
        lines = [ln for ln in f if not ln.startswith("#")]
    return list(csv.DictReader(io.StringIO("".join(lines))))


def norm(s):
    s = re.sub(r"^(гр|с|РСПБЗН|УПБЗН)\.?\s*[–-]?\s*", "", str(s).strip(), flags=re.I)
    return s.lower().replace("ѝ", "и").replace("й", "и").strip()


def sluzhbi():
    return read_csv(SLUZHBI)


def find_sluzhba(name):
    q = norm(name)
    rows = sluzhbi()
    hit = [r for r in rows if norm(r["sluzhba"].split("–", 1)[-1]) == q] or \
          [r for r in rows if q in norm(r["sluzhba"])]
    if len(hit) != 1:
        bad(f"няма такава служба: „{name}“ – " + ", ".join(r["sluzhba"] for r in rows), "NOT_FOUND")
    return hit[0]


def dist_km(a, b):
    """The great-circle distance, km."""
    la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 6371.0 * 2 * math.asin(math.sqrt(h))


def point(text):
    m = re.match(r"^\s*(-?\d+(?:\.\d+)?)\s*[, ]\s*(-?\d+(?:\.\d+)?)\s*$", text or "")
    if not m:
        bad(f"очаква се „ширина,дължина“, а е {text!r}")
    return float(m.group(1)), float(m.group(2))


def from_link(link):
    """The point of a Google Maps (or any) link: !3d…!4d… (the place itself), q=…, @lat,lon. A short link
    (maps.app.goo.gl) is followed once to where it leads."""
    if re.search(r"goo\.gl|g\.co/", link):
        try:
            req = urllib.request.Request(link, method="HEAD", headers={"User-Agent": "fire-service/marshrut"})
            with urllib.request.urlopen(req, timeout=20) as r:
                link = r.geturl()
        except (urllib.error.URLError, OSError):
            bad(f"не мога да отворя краткия линк – отвори го с WebFetch и подай адреса, към който води: {link}",
                "NO_NETWORK", 3)
    for pat in (r"!3d(-?\d+\.\d+)!4d(-?\d+\.\d+)", r"[?&](?:q|query|ll)=(-?\d+\.\d+),\s*(-?\d+\.\d+)",
                r"@(-?\d+\.\d+),(-?\d+\.\d+)"):
        m = re.search(pat, link)
        if m:
            return float(m.group(1)), float(m.group(2))
    bad(f"в линка няма координати: {link}")


def nearest_place(p):
    rows = read_csv(MESTA)
    best = min(rows, key=lambda r: dist_km(p, (float(r["lat"]), float(r["lng"]))))
    return best, dist_km(p, (float(best["lat"]), float(best["lng"])))


def place_by_name(name, obshtina=None):
    q = norm(name)
    rows = [r for r in read_csv(MESTA) if norm(r["naseleno_masto"]) == q]
    if obshtina:
        rows = [r for r in rows if norm(r["obshtina"]) == norm(obshtina)] or rows
    if not rows:
        bad(f"няма населено място „{name}“ в района на РДПБЗН – Плевен", "NOT_FOUND")
    if len(rows) > 1:
        bad(f"„{name}“ е в няколко общини ({', '.join(r['obshtina'] for r in rows)}) – дай --obshtina")
    return rows[0]


def by_order(masto, obshtina):
    """The service for a settlement by Заповед № 8121з-208 (koya_sluzhba.py --spravka); None without a key."""
    cmd = [sys.executable, os.path.join(HERE, "koya_sluzhba.py"), masto, "--spravka"]
    if obshtina:
        cmd += ["--obshtina", obshtina]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if r.returncode == 0:
            return json.loads(r.stdout)
    except (OSError, ValueError, subprocess.TimeoutExpired):
        pass
    return None


def by_quarter(p, note):
    """A town shared by several services (the note of Заповед № 8121з-208 names the ж.к. and streets of each):
    the service whose ж.к. or street the point lies in, by OpenStreetMap's address of the point – (service,
    "ж.к. „…“") or None (no match, or no network)."""
    try:
        url = ("https://nominatim.openstreetmap.org/reverse?format=json&zoom=17&addressdetails=1"
               f"&lat={p[0]}&lon={p[1]}&accept-language=bg")
        req = urllib.request.Request(url, headers={"User-Agent": "fire-service/marshrut"})
        with urllib.request.urlopen(req, timeout=20) as r:
            addr = json.load(r).get("address") or {}
    except (urllib.error.URLError, OSError, ValueError):
        return None
    areas = [norm(addr.get(k, "")) for k in ("suburb", "quarter", "neighbourhood", "city_district")]
    road = norm(addr.get("road", ""))
    for seg in re.split(r";", note):
        svc = re.findall(r"((?:РСПБЗН|УПБЗН|РС ПБЗН|У ПБЗН)\s*[–-]\s*[А-ЯA-Z][\w ]*?)(?=[,;.]|$|\s+–|\s*\()", seg)
        if not svc:
            continue
        for name in re.findall(r"ж\.к\.\s*[„\"]([^“\"]+)[“\"]", seg):
            if any(norm(name) and norm(name) in a for a in areas):
                return svc[-1].strip(), f"ж.к. „{name}“"
        for name in re.findall(r"ул\.\s*[„\"]([^“\"]+)[“\"]", seg):
            if road and norm(name).split()[-1] in road:
                return svc[-1].strip(), f"ул. „{name}“"
    return None


def route(a, b, fail=None):
    """(km, min, streets) by OSRM; a and b are (lat, lon)."""
    if fail:
        with open(fail, encoding="utf-8") as f:
            j = json.load(f)
    else:
        fmt = {"a": f"{a[1]},{a[0]}", "b": f"{b[1]},{b[0]}"}
        j, last = None, None
        for url in ROUTERS:
            try:
                req = urllib.request.Request(url.format(**fmt), headers={"User-Agent": "fire-service/marshrut"})
                with urllib.request.urlopen(req, timeout=30) as r:
                    j = json.load(r)
                break
            except (urllib.error.URLError, OSError, ValueError) as e:
                last = e
        if j is None:
            bad(f"маршрутът не се изтегли ({last}); свали с WebFetch {ROUTERS[0].format(**fmt)} и подай файла с --fail",
                "NO_NETWORK", 3)
    if j.get("code") != "Ok" or not j.get("routes"):
        bad(f"няма маршрут: {j.get('code')} {j.get('message', '')}", "NOT_FOUND")
    r = j["routes"][0]
    names = []
    for st in r["legs"][0].get("steps", []):
        n = st.get("name") or ""
        if n and n not in names:
            names.append(n)
    return r["distance"] / 1000, r["duration"] / 60, names


def main():
    ap = argparse.ArgumentParser(description="Маршрут от службата до обекта – разстояние и време за движение")
    ap.add_argument("--do", help="точката на обекта – „ширина,дължина“")
    ap.add_argument("--link", help="линк към обекта в Google Maps или друга карта")
    ap.add_argument("--masto", help="населено място (обектът или центърът му, ако няма точка)")
    ap.add_argument("--obshtina", help="общината, ако името на мястото се повтаря")
    ap.add_argument("--ot", help="службата, от която тръгват (напр. „Левски“, „УПБЗН – Сторгозия“)")
    ap.add_argument("--skorost", type=float, default=SKOROST, help=f"km/min (по подразбиране {SKOROST:g})")
    ap.add_argument("--izlizane", type=float, default=IZLIZANE, help=f"min от сигнала до излизането (по подразбиране {IZLIZANE:g})")
    ap.add_argument("--fail", help="отговорът на OSRM, свален с WebFetch (при NO_NETWORK)")
    ap.add_argument("--sluzhbi", action="store_true", help="адресите и координатите на службите")
    a = ap.parse_args()

    if a.sluzhbi:
        print(json.dumps(sluzhbi(), ensure_ascii=False, indent=1))
        return
    notes = []
    if a.do:
        dest = point(a.do)
    elif a.link:
        dest = from_link(a.link)
    elif a.masto:
        pl = place_by_name(a.masto, a.obshtina)
        dest = (float(pl["lat"]), float(pl["lng"]))
        notes.append(f"точката е центърът на {pl['vid']} {pl['naseleno_masto']} – за обект дай --do или --link")
    else:
        bad("дай --do, --link или --masto")
    if a.izlizane < 0:
        bad("--izlizane не може да е отрицателно")
    if a.skorost <= 0:
        bad("--skorost трябва да е положителна")

    if a.ot:
        st, how = find_sluzhba(a.ot), "зададена"
    else:
        if a.masto:
            pl = place_by_name(a.masto, a.obshtina)
        else:
            pl, d = nearest_place(dest)
            if d > 3:
                notes.append(f"най-близкото населено място е {pl['vid']} {pl['naseleno_masto']} на {d:.1f} km – "
                             "провери службата")
        order = by_order(pl["naseleno_masto"], pl["obshtina"])
        if order and order.get("osnova") == "по мястото":
            # a settlement of a участък (УПБЗН) is served from the участък – the engines leave from there
            st = find_sluzhba(order.get("uchastak") or order["sluzhba"])
            how = f"по Заповед № 8121з-208/16.02.2026 г. ({pl['vid']} {pl['naseleno_masto']})"
            if order.get("belezhka"):
                part = by_quarter(dest, order["belezhka"])   # a town split between services: by its ж.к./streets
                if part:
                    st = find_sluzhba(part[0])
                    how = f"по Заповед № 8121з-208/16.02.2026 г. ({pl['vid']} {pl['naseleno_masto']}, {part[1]})"
                else:
                    notes.append("заповедта: " + order["belezhka"])
        else:
            st = min(sluzhbi(), key=lambda r: dist_km(dest, (float(r["lat"]), float(r["lon"]))))
            how = "най-близката по права линия (заповедта не е прочетена – без ключ или мястото е извън района)"
            notes.append("службата не е определена по заповедта – провери я с raioni-na-deistvie")
    if st["tochnost"] == "по адреса":
        notes.append(f"точката на {st['sluzhba']} е само по адреса – маршрутът е приблизителен")

    start = (float(st["lat"]), float(st["lon"]))
    km, osrm_min, prez = route(start, dest, a.fail)
    t = km / a.skorost
    print(json.dumps({
        "ot": {"sluzhba": st["sluzhba"], "adres": st["adres"], "lat": start[0], "lon": start[1], "kak": how},
        "do": {"lat": dest[0], "lon": dest[1]},
        "razstoyanie_km": round(km, 2), "prava_km": round(dist_km(start, dest), 2),
        "skorost_km_min": a.skorost, "vreme_dvizhenie_min": round(t, 1), "izlizane_min": a.izlizane,
        "vreme_reagirane_min": round(t + a.izlizane, 1), "vreme_min": math.ceil(round(t + a.izlizane, 2)),
        "osrm_min": round(osrm_min, 1), "prez": prez, "belezhki": notes,
    }, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
