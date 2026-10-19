#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
regs.py — нормативната база (Fire Safety Regulatory Documents) през n8n.

Файловете стоят в Google Drive на администратора; n8n ги чете и ги дава на всеки активен личен ключ
(`regs_url` в `_shared/incident_api.json`; ключът идва от `api_config.py`). Друг път към базата няма.

    python3 scripts/regs.py list                       # всички файлове (JSON: path, id, modified_at, size)
    python3 scripts/regs.py list --folder tier-a       # само една папка ("" = корена)
    python3 scripts/regs.py list --name 8121з-1006     # името съдържа текста
    python3 scripts/regs.py index                      # сваля текущия индекс (_INDEX_*.md, най-новия)
    python3 scripts/regs.py get _MAP_pg_sd.md          # сваля файл по име, път, част от името или Drive ID
    python3 scripts/regs.py get tier-a/…_2026_ed2026-02-27.md -o work
    python3 scripts/regs.py katalog --q 8121з-1006            # статусът от index.json: in_force, superseded_by, map …
    python3 scripts/regs.py figuri RDPBZN-Pleven_Lesson-Plan_ASD-PTP-Hibridni-Avtomobili_2021.md -o fig
                                                       # картинките, към които сочи файлът (![…](assets/…))
    python3 scripts/regs.py get assets/…_fig01.png -o fig    # една картинка от папката assets/

Картинките на базата стоят в папката `assets/` в корена; файлът сочи към тях с
`![Фиг. N. Надпис](assets/ИМЕ.png)`. `figuri` ги сваля всичките и отпечатва JSON
{"count", "figuri": [{"fig", "caption", "path", "bytes"}]} – полето "fig" отива направо във фигура на
документ (напр. {"fig": …, "caption": …} в изложението на план-конспекта).

Свалените файлове отиват в папката от -o (по подразбиране `regs/` в текущата папка). Скриптът
отпечатва JSON {"file", "path", "id", "modified_at", "bytes", "link"} – после четеш файла `file`
(търси в него члена с Grep/Read, не го изсипвай целия в чата). `link` е адресът в Drive за
позоваването в отговора; отваря се само от хора с достъп до папката.

Грешки (на stderr, код ≠ 0):
    N8N_UNAVAILABLE: ...   — n8n не отговаря или върна грешка → опитай веднъж отново
    NOT_FOUND: ...         — няма такъв файл в базата
    AMBIGUOUS: ...         — името пасва на няколко файла; изброени са – подай по-точно име или ID
    UNSUPPORTED: ...       — файлът не е текстов (PDF оригинал) и не се сваля
"""
import argparse
import base64
import json
import os
import re
import sys
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "_shared", "scripts"))
import api_config  # noqa: E402  (addresses of n8n and the personal key)


def call(body):
    try:
        return api_config.post("regs_url", body)
    except urllib.error.HTTPError as e:
        text = e.read().decode(errors="ignore")[:200]
        if e.code == 415 or "UNSUPPORTED" in text:
            sys.exit("UNSUPPORTED: файлът не е текстов и не се сваля през n8n")
        if "File not found" in text or "NOT_FOUND" in text:
            sys.exit("NOT_FOUND: няма такъв файл в базата")
        sys.exit(f"N8N_UNAVAILABLE: HTTP {e.code} {text}")
    except (OSError, KeyError, ValueError) as e:
        sys.exit(f"N8N_UNAVAILABLE: {type(e).__name__}: {e}"[:300])


def listing():
    res = call({"action": "list"})
    if not isinstance(res, dict) or not isinstance(res.get("files"), list):
        sys.exit("N8N_UNAVAILABLE: unexpected response shape")
    return res["files"]


def norm(s):
    return (s or "").strip().lower()


def resolve(files, what):
    """One file by Drive ID, exact path, exact name, or a unique part of the path."""
    q = norm(what)
    for key in ("id", "path", "name"):
        hit = [f for f in files if norm(f.get(key)) == q or (key == "id" and f.get("id") == what)]
        if len(hit) == 1:
            return hit[0]
    hit = [f for f in files if q in norm(f.get("path"))]
    if len(hit) == 1:
        return hit[0]
    if not hit:
        sys.exit(f"NOT_FOUND: няма файл „{what}“ в базата")
    names = "\n".join("  " + f["path"] for f in hit[:30])
    sys.exit(f"AMBIGUOUS: „{what}“ пасва на {len(hit)} файла:\n{names}")


def download(f, out_dir):
    res = call({"action": "download", "id": f["id"]})
    if not isinstance(res, dict) or not isinstance(res.get("content"), str):
        sys.exit("N8N_UNAVAILABLE: unexpected response shape")
    os.makedirs(out_dir, exist_ok=True)
    safe = re.sub(r"[^\w.\-]+", "_", res.get("path") or f["path"], flags=re.UNICODE) or f["id"]
    target = os.path.join(out_dir, safe)
    with open(target, "w", encoding="utf-8") as fh:
        fh.write(res["content"])
    print(json.dumps({"file": target, "path": res.get("path") or f["path"], "id": f["id"],
                      "modified_at": res.get("modified_at") or f.get("modified_at"),
                      "bytes": len(res["content"].encode("utf-8")),
                      "link": f"https://drive.google.com/file/d/{f['id']}/view"},
                     ensure_ascii=False))


ASSET_RE = re.compile(r"!\[([^\]]*)\]\((assets/[^)\s]+)\)")


def download_asset(f, out_dir):
    """One picture from assets/ – n8n hands it out base64-encoded through the files endpoint."""
    try:
        res = api_config.post("samples_url", {"action": "get", "kind": "regs-assets", "name": f["name"]})
    except urllib.error.HTTPError as e:
        text = e.read().decode(errors="ignore")[:200]
        if "NOT_FOUND" in text:
            sys.exit(f"NOT_FOUND: няма картинка „{f['name']}“ в assets/")
        sys.exit(f"N8N_UNAVAILABLE: HTTP {e.code} {text}")
    except (OSError, KeyError, ValueError) as e:
        sys.exit(f"N8N_UNAVAILABLE: {type(e).__name__}: {e}"[:300])
    if not isinstance(res, dict) or not isinstance(res.get("base64"), str):
        sys.exit("N8N_UNAVAILABLE: unexpected response shape (n8n не дава картинки)")
    data = base64.b64decode(res["base64"])
    os.makedirs(out_dir, exist_ok=True)
    target = os.path.join(out_dir, f["name"])
    with open(target, "wb") as fh:
        fh.write(data)
    return {"file": target, "path": "assets/" + f["name"], "id": f["id"], "bytes": len(data),
            "link": f"https://drive.google.com/file/d/{f['id']}/view"}


def figuri(files, what, out_dir):
    """Every picture a file of the base points to with ![caption](assets/NAME), in the order of the text."""
    f = resolve(files, what)
    res = call({"action": "download", "id": f["id"]})
    text = res.get("content") if isinstance(res, dict) else None
    if not isinstance(text, str):
        sys.exit("N8N_UNAVAILABLE: unexpected response shape")
    out, seen = [], set()
    for caption, path in ASSET_RE.findall(text):
        if path in seen:
            continue
        seen.add(path)
        got = download_asset(resolve([x for x in files if x.get("folder") == "assets"], path), out_dir)
        out.append({"fig": got["file"], "caption": caption.strip(), "path": path, "bytes": got["bytes"]})
    print(json.dumps({"file": f["path"], "count": len(out), "figuri": out}, ensure_ascii=False, indent=1))


def katalog(files, q, out_dir):
    """Records of index.json (the generated catalogue in the root) whose path, title, act_id, subject or
    keywords contain q; without q – all of them."""
    hit = [f for f in files if f.get("folder", "") == "" and f.get("name") == "index.json"]
    if not hit:
        sys.exit("NOT_FOUND: в корена на базата няма index.json")
    res = call({"action": "download", "id": hit[0]["id"]})
    try:
        records = json.loads(res["content"])["files"]
    except (KeyError, TypeError, ValueError):
        sys.exit("N8N_UNAVAILABLE: index.json не е във формата на каталога")
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "index.json"), "w", encoding="utf-8") as fh:
        fh.write(res["content"])
    if q:
        needle = norm(q).replace("з", "z")
        def text(r):
            parts = [r.get("path"), r.get("title"), r.get("act_id"), r.get("subject")] + list(r.get("keywords") or [])
            return norm(" ".join(str(x) for x in parts if x))
        records = [r for r in records if norm(q) in text(r) or needle in text(r).replace("з", "z")]
    keep = ("path", "in_force", "in_force_note", "superseded_by", "act_id", "subject", "articles", "map")
    print(json.dumps({"count": len(records), "files": [{k: r.get(k) for k in keep} for r in records]},
                     ensure_ascii=False, indent=1))


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("list", help="файловете в базата")
    p.add_argument("--folder", help='само тази папка ("" = корена)')
    p.add_argument("--name", help="името съдържа този текст")
    p = sub.add_parser("index", help="сваля текущия индекс (_INDEX_*.md)")
    p.add_argument("-o", "--output", default="regs", help="папка за свалените файлове (по подразбиране regs)")
    p = sub.add_parser("katalog", help="записите от index.json – статус, заменена редакция, карта")
    p.add_argument("--q", help="търси в пътя, заглавието, act_id, subject и keywords")
    p.add_argument("-o", "--output", default="regs", help="папка за index.json (по подразбиране regs)")
    p = sub.add_parser("figuri", help="сваля картинките, към които сочи файлът (assets/)")
    p.add_argument("what", help="име, път, част от името или Drive ID на текстовия файл")
    p.add_argument("-o", "--output", default="fig", help="папка за картинките (по подразбиране fig)")
    p = sub.add_parser("get", help="сваля един файл")
    p.add_argument("what", help="име, път, част от името или Drive ID")
    p.add_argument("-o", "--output", default="regs", help="папка за свалените файлове (по подразбиране regs)")
    a = ap.parse_args()

    files = listing()
    if a.cmd == "list":
        if a.folder is not None:
            files = [f for f in files if norm(f.get("folder")) == norm(a.folder)]
        if a.name:
            files = [f for f in files if norm(a.name) in norm(f.get("name"))]
        rows = [{"path": f["path"], "id": f["id"], "modified_at": f.get("modified_at"), "size": f.get("size")}
                for f in files]
        print(json.dumps({"count": len(rows), "files": rows}, ensure_ascii=False, indent=1))
    elif a.cmd == "katalog":
        katalog(files, a.q, a.output)
    elif a.cmd == "index":
        idx = [f for f in files if f.get("folder", "") == "" and f.get("name", "").startswith("_INDEX_")]
        if not idx:
            sys.exit("NOT_FOUND: в корена на базата няма файл, започващ с _INDEX_")
        idx.sort(key=lambda f: (f.get("modified_at") or "", f.get("name") or ""))
        download(idx[-1], a.output)
    elif a.cmd == "figuri":
        figuri(files, a.what, a.output)
    else:
        f = resolve(files, a.what)
        if f.get("folder") == "assets":
            print(json.dumps(download_asset(f, a.output), ensure_ascii=False))
        else:
            download(f, a.output)


if __name__ == "__main__":
    main()
