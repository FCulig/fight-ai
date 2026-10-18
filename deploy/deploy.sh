#!/usr/bin/env bash
# Build and (re)start the production stack from the current checkout.
# remote-deploy.sh runs it on every push to `release`; it is also safe to run by
# hand on the server.
set -euo pipefail

main() {
  cd "$(dirname "$0")"
  ln -sfn /opt/fight-ai/.env .env

  docker compose pull --quiet db caddy
  docker compose build --pull
  docker compose up -d --wait db
  # Migrate before the new backend starts: if this fails, the old one keeps serving.
  docker compose run --rm --no-deps backend \
    /opt/venv-ai/bin/alembic -c /app/db/alembic.ini upgrade head
  docker compose up -d --wait --remove-orphans
  # Caddy reads its config only at start, and a single-file bind mount keeps
  # serving the old file once git replaces it, so recreate Caddy (a second of
  # downtime) only when the Caddyfile it sees differs from the checkout's.
  if ! docker compose exec -T caddy cat /etc/caddy/Caddyfile | cmp -s - Caddyfile; then
    docker compose up -d --force-recreate --no-deps caddy
  fi
  docker image prune -f > /dev/null
  echo "Deployed $(git rev-parse --short HEAD)"
}

main "$@"
