#!/usr/bin/env bash
# Deploy on the VM, called by the git post-receive hook of ~/tenara.git with a fresh checkout of main.
# Same steps as the GitHub Actions deploy job: sync code, back up the database, rebuild, health check.
#
#   deploy-vm.sh <dir with the checked-out code>
#
# The VM's .env, models and storage are excluded from the sync, so they are never touched.
set -euo pipefail

SRC=${1:?usage: deploy-vm.sh <checkout dir>}
DEST=${DEST:-$HOME/tenara}

echo "==> sync code to $DEST"
rsync -a --checksum --delete \
  --exclude=.git --exclude=.github --exclude=node_modules --exclude=.venv --exclude=.next \
  --exclude='.env*' --exclude=services/api/storage --exclude=services/api/models \
  --exclude=docs --exclude=backups --exclude=experiments --exclude='*.md' \
  --exclude=tests --exclude=Tenara_PRD.md \
  "$SRC"/ "$DEST"/

cd "$DEST"
export COMPOSE_FILE=docker-compose.yml:docker-compose.prod.yml

echo "==> back up the database"
mkdir -p ~/backups
docker compose exec -T db pg_dump -U tenara tenara | gzip > ~/backups/pre-deploy-$(date +%Y%m%d-%H%M%S).sql.gz
ls -1t ~/backups/pre-deploy-*.sql.gz | tail -n +6 | xargs -r rm --

echo "==> build and restart"
docker compose up -d --build
docker image prune -f >/dev/null
docker compose ps

echo "==> health check"
SITE=$(grep -E '^SITE_ADDRESS=' .env | cut -d= -f2-)
# --resolve: ask this machine's own Caddy, no round trip through DNS
curl -fsS --retry 12 --retry-delay 10 --retry-all-errors --max-time 15 \
  --resolve "$SITE:443:127.0.0.1" "https://$SITE/api/v1/health"
echo
echo "==> deployed"
