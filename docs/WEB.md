# Dashboard (apps/web)

Next.js 15 App Router · React 19 · Tailwind v4 · Supabase (auth, data, realtime, storage).

## Deploy on Vercel
- Root directory: `apps/web` · Framework: Next.js · Node 22.
- Environment variables (Production):

| Name | Value |
|---|---|
| `NEXT_PUBLIC_SUPABASE_URL` | `https://xkbgusqmdeocjwxaknjx.supabase.co` |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | the publishable key (`sb_publishable_…`) |
| `SUPABASE_SERVICE_ROLE_KEY` | the secret key (`sb_secret_…`) — server only |
| `MASTER_KEY` | `openssl rand -base64 32` — **same value as the worker** |
| `APP_URL` | `https://studio.<your-domain>` (no trailing slash) |
| `SETUP_TOKEN` | any long random string; used once at `/setup` |

- Domain: add `studio.<your-domain>` in Vercel → Domains, then a CNAME to `cname.vercel-dns.com`.
- Supabase → Authentication → URL configuration: Site URL = `APP_URL`. Turn **off** "Allow new users to sign up" (owner is created by `/setup` through the admin API).

## First run
1. Open `/setup`, enter `SETUP_TOKEN`, your email and a password. Works only while no owner exists.
2. Settings → API keys: paste Claude, ElevenLabs, RunPod, TikTok client key/secret.
3. TikTok accounts: follow the on-page guide (redirect URI, privacy and terms URLs are shown with copy buttons).

## Routes
| Route | Purpose |
|---|---|
| `/` | Overview: pause switch, KPIs, live production line, up next, activity, services |
| `/channels`, `/channels/new`, `/channels/[slug]` (+ `/videos`, `/ideas`, `/strategy`, `/settings`) | Channel management |
| `/videos`, `/videos/[id]` | All videos; detail with player, script, sources, fact-check, caption, actions |
| `/analytics` | Trend chart, performance vs channel median, TikTok Studio CSV import |
| `/reports` | Weekly reports |
| `/accounts` | TikTok accounts, connect/disconnect, app setup guide |
| `/settings` | Encrypted API keys, budgets, model, auto-publish, Claude credit, worker status |
| `/logs` | Events and job queue (retry/cancel) |
| `/privacy`, `/terms` | Public pages for TikTok app review |
| `/api/tiktok/connect`, `/api/tiktok/callback` | Login Kit OAuth |

## How it talks to the worker
Only through Supabase: buttons insert rows into `jobs` (deduped per target), edits write `channels`/`settings`/`secrets`,
approvals update `videos`. Pages re-render live from Realtime on `videos`, `jobs`, `events`, `channels`, `services`.

## Security notes
- Every server action calls `requireAdmin()` and validates input with zod.
- Service-role client lives in `lib/supabase/service.ts` (`server-only`); secrets are encrypted with AES-256-GCM
  (`lib/crypto.ts`, format `v1:` + base64(iv‖ct‖tag)) and never sent back to the browser — only the last 4 characters.
- `/setup` fails closed if the database can't be read.
- Middleware runs on the Node.js runtime and refreshes the Supabase session cookie.
