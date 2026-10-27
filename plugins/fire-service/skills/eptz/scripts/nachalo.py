#!/usr/bin/env python3
"""
nachalo.py — всичко за началото на ЕПТЗ с една команда, накратко:

  - папката на скила (командите се пускат от нея);
  - профилът на потребителя (експертът) – `sluzhiteli.py --profil`;
  - произшествията на датата по мястото – само полетата, нужни за заключението, с часовете
    (пристигане, локализиране, ликвидиране) и техниката от `ops`;
  - времето около часа на всяко произшествие от най-близката станция на НИМХ с данни (летище – само ако
    няма), по GPS от адреса, иначе по населеното място;
  - одобрените експертизи – само име, обект и причина от INDEX.md;
  - еталонът Буковлък – свален, с пътя до файла.

    python3 scripts/nachalo.py --data 2026-07-11 --mesto "Луковит"
    python3 scripts/nachalo.py --data 2026-07-11            # без място – всички произшествия на датата

Част, която не може да се вземе (няма ключ, n8n не отговаря, няма мрежа), излиза с грешката си –
останалото се дава. С конектора (NO_KEY) същото се взема с инструментите му: `_shared/connector.md`.
"""
import argparse
import datetime
import json
import os
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
SH = os.path.join(SKILL, "_shared", "scripts")
sys.path.insert(0, SH)
ETALON = "Ekspertiza_Stopanski_Postroyki_Bukovlak_2025-07-22_Suha_Treva.md"
POLETA = ["num_event", "datetime", "type", "address", "object_place", "other_data", "unit", "forces", "reason_fire"]
DETAIL = ["activity_area", "destroyed", "saved", "extinguishing_agent"]
DEYNOST = ["activity", "arrival", "action_start", "localized", "extinguished", "area_found_m2", "localized_area_m2"]
TEHNIKA = ["vehicle", "departure", "personnel"]
OBR = os.path.join(tempfile.gettempdir(), "fire-service-obraztsi")  # not in the skill folder – it may be read-only


def run(*args):
    r = subprocess.run([sys.executable, *args], capture_output=True, text=True, cwd=SKILL)
    if r.returncode:
        raise RuntimeError((r.stderr or r.stdout).strip().splitlines()[-1] if (r.stderr or r.stdout).strip() else "грешка")
    return r.stdout


def profil():
    return json.loads(run(os.path.join(SH, "sluzhiteli.py"), "--profil")).get("profil")


def proizshestviya(data, mesto):
    args = [os.path.join(SH, "fetch_incidents.py"), data, "--all"] + (["--place", mesto] if mesto else [])
    out = []
    for r in json.loads(run(*args)):
        d = {k: r.get(k, "").strip() for k in POLETA if r.get(k, "").strip()}
        d.update({k: r["detail"][k] for k in DETAIL if (r.get("detail") or {}).get(k)})
        d.update(ops(r))
        d["vreme"] = vreme_za(r)
        out.append(d)
    return out


def ops(r):
    """The times and vehicles of the telephonogram (`ops`, after the nightly sync) – only what the report uses."""
    o = r.get("ops") or {}
    out = {}
    if o.get("activities"):
        out["deynosti"] = [{k: a[k] for k in DEYNOST if a.get(k) not in (None, "")} for a in o["activities"]]
    if o.get("vehicles"):
        out["tehnika"] = [{k: v[k] for k in TEHNIKA if v.get(k) not in (None, "")} for v in o["vehicles"]]
    if not out:
        out["deynosti"] = "няма в базата (още не е синхронизирано) – часовете от телефонограмата или питай"
    return out


def vreme_za(r):
    """The weather from an hour before the signal to the signal, at the nearest station with reports
    (НИМХ SYNOP or airport METAR – vreme.vzemi, on the server when the archives are out of reach)."""
    try:
        import vreme
        m = re.search(r"GPS\s*(\d{2})[,.](\d+)\s*;\s*(\d{2})[,.](\d+)", r.get("address", ""))
        if m:
            lat, lon = float(f"{m.group(1)}.{m.group(2)}"), float(f"{m.group(3)}.{m.group(4)}")
        else:
            lat, lon = map(float, vreme.koordinati(r.get("location", "")).split(","))
        t = datetime.datetime.strptime(r["dat"], "%Y-%m-%d %H:%M:%S")
        ot, do = (t - datetime.timedelta(hours=1)).strftime("%H:%M"), t.strftime("%H:%M")
        if (t - datetime.timedelta(hours=1)).date() != t.date():
            ot = "00:00"
        v = vreme.vzemi({"lat": lat, "lon": lon, "data": t.date().isoformat(), "ot": ot, "do": do})
        out = {k: v[k] for k in ("stantsiya", "razstoyanie_km", "obobshtenie", "marker") if k in v}
        if v.get("propusnati"):
            out["propusnati"] = [f"{p['stantsiya']} – {p['prichina'][:80]}" for p in v["propusnati"]]
        return out
    except Exception as e:  # noqa: BLE001 – the weather is optional here; vreme.py gives it in full
        return f"няма ({str(e)[:160]}) – пусни _shared/scripts/vreme.py"


def obraztsi():
    info = json.loads(run(os.path.join(SH, "obraztsi.py"), "index", "eptz", "-o", OBR))
    rows = []
    for line in open(info["file"], encoding="utf-8"):
        c = [x.strip() for x in line.strip().strip("|").split("|")]
        if len(c) >= 3 and c[0].startswith("`"):
            rows.append(f"{c[0].strip('`')} | {c[1]} | {c[2]}")
    return rows


def etalon():
    return json.loads(run(os.path.join(SH, "obraztsi.py"), "get", "eptz", ETALON, "-o", OBR))["file"]


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--data", required=True, help="датата на пожара ГГГГ-ММ-ДД")
    ap.add_argument("--mesto", help="населено място, местност или улица")
    a = ap.parse_args()
    out = {"papka": SKILL, "obraztsi_papka": OBR}
    for key, fn in (("profil", profil), ("proizshestviya", lambda: proizshestviya(a.data, a.mesto)),
                    ("obraztsi", obraztsi), ("etalon", etalon)):
        try:
            out[key] = fn()
        except Exception as e:  # noqa: BLE001 – one missing part never stops the rest
            out[key] = f"ГРЕШКА: {e}"
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
