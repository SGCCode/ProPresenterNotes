#!/bin/zsh
set -e
cd "$(dirname "$0")"

if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3 is required to run this app."
  echo "Install Python 3 from python.org or with Homebrew, then run this again."
  read "?Press Return to close."
  exit 1
fi

APP_PORT=$(python3 - <<'PY'
import json
from pathlib import Path
try:
    print(json.loads(Path('config.json').read_text()).get('app_port', 3000))
except Exception:
    print(3000)
PY
)

open "http://127.0.0.1:${APP_PORT}" >/dev/null 2>&1 || true
python3 server.py
