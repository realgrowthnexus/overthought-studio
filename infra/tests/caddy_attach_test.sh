#!/usr/bin/env bash
# Tests infra/caddy-attach.sh against a fake `docker` (no real containers touched).
#   bash infra/tests/caddy_attach_test.sh
set -euo pipefail
HERE=$(cd "$(dirname "$0")/.." && pwd)
T=$(mktemp -d); trap 'rm -rf -- "$T"' EXIT
mkdir -p "$T/bin" "$T/caddy"
printf 'juc.example.com {\n    reverse_proxy app:3000\n}\n' > "$T/caddy/Caddyfile"
ORIG=$(cat "$T/caddy/Caddyfile")

cat > "$T/bin/docker" <<STUB
#!/usr/bin/env bash
echo "\$*" >> "$T/calls"
case "\$1 \$2" in
  "ps --format"*) printf 'juc-app-1 juc-app:latest\njuc-caddy-1 caddy:2-alpine\nots-web e17e7\n' ;;
  "inspect juc-caddy-1") printf '%s|/etc/caddy/Caddyfile\n/var/lib/x|/data\n' "$T/caddy/Caddyfile" ;;
  "exec juc-caddy-1")
     case "\$*" in
       *wget*) exit "\${REACH_RC:-0}" ;;
       *reload*) exit "\${RELOAD_RC:-0}" ;;
     esac ;;
  "network connect") exit 0 ;;
esac
STUB
chmod +x "$T/bin/docker"
export PATH="$T/bin:$PATH"
fail() { echo "FAIL: $*"; exit 1; }

# 1. attaches once, reloads, and is idempotent
bash "$HERE/caddy-attach.sh" studio.example.com 172.17.0.1 >/dev/null || fail "attach exit code"
grep -q 'studio.example.com {' "$T/caddy/Caddyfile" || fail "block not added"
grep -q 'reverse_proxy 172.17.0.1:3100' "$T/caddy/Caddyfile" || fail "upstream wrong"
grep -q 'reload' "$T/calls" || fail "caddy not reloaded"
bash "$HERE/caddy-attach.sh" studio.example.com 172.17.0.1 >/dev/null || fail "second run exit code"
[ "$(grep -c 'studio.example.com {' "$T/caddy/Caddyfile")" = 1 ] || fail "block duplicated"

# 2. a failed reload restores the original file
printf '%s\n' "$ORIG" > "$T/caddy/Caddyfile"
if RELOAD_RC=1 bash "$HERE/caddy-attach.sh" studio.example.com 172.17.0.1 >/dev/null 2>&1; then fail "reload failure not reported"; fi
[ "$(cat "$T/caddy/Caddyfile")" = "$ORIG" ] || fail "file not restored after failed reload"

# 3. bridge IP unreachable from that caddy -> joins our network and proxies to ots-web:3000
printf '%s\n' "$ORIG" > "$T/caddy/Caddyfile"; : > "$T/calls"
REACH_RC=1 bash "$HERE/caddy-attach.sh" studio.example.com 172.17.0.1 >/dev/null || fail "fallback exit code"
grep -q 'network connect overthought-studio_default juc-caddy-1' "$T/calls" || fail "network not connected"
grep -q 'reverse_proxy ots-web:3000' "$T/caddy/Caddyfile" || fail "fallback upstream wrong"
echo "caddy-attach: all tests passed"
