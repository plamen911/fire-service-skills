#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
obekti.py — регистърът на обектите: всеки обект има своя папка в Google Drive (fire-service/Обекти)
с всичко за него – ситуационна схема, оперативна картичка, схеми за ПТЗ и планове, снимки – и
history.md с промените. Индексът obekti.csv в корена намира обекта. Пази се само последната версия
на всеки документ – със същото име, без дати и без дубликати. Всеки с личен ключ чете и пише (n8n).

ПРЕДИ ДА ИЗГОТВИШ документ за обект (ситуационна схема, оперативна картичка, схема, план) – провери:
    python3 _shared/scripts/obekti.py tarsi --ime "Магазин Х" --adres "ул. Примерна 1" --masto Плевен
    python3 _shared/scripts/obekti.py tarsi --lat 43.4196 --lon 24.6078
    python3 _shared/scripts/obekti.py tarsi "Ново име"              # и по стари имена
  Намерен е, ако съвпадат кадастралният идентификатор, координатите (до 60 m) или адресът. Само по
  име не е намерен: името се повтаря (няколко магазина на една верига в един град) и се сменя. Кандидатите по име се
  показват, за да попиташ кой е. Различен адрес или далечни координати = друг обект.

    python3 _shared/scripts/obekti.py pokazhi OB-0001                         # документите, снимките, историята
    python3 _shared/scripts/obekti.py pokazhi OB-0001 --svali situacionna_shema -o /mnt/user-data/outputs

Запис:
    python3 _shared/scripts/obekti.py nov --ime "Магазин Х" --masto Плевен --adres "ул. „Примерна“ № 1" \
        --lat 43.41257 --lon 24.65047 --kadastar 56722.27.446 [--eik 123456789] [--sluzhba "РСПБЗН – Плевен"]
    python3 _shared/scripts/obekti.py zapishi OB-0001 --vid situacionna_shema F.docx F.dxf F_grafichna.png F.json
    python3 _shared/scripts/obekti.py snimka OB-0001 IMG_1234.jpg --opisanie "главен вход"
    python3 _shared/scripts/obekti.py preimenuvai OB-0001 --ime "Ново име" [--ot 2026]   # старото име остава за търсене
    python3 _shared/scripts/obekti.py promeni OB-0001 adres="…" eik=… belezhka="…"
    python3 _shared/scripts/obekti.py istoriya OB-0001

Видове документи (--vid) – едно текущо копие на вид, файловете се казват <вид>.<разширение>:
    situacionna_shema, operativna_kartichka, plan_za_pozharogasene, shema_<тема> (схема на силите по сценарий),
    ptz_<тема> (план-конспект за ПТЗ: .docx, схемата му …_shema.png/.dxf и входът .json).
    Към всеки документ се пази и входният му .json – от него документът се изгражда наново, когато нещо
    се промени, вместо да се чертае от нулата.

Режим „конектор“ (колега без личен ключ): прочети с инструмента `obekti` (get root/obekti.csv и
нужните файлове) в папка ПАПКА – `ПАПКА/root/obekti.csv`, `ПАПКА/<papka_id>/history.md` – и пусни
скрипта с `--store ПАПКА --avtor "Име Фамилия"`. Четенето работи направо; при запис скриптът не пише
никъде, а дава списък `kachi` – стъпките за `obekti_save` по ред (виж _shared/connector.md).

Всички команди приемат --json (отговор за машина).
"""
import argparse
import base64
import csv
import datetime
import difflib
import hashlib
import io
import json
import math
import os
import re
import sys
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import api_config  # noqa: E402

INDEX = "obekti.csv"
HISTORY = "history.md"
PHOTOS = "snimki"
FIELDS = ["id", "ime", "predishni_imena", "naseleno_masto", "adres", "lat", "lon", "kadastar", "eik", "sluzhba",
          "papka_id", "papka", "sazdaden", "promenen", "promenil", "belezhka"]
EDITABLE = ["naseleno_masto", "adres", "lat", "lon", "kadastar", "eik", "sluzhba", "belezhka"]
VIDOVE = {
    "situacionna_shema": "Ситуационна схема",
    "operativna_kartichka": "Оперативна картичка",
    "plan_za_pozharogasene": "План за пожарогасене",
}
SUFFIXES = ("_grafichna", "_legenda", "_shema")   # parts of one document: the picture of a docx, its scheme
SAME_M = 60          # same object when the points are this close
FAR_M = 400          # a name match farther than this is another object
TZ = datetime.timezone(datetime.timedelta(hours=2))


class Problem(Exception):
    pass


# --------------------------------------------------------------------------- storage

class Remote:
    """The objects endpoint of n8n (fire-obekti)."""
    plan = False

    def __init__(self):
        if not api_config.has_key():
            raise Problem(api_config.NO_KEY + " – инструментите obekti и obekti_save; пусни скрипта с --store")
        self.by = None

    def call(self, body):
        try:
            res = api_config.post("obekti_url", body, timeout=180)
        except api_config.urllib.error.HTTPError as e:
            try:
                msg = json.loads(e.read()).get("error", "")
            except ValueError:
                msg = ""
            if e.code == 404 or msg.startswith("NOT_FOUND"):
                return None
            if e.code == 409 or msg.startswith("CONFLICT"):
                raise Problem(msg or "CONFLICT") from None
            raise Problem(f"N8N_ERROR {e.code}: {msg}") from None
        if isinstance(res, dict) and res.get("by"):
            self.by = res["by"]
        return res

    def list(self, folder):
        return (self.call({"action": "list", "folder": folder}) or {}).get("files", [])

    def get(self, folder, name):
        res = self.call({"action": "get", "folder": folder, "name": name})
        return None if res is None else base64.b64decode(res["base64"])

    def put(self, folder, name, data, if_md5=None):
        body = {"action": "put", "folder": folder, "name": name, "base64": base64.b64encode(data).decode("ascii")}
        if if_md5:
            body["if_md5"] = if_md5
        return self.call(body)

    def mkdir(self, folder, name):
        return self.call({"action": "mkdir", "folder": folder, "name": name})["folder"]

    def rename(self, folder, name, new_name):
        return self.call({"action": "rename", "folder": folder, "name": name, "new_name": new_name})


class Store:
    """Connector mode: files read with the tool `obekti` lie in DIR/<folder>/<name>; writes become steps."""
    plan = True

    def __init__(self, folder, avtor):
        self.dir, self.by, self.steps = folder, avtor or None, []

    def _path(self, folder, name):
        return os.path.join(self.dir, folder, name)

    def list(self, folder):
        d = os.path.join(self.dir, folder)
        out = []
        for name in sorted(os.listdir(d)) if os.path.isdir(d) else []:
            p = os.path.join(d, name)
            out.append({"id": None, "name": name, "folder": os.path.isdir(p),
                        "md5": None if os.path.isdir(p) else md5(open(p, "rb").read())})
        return out

    def get(self, folder, name):
        p = self._path(folder, name)
        return open(p, "rb").read() if os.path.isfile(p) else None

    def put(self, folder, name, data, if_md5=None):
        p = self._path(folder, name)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "wb") as f:
            f.write(data)
        step = {"tool": "obekti_save", "action": "put", "folder": folder, "name": name, "file": p}
        if if_md5:
            step["if_md5"] = if_md5
        self.steps.append(step)
        return {"saved": True, "name": name, "md5": md5(data)}

    def mkdir(self, folder, name):
        raise Problem(f"NEED_MKDIR: създай папката с obekti_save (action mkdir, folder {folder!r}, name {name!r}) "
                      "и пусни командата отново с --papka-id <върнатия folder>")

    def rename(self, folder, name, new_name):
        self.steps.append({"tool": "obekti_save", "action": "rename", "folder": folder, "name": name, "new_name": new_name})


# --------------------------------------------------------------------------- helpers

def md5(data):
    return hashlib.md5(data).hexdigest()


def now():
    return datetime.datetime.now(TZ)


_LAT = dict(zip("абвгдежзийклмнопрстуфхцчшщъьюяѝ",
                ["a", "b", "v", "g", "d", "e", "zh", "z", "i", "y", "k", "l", "m", "n", "o", "p", "r", "s", "t", "u",
                 "f", "h", "ts", "ch", "sh", "sht", "a", "", "yu", "ya", "i"]))


def fold(s):
    """Lower case Latin letters and digits only – Lidl = Лидл, „Дъбрава“ = dabrava."""
    s = unicodedata.normalize("NFC", str(s or "")).lower()
    s = "".join(_LAT.get(c, c) for c in s)
    s = unicodedata.normalize("NFKD", s)
    return re.sub(r"[^a-z0-9]+", " ", "".join(c for c in s if not unicodedata.combining(c))).strip()


_ADDR_WORDS = r"\b(ul|ulitsa|bul|bulevard|zh ?k|kv|zhk|gr|grad|s|selo|no|nomer|bl|blok|pl|ploshtad|obl|obsht)\b"


def addr_key(adres, masto=""):
    """(street words, number, settlement) of an address."""
    a = fold(adres)
    m = fold(masto)
    if m and a.endswith(" " + m):
        a = a[: -len(m) - 1]
    nums = re.findall(r"\b\d+[a-z]?\b", a)
    street = re.sub(r"\s+", " ", re.sub(_ADDR_WORDS + r"|\b\d+[a-z]?\b", " ", a)).strip()
    return street, (nums[0] if nums else ""), m


def same_address(a, b):
    if not a[0] or not b[0] or not a[1] or not b[1]:
        return False
    if a[2] and b[2] and a[2] != b[2]:
        return False
    return a[1] == b[1] and difflib.SequenceMatcher(None, a[0], b[0]).ratio() >= 0.8


def metres(p, q):
    r = math.radians
    h = math.sin(r(q[0] - p[0]) / 2) ** 2 + math.cos(r(p[0])) * math.cos(r(q[0])) * math.sin(r(q[1] - p[1]) / 2) ** 2
    return 2 * 6371000 * math.asin(math.sqrt(h))


def point(row):
    try:
        return float(row.get("lat")), float(row.get("lon"))
    except (TypeError, ValueError):
        return None


def names(row):
    old = [re.sub(r"\s*\(.*?\)\s*$", "", x).strip() for x in (row.get("predishni_imena") or "").split("|")]
    return [row.get("ime", "")] + [x for x in old if x]


def safe(s):
    s = re.sub(r"[\\/\x00-\x1f]+", " ", str(s or "")).strip()
    return re.sub(r"\s+", " ", s)[:120]


# --------------------------------------------------------------------------- index

class Register:
    def __init__(self, store):
        self.s = store
        raw = store.get("root", INDEX)
        self.md5 = md5(raw) if raw is not None else None
        self.rows = []
        if raw:
            text = raw.decode("utf-8-sig")
            self.rows = [{k: (r.get(k) or "").strip() for k in FIELDS} for r in csv.DictReader(io.StringIO(text))]

    def find(self, oid):
        oid = oid.strip().upper()
        if re.fullmatch(r"\d+", oid):
            oid = f"OB-{int(oid):04d}"
        for r in self.rows:
            if r["id"].upper() == oid:
                return r
        raise Problem(f"NOT_FOUND: няма обект {oid} в регистъра")

    def next_id(self):
        n = [int(r["id"][3:]) for r in self.rows if re.fullmatch(r"OB-\d+", r["id"])]
        return f"OB-{(max(n) + 1 if n else 1):04d}"

    def dump(self):
        out = io.StringIO()
        w = csv.DictWriter(out, FIELDS, lineterminator="\n")
        w.writeheader()
        for r in sorted(self.rows, key=lambda r: r["id"]):
            w.writerow(r)
        return out.getvalue().encode("utf-8")

    def save(self, change):
        """Write the index; on CONFLICT read it again, re-apply `change` (a function of the row list) once."""
        try:
            self.s.put("root", INDEX, self.dump(), self.md5 or "new")
            self.md5 = md5(self.dump())
            return
        except Problem as e:
            if "CONFLICT" not in str(e):
                raise
            fresh = Register(self.s)
            change(fresh.rows)
            self.s.put("root", INDEX, fresh.dump(), fresh.md5 or "new")
            self.rows, self.md5 = fresh.rows, md5(fresh.dump())


def history(store, row, line):
    """Add one line to the object's history.md (read – append – write with if_md5)."""
    stamp = now().strftime("%d.%m.%Y %H:%M")
    who = store.by or "?"
    for attempt in (1, 2):
        old = store.get(row["papka_id"], HISTORY)
        head = f"# История – {row['id']} {row['ime']}\n\n" if old is None else ""
        text = (old.decode("utf-8") if old else head) + f"- {stamp} – {who} – {line}\n"
        try:
            store.put(row["papka_id"], HISTORY, text.encode("utf-8"), md5(old) if old is not None else "new")
            return
        except Problem as e:
            if "CONFLICT" not in str(e) or attempt == 2:
                raise


# --------------------------------------------------------------------------- search

def search(reg, tekst="", ime="", adres="", masto="", lat=None, lon=None, kadastar=""):
    q_point = (lat, lon) if lat is not None and lon is not None else None
    q_addr = addr_key(adres, masto) if adres else None
    q_names = [fold(x) for x in (ime, tekst) if x]
    q_kad = {k.strip() for k in re.split(r"[|,;\s]+", kadastar or "") if k.strip()}
    found, by_name = [], []
    for r in reg.rows:
        why, other = [], []
        kad = {k.strip() for k in r["kadastar"].split("|") if k.strip()}
        if q_kad and kad and (q_kad & kad or any(a.startswith(b + ".") or b.startswith(a + ".") for a in q_kad for b in kad)):
            why.append("кадастрален идентификатор")
        p = point(r)
        if q_point and p:
            d = metres(q_point, p)
            if d <= SAME_M:
                why.append(f"координати ({d:.0f} m)")
            elif d > FAR_M:
                other.append(f"на {d:.0f} m")
        if q_addr and r["adres"]:
            if same_address(q_addr, addr_key(r["adres"], r["naseleno_masto"])):
                why.append("адрес")
            elif q_addr[1]:
                other.append(f"друг адрес ({r['adres']})")
        if masto and r["naseleno_masto"] and fold(masto) != fold(r["naseleno_masto"]):
            other.append(f"друго място ({r['naseleno_masto']})")
        named = []
        for n in names(r):
            fn = fold(n)
            if fn and any(q and (q == fn or q in fn.split() or fn in q.split() or
                                 difflib.SequenceMatcher(None, q, fn).ratio() >= 0.85) for q in q_names):
                named.append(n)
        if not why and tekst and not (q_point or q_addr or q_kad):
            # a free text may be an address or an identifier too
            if re.fullmatch(r"OB-\d+", tekst.strip().upper()) and tekst.strip().upper() == r["id"]:
                why.append("номер")
            elif same_address(addr_key(tekst, masto), addr_key(r["adres"], r["naseleno_masto"])):
                why.append("адрес")
        item = {"id": r["id"], "ime": r["ime"], "predishni_imena": r["predishni_imena"], "naseleno_masto": r["naseleno_masto"],
                "adres": r["adres"], "papka_id": r["papka_id"], "papka": r["papka"]}
        if why:
            found.append({**item, "savpada_po": why})
        elif named:
            by_name.append({**item, "savpada_po": ["име" + (f" (старо: {named[0]})" if named[0] != r["ime"] else "")],
                            "razlichno": other})
    if len(found) == 1:
        return {"nameren": found[0], "kandidati": by_name, "dvusmisleno": False}
    if len(found) > 1:
        return {"nameren": None, "kandidati": found + by_name, "dvusmisleno": True,
                "belezhka": "повече от един обект съвпада – попитай кой"}
    # only by name: the same object only when nothing contradicts and the query had nothing else to compare
    same = [c for c in by_name if not c["razlichno"]]
    if len(same) == 1 and not (q_point or q_addr or q_kad) and len(by_name) == 1:
        return {"nameren": None, "kandidati": by_name, "dvusmisleno": True,
                "belezhka": "намерен е само по име – потвърди адреса, преди да го ползваш"}
    return {"nameren": None, "kandidati": by_name, "dvusmisleno": len(same) > 0,
            "belezhka": ("кандидатите по име са на друго място – това е нов обект" if by_name and not same else
                         "попитай кой от кандидатите е" if same else "няма го в регистъра")}


# --------------------------------------------------------------------------- commands

def describe(store, row):
    files = store.list(row["papka_id"])
    docs, photos = {}, []
    for f in files:
        if f["folder"]:
            if f["name"] == PHOTOS:
                photos = [p["name"] for p in store.list(f.get("id") or os.path.join(row["papka_id"], PHOTOS)) if not p["folder"]]
            continue
        if f["name"] == HISTORY:
            continue
        stem = f["name"].rsplit(".", 1)[0]
        vid = stem
        for x in SUFFIXES:
            if stem.endswith(x) and stem not in VIDOVE and valid_vid(stem[: -len(x)]):
                vid = stem[: -len(x)]
        docs.setdefault(vid, []).append({"name": f["name"], "promenen": f.get("modified_at"),
                                         "link": f"https://drive.google.com/file/d/{f['id']}/view" if f.get("id") else None})
    hist = store.get(row["papka_id"], HISTORY)
    lines = [x for x in (hist.decode("utf-8").splitlines() if hist else []) if x.startswith("- ")]
    return {"obekt": row, "dokumenti": {v: {"vid": VIDOVE.get(v, v.replace("_", " ")), "failove": fs} for v, fs in sorted(docs.items())},
            "snimki": photos, "istoriya_posledni": lines[-5:],
            "papka_link": f"https://drive.google.com/drive/folders/{row['papka_id']}" if row["papka_id"] and not store.plan else None}


def cmd_nov(store, reg, a):
    hit = search(reg, ime=a.ime, adres=a.adres, masto=a.masto, lat=a.lat, lon=a.lon, kadastar=a.kadastar or "")
    if hit["nameren"] and not a.vse_pak:
        raise Problem(f"EXISTS: обектът вече е в регистъра – {hit['nameren']['id']} {hit['nameren']['ime']} "
                      f"({', '.join(hit['nameren']['savpada_po'])}); ползвай него или --vse-pak")
    oid = reg.next_id()
    kratak = re.sub(r"[„“\"]", "", a.adres or "").strip()
    papka = safe(f"{oid} {a.ime} – {kratak}, {a.masto}" if kratak else f"{oid} {a.ime}, {a.masto}")
    papka_id = a.papka_id or store.mkdir("root", papka)
    t = now().strftime("%Y-%m-%d")
    row = {k: "" for k in FIELDS}
    row.update(id=oid, ime=a.ime.strip(), naseleno_masto=a.masto.strip(), adres=(a.adres or "").strip(),
               lat=f"{a.lat:.6f}" if a.lat is not None else "", lon=f"{a.lon:.6f}" if a.lon is not None else "",
               kadastar=(a.kadastar or "").strip(), eik=(a.eik or "").strip(), sluzhba=(a.sluzhba or "").strip(),
               papka_id=papka_id, papka=papka, sazdaden=t, promenen=t, promenil=store.by or "", belezhka=(a.belezhka or "").strip())

    def add(rows):
        if any(r["id"] == oid for r in rows):
            raise Problem("CONFLICT: друг е добавил обект с този номер междувременно – пусни командата отново")
        rows.append(row)
    reg.rows.append(row)
    reg.save(add)
    history(store, row, f"Нов обект: {row['ime']}, {row['adres']}, {row['naseleno_masto']}")
    if store.by and not row["promenil"]:
        row["promenil"] = store.by
    return {"nov": row, "papka_link": None if store.plan else f"https://drive.google.com/drive/folders/{papka_id}"}


def valid_vid(vid):
    return bool(re.fullmatch(r"[a-z0-9_]{3,60}", vid)) and (vid in VIDOVE or bool(re.match(r"(shema|ptz)_[a-z0-9_]+$", vid)))


def target_name(vid, path):
    base = os.path.basename(path)
    stem, ext = os.path.splitext(base)
    ext = ext.lower()
    if not ext:
        raise Problem(f"BAD_FILE: {base} няма разширение")
    low = stem.lower()
    extra = "" if low.endswith(vid) else next((x for x in SUFFIXES if low.endswith(x)), "")
    return f"{vid}{extra}{ext}"


def cmd_zapishi(store, reg, a):
    row = reg.find(a.id)
    vid = a.vid.strip().lower()
    if not valid_vid(vid):
        raise Problem("BAD_VID: --vid е situacionna_shema, operativna_kartichka, plan_za_pozharogasene, "
                      "shema_<тема> или ptz_<тема>")
    existing = {f["name"]: f for f in store.list(row["papka_id"]) if not f["folder"]}
    done, same = [], []
    for path in a.files:
        data = open(path, "rb").read()
        name = target_name(vid, path)
        old = existing.get(name)
        if old and old.get("md5") == md5(data):
            same.append(name)
            continue
        store.put(row["papka_id"], name, data)
        done.append(name + (" (заменен)" if old else " (нов)"))
    if done:
        label = VIDOVE.get(vid, vid.replace("_", " "))
        history(store, row, f"{label}: " + ", ".join(done) + (f" – {a.belezhka}" if a.belezhka else ""))
        touch(store, reg, row)
    return {"obekt": row["id"], "zapisani": done, "bez_promyana": same}


def touch(store, reg, row, **changes):
    t = now().strftime("%Y-%m-%d")

    def apply(rows):
        for r in rows:
            if r["id"] == row["id"]:
                r.update(changes)
                r["promenen"], r["promenil"] = t, store.by or r["promenil"]
    apply(reg.rows)
    reg.save(apply)


def cmd_snimka(store, reg, a):
    row = reg.find(a.id)
    sub = [f for f in store.list(row["papka_id"]) if f["folder"] and f["name"] == PHOTOS]
    if store.plan:
        if not a.snimki_id:
            if sub:
                raise Problem(f"NEED_ID: подай --snimki-id – id на папката {PHOTOS} от obekti list на {row['papka_id']}")
            store.mkdir(row["papka_id"], PHOTOS)
        folder = a.snimki_id
    elif sub:
        folder = sub[0]["id"]
    else:
        folder = store.mkdir(row["papka_id"], PHOTOS)
    have = {f.get("md5"): f["name"] for f in store.list(folder) if not f["folder"]} if folder else {}
    done, dup = [], []
    for path in a.files:
        data = open(path, "rb").read()
        if md5(data) in have:
            dup.append(f"{os.path.basename(path)} = {have[md5(data)]}")
            continue
        ext = os.path.splitext(path)[1].lower() or ".jpg"
        opis = re.sub(r"\s+", "_", fold(a.opisanie or os.path.splitext(os.path.basename(path))[0]))[:50] or "snimka"
        name = f"{(a.data or now().strftime('%Y-%m-%d'))}_{opis}{ext}"
        n = 2
        while name in have.values():
            name = f"{(a.data or now().strftime('%Y-%m-%d'))}_{opis}_{n}{ext}"
            n += 1
        store.put(folder, name, data, "new")
        have[md5(data)] = name
        done.append(name)
    if done:
        history(store, row, "Снимки: " + ", ".join(done) + (f" – {a.opisanie}" if a.opisanie else ""))
        touch(store, reg, row)
    return {"obekt": row["id"], "zapisani": done, "dubliki": dup}


def cmd_preimenuvai(store, reg, a):
    row = reg.find(a.id)
    new = a.ime.strip()
    if fold(new) == fold(row["ime"]):
        return {"obekt": row["id"], "bez_promyana": True}
    old = row["ime"] + (f" (до {a.ot})" if a.ot else f" (до {now().year})")
    prev = "|".join([old] + [x for x in row["predishni_imena"].split("|") if x])
    papka = safe(row["papka"].replace(f"{row['id']} {row['ime']}", f"{row['id']} {new}", 1))
    if papka == row["papka"]:
        papka = safe(f"{row['id']} {new}")
    store.rename("root", row["papka"], papka)
    touch(store, reg, row, ime=new, predishni_imena=prev, papka=papka)
    row.update(ime=new, predishni_imena=prev, papka=papka)
    history(store, row, f"Ново име: {new} (досега {old})")
    return {"obekt": row}


def cmd_promeni(store, reg, a):
    row = reg.find(a.id)
    changes = {}
    for pair in a.fields:
        if "=" not in pair:
            raise Problem(f"BAD_FIELD: {pair} – пиши поле=стойност")
        k, v = pair.split("=", 1)
        if k not in EDITABLE:
            raise Problem(f"BAD_FIELD: {k} – може само {', '.join(EDITABLE)} (името – с preimenuvai)")
        changes[k] = v.strip()
    diff = {k: v for k, v in changes.items() if row[k] != v}
    if not diff:
        return {"obekt": row["id"], "bez_promyana": True}
    line = "Данни: " + "; ".join(f"{k}: {row[k] or '–'} → {v or '–'}" for k, v in diff.items())
    touch(store, reg, row, **diff)
    history(store, row, line)
    return {"obekt": row}


def main():
    p = argparse.ArgumentParser(description="Регистърът на обектите (fire-service/Обекти в Drive)")
    p.add_argument("--json", action="store_true")
    p.add_argument("--store", help="режим „конектор“: папка с файловете, прочетени с инструмента obekti")
    p.add_argument("--avtor", help="с --store: кой записва (ime от whoami)")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("tarsi"); s.add_argument("tekst", nargs="?", default="")
    for x in ("--ime", "--adres", "--masto", "--kadastar"):
        s.add_argument(x, default="")
    s.add_argument("--lat", type=float); s.add_argument("--lon", type=float)
    s = sub.add_parser("spisak")
    s = sub.add_parser("pokazhi"); s.add_argument("id"); s.add_argument("--svali"); s.add_argument("-o", "--out", default=".")
    s = sub.add_parser("istoriya"); s.add_argument("id")
    s = sub.add_parser("nov")
    s.add_argument("--ime", required=True); s.add_argument("--masto", required=True); s.add_argument("--adres", default="")
    s.add_argument("--lat", type=float); s.add_argument("--lon", type=float)
    for x in ("--kadastar", "--eik", "--sluzhba", "--belezhka", "--papka-id"):
        s.add_argument(x)
    s.add_argument("--vse-pak", action="store_true", help="създай го, въпреки че прилича на съществуващ")
    s = sub.add_parser("zapishi"); s.add_argument("id"); s.add_argument("--vid", required=True)
    s.add_argument("--belezhka"); s.add_argument("files", nargs="+")
    s = sub.add_parser("snimka"); s.add_argument("id"); s.add_argument("files", nargs="+")
    s.add_argument("--opisanie"); s.add_argument("--data"); s.add_argument("--snimki-id")
    s = sub.add_parser("preimenuvai"); s.add_argument("id"); s.add_argument("--ime", required=True); s.add_argument("--ot")
    s = sub.add_parser("promeni"); s.add_argument("id"); s.add_argument("fields", nargs="+")
    a = p.parse_args()

    try:
        store = Store(a.store, a.avtor) if a.store else Remote()
        reg = Register(store)
        if a.cmd == "tarsi":
            if not (a.tekst or a.ime or a.adres or a.kadastar or a.lat is not None):
                raise Problem("BAD_REQUEST: дай име, адрес, координати или кадастрален идентификатор")
            out = search(reg, a.tekst, a.ime, a.adres, a.masto, a.lat, a.lon, a.kadastar)
            out["obekti_v_registara"] = len(reg.rows)
        elif a.cmd == "spisak":
            out = {"obekti": [{k: r[k] for k in ("id", "ime", "predishni_imena", "naseleno_masto", "adres", "promenen")}
                              for r in reg.rows]}
        elif a.cmd == "pokazhi":
            row = reg.find(a.id)
            out = describe(store, row)
            if a.svali:
                os.makedirs(a.out, exist_ok=True)
                files = (out["dokumenti"].get(a.svali) or {}).get("failove", [])
                if not files:
                    raise Problem(f"NOT_FOUND: {row['id']} няма {a.svali}")
                got = []
                for f in files:
                    data = store.get(row["papka_id"], f["name"])
                    os.makedirs(os.path.join(a.out, row["id"]), exist_ok=True)
                    dest = os.path.join(a.out, row["id"], f["name"])     # the names the title block refers to
                    with open(dest, "wb") as fh:
                        fh.write(data)
                    got.append(dest)
                out["svaleni"] = got
        elif a.cmd == "istoriya":
            row = reg.find(a.id)
            h = store.get(row["papka_id"], HISTORY)
            out = {"obekt": row["id"], "istoriya": h.decode("utf-8") if h else ""}
        elif a.cmd == "nov":
            out = cmd_nov(store, reg, a)
        elif a.cmd == "zapishi":
            out = cmd_zapishi(store, reg, a)
        elif a.cmd == "snimka":
            out = cmd_snimka(store, reg, a)
        elif a.cmd == "preimenuvai":
            out = cmd_preimenuvai(store, reg, a)
        else:
            out = cmd_promeni(store, reg, a)
        if store.plan and store.steps:
            out["kachi"] = store.steps
    except Problem as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)
    print(json.dumps(out, ensure_ascii=False, indent=None if a.json else 1))


if __name__ == "__main__":
    main()
