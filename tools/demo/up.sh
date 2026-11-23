#!/usr/bin/env bash
# Starts the local demo copy: Docker, a local Supabase with the real migrations, and the dashboard on :3000.
# Local only — never deployed. Keys printed by `supabase start` are the CLI's public local defaults.
#   bash tools/demo/up.sh
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
DEMO=$ROOT/tools/demo
SB=$DEMO/.supabase                      # scratch Supabase project (git-ignored)
export SUPABASE_INTERNAL_IMAGE_REGISTRY=${SUPABASE_INTERNAL_IMAGE_REGISTRY:-public.ecr.aws} NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1

docker info >/dev/null 2>&1 || { (dockerd >/tmp/dockerd.log 2>&1 &); for _ in $(seq 30); do docker info >/dev/null 2>&1 && break; sleep 1; done; }

mkdir -p "$SB/supabase/migrations"
[ -f "$SB/supabase/config.toml" ] || (cd "$SB" && npx -y supabase@2 init --force >/dev/null)
cp "$ROOT"/supabase/migrations/*.sql "$SB/supabase/migrations/"
(cd "$SB" && npx -y supabase@2 start -x studio,imgproxy,edge-runtime,logflare,vector,supavisor,mailpit,postgres-meta >/dev/null)
eval "$(cd "$SB" && npx -y supabase@2 status -o env | grep -E '^(API_URL|PUBLISHABLE_KEY|SECRET_KEY)=')"

if [ ! -f "$DEMO/demo.env" ]; then
  cat > "$DEMO/demo.env" <<ENV
NEXT_PUBLIC_SUPABASE_URL=$API_URL
NEXT_PUBLIC_SUPABASE_ANON_KEY=$PUBLISHABLE_KEY
SUPABASE_URL=$API_URL
SUPABASE_SERVICE_ROLE_KEY=$SECRET_KEY
MASTER_KEY=$(openssl rand -base64 32)
APP_URL=http://localhost:3000
SETUP_TOKEN=demo-setup-token
ENV
fi
set -a; . "$DEMO/demo.env"; set +a

cd "$ROOT/apps/web"
if [ "${REBUILD:-0}" = 1 ] || [ ! -f .next/BUILD_ID ] || ! grep -q "$API_URL" .next/required-server-files.json 2>/dev/null; then
  NEXT_TELEMETRY_DISABLED=1 npm run build >/tmp/demo-web-build.log 2>&1
fi
fuser -k 3000/tcp >/dev/null 2>&1 || true; sleep 1
(nohup npx next start -p 3000 >/tmp/demo-web.log 2>&1 &)
for _ in $(seq 30); do curl -s -o /dev/null http://localhost:3000/login && break; sleep 1; done
echo "demo up: http://localhost:3000  (Supabase $API_URL)"
