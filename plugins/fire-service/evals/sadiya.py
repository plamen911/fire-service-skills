#!/usr/bin/env python3
"""ИИ съдия за целите заключения от evals – вместо съдията на `claude plugin eval`.

Съдията на `plugin eval` отхвърля всеки дълъг документ (около 10 000 знака), включително верните.
Този скрипт пуска проверките от `<случай>/sadiya.yaml` направо през `claude -p` (Sonnet, 3 гласа,
мнозинство) и показва за всяка PASS/FAIL с причината и цитат.

    # след `claude plugin eval . --tag output --keep-temp --output-dir РЕЗУЛТАТИ`
    python3 evals/sadiya.py РЕЗУЛТАТИ
    # или за един отчет
    python3 evals/sadiya.py --case eptz/zaklyuchenie-bez-oglet --report path/report.md

Ползва абонамента, с който е влязъл `claude` (не API ключ, освен ако е зададен ANTHROPIC_API_KEY).
Записва `sadiya.json` до `aggregate-result.json`. Изход 1, ако има FAIL.
"""
import argparse
import concurrent.futures as cf
import glob
import json
import os
import re
import subprocess
import sys

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
VOTES = 3
INSTRUCTION = ("Първи ред: само PASS или FAIL. После до две изречения защо, с цитат от текста "
               "(при FAIL – цитирай проблемното място).")


def case_dir(name):
    """'eptz-zaklyuchenie-bez-oglet' or 'eptz/zaklyuchenie-bez-oglet' -> the case folder."""
    if os.path.isdir(os.path.join(HERE, name)):
        return os.path.join(HERE, name)
    for d in glob.glob(os.path.join(HERE, "*", "*")):
        if os.path.basename(os.path.dirname(d)) + "-" + os.path.basename(d) == name:
            return d
    return None


def materiali(cdir):
    """The case materials, verbatim: the prompt from the постановление on."""
    prompt = yaml.safe_load(open(os.path.join(cdir, "case.yaml"), encoding="utf-8"))["execution"]["prompt"]
    i = prompt.find("ПОСТАНОВЛЕНИЕ")
    return (prompt[i:] if i >= 0 else prompt).rstrip()


def one_vote(criteria, text, model):
    prompt = f"Ти си съдия. Критерий:\n{criteria}\n\nТекст за оценка:\n<<<\n{text}\n>>>\n\n{INSTRUCTION}"
    r = subprocess.run(["claude", "-p", "--model", model, prompt], capture_output=True, text=True, timeout=600)
    out = r.stdout.strip()
    first = out.splitlines()[0] if out else ""
    verdict = "PASS" if re.search(r"\bPASS\b", first) and not re.search(r"\bFAIL\b", first) else "FAIL"
    return verdict, out


def judge(cdir, report, model):
    checks = yaml.safe_load(open(os.path.join(cdir, "sadiya.yaml"), encoding="utf-8"))["proverki"]
    text = open(report, encoding="utf-8").read()
    mat = materiali(cdir)
    jobs = [(c["name"], c["criteria"].replace("{materiali}", mat)) for c in checks]
    results = []
    with cf.ThreadPoolExecutor(len(jobs) * VOTES) as ex:
        futs = {name: [ex.submit(one_vote, crit, text, model) for _ in range(VOTES)] for name, crit in jobs}
        for name, fs in futs.items():
            votes = [f.result() for f in fs]
            passed = sum(v == "PASS" for v, _ in votes) > VOTES / 2
            # the reason shown is from a vote that agrees with the majority
            reason = next(o for v, o in votes if (v == "PASS") == passed)
            results.append({"name": name, "passed": passed, "votes": [v for v, _ in votes], "reason": reason})
    return results


def runs_from(results_dir):
    """(case name, run no., report.md) for every kept run of a case that has sadiya.yaml."""
    agg = json.load(open(os.path.join(results_dir, "aggregate-result.json"), encoding="utf-8"))
    for c in agg["cases"]:
        cdir = case_dir(c["name"])
        if not cdir or not os.path.exists(os.path.join(cdir, "sadiya.yaml")):
            continue
        for i, r in enumerate(c["arms"]["with"], 1):
            rep = os.path.join(os.path.dirname(os.path.dirname(r["tracePath"])), "home", "cwd", "report.md")
            yield c["name"], i, rep


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("results", nargs="?", help="папката с aggregate-result.json (пуснато с --keep-temp)")
    ap.add_argument("--case", help="случаят, напр. eptz/zaklyuchenie-bez-oglet (с --report)")
    ap.add_argument("--report", help="report.md за оценка (с --case)")
    ap.add_argument("--model", default="sonnet")
    a = ap.parse_args()

    if a.report:
        targets = [(a.case, 1, a.report)]
    elif a.results:
        targets = list(runs_from(a.results))
    else:
        ap.error("дай папка с резултати или --case и --report")

    out, failed = [], False
    for name, i, rep in targets:
        cdir = case_dir(name)
        if not os.path.exists(rep):
            print(f"✗ {name} опит {i}: няма {rep} (пусни plugin eval с --keep-temp)")
            failed = True
            continue
        res = judge(cdir, rep, a.model)
        for r in res:
            mark = "✓" if r["passed"] else "✗"
            failed |= not r["passed"]
            reason = " ".join(r["reason"].split())[:400]
            print(f"{mark} {name} опит {i} · {r['name']} · {' '.join(r['votes'])}\n    {reason}")
        out.append({"case": name, "run": i, "report": rep, "checks": res})

    if a.results:
        with open(os.path.join(a.results, "sadiya.json"), "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=1)
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
