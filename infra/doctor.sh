#!/usr/bin/env bash
# Overthought Studio — health report for the VPS. Safe to run any time; changes nothing.
# Prints no keys: paste the whole output to Claude.
#   /opt/overthought-studio/doctor.sh
set -uo pipefail

DIR=/opt/overthought-studio
cd "$DIR" 2>/dev/null || { echo "Not installed: $DIR is missing. Run the installer first."; exit 1; }
DOMAIN=$(grep -E '^DOMAIN=' .env 2>/dev/null | cut -d= -f2-)
DOMAIN=${DOMAIN:-studio.getgrowthnexus.com}

redact() { sed -E 's/(sk-[A-Za-z0-9_-]{6,}|sb_secret_[A-Za-z0-9_-]+|eyJ[A-Za-z0-9._-]{20,})/***/g; s/((api_key|apikey|key|secret|token|password)=)[^[:space:]&,"]+/\1***/Ig'; }
section() { printf '\n===== %s =====\n' "$1"; }

section "Version"
echo "code: $(git -C src log -1 --format='%h %ci %s' 2>/dev/null || echo unknown)"
tail -n 3 update.log 2>/dev/null || echo "no auto-updates yet"

section "Containers"
docker compose ps --format 'table {{.Name}}\t{{.State}}\t{{.Status}}' 2>&1

section "Worker heartbeat"
docker compose exec -T worker python -c '
from datetime import datetime, timezone
from studio import db
rows = db.select("worker_heartbeats", order="last_seen.desc", limit=1)
if not rows:
    print("no heartbeat yet")
else:
    hb = rows[0]
    age = datetime.now(timezone.utc) - datetime.fromisoformat(hb["last_seen"])
    print(hb["worker_id"], "last seen", int(age.total_seconds()), "seconds ago")
' 2>&1 | redact | tail -n 3

section "Dashboard (local)"
curl -s -o /dev/null -w 'http://127.0.0.1:3100/login -> %{http_code}\n' --max-time 10 http://127.0.0.1:3100/login

section "DNS and HTTPS"
echo "this VPS: $(curl -s --max-time 5 https://api.ipify.org || echo unknown)"
echo "$DOMAIN -> $(getent hosts "$DOMAIN" | awk '{print $1}' | head -n 1 || true)"
curl -s -o /dev/null -w "https://$DOMAIN/login -> %{http_code}\n" --max-time 15 "https://$DOMAIN/login" \
  || echo "https://$DOMAIN/login -> not reachable yet (DNS or certificate)"

section "Services (one live call each)"
docker compose exec -T worker python -m studio.cli smoke 2>&1 | redact | tail -n 1

section "Recent worker log"
docker compose logs --no-color --tail 30 worker 2>&1 | redact

section "Disk and memory"
df -h / | tail -n 1
free -h | awk 'NR<=2'
