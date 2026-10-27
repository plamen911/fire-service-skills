#!/bin/sh
set -e
REPO_URL="${REPO_URL:-https://github.com/plamen911/fire-service-skills.git}"
if [ -d "$REPO_DIR/.git" ]; then
    git -C "$REPO_DIR" pull --ff-only -q || echo "git pull failed – starting with the copy on disk" >&2
else
    git clone --depth 1 -q "$REPO_URL" "$REPO_DIR"
fi
exec python "$REPO_DIR/server/fire-render/app.py"
