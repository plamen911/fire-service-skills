#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
plan_avto.py — целият план за пожарогасене с една команда: данните (plan_danni.py), етажите (одобрените от регистъра,
иначе условни - shemi/scripts/uslovni_etazhi.py), разчетите, конкретните схеми, plan.json и сглобяването. Около 2 минути.
С условни етажи планът е РАБОТНА ЧЕРНОВА: така пише в документа и на схемите.
Планът стъпва върху запазената ситуационна схема. Ако обектът няма такава, скриптът спира с "trebva_situacionna_shema": първо
схемата през формуляра с въпроси (скилът shemi, както и през конектора), запис в регистъра, и после пак тази команда.

    python3 scripts/plan_avto.py --ime "…" --masto Плевен --adres "ул. … № 1" --kadastar 56722.1.2 -d /mnt/user-data/outputs
    python3 scripts/plan_avto.py --ime "…" --id OB-0014 --varianti varianti.json --danni danni.json --zapishi-chernova -d …

varianti.json (по желание; без него - горният етаж в края и партерът до стълбището):
    [{"ime": "пожар в концертната зала", "fail": "Konkretna_shema_Zala_1et", "etazh": 1, "pozitsiya": "zala",
      "sgrada": "56722.1.2.3", "vl_red": "4", "i_red": "6.2", "natovarvane_vid": "седалки, завеси"},
     {"ime": "…", "etazh": 4, "pozitsiya": "kray" | "do_stalbishte", "naimenovanie": "Клас", …},
     {"ime": "…", "etazh": 2, "pomeshtenie": "Гардероб", "vhod": "Фоайе", "pat": "Стълбище,Коридор", …}]   # етажи от чертеж
danni.json (по желание): [["Заглавие на точка.", "текст"], …] - заменя точката със същото заглавие или се добавя.
--zapishi-chernova: записва всичко в регистъра като shema_chernova_* (не като одобрен план и схема).

Отпечатва JSON {"plan", "failove", "uslovni_etazhi", "varianti", "da_se_utochni", "preduprezhdeniya", "vreme_s"}.
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
SKILLS = os.path.dirname(SKILL)
SHEMI = os.path.join(SKILLS, "shemi", "scripts")
sys.path.insert(0, HERE)
sys.path.insert(0, SHEMI)
import plan_danni  # noqa: E402
import situacionna  # noqa: E402
import uslovni_etazhi as U  # noqa: E402
from shapely.geometry import Polygon  # noqa: E402

SILI = os.path.join(SKILLS, "sili-i-sredstva", "scripts", "sili.py")
KONKRETNA = os.path.join(SHEMI, "konkretna.py")
BUILD = os.path.join(HERE, "build_plan.py")
UT = "да се уточни при огледа"
LAT = dict(zip("абвгдежзийклмнопрстуфхцчшщъьюя", "a b v g d e zh z i y k l m n o p r s t u f h ts ch sh sht a y yu ya".split()))
# by the object's purpose: (the row of table 1, the row of table 2, what burns, the class of Наредба № Iз-1971)
VIDOVE = ((r"театър|кино|култур|читалищ", "4", "6.2", "седалки, сцена, завеси", "Ф2.1"),
          (r"училищ|НУИ|образов|университет", "1", "6.3", "мебели, хартия, учебни пособия", "Ф4.1"),
          (r"детск|градин|ясла", "1", "6.3", "мебели, играчки, текстил", "Ф1.1"),
          (r"болниц|лечебн|МБАЛ", "2.2", "3", "мебели, легла, текстил", "Ф1.1"),
          (r"жилищ", "3", "4.1", "мебели, текстил", "Ф1.3"))


def bad(msg):
    sys.stderr.write("BAD_INPUT: " + msg + "\n")
    sys.exit(2)


def latin(text):
    s = "".join(LAT.get(c, c) for c in str(text).lower())
    return "_".join(re.findall(r"[a-z0-9]+", s))[:40] or "obekt"


def num(v):
    return f"{v:g}".replace(".", ",")


def script(path, args, cwd):
    p = subprocess.run([sys.executable, path, *args], cwd=cwd, capture_output=True, text=True, timeout=280)
    if p.returncode != 0:
        lines = (p.stderr or p.stdout).strip().splitlines()
        bad(f"{os.path.basename(path)}: " + " / ".join(lines[-3:])[:500])
    return p.stdout


def jsave(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)


def vid_of(ime, predn):
    for pat, vl, i, what, klas in VIDOVE:
        if re.search(pat, f"{ime} {predn}", re.I):
            return vl, i, what, klas
    return "1", "1.1", "мебели, хартия", ""


def own_of(sit):
    return U.own_buildings(sit)


def nearest_hydrant(sit, b):
    c = Polygon(b["kontur"]).buffer(0).centroid
    rows = [v for v in sit.get("vodoiztochnitsi") or [] if v.get("voda_id") and v.get("x") is not None]
    return min(rows, key=lambda v: (v["x"] - c.x) ** 2 + (v["y"] - c.y) ** 2) if rows else None


def pick(pod, pos):
    """A room of a conditional floor: the far end of the floor, or next to the stairs."""
    rooms = pod["pomeshtenia"]
    stair = next(r for r in rooms if r["ime"] == "Стълбище")["tsentar"]
    rows = [r for r in rooms if r["ime"].startswith("Помещение") and 15 <= r["plosht_m2"] <= 80] or \
        [r for r in rooms if r["ime"].startswith("Помещение")]
    if not rows:
        bad("на условния етаж няма помещения")
    dist = lambda r: (r["tsentar"][0] - stair[0]) ** 2 + (r["tsentar"][1] - stair[1]) ** 2   # noqa: E731
    return (max if pos == "kray" else min)(rows, key=dist)


def default_variants(pods, vl, i, what):
    top = max(pods)
    out = [{"ime": f"пожар в помещение на {top} етаж", "fail": f"Konkretna_shema_Pomeshtenie_{top}et", "etazh": top,
            "pozitsiya": "kray", "vl_red": vl, "i_red": i, "natovarvane_vid": what}]
    if top > 1:
        out.append({"ime": "пожар в помещение на 1 етаж до стълбището", "fail": "Konkretna_shema_Pomeshtenie_1et", "etazh": 1,
                    "pozitsiya": "do_stalbishte", "vl_red": vl, "i_red": i, "natovarvane_vid": what})
    return out


def osnovni_danni(a, sit, res, ustanovka):
    imot = (sit.get("kais") or {}).get("imot") or a.kadastar
    sgr = "; ".join(f"{b.get('kais_id')} - {U.floors_of(b)} етажа, застроена площ около {num(round(Polygon(b['kontur']).buffer(0).area))} m²"
                    for b in own_of(sit))
    b0 = max(own_of(sit), key=lambda b: U.floors_of(b))
    m = res.get("marshrut") or {}
    hyd = ", ".join(f"{v.get('voda_id')} ({v.get('etiket')})" for v in (sit.get("vodoiztochnitsi") or [])[:3]) or UT
    rows = [["Забележка.", ustanovka]] if ustanovka else []
    form = sit.get("formulyar") or {}
    def otg(key, gotovo):
        v = form.get(key)
        v = ", ".join(v) if isinstance(v, list) else v
        return gotovo(v) if v and "не знам" not in str(v) else UT
    arh = res.get("arhiv") or {}
    if arh.get("namereno"):
        rows.append(["Стар план.", f"{arh.get('iztochnik')}: " + "; ".join(f"{k}: {v}" for k, v in (arh.get("danni") or {}).items())])
    rows += [["Разположение на сградите.", f"Имот {imot}. Сгради: {sgr} (КАИС). Степен на огнеустойчивост "
              f"{b0.get('ogneustoychivost') or UT}, клас {b0.get('kategoriya') or UT} (приети, да се потвърдят)."],
             ["Предназначение и разпределение.", f"{a.ime}. Разпределението по етажи - {UT}."],
             ["Съхранявани вещества и материали.", f"Видовете, количествата и горимото натоварване - {UT}."],
             ["Комуникации.", "Газ - " + otg("gaz", str) + f". Вода, отопление, вентилация, асансьори - {UT}."],
             ["Главно електрическо табло.", "Мястото - " + otg("el_tablo", str) + "."],
             ["Пожароизвестителна и пожарогасителна инсталация.", "Пожарогасителна инсталация - " + otg("pgi", str) + f". ПИИ, предаване към ЕЕНСП-112, вътрешни пожарни кранове - {UT}. В разчетите е прието без ПИИ: 10 min до съобщението."],
             ["Вероятни опасности.", f"Късо съединение в електрическата инсталация; задимяване на пътищата за евакуация; останалото - {UT}."],
             ["Връзка с обекта.", "Телефони и брой на пребиваващите - да се уточнят с ръководството."],
             ["Водоизточници.", f"Хидранти по базата с водоизточници: {hyd}. Състоянието им да се провери на място."],
             ["Подстъпи.", "Входът за пожарните автомобили - " + otg("vhod_kola", str) + "."]]
    t = f"{m.get('sluzhba') or (m.get('ot') or {}).get('sluzhba') or 'Обслужващото звено'}"
    if m:
        t += f"; разстояние {num(m.get('razstoyanie_km'))} km, време за реагиране около {num(m.get('vreme_min'))} min."
    rows.append(["Обслужващо звено и време за реагиране.", t])
    return rows


def reshenie(v, vname, r, tvr, res_k, sili, usl):
    Rz = sili["rezultat"]
    linii = res_k.get("linii") or []
    glavna, rabotna = (linii + ["", ""])[:2]
    n = int(Rz.get("struinitsi_za_gasene") or 1)
    zash = " Струйник „В“ за защита на стълбищната клетка." if int(Rz.get("struinitsi_za_zashtita") or 0) else ""
    vl = str((sili.get("vhodni") or {}).get("vl") or "")
    note = " Разпределението е условно." if usl else ""
    return [["Място на пожара.", f"{r}, {v['etazh']} етаж.{note}"],
            ["Прогнозирано развитие.", f"Линейна скорост {vl}. Свободно развитие {tvr} min; при този разчет пожарът обхваща {num(Rz['plosht_na_pozhara_m2'])} m²."],
            ["Гасителни вещества.", "Вода - струйници „В“. Забранено: вода върху електрически уредби под напрежение."],
            ["Схема на подаване.", f"I ПА пред входа; работна линия до вратата на помещението ({rabotna}); {n} струйник(а) „В“ пред вратата, пред пожара.{zash} II ПА на хидранта, главна линия до I ПА ({glavna})."],
            ["Евакуация.", f"По пътя, отбелязан на схемата; действителните изходи - {UT}." if usl else "По пътя, отбелязан на схемата."],
            ["Защита на служителите.", "ВДА и лични предпазни средства; пост по безопасност при входа."]]


def object_id(a, res):
    """The object in the register, created when it is not there yet → (id, error)."""
    if res.get("v_registara"):
        return res["obekt"]["id"], None
    args = ["--json", "nov", "--ime", a.ime, "--masto", a.masto or "-", "--adres", a.adres]
    if a.kadastar:
        args += ["--kadastar", a.kadastar]
    if a.lat is not None and a.lon is not None:
        args += ["--lat", str(a.lat), "--lon", str(a.lon)]
    created, err = plan_danni.call(plan_danni.OBEKTI, args, timeout=120)
    if err:
        return None, err
    row = created.get("nov") or {}
    res["obekt"], res["v_registara"] = row, bool(row.get("id"))
    return row.get("id"), None


def save_draft(a, res, sit, plan, built, out, work):
    obekti = plan_danni.OBEKTI
    oid, err = object_id(a, res)
    if err:
        return None, [err]
    note = "РАБОТНА ЧЕРНОВА - вътрешното разпределение е условно; да не се утвърждава."
    errors = []
    def put(vid, files):
        got, err = plan_danni.call(obekti, ["--json", "zapishi", oid, "--vid", vid, "--belezhka", note, *files], timeout=180)
        if err:
            errors.append(err)
    whole = dict(plan)
    whole["situacionna"] = sit
    whole["varianti"] = [{**v, "konkretna": json.load(open(os.path.join(work, v["konkretna"]), encoding="utf-8")),
                          "sili": json.load(open(os.path.join(work, v["sili"]), encoding="utf-8"))} for v in plan["varianti"]]
    wf = os.path.join(work, "shema_chernova_plan.json")
    jsave(wf, whole)
    put("shema_chernova_plan", [os.path.join(out, plan["fail"] + ".docx"), wf])
    for v in whole["varianti"]:
        f = v["fail"]
        vid = "shema_chernova_" + latin(re.sub(r"^Konkretna_shema_?", "", f, flags=re.I))
        k = os.path.join(work, vid + ".json")
        jsave(k, v["konkretna"])
        files = [os.path.join(out, x) for x in (f + ".docx", f + ".dxf", f + "_grafichna.png", "Razchet_" + f + ".docx")]
        put(vid, [x for x in files if os.path.isfile(x)] + [k])
    sits = [x for x in built.get("failove") or [] if os.path.basename(x).startswith("Situacionna_shema")]
    sj = os.path.join(work, "shema_chernova_situacionna.json")
    jsave(sj, sit)
    put("shema_chernova_situacionna", sits + [sj])
    return oid, errors


def main():
    ap = argparse.ArgumentParser(description="Планът за пожарогасене с една команда")
    ap.add_argument("--ime", required=True)
    ap.add_argument("--id", default="")
    ap.add_argument("--adres", default="")
    ap.add_argument("--masto", default="")
    ap.add_argument("--kadastar", default="")
    ap.add_argument("--lat", type=float)
    ap.add_argument("--lon", type=float)
    ap.add_argument("--izgotvil", default="")
    ap.add_argument("--varianti", help="JSON - вариантите (виж началото на файла)")
    ap.add_argument("--danni", help="JSON - точки от данните, които заменят подразбиращите се")
    ap.add_argument("--fail", default="", help="името на плана, на латиница")
    ap.add_argument("--zapishi-chernova", action="store_true")
    ap.add_argument("-d", "--dir", default=".")
    a = ap.parse_args()
    t0 = time.time()
    out = os.path.abspath(a.dir)
    work = os.path.join(out, "_rabotni")
    os.makedirs(work, exist_ok=True)
    args = argparse.Namespace(ime=a.ime, id=a.id, adres=a.adres, masto=a.masto, kadastar=a.kadastar, lat=a.lat, lon=a.lon,
                              izgotvil=a.izgotvil, dir=work, bez_kais=True)
    res = plan_danni.collect(args)
    times = dict(res.get("vreme_s") or {})
    if res.get("kandidati") and not res.get("v_registara") and not (a.kadastar or a.lat is not None):
        bad("има няколко възможни обекта - посочи --id, --kadastar или точка: " + json.dumps(res["kandidati"], ensure_ascii=False)[:400])
    sit_path = next((f for f in res.get("failove") or [] if os.path.basename(str(f)) == "situacionna_shema.json"), None)
    if not res.get("ima_situacionna_shema") or not sit_path:
        print(json.dumps({"trebva_situacionna_shema": True, "obekt": res.get("obekt"), "preduprezhdeniya": res.get("preduprezhdeniya") or [],
                          "za_claude": "Обектът няма запазена ситуационна схема. Направи я сега, без да питаш дали: скилът shemi, ситуационна "
                                       "схема с формуляра с въпроси (references/situacionna.md, references/formulyar.md), запис с obekti.py "
                                       "zapishi --vid situacionna_shema. После пусни отново plan_avto.py."}, ensure_ascii=False, indent=1))
        return
    if not os.path.isabs(sit_path):
        sit_path = os.path.join(work, sit_path)
    sit = json.load(open(sit_path, encoding="utf-8"))
    site = os.path.join(work, "situacionna.json")
    predn = " ".join(str(b.get("etiket") or "") for b in own_of(sit))
    vl, i, what, klas = vid_of(a.ime, predn)
    for b in own_of(sit):                 # never an invented degree: unknown stays „to be checked“, on the scheme too
        b.setdefault("kategoriya", klas)
        b["kategoriya"] = b["kategoriya"] or klas
        b["ogneustoychivost"] = b.get("ogneustoychivost") or "да се уточни"
    jsave(site, sit)
    t1 = time.time()
    real = {}
    for f in res.get("failove") or []:
        m = re.fullmatch(r"shema_podlozhka_et(\d+)\.json", os.path.basename(str(f)))
        if m:
            real[int(m.group(1))] = json.load(open(f if os.path.isabs(str(f)) else os.path.join(work, f), encoding="utf-8"))
    usl = not real
    main_b = U.main_building(sit)
    varianti = json.load(open(a.varianti, encoding="utf-8")) if a.varianti else None
    if real and not varianti:
        bad("обектът има етажи от чертеж - подай --varianti с помещенията им: " +
            json.dumps({n: [r["ime"] for r in p["pomeshtenia"]] for n, p in real.items()}, ensure_ascii=False)[:800])
    built_pods = {}
    def floors_for(v):
        if real:
            return real
        key = (v.get("sgrada"), v["etazh"] if v.get("pozitsiya") == "zala" else None)
        if key not in built_pods:
            built_pods[key] = U.make(sit, v.get("sgrada"), None, (v["etazh"],) if v.get("pozitsiya") == "zala" else ())[0]
        return built_pods[key]
    if not varianti:
        varianti = default_variants(floors_for({"etazh": 1}), vl, i, what)
    m = res.get("marshrut") or {}
    t_dv = max(1, round(float(m.get("vreme_min") or 3)))
    tvr = 10 + t_dv + 5
    lst = sit.get("list") or {}
    izgotvil = res.get("izgotvil") or situacionna.own_name() or lst.get("izgotvil") or ""
    dat = time.strftime("%d.%m.%Y")
    plan_v = []
    for k, v in enumerate(varianti, 1):
        tag = f"v{k}"
        pods = floors_for(v)
        n = int(v["etazh"])
        if n not in pods:
            bad(f"няма етаж {n}: {sorted(pods)}")
        pod = json.loads(json.dumps(pods[n]))
        pos = v.get("pozitsiya")
        if usl:
            room = next(r for r in pod["pomeshtenia"] if r["ime"] == "Зала") if pos == "zala" else pick(pod, pos or "kray")
            if v.get("naimenovanie"):
                room["ime"] = v["naimenovanie"]
            ime_r = room["ime"]
        else:
            ime_r = v["pomeshtenie"]
            room = next((r for r in pod["pomeshtenia"] if r["ime"] == ime_r), None)
            if not room:
                bad(f"няма помещение „{ime_r}“ на етаж {n}")
        jsave(os.path.join(work, f"pod_{tag}.json"), pod)
        area, (ra, rb) = room["plosht_m2"], room["razmeri_m"]
        front = rb if pos == "zala" else ra
        depth = round(area / front, 1)
        sili_args = ["tvardi", "--forma", "pravoagalnik", "--t-ds", "10", "--t-dv", str(t_dv), "--t-r", "5", "--ataka", "front1",
                     "--struinik", "В", "--q-pa", "40", "-o", f"s_{tag}.json", "--vl-red", str(v.get("vl_red") or vl),
                     "--i-red", str(v.get("i_red") or i), "--a", str(front), "--b", str(depth),
                     "--pomeshtenie", f"{num(depth)}x{num(front)}"]
        zashtita = n > 1
        if zashtita:
            sili_args += ["--n-zashtita", "1"]
        script(SILI, sili_args, work)
        sili = json.load(open(os.path.join(work, f"s_{tag}.json"), encoding="utf-8"))
        b = next((x for x in own_of(sit) if str(x.get("kais_id")) == str(v.get("sgrada"))), main_b)
        hyd = nearest_hydrant(sit, b)
        if not hyd:
            bad("в схемата няма водоизточник с voda_id")
        fail = v.get("fail") or f"Konkretna_shema_V{k}"
        t3b = {"redove": [{"natovarvane_vid": v.get("natovarvane_vid") or what, "natovarvane_kg_m2": UT, "pgi_vid": UT,
                           "gasitelni_neobhodimi": "вода", "gasitelni_zabraneni": "вода върху ел. уредби под напрежение",
                           "zashtita": "СИЗ на пожарникаря, ВДА", "rvm_vid": "няма данни",
                           "drugi": "Разпределението е условно" if usl else ""}], "prazni_redove": 3}
        jsave(os.path.join(work, f"t3b_{tag}.json"), t3b)
        vhod = v.get("vhod") or "Фоайе"
        pat = v.get("pat") if v.get("pat") is not None else ("" if pos == "zala" else ("Стълбище,Коридор" if zashtita else "Коридор"))
        kargs = ["--podlozhka", f"pod_{tag}.json", "--kais", "situacionna.json", "--pomeshtenie", ime_r, "--vhod", vhod,
                 "--pat", pat, "--hidrant", hyd["voda_id"], "--hidrant-etiket", hyd.get("etiket") or "ПХ", "--sili", f"s_{tag}.json",
                 "--etazh", str(n), "--ogneustoychivost", str(b.get("ogneustoychivost") or "да се уточни"),
                 "--kategoriya", str(b.get("kategoriya") or ""), "--tablitsa-3b", f"t3b_{tag}.json",
                 "--obekt", str(lst.get("obekt") or a.ime), "--sobstvenik", str(lst.get("sobstvenik") or ""),
                 "--izgotvil", izgotvil, "--data", dat, "--fail", fail + ".dxf", "-o", f"k_{tag}.json"]
        if zashtita and pos != "zala":
            kargs += ["--zashtita", "Стълбище"]
        res_k = json.loads(script(KONKRETNA, kargs, work))
        plan_v.append({"ime": v["ime"], "fail": fail, "konkretna": f"k_{tag}.json", "sili": f"s_{tag}.json",
                       "pomeshtenie": f"{ime_r}, {n} ет." + (f" - условно {num(ra)} x {num(rb)} m" if usl else f" - {num(ra)} x {num(rb)} m"),
                       "reshenie": reshenie(v, tag, ime_r, tvr, res_k, sili, usl), **({"zashtita": "Стълбище"} if zashtita and pos != "zala" else {})})
    times["varianti"] = round(time.time() - t1, 1)
    bele = ("РАБОТНА ЧЕРНОВА. Няма одобрени етажни чертежи: контурите, площите и етажността са от КАИС, а вътрешното разпределение "
            "(помещения, врати, стълбище, вход) е условно. Числата в разчетите важат само за условните размери. Да не се утвърждава в този вид.") if usl else ""
    danni = osnovni_danni(a, sit, res, bele)
    if a.danni:
        for row in json.load(open(a.danni, encoding="utf-8")):
            i_ = next((j for j, d in enumerate(danni) if d[0] == row[0]), None)
            if i_ is None:
                danni.append(row)
            else:
                danni[i_] = row
    obekt_id = (res.get("obekt") or {}).get("kadastar") or a.kadastar or a.id
    fail = a.fail or ("Plan_pozharogasene_" + latin(a.ime)[:30] + ("_CHERNOVA" if usl else ""))
    plan = {"fail": fail, "godina": time.localtime().tm_year, "obekt": a.ime + (" (чернова)" if usl else ""),
            "adres": ", ".join(x for x in (a.masto, a.adres) if x),
            "identifikator": f"ПИ {(sit.get('kais') or {}).get('imot') or obekt_id}",
            "saglasuvano": {"lines": ["Ръководител на обекта"], "name": ""}, "danni": danni, "situacionna": "situacionna.json",
            "varianti": plan_v, "prilozhenie_4": {"broi": 14},
            "izgotvil": {"lines": [], "name": izgotvil, "data": dat + " г."}}
    jsave(os.path.join(work, "plan.json"), plan)
    t2 = time.time()
    built = json.loads(script(BUILD, ["plan.json", "-d", out], work))
    times["sglobyavane"] = round(time.time() - t2, 1)
    draft, errors = (None, [])
    if a.zapishi_chernova:
        t3 = time.time()
        draft, errors = save_draft(a, res, sit, plan, built, out, work)
        times["zapis"] = round(time.time() - t3, 1)
    times["obshto"] = round(time.time() - t0, 1)
    print(json.dumps({"plan": built.get("plan"), "failove": built.get("failove"), "uslovni_etazhi": usl,
                      "varianti": [v["ime"] for v in plan_v], "chernova_v_registara": draft,
                      "da_se_utochni": [d[0] for d in danni if UT in str(d[1])], "prieto": res.get("prieto") or [],
                      "preduprezhdeniya": (built.get("preduprezhdeniya") or []) + (res.get("preduprezhdeniya") or []) + errors,
                      "vreme_s": times}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
