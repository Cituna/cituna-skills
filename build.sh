#!/usr/bin/env bash
# Checks the skills and builds dist/<skill>.zip for upload to the Claude apps.
#   bash build.sh          check, then rebuild the zips
#   bash build.sh --check  check only
# Three files are shared between skills so each skill installs on its own. Edit the first copy named
# below, then run this: it copies it to the others and fails if a skill's SKILL.md breaks the upload rules.
set -euo pipefail
cd "$(dirname "$0")"

sync() { # sync <source> <copy>...
  local src="$1"; shift
  for dst in "$@"; do
    if [ "${CHECK:-}" = 1 ]; then cmp -s "$src" "$dst" || { echo "out of date: $dst (run: bash build.sh)"; exit 1; }
    else cp "$src" "$dst"; fi
  done
}
[ "${1:-}" = "--check" ] && CHECK=1
sync skills/audit/scripts/pagefacts.py skills/clicks/scripts/pagefacts.py skills/sources/scripts/pagefacts.py skills/rivals/scripts/pagefacts.py
sync skills/cited/collect.md skills/sources/collect.md skills/rivals/collect.md
sync skills/cited/scripts/tally.py skills/rivals/scripts/tally.py

CHECK="${CHECK:-}" python3 - <<'PY'
import os, re, sys, zipfile
ALLOWED = {"name", "description", "license", "compatibility", "metadata", "allowed-tools"}  # what the Claude apps accept
bad = 0
for name in sorted(os.listdir("skills")):
    path = os.path.join("skills", name, "SKILL.md")
    if not os.path.isfile(path):
        continue
    text = open(path, encoding="utf-8").read()
    m = re.match(r"---\n(.*?)\n---\n", text, re.S)
    keys = dict(re.findall(r"^([\w-]+):\s*(.*)$", m.group(1), re.M)) if m else {}
    desc = keys.get("description", "").strip('"')
    problems = []
    if keys.get("name") != name: problems.append("name must equal the folder name")
    if not re.fullmatch(r"[a-z0-9-]{1,64}", name): problems.append("name: lower-case letters, digits and hyphens only")
    if not 1 <= len(desc) <= 1024: problems.append(f"description is {len(desc)} characters (limit 1024)")
    if set(keys) - ALLOWED: problems.append(f"keys the Claude apps reject: {sorted(set(keys) - ALLOWED)}")
    if len(text.splitlines()) > 500: problems.append("SKILL.md is over 500 lines")
    for p in problems:
        bad += 1
        print(f"{name}: {p}")
    if problems or os.environ.get("CHECK"):
        continue
    os.makedirs("dist", exist_ok=True)
    with zipfile.ZipFile(f"dist/{name}.zip", "w", zipfile.ZIP_DEFLATED) as z:
        for root, dirs, files in os.walk(os.path.join("skills", name)):
            dirs[:] = sorted(d for d in dirs if d != "__pycache__")
            for f in sorted(files):
                if f.endswith(".pyc") or f == ".DS_Store":
                    continue
                full = os.path.join(root, f)
                info = zipfile.ZipInfo(os.path.relpath(full, "skills"), date_time=(2026, 1, 1, 0, 0, 0))  # fixed date: same input, same zip
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o644 << 16
                z.writestr(info, open(full, "rb").read())
    print(f"built dist/{name}.zip")
sys.exit(1 if bad else 0)
PY
