#!/usr/bin/env bash
# The forced command for the GitHub Actions deploy key (installed by
# bootstrap-server.sh). The key can deploy a commit that is on `release` and do
# nothing else, not even open a shell. The workflow sends the SHA as the command.
set -euo pipefail

# Everything runs inside main(), so bash has parsed the whole script before the
# checkout below rewrites this file.
main() {
  local sha="${SSH_ORIGINAL_COMMAND:-}"
  if [[ ! "$sha" =~ ^[0-9a-f]{40}$ ]]; then
    echo "expected a full commit SHA, got '$sha'" >&2
    exit 2
  fi
  cd /opt/fight-ai/app
  git fetch --quiet origin release
  if ! git merge-base --is-ancestor "$sha" origin/release; then
    echo "$sha is not on origin/release" >&2
    exit 3
  fi
  git checkout --quiet --force --detach "$sha"
  exec ./deploy/deploy.sh
}

main "$@"
