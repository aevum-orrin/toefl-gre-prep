#!/usr/bin/env bash
# Launch one prep tool by name:
#   ./run.sh writing | speaking | vocab | reading
# Loads the env (module + venv + .env is read in-process by the app) and starts uvicorn.
# No `set -e`: env.sh's module/lmod calls can return nonzero, which is expected when sourced.
cd "$(dirname "${BASH_SOURCE[0]}")" || exit 1

case "${1:-}" in
  writing)  dir=writing-coach;     port=8001 ;;
  speaking) dir=speaking-app;      port=8002 ;;
  vocab)    dir=vocab-srs;         port=8003 ;;
  reading)  dir=reading-listening; port=8004 ;;
  *)
    echo "usage: ./run.sh writing|speaking|vocab|reading"
    echo "  writing  -> writing-coach     :8001"
    echo "  speaking -> speaking-app      :8002  (needs a microphone)"
    echo "  vocab    -> vocab-srs         :8003"
    echo "  reading  -> reading-listening :8004"
    exit 1 ;;
esac

source env.sh
echo "▶ ${dir} running at  http://localhost:${port}   (Ctrl+C to stop)"
cd "tools/${dir}"
exec uvicorn app:app --port "${port}"
