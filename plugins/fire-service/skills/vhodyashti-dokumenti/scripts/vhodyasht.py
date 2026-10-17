#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
vhodyasht.py — обработва данните, разчетени от входящ документ (постановление за експертиза,
писмо от РУ МВР, прокуратура или съд, заявление за удостоверение, призовка), и подготвя
следващата стъпка: кой скил продължава, срокът, файлът за календара и попълнените полета.

Документа го чете Claude (снимка, скан, PDF) и записва разчетеното в data.json. Скриптът не
пипа мрежата: проверява и нормализира полетата, смята срока, пише файловете и казва какво липсва.

    python3 scripts/vhodyasht.py obraboti data.json --out-dir ПАПКА
    python3 scripts/vhodyasht.py srok --ot 2026-10-17 --dni 7
    python3 scripts/vhodyasht.py srok --ot 2026-10-17 --mesetsi 1
    python3 scripts/vhodyasht.py srok --do 2026-11-14

obraboti пише в ПАПКА (само каквото е приложимо):
    kalendar.ics           – срокът (събитие за цял ден с напомняния) или заседанието (с час)
    eptz_meta.chast.json   – полетата на постановлението за meta.json на скила eptz
    pismo.chast.json       – полетата на придружителното писмо за udostovereniya-pozhari
    udostoverenie.chast.json – адресатът на удостоверението за udostovereniya-pozhari
и отпечатва JSON: {"ok", "vid", "skil", "srok", "zasedanie", "lipsva", "preduprezhdeniya", "failove", "rezyume"}.

data.json (празните полета се пропускат):
{
  "vid": "postanovlenie_spte",     // postanovlenie_spte | iskane_dokumenti | zayavlenie_udostoverenie | prizovka | drugo
  "izprashtach": {"institutsiya": "Първо РУ – Плевен", "dlazhnost": "разследващ полицай", "ime": "Иван Дъбов"},
  "reg_no": "1234р-56789",          // регистрационният номер на входящия документ
  "data_dokument": "2026-10-15",    // датата на документа
  "data_poluchavane": "2026-10-17", // кога е получен; няма → датата на документа, после днес
  "postanovlenie_no": "1234р-56789",// само за постановление, ако е различен от reg_no
  "zm_no": "123/2026", "zm_opis": "Първо РУ – Плевен",
  "dp_no": "1234/2026", "prokuratura": "РП – Плевен",
  "proizshestvie": {"data": "2026-10-01", "masto": "с. Буковлък", "adres": "…", "obekt": "къща"},
  "vaprosi": ["Къде се намира огнището на пожара?", "…"],
  "srok": {"data": "2026-11-14"},   // или {"dni": 7}, {"rabotni_dni": 5}, {"sedmitsi": 2}, {"mesetsi": 1};
                                    //    "ot": "poluchavane" (по подразбиране) | "dokument"
  "iskani_dokumenti": ["заверени копия на телефонограмата", "…"],
  "zayavitel": {"ime": "Мария Петрова", "adres": ["ГР. ПЛЕВЕН", "ОБЩ. ПЛЕВЕН", "УЛ. „ПРИМЕРНА“ № 1"],
                "pred": "ЗАД „…“ АД", "mps": "„Рено Клио“ с ДКН …"},
  "zasedanie": {"data": "2026-11-20", "chas": "10:00", "sad": "Районен съд – Плевен", "zala": "…", "delo": "…"},
  "belezhki": "свободен текст – нещо важно от документа, което не е в полетата"
}

Сроковете се броят по правилата на НПК (чл. 183) и ГПК (чл. 60): денят, от който тече срокът, не
се брои; срок в седмици или месеци изтича в съответния ден на последната седмица или месец (ако
в месеца няма такъв ден – в последния му ден); изтичащ в неработен ден срок свършва в първия
следващ работен ден. Неработни са събота, неделя, официалните празници и преместените почивни
дни за празник в почивен ден (чл. 154 КТ). Дни, обявени за неработни с решение на Министерския
съвет, скриптът не знае – затова и срокът никога не се мести назад.
Изричната дата („в срок до 14.11.2026 г.“) не се мести – ако е неработен ден, само се предупреждава.
"""
import argparse
import datetime
import json
import os
import re
import sys
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))
SHARED_SCRIPTS = os.path.join(HERE, "..", "_shared", "scripts")
sys.path.insert(0, SHARED_SCRIPTS)

VIDOVE = {
    "postanovlenie_spte": ("eptz", "постановление за назначаване на съдебна пожаро-техническа експертиза"),
    "iskane_dokumenti": ("udostovereniya-pozhari", "писмо с искане на документи за произшествие"),
    "zayavlenie_udostoverenie": ("udostovereniya-pozhari", "заявление за удостоверение за възникнало произшествие"),
    "prizovka": (None, "призовка за съдебно заседание"),
    "drugo": (None, "друг входящ документ"),
}
DAYS = ["понеделник", "вторник", "сряда", "четвъртък", "петък", "събота", "неделя"]
WEEKDAY_SHORT = ["пн", "вт", "ср", "чт", "пт", "сб", "нд"]


# ── small helpers ────────────────────────────────────────────────────────────

def out(obj):
    print(json.dumps(obj, ensure_ascii=False, indent=2))


def fail(msg):
    out({"ok": False, "error": msg})
    sys.exit(1)


def parse_date(value, field):
    """ISO (2026-10-17) or Bulgarian (17.10.2026, 17.10.2026 г.) → date."""
    if value in (None, ""):
        return None
    if isinstance(value, datetime.date):
        return value
    s = str(value).strip().rstrip(".").replace(" г", "").replace("г", "").strip().rstrip(".")
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d.%m.%y", "%d/%m/%Y"):
        try:
            return datetime.datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    fail(f"{field}: „{value}“ не е дата (ГГГГ-ММ-ДД или ДД.ММ.ГГГГ)")


def parse_time(value, field):
    if value in (None, ""):
        return None
    m = re.fullmatch(r"\s*(\d{1,2})[:.](\d{2})\s*(ч\.?)?\s*", str(value))
    if not m or int(m.group(1)) > 23 or int(m.group(2)) > 59:
        fail(f"{field}: „{value}“ не е час (ЧЧ:ММ)")
    return datetime.time(int(m.group(1)), int(m.group(2)))


def bg(d):
    return f"{d.day:02d}.{d.month:02d}.{d.year} г."


def bg_day(d):
    return f"{bg(d)} ({DAYS[d.weekday()]})"


def typo(text):
    """The common typography: „№ 4“ with a space and the en dash between spaces."""
    if not isinstance(text, str):
        return text
    t = re.sub(r"№\s*(?=\S)", "№ ", text)
    t = re.sub(r"\s+[-—]\s+", " – ", t)
    return t.strip()


def two_names(name):
    """People are written with first name and surname only („Иван Георгиев Дъбов“ → „Иван Дъбов“).
    Initials and single words stay as they are."""
    if not name:
        return name
    parts = str(name).split()
    if len(parts) == 3 and all(len(p.rstrip(".")) > 1 for p in parts):
        return f"{parts[0]} {parts[2]}"
    return " ".join(parts)


def number_part(value):
    """„№ 123/2026 г.“, „123/2026“ → „123/2026“."""
    if not value:
        return value
    s = str(value).strip()
    s = re.sub(r"^(ЗМ|ДП|рег\.?|рег\. ?№|пр\. ?пр\.)\s*", "", s, flags=re.I)
    s = s.replace("№", "").strip()
    s = re.sub(r"\s*г\.?$", "", s).strip()
    return re.sub(r"\s*/\s*", "/", s)


# ── non-working days and deadlines ───────────────────────────────────────────

def _holidays(year):
    try:
        from grafik import holidays  # the official holidays and the moved days off (_shared/scripts/grafik.py)
        return holidays(year, moved=True)
    except Exception:  # noqa: BLE001 – without the shared module only weekends count
        return {}


def non_working(d):
    """None for a working day, else the reason."""
    if d.weekday() >= 5:
        return DAYS[d.weekday()]
    name = _holidays(d.year).get(d)
    return name or None


def next_working(d):
    moved = []
    while True:
        why = non_working(d)
        if not why:
            return d, moved
        moved.append(f"{bg(d)} – {why}")
        d += datetime.timedelta(days=1)


def add_months(d, n):
    y, m = divmod(d.month - 1 + n, 12)
    y, m = d.year + y, m + 1
    import calendar
    return datetime.date(y, m, min(d.day, calendar.monthrange(y, m)[1]))


def compute_deadline(start, dni=None, rabotni_dni=None, sedmitsi=None, mesetsi=None, do=None):
    """{"data", "den", "pravilo", "premestena_ot", "neraboten"} – see the module docstring."""
    if do:
        why = non_working(do)
        return {"data": do.isoformat(), "data_bg": bg(do), "den": DAYS[do.weekday()],
                "pravilo": "изрична дата в документа",
                **({"neraboten": f"{bg(do)} е неработен ден ({why}) – срокът е оставен, както е в документа; "
                                  f"ако трябва, той изтича в първия работен ден след него"} if why else {})}
    if start is None:
        fail("за срок в дни, седмици или месеци трябва начална дата (--ot)")
    if rabotni_dni:
        d, left = start, int(rabotni_dni)
        while left:
            d += datetime.timedelta(days=1)
            if not non_working(d):
                left -= 1
        rule = f"{rabotni_dni} работни дни от {bg(start)}"
        end, moved = d, []
    else:
        if dni:
            end, rule = start + datetime.timedelta(days=int(dni)), f"{dni} дни от {bg(start)} (началният ден не се брои)"
        elif sedmitsi:
            end, rule = start + datetime.timedelta(weeks=int(sedmitsi)), f"{sedmitsi} седм. от {bg(start)}"
        elif mesetsi:
            end, rule = add_months(start, int(mesetsi)), f"{mesetsi} мес. от {bg(start)}"
        else:
            fail("срокът иска едно от: дни, работни дни, седмици, месеци или дата")
        end, moved = next_working(end)
    res = {"data": end.isoformat(), "data_bg": bg(end), "den": DAYS[end.weekday()], "pravilo": rule}
    if moved:
        res["premestena_ot"] = moved
    return res


# ── calendar (.ics) ──────────────────────────────────────────────────────────

VTIMEZONE = """BEGIN:VTIMEZONE
TZID:Europe/Sofia
BEGIN:DAYLIGHT
TZOFFSETFROM:+0200
TZOFFSETTO:+0300
TZNAME:EEST
DTSTART:19700329T030000
RRULE:FREQ=YEARLY;BYMONTH=3;BYDAY=-1SU
END:DAYLIGHT
BEGIN:STANDARD
TZOFFSETFROM:+0300
TZOFFSETTO:+0200
TZNAME:EET
DTSTART:19701025T040000
RRULE:FREQ=YEARLY;BYMONTH=10;BYDAY=-1SU
END:STANDARD
END:VTIMEZONE"""


def ics_escape(text):
    return (str(text).replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n"))


def ics_fold(line):
    """Lines longer than 75 octets are folded (RFC 5545, 3.1)."""
    raw = line.encode("utf-8")
    if len(raw) <= 75:
        return line
    parts, cur = [], b""
    for ch in line:
        b = ch.encode("utf-8")
        if len(cur) + len(b) > (75 if not parts else 74):
            parts.append(cur.decode("utf-8"))
            cur = b""
        cur += b
    parts.append(cur.decode("utf-8"))
    return "\r\n ".join(parts)


def alarm(trigger, text):
    return ["BEGIN:VALARM", "ACTION:DISPLAY", f"DESCRIPTION:{ics_escape(text)}", f"TRIGGER:{trigger}", "END:VALARM"]


def build_ics(events):
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//fire-service-skills//vhodyashti-dokumenti//BG",
             "CALSCALE:GREGORIAN", "METHOD:PUBLISH"]
    if any(e.get("chas") for e in events):
        lines += VTIMEZONE.split("\n")
    for e in events:
        lines += ["BEGIN:VEVENT", f"UID:{e['uid']}", f"DTSTAMP:{stamp}", f"SUMMARY:{ics_escape(e['zaglavie'])}"]
        d = e["data"]
        if e.get("chas"):
            start = datetime.datetime.combine(d, e["chas"])
            end = start + datetime.timedelta(hours=e.get("chasove", 2))
            lines += [f"DTSTART;TZID=Europe/Sofia:{start:%Y%m%dT%H%M%S}",
                      f"DTEND;TZID=Europe/Sofia:{end:%Y%m%dT%H%M%S}"]
        else:
            lines += [f"DTSTART;VALUE=DATE:{d:%Y%m%d}",
                      f"DTEND;VALUE=DATE:{d + datetime.timedelta(days=1):%Y%m%d}", "TRANSP:TRANSPARENT"]
        if e.get("myasto"):
            lines.append(f"LOCATION:{ics_escape(e['myasto'])}")
        if e.get("opisanie"):
            lines.append(f"DESCRIPTION:{ics_escape(e['opisanie'])}")
        for trig, text in e.get("napomnyaniya", []):
            lines += alarm(trig, text)
        lines.append("END:VEVENT")
    lines.append("END:VCALENDAR")
    return "\r\n".join(ics_fold(l) for l in lines) + "\r\n"


# ── the document ─────────────────────────────────────────────────────────────

def clean(obj):
    """Typography on every string; names of people reduced to two names."""
    if isinstance(obj, dict):
        return {k: (two_names(clean(v)) if k == "ime" else clean(v)) for k, v in obj.items() if v not in (None, "", [], {})}
    if isinstance(obj, list):
        return [clean(v) for v in obj if v not in (None, "", [], {})]
    return typo(obj) if isinstance(obj, str) else obj


def institution_lines(inst):
    """The addressee block of a letter to the sender institution („ДО“ is in the template)."""
    up = inst.upper()
    if re.search(r"\bРУ\b|РАЙОННО УПРАВЛЕНИЕ|ОДМВР|\bРС\b|СЛУЖБА|ОТДЕЛ|СЕКТОР", up):
        return ["НАЧАЛНИКА НА", up]
    if "СЪД" in up:
        return ["ПРЕДСЕДАТЕЛЯ НА", up]
    return [up]


def salutation_for(inst):
    up = inst.upper()
    if "ПРОКУРАТУРА" in up:
        return "УВАЖАЕМИ ГОСПОДИН ПРОКУРОР,"
    if re.search(r"\bРУ\b|РАЙОННО УПРАВЛЕНИЕ|ОДМВР|СЛУЖБА|ОТДЕЛ|СЕКТОР", up):
        return "УВАЖАЕМИ ГОСПОДИН НАЧАЛНИК,"
    return None


def cmd_obraboti(a):
    try:
        raw = json.load(open(a.data, encoding="utf-8"))
    except (OSError, ValueError) as e:
        fail(f"{a.data}: {e}")
    data = clean(raw)
    vid = data.get("vid") or "drugo"
    if vid not in VIDOVE:
        fail(f"vid: „{vid}“ – трябва едно от: {', '.join(VIDOVE)}")
    skil, vid_text = VIDOVE[vid]
    today = datetime.date.fromisoformat(a.dnes) if a.dnes else datetime.date.today()
    izp = data.get("izprashtach") or {}
    inst = izp.get("institutsiya", "")
    lipsva, warn, files, events = [], [], {}, []

    d_doc = parse_date(data.get("data_dokument"), "data_dokument")
    d_pol = parse_date(data.get("data_poluchavane"), "data_poluchavane")
    reg = number_part(data.get("reg_no"))
    if not d_doc:
        lipsva.append("датата на документа")
    if not reg and vid != "zayavlenie_udostoverenie":
        lipsva.append("регистрационният номер на документа")
    if not inst and vid != "zayavlenie_udostoverenie":
        lipsva.append("изпращачът (институцията)")

    # ── deadline ──
    srok = None
    s = data.get("srok") or {}
    if s:
        if s.get("data"):
            srok = compute_deadline(None, do=parse_date(s["data"], "srok.data"))
        else:
            ot = s.get("ot", "poluchavane")
            start = (d_doc if ot == "dokument" else d_pol) or d_pol or d_doc
            if start is None:
                start = today
                warn.append(f"срокът е броен от днес ({bg(today)}) – в документа няма дата на получаване; "
                            f"кажи датата на получаване, ако е друга")
            elif ot != "dokument" and not d_pol:
                warn.append(f"срокът е броен от датата на документа ({bg(start)}), защото датата на получаване "
                            f"не е дадена – по правило тече от получаването")
            srok = compute_deadline(start, dni=s.get("dni"), rabotni_dni=s.get("rabotni_dni"),
                                    sedmitsi=s.get("sedmitsi"), mesetsi=s.get("mesetsi"))
        end = datetime.date.fromisoformat(srok["data"])
        srok["ostavat_dni"] = (end - today).days
        if end < today:
            warn.append(f"срокът ({srok['data_bg']}) е изтекъл")
        elif (end - today).days <= 3:
            warn.append(f"срокът изтича след {(end - today).days} дни ({srok['data_bg']})")
    elif vid in ("postanovlenie_spte", "iskane_dokumenti"):
        warn.append("в документа не е разчетен срок – провери го на снимката; без срок няма напомняне")

    # ── per kind ──
    pr = data.get("proizshestvie") or {}
    pr_date = parse_date(pr.get("data"), "proizshestvie.data")
    rezyume = [f"{vid_text[0].upper()}{vid_text[1:]}" + (f" от {inst}" if inst else "")
               + (f", рег. № {reg}" if reg else "") + (f"/{bg(d_doc)}" if reg and d_doc else (f" от {bg(d_doc)}" if d_doc else ""))]

    if vid == "postanovlenie_spte":
        post_no = number_part(data.get("postanovlenie_no")) or reg
        zm, dp = number_part(data.get("zm_no")), number_part(data.get("dp_no"))
        meta = {"zm_no": zm, "zm_opis": data.get("zm_opis") or inst, "dp_no": dp,
                "postanovlenie_no": post_no, "postanovlenie_date": bg(d_doc) if d_doc else "",
                "naznachil": (lambda who: who + (f" при {inst}" if inst else "") if who else "")(
                    " ".join(x for x in (izp.get("dlazhnost"), izp.get("ime")) if x)),
                "copies": ["деловодство", data.get("zm_opis") or inst] if (data.get("zm_opis") or inst) else ["деловодство"]}
        prok = data.get("prokuratura", "")
        m = re.fullmatch(r"РП\s*–\s*(.+)", prok)
        if m:
            meta["rp_grad"] = m.group(1)
        elif prok:
            meta["prokuratura"] = prok
        meta = {k: v for k, v in meta.items() if v not in (None, "", [])}
        for key, label in (("zm_no", "№ на ЗМ"), ("dp_no", "№ на ДП"), ("postanovlenie_no", "№ на постановлението"),
                           ("naznachil", "кой е назначил експертизата")):
            if not meta.get(key):
                lipsva.append(label)
        if not data.get("vaprosi"):
            lipsva.append("въпросите към вещото лице")
        if not prok:
            warn.append("прокуратурата не е разчетена – по подразбиране в ЕПТЗ е „РП – Плевен“")
        files["eptz_meta.chast.json"] = meta
        if zm or dp:
            rezyume.append(" и ".join(x for x in ((f"ЗМ № {zm}" if zm else ""), (f"ДП № {dp}" if dp else "")) if x))
        if data.get("vaprosi"):
            rezyume.append(f"{len(data['vaprosi'])} въпроса към вещото лице")
    elif vid == "iskane_dokumenti":
        pismo = {"kind": "pridruzhitelno"}
        if inst:
            pismo["addressee"] = institution_lines(inst)
            sal = salutation_for(inst)
            if sal:
                pismo["salutation"] = sal
            pismo["copies"] = ["деловодство", inst]
        att = " ".join(x for x in (izp.get("dlazhnost"), izp.get("ime")) if x)
        if att and izp.get("ime"):
            pismo["attention"] = att[0].upper() + att[1:]
        if reg and d_doc:
            pismo["reference"] = f"На Ваш рег. № {reg}/{bg(d_doc)}"
        files["pismo.chast.json"] = pismo
        if not pr_date:
            lipsva.append("датата на произшествието")
        if data.get("iskani_dokumenti"):
            rezyume.append("искат: " + "; ".join(data["iskani_dokumenti"]))
    elif vid == "zayavlenie_udostoverenie":
        z = data.get("zayavitel") or {}
        ud = {"kind": "udostoverenie"}
        if z.get("ime"):
            ud["ime"] = z["ime"]
            ud["copies"] = ["деловодство", z["ime"]]
        if z.get("adres"):
            ud["adres"] = [l.upper() for l in z["adres"]] if isinstance(z["adres"], list) else [z["adres"].upper()]
        if z.get("pred"):
            ud["pred"] = z["pred"]
        if z.get("mps"):
            ud["mps"] = z["mps"]
        files["udostoverenie.chast.json"] = ud
        if not z.get("ime"):
            lipsva.append("името на заявителя")
        if not z.get("adres"):
            lipsva.append("адресът на заявителя")
        if not pr_date:
            lipsva.append("датата на произшествието")
    elif vid == "prizovka":
        z = data.get("zasedanie") or {}
        zd = parse_date(z.get("data"), "zasedanie.data")
        zt = parse_time(z.get("chas"), "zasedanie.chas")
        if not zd:
            lipsva.append("датата на заседанието")
        if not zt:
            lipsva.append("часът на заседанието")
        if zd:
            where = ", ".join(x for x in (z.get("sad"), (f"зала {z['zala']}" if z.get("zala") and not str(z['zala']).lower().startswith("зала") else z.get("zala"))) if x)
            title = "Съдебно заседание – вещо лице" + (f", {z['delo']}" if z.get("delo") else "")
            events.append({"uid": f"{uuid.uuid4()}@fire-service", "zaglavie": title, "data": zd, "chas": zt,
                           "myasto": where, "opisanie": "Да се вземат ЕПТЗ, сметката и документ за самоличност."
                           + (f"\nПризовката: {inst}, рег. № {reg}" if reg else ""),
                           "napomnyaniya": [("-P1D", "Утре – съдебно заседание"), ("-PT2H", "След 2 часа – съдебно заседание")]})
            rezyume.append(f"заседание на {bg_day(zd)}" + (f" от {zt:%H:%M} ч." if zt else "") + (f", {where}" if where else ""))
            if zd < today:
                warn.append(f"заседанието ({bg(zd)}) е минало")

    if pr_date or pr.get("masto"):
        rezyume.append("произшествие " + ", ".join(x for x in ((f"от {bg(pr_date)}" if pr_date else ""), pr.get("masto", ""),
                                                             pr.get("obekt", "")) if x))
    if srok:
        rezyume.append(f"срок {srok['data_bg']} ({srok['den']})")
        names = {"postanovlenie_spte": "ЕПТЗ", "iskane_dokumenti": "отговор с документите",
                 "zayavlenie_udostoverenie": "удостоверение", "prizovka": "отговор", "drugo": "отговор"}
        ref = " ".join(x for x in ((f"ЗМ № {number_part(data.get('zm_no'))}" if data.get("zm_no") else ""),
                                   (f"рег. № {reg}" if reg else "")) if x)
        desc = "\n".join(x for x in (vid_text[0].upper() + vid_text[1:] + (f" от {inst}" if inst else ""), ref,
                                     ("Произшествие: " + ", ".join(y for y in ((bg(pr_date) if pr_date else ""), pr.get("masto", ""), pr.get("obekt", "")) if y)) if (pr_date or pr.get("masto")) else "",
                                     f"Срок: {srok['pravilo']}") if x)
        events.append({"uid": f"{uuid.uuid4()}@fire-service",
                       "zaglavie": f"Срок: {names[vid]}" + (f" – {inst}" if inst else "") + (f", {ref}" if ref else ""),
                       "data": datetime.date.fromisoformat(srok["data"]), "opisanie": desc,
                       "napomnyaniya": [("-P2DT16H", "След 3 дни изтича срокът"), ("-PT16H", "Утре изтича срокът")]})

    os.makedirs(a.out_dir, exist_ok=True)
    written = []
    for name, obj in files.items():
        p = os.path.join(a.out_dir, name)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=2)
        written.append(p)
    if events:
        p = os.path.join(a.out_dir, "kalendar.ics")
        with open(p, "w", encoding="utf-8", newline="") as f:
            f.write(build_ics(events))
        written.append(p)

    out({"ok": True, "vid": vid, "vid_text": vid_text, "skil": skil,
         "proizshestvie": {**({"data": pr_date.isoformat()} if pr_date else {}),
                           **{k: v for k, v in pr.items() if k != "data"}},
         "vaprosi": data.get("vaprosi", []), "srok": srok,
         "zasedanie": data.get("zasedanie"), "lipsva": lipsva, "preduprezhdeniya": warn,
         "failove": written, "rezyume": "; ".join(rezyume) + "."})
    return 0


def cmd_srok(a):
    start = parse_date(a.ot, "--ot")
    do = parse_date(a.do, "--do")
    out({"ok": True, **compute_deadline(start, dni=a.dni, rabotni_dni=a.rabotni_dni,
                                        sedmitsi=a.sedmitsi, mesetsi=a.mesetsi, do=do)})
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="Входящ документ → следваща стъпка, срок и календар")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("obraboti", help="data.json с разчетения документ → файловете и резюмето")
    p.add_argument("data")
    p.add_argument("--out-dir", required=True)
    p.add_argument("--dnes", help="днешната дата ГГГГ-ММ-ДД (за тестове)")
    p.set_defaults(fn=cmd_obraboti)
    p = sub.add_parser("srok", help="изчислява срок")
    p.add_argument("--ot", help="началната дата (денят на получаване)")
    p.add_argument("--dni", type=int)
    p.add_argument("--rabotni-dni", type=int)
    p.add_argument("--sedmitsi", type=int)
    p.add_argument("--mesetsi", type=int)
    p.add_argument("--do", help="изрична крайна дата")
    p.set_defaults(fn=cmd_srok)
    a = ap.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
