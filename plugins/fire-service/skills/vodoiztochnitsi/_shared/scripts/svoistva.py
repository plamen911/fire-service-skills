#!/usr/bin/env python3
"""
svoistva.py — пожароопасните свойства на веществата с източника на всяка стойност, и позоваванията
на източниците в документите (ЕПТЗ).

Стойностите са в `_shared/svoistva/stoinosti.csv` – всяка е свалена от Международната карта за
химична безопасност (ICSC, ILO/WHO) на веществото, с номера и версията на картата, адреса и датата,
на която е сверена (tools/icsc_fetch.py в хранилището). Каталогът на източниците (книги, стандарти,
бази) е в `_shared/svoistva/iztochnitsi.json`. Нищо не се пише по памет: вещество, което го няма в
таблицата, излиза с NOT_FOUND.

    python3 _shared/scripts/svoistva.py дизел                 # свойствата, позоваването и реда за литературата
    python3 _shared/scripts/svoistva.py "пропан-бутан" --json
    python3 _shared/scripts/svoistva.py --spisak              # всички вещества в таблицата
    python3 _shared/scripts/svoistva.py --iztochnitsi         # ключовете на източниците за [[…]]

Позоваване в текста на документ: маркер `[[ключ]]` или `[[ключ: място]]` след числото, напр.
„52 °C [[icsc:1561]]“, „600 ÷ 660 °C [[chochev: прил. № 7, с. 223]]“, няколко – с „;“:
`[[icsc:1561; simeonov]]`. `citiraj()` ги сменя с „(ICSC 1561)“, „(Чочев, 2003, прил. № 7, с. 223)“
и връща редовете на „Използвана литература“ – винаги задължителните, после цитираните по реда
на първото позоваване.
"""
import argparse
import csv
import difflib
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "svoistva")
STOINOSTI = os.path.join(DATA, "stoinosti.csv")
KATALOG = os.path.join(DATA, "iztochnitsi.json")
MARKER_RE = re.compile(r"\s*\[\[([^\[\]]*)\]\]")
ITEM_RE = re.compile(r"^\s*(icsc:\d{4}|[a-z0-9][a-z0-9-]*)\s*(?:[:,]\s*(.+?))?\s*$")

LABELS = [("plamna", "Пламна температура"), ("samovazpl", "Температура на самовъзпламеняване"),
          ("granitsi", "Граници на взривяемост във въздух (КГВ–ВГВ)"), ("kipene", "Температура на кипене"),
          ("otn_platnost_pari", "Относителна плътност на парите (въздух = 1)")]
METOD = {"з.т.": "затворен тигел", "о.т.": "открит тигел"}


class Problem(Exception):
    pass


# ---------- data ----------
def stoinosti():
    with open(STOINOSTI, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def katalog():
    with open(KATALOG, encoding="utf-8") as f:
        return json.load(f)


def norm(s):
    s = s.lower().replace("ѝ", "й").replace("ё", "е")
    return re.sub(r"[\s\-–_.,]+", "", s)


def chislo(v):
    """'12.0' -> '12,0'; '254-285' -> '254–285'; '<-21' -> 'под -21'; '~250' -> 'около 250'."""
    if not v:
        return ""
    pre = {"<": "под ", ">": "над ", "~": "около "}.get(v[0], "")
    if pre:
        v = v[1:]
    v = re.sub(r"(?<=\d)-(?=-?\d)", "–", v).replace(".", ",")
    return pre + v


def formatirai(r):
    """The values of one row as Bulgarian text, empty values left out."""
    out = {}
    if r["plamna"]:
        out["plamna"] = f"{chislo(r['plamna'])} °C" + (f", {METOD[r['plamna_metod']]}" if r["plamna_metod"] else "")
    elif r["sastoyanie"] == "газ":
        out["plamna"] = "няма – горим газ"
    if r["samovazpl"]:
        out["samovazpl"] = f"{chislo(r['samovazpl'])} °C"
    if r["kgv"] and r["vgv"]:
        out["granitsi"] = f"{chislo(r['kgv'])}–{chislo(r['vgv'])} % (об.)"
    if r["kipene"]:
        out["kipene"] = f"{chislo(r['kipene'])} °C"
    if r["otn_platnost_pari"]:
        out["otn_platnost_pari"] = chislo(r["otn_platnost_pari"])
    return out


def tarsi(q, rows=None):
    rows = rows if rows is not None else stoinosti()
    n = norm(q)
    if not n:
        raise Problem("NOT_FOUND: празно търсене")
    exact, part = [], []
    for r in rows:
        names = [r["ime"], r["ime_en"], r["cas"], r["kluch"], r["kluch"].split(":")[1]] + r["sinonimi"].split(";")
        ns = [norm(x) for x in names if x]
        if n in ns:
            exact.append(r)
        elif len(n) >= 4 and any(n in x for x in ns):
            part.append(r)
    if exact or part:
        return exact or part
    names = sorted({x for r in rows for x in [r["ime"]] + r["sinonimi"].split(";") if x})
    close = difflib.get_close_matches(q.lower(), names, n=5, cutoff=0.6)
    raise Problem(f"NOT_FOUND: няма потвърдена стойност за „{q}“ в таблицата – не я давай по памет"
                  + (f". Най-близки: {', '.join(close)}" if close else ""))


# ---------- sources ----------
def iztochnik(kluch, extra=None, rows=None):
    """{'kratko', 'palno'} for a source key: a catalogue entry, an ICSC card or an extra (per-case) source."""
    if extra and kluch in extra:
        e = extra[kluch]
        if not e.get("kratko") or not e.get("palno"):
            raise Problem(f"BAD_SOURCE: „{kluch}“ в dop_iztochnitsi иска „kratko“ и „palno“")
        return {"kratko": e["kratko"], "palno": e["palno"]}
    k = katalog()
    if kluch in k["iztochnitsi"]:
        return k["iztochnitsi"][kluch]
    if kluch.startswith("icsc:"):
        rows = rows if rows is not None else stoinosti()
        r = next((x for x in rows if x["kluch"] == kluch), None)
        if r is None:
            raise Problem(f"UNKNOWN_SOURCE: картата {kluch} не е в таблицата – добави я с tools/icsc_fetch.py")
        nomer = kluch.split(":")[1]
        d = {**r, "nomer": nomer, "proveren": ".".join(reversed(r["proveren"].split("-"))) + " г."}
        return {"kratko": k["_icsc"]["kratko"].format(**d), "palno": k["_icsc"]["palno"].format(**d)}
    keys = list(k["iztochnitsi"]) + list(extra or {})
    close = difflib.get_close_matches(kluch, keys, n=3)
    raise Problem(f"UNKNOWN_SOURCE: няма източник „{kluch}“" + (f" – може би {', '.join(close)}?" if close else ""))


def _krai(lines):
    """';' after every line, '.' after the last one."""
    out = [l.rstrip().rstrip(";").rstrip() for l in lines]
    out = [l + ";" for l in out[:-1]] + ([out[-1] if out[-1].endswith(".") else out[-1] + "."] if out else [])
    return out


def _sravni(s):
    return re.sub(r"[\s„“”\"';.,]+", "", s).lower()


def citiraj(text, extra=None, dop_literatura=None):
    """Replace the [[…]] markers with „(Кратко, място)“ and build the literature list.

    Returns (text, literature lines, used keys). Unknown keys raise Problem – a document must not
    cite a source that is not in the catalogue."""
    rows = stoinosti()
    used, errors = [], []

    def sub(m):
        parts = []
        for item in m.group(1).split(";"):
            im = ITEM_RE.match(item)
            if not im:
                errors.append(f"неразпознат маркер „[[{m.group(1)}]]“")
                continue
            kluch, mesto = im.group(1), im.group(2)
            try:
                src = iztochnik(kluch, extra, rows)
            except Problem as e:
                errors.append(str(e))
                continue
            if kluch not in used:
                used.append(kluch)
            parts.append(src["kratko"] + (f", {mesto}" if mesto else ""))
        return f" ({'; '.join(parts)})" if parts else ""

    out = MARKER_RE.sub(sub, text)
    if errors:
        raise Problem("; ".join(dict.fromkeys(errors)))
    # a reference typed by hand – „(Чочев, 2003, …)“, „(ICSC 1561)“ – counts as a citation too
    k = katalog()["iztochnitsi"]
    first = {}
    for key, v in list(k.items()) + list((extra or {}).items()):
        i = out.find(v["kratko"])
        if i >= 0:
            first[key] = i
    for m in re.finditer(r"ICSC (\d{4})", out):
        key = f"icsc:{m.group(1)}"
        if key not in first:
            if not any(r["kluch"] == key for r in rows):
                raise Problem(f"UNKNOWN_SOURCE: в текста има {m.group(0)}, а картата не е в таблицата")
            first[key] = m.start()
    used = sorted(set(used) | set(first), key=lambda x: first.get(x, 0))
    keys = [x for x, v in k.items() if v.get("vinagi")] + [x for x in used if not k.get(x, {}).get("vinagi")]
    lines = [iztochnik(x, extra, rows)["palno"] for x in keys]
    seen = {_sravni(l) for l in lines}
    for l in dop_literatura or []:
        if l and _sravni(l) not in seen:
            lines.append(l)
            seen.add(_sravni(l))
    return out, _krai(lines), used


def bez_iztochnik(text):
    """Sentences with a temperature, energy or concentration but without a [[…]] marker (a warning)."""
    out = []
    for s in re.split(r"(?<=[.!?])\s+", text):
        if re.search(r"\d\s*(?:°\s*C|°С|kW|kJ|MJ|% ?\(об\.\)|об\. ?%)", s) and "[[" not in s:
            out.append(s.strip())
    return out


# ---------- CLI ----------
def pokazhi(r, extra=None):
    f = formatirai(r)
    src = iztochnik(r["kluch"], extra)
    lines = [f"{r['ime']} – {r['ime_en']}" + (f", CAS {r['cas']}" if r["cas"] else "")]
    for k, label in LABELS:
        lines.append(f"  {label}: {f.get(k, '—')}")
    lines.append(f"  Позоваване в текста: ({src['kratko']})   маркер в ЕПТЗ: [[{r['kluch']}]]")
    lines.append(f"  Литература: {src['palno']}")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="Пожароопасни свойства на веществата с източника им")
    ap.add_argument("ime", nargs="?", help="вещество – име, синоним, CAS или номер на ICSC карта")
    ap.add_argument("--spisak", action="store_true", help="всички вещества в таблицата")
    ap.add_argument("--iztochnitsi", action="store_true", help="ключовете на източниците за [[…]]")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    try:
        if a.iztochnitsi:
            k = katalog()
            for key, v in k["iztochnitsi"].items():
                print(f"{key:26} ({v['kratko']}){'  – винаги в литературата' if v.get('vinagi') else ''}")
                print(f"{'':26} {v['v_skila']}")
            print(f"{'icsc:NNNN':26} ({k['_icsc']['kratko'].format(nomer='NNNN')}) – картите в таблицата, виж --spisak")
            return
        rows = stoinosti()
        if a.spisak:
            for r in rows:
                print(f"{r['kluch']}  {r['ime']} ({r['sinonimi'].replace(';', ', ')})")
            return
        if not a.ime:
            ap.error("кажи вещество, --spisak или --iztochnitsi")
        found = tarsi(a.ime, rows)
        if a.json:
            print(json.dumps([{**r, "tekst": formatirai(r), "iztochnik": iztochnik(r["kluch"])} for r in found],
                             ensure_ascii=False, indent=1))
        else:
            print("\n\n".join(pokazhi(r) for r in found))
    except Problem as e:
        print(e, file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
