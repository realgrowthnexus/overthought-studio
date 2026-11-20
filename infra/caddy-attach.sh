#!/usr/bin/env bash
# Adds the studio site to a Caddy server that another app already runs on this VPS (it owns ports 80/443).
# Only appends one site block; Caddy validates the new config before switching, and the file is restored
# if the reload fails, so the other app's sites keep working.
#   caddy-attach.sh <domain> <docker-bridge-ip>
# Exit: 0 attached (or already attached) · 1 failed (nothing changed) · 2 no other Caddy container found
set -euo pipefail
DOMAIN=${1:?domain}
BRIDGE=${2:-172.17.0.1}

C=$(docker ps --format '{{.Names}} {{.Image}}' | awk '$2 ~ /(^|\/)caddy(:|$)/ && $1 != "ots-caddy" {print $1; exit}')
[ -n "$C" ] || { echo "No other Caddy container found."; exit 2; }

FILE=""
while IFS='|' read -r src dst; do
  case "$dst" in
    /etc/caddy/Caddyfile) FILE=$src ;;
    /etc/caddy) [ -z "$FILE" ] && FILE=$src/Caddyfile ;;
  esac
done < <(docker inspect "$C" --format '{{range .Mounts}}{{.Source}}|{{.Destination}}{{"\n"}}{{end}}')
[ -n "$FILE" ] && [ -f "$FILE" ] || { echo "Caddy '$C' has no Caddyfile mounted from the host; add the site by hand:"
  echo "  $DOMAIN { reverse_proxy $BRIDGE:3100 }"; exit 1; }

if grep -qE "^[[:space:]]*${DOMAIN}[[:space:]]*\{" "$FILE"; then
  echo "$DOMAIN is already in $FILE (Caddy: $C)."; exit 0
fi

UP="$BRIDGE:3100"
if ! docker exec "$C" wget -q -T 5 -O /dev/null "http://$UP/login" 2>/dev/null; then
  # that Caddy cannot reach the docker bridge: put it on our network and proxy by container name
  docker network connect overthought-studio_default "$C" 2>/dev/null || true
  UP="ots-web:3000"
  echo "Note: joined '$C' to the overthought-studio network (re-run this script if that app is re-created)."
fi

cp -p "$FILE" "$FILE.bak-ots"
printf '\n# Overthought Studio dashboard (added by /opt/overthought-studio/caddy-attach.sh)\n%s {\n    reverse_proxy %s\n}\n' \
  "$DOMAIN" "$UP" >> "$FILE"
if docker exec "$C" caddy reload --config /etc/caddy/Caddyfile --adapter caddyfile; then
  echo "Added $DOMAIN → $UP to Caddy '$C' ($FILE). HTTPS certificate is issued automatically."
else
  cp -p "$FILE.bak-ots" "$FILE"
  echo "Caddy rejected the change; restored $FILE. Nothing else changed."; exit 1
fi
