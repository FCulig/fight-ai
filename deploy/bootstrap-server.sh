#!/usr/bin/env bash
# One-time setup of a fresh Oracle Cloud VM (Canonical Ubuntu 24.04, arm64),
# run as the default `ubuntu` user. Safe to re-run. From your laptop:
#
#   scp deploy/bootstrap-server.sh ubuntu@<SERVER_IP>:
#   ssh ubuntu@<SERVER_IP> "DEPLOY_PUBKEY='$(cat ~/.ssh/fight_ai_deploy.pub)' bash bootstrap-server.sh"
#
# It clones the repo from GitHub, so deploy/ must already be on master there.
# See deploy/README.md for the steps around it.
set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/FCulig/fight-ai.git}"

install_docker() {
  if command -v docker > /dev/null; then return; fi
  sudo apt-get update
  sudo apt-get install -y ca-certificates curl git
  sudo install -m 0755 -d /etc/apt/keyrings
  sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
  sudo chmod a+r /etc/apt/keyrings/docker.asc
  # /etc/os-release exists on the VM, not where shellcheck runs.
  # shellcheck disable=SC1091
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
    | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
  sudo apt-get update
  sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
  # Rotate container logs; the default json-file driver grows without limit.
  echo '{"log-driver": "json-file", "log-opts": {"max-size": "20m", "max-file": "5"}}' \
    | sudo tee /etc/docker/daemon.json > /dev/null
  sudo systemctl restart docker
  sudo usermod -aG docker "$USER"
}

# Oracle's Ubuntu image ends the INPUT chain with a REJECT that only lets SSH
# through, so accept 80/443 ahead of it. The VCN security list must allow them too.
open_firewall() {
  if ! command -v netfilter-persistent > /dev/null; then
    sudo DEBIAN_FRONTEND=noninteractive apt-get install -y iptables-persistent
  fi
  local rule reject_at
  for rule in "-p tcp --dport 80" "-p tcp --dport 443" "-p udp --dport 443"; do
    # shellcheck disable=SC2086  # $rule is split into arguments on purpose
    if sudo iptables -C INPUT $rule -j ACCEPT 2> /dev/null; then continue; fi
    reject_at=$(sudo iptables -L INPUT --line-numbers -n | awk '$2 == "REJECT" { print $1; exit }')
    # shellcheck disable=SC2086
    sudo iptables -I INPUT "${reject_at:-1}" $rule -j ACCEPT
  done
  sudo netfilter-persistent save
}

prepare_dirs() {
  sudo mkdir -p /opt/fight-ai /srv/fight-ai/videos /srv/fight-ai/runs /srv/fight-ai/backups
  sudo chown "$USER:$USER" /opt/fight-ai /srv/fight-ai /srv/fight-ai/videos /srv/fight-ai/runs /srv/fight-ai/backups
  if [ ! -d /opt/fight-ai/app/.git ]; then
    git clone "$REPO_URL" /opt/fight-ai/app
  fi
  if [ ! -f /opt/fight-ai/.env ]; then
    install -m 600 /opt/fight-ai/app/deploy/env.example /opt/fight-ai/.env
    sed -i \
      -e "s/^POSTGRES_PASSWORD=$/POSTGRES_PASSWORD=$(openssl rand -hex 24)/" \
      -e "s/^SESSION_SECRET=$/SESSION_SECRET=$(openssl rand -hex 32)/" \
      -e "s/^APP_UID=.*/APP_UID=$(id -u)/" \
      -e "s/^APP_GID=.*/APP_GID=$(id -g)/" \
      /opt/fight-ai/.env
  fi
}

# The GitHub Actions key may only run remote-deploy.sh, never open a shell.
install_deploy_key() {
  if [ -z "${DEPLOY_PUBKEY:-}" ]; then
    echo "DEPLOY_PUBKEY is not set: skipping the GitHub Actions deploy key."
    return
  fi
  install -m 700 -d ~/.ssh
  touch ~/.ssh/authorized_keys
  chmod 600 ~/.ssh/authorized_keys
  if ! grep -qF "$DEPLOY_PUBKEY" ~/.ssh/authorized_keys; then
    echo "command=\"/opt/fight-ai/app/deploy/remote-deploy.sh\",restrict $DEPLOY_PUBKEY" >> ~/.ssh/authorized_keys
  fi
}

install_backup_cron() {
  local job="0 3 * * * /opt/fight-ai/app/deploy/backup.sh >> /srv/fight-ai/backups/backup.log 2>&1"
  ( crontab -l 2> /dev/null | grep -vF deploy/backup.sh || true; echo "$job" ) | crontab -
}

main() {
  install_docker
  open_firewall
  prepare_dirs
  install_deploy_key
  install_backup_cron
  echo
  echo "Server ready. Next: fill in /opt/fight-ai/.env (deploy/README.md, step 5)."
}

main "$@"
