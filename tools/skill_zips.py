#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
skill_zips.py — packs every skill of the fire-service plugin as its own .zip for upload in
Settings → Capabilities → Skills, for accounts where plugins (the marketplace) are not available.

    python3 tools/skill_zips.py [-o dist/skills] [skill …]

Each zip holds one folder `<skill>/` with SKILL.md at its root, plus `_shared/`, scripts, references,
assets and data; `tests/` and caches are left out. Uploaded skills do not update by themselves – after a
change the zips are built again and uploaded again.
"""
import argparse
import os
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILLS = os.path.join(ROOT, "plugins", "fire-service", "skills")
SKIP_DIRS = {"tests", "__pycache__", ".pytest_cache"}


def pack(name, out_dir):
    src = os.path.join(SKILLS, name)
    if not os.path.isfile(os.path.join(src, "SKILL.md")):
        sys.exit(f"{name}: няма SKILL.md")
    path = os.path.join(out_dir, f"{name}.zip")
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for folder, dirs, files in os.walk(src):
            dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
            for f in sorted(files):
                if f.endswith(".pyc") or f == ".DS_Store":
                    continue
                full = os.path.join(folder, f)
                z.write(full, os.path.join(name, os.path.relpath(full, src)))
    return path, os.path.getsize(path)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("skills", nargs="*", help="само тези скилове (по подразбиране – всички)")
    ap.add_argument("-o", "--out", default=os.path.join(ROOT, "dist", "skills"))
    a = ap.parse_args()
    names = a.skills or sorted(d for d in os.listdir(SKILLS) if os.path.isdir(os.path.join(SKILLS, d)))
    os.makedirs(a.out, exist_ok=True)
    for name in names:
        path, size = pack(name, a.out)
        print(f"{os.path.relpath(path, ROOT)}  {size // 1024} KB")


if __name__ == "__main__":
    main()
