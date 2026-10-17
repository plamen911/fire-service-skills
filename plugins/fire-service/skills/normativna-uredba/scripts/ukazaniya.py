#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ukazaniya.py — „Указания и разяснения“: писма и указания на ГДПБЗН, МВР и дирекцията, които отговарят
на практически въпрос („може ли пожарникарите да бъдат задължавани да пренасят починали при
съдействие на ЦСМП“), записани в нормативната база (tier-c), така че normativna-uredba да ги намира.

Преди запис се проверява, че указанието не е вече в базата (дубликат) и дали не е заменено от
по-ново по същия въпрос – или то заменя по-старо.

    python3 scripts/ukazaniya.py podgotvi data.json -o ukaz             # → ukaz/GDPBZN_Ukazanie_….md
    python3 scripts/ukazaniya.py kandidati ukaz/НОВО.md [--listing listing.json]
    python3 scripts/ukazaniya.py sravni ukaz/НОВО.md regs/tier-c/СТАРО.md …
    python3 scripts/ukazaniya.py zameni regs/tier-c/СТАРО.md --s tier-c/НОВО.md -o ukaz
    python3 scripts/ukazaniya.py zapis ukaz/НОВО.md                       # само администраторът

data.json:
{
  "izdatel": "ГДПБЗН",                 // ГДПБЗН | МВР | РДПБЗН – Плевен | … – кой е издал документа
  "vid": "писмо",                      // писмо | указание | разяснение | заповед | становище
  "reg_no": "1234р-56789",
  "data": "2026-10-15",                // датата на документа
  "tema": "Пренасяне на починали лица при съдействие на ЦСМП и полицията",   // до ~10 думи
  "vapros": "Може ли служителите да бъдат задължавани да пренасят починали лица?",
  "otgovor": "Кратко какво казва документът – с неговите думи, без тълкуване.",
  "tekst": "Дословният текст на писмото (или на относимата част).",
  "akt": "Наредба № 8121з-… – кой акт урежда темата, ако документът го казва",
  "keywords": ["починали", "ЦСМП", "съдействие"],
  "iztochnik": "служебната поща – копие, предоставено от администратора"
}

kandidati без --listing чете списъка на базата през n8n (личен ключ); с конектора – запиши
отговора на regs_list във файл и го подай с --listing.
sravni връща решение: "zapishi" (ново), "dublikat" (вече е в базата – не се записва),
"zapishi_i_zameni" (новото заменя изброените по-стари – за всяко zameni), "po_staro" (в базата има
по-ново по същия въпрос – новото е по-старо; питай дали изобщо да се записва).
"""
import argparse
import datetime
import difflib
import json
import os
import re
import sys
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "_shared", "scripts"))

FOLDER = "tier-c"
TYPE = "Ukazanie"
ZEN_FOLDER = "указания-и-писма"
ISSUERS = {"гдпбзн": "GDPBZN", "мвр": "MVR", "рдпбзн": "RDPBZN-Pleven", "одмвр": "ODMVR", "мс": "MS",
           "министерски съвет": "MS", "цсмп": "TsSMP", "прокуратура": "Prokuratura"}
TR = dict(zip("абвгдежзийклмнопрстуфхцчшщъьюя",
              ["a", "b", "v", "g", "d", "e", "zh", "z", "i", "y", "k", "l", "m", "n", "o", "p", "r", "s", "t", "u",
               "f", "h", "ts", "ch", "sh", "sht", "a", "y", "yu", "ya"]))
STOP = set("на за от по при и в във с със да се не че е са към до като или но а ли на-".split())


def out(obj):
    print(json.dumps(obj, ensure_ascii=False, indent=2))


def fail(msg, code="BAD_INPUT"):
    out({"ok": False, "error": f"{code}: {msg}"})
    sys.exit(1)


def translit(text):
    res = []
    for ch in text:
        low = ch.lower()
        if low in TR:
            t = TR[low]
            res.append(t.capitalize() if ch != low else t)
        else:
            res.append(ch)
    return "".join(res)


def slug(text, words=6):
    t = translit(re.sub(r"[„“”\"'«»()]", "", text))
    parts = [p for p in re.split(r"[^A-Za-z0-9]+", t) if p and p.lower() not in {translit(s) for s in STOP}]
    return "-".join(p[:1].upper() + p[1:] for p in parts[:words])


def words_of(text):
    t = unicodedata.normalize("NFC", text or "").lower()
    return {w for w in re.findall(r"[а-яa-z0-9]{3,}", t) if w not in STOP}


def stem(w):
    return w[:6]


def norm_reg(value):
    return re.sub(r"\s+", "", str(value or "")).replace("№", "").lower()


def parse_date(value):
    if not value:
        return None
    s = str(value).strip().rstrip(".").replace("г", "").strip().rstrip(".").strip()
    for fmt in ("%Y-%m-%d", "%d.%m.%Y"):
        try:
            return datetime.datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    fail(f"„{value}“ не е дата (ГГГГ-ММ-ДД или ДД.ММ.ГГГГ)")


def typo(text):
    t = re.sub(r"№\s*(?=\S)", "№ ", text or "")
    return re.sub(r"\s+[-—]\s+", " – ", t).strip()


def yaml_str(value):
    return json.dumps(str(value), ensure_ascii=False)   # a JSON string is a valid YAML scalar


# ── front matter ────────────────────────────────────────────────────────────

def split(text):
    m = re.match(r"^---\n(.*?)\n---\n?", text, re.S)
    if not m:
        return {}, text
    fm = {}
    try:
        import yaml
        fm = yaml.safe_load(m.group(1)) or {}
    except Exception:  # noqa: BLE001 – without PyYAML: the simple "key: value" lines are enough here
        for line in m.group(1).splitlines():
            km = re.match(r"^([a-z_]+):\s*(.*)$", line)
            if km:
                v = km.group(2).strip()
                if v.startswith("["):
                    try:
                        v = json.loads(v)
                    except ValueError:
                        pass
                elif v.startswith('"'):
                    try:
                        v = json.loads(v)
                    except ValueError:
                        v = v.strip('"')
                fm[km.group(1)] = v
    return fm, text[m.end():]


def set_fields(text, fields):
    """Replaces or adds top-level "key: value" lines in the front matter, keeps everything else."""
    m = re.match(r"^---\n(.*?)\n---\n?", text, re.S)
    if not m:
        fail("файлът няма front matter")
    lines = m.group(1).split("\n")
    for key, value in fields.items():
        line = f"{key}: {yaml_str(value)}"
        idx = next((i for i, l in enumerate(lines) if re.match(rf"^{key}:", l)), None)
        if idx is None:
            lines.append(line)
        else:
            end = idx + 1
            while end < len(lines) and re.match(r"^\s+\S|^\s*-\s", lines[end]):   # a multi-line value
                end += 1
            lines[idx:end] = [line]
    return "---\n" + "\n".join(lines) + "\n---\n" + text[m.end():]


# ── commands ────────────────────────────────────────────────────────────────

def cmd_podgotvi(a):
    try:
        d = json.load(open(a.data, encoding="utf-8"))
    except (OSError, ValueError) as e:
        fail(f"{a.data}: {e}")
    d = {k: (typo(v) if isinstance(v, str) else v) for k, v in d.items()}
    missing = [k for k in ("izdatel", "vid", "data", "tema", "vapros", "otgovor", "tekst") if not d.get(k)]
    if missing:
        fail("липсват полета: " + ", ".join(missing))
    date = parse_date(d["data"])
    issuer = next((v for k, v in ISSUERS.items() if d["izdatel"].lower().startswith(k)), slug(d["izdatel"], 2) or "UNKNOWN")
    reg = d.get("reg_no", "")
    topic = "-".join(x for x in (slug(reg, 3) if reg else "", slug(d["tema"])) if x)
    name = f"{issuer}_{TYPE}_{topic}_{date:%Y-%m}.md"
    kw = list(dict.fromkeys([k for k in d.get("keywords", []) if k] + ["указание", "разяснение"]))
    title = f"{d['vid'][:1].upper()}{d['vid'][1:]} на {d['izdatel']}" + (f" рег. № {reg}" if reg else "") + \
            f" от {date:%d.%m.%Y} г. – {d['tema']}"
    fm = [
        "---",
        f"title: {yaml_str(title[:300])}",
        "tier: C",
        f"issuer: {yaml_str(d['izdatel'])}",
        f"act_type: {yaml_str(d['vid'] + ' (указание по прилагането – не е нормативен акт)')}",
        "in_force: непроверен",
        f"in_force_note: {yaml_str('в сила, докато не бъде заменено с по-ново указание по същия въпрос; актуалността е проверена при записа ' + datetime.date.today().strftime('%d.%m.%Y') + ' г. срещу записаните в базата указания')}",
        f"text_source: {yaml_str(d.get('iztochnik') or 'копие от служебната поща, разчетено от потребителя')}",
        f"keywords: {json.dumps(kw, ensure_ascii=False)}",
        f"subject: {yaml_str(d['vapros'])}",
        f"edition_date: {date:%Y-%m-%d}",
        f"reg_no: {yaml_str(reg)}",
        "---",
    ]
    body = [
        "",
        "> ТОВА НЕ Е НОРМАТИВЕН АКТ. Указание или разяснение по прилагането, записано за справка."
        + (f" Темата се урежда от: {d['akt']}." if d.get("akt") else "")
        + " При цитиране – като писмо с номера и датата му, не като уредба.",
        "",
        f"# {title}",
        "",
        "## Въпрос",
        "",
        d["vapros"],
        "",
        "## Какво казва документът",
        "",
        d["otgovor"],
        "",
        "## Текст",
        "",
        d["tekst"],
        "",
    ]
    os.makedirs(a.out, exist_ok=True)
    path = os.path.join(a.out, name)
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write("\n".join(fm + body))
    words = len(re.findall(r"\w+", "\n".join(body)))
    out({"ok": True, "file": path, "name": name, "path": f"{FOLDER}/{name}", "dumi": words,
         **({"preduprezhdenie": "текстът е под 30 думи – базата не държи файл без текст; добави дословния текст"} if words < 30 else {})})
    return 0


def load(path):
    try:
        text = open(path, encoding="utf-8").read()
    except OSError as e:
        fail(f"{path}: {e}")
    fm, body = split(text)
    return {"path": path, "fm": fm, "body": body, "text": text}


def date_of(doc):
    fm = doc["fm"]
    v = fm.get("edition_date")
    if isinstance(v, datetime.date):
        return v
    if v and re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(v)):
        return datetime.date.fromisoformat(str(v))
    m = re.search(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", str(fm.get("title", "")) + doc["body"][:600])
    return datetime.date(int(m.group(3)), int(m.group(2)), int(m.group(1))) if m else None


def reg_of(doc):
    r = doc["fm"].get("reg_no")
    if r:
        return norm_reg(r)
    m = re.search(r"рег\.?\s*№\s*([0-9]{2,6}[а-яa-z]?-[0-9]+)", doc["text"], re.I)
    return norm_reg(m.group(1)) if m else ""


def body_text(doc):
    t = doc["body"]
    m = re.search(r"^## Текст\s*$", t, re.M)
    return re.sub(r"\s+", " ", (t[m.end():] if m else t)).strip().lower()


def topic_words(doc):
    fm = doc["fm"]
    kws = fm.get("keywords") or []
    base = " ".join([str(fm.get("subject", "")), str(fm.get("title", ""))] + [str(k) for k in kws])
    if not fm:
        base = doc["body"][:1500]
    return {stem(w) for w in words_of(base)} - {"указан", "разясн", "писмо", "гдпбзн"}


def compare(new, old):
    rn, ro = reg_of(new), reg_of(old)
    if rn and ro and rn == ro:
        return "dublikat", "същият регистрационен номер"
    sim = difflib.SequenceMatcher(None, body_text(new)[:6000], body_text(old)[:6000]).ratio()
    if sim >= 0.85:
        return "dublikat", f"текстът съвпада на {sim:.0%}"
    tn, to = topic_words(new), topic_words(old)
    overlap = len(tn & to) / max(1, min(len(tn), len(to)))
    if overlap >= 0.5:
        dn, do = date_of(new), date_of(old)
        if dn and do:
            if dn > do:
                return "po_novo", f"същият въпрос ({overlap:.0%} общи думи), новото е от {dn:%d.%m.%Y}, старото от {do:%d.%m.%Y}"
            if dn < do:
                return "po_staro", f"същият въпрос ({overlap:.0%} общи думи), в базата има по-ново – от {do:%d.%m.%Y}"
        return "sashta_tema", f"същият въпрос ({overlap:.0%} общи думи), датите не дават кое е по-ново"
    return "razlichno", f"{overlap:.0%} общи думи"


def cmd_sravni(a):
    new = load(a.novo)
    rows, decision, zameni = [], "zapishi", []
    for p in a.kandidati:
        old = load(p)
        verdict, why = compare(new, old)
        if old["fm"].get("in_force") == "не" and verdict in ("po_novo", "po_staro", "sashta_tema"):
            why += "; то вече е заменено"
        rows.append({"file": p, "zaklyuchenie": verdict, "zashto": why,
                     "superseded_by": old["fm"].get("superseded_by")})
    verdicts = [r["zaklyuchenie"] for r in rows]
    if "dublikat" in verdicts:
        decision = "dublikat"
    elif "po_staro" in verdicts and not any(r["zaklyuchenie"] == "po_staro" and r["superseded_by"] for r in rows):
        decision = "po_staro"
    elif "po_novo" in verdicts:
        decision = "zapishi_i_zameni"
        zameni = [r["file"] for r in rows if r["zaklyuchenie"] == "po_novo" and not r["superseded_by"]]
        if not zameni:
            decision = "zapishi"
    if "sashta_tema" in verdicts and decision == "zapishi":
        decision = "provera"
    out({"ok": True, "reshenie": decision, "zameni": zameni, "kandidati": rows,
         "obyasnenie": {"zapishi": "няма такова указание в базата – записва се",
                        "dublikat": "вече е в базата – не се записва",
                        "zapishi_i_zameni": "записва се, а изброените по-стари се отбелязват като заменени (zameni)",
                        "po_staro": "в базата има по-ново указание по същия въпрос – питай дали изобщо да се записва",
                        "provera": "по същия въпрос има указание без ясна дата – прочети двете и питай"}[decision]})
    return 0


def listing_from(path):
    if path:
        try:
            data = json.load(open(path, encoding="utf-8"))
        except (OSError, ValueError) as e:
            fail(f"{path}: {e}")
        return data.get("files", data) if isinstance(data, dict) else data
    try:
        import api_config
        res = api_config.post("regs_url", {"action": "list"})
    except SystemExit:
        raise
    except Exception as e:  # noqa: BLE001
        fail(f"{type(e).__name__}: {e}"[:300], "N8N_UNAVAILABLE")
    return res.get("files", [])


def cmd_kandidati(a):
    if not a.listing:
        import api_config
        if not api_config.has_key():
            fail("няма личен ключ – с конектора запиши отговора на regs_list във файл и го подай с --listing", "NO_KEY")
    new = load(a.novo)
    tn = topic_words(new)
    rn = reg_of(new)
    files = listing_from(a.listing)
    scored = []
    for f in files:
        path = f.get("path") or f.get("name") or ""
        folder = path.split("/")[0] if "/" in path else ""
        if folder not in (FOLDER, ZEN_FOLDER) or not path.endswith((".md", ".txt")):
            continue
        name = os.path.basename(path)
        if path == new["fm"].get("path"):
            continue
        name_words = {stem(w) for w in words_of(translit(name).replace("-", " ").replace("_", " ").lower())}
        tn_lat = {stem(translit(w).lower()) for w in tn}
        reg_hit = bool(rn) and translit(rn).replace("-", "") in translit(name).lower().replace("-", "")
        score = (1.0 if reg_hit else 0) + len(tn_lat & name_words) / max(1, len(tn_lat))
        if folder == ZEN_FOLDER or f"_{TYPE}_" in name:
            score += 0.15
        if score >= a.prag:
            scored.append({"path": path, "id": f.get("id"), "score": round(score, 2)})
    scored.sort(key=lambda r: -r["score"])
    out({"ok": True, "kandidati": scored[:a.broi],
         "sledva": "свали всеки с regs.py get ПЪТ (с конектора – regs_read) и ги подай на sravni"})
    return 0


def cmd_zameni(a):
    old = load(a.staro)
    new_path = a.s
    note = f"заменено от {new_path}" + (f" ({a.belezhka})" if a.belezhka else "")
    text = set_fields(old["text"], {"in_force": "не", "superseded_by": new_path, "in_force_note": note})
    os.makedirs(a.out, exist_ok=True)
    path = os.path.join(a.out, os.path.basename(a.staro))
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(text)
    folder = os.path.basename(os.path.dirname(os.path.abspath(a.staro)))
    out({"ok": True, "file": path, "path": f"{folder}/{os.path.basename(a.staro)}",
         "zapis": "tier-c → zapis ФАЙЛ; указание от папката на Zen остава там – отбележи го само в чата"
         if folder != FOLDER else "zapis ФАЙЛ (същото име – файлът в базата се заменя на място)"})
    return 0


def cmd_zapis(a):
    import hashlib
    import api_config
    text = open(a.file, encoding="utf-8").read()
    fm, body = split(text)
    if str(fm.get("tier", "")) != "C":
        fail("записват се само файлове с tier: C")
    if len(re.findall(r"\w+", body)) < 30:
        fail("тялото е под 30 думи – добави дословния текст")
    name = os.path.basename(a.file)
    try:
        res = api_config.post("samples_url", {"action": "put", "kind": "regs-c", "name": name, "text": text,
                                              "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest()}, timeout=120)
    except SystemExit:
        raise
    except Exception as e:  # noqa: BLE001
        msg = str(e)
        if "403" in msg or "FORBIDDEN" in msg:
            fail("само администраторът записва в нормативната база", "FORBIDDEN")
        fail(f"{type(e).__name__}: {e}"[:300], "N8N_UNAVAILABLE")
    out({"ok": True, "path": f"{FOLDER}/{name}", "link": (res or {}).get("link"),
         "belezhka": "index.json се обновява при следващия kb_lint.py --catalog; дотогава указанието се намира с "
                     "regs.py list --folder tier-c --name Ukazanie"})
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="Указания и разяснения в нормативната база")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("podgotvi"); p.add_argument("data"); p.add_argument("-o", "--out", default="ukaz")
    p.set_defaults(fn=cmd_podgotvi)
    p = sub.add_parser("kandidati"); p.add_argument("novo"); p.add_argument("--listing")
    p.add_argument("--broi", type=int, default=8); p.add_argument("--prag", type=float, default=0.3)
    p.set_defaults(fn=cmd_kandidati)
    p = sub.add_parser("sravni"); p.add_argument("novo"); p.add_argument("kandidati", nargs="*")
    p.set_defaults(fn=cmd_sravni)
    p = sub.add_parser("zameni"); p.add_argument("staro"); p.add_argument("--s", required=True, help="пътят на новото в базата")
    p.add_argument("--belezhka", default=""); p.add_argument("-o", "--out", default="ukaz")
    p.set_defaults(fn=cmd_zameni)
    p = sub.add_parser("zapis"); p.add_argument("file")
    p.set_defaults(fn=cmd_zapis)
    a = ap.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
