#!/usr/bin/env bash
# Nightly database dump, kept for 14 days. bootstrap-server.sh schedules it with
# cron. The dumps stay on this VM, so copy them off regularly (README.md): if
# Oracle reclaims the VM, they go with it.
set -euo pipefail

main() {
  local dir=/srv/fight-ai/backups
  local out
  out="$dir/fight_ai_$(date -u +%Y%m%d_%H%M%S).dump"
  cd "$(dirname "$0")"
  docker compose exec -T db sh -c 'pg_dump -Fc -U "$POSTGRES_USER" "$POSTGRES_DB"' > "$out.part"
  mv "$out.part" "$out"
  find "$dir" -name 'fight_ai_*.dump' -mtime +14 -delete
  find "$dir" -name '*.part' -mmin +60 -delete
  echo "$(date -u +%FT%TZ) $out $(du -h "$out" | cut -f1)"
}

main "$@"
