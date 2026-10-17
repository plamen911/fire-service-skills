#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
diktovka.py — справка по диктовка: потребителят разказва пожара с гласа си (микрофонът на
клавиатурата на телефона или гласовото въвеждане в приложението на Claude), Claude разпределя
казаното по въпросите на бързия формуляр (references/formulyar.json), а скриптът проверява
разпределението и казва кои въпроси остават – само те се питат с кликване.

    python3 scripts/diktovka.py proveri otgovori.json

otgovori.json (пише го Claude от диктовката):
{
  "form": "mps",                         // ключът на формуляра (formulyar.md, т. 2)
  "prichina": "01",                      // кодът на причината – от записа или от казаното; "" ако не е ясна
  "prichini_veroyatni": ["01", "08"],    // само при „в процес на установяване“ (09) – казаните вероятни причини
  "utochnenie": "ел. инсталация в двигателния отсек",   // от causes.details или „Друго: …“
  "otgovori": {                          // id на въпроса → избраните опции (дословно от формуляра)
    "gorivo": ["дизел"],
    "ognishte": ["Друго: под капака, отляво до акумулатора"],   // казаното, което не пасва на опция
    "sasedni": ["няма"]
  },
  "zapis": {"place": "двигател", "detail.activity_area": "", "reason": "късо съединение-01"},
                                         // полетата от записа в базата, които формулярът ползва (from_record)
  "izvan_formulyara": ["собственикът казва, че е карал 200 км преди това"]
                                         // казаното, което не е отговор на въпрос – влиза в т. 3 като факт
}

Изход – JSON: {"ok", "prieti", "greshki", "protivorechiya", "ostavat", "ekrani", "izvan_formulyara"}.
„ekrani“ са готовите въпроси за AskUserQuestion – до 4 на екран, до 4 опции, най-честата първа.
"""
import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
FORMULYAR = os.path.join(HERE, "..", "references", "formulyar.json")
OTHER = re.compile(r"^\s*друго\s*[:–-]\s*(.+)$", re.I)
MAX_PER_SCREEN, MAX_OPTIONS = 4, 4


def out(obj):
    print(json.dumps(obj, ensure_ascii=False, indent=2))


def fail(msg):
    out({"ok": False, "error": f"BAD_INPUT: {msg}"})
    sys.exit(1)


def norm(s):
    return re.sub(r"\s+", " ", str(s or "")).strip().lower()


def record_value(zapis, key):
    v = zapis.get(key)
    if v in (None, "") and "." in key:
        cur = zapis
        for part in key.split("."):
            cur = cur.get(part) if isinstance(cur, dict) else None
        v = cur
    return v


def check(data, f):
    forms, causes = f["forms"], f["causes"]
    form = data.get("form")
    if form not in forms:
        fail(f"form „{form}“ – трябва едно от: {', '.join(forms)}")
    questions = {q["id"]: q for q in forms[form]["questions"]}
    zapis = data.get("zapis") or {}
    ignore = {norm(v) for v in (f.get("place_ignore") or {}).get("values", [])}
    code = str(data.get("prichina") or "")
    m = re.search(r"-(\d{2})\s*$", str(zapis.get("reason") or ""))
    if not code and m:
        code = m.group(1)
    greshki, protiv, prieti = [], [], {}

    for qid, raw in (data.get("otgovori") or {}).items():
        q = questions.get(qid)
        if not q:
            greshki.append(f"въпрос „{qid}“ няма във формуляра „{form}“ – провери ключа")
            continue
        vals = raw if isinstance(raw, list) else [raw]
        vals = [v for v in vals if str(v).strip()]
        if not vals:
            continue
        if not q.get("multi") and len(vals) > 1:
            greshki.append(f"„{q['label']}“ приема един отговор, дадени са {len(vals)}: {vals}")
            continue
        good = []
        opts = {norm(o): o for o in q["options"]}
        for v in vals:
            if OTHER.match(str(v)):
                good.append("Друго: " + OTHER.match(str(v)).group(1).strip())
            elif norm(v) in opts:
                good.append(opts[norm(v)])
            elif q.get("number") and re.search(r"\d", str(v)):
                n = re.search(r"\d+(?:[.,]\d+)?", str(v)).group(0).replace(",", ".")
                good.append(f"около {n} {q['number']}")
            else:
                greshki.append(f"„{q['label']}“: „{v}“ не е опция – дай я като „Друго: {v}“ или избери от: "
                               + " / ".join(q["options"]))
        neg = [g for g in good if norm(g).startswith(("няма", "нямало"))]
        if q.get("multi") and neg and len(good) > 1:
            greshki.append(f"„{q['label']}“: „{neg[0]}“ не върви заедно с други отговори")
            continue
        if good:
            prieti[qid] = good
        rec_key = q.get("from_record")
        rec = record_value(zapis, rec_key) if rec_key else None
        if rec and norm(rec) not in ignore and good and not any(norm(rec) in norm(g) or norm(g) in norm(rec) for g in good):
            protiv.append(f"„{q['label']}“: казано е „{good[0]}“, а в записа е „{rec}“ – пише се казаното; кажи го с едно изречение")

    if code and code not in causes["codes"]:
        greshki.append(f"причина „{code}“ няма такъв код ({', '.join(causes['codes'])})")
    for c in data.get("prichini_veroyatni") or []:
        if str(c) not in causes["codes"] or str(c) == causes.get("in_progress"):
            greshki.append(f"вероятна причина „{c}“ не е допустим код")

    # what is still to be asked
    ostavat = []
    for q in forms[form]["questions"]:
        if q["id"] in prieti:
            continue
        rec_key = q.get("from_record")
        rec = record_value(zapis, rec_key) if rec_key else None
        if rec and norm(rec) not in ignore:
            continue
        if code and code in (q.get("by_cause") or {}):
            prieti[q["id"]] = [q["by_cause"][code]]
            continue
        ostavat.append(q)
    if not code:
        ostavat.insert(0, {"id": "prichina", "label": "Причина", "multi": False,
                           "options": [causes["codes"][c] for c in causes["by_form"][form]]})
    elif code != causes.get("in_progress") and not data.get("utochnenie") and code in causes["details"]:
        det = causes["details"][code]
        ostavat.insert(0, {"id": "utochnenie", "label": "Уточнение на причината", "multi": False,
                           "options": det.get(form) or det.get("default") or []})

    ekrani, screen = [], []
    for q in ostavat:
        opts = list(q["options"])
        first = q.get("default") or opts[0]
        opts = [first] + [o for o in opts if o != first]
        item = {"id": q["id"], "header": q["label"][:12], "question": q["label"] + "?", "multiSelect": bool(q.get("multi")),
                "options": [o + (" (най-често)" if i == 0 else "") for i, o in enumerate(opts[:MAX_OPTIONS])]}
        screen.append(item)
        if len(screen) == MAX_PER_SCREEN:
            ekrani.append(screen)
            screen = []
    if screen:
        ekrani.append(screen)
    return {"ok": not greshki, "form": form, "prichina": code, "prieti": prieti, "greshki": greshki,
            "protivorechiya": protiv, "ostavat": [q["id"] for q in ostavat], "ekrani": ekrani,
            "izvan_formulyara": data.get("izvan_formulyara") or []}


def main(argv=None):
    ap = argparse.ArgumentParser(description="справка по диктовка – проверка и останалите въпроси")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("proveri"); p.add_argument("otgovori")
    p.add_argument("--formulyar", default=FORMULYAR)
    a = ap.parse_args(argv)
    try:
        data = json.load(open(a.otgovori, encoding="utf-8"))
        f = json.load(open(a.formulyar, encoding="utf-8"))
    except (OSError, ValueError) as e:
        fail(str(e))
    out(check(data, f))
    return 0


if __name__ == "__main__":
    sys.exit(main())
