#!/usr/bin/env python3
"""
svoistva.py — пожароопасните свойства на веществата и материалите с източника на всяка стойност, и
позоваванията на източниците в документите (ЕПТЗ).

Данните са в `_shared/svoistva/`, всяка стойност – свалена от източника си със скрипт от `tools/` в
хранилището, с адреса и датата на сверяване:
  • `stoinosti.csv` – горими течности и газове, от Международните карти за химична безопасност
    (ICSC, ILO/WHO);
  • `chris.csv` – растителни масла и мазнини, от картите CHRIS на Бреговата охрана на САЩ
    (температурите в картите са във °F – пазят се и те, и преводът в °C);
  • `prahove.csv` – прахове (дървесен прах, слама, брашно, памук, пластмаси, въглища), проба по проба,
    от базата GESTIS-STAUB-EX (IFA/DGUV);
  • `literatura.csv` – стойности от книги и статии (масивна дървесина – Babrauskas, 2002), всяка със
    страницата; маркерът ѝ е ключът на източника с мястото – `[[babrauskas-2002: табл. 5, с. 184]]`.
Каталогът на източниците (книги, стандарти, бази) е `_shared/svoistva/iztochnitsi.json`. Нищо не се
пише по памет: вещество, което го няма в таблиците, излиза с NOT_FOUND.

    python3 _shared/scripts/svoistva.py дизел                 # свойствата, позоваването и реда за литературата
    python3 _shared/scripts/svoistva.py слама
    python3 _shared/scripts/svoistva.py "пропан-бутан" --json
    python3 _shared/scripts/svoistva.py --spisak              # всичко в таблиците
    python3 _shared/scripts/svoistva.py --iztochnitsi         # ключовете на източниците за [[…]]

Позоваване в текста на документ: маркер `[[ключ]]` или `[[ключ: място]]` след числото, напр.
„52 °C [[icsc:1561]]“, „600 ÷ 660 °C [[chochev: прил. № 7, с. 223]]“, няколко – с „;“:
`[[icsc:1561; simeonov]]`. `citiraj()` ги сменя с „(ICSC 1561)“, „(Чочев, 2003, прил. № 7)“ – в текста
само автор и година (при Чочев и приложението); страницата остава в маркера за проверката
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
KEY = r"icsc:\d{4}|chris:[a-z]{3}|gestis-staub:\d+|metar:[A-Za-z]{4}|[a-z0-9][a-z0-9-]*"
ITEM_RE = re.compile(r"^\s*(" + KEY + r")\s*(?:[:,]\s*(.+?))?\s*$")
# a reference typed by hand instead of a marker
HAND_RE = re.compile(r"ICSC (\d{4})|CHRIS ([A-Z]{3})\b|GESTIS-STAUB-EX, № (\d+)")

LABELS = [("plamna", "Пламна температура"), ("samovazpl", "Температура на самовъзпламеняване"),
          ("granitsi", "Граници на взривяемост във въздух (КГВ–ВГВ)"), ("kipene", "Температура на кипене"),
          ("topene", "Температура на топене"),
          ("otn_platnost_pari", "Относителна плътност на парите (въздух = 1)")]
LABELS_PRAH = [("zapalvane_oblak", "Температура на запалване на облак прах"),
               ("tleene_sloy", "Температура на тлеене на слой прах 5 mm"),
               ("dgv", "Долна граница на взривяемост"), ("proba", "Пробата")]
METOD = {"з.т.": "затворен тигел", "о.т.": "открит тигел"}
METOD_PRAH = {"G-G": "пещ на Годберт-Грийнуолд", "BAM": "пещ BAM"}


class Problem(Exception):
    pass


# ---------- data ----------
def katalog():
    with open(KATALOG, encoding="utf-8") as f:
        return json.load(f)


def _read(name):
    path = os.path.join(DATA, name)
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def stoinosti():
    """All rows of all tables; dust rows carry vid='прах', the rest vid='течност/газ'."""
    rows = []
    # values from books first: a question about „дърво“ is usually about the solid material, not its dust
    for r in _read("literatura.csv"):
        r.update(vid="литература", kluch="lit:" + r["id"], ime_en="")
        rows.append(r)
    for name in dict.fromkeys(s["tablitsa"] for s in katalog()["_shabloni"].values()):
        for r in _read(name):
            r["vid"] = "прах" if "zapalvane_oblak" in r else "течност/газ"
            rows.append(r)
    return rows


def marker(r):
    """The [[…]] marker that cites this row."""
    if r["vid"] == "литература":
        return f"[[{r['iztochnik']}: {r['mesto']}]]"
    return f"[[{r['kluch']}]]"


def norm(s):
    s = s.lower().replace("ѝ", "й").replace("ё", "е")
    return re.sub(r"[\s\-–_.,/()]+", "", s)


def chislo(v):
    """'12.0' -> '12,0'; '254-285' -> '254–285'; '<-21' -> 'под -21'; '~250' -> 'около 250'."""
    if not v:
        return ""
    pre = {"<": "под ", ">": "над ", "~": "около "}.get(v[0], "")
    if pre:
        v = v[1:]
    v = re.sub(r"(?<=\d)-(?=-?\d)", "–", v).replace(".", ",")
    return pre + v


def _izhodni_f(r, label):
    m = re.search(re.escape(label) + r": (\d+)°F", r.get("izhodni", ""))
    return f" ({m.group(1)} °F в картата)" if m else ""


def formatirai(r):
    """The values of one row as Bulgarian text, empty values left out."""
    out = {}
    if r["vid"] == "литература":
        return {"stoinost": r["stoinost"], "usloviya": r["usloviya"]}
    if r["vid"] == "прах":
        if r["zapalvane_oblak"]:
            out["zapalvane_oblak"] = f"{chislo(r['zapalvane_oblak'])} °C" + (
                f" ({METOD_PRAH[r['zapalvane_metod']]})" if r["zapalvane_metod"] in METOD_PRAH else "")
        t = r["tleene_sloy"].replace(" ", "")
        if t.startswith("n.g.u."):
            out["tleene_sloy"] = f"не тлее до {t[6:]} °C"
        elif t == "melts":
            out["tleene_sloy"] = "топи се, преди да започне да тлее"
        elif t:
            out["tleene_sloy"] = f"{chislo(t)} °C"
        if r["dgv"]:
            out["dgv"] = f"{chislo(r['dgv'])} g/m³"
        proba = [f"медиана на частиците {chislo(r['mediana_um'])} μm" if r["mediana_um"] else "",
                 f"влажност {chislo(r['vlazhnost'])} %" if r["vlazhnost"] else ""]
        if any(proba):
            out["proba"] = ", ".join(x for x in proba if x)
        return out
    if r["plamna"]:
        out["plamna"] = f"{chislo(r['plamna'])} °C" + (f", {METOD[r['plamna_metod']]}" if r["plamna_metod"] else "") \
            + _izhodni_f(r, "Flash Point")
    elif r["sastoyanie"] == "газ":
        out["plamna"] = "няма – горим газ"
    if r["samovazpl"]:
        out["samovazpl"] = f"{chislo(r['samovazpl'])} °C" + _izhodni_f(r, "Auto Ignition Temperature")
    if r["kgv"] and r["vgv"]:
        out["granitsi"] = f"{chislo(r['kgv'])}–{chislo(r['vgv'])} % (об.)"
    if r["kipene"]:
        out["kipene"] = f"{chislo(r['kipene'])} °C"
    if r.get("topene"):
        out["topene"] = f"{chislo(r['topene'])} °C"
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
        names = [r["ime"], r["ime_en"], r.get("cas", ""), r["kluch"], r["kluch"].split(":")[1]] + r["sinonimi"].split(";")
        ns = [norm(x) for x in names if x]
        if n in ns:
            exact.append(r)
        elif len(n) >= 4 and any(n in x for x in ns):
            part.append(r)
    if exact or part:
        return exact or part
    names = sorted({x for r in rows for x in [r["ime"]] + r["sinonimi"].split(";") if x})
    close = difflib.get_close_matches(q.lower(), names, n=5, cutoff=0.6)
    raise Problem(f"NOT_FOUND: няма потвърдена стойност за „{q}“ в таблиците – не я давай по памет"
                  + (f". Най-близки: {', '.join(close)}" if close else ""))


# ---------- sources ----------
def _iso(d):
    return ".".join(reversed(d.split("-"))) + " г." if re.fullmatch(r"\d{4}-\d{2}-\d{2}", d or "") else d


def iztochnik(kluch, extra=None, rows=None):
    """{'kratko', 'palno'} for a source key: a catalogue entry, a card/record from a table or an extra (per-case) source."""
    if extra and kluch in extra:
        e = extra[kluch]
        if not e.get("kratko") or not e.get("palno"):
            raise Problem(f"BAD_SOURCE: „{kluch}“ в dop_iztochnitsi иска „kratko“ и „palno“")
        return {"kratko": e["kratko"], "palno": e["palno"]}
    k = katalog()
    if kluch in k["iztochnitsi"]:
        return k["iztochnitsi"][kluch]
    prefix = kluch.split(":")[0]
    if prefix == "metar":
        sys.path.insert(0, HERE)
        import vreme
        icao = kluch.split(":", 1)[1].upper() if ":" in kluch else ""
        if icao not in vreme.STANTSII:
            raise Problem(f"UNKNOWN_SOURCE: {kluch} – летището не е в списъка ({', '.join(vreme.STANTSII)})")
        d = {"icao": icao, "ime": vreme.STANTSII[icao][0]}
        return {"kratko": k["_metar"]["kratko"].format(**d), "palno": k["_metar"]["palno"].format(**d)}
    if ":" in kluch and prefix in k["_shabloni"]:
        rows = rows if rows is not None else stoinosti()
        r = next((x for x in rows if x["kluch"] == kluch), None)
        if r is None:
            raise Problem(f"UNKNOWN_SOURCE: {kluch} не е в таблиците – добави го със скрипта в tools/")
        sh = k["_shabloni"][prefix]
        d = {**r, "id": kluch.split(":")[1].upper(), "proveren": _iso(r["proveren"])}
        return {"kratko": sh["kratko"].format(**d), "palno": sh["palno"].format(**d)}
    keys = list(k["iztochnitsi"]) + list(extra or {})
    close = difflib.get_close_matches(kluch, keys, n=3)
    raise Problem(f"UNKNOWN_SOURCE: няма източник „{kluch}“" + (f" – може би {', '.join(close)}?" if close else ""))


def v_teksta(kluch, mesto, extra=None):
    """The part of the place that the document shows. The page or section stays in the marker – the
    check and the chat use it – but the text shows only the author and year; a source may keep a
    short part (Чочев – the appendix) through „mesto_v_teksta“ (a regex) in the catalogue.
    A per-case source (ИЛБ) shows its place as written."""
    if not mesto:
        return ""
    if extra and kluch in extra:
        return mesto
    k = katalog()
    pat = (k["_metar"] if kluch.split(":")[0] == "metar" else k["iztochnitsi"].get(kluch, {})).get("mesto_v_teksta")
    m = re.search(pat, mesto) if pat else None
    return m.group(0) if m else ""


def _krai(lines):
    """';' after every line, '.' after the last one."""
    out = [l.rstrip().rstrip(";").rstrip() for l in lines]
    out = [l + ";" for l in out[:-1]] + ([out[-1] if out[-1].endswith(".") else out[-1] + "."] if out else [])
    return out


def _sravni(s):
    return re.sub(r"[\s„“”\"';.,]+", "", s).lower()


# ---------- number ↔ source check ----------
UNIT_NUM_RE = re.compile(r"(-?\d+(?:[.,]\d+)?)(?=\s*(?:–\s*-?\d+(?:[.,]\d+)?\s*)?(?:°\s*C|°С|°F|kW|kJ|MJ|g/m|μm|% ?\(об|об\. ?%))")
RANGE_RE = re.compile(r"(-?\d+(?:[.,]\d+)?)\s*[–÷-]\s*(-?\d+(?:[.,]\d+)?)(?=\s*(?:°\s*C|°С|°F|kW|kJ|MJ|g/m|μm|%))")
NUM_RE = re.compile(r"\d+(?:[.,]\d+)?")


def _n(x):
    return str(float(x.replace(",", ".").lstrip("-"))).rstrip("0").rstrip(".")


def _chisla(text):
    return {_n(x) for x in NUM_RE.findall(text or "")}


def _stranitsi(mesto):
    """('II', {'с:235', 'с:236'}) from „ч. II, с. 235–236“; sections („т. 4.1.5.1“) and chapters
    („гл. 9“) are places too; „табл. 5“ alone is not a place."""
    part = re.search(r"ч\.\s*(I+)", mesto or "")
    places = set()
    for a, b in re.findall(r"с\.\s*(\d+)(?:\s*[–-]\s*(\d+))?", mesto or ""):
        places |= {f"с:{n}" for n in range(int(a), int(b or a) + 1)}
    for extra_page in re.findall(r"\bи\s+(\d{2,4})\b", mesto or ""):
        places.add(f"с:{extra_page}")
    places |= {f"т:{x}" for x in re.findall(r"т\.\s*(\d+(?:\.\d+)*)", mesto or "")}
    places |= {f"гл:{x}" for x in re.findall(r"гл\.\s*(\d+)", mesto or "")}
    return (part.group(1) if part else ""), places


CHOCHEV_FILE = "Ogneborets_Reference_Chochev"
_chochev = {"loaded": False, "text": None}


def _chochev_tekst():
    """The Чочев tables from the normative base (n8n, personal key), cached for a day; None without
    a key or a network – then numbers cited from Чочев are not checked."""
    if _chochev["loaded"]:
        return _chochev["text"]
    _chochev["loaded"] = True
    if os.environ.get("FIRE_SERVICE_NO_KEY"):
        return None
    import tempfile
    import time
    cache = os.path.join(tempfile.gettempdir(), "fire-service-chochev.md")
    try:
        if os.path.exists(cache) and time.time() - os.path.getmtime(cache) < 86400:
            _chochev["text"] = open(cache, encoding="utf-8").read()
            return _chochev["text"]
        sys.path.insert(0, HERE)
        import api_config
        files = api_config.post("regs_url", {"action": "list"})["files"]
        f = next(x for x in files if CHOCHEV_FILE in (x.get("path") or "") and x["path"].endswith(".md"))
        _chochev["text"] = api_config.post("regs_url", {"action": "download", "id": f["id"]})["content"]
        open(cache, "w", encoding="utf-8").write(_chochev["text"])
    except Exception:  # noqa: BLE001 – no key, no network, no file: the check is skipped, never fails
        _chochev["text"] = None
    return _chochev["text"]


def chochev_prilozheniya(text=None):
    """{appendix number: the numbers in its table} from the Чочев file („## Прил. № N – … – с. X“)."""
    text = text if text is not None else _chochev_tekst()
    if not text:
        return None
    text = re.sub(r"(?<=\d) (?=\d{3}\b)", "", text)  # „1 000“ → „1000“
    text = re.sub(r"^>.*$", "", text, flags=re.M)  # notes under a table are not the book's numbers
    out = {}
    for m in re.finditer(r"^## Прил\. № (\d+)[^\n]*\n(.*?)(?=^## |\Z)", text, re.S | re.M):
        out[m.group(1)] = _chisla(m.group(2))
    return out


def _metar_chisla(icao, mesto):
    """The temperatures, winds and humidities the airport reported in the window of the place
    („04.08.2026, 16:00–19:00 ч.“); None offline – then the weather is not checked."""
    if os.environ.get("FIRE_SERVICE_OFFLINE") or os.environ.get("FIRE_SERVICE_NO_KEY"):
        return None
    sys.path.insert(0, HERE)
    import vreme
    dni, ot, do = vreme.ot_mesto(mesto)
    if not dni or icao.upper() not in vreme.STANTSII:
        return None
    out = set()
    try:
        for den in dni:
            obs, _ = vreme.svali(icao.upper(), den)
            out |= vreme.chisla(vreme.prozorets(obs, ot, do) if len(dni) == 1 else obs)
    except Exception:  # noqa: BLE001 – no network: the check is skipped, never fails
        return None
    return out or None


def danni_za(kluch, mesto, rows):
    """The numbers the source gives at that place, or None when the plugin has no data for it."""
    if kluch == "chochev":
        pril = re.search(r"прил\.\s*№\s*(\d+)", mesto or "")
        tables = chochev_prilozheniya() if pril else None
        if not tables or pril.group(1) not in tables:
            return None
        return tables[pril.group(1)]
    if kluch.split(":")[0] == "metar":
        return _metar_chisla(kluch.split(":", 1)[1], mesto)
    if kluch.split(":")[0] in ("icsc", "chris", "gestis-staub"):
        r = next((x for x in rows if x["kluch"] == kluch), None)
        if r is None:
            return None
        return _chisla(" ".join(v for k, v in r.items() if k not in ("kluch", "url", "proveren", "cas", "sinonimi",
                                                                       "karta_versiya", "ime", "ime_en")))
    part, pages = _stranitsi(mesto)
    found = [r for r in rows if r.get("vid") == "литература" and r["iztochnik"] == kluch]
    if not found:
        return None
    hit = [r for r in found if (lambda rp: (not part or rp[0] == part) and (not pages or rp[1] & pages))(_stranitsi(r["mesto"]))]
    if not hit:
        return set()
    return set().union(*(_chisla(r["stoinost"] + " " + r["usloviya"]) for r in hit))


def proveri_chisla(text, extra=None):
    """The value with a unit right before a [[…]] marker, when the cited place does not give it.
    Sources without data in the plugin (Чочев, Симеонов, a per-case ИЛБ) are not checked."""
    rows = stoinosti()
    problems, start = [], 0
    for m in MARKER_RE.finditer(text):
        before = text[start:m.start()]
        cut = max(before.rfind(". "), before.rfind("\n"), before.rfind("; "))
        clause = before[cut + 1:] if cut >= 0 else before
        clause = re.sub(r"(?<=\d)[ \u00a0\u202f](?=\d{3}\b)", "", clause)  # „1 000“ → „1000“
        start = m.end()
        # only the value right before the marker is checked – the marker stands right after the
        # number it proves; other numbers in the clause may come from the case or a calculation
        found = list(re.finditer(r"(-?\d+(?:[.,]\d+)?)(?:\s*[–÷-]\s*(-?\d+(?:[.,]\d+)?))?\s*"
                                 r"(?:°\s*C|°С|°F|kW|kJ|MJ|g/m|μm|m/s|% ?\(об|об\. ?%)", clause))
        if not found:
            continue
        # a weather clause is all from the airport – every value in it is checked
        items = [ITEM_RE.match(i) for i in m.group(1).split(";")]
        vreme_samo = all(i and i.group(1).startswith("metar:") for i in items)
        nums = {_n(x) for mm in (found if vreme_samo else found[-1:]) for x in mm.groups() if x}
        data, checked = set(), False
        for item in m.group(1).split(";"):
            im = ITEM_RE.match(item)
            if not im:
                continue
            gr = next((g for g in katalog()["iztochnitsi"].get(im.group(1), {}).get("greshki", [])
                       if g["duma"] in clause.lower()), None)
            if gr:
                problems.append(f"„{clause.strip()[-90:]}“ → [[{m.group(1)}]]: {gr['belezhka']} – не се цитира "
                                f"оттам; вярната стойност е {gr['pravilno']}")
                continue
            if extra and im.group(1) in extra:
                # a per-case source (ИЛБ) is checked against the values copied from it, if given
                d = _chisla(extra[im.group(1)].get("stoinosti")) if extra[im.group(1)].get("stoinosti") else None
            else:
                d = danni_za(im.group(1), im.group(2), rows)
            if d is not None:
                data |= d
                checked = True
        if checked and nums - data:
            problems.append(f"„{clause.strip()[-90:]}“ → [[{m.group(1)}]]: "
                            f"{', '.join(sorted(nums - data))} го няма на посоченото място")
    return problems


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
            shown = src["kratko"] + (f", {v_teksta(kluch, mesto, extra)}" if v_teksta(kluch, mesto, extra) else "")
            if shown not in parts:
                parts.append(shown)
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
    for m in HAND_RE.finditer(out):
        key = ("icsc:" + m.group(1) if m.group(1) else "chris:" + m.group(2).lower() if m.group(2)
               else "gestis-staub:" + m.group(3))
        if key not in first:
            if not any(r["kluch"] == key for r in rows):
                raise Problem(f"UNKNOWN_SOURCE: в текста има „{m.group(0)}“, а го няма в таблиците")
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
    for s in re.split(r"(?<=[.!?])\s+|\n+", text):
        if re.search(r"\d\s*(?:°\s*C|°С|kW|kJ|MJ|% ?\(об\.\)|об\. ?%|g/m)", s) and "[[" not in s:
            out.append(s.strip())
    return out


# ---------- CLI ----------
def pokazhi(r, extra=None):
    f = formatirai(r)
    if r["vid"] == "литература":
        src = iztochnik(r["iztochnik"], extra)
        return "\n".join([f"{r['ime']} – {r['pokazatel']}: {r['stoinost']}",
                          f"  Условия: {r['usloviya']}",
                          f"  Позоваване в текста: ({src['kratko']})   място (за проверка): {r['mesto']}",
                          f"  Маркер в ЕПТЗ: {marker(r)}",
                          f"  Литература: {src['palno']}"])
    src = iztochnik(r["kluch"], extra)
    head = f"{r['ime']} – {r['ime_en']}" + (f", CAS {r['cas']}" if r.get("cas") else "")
    lines = [head]
    for k, label in (LABELS_PRAH if r["vid"] == "прах" else LABELS):
        if k == "proba" and k not in f:
            continue
        lines.append(f"  {label}: {f.get(k, '—')}")
    lines.append(f"  Позоваване в текста: ({src['kratko']})   маркер в ЕПТЗ: {marker(r)}")
    lines.append(f"  Литература: {src['palno']}")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="Пожароопасни свойства на веществата с източника им")
    ap.add_argument("ime", nargs="?", help="вещество или материал – име, синоним, CAS, номер или код на карта/запис")
    ap.add_argument("--spisak", action="store_true", help="всичко в таблиците")
    ap.add_argument("--iztochnitsi", action="store_true", help="ключовете на източниците за [[…]]")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    try:
        if a.iztochnitsi:
            k = katalog()
            for key, v in k["iztochnitsi"].items():
                print(f"{key:26} ({v['kratko']}){'  – винаги в литературата' if v.get('vinagi') else ''}")
                print(f"{'':26} {v['v_skila']}")
            for p, sh in k["_shabloni"].items():
                print(f"{p + ':…':26} ({sh['kratko'].format(id='…')}) – {sh['v_skila']}")
            return
        rows = stoinosti()
        if a.spisak:
            for r in rows:
                print(f"{r['kluch']:20} {r['ime']} [{r['vid']}] ({r['sinonimi'].replace(';', ', ')})")
            return
        if not a.ime:
            ap.error("кажи вещество, --spisak или --iztochnitsi")
        found = tarsi(a.ime, rows)
        if a.json:
            print(json.dumps([{**r, "tekst": formatirai(r), "marker": marker(r),
                               "citat": iztochnik(r["iztochnik"] if r["vid"] == "литература" else r["kluch"])}
                              for r in found],
                             ensure_ascii=False, indent=1))
        else:
            print("\n\n".join(pokazhi(r) for r in found))
    except Problem as e:
        print(e, file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
