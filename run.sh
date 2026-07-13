#!/usr/bin/env bash
# Launch one prep tool by name:
#   ./run.sh writing | speaking | vocab | reading | mock   [PORT]
# Loads the env (module + venv + .env is read in-process by the app) and starts uvicorn.
# No `set -e`: env.sh's module/lmod calls can return nonzero, which is expected when sourced.
#
# PORT overrides the default. Use it when the browser hangs on the usual port: a stale
# SSH/VS Code forward from an older session (possibly to a DIFFERENT login node) can still
# own localhost:<port> on the laptop, so the request never reaches this host. A fresh port
# forces a fresh forward:  ./run.sh vocab 8013
cd "$(dirname "${BASH_SOURCE[0]}")" || exit 1

case "${1:-}" in
  writing)  dir=writing-coach;     port=8001 ;;
  speaking) dir=speaking-app;      port=8002 ;;
  vocab)    dir=vocab-srs;         port=8003 ;;
  reading)  dir=reading-listening; port=8004 ;;
  mock)     dir=mock-test;         port=8005 ;;
  *)
    echo "usage: ./run.sh writing|speaking|vocab|reading|mock"
    echo "  writing  -> writing-coach     :8001"
    echo "  speaking -> speaking-app      :8002  (needs a microphone)"
    echo "  vocab    -> vocab-srs         :8003"
    echo "  reading  -> reading-listening :8004"
    echo "  mock     -> mock-test         :8005  (full-length timed R/L)"
    exit 1 ;;
esac

port="${2:-$port}"                       # optional PORT override (see header)

source env.sh
if ss -ltn 2>/dev/null | grep -q "127.0.0.1:${port} "; then
  echo "⚠ port ${port} on $(hostname -s) is ALREADY in use — an old server is still running."
  echo "  kill it:  pkill -f 'uvicorn app:app --port ${port}'      or pick another: ./run.sh $1 8013"
  exit 1
fi
echo "▶ ${dir} running at  http://localhost:${port}   on $(hostname -s)   (Ctrl+C to stop)"
echo "  If the browser just spins: the laptop's localhost:${port} is likely still forwarded to"
echo "  an OLD session/node. Re-forward the port in VS Code's PORTS panel, or use: ./run.sh $1 8013"
cd "tools/${dir}"
exec uvicorn app:app --port "${port}"
