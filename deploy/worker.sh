#!/usr/bin/env bash
# Runs the pipeline worker on this machine against the production database.
# It needs what a local ai/ setup has: the root .venv, the model weights and,
# ideally, a GPU (MPS on a Mac). From the repo root:
#
#   deploy/worker.sh
#
# It opens an SSH tunnel to the server's Postgres, reads the database password
# from the server (nothing is stored here), keeps the Mac awake, and processes
# queued uploads until Ctrl-C. See deploy/README.md, "Processing uploads".
set -euo pipefail

SERVER="${FIGHT_AI_SERVER:-ubuntu@app-fightlytics.duckdns.org}"
PORT="${FIGHT_AI_TUNNEL_PORT:-55432}"

main() {
  local root creds user db password tunnel
  root="$(cd "$(dirname "$0")/.." && pwd)"

  creds=$(ssh -o BatchMode=yes -o StrictHostKeyChecking=accept-new "$SERVER" \
    "grep -E '^POSTGRES_(USER|DB|PASSWORD)=' /opt/fight-ai/.env")
  user=$(sed -n 's/^POSTGRES_USER=//p' <<< "$creds")
  db=$(sed -n 's/^POSTGRES_DB=//p' <<< "$creds")
  password=$(sed -n 's/^POSTGRES_PASSWORD=//p' <<< "$creds")

  # Reopen the tunnel whenever it drops (sleep, network change). The worker
  # waits and retries while it is down.
  (
    while true; do
      ssh -N -o BatchMode=yes -o ExitOnForwardFailure=yes \
        -o ServerAliveInterval=15 -o ServerAliveCountMax=3 \
        -L "127.0.0.1:$PORT:127.0.0.1:5432" "$SERVER" || true
      sleep 5
    done
  ) &
  tunnel=$!
  trap 'pkill -P "$tunnel" 2> /dev/null; kill "$tunnel" 2> /dev/null || true' EXIT
  for _ in $(seq 1 30); do
    nc -z 127.0.0.1 "$PORT" 2> /dev/null && break
    sleep 1
  done

  cd "$root/ai"
  DATABASE_URL="postgresql://$user:$password@127.0.0.1:$PORT/$db" \
    caffeinate -i "$root/.venv/bin/python" main.py --worker \
    --video-source "$SERVER:/srv/fight-ai/videos" --debug-level normal
}

main "$@"
