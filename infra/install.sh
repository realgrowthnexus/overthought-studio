#!/usr/bin/env bash
# One-time VPS setup for Overthought Studio (Ubuntu 22/24). Safe to re-run (updates config, keeps data).
# Self-contained: paste it into the VPS terminal (Hostinger → VPS → Browser terminal) with the env vars set:
#   SUPABASE_SERVICE_ROLE_KEY=... MASTER_KEY=... GHCR_TOKEN=... bash ots-install.sh
set -euo pipefail

DIR=/opt/overthought-studio
: "${SUPABASE_SERVICE_ROLE_KEY:?set SUPABASE_SERVICE_ROLE_KEY}"
: "${MASTER_KEY:?set MASTER_KEY}"
SUPABASE_URL=${SUPABASE_URL:-https://xkbgusqmdeocjwxaknjx.supabase.co}
WORKER_ID=${WORKER_ID:-vps-$(hostname -s)}

echo "==> Overthought Studio installer"
if ! command -v docker >/dev/null 2>&1; then
  echo "==> Installing Docker"
  curl -fsSL https://get.docker.com | sh
fi
docker compose version >/dev/null 2>&1 || { echo "Docker Compose v2 is required"; exit 1; }

mkdir -p "$DIR"
cd "$DIR"
cat > docker-compose.yml <<'COMPOSE'
# Overthought Studio on the VPS. Lives in /opt/overthought-studio and touches nothing else on the server:
# no ports are published, it only makes outbound HTTPS calls.
name: overthought-studio

services:
  worker:
    image: ghcr.io/realgrowthnexus/overthought-studio-worker:latest
    container_name: ots-worker
    restart: unless-stopped
    env_file: .env
    volumes:
      - work:/data/work
    # leave head-room for the other app on this VPS (4 vCPU / 16 GB)
    cpus: "3.0"
    mem_limit: 6g
    labels:
      - com.centurylinklabs.watchtower.enable=true
    logging:
      driver: json-file
      options: { max-size: "20m", max-file: "5" }

  updater:
    image: containrrr/watchtower:1.7.1
    container_name: ots-updater
    restart: unless-stopped
    command: --label-enable --interval 300 --cleanup
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
      - ${HOME}/.docker/config.json:/config.json:ro
    labels:
      - com.centurylinklabs.watchtower.enable=false

volumes:
  work:
COMPOSE

umask 077
cat > .env <<ENV
SUPABASE_URL=$SUPABASE_URL
SUPABASE_SERVICE_ROLE_KEY=$SUPABASE_SERVICE_ROLE_KEY
MASTER_KEY=$MASTER_KEY
WORKER_ID=$WORKER_ID
WORKER_CONCURRENCY=2
RENDER_PROCS=3
ENV
chmod 600 .env

mkdir -p "$HOME/.docker"; [ -f "$HOME/.docker/config.json" ] || echo '{}' > "$HOME/.docker/config.json"
if [ -n "${GHCR_TOKEN:-}" ]; then
  echo "$GHCR_TOKEN" | docker login ghcr.io -u "${GHCR_USER:-realgrowthnexus}" --password-stdin
fi

docker compose pull
docker compose up -d
sleep 5
docker compose ps
echo
echo "==> Done. The worker is running and will auto-update within 5 minutes of every new release."
echo "    Logs:    cd $DIR && docker compose logs -f worker"
echo "    Stop:    cd $DIR && docker compose down"
echo "    Moving to a new VPS? Run this same installer there, then 'docker compose down' here. All data lives in Supabase."
