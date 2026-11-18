#!/usr/bin/env bash
# One-time VPS setup for Overthought Studio (Ubuntu 22/24). Safe to re-run: updates config, keeps data.
# Paste into the VPS terminal (Hostinger → VPS → Browser terminal). It asks for the three secrets (input hidden),
# so nothing sensitive lands in shell history.
set -euo pipefail
ask() { local v="$1" p="$2"; if [ -z "${!v:-}" ]; then read -r -s -p "$p: " "$v" </dev/tty; echo; export "$v"; fi; }
ask SUPABASE_SERVICE_ROLE_KEY "Supabase secret key (sb_secret_...)"
ask MASTER_KEY "MASTER_KEY (from your setup message)"
ask GITHUB_TOKEN "GitHub read-only token (github_pat_...)"

DIR=/opt/overthought-studio
REPO=realgrowthnexus/overthought-studio
: "${SUPABASE_SERVICE_ROLE_KEY:?set SUPABASE_SERVICE_ROLE_KEY}"
: "${MASTER_KEY:?set MASTER_KEY}"
: "${GITHUB_TOKEN:?set GITHUB_TOKEN (fine-grained, read-only Contents on $REPO)}"
SUPABASE_URL=${SUPABASE_URL:-https://xkbgusqmdeocjwxaknjx.supabase.co}
WORKER_ID=${WORKER_ID:-vps-$(hostname -s)}

echo "==> Overthought Studio installer"
command -v git >/dev/null || (apt-get update -y && apt-get install -y git)
if ! command -v docker >/dev/null 2>&1; then
  echo "==> Installing Docker"
  curl -fsSL https://get.docker.com | sh
fi
docker compose version >/dev/null 2>&1 || { echo "Docker Compose v2 is required"; exit 1; }

mkdir -p "$DIR"
cd "$DIR"
umask 077
printf 'https://x-access-token:%s@github.com\n' "$GITHUB_TOKEN" > .git-credentials
if [ -d src/.git ]; then
  git -C src -c credential.helper="store --file=$DIR/.git-credentials" pull --ff-only
else
  git -c credential.helper="store --file=$DIR/.git-credentials" clone --depth 1 "https://github.com/$REPO.git" src
fi
git -C src config credential.helper "store --file=$DIR/.git-credentials"
cp src/infra/docker-compose.yml docker-compose.yml

cat > .env <<ENV
SUPABASE_URL=$SUPABASE_URL
SUPABASE_SERVICE_ROLE_KEY=$SUPABASE_SERVICE_ROLE_KEY
MASTER_KEY=$MASTER_KEY
WORKER_ID=$WORKER_ID
WORKER_CONCURRENCY=2
RENDER_PROCS=3
ENV
chmod 600 .env .git-credentials

# auto-update: every 10 minutes pull main; rebuild + restart only when something changed
cat > update.sh <<'UPD'
#!/usr/bin/env bash
set -euo pipefail
cd /opt/overthought-studio
old=$(git -C src rev-parse HEAD)
git -C src fetch -q --depth 1 origin main && git -C src reset -q --hard origin/main
new=$(git -C src rev-parse HEAD)
if [ "$old" != "$new" ] || [ "${1:-}" = "--force" ]; then
  cp src/infra/docker-compose.yml docker-compose.yml
  docker compose build -q && docker compose up -d
  docker image prune -f >/dev/null
  echo "$(date -Is) updated $old -> $new" >> update.log
fi
UPD
chmod 700 update.sh
{ crontab -l 2>/dev/null | grep -v 'overthought-studio/update.sh' || true; echo "*/10 * * * * /opt/overthought-studio/update.sh >/dev/null 2>&1"; } | crontab -

echo "==> Building and starting (first build takes 3-6 minutes)"
docker compose build
docker compose up -d
sleep 5
docker compose ps
echo
echo "==> Done. The worker runs 24/7 and updates itself within 10 minutes of every code change."
echo "    Logs:  cd $DIR && docker compose logs -f worker"
echo "    Stop:  cd $DIR && docker compose down"
echo "    New VPS? Run this same installer there, then 'docker compose down' on the old one. All data lives in Supabase."
