#!/usr/bin/env bash
# Signs the studio worker into YOUR Claude subscription (Pro/Max). No API key, no credits.
#   sudo bash /opt/overthought-studio/src/infra/connect-claude.sh
# It opens Claude's sign-in: open the link it prints, sign in, and paste the code back here.
# The token is captured automatically, saved encrypted in the studio database, and never shown again.
# Run it again any time the dashboard says "Sign in to Claude".
set -euo pipefail
DIR=${STUDIO_DIR:-/opt/overthought-studio}
cd "$DIR"
umask 077
LOG=$(mktemp /tmp/connect-claude.XXXXXX)
cleanup() { shred -u "$LOG" 2>/dev/null || rm -f -- "$LOG"; }
trap cleanup EXIT

echo
echo "== Connect Claude =="
echo "1) A link appears below. Open it in your browser and sign in with your Claude account."
echo "2) Claude shows a code. Copy it, paste it here, and press Enter."
echo

script -q -e -c "docker compose exec -it worker claude setup-token" "$LOG" || true

# strip colours and carriage returns, then take the token line plus any wrapped continuation lines
TOKEN=$(sed -e 's/\x1b\[[0-9;?]*[A-Za-z]//g' -e 's/\r//g' "$LOG" | awk '
  found && /^[A-Za-z0-9_-]+$/ { tok = tok $0; next }
  found { exit }
  match($0, /sk-ant-oat[0-9][0-9]-[A-Za-z0-9_-]+/) { tok = substr($0, RSTART, RLENGTH); found = 1 }
  END { print tok }')

clear 2>/dev/null || true
if [ -z "$TOKEN" ]; then
  echo "Claude is NOT signed in: no token came back (the sign-in was cancelled or failed)."
  echo "Run this script again and finish the sign-in in the browser."
  exit 1
fi

printf '%s' "$TOKEN" | docker compose exec -T worker python -m studio.cli claude-token
TOKEN=
echo
echo "Status: $(docker compose exec -T worker python -m studio.cli claude-status 2>/dev/null || echo 'unknown')"
echo "Done. The dashboard's Claude card updates within ~10 minutes (or press 'Run health check' in Settings)."
