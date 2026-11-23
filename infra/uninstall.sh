#!/usr/bin/env bash
# Overthought Studio: remove it completely from this VPS. Touches ONLY what install.sh created:
#   - the 10-minute auto-update cron line
#   - containers ots-worker / ots-web / ots-caddy, their volumes, network and images
#   - the studio site block in another app's Caddyfile (if caddy-attach.sh added one) or our Nginx site
#   - /opt/overthought-studio
# Your other apps keep running. Data in Supabase is NOT touched.
# A copy of the .env (contains MASTER_KEY) is kept at /root/overthought-studio-env-backup unless KEEP_ENV=0.
set -uo pipefail
DIR=/opt/overthought-studio
say() { printf '\n\033[1;33m==> %s\033[0m\n' "$*"; }
[ "$(id -u)" = 0 ] || { echo "Please run as root (sudo -i)"; exit 1; }

DOMAIN=studio.getgrowthnexus.com
[ -f "$DIR/.env" ] && DOMAIN=$(awk -F= '/^DOMAIN=/{print $2}' "$DIR/.env") && DOMAIN=${DOMAIN:-studio.getgrowthnexus.com}

say "1/6 Stopping the auto-update"
( crontab -l 2>/dev/null | grep -v 'overthought-studio/update.sh' ) | crontab - 2>/dev/null || true

say "2/6 Saving a private copy of the settings file"
if [ -f "$DIR/.env" ] && [ "${KEEP_ENV:-1}" != 0 ]; then
  install -m 600 "$DIR/.env" /root/overthought-studio-env-backup
  echo "Saved /root/overthought-studio-env-backup (delete it later with: rm /root/overthought-studio-env-backup)"
fi

say "3/6 Removing the studio site from the web server"
C=$(docker ps --format '{{.Names}} {{.Image}}' 2>/dev/null | awk '$2 ~ /(^|\/)caddy(:|$)/ && $1 != "ots-caddy" {print $1; exit}')
if [ -n "$C" ]; then
  FILE=""
  while IFS='|' read -r src dst; do
    case "$dst" in
      /etc/caddy/Caddyfile) FILE=$src ;;
      /etc/caddy) [ -z "$FILE" ] && FILE=$src/Caddyfile ;;
    esac
  done < <(docker inspect "$C" --format '{{range .Mounts}}{{.Source}}|{{.Destination}}{{"\n"}}{{end}}')
  if [ -n "$FILE" ] && [ -f "$FILE" ] && grep -q "Overthought Studio dashboard" "$FILE"; then
    cp -p "$FILE" "$FILE.bak-ots-uninstall"
    # drop our marker comment, the "<domain> {" line and everything up to its closing "}"
    awk -v d="$DOMAIN" '
      /# Overthought Studio dashboard/ {next}
      skip==0 && $0 ~ "^[[:space:]]*" d "[[:space:]]*\\{" {skip=1; next}
      skip==1 { if ($0 ~ /^[[:space:]]*\}[[:space:]]*$/) skip=0; next }
      {print}' "$FILE.bak-ots-uninstall" > "$FILE"
    if docker exec "$C" caddy reload --config /etc/caddy/Caddyfile --adapter caddyfile; then
      echo "Removed $DOMAIN from Caddy '$C'. Backup: $FILE.bak-ots-uninstall"
    else
      cp -p "$FILE.bak-ots-uninstall" "$FILE"
      echo "!! Caddy did not accept the change, so the file was restored (other app unaffected)."
      echo "   Remove the '$DOMAIN { ... }' block from $FILE by hand later."
    fi
  else
    echo "Caddy '$C' has no studio block. Nothing to change."
  fi
  docker network disconnect overthought-studio_default "$C" 2>/dev/null || true
fi
if [ -e /etc/nginx/sites-enabled/overthought-studio ] || [ -e /etc/nginx/sites-available/overthought-studio ]; then
  rm -f /etc/nginx/sites-enabled/overthought-studio /etc/nginx/sites-available/overthought-studio
  nginx -t && systemctl reload nginx && echo "Removed the Nginx site for $DOMAIN."
fi

say "4/6 Stopping and removing the studio containers"
if [ -f "$DIR/docker-compose.yml" ]; then
  (cd "$DIR" && COMPOSE_PROFILES=caddy docker compose down --volumes --remove-orphans) || true
fi
for c in ots-worker ots-web ots-caddy; do docker rm -f "$c" >/dev/null 2>&1 || true; done
for v in overthought-studio_work overthought-studio_caddy_data overthought-studio_caddy_config; do
  docker volume rm "$v" >/dev/null 2>&1 || true
done
docker network rm overthought-studio_default >/dev/null 2>&1 || true

say "5/6 Removing the studio images"
docker rmi overthought-studio-worker:local overthought-studio-web:local >/dev/null 2>&1 || true
docker image prune -f >/dev/null 2>&1 || true

say "6/6 Deleting $DIR"
rm -rf "$DIR"

say "Done. Overthought Studio is removed from this VPS."
docker ps --format '   still running: {{.Names}}' 2>/dev/null
echo "Your other apps above are untouched. Supabase data was not changed."
