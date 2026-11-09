#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
plan_danni.py — всички данни за плана за пожарогасене с едно извикване, успоредно (около минута, колкото КАИС):
регистърът (обектът, документите му; ситуационната схема, етажите и планът – свалени), старият план в архива и – когато
обектът още няма ситуационна схема – КАИС, допълването (dopalni.py) и работна ситуационна схема с маршрута от службата.
Така моделът не прави по едно извикване за всеки източник.

    python3 scripts/plan_danni.py --ime "Обект" --adres "ул. „Примерна“ № 1" --masto Плевен -d danni
    python3 scripts/plan_danni.py --ime "…" --id OB-0010 -d danni
    python3 scripts/plan_danni.py --ime "…" --kadastar 56722.660.887 --masto Плевен -d danni   # или --lat … --lon …

Записва <папка>/plan_danni.json и отпечатва същия JSON: "obekt", "registar", "failove", "arhiv", "kais", "marshrut",
"prieto", "ne_e_popalneno", "lipsva", "preduprezhdeniya", "vreme_s". Един неуспешен източник не спира другите – казва се
в "preduprezhdeniya". Само чете; в регистъра не записва нищо.
"""
import argparse
import concurrent.futures
import datetime
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
SHARED = os.path.join(SKILL, "_shared", "scripts")
SHEMI = os.path.join(os.path.dirname(SKILL), "shemi", "scripts")
OBEKTI = os.path.join(SHARED, "obekti.py")
KAIS = os.path.join(SHARED, "kais.py")
ARHIV = os.path.join(SHEMI, "arhiv_danni.py")
DOPALNI = os.path.join(SHEMI, "dopalni.py")
SITUACIONNA = os.path.join(SHEMI, "situacionna.py")
SVALI = ("situacionna_shema", "plan_za_pozharogasene")     # + every shema_podlozhka_*


def call(script, args, cwd=None, timeout=240):
    """One plugin script → (its JSON, None) or (None, the reason)."""
    try:
        p = subprocess.run([sys.executable, script, *args], cwd=cwd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return None, f"{os.path.basename(script)}: няма отговор за {timeout} s"
    if p.returncode != 0:
        lines = (p.stderr or p.stdout).strip().splitlines()
        return None, f"{os.path.basename(script)}: " + (" / ".join(lines[-2:])[:300] or f"код {p.returncode}")
    try:
        return json.loads(p.stdout), None
    except ValueError:
        return None, f"{os.path.basename(script)}: отговорът не е JSON"


def timed(fn, *args, **kw):
    t = time.time()
    res = fn(*args, **kw)
    return res, round(time.time() - t, 1)


def registar(a, out, warn):
    """The object in the register → (its row or None, {vid: …}, files, candidates)."""
    oid = a.id
    kandidati = []
    if not oid:
        args = ["--json", "tarsi", "--ime", a.ime, "--adres", a.adres, "--masto", a.masto, "--kadastar", a.kadastar]
        if a.lat is not None and a.lon is not None:
            args += ["--lat", str(a.lat), "--lon", str(a.lon)]
        found, err = call(OBEKTI, args, timeout=120)
        if err:
            warn.append(err)
            return None, {}, [], []
        oid = (found.get("nameren") or {}).get("id")
        kandidati = found.get("kandidati") or []
    if not oid:
        return None, {}, [], kandidati
    d, err = call(OBEKTI, ["--json", "pokazhi", oid], timeout=120)
    if err:
        warn.append(err)
        return None, {}, [], kandidati
    docs = d.get("dokumenti") or {}
    want = [v for v in docs if v in SVALI or v.startswith("shema_podlozhka_")]
    files = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
        for got, err in ex.map(lambda v: call(OBEKTI, ["--json", "pokazhi", oid, "--svali", v, "-o", out], timeout=180), want):
            if err:
                warn.append(err)
            else:
                files += got.get("svaleni") or []
    return d.get("obekt"), docs, files, kandidati


def kais(a, row, out, warn):
    """The cadastre for an object without a situational scheme; the scheme JSON is shema.json in the folder."""
    ident = a.kadastar or (row or {}).get("kadastar") or ""
    lat, lon = a.lat, a.lon
    if lat is None and row and row.get("lat") and row.get("lon"):
        lat, lon = float(row["lat"]), float(row["lon"])
    args = ["obekt", "-o", "kais.json", "--shema", "shema.json", "--voda", "--ortofoto", "--trevni-ortofoto", "--pateki"]
    if ident:
        args += ["--id", ident]
    elif lat is not None and lon is not None:
        args += ["--lat", str(lat), "--lon", str(lon)]
    else:
        warn.append("КАИС не е питан: липсва идентификатор или точка – подай --kadastar или --lat и --lon")
        return None
    res, err = call(KAIS, args, cwd=out, timeout=240)
    if err:
        warn.append(err)
    return res


def situacionna(a, out, warn):
    """dopalni.py and a working situational scheme: what it takes from the data, the distance and the time."""
    path = os.path.join(out, "shema.json")
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    data["list"] = {"nomer": "", "obekt": ", ".join(x for x in (a.ime, a.masto, a.adres) if x), "sobstvenik": "",
                    "izgotvil": a.izgotvil, "data": datetime.date.today().strftime("%d.%m.%Y"),
                    "fail": "Situacionna_shema.dxf"}
    with open(os.path.join(out, "situacionna.json"), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    dop, err = call(DOPALNI, ["situacionna.json", "--kais", "kais.json"], cwd=out, timeout=120)
    if err:
        warn.append(err)
    sit, err = call(SITUACIONNA, ["situacionna.json", "-o", "Situacionna_shema.docx", "--izgotvil", a.izgotvil or ""], cwd=out, timeout=120)
    if err:
        warn.append(err)
    return dop or {}, sit or {}


def collect(a):
    out = os.path.abspath(a.dir)
    os.makedirs(out, exist_ok=True)
    warn, times = [], {}
    (row, docs, files, kandidati), times["registar"] = timed(registar, a, out, warn)
    ima_shema = "situacionna_shema" in docs
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
        # by the name only: the fallback by address is slow and matches other objects on a street of the same name
        f_arhiv = ex.submit(timed, call, ARHIV, [a.ime], None, 200)
        f_kais = None if ima_shema or getattr(a, "bez_kais", False) else ex.submit(timed, kais, a, row, out, warn)
        (arhiv, err), times["arhiv"] = f_arhiv.result()
        if err:
            warn.append(err)
        k_res = None
        if f_kais:
            k_res, times["kais"] = f_kais.result()
    dop, sit = {}, {}
    if k_res and os.path.isfile(os.path.join(out, "shema.json")):
        (dop, sit), times["situacionna"] = timed(situacionna, a, out, warn)
    lipsva = []
    if not any(v.startswith("shema_podlozhka_") for v in docs):
        lipsva.append("етажите – няма подложки в регистъра: планът се прави с условни етажи (plan_avto.py), докато няма чертежи")
    if not (arhiv or {}).get("varianti"):
        lipsva.append("вариантите – няма стари варианти в архива")
    res = {"obekt": row or {"ime": a.ime, "adres": a.adres, "masto": a.masto, "kadastar": a.kadastar},
           "v_registara": bool(row), "kandidati": kandidati,
           "registar": sorted(docs), "failove": files, "papka": out,
           "arhiv": arhiv or {"namereno": False}, "ima_situacionna_shema": ima_shema,
           "kais": {k: (k_res or {}).get(k) for k in ("imot", "sgradi", "ulitsi", "do_vodoiztochnika_m", "vodoiztochnitsi")}
           if k_res else None,
           "situacionna_json": os.path.join(out, "situacionna.json") if sit or dop else None,
           "marshrut": sit.get("marshrut"), "izgotvil": sit.get("izgotvil") or a.izgotvil, "prieto": dop.get("prieto") or [],
           "ne_e_popalneno": dop.get("ne_e_popalneno") or [], "lipsva": lipsva, "preduprezhdeniya": warn, "vreme_s": times}
    with open(os.path.join(out, "plan_danni.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    return res


def main():
    ap = argparse.ArgumentParser(description="Данните за плана за пожарогасене с едно извикване")
    ap.add_argument("--ime", required=True, help="името на обекта")
    ap.add_argument("--id", default="", help="OB-… от регистъра")
    ap.add_argument("--adres", default="")
    ap.add_argument("--masto", default="")
    ap.add_argument("--kadastar", default="", help="кадастрален идентификатор на имота")
    ap.add_argument("--lat", type=float)
    ap.add_argument("--lon", type=float)
    ap.add_argument("--izgotvil", default="", help="иначе – потребителят по личния ключ")
    ap.add_argument("-d", "--dir", default="danni", help="папката за файловете")
    print(json.dumps(collect(ap.parse_args()), ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
