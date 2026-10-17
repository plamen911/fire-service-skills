#!/usr/bin/env python3
"""tools/kb_lint.py against a small invented regulations base in a temporary folder.

Run from the repository root:  python3 tests/test_kb_lint.py
"""
import json
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LINT = os.path.join(ROOT, "tools", "kb_lint.py")
failures = []

ACT = "MVR_Instruction_Primerna-Instruktsiya-Proba_2020_ed2024-01-01.md"
OLD = "MVR_Instruction_Primerna-Instruktsiya-Proba_2020_ed2020-05-05.md"
REP = "MVR_Instruction_Otmenena-Proba_2010.md"
APP = "MVR_Instruction_Primerna-Instruktsiya-Proba_2020_ed2024-01-01_Appendices.md"
REF = "RDPBZN-Pleven_Reference_Spravochen-Material-Proba_2026-10.md"
TEXT = " ".join(["Примерен текст на члена за проверката на базата."] * 8)


def act(articles, in_force, extra=""):
    body = "\n".join(f"## Чл. {n}\n\nЧл. {n}. {TEXT}\n" for n in range(1, articles + 1))
    return f"""---
title: Примерна инструкция за проба
tier: A
issuer: МВР
act_type: инструкция
act_id: proba-2020
in_force: {in_force}
in_force_source: проверено за теста
text_source: измислен текст
subject: Примерна инструкция (тест)
articles: 1-{articles}
keywords: [проба, тест]
{extra}---

{body}"""


def write_base(root):
    os.makedirs(os.path.join(root, "tier-a"))
    os.makedirs(os.path.join(root, "tier-a-repealed"))
    os.makedirs(os.path.join(root, "tier-b"))
    os.makedirs(os.path.join(root, "tier-c"))
    files = {
        f"tier-a/{ACT}": act(3, "да", "superseded_by: null\n"),
        f"tier-a/{OLD}": act(3, "не", f"superseded_by: tier-a/{ACT}\n"),
        f"tier-a-repealed/{REP}": act(2, "отменен", "repealed_by: Примерна инструкция (тест)\n").replace(
            "tier: A\n", "tier: A-REPEALED\n").replace("proba-2020", "otmenena-2010"),
        f"tier-b/{APP}": f"---\ntitle: Приложения\ntier: B\nissuer: МВР\nact_type: приложение\nin_force: да\n"
                         f"text_source: измислен\nsubject: Приложения (тест)\nkeywords: []\n---\n\n{TEXT}\n",
        f"tier-c/{REF}": f"---\ntitle: Справочен материал\ntier: C\nissuer: РДПБЗН – Плевен\nact_type: справочен материал\n"
                         f"in_force: неприложимо\ntext_source: измислен\nkeywords: [проба]\n---\n\n{TEXT}\n",
        "_MAP_Proba.md": f"# КАРТА\n\n- **Файл:** `tier-a/{ACT}`\n\n## Чл. 1\n",
        "_INDEX_proba_2026-10-12a.md": f"""# ИНДЕКС

Дата на актуализация: 12.10.2026 (редакция a)

<!-- AUTO-COUNTS -->
<!-- /AUTO-COUNTS -->

| Акт | Карта |
|---|---|
| Проба | `_MAP_Proba.md` |

- `tier-a/{ACT}` – действаща; `tier-a/{OLD}` – заменена.
- Отменена: `tier-a-repealed/{REP}`.
""",
    }
    for rel, text in files.items():
        with open(os.path.join(root, rel), "w", encoding="utf-8") as fh:
            fh.write(text)


def lint(root, *args):
    r = subprocess.run([sys.executable, LINT, root, "--json", *args], capture_output=True, text=True)
    if not r.stdout.strip():
        raise SystemExit(r.stderr[-2000:])
    return r.returncode, json.loads(r.stdout)


def check(name, cond, detail=""):
    if not cond:
        failures.append(f"{name}: {detail}")


with tempfile.TemporaryDirectory() as tmp:
    write_base(tmp)
    code, res = lint(tmp)
    check("catalog missing is an error", code == 1 and any(p == "index.json" for p, _ in res["errors"]), res)
    code, res = lint(tmp, "--catalog")
    check("clean base passes", code == 0, res["errors"])
    idx = open(os.path.join(tmp, "_INDEX_proba_2026-10-12a.md"), encoding="utf-8").read()
    check("counts written", "Действащи актове (tier-a): 1 акта в 2 текстови файла" in idx, idx[:600])
    cat = json.load(open(os.path.join(tmp, "index.json"), encoding="utf-8"))
    check("map in catalog", any(r["map"] == "_MAP_Proba.md" and r["path"] == f"tier-a/{ACT}" for r in cat["files"]), cat)

    # status outside the vocabulary, a superseded edition without its pointer, a stub, a short path
    p = os.path.join(tmp, "tier-a", OLD)
    open(p, "w", encoding="utf-8").write(act(3, "yes", "superseded_by: null\n"))
    with open(os.path.join(tmp, "tier-c", "GDPBZN_Order_Prazen-Fayl_2020.md"), "w", encoding="utf-8") as fh:
        fh.write("---\ntitle: Празен\ntier: C\nissuer: x\nact_type: заповед\nin_force: непроверен\n"
                 "text_source: x\nkeywords: []\n---\n")
    with open(os.path.join(tmp, "_INDEX_proba_2026-10-12a.md"), "a", encoding="utf-8") as fh:
        fh.write("\n- `tier-b/…_Appendices.md`\n")
    code, res = lint(tmp)
    msgs = " | ".join(m for _, m in res["errors"])
    check("bad in_force caught", "in_force: 'yes'" in msgs, msgs)
    check("stub caught", "файл без текст" in msgs, msgs)
    check("short path caught", "съкратен път" in msgs, msgs)
    check("stale counts caught", "броевете в индекса" in msgs, msgs)

    # a missing article heading
    open(p, "w", encoding="utf-8").write(act(3, "не", f"superseded_by: tier-a/{ACT}\n").replace("## Чл. 2\n", ""))
    code, res = lint(tmp)
    check("missing article caught", any("липсват заглавия" in m for _, m in res["errors"]), res["errors"])

if failures:
    print("FAIL\n" + "\n".join(failures))
    sys.exit(1)
print("ok – kb_lint")
