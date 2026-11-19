#!/usr/bin/env bash
# Overthought Studio — one-time VPS setup (Ubuntu 22/24). Safe to re-run: updates code/config, keeps data and keys.
# Runs the worker + dashboard in Docker under /opt/overthought-studio and never touches your other apps.
# It asks for two secrets (input hidden): the Supabase secret key and a read-only GitHub token.
set -euo pipefail

DIR=/opt/overthought-studio
REPO=realgrowthnexus/overthought-studio
DOMAIN=${DOMAIN:-studio.getgrowthnexus.com}
SUPABASE_URL=${SUPABASE_URL:-https://xkbgusqmdeocjwxaknjx.supabase.co}
SUPABASE_PUBLISHABLE_KEY=${SUPABASE_PUBLISHABLE_KEY:-sb_publishable_YsB1YII7YQ3d1s3NRfs9MQ_1YzxWIfR}

say()  { printf '\n\033[1;33m==> %s\033[0m\n' "$*"; }
ask()  { local v="$1" p="$2"; if [ -z "${!v:-}" ]; then read -r -s -p "$p: " "$v" </dev/tty; echo; export "$v"; fi; }
[ "$(id -u)" = 0 ] || { echo "Please run as root (sudo -i)"; exit 1; }

mkdir -p "$DIR"; cd "$DIR"; umask 077
# keep existing secrets on re-run
[ -f .env ] && set -a && . ./.env && set +a
ask SUPABASE_SERVICE_ROLE_KEY "Supabase secret key (sb_secret_...)"
# The repo is public: a GitHub token is optional (only needed if the repo is made private later).
GITHUB_TOKEN=${GITHUB_TOKEN:-}
MASTER_KEY=${MASTER_KEY:-$(openssl rand -base64 32)}
SETUP_TOKEN=${SETUP_TOKEN:-$(openssl rand -hex 16)}
WORKER_ID=${WORKER_ID:-vps-$(hostname -s)}

say "Installing prerequisites"
command -v git >/dev/null || { apt-get update -y && apt-get install -y git; }
command -v docker >/dev/null || curl -fsSL https://get.docker.com | sh
docker compose version >/dev/null 2>&1 || { echo "Docker Compose v2 is required"; exit 1; }

say "Getting the code"
# code is not secret: check it out world-readable so the non-root containers can read it
umask 022
if [ -n "$GITHUB_TOKEN" ]; then
  printf 'https://x-access-token:%s@github.com\n' "$GITHUB_TOKEN" > .git-credentials
else
  : > .git-credentials
fi
if [ -d src/.git ]; then
  git -C src fetch -q --depth 1 origin main && git -C src reset -q --hard origin/main
else
  git -c credential.helper="store --file=$DIR/.git-credentials" clone -q --depth 1 "https://github.com/$REPO.git" src
fi
git -C src config credential.helper "store --file=$DIR/.git-credentials"
cp src/infra/docker-compose.yml docker-compose.yml
chmod -R a+rX src
umask 077

say "Choosing how HTTPS is served"
BRIDGE=$(ip -4 addr show docker0 2>/dev/null | awk '/inet /{print $2}' | cut -d/ -f1); BRIDGE=${BRIDGE:-172.17.0.1}
PORTS=$(ss -ltnpH '( sport = :80 or sport = :443 )' 2>/dev/null || true)
PROFILES=""; MODE=""
if [ -z "$PORTS" ]; then
  MODE=caddy; PROFILES=caddy
  echo "Ports 80/443 are free → a small Caddy server will handle HTTPS for $DOMAIN automatically."
elif echo "$PORTS" | grep -q '"nginx"'; then
  MODE=nginx
  echo "Nginx already serves this VPS → adding a site for $DOMAIN (your other sites stay untouched)."
elif echo "$PORTS" | grep -q 'ots-caddy\|docker-proxy' && docker ps --format '{{.Names}}' | grep -qx ots-caddy; then
  MODE=caddy; PROFILES=caddy; echo "Re-using our Caddy."
else
  MODE=manual
  echo "Ports 80/443 are used by another program:"; echo "$PORTS" | awk '{print "   " $NF}'
fi

cat > .env <<ENV
SUPABASE_URL=$SUPABASE_URL
SUPABASE_PUBLISHABLE_KEY=$SUPABASE_PUBLISHABLE_KEY
SUPABASE_SERVICE_ROLE_KEY=$SUPABASE_SERVICE_ROLE_KEY
MASTER_KEY=$MASTER_KEY
SETUP_TOKEN=$SETUP_TOKEN
APP_URL=https://$DOMAIN
DOMAIN=$DOMAIN
DOCKER_BRIDGE_IP=$BRIDGE
COMPOSE_PROFILES=$PROFILES
WORKER_ID=$WORKER_ID
WORKER_CONCURRENCY=2
RENDER_PROCS=3
GITHUB_TOKEN=$GITHUB_TOKEN
ENV
chmod 600 .env .git-credentials

# auto-update every 10 minutes: rebuild + restart only when main changed
cat > update.sh <<'UPD'
#!/usr/bin/env bash
set -euo pipefail
cd /opt/overthought-studio
exec 9>update.lock; flock -n 9 || exit 0
old=$(git -C src rev-parse HEAD)
git -C src fetch -q --depth 1 origin main && git -C src reset -q --hard origin/main
new=$(git -C src rev-parse HEAD)
if [ "$old" != "$new" ] || [ "${1:-}" = "--force" ]; then
  cp src/infra/docker-compose.yml docker-compose.yml
  docker compose build -q && docker compose up -d --remove-orphans
  docker image prune -f >/dev/null
  echo "$(date -Is) updated $old -> $new" >> update.log
fi
UPD
chmod 700 update.sh
{ crontab -l 2>/dev/null | grep -v 'overthought-studio/update.sh' || true; echo "*/10 * * * * /opt/overthought-studio/update.sh >/dev/null 2>&1"; } | crontab -

say "Building and starting (first build takes 5-10 minutes)"
docker compose build
docker compose up -d --remove-orphans

if [ "$MODE" = nginx ]; then
  say "Configuring Nginx for $DOMAIN"
  cat > /etc/nginx/sites-available/overthought-studio <<NGX
server {
    listen 80;
    server_name $DOMAIN;
    client_max_body_size 30m;
    location / {
        proxy_pass http://127.0.0.1:3100;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
NGX
  ln -sf /etc/nginx/sites-available/overthought-studio /etc/nginx/sites-enabled/overthought-studio
  nginx -t && systemctl reload nginx
  command -v certbot >/dev/null || apt-get install -y certbot python3-certbot-nginx
  certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos --register-unsafely-without-email --redirect \
    || echo "!! Certificate not issued yet — check that the DNS A record for $DOMAIN points to this VPS, then re-run this script."
fi

sleep 8
docker compose ps
say "Done"
echo "Dashboard:   https://$DOMAIN"
if [ "$MODE" = manual ]; then
  echo
  echo "One manual step: in the program that owns ports 80/443 (Coolify / CapRover / Nginx Proxy Manager / Traefik…),"
  echo "add a proxy/domain for  $DOMAIN  →  http://$BRIDGE:3100   (or http://127.0.0.1:3100 if it runs outside Docker)."
fi
echo
echo "Create your owner login at https://$DOMAIN/setup with this one-time setup token:"
echo "   $SETUP_TOKEN"
echo
echo "Your encryption key (MASTER_KEY) is saved in $DIR/.env — copy it somewhere safe (password manager):"
echo "   $MASTER_KEY"
echo
echo "Logs: cd $DIR && docker compose logs -f      Stop: cd $DIR && docker compose down"
echo "New VPS later? Copy $DIR/.env to it, run this installer there, then 'docker compose down' on the old one."
