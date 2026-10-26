#!/usr/bin/env bash
#
# Get the app running in front of you, from a fresh clone, in one command.
#
#     ./scripts/try_it.sh
#
# It installs what is missing, starts the API and the client, and prints the
# URL. Ctrl-C stops both.
#
# This exists because the project had instructions for running each piece and
# nothing that ran the whole thing. Every screenshot in docs/screenshots was
# produced by a machine driving the app, which is not the same as the author
# ever having used it -- and a safety argument you have only read is one you
# have not actually checked.
#
# No GPU, no dataset, no trained model. The classifier is a stub that returns
# deterministic nonsense; everything around it -- the refusal, the questions,
# the hazard display, the consent gate -- is real.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

API_PORT="${API_PORT:-8000}"
WEB_PORT="${WEB_PORT:-8081}"

say()  { printf "\n\033[1m%s\033[0m\n" "$1"; }
note() { printf "  \033[2m%s\033[0m\n" "$1"; }
die()  { printf "\n\033[31m%s\033[0m\n\n" "$1" >&2; exit 1; }

# --- What we need ------------------------------------------------------------

command -v python3 >/dev/null || die "python3 is not installed. Need 3.11 or newer."
command -v npm     >/dev/null || die "npm is not installed. Install Node 18 or newer."

PY_OK=$(python3 -c 'import sys; print(1 if sys.version_info >= (3, 11) else 0)')
[ "$PY_OK" = "1" ] || die "Python 3.11 or newer is needed; this is $(python3 -V)."

# --- The API -----------------------------------------------------------------

say "1/3  The API"
if python3 -c "import fastapi, numpy, PIL" 2>/dev/null; then
  note "dependencies already installed"
else
  note "installing server dependencies (a minute or so)"
  python3 -m pip install --quiet --break-system-packages -r server/requirements.txt \
    || python3 -m pip install --quiet -r server/requirements.txt
fi

cleanup() {
  printf "\n  stopping...\n"
  [ -n "${API_PID:-}" ] && kill "$API_PID" 2>/dev/null || true
  [ -n "${WEB_PID:-}" ] && kill "$WEB_PID" 2>/dev/null || true
  wait 2>/dev/null || true
}
trap cleanup EXIT INT TERM

( cd server && python3 -m uvicorn app.main:app --host 127.0.0.1 --port "$API_PORT" \
    >"$ROOT/.try_it_api.log" 2>&1 ) &
API_PID=$!

for _ in $(seq 1 60); do
  if curl -sS -o /dev/null "http://127.0.0.1:$API_PORT/health" 2>/dev/null; then break; fi
  sleep 1
done
curl -sS -o /dev/null "http://127.0.0.1:$API_PORT/health" 2>/dev/null \
  || die "The API did not start. See .try_it_api.log"

note "running on http://127.0.0.1:$API_PORT"
python3 - <<PY
import json, urllib.request
h = json.load(urllib.request.urlopen("http://127.0.0.1:$API_PORT/health"))
print(f"  \033[2m{h['n_classes']} species  |  model_loaded={h['model_loaded']}  "
      f"calibrated={h['calibrated']}  taxonomy_reviewed={h['taxonomy_reviewed']}\033[0m")
PY

# --- The client --------------------------------------------------------------

say "2/3  The client"
if [ -d app/node_modules ]; then
  note "dependencies already installed"
else
  note "installing client dependencies (a few minutes the first time)"
  ( cd app && npm install --no-audit --no-fund >/dev/null 2>&1 )
fi

( cd app && EXPO_PUBLIC_API_URL="http://127.0.0.1:$API_PORT" \
    npx expo start --web --port "$WEB_PORT" >"$ROOT/.try_it_web.log" 2>&1 ) &
WEB_PID=$!

note "starting Metro (this takes 30-60 seconds the first time)"
for _ in $(seq 1 180); do
  if curl -sS -o /dev/null "http://localhost:$WEB_PORT" 2>/dev/null; then break; fi
  sleep 1
done
curl -sS -o /dev/null "http://localhost:$WEB_PORT" 2>/dev/null \
  || die "The client did not start. See .try_it_web.log"

# --- Over to you -------------------------------------------------------------

say "3/3  Open this"
printf "\n      \033[1;4mhttp://localhost:%s\033[0m\n\n" "$WEB_PORT"

cat <<'EOF'
  What to do when it loads:

    1. Tick all six boxes and continue. There is no accept-all, on purpose.
    2. Add any photograph as the cap -- a real mushroom, a chair, anything.
       The classifier is a stub, so what it names is meaningless.
    3. Look at what happens AROUND the name. That is the whole product:
       whether it refuses, what it asks you next, and what it declines
       to say about eating anything.
    4. Try the red cross, top right. That screen is hardcoded and offline
       and sits above the consent gate.

  Different photographs give different (fake) verdicts. Keep going until you
  get "I can't safely narrow this down" -- that is the one worth seeing.

  Ctrl-C stops both.
EOF

wait
