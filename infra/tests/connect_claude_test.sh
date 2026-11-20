#!/usr/bin/env bash
# Tests infra/connect-claude.sh against a fake `docker` (no real containers, no real sign-in).
#   bash infra/tests/connect_claude_test.sh
set -euo pipefail
HERE=$(cd "$(dirname "$0")/.." && pwd)
T=$(mktemp -d); trap 'rm -rf -- "$T"' EXIT
mkdir -p "$T/bin" "$T/studio"
TOK="sk-ant-oat01-AAAAAAAAAAbbbbbbbbbbCCCCCCCCCC_dddddddddd-EEEEEEEEEE1234567890"
cat > "$T/bin/docker" <<STUB
#!/usr/bin/env bash
echo "\$*" >> "$T/calls"
case "\$*" in
  *"claude setup-token"*)
     # Ink-style output: colours, CR, and the token wrapped at the terminal width
     printf '\033[1mOpen this link to sign in:\033[0m https://claude.ai/oauth/authorize?x=1\r\n'
     printf 'Paste code here > \r\n\r\n'
     [ "\${NO_TOKEN:-}" = 1 ] && exit 1
     printf '\033[32m✓ Long-lived authentication token created successfully!\033[0m\r\n\r\n'
     printf 'Your OAuth token (valid for 1 year):\r\n\r\n'
     printf '\033[33m${TOK:0:40}\r\n${TOK:40}\033[0m\r\n\r\n'
     printf 'Store this token securely. You will not be able to see it again.\r\n' ;;
  *"studio.cli claude-token"*) cat > "$T/saved"; echo "Claude connected ✓ (sign-in saved, encrypted)" ;;
  *"studio.cli claude-status"*) echo "connected (Claude subscription)" ;;
esac
STUB
chmod +x "$T/bin/docker"
export PATH="$T/bin:$PATH"
fail() { echo "FAIL: $*"; exit 1; }

# 1. the wrapped, coloured token is captured whole and handed to the worker over stdin, not argv
out=$(STUDIO_DIR="$T/studio" bash "$HERE/connect-claude.sh" </dev/null 2>&1) || fail "exit code: $out"
[ "$(cat "$T/saved")" = "$TOK" ] || fail "saved token: $(cat "$T/saved")"
grep -q "$TOK" "$T/calls" && fail "token appeared in docker argv"
echo "$out" | grep -q "Claude connected" || fail "no success line"
ls /tmp | grep -q "^connect-claude" && fail "temp transcript left behind"

# 2. no token (sign-in cancelled) → clear failure, nothing saved
rm -f "$T/saved"
if out=$(NO_TOKEN=1 STUDIO_DIR="$T/studio" bash "$HERE/connect-claude.sh" </dev/null 2>&1); then fail "should fail"; fi
[ ! -e "$T/saved" ] || fail "saved something without a token"
echo "$out" | grep -qi "not signed in\|no token" || fail "unclear failure: $out"
echo "connect_claude_test: OK"
