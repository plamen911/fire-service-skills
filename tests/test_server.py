#!/usr/bin/env python3
"""The personal key, the mail and the incident search – against a local stand-in for the server.

Nothing here reaches n8n: a small HTTP server on 127.0.0.1 plays its part and records what it was sent.
Run from the repository root:  python3 tests/test_server.py
"""
import base64
import contextlib
import http.server
import io
import json
import os
import subprocess
import sys
import tempfile
import threading

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHARED = os.path.join(ROOT, "plugins", "fire-service", "shared", "scripts")
os.environ.pop("FIRE_SERVICE_NO_KEY", None)
os.environ.pop("FIRE_SERVICE_KEY", None)
sys.path.insert(0, SHARED)
import api_config  # noqa: E402
import fetch_incidents  # noqa: E402
import kais  # noqa: E402
import poshta  # noqa: E402

failures = []
FAKE = "stub-key-for-tests"


def check(cond, msg):
    print(("  ok  " if cond else "  FAIL ") + msg)
    if not cond:
        failures.append(msg)


class Stub(http.server.BaseHTTPRequestHandler):
    plan, seen = [], []

    def do_POST(self):  # noqa: N802
        raw = self.rfile.read(int(self.headers.get("Content-Length") or 0))
        Stub.seen.append({"path": self.path, "key": self.headers.get("X-Api-Key"), "body": json.loads(raw or b"{}")})
        status, body = Stub.plan.pop(0) if Stub.plan else (200, "{}")
        self.send_response(status)
        self.end_headers()
        self.wfile.write((body if isinstance(body, str) else json.dumps(body, ensure_ascii=False)).encode("utf-8"))

    def log_message(self, *a):
        pass


def call(fn, argv):
    """Run a script's main() in-process → (exit message or None, stdout, stderr)."""
    out, err, old = io.StringIO(), io.StringIO(), sys.argv
    sys.argv = ["x"] + argv
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            fn()
        code = None
    except SystemExit as e:
        code = e.code
    finally:
        sys.argv = old
    return code, out.getvalue(), err.getvalue()


def test_key(tmp):
    """Where the key comes from, in order: the environment, the settings file, the personal skill."""
    settings = os.path.join(tmp, "incident_api.json")
    skill = os.path.join(tmp, "fire-service-key", "SKILL.md")
    os.makedirs(os.path.dirname(skill))
    with open(skill, "w", encoding="utf-8") as f:
        f.write("---\nname: fire-service-key\ndescription: личен ключ\n---\n\nkey: from-the-skill\nexpert_position: инспектор\n")
    real_config, real_files = api_config.CONFIG, api_config._key_skill_files
    api_config.CONFIG, api_config._key_skill_files = settings, lambda: [skill]

    def load(file_key="", env=None, no_key=False):
        with open(settings, "w", encoding="utf-8") as f:
            json.dump({"url": "http://127.0.0.1:9/", "key": file_key}, f)
        api_config._cache.clear()
        for name, value in (("FIRE_SERVICE_KEY", env), ("FIRE_SERVICE_NO_KEY", "1" if no_key else None)):
            os.environ.pop(name, None)
            if value:
                os.environ[name] = value
        return api_config.load()

    try:
        c = load()
        check(c["key"] == "from-the-skill" and c["key_source"] == "скил fire-service-key", "no key elsewhere → the personal skill")
        check(api_config.profile() == {"expert_position": "инспектор"}, "the other lines of the personal skill are the profile, not the key")
        c = load(file_key="from-the-file")
        check(c["key"] == "from-the-file" and c["key_source"] == "incident_api.json", "a key in the settings file wins over the skill")
        c = load(file_key="from-the-file", env="  from-the-env ")
        check(c["key"] == "from-the-env" and c["key_source"] == "FIRE_SERVICE_KEY", "the environment wins over both, trimmed")
        c = load(file_key="from-the-file", env="from-the-env", no_key=True)
        check(c["key"] == "" and c["key_source"] is None and not api_config.has_key(), "FIRE_SERVICE_NO_KEY switches all three off")
        check(api_config.profile() == {}, "… and the profile with them")
        try:
            api_config.request("url", {})
            check(False, "no key → NO_KEY")
        except SystemExit as e:
            check(str(e).startswith("NO_KEY"), "a request without a key stops with NO_KEY before any connection")
        c = load(env="from-the-env")
        check(c["header"] == "X-Api-Key", "the header name has a default")
        try:
            api_config.request("staff_url", {})
            check(False, "missing address")
        except SystemExit as e:
            check("staff_url" in str(e) and "from-the-env" not in str(e), "an address missing from the settings is named; the key is not printed")
        api_config._key_skill_files = lambda: []
        check(load()["key"] == "", "no skill, no file, no variable → no key")
        # the self-check of the module says whether there is a key and where from – never the key itself
        r = subprocess.run([sys.executable, os.path.join(SHARED, "api_config.py")], capture_output=True, text=True,
                           env=dict(os.environ, FIRE_SERVICE_KEY="secret-value-123"))
        told = json.loads(r.stdout)
        check(told["key"] is True and told["key_source"] == "FIRE_SERVICE_KEY" and "secret-value-123" not in r.stdout + r.stderr,
              "api_config.py reports that a key exists, never its value")
        path = os.path.join(tmp, "cache.csv")
        api_config.write_private(path, "x")
        check(os.stat(path).st_mode & 0o777 == 0o600, "cached copies of server data are readable only by their owner")
    finally:
        api_config.CONFIG, api_config._key_skill_files = real_config, real_files
        os.environ.pop("FIRE_SERVICE_KEY", None)
        os.environ.pop("FIRE_SERVICE_NO_KEY", None)
        api_config._cache.clear()


def test_mail(tmp, base):
    doc = os.path.join(tmp, "Plan.docx")
    with open(doc, "wb") as f:
        f.write(b"PK\x03\x04 not a real document")
    Stub.plan, Stub.seen = [(200, {"ok": True, "do": ["ivan@example.bg"], "tema": "План", "faylove": [{"ime": "Plan.docx"}]})], []
    code, out, _ = call(poshta.main, ["--do", "Аз", "--do", " ivan@example.bg ", "--tema", "План", "--tekst", "Здравей", doc])
    sent = Stub.seen[-1]
    check(code is None and out.startswith("Изпратено.") and "Plan.docx" in out, "a sent letter is confirmed with recipient, subject and files")
    check(sent["path"] == "/mail" and sent["key"] == FAKE, "the letter goes to the mail address with the key in the header")
    check(sent["body"]["to"] == ["me", "ivan@example.bg"] and sent["body"]["subject"] == "План" and sent["body"]["dry_run"] is False,
          "„аз“ becomes the sender's own address; the other recipients are trimmed")
    att = sent["body"]["attachments"]
    check(len(att) == 1 and att[0]["name"] == "Plan.docx" and base64.b64decode(att[0]["base64"]) == open(doc, "rb").read(),
          "the attachment travels whole, under its file name")

    Stub.plan, Stub.seen = [(200, {"dry_run": True, "do": ["ivan@example.bg"], "tema": "T", "faylove": []})], []
    code, out, _ = call(poshta.main, ["--do", "az", "--tema", "T", "--tekst", "само текст", "--dry-run"])
    check(out.startswith("Проба – нищо не е изпратено.") and Stub.seen[-1]["body"]["dry_run"] is True and "без прикачени файлове" in out,
          "--dry-run is passed on and reported as a rehearsal")

    Stub.seen = []
    bad = os.path.join(tmp, "run.exe")
    open(bad, "wb").write(b"x")
    code, _, _ = call(poshta.main, ["--do", "az", "--tema", "T", bad])
    check(str(code).startswith("BAD_INPUT") and not Stub.seen, "a file type that is not allowed is refused before anything is sent")
    code, _, _ = call(poshta.main, ["--do", "az", "--tema", "T"])
    check(str(code).startswith("BAD_INPUT") and not Stub.seen, "an empty letter is refused")
    code, _, _ = call(poshta.main, ["--do", "az", "--tema", "T", os.path.join(tmp, "missing.docx")])
    check(str(code).startswith("NO_DATA") and not Stub.seen, "a missing file is reported, nothing is sent")
    big = os.path.join(tmp, "big.pdf")
    with open(big, "wb") as f:
        f.write(b"0" * (poshta.MAX_BYTES + 1))
    code, _, _ = call(poshta.main, ["--do", "az", "--tema", "T", big])
    check(str(code).startswith("BAD_INPUT") and "MB" in str(code) and not Stub.seen, "more than the size limit is refused locally")

    Stub.plan = [(403, {"error": "FORBIDDEN: only your own address"})]
    code, _, _ = call(poshta.main, ["--do", "ivan@example.bg", "--tema", "T", "--tekst", "x"])
    check(str(code) == "FORBIDDEN: only your own address", "the server's own refusal is shown as it is")
    Stub.plan = [(401, {"error": "UNAUTHORIZED: unknown key"})]
    code, _, _ = call(poshta.main, ["--do", "az", "--tema", "T", "--tekst", "x"])
    check(str(code).startswith("KEY_REJECTED") and FAKE not in str(code), "a rejected key is named as such, without printing it")
    Stub.plan = [(500, "<html>boom</html>")]
    code, _, _ = call(poshta.main, ["--do", "az", "--tema", "T", "--tekst", "x"])
    check(str(code).startswith("N8N_UNAVAILABLE: HTTP 500"), "a server failure is N8N_UNAVAILABLE")
    api_config._cache["cfg"] = dict(api_config._cache["cfg"], mail_url="http://127.0.0.1:9/")
    code, _, _ = call(poshta.main, ["--do", "az", "--tema", "T", "--tekst", "x"])
    check(str(code).startswith("N8N_UNAVAILABLE"), "no connection is N8N_UNAVAILABLE")
    api_config._cache["cfg"] = dict(api_config._cache["cfg"], mail_url=base + "mail")


def test_search(tmp):
    rows = [{"id": i, "dat": f"2026-09-{i:02d} 10:00:00", "casulaty": fetch_incidents.FIRE, "location": "Опанец"}
            for i in range(1, 4)]
    Stub.plan, Stub.seen = [(200, {"incidents": rows, "total": 3})], []
    code, out, err = call(fetch_incidents.main, ["--from", "2026-09-01", "--to", "2026-09-24", "--filter", "location=Опанец",
                                                 "--filter", "location=Буковлък", "--sort", "dat:asc", "--limit", "20"])
    body = Stub.seen[-1]["body"]
    check(code is None and json.loads(out) == rows and not err, "the records come back as they were sent")
    check(Stub.seen[-1]["path"] == "/incidents" and Stub.seen[-1]["key"] == FAKE, "the search goes to the incidents address with the key")
    check(body == {"from": "2026-09-01", "to": "2026-09-24", "all": False, "filters": {"location": ["Опанец", "Буковлък"]},
                   "sort": "dat:asc", "limit": 20}, "period, filters (repeated = any of), sort and limit are passed to the server")

    target = os.path.join(tmp, "rec.json")
    Stub.plan = [(200, {"incidents": rows[:2], "total": 3})]
    code, out, err = call(fetch_incidents.main, ["2026-09-01", "--all", "--limit", "2", "-o", target])
    summary = json.loads(out)
    check(summary["returned"] == 2 and summary["total"] == 3 and summary["truncated"] is True and "TRUNCATED: returned 2 of 3" in err,
          "a list cut by the limit is said so, on stdout and on stderr")
    check(json.load(open(target, encoding="utf-8")) == rows[:2] and json.load(open(target + ".meta.json"))["truncated"] is True,
          "… and marked beside the saved file")
    check(Stub.seen[-1]["body"]["all"] is True, "--all is passed on")
    Stub.plan = [(200, {"incidents": rows, "total": 3})]
    code, out, err = call(fetch_incidents.main, ["2026-09-01", "-o", target])
    check(not os.path.exists(target + ".meta.json") and json.loads(out)["truncated"] is False, "a complete list removes the mark")

    # --place: the whole period is asked for and sifted here; the place is not sent as a server filter
    mixed = [dict(rows[0], id=1, location="гр. Плевен", address="гр. Плевен, пътя Плевен-Ясен"),
             dict(rows[1], id=2, location="пътя Плевен-Ясен"), dict(rows[2], id=3)]
    Stub.plan = [(200, {"incidents": mixed, "total": 3})]
    code, out, err = call(fetch_incidents.main, ["2026-09-01", "--all", "--place", "Ясен", "--limit", "1", "-o", target])
    body, summary = Stub.seen[-1]["body"], json.loads(out)
    check(body["limit"] == 5000 and body["filters"] == {} and "place" not in body,
          "--place asks the server for the whole period, without a place filter")
    check(summary["returned"] == 1 and summary["total"] == 2 and summary["truncated"] is True,
          "… the records are sifted locally, then cut by --limit; total is the number that matched")
    check(json.load(open(target, encoding="utf-8"))[0]["matched_in"] == ["address"], "… and say where the place was found")
    Stub.plan = [(200, {"incidents": mixed, "total": 9000})]
    code, _, _ = call(fetch_incidents.main, ["2026-09-01", "--all", "--place", "Ясен"])
    check(str(code).startswith("TOO_MANY_RECORDS"), "--place over a period the server cut → refused, not a silent partial search")

    other = dict(rows[0], id=9, casulaty="техническа помощ")
    Stub.plan = [(200, rows + [other])]                       # an older server answers with the bare list
    code, out, _ = call(fetch_incidents.main, ["2026-09-01", "--limit", "2"])
    check([r["id"] for r in json.loads(out)] == [3, 2], "a bare list from an older server is filtered, sorted and cut locally")

    Stub.plan = [(200, {"rows": []})]
    code, _, _ = call(fetch_incidents.main, ["2026-09-01"])
    check(str(code) == "N8N_UNAVAILABLE: unexpected response shape", "an unexpected answer is not taken for „no records“")
    Stub.plan = [(500, "boom")]
    code, _, _ = call(fetch_incidents.main, ["2026-09-01"])
    check(str(code).startswith("N8N_UNAVAILABLE: HTTP 500"), "a server failure is N8N_UNAVAILABLE")
    Stub.plan = [(403, "no")]
    code, _, _ = call(fetch_incidents.main, ["2026-09-01"])
    check(str(code).startswith("KEY_REJECTED") and FAKE not in str(code), "a rejected key is KEY_REJECTED")
    before = len(Stub.seen)
    code, _, _ = call(fetch_incidents.main, ["2026-09-01", "--filter", "location"])
    check(str(code).startswith("BAD_REQUEST") and len(Stub.seen) == before, "a malformed filter never reaches the server")


# a 1×1 PNG – the stand-in for the cadastral picture
PNG1 = ("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII=")


def test_kais(tmp, base):
    """kais.py: the request, the picture beside the JSON and the beginning of a scheme in local metres."""
    api_config._cache["cfg"] = dict(api_config._cache["cfg"], kais_url=base + "kais")
    x0, y0 = 400000.0, 4800000.0        # an invented parcel and buildings – not a real place
    imot = {"id": "99999.10.20", "vid": "ПИ", "adres": "м. „Примерна“", "plosht_m2": 1200,
            "kontur": [[x0 + 50, y0 + 50], [x0 + 90, y0 + 50], [x0 + 90, y0 + 80], [x0 + 50, y0 + 80], [x0 + 50, y0 + 50]]}
    big = {"id": "99999.10.20.1", "vid": "сграда", "predn": "промишлена сграда", "etazhi": 3, "zastroena_m2": 300,
           "kontur": [[x0 + 55, y0 + 55], [x0 + 85, y0 + 55], [x0 + 85, y0 + 65], [x0 + 55, y0 + 65], [x0 + 55, y0 + 55]]}
    small = {"id": "99999.10.20.2", "vid": "сграда", "predn": "Промишлена сграда", "etazhi": 1, "zastroena_m2": 12,
             "kontur": [[x0 + 60, y0 + 70], [x0 + 64, y0 + 70], [x0 + 64, y0 + 73], [x0 + 60, y0 + 73], [x0 + 60, y0 + 70]]}
    answer = {"ok": True, "action": "obekt", "imot": imot, "sgradi": [big, small],
              "ramka": {"bbox": [x0, y0, x0 + 140, y0 + 130], "radius_m": 40},
              "fon": {"bbox": [x0, y0, x0 + 140, y0 + 130], "px": [1, 1], "png_base64": PNG1},
              "ulitsi": [{"ime": "бул. Примерен", "vid": "secondary", "shirina": 12,     # runs off the terrain on both ends
                          "tochki": [[x0 - 50, y0 + 95], [x0 + 70, y0 + 95], [x0 + 200, y0 + 95]]},
                         {"ime": "бул. Примерен", "vid": "secondary", "shirina": 12, "tochki": [[x0 + 100, y0 + 95], [x0 + 105, y0 + 95]]},
                         {"ime": "", "vid": "service", "shirina": 5, "tochki": [[x0 + 300, y0 + 300], [x0 + 310, y0 + 310]]}],
              "istochnik": "КАИС", "zaiavki_kais": 9}
    Stub.plan, Stub.seen = [(200, answer)], []
    out, sh = os.path.join(tmp, "k", "kais.json"), os.path.join(tmp, "k", "shema.json")
    code, printed, err = call(kais.main, ["obekt", "--link", "43.41,24.65", "-o", out, "--shema", sh])
    sent = Stub.seen[-1]
    check(code is None, "obekt answers" + (": " + err if code else ""))
    check(sent["path"] == "/kais" and sent["key"] == FAKE and sent["body"] == {"action": "obekt", "fon": False, "radius_m": 40,
                                                                                "lat": 43.41, "lon": 24.65},
          "a „ширина,дължина“ point goes to the КАИС address with the key and the radius – no picture by default")
    d = json.load(open(sh, encoding="utf-8"))
    check("fon" not in d and d["imot"]["etiket"] == "ПИ 99999.10.20", "by default: the parcel's boundary, no picture")
    u = d["ulitsi"]
    check(len(u) == 2 and u[0]["tochki"] == [[0, 85], [60, 85], [120, 85]] and u[0]["shirina"] == 12,
          "a street is cut to the terrain; one far away is left out")
    check(u[0]["ime"] == "бул. „Примерен“" and u[1]["ime"] == "", "the name once, on the longest piece, in „…“")
    Stub.plan = [(200, answer)]
    code, printed, err = call(kais.main, ["obekt", "--link", "43.41,24.65", "-o", out, "--shema", sh, "--fon"])
    check(code is None and Stub.seen[-1]["body"]["fon"] is True, "--fon asks for the picture")
    fon = os.path.join(tmp, "k", "kais_fon.png")
    saved = json.load(open(out, encoding="utf-8"))
    check(os.path.exists(fon) and open(fon, "rb").read()[1:4] == b"PNG" and "png_base64" not in json.dumps(saved),
          "the picture is saved beside the JSON, not inside it")
    d = json.load(open(sh, encoding="utf-8"))
    check(d["teren"] == [120, 110] and d["kais"]["x0"] == x0 + 10 and d["kais"]["y0"] == y0 + 10,
          "the terrain is the parcel plus the radius, its origin kept in КС2005")
    check(d["imot"]["kontur"][0] == [40, 40] and len(d["imot"]["kontur"]) == 4 and d["imot"]["etiket"] == "ПИ 99999.10.20",
          "the parcel's outline in local metres, without the closing point")
    Stub.plan = [(200, answer)]
    call(kais.main, ["obekt", "--id", "99999.10.20", "-o", out, "--shema", sh, "--bez-granitsa"])
    check("imot" not in json.load(open(sh, encoding="utf-8")), "--bez-granitsa leaves the boundary out")
    check(kais.clip_polyline([[-5, 5], [5, 5], [5, 15], [15, 15]], 0, 0, 10, 10) == [[(0.0, 5.0), (5.0, 5.0), (5.0, 10.0)]],
          "clipping keeps the inside part of a bent line")
    check(kais.street_name("ул. Васил Левски") == "ул. „Васил Левски“" and kais.street_name("Северна промишлена зона") ==
          "Северна промишлена зона", "street names get „…“, other names stay")
    check(d["fon"]["ramka"] == [-10, -10, 130, 120], "the picture is placed by its own frame")
    b1, b2 = d["sgradi"]
    check(b1["etiket"] == "Промишлена сграда" and b1["etazhnost"] == "+3" and b1["kontur"][0] == [45, 45],
          "a building: its purpose with a capital letter, the floors, the outline")
    check(b2["etiket"] == "" and b2["razmeri"] is False, "an annex narrower than 8 m – no name and no dimensions")
    summary = json.loads(printed)
    check(summary["sgradi"][0]["razmeri_m"] == [30.0, 10.0] and any("сутерен" in z for z in summary["zabelezhki"]),
          "the walls' lengths and the reminder that КАИС has no basements or categories")
    Stub.plan = [(400, {"error": "BAD_REQUEST: lat/lon извън България [line 185]"})]
    code, _, err = call(kais.main, ["obekt", "--lat", "40", "--lon", "24"])
    check(code == 2 and err.startswith("BAD_INPUT: lat/lon извън България") and "[line" not in err,
          "a refused point is BAD_INPUT, without the node's line number")
    Stub.plan = [(404, {"error": "NOT_FOUND: 99999.10.21 не е намерен в КАИС"})]
    code, _, err = call(kais.main, ["obekt", "--id", "99999.10.21", "-o", out])
    check(code == 2 and err.startswith("NOT_FOUND"), "an unknown identifier is NOT_FOUND")
    x, y = kais.wgs_to_kc(43.4125702, 24.6504731)
    check(abs(x - 431194.0109) < 0.01 and abs(y - 4808897.5614) < 0.01, "КС2005 as EPSG:7801 (checked against PROJ)")
    la, lo = kais.kc_to_wgs(x, y)
    check(abs(la - 43.4125702) < 1e-8 and abs(lo - 24.6504731) < 1e-8, "… and back")


def main():
    with tempfile.TemporaryDirectory() as tmp:
        test_key(tmp)
        srv = http.server.HTTPServer(("127.0.0.1", 0), Stub)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        base = f"http://127.0.0.1:{srv.server_port}/"
        api_config._cache["cfg"] = {"key": FAKE, "key_source": "test", "header": "X-Api-Key",
                                    "url": base + "incidents", "mail_url": base + "mail"}
        api_config.RETRY_PAUSE = 0
        test_mail(tmp, base)
        test_search(tmp)
        test_kais(tmp, base)
        srv.shutdown()
    print("\nALL PASS" if not failures else f"\n{len(failures)} FAILED")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
