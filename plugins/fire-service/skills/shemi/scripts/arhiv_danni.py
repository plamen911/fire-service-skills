#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
arhiv_danni.py — данните за обекта от стария му оперативен план в архива („_Архив оперативни планове“,
_shared/arhiv.md), за да не се питат: етажност, степен на огнеустойчивост, главното ел. табло, газ, водопровод и
хидранти, пожарогасителни и пожароизвестителни инсталации. Чете само характеристиката на обекта (.md) от неговата
папка – PDF не се тегли.

    python3 scripts/arhiv_danni.py "Драматично-куклен театър „Иван Радоев“" [--adres "ул. „Васил Левски“ 155"]

Отпечатва JSON {"namereno": bool, "papka", "godina", "iztochnik": "по план от 2007 г.", "danni": {…}, "izrecheniya": {…}}.
"danni" може да има: etazhi (int), ogneustoychivost ("I"…"V"), el_tablo (изречението), gaz ("да"/"не" + изречението),
vodoprovod_mm (int), natisk_atm (число), hidranti (брой), vpk (брой), vodoem_m3, apii (True), sprinkler (True),
vodna_zavesa (True). Каквото текстът не казва ясно – липсва; нищо не се измисля.

Правилата за ползването (_shared/arhiv.md): архивът попълва само липсващото, КАИС и одобрените образци са с предимство,
всяка данна носи годината на плана, а план отпреди 2010 г. е ориентир – „да се провери на място“.
"""
import argparse
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OBEKTI = None
for _p in (os.path.join(os.path.dirname(HERE), "_shared", "scripts", "obekti.py"),
           os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(HERE))), "shared", "scripts", "obekti.py")):
    if os.path.exists(_p):
        OBEKTI = _p
        break

ROMAN = {"I": "I", "II": "II", "III": "III", "IV": "IV", "V": "V"}
SLOVOM = {"едно": 1, "една": 1, "дву": 2, "дво": 2, "два": 2, "три": 3, "четири": 4, "пет": 5, "шест": 6,
          "седем": 7, "осем": 8, "девет": 9, "десет": 10}
GENERIC = {"театър", "магазин", "сграда", "склад", "обект", "фирма", "ул", "бул", "гр", "плевен", "ет", "еоод", "оод",
           "ад", "ет.", "център", "детска", "градина", "училище", "на", "и", "за", "в"}


def run_obekti(*args):
    if not OBEKTI:
        return None
    try:
        r = subprocess.run([sys.executable, OBEKTI, *args], capture_output=True, text=True, timeout=180)
        return json.loads(r.stdout) if r.returncode == 0 else None
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return None


def clean(text):
    """Markdown от стария .doc – без получер, span-ове и празни редове; латинските І/V от кирилица – латински."""
    t = re.sub(r"<[^>]+>", " ", text)
    t = t.replace("**", " ").replace("\\", " ")
    t = t.replace("І", "I")
    return re.sub(r"[ \t]+", " ", t)


def sentences(text):
    # „ел. табло“, „бр. ПХ“ – точка в средата на изречението; ново изречение – след точка и главна буква
    return [s.strip() for s in re.split(r"(?<=[.;])\s+(?=[А-ЯA-Z0-9„\"])|\n+", text) if s.strip()]


def extract(text):
    """Данните от текста на характеристиката – само това, което е казано ясно."""
    t = clean(text)
    low = t.lower()
    out, why = {}, {}
    m = re.search(r"(\d+|едно|една|дву|дво|два|три|четири|пет|шест|седем|осем|девет|десет)\s*-?\s*етажн", low)
    if m:
        v = m.group(1)
        out["etazhi"] = int(v) if v.isdigit() else SLOVOM.get(v)
    m = re.search(r"\b(I{1,3}|IV|V)\b\s*[-–]?\s*(?:-?[а-я]{1,3}\.?)?\s*степен\s+(?:на\s+)?(?:пожаро|огне)устойчивост", t,
                  re.I)
    if m and m.group(1).upper() in ROMAN:
        out["ogneustoychivost"] = ROMAN[m.group(1).upper()]
    for s in sentences(t):
        sl = s.lower()
        if "el_tablo" not in out and re.search(r"ел(?:\.|ектрическ\w*)\s*табл", sl) and re.search(r"намира|разположен|е в|се помещава|до ", sl):
            out["el_tablo"] = s
        if "gaz" not in out and re.search(r"газифицир|природен газ|пропан|газово отопление|газов котел", sl):
            out["gaz"] = "не" if re.search(r"не е газифицир|няма газ|не се използва газ", sl) else "да"
            why["gaz"] = s
    m = re.search(r"водопровод\w*\s*(?:с\s*)?(?:ф|ø|Ф|диаметър)\s*(\d{2,3})", t)
    if m:
        out["vodoprovod_mm"] = int(m.group(1))
    m = re.search(r"(\d{1,2})\s*бр\.?\s*(?:ПХ|пожарни хидранти|хидранти)", t)
    if m:
        out["hidranti"] = int(m.group(1))
    m = re.search(r"(\d{1,3})\s*бр\.?\s*вътрешни\s*пожарни\s*кранове", low)
    if m:
        out["vpk"] = int(m.group(1))
    m = re.search(r"водоем\s*[–-]?\s*(\d+(?:[.,]\d+)?)\s*(?:куб|m3|м3)", low)
    if m:
        out["vodoem_m3"] = float(m.group(1).replace(",", "."))
    if re.search(r"\bАПИИ\b|пожароизвестител", t):
        out["apii"] = True
    if re.search(r"спринклер", low):
        out["sprinkler"] = not re.search(r"(няма|без)\s+спринклер", low)
    if re.search(r"водна\w*\s+завес|дренчер", low):
        out["vodna_zavesa"] = True
    return {k: v for k, v in out.items() if v is not None}, why


FORMI = (("секторн", "sektor"), ("кръгов", "kragova"), ("правоъгълн", "pravoagalnik"), ("ъглов", "aglova"))


def num(v):
    return float(v.replace(",", ".")) if v else None


def variants(text):
    """Вариантите от разчета на стария план: [{"ime", "priemam", "vl_m_min", "i_l_s_m2", "forma", "ataka",
    "a_m", "b_m", "h_m"}] – по един за всеки „Разчет на силите … – <помещение>“; каквото не е казано – липсва."""
    t = clean(re.sub(r"\\text\{([^}]*)\}", r"\1", text))   # LaTeX от формулите – само числата
    parts = re.split(r"(?=Разчет на силите)", t)
    out = []
    for p_ in parts:
        m = re.match(r"Разчет на силите[^\n]*?–\s*([^\n–]+?)\s*$", p_.split("\n")[0].strip())
        if not m:
            continue
        v = {"ime": m.group(1).strip(" ”\"")}
        low = p_.lower()
        if (m2 := re.search(r"(Приемам[^.\n]*)", p_)):
            v["priemam"] = m2.group(1).strip(" *")
        if (m2 := re.search(r"V\s*(?:<sub>)?\s*л\s*(?:</sub>)?\s*=\s*(\d+(?:[.,]\d+)?)", p_)):
            v["vl_m_min"] = num(m2.group(1))
        if (m2 := re.search(r"J\s*(?:<sub>)?\s*н\s*(?:</sub>)?.{0,30}?=\s*(\d+(?:[.,]\d+)?)\s*л", p_)):
            v["i_l_s_m2"] = num(m2.group(1))
        v["forma"] = next((f for k, f in FORMI if k in low), None)
        v["ataka"] = "perimetar" if "по периметър" in low else "front" if "по фронт" in low else None
        if (m2 := re.search(r"2\s*\.\s*(\d+(?:,\d+)?)\s*\.\s*\(\s*(\d+(?:,\d+)?)\s*\+\s*(\d+(?:,\d+)?)\s*-\s*2", p_)):
            v["h_m"], v["a_m"], v["b_m"] = num(m2.group(1)), num(m2.group(2)), num(m2.group(3))
        out.append({k: x for k, x in v.items() if x is not None})
    # един вариант, казан в няколко файла (стара и нова редакция) – веднъж, последната дума
    seen = {}
    for v in out:
        key = v["ime"].split("–")[-1].strip().lower()
        seen[key] = {**seen.get(key, {}), **v}
    return list(seen.values())


def keywords(name):
    """Думите, по които се търси в индекса: името в кавичките („Иван Радоев“), иначе нетипичните думи."""
    q = re.findall(r"[„\"“]([^“”\"]+)[“”\"]", name or "")
    words = re.findall(r"[\w\-]+", q[0] if q else name or "")
    words = [w for w in words if w.lower() not in GENERIC and len(w) > 2]
    return words[-1:] if q and words else words[:2]


def lookup(name, adres=""):
    """Папката на обекта в архива и данните от характеристиката му; {"namereno": False} – нищо сигурно."""
    # only by the name: an address finds other objects on a street of the same name, and takes minutes
    for words in (keywords(name),):
        if not words:
            continue
        found = run_obekti("arhiv", " ".join(words))
        rows = [r for r in (found or {}).get("redove") or [] if r.get("grupa") == "Оперативни планове"]
        if len(rows) == 1:
            row = rows[0]
            break
    else:
        return {"namereno": False}
    listing = run_obekti("arhiv", "--papka", row["papka"]) or {}
    texts = [f["name"] for f in listing.get("failove") or [] if f["name"].lower().endswith(".md")]
    texts.sort(key=lambda n: (0 if "harak" in n.lower() else 1 if "main" in n.lower() or "pz" in n.lower() else 2))
    danni, izr = {}, {}
    varianti = []
    for name_ in [n_ for n_ in texts if re.search(r"raz[4c]h?et", n_, re.I)][:3]:
        r = run_obekti("arhiv", "--papka", row["papka"], "--chete", name_) or {}
        for v in variants(r.get("tekst") or ""):
            if not any(v["ime"].lower() == w["ime"].lower() for w in varianti):
                varianti.append(v)
    pdfs = [f["name"] for f in listing.get("failove") or [] if f["name"].lower().endswith(".pdf")]
    for name_ in [n_ for n_ in texts if not re.search(r"raz[4c]h?et", n_, re.I)][:3]:
        r = run_obekti("arhiv", "--papka", row["papka"], "--chete", name_) or {}
        d_, w_ = extract(r.get("tekst") or "")
        for k, v in d_.items():
            danni.setdefault(k, v)
        for k, v in w_.items():
            izr.setdefault(k, v)
        if "etazhi" in danni and "el_tablo" in danni:
            break
    god = re.search(r"\d{4}", str(row.get("godina") or ""))
    godina = int(god.group(0)) if god else None
    return {"namereno": bool(danni or varianti), "papka": row["papka"], "obekt": row.get("obekt"), "godina": godina,
            "iztochnik": f"по план от {godina} г." if godina else "по стария план",
            "star": bool(godina and godina < 2010), "danni": danni, "izrecheniya": izr,
            "varianti": varianti, "skhemi_pdf": pdfs}


def main():
    ap = argparse.ArgumentParser(description="Данните за обекта от стария му оперативен план")
    ap.add_argument("ime", help="името на обекта")
    ap.add_argument("--adres", default="")
    a = ap.parse_args()
    print(json.dumps(lookup(a.ime, a.adres), ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
