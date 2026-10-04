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
  docker image prune -f > /dev/null
  echo "Deployed $(git rev-parse --short HEAD)"
}

main "$@"
