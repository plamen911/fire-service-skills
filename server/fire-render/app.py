#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fire-render – the situational scheme (ситуационна схема) made on the server, for colleagues on the free plan.

Why: without a personal key the model used to carry the cadastre data (~77 000 characters) and the scheme
JSON (~55 000) through the chat, copying them into files by hand – one scheme used up the whole free limit.
Here the heavy JSON stays on the server, in a session; the model sends only small operations and gets back
short answers, a preview picture and, at the end, the files in the objects register.

Only n8n calls this service (the connector tool `shema`): it runs in n8n's Docker network with no published
port, and every request must carry the shared token (X-Render-Token). n8n adds who is calling ("klient").

    POST /shema {"action": "nachalo", "lat", "lon" | "kadastar" | "papka_id", "opcii": {…, "promyana"|"nanovo": true}}
    POST /shema {"action": "pokazhi", "sesiya", "pat": "/sgradi/0"}
    POST /shema {"action": "promeni", "sesiya", "operacii": [{"op": "set"|"add"|"remove"|"merge", "pat", "stoynost"},
                                                             {"op": "formulyar", "stoynost": {id: отговор}}, {"op": "chertai"}]}
    POST /shema {"action": "chertai", "sesiya"}
    POST /shema {"action": "zapishi", "sesiya"[, "obekt": "OB-0001" | "nov": {"ime", "adres", "masto"}]}

Every round trip resends the whole conversation, so the service saves the model calls: nachalo looks the object up
in the register first (an existing scheme comes back as links, without the minute-long КАИС query) and hands over
only the form questions that apply (formulyar.json stays here); promeni records the answers and returns only the
"deistvie" of the chosen options, and draws in the same call with {"op": "chertai"}; zapishi remembers the object
found by nachalo and returns the download links itself.
    POST /vreme {"data": "2026-10-26", "mesto": "Плевен" | "lat", "lon" | "stantsiya": "15528"|"LBPL",
                 "ot": "15:00", "do": "16:00", "do_data": "2026-10-28"}   – времето (vreme.py) за колегите,
                                                                     чиято среда не стига до архивите
    GET  /health

The scripts are the plugin's own (kais.py, situacionna.py, obekti.py) from the public repository, pulled at
most every 5 minutes – the server never has its own copy of the drawing rules.
"""
import base64
import io
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

REPO = os.environ.get("REPO_DIR", "/srv/repo")
DATA = os.environ.get("DATA_DIR", "/data/sesii")
TOKEN = os.environ.get("RENDER_TOKEN", "")
PULL_EVERY = 300
SESSION_TTL = 3 * 24 * 3600
SHEMI = os.path.join(REPO, "plugins", "fire-service", "skills", "shemi")
SCRIPTS = os.path.join(SHEMI, "_shared", "scripts")
FORMULYAR = os.path.join(SHEMI, "references", "formulyar.json")
VID = "situacionna_shema"
ACTIONS = ("nachalo", "pokazhi", "promeni", "chertai", "zapishi")
OPCII = {  # kais.py obekt options the model may set: name → (flag, takes a value)
    "radius": ("--radius", True), "granitsa": ("--granitsa", False), "ograda": ("--ograda", "maybe"),
    "trotoar": ("--trotoar", True), "trotoar_ulitsa": ("--trotoar-ulitsa", True), "bez_sasedni": ("--bez-sasedni", False),
    "vodoprovod": ("--vodoprovod", True), "natisk": ("--natisk", True), "hidrant_v_terena": ("--hidrant-v-terena", False),
    "bez_trevni": ("--bez-trevni", False), "bez_reki": ("--bez-reki", False), "s_vatreshni": ("--s-vatreshni", False),
    "sloi": ("--sloi", True),
}
_pull_lock = threading.Lock()
_last_pull = [0.0]


class Problem(Exception):
    def __init__(self, code, msg, status=400):
        super().__init__(msg)
        self.code, self.status = code, status


# ------------------------------------------------------------------------------------------- helpers

APP = os.path.abspath(__file__)


def _app_text():
    try:
        with open(APP, "rb") as f:
            return f.read()
    except OSError:
        return b""


_app_loaded = [_app_text()]


def pull():
    """git pull at most every PULL_EVERY seconds, so a change pushed to the plugin reaches the server.
    When the pull changes this very file, the process restarts itself (os.execv) a moment later – a new
    action of the service needs no manual deploy; only a new system package (Dockerfile) does."""
    with _pull_lock:
        if time.time() - _last_pull[0] < PULL_EVERY:
            return
        subprocess.run(["git", "-C", REPO, "pull", "--ff-only", "-q"], capture_output=True, timeout=120)
        _last_pull[0] = time.time()
        if APP.startswith(REPO) and _app_text() not in (b"", _app_loaded[0]):
            threading.Thread(target=_restart, daemon=True).start()


def _restart():
    time.sleep(3)  # let the answers in progress finish
    sys.stderr.write("app.py changed in the repository – restarting\n")
    os.execv(sys.executable, [sys.executable, APP])


def _puller():
    while True:
        time.sleep(PULL_EVERY + 5)
        try:
            pull()
        except Exception:  # noqa: BLE001 – the next round tries again
            pass


def cleanup():
    if not os.path.isdir(DATA):
        return
    for name in os.listdir(DATA):
        path = os.path.join(DATA, name)
        try:
            if time.time() - os.path.getmtime(path) > SESSION_TTL:
                shutil.rmtree(path, ignore_errors=True)
        except OSError:
            pass


def session(sid, new=False):
    if new:
        sid = secrets.token_hex(8)
        os.makedirs(os.path.join(DATA, sid, "out"))
        return sid, os.path.join(DATA, sid)
    if not re.fullmatch(r"[0-9a-f]{16}", str(sid or "")):
        raise Problem("BAD_INPUT", "липсва или е невярна \"sesiya\" (от отговора на nachalo)")
    path = os.path.join(DATA, sid)
    if not os.path.isfile(os.path.join(path, "shema.json")):
        raise Problem("NOT_FOUND", "няма такава сесия (пазят се 3 дни) – започни с nachalo", 404)
    os.utime(path)
    return sid, path


def run(args, cwd, timeout=240, env=None):
    p = subprocess.run([sys.executable, *args], cwd=cwd, capture_output=True, text=True, timeout=timeout,
                       env={**os.environ, **(env or {})})
    if p.returncode != 0:
        msg = (p.stderr or p.stdout).strip().splitlines()
        raise Problem("SCRIPT_ERROR", " / ".join(msg[-4:])[:900] or f"код {p.returncode}")
    return p.stdout


def load(path):
    with open(os.path.join(path, "shema.json"), encoding="utf-8") as f:
        return json.load(f)


def save(path, data):
    tmp = os.path.join(path, "shema.json.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    os.replace(tmp, os.path.join(path, "shema.json"))


def picture(path, width=1300):
    """A preview the model can look at: JPEG, at most `width` px wide (the originals are megabytes)."""
    from PIL import Image
    with Image.open(path) as im:
        im = im.convert("RGB")
        if im.width > width:
            im = im.resize((width, round(im.height * width / im.width)))
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=62, optimize=True)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def label(x):
    if not isinstance(x, dict):
        return json.dumps(x, ensure_ascii=False)[:60]
    for k in ("etiket", "tekst", "ime", "vid", "id", "naslov"):
        if x.get(k) not in (None, ""):
            v = str(x[k]).replace("\n", " ")
            extra = [f"{c}={x[c]}" for c in ("x", "y") if isinstance(x.get(c), (int, float))]
            return (f"{k}: {v}"[:70] + (" @ " + ",".join(extra) if extra else ""))
    return "{" + ", ".join(list(x)[:6]) + "}"


def outline(data):
    """The scheme in a few lines: what each field holds, list items by index – enough to aim a "pat"."""
    out = {}
    for k, v in data.items():
        if isinstance(v, list) and v and not any(isinstance(x, dict) for x in v):
            out[k] = f"{len(v)} стойности (точки) – виж ги с pokazhi /{k}"
        elif isinstance(v, list):
            items = [f"[{i}] {label(x)}" for i, x in enumerate(v[:25])]
            if len(v) > 25:
                items.append(f"… общо {len(v)}")
            out[k] = items
        elif isinstance(v, dict):
            out[k] = {kk: (vv if isinstance(vv, (str, int, float, bool)) and len(str(vv)) < 80 else type(vv).__name__)
                      for kk, vv in list(v.items())[:20]}
        else:
            out[k] = v
    return out


def meta(path, **upd):
    """Small facts of the session besides the scheme (the object found in the register)."""
    f = os.path.join(path, "meta.json")
    try:
        with open(f, encoding="utf-8") as fh:
            m = json.load(fh)
    except (OSError, ValueError):
        m = {}
    if upd:
        m.update(upd)
        with open(f, "w", encoding="utf-8") as fh:
            json.dump(m, fh, ensure_ascii=False)
    return m


def obekti(*args, cwd=DATA, env=None):
    script = os.environ.get("OBEKTI_SCRIPT") or os.path.join(SCRIPTS, "obekti.py")
    os.makedirs(cwd, exist_ok=True)
    return json.loads(run([script, "--json", *args], cwd=cwd, env=env))


def links(oid):
    """The download links (signed by n8n, 24 h, no Google account) of the object's situacionna_shema files."""
    try:
        d = obekti("pokazhi", oid)
    except (Problem, ValueError):
        return []
    fs = ((d.get("dokumenti") or {}).get(VID) or {}).get("failove") or []
    return [{"ime": f.get("name"), "link": f.get("link")} for f in fs if not str(f.get("name", "")).endswith(".json")]


def in_register(b):
    """The register entry for the point or the cadastral id, or None. A failing lookup never blocks the scheme."""
    args = ["tarsi"]
    if b.get("kadastar"):
        args += ["--kadastar", str(b["kadastar"])]
    if b.get("lat") is not None and b.get("lon") is not None:
        args += ["--lat", str(float(b["lat"])), "--lon", str(float(b["lon"]))]
    if len(args) == 1:
        return None
    try:
        return obekti(*args).get("nameren")
    except (Problem, ValueError, subprocess.TimeoutExpired):
        return None


def questions(data):
    """The form questions still open, compact (no "deistvie" – promeni returns it for the chosen answers).
    The streets around the parcel become the options of "vhod_kola"."""
    with open(FORMULYAR, encoding="utf-8") as f:
        form = json.load(f)
    done = data.get("formulyar") or {}
    streets = []
    for u in data.get("ulitsi") or []:
        name = isinstance(u, dict) and str(u.get("ime") or "").strip()
        if name and name not in streets:
            streets.append(name)
    out = []
    for scr in form["screens"]:
        qs = []
        for q in scr["questions"]:
            if q["id"] in done:
                continue
            item = {"id": q["id"], "vapros": q["question"], "opcii": q["options"]}
            if q["id"] == "vhod_kola" and streets:
                item["opcii"] = ["от " + x for x in streets[:3]] + ["не личи – ще кажа къде"]
            for k in ("multi", "always", "kogato", "dinamichni"):
                if q.get(k):
                    item[k] = q[k]
            qs.append(item)
        if qs:
            out.append({"ekran": scr["title"], "vaprosi": qs})
    return out


def answers(data, given):
    """Records the form answers in the scheme and returns what each one means for the drawing and the table."""
    if not isinstance(given, dict) or not given:
        raise Problem("BAD_INPUT", "formulyar: \"stoynost\" е {id: отговор}")
    with open(FORMULYAR, encoding="utf-8") as f:
        qs = {q["id"]: q for scr in json.load(f)["screens"] for q in scr["questions"]}
    data.setdefault("formulyar", {}).update(given)
    out = {}
    for qid, ans in given.items():
        q = qs.get(qid)
        if not q:
            raise Problem("BAD_INPUT", f"formulyar: няма въпрос „{qid}“ – ид-тата са {', '.join(qs)}")
        dei = q.get("deistvie") or {}
        picked = [a for a in (ans if isinstance(ans, list) else [ans]) if isinstance(a, str)]
        hit = {a: dei[a] for a in picked if a in dei}
        # a street, a point, a name or a free "Друго" – the option templates say what to do with it
        out[qid] = hit if len(hit) == len(picked) else dei
    return out


def pointer(pat):
    if pat in ("", "/"):
        return []
    if not str(pat).startswith("/"):
        raise Problem("BAD_INPUT", f"\"pat\" започва с „/“, напр. /sgradi/0/etiket – не „{pat}“")
    return [p.replace("~1", "/").replace("~0", "~") for p in str(pat)[1:].split("/")]


def walk(data, parts, create=False):
    """The container of the last part, and that part (int for lists)."""
    node = data
    for i, p in enumerate(parts[:-1]):
        nxt = parts[i + 1]
        if isinstance(node, list):
            node = node[int(p)]
        else:
            if p not in node:
                if not create:
                    raise Problem("BAD_INPUT", f"няма поле „{p}“")
                node[p] = [] if nxt == "-" or nxt.isdigit() else {}
            node = node[p]
    last = parts[-1]
    if isinstance(node, list) and last != "-":
        last = int(last)
    return node, last


def apply_ops(data, ops):
    if not isinstance(ops, list) or not ops:
        raise Problem("BAD_INPUT", "\"operacii\" – списък с {op, pat, stoynost}")
    done = []
    for n, o in enumerate(ops, 1):
        op, parts = str(o.get("op", "")).strip(), pointer(o.get("pat", ""))
        if not parts:
            raise Problem("BAD_INPUT", f"операция {n}: \"pat\" не може да е коренът")
        try:
            if op in ("set", "add"):
                node, last = walk(data, parts, create=True)
                if isinstance(node, list):
                    if last == "-":
                        node.append(o.get("stoynost"))
                    elif op == "add":
                        node.insert(last, o.get("stoynost"))
                    else:
                        node[last] = o.get("stoynost")
                else:
                    node[last] = o.get("stoynost")
            elif op == "remove":
                node, last = walk(data, parts)
                del node[last]
            elif op == "merge":
                node, last = walk(data, parts, create=True)
                cur = node[last] if (isinstance(node, list) or last in node) else {}
                if not isinstance(cur, dict) or not isinstance(o.get("stoynost"), dict):
                    raise Problem("BAD_INPUT", f"операция {n}: merge е само за обект")
                cur.update(o["stoynost"])
                node[last] = cur
            else:
                raise Problem("BAD_INPUT", f"операция {n}: op е set, add, remove или merge")
        except (KeyError, IndexError, ValueError, TypeError) as e:
            raise Problem("BAD_INPUT", f"операция {n} ({op} {o.get('pat')}): {type(e).__name__} {e}") from None
        done.append(f"{op} {o.get('pat')}")
    return done


# ------------------------------------------------------------------------------------------- actions

def from_register(path, papka):
    sys.path.insert(0, SCRIPTS)
    import api_config  # noqa: E402
    res = api_config.post("obekti_url", {"action": "get", "folder": papka, "name": VID + ".json"}, timeout=120)
    with open(os.path.join(path, "shema.json"), "wb") as f:
        f.write(base64.b64decode(res["base64"]))
    return load(path)


def a_nachalo(b):
    pull()
    cleanup()
    opcii = b.get("opcii") or {}
    papka = str(b.get("papka_id") or "").strip()
    found = None if papka else in_register(b)
    if found and not papka:
        fs = links(found["id"])
        if fs and not (opcii.get("promyana") or opcii.get("nanovo")):
            return {"ima_shema": True, "obekt": found["id"], "ime": found.get("ime"), "adres": found.get("adres"),
                    "failove": fs,
                    "za_claude": "Обектът вече има ситуационна схема – дай линковете и спри. Промяна на записаната: "
                                 "nachalo отново с opcii.promyana; изцяло нова от КАИС: opcii.nanovo."}
        if fs and opcii.get("promyana"):
            papka = found.get("papka_id") or ""
    sid, path = session(None, new=True)
    if found:
        meta(path, obekt=found["id"])
    if papka:  # an object already in the register: continue from its stored JSON
        data = from_register(path, papka)
        return {"sesiya": sid, "ot_registara": True, "obekt": (found or {}).get("id"), "shema": outline(data),
                "vaprosi": questions(data),
                "za_claude": "Схемата е заредена от регистъра. Промени с promeni (с {\"op\": \"chertai\"} накрая), "
                             "после zapishi."}
    args = [os.path.join(SCRIPTS, "kais.py"), "obekt", "-o", "kais.json", "--shema", "shema.json", "--voda", "--ortofoto"]
    if b.get("kadastar"):
        args += ["--id", str(b["kadastar"])]
    elif b.get("lat") is not None and b.get("lon") is not None:
        args += ["--lat", str(float(b["lat"])), "--lon", str(float(b["lon"]))]
    elif b.get("link"):
        args += ["--link", str(b["link"])]
    else:
        raise Problem("BAD_INPUT", "nachalo иска \"kadastar\", \"lat\"+\"lon\", \"link\" или \"papka_id\"")
    for k, v in opcii.items():
        if k not in OPCII or v in (None, False, ""):
            continue
        flag, takes = OPCII[k]
        args += [flag] if (takes is False or (takes == "maybe" and v is True)) else [flag, str(v)]
    out = run(args, cwd=path)
    try:
        rez = json.loads(out)
    except ValueError:
        rez = {"izhod": out[-1500:]}
    for k in ("kais_json", "fon", "shema", "ortofoto"):
        rez.pop(k, None)
    data = load(path)
    ans = {"sesiya": sid, "kais": rez, "shema": outline(data), "vaprosi": questions(data),
           "za_claude": "Данните от КАИС са на сървъра. Задай vaprosi наведнъж (входовете – по номерираните точки на "
                        "ортофотото); отговорите – promeni с {\"op\": \"formulyar\"} (връща deistvie); deistvie и "
                        "антетката – второ promeni с {\"op\": \"chertai\"} накрая; после zapishi."}
    if found:
        ans["obekt"] = found["id"]
    orto = os.path.join(path, "shema_ortofoto.png")
    if os.path.isfile(orto):
        ans["png_base64"], ans["format"] = picture(orto, 1100), "image/jpeg"
    return ans


def a_pokazhi(b):
    _, path = session(b.get("sesiya"))
    data = load(path)
    parts = pointer(b.get("pat", ""))
    node = data
    try:
        for p in parts:
            node = node[int(p)] if isinstance(node, list) else node[p]
    except (KeyError, IndexError, ValueError):
        raise Problem("NOT_FOUND", f"няма {b.get('pat')}", 404) from None
    text = json.dumps(node, ensure_ascii=False)
    if len(text) > 8000:
        return {"pat": b.get("pat", "/"), "sakrateno": True, "obzor": outline(node) if isinstance(node, dict) else
                [f"[{i}] {label(x)}" for i, x in enumerate(node)] if isinstance(node, list) else text[:8000],
                "za_claude": "Твърде голямо – поискай по-тясна част (напр. /sgradi/0)."}
    return {"pat": b.get("pat", "/"), "stoynost": node}


def a_promeni(b):
    _, path = session(b.get("sesiya"))
    data = load(path)
    ops = b.get("operacii")
    if not isinstance(ops, list) or not ops:
        raise Problem("BAD_INPUT", "\"operacii\" – списък с {op, pat, stoynost}")
    draw = any(isinstance(o, dict) and o.get("op") == "chertai" for o in ops)
    form = [o for o in ops if isinstance(o, dict) and o.get("op") == "formulyar"]
    rest = [o for o in ops if not (isinstance(o, dict) and o.get("op") in ("chertai", "formulyar"))]
    res = {}
    for o in form:
        res.setdefault("deistvie", {}).update(answers(data, o.get("stoynost")))
    res["napraveno"] = apply_ops(data, rest) if rest else []
    save(path, data)
    if draw:
        res.update(a_chertai(b))
    else:
        res["shema"] = outline(data)
        if "deistvie" in res:
            res["za_claude"] = "Приложи deistvie на отговорите с още едно promeni, с {\"op\": \"chertai\"} накрая."
    return res


def a_chertai(b):
    pull()
    _, path = session(b.get("sesiya"))
    data = load(path)
    lst = data.setdefault("list", {})
    if b.get("klient") and not lst.get("izgotvil"):
        lst["izgotvil"] = b["klient"]
        save(path, data)
    if not lst.get("obekt"):
        raise Problem("BAD_INPUT", "липсва list.obekt (антетката) – promeni set /list/obekt")
    out = os.path.join(path, "out")
    shutil.rmtree(out, ignore_errors=True)
    os.makedirs(out)
    res = json.loads(run([os.path.join(SHEMI, "scripts", "situacionna.py"), "shema.json", "-o",
                          os.path.join(out, VID + ".docx")], cwd=path))
    for k in ("output", "grafichna", "dxf"):
        res.pop(k, None)
    res["failove"] = sorted(os.listdir(out))
    res["png_base64"], res["format"] = picture(os.path.join(out, VID + "_grafichna.png")), "image/jpeg"
    res["za_claude"] = ("Прегледай картинката (надписи, входове, хидранти). Поправи с promeni и chertai отново; "
                        "когато е готова – zapishi.")
    return res


def a_zapishi(b):
    pull()
    _, path = session(b.get("sesiya"))
    out = os.path.join(path, "out")
    files = [os.path.join(out, VID + x) for x in (".docx", ".dxf", "_grafichna.png")]
    if not all(os.path.isfile(f) for f in files):
        raise Problem("BAD_INPUT", "първо chertai – няма начертана схема")
    shutil.copy(os.path.join(path, "shema.json"), os.path.join(out, VID + ".json"))
    files.append(os.path.join(out, VID + ".json"))
    env = {"FIRE_SERVICE_AVTOR": str(b.get("klient") or "")}
    oid = str(b.get("obekt") or ("" if b.get("nov") else meta(path).get("obekt")) or "").strip()
    nov = None
    if not oid:
        n = b.get("nov") or {}
        if not (n.get("ime") and n.get("masto")):
            raise Problem("BAD_INPUT", "zapishi иска \"obekt\" (OB-…) или \"nov\" с ime, adres, masto")
        data = load(path)
        kais = (data.get("kais") or {})
        args = ["nov", "--ime", n["ime"], "--masto", n["masto"], "--adres", n.get("adres", "")]
        for k in ("lat", "lon"):
            if n.get(k) is not None:
                args += [f"--{k}", str(float(n[k]))]
        if kais.get("imot") or n.get("kadastar"):
            args += ["--kadastar", str(n.get("kadastar") or kais.get("imot"))]
        nov = obekti(*args, cwd=path, env=env)
        oid = (nov.get("nov") or {}).get("id") or ""
        if not oid:
            return {"zapisano": False, "otgovor": nov,
                    "za_claude": "Обектът не е създаден – виж отговора (вероятно прилича на съществуващ)."}
    res = obekti("zapishi", oid, "--vid", VID, *files, cwd=path, env=env)
    meta(path, obekt=oid)
    return {"zapisano": True, "obekt": oid, "nov_obekt": bool(nov), "otgovor": res, "failove": links(oid),
            "za_claude": "Записано в регистъра. Дай на потребителя линковете от failove – .docx, .dxf и картинката."}


VREME = os.path.join(SCRIPTS, "vreme.py")
DATA_RE = r"\d{4}-\d{2}-\d{2}|\d{2}\.\d{2}\.\d{4}"


def a_vreme(b):
    """vreme.py on the server: the НИМХ SYNOP, the airport METAR and the НИМХ bulletin are fetched here,
    where the network reaches them; the answer is the script's JSON, unchanged."""
    pull()
    data = str(b.get("data") or "").strip()
    if not re.fullmatch(DATA_RE, data):
        raise Problem("BAD_INPUT", "\"data\" е ГГГГ-ММ-ДД")
    args = [VREME]
    st = str(b.get("stantsiya") or "").strip().upper()
    if st:
        if not re.fullmatch(r"\d{5}|[A-Z]{4}", st):
            raise Problem("BAD_INPUT", "\"stantsiya\" е WMO (15528) или ICAO (LBPL)")
        args.append(st)
    args.append(data)
    if b.get("do_data"):
        dd = str(b["do_data"]).strip()
        if not re.fullmatch(DATA_RE, dd):
            raise Problem("BAD_INPUT", "\"do_data\" е ГГГГ-ММ-ДД")
        args.append(dd)
    if b.get("lat") is not None and b.get("lon") is not None:
        args += ["--blizo", f"{float(b['lat'])},{float(b['lon'])}"]
    elif b.get("mesto"):
        m = str(b["mesto"]).strip()
        if len(m) > 80 or m.startswith("-"):
            raise Problem("BAD_INPUT", "\"mesto\" е име на населено място")
        args += ["--mesto", m]
    elif not st:
        raise Problem("BAD_INPUT", "дай \"mesto\", \"lat\"/\"lon\" или \"stantsiya\"")
    for k in ("ot", "do"):
        if b.get(k):
            v = str(b[k]).strip()
            if not re.fullmatch(r"\d{1,2}:\d{2}", v):
                raise Problem("BAD_INPUT", f"\"{k}\" е ЧЧ:ММ")
            args += [f"--{k}", v]
    p = subprocess.run([sys.executable, *args], capture_output=True, text=True, timeout=240,
                       env={**os.environ, "FIRE_SERVICE_NA_SARVARA": "1"})
    if p.returncode != 0:
        msg = (p.stderr or p.stdout).strip()
        code = msg.split(":", 1)[0] if re.match(r"[A-Z_]+:", msg) else "SCRIPT_ERROR"
        raise Problem(code, msg.split(":", 1)[-1].strip()[:900], 404 if code == "NO_DATA" else 400)
    return json.loads(p.stdout)


HANDLERS = {"nachalo": a_nachalo, "pokazhi": a_pokazhi, "promeni": a_promeni, "chertai": a_chertai, "zapishi": a_zapishi}


# ------------------------------------------------------------------------------------------- server

class Handler(BaseHTTPRequestHandler):
    server_version = "fire-render"

    def send(self, status, obj):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/health":
            ok = os.path.isfile(os.path.join(SHEMI, "scripts", "situacionna.py"))
            return self.send(200 if ok else 503, {"status": "ok" if ok else "no_repo",
                                                  "key": bool(os.environ.get("FIRE_SERVICE_KEY"))})
        self.send(404, {"error": "NOT_FOUND"})

    def do_POST(self):
        if not TOKEN or not secrets.compare_digest(self.headers.get("X-Render-Token", ""), TOKEN):
            return self.send(401, {"error": "UNAUTHORIZED"})
        if self.path not in ("/shema", "/vreme"):
            return self.send(404, {"error": "NOT_FOUND"})
        try:
            n = int(self.headers.get("Content-Length") or 0)
            if n > 2_000_000:
                raise Problem("TOO_LARGE", "заявката е над 2 MB")
            b = json.loads(self.rfile.read(n) or b"{}")
            if self.path == "/vreme":
                return self.send(200, a_vreme(b))
            action = str(b.get("action", ""))
            if action not in HANDLERS:
                raise Problem("BAD_INPUT", "action е " + ", ".join(ACTIONS))
            self.send(200, HANDLERS[action](b))
        except Problem as e:
            self.send(e.status, {"error": f"{e.code}: {e}"})
        except subprocess.TimeoutExpired:
            self.send(504, {"error": "TIMEOUT: скриптът не отговори навреме"})
        except Exception as e:  # noqa: BLE001 – the answer goes back to the model, not a stack trace
            self.send(500, {"error": f"SERVER_ERROR: {type(e).__name__}: {e}"[:600]})

    def log_message(self, fmt, *args):
        sys.stderr.write("%s %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), fmt % args))


if __name__ == "__main__":
    os.makedirs(DATA, exist_ok=True)
    threading.Thread(target=_puller, daemon=True).start()
    ThreadingHTTPServer(("0.0.0.0", int(os.environ.get("PORT", "8080"))), Handler).serve_forever()
