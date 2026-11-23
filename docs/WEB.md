# Dashboard (apps/web)

Next.js 15 App Router · React 19 · Tailwind v4 · Supabase (auth, data, realtime, storage).

## Deploy (VPS, Docker)
Deployed by `infra/install.sh` on the VPS as the `web` container (standalone Next.js, Node 22), on
`127.0.0.1:3100` behind Caddy or Nginx. The installer writes these env vars to `/opt/overthought-studio/.env`:

| Name | Value |
|---|---|
| `NEXT_PUBLIC_SUPABASE_URL` | `https://xkbgusqmdeocjwxaknjx.supabase.co` |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | the publishable key (`sb_publishable_…`) |
| `SUPABASE_SERVICE_ROLE_KEY` | the secret key (`sb_secret_…`) — server only |
| `MASTER_KEY` | `openssl rand -base64 32` — **same value as the worker** |
| `APP_URL` | `https://studio.<your-domain>` (no trailing slash) |
| `SETUP_TOKEN` | any long random string; used once at `/setup` |

- Domain: an A record `studio` → the VPS IP. The installer sets up HTTPS.
- Supabase → Authentication → URL configuration: Site URL = `APP_URL`. Turn **off** "Allow new users to sign up" (owner is created by `/setup` through the admin API).

## First run
1. Open `/setup`, enter `SETUP_TOKEN`, your email and a password. Works only while no owner exists.
2. Claude: run `infra/connect-claude.sh` on the VPS once (signs in with the owner's Claude plan; no API key).
   Settings → API keys: paste RunPod and the TikTok client key/secret. (The voice is free and needs no key.)
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
| `/settings` | Claude card (sign-in, 5-hour/weekly limits, pacing), encrypted API keys, budgets, model, auto-publish, worker status; API credit under "Advanced" |
| `/logs` | Events and job queue (retry/cancel) |
| `/privacy`, `/terms` | Public pages for TikTok app review |
| `/api/tiktok/connect`, `/api/tiktok/callback` | Login Kit OAuth |

## Design system notes
- Tokens live in `app/globals.css` (`:root` = warm paper, `.dark` = charcoal). Adding `dark` to any element re-scopes the
  tokens, used for always-dark surfaces (login brand panel, video frame).
- Contrast (WCAG AA, checked from the token hex values): body text `ink`/`ink-2`/`ink-3` ≥ 4.5:1 on every surface in both
  themes (lowest: `ink-3` on `inset`, light, 4.53:1). Status colours ≥ 4.5:1 on their soft badge fills.
- `accent` (#FFD60A) is for fills with dark text on top (primary button, active step). For small marks — dots, ticks,
  tab underlines, thin progress bars, link underlines — use `accent-mark`: yellow in dark mode, ochre `#9a7400` on paper
  (3.6:1; raw yellow is 1.2:1 there).
- Form controls and switch tracks use `line-input` (≥ 3:1 against `bg` and `elev`); `line`/`line-strong` are for dividers only.
- Touch: add `tap` (plus `relative`) to compact controls; on coarse pointers it grows the hit area to 44px without
  changing the look. `scroll-fade-x` fades the trailing edge of horizontal scroll rows on phones.
- Dates/times in server components are fine (no hydration). Client components must not format "now"-relative times
  without `suppressHydrationWarning`. `formatDetection` is off so iOS Safari doesn't rewrite dates/numbers into links
  before hydration (React #418).

## How it talks to the worker
Only through Supabase: buttons insert rows into `jobs` (deduped per target), edits write `channels`/`settings`/`secrets`,
approvals update `videos`. Pages re-render live from Realtime on `videos`, `jobs`, `events`, `channels`, `services`.

## Security notes
- **AuthZ in depth**: middleware only refreshes the session and redirects. The real gate is server-side:
  every server action runs `requireAdmin()` before any service-role call, every loader in `lib/data.ts` calls it
  too (cached per request), pages use `requireAdminPage()`, route handlers use `getAdmin()`. Signed-in users who
  aren't in `admins` land on `/login?error=not_admin`.
- **Validation**: zod on every mutation. `enqueueJob` accepts only dashboard job types, each with a strict payload
  schema (production stages whitelisted), and checks the target row exists. Channel JSON fields are size-capped;
  caption + hashtags must fit TikTok's 2200-char title; CSV/XLSX import checks extension + MIME, max 20 MB, and the
  storage path is built only from the channel uuid, a timestamp and the extension.
- **/setup**: answers only while no owner exists and fails closed when the DB can't be read. `SETUP_TOKEN`
  (≥ 12 chars) is compared in constant time on SHA-256 digests. Claims are serialized, and a post-insert
  earliest-row check rolls back a second owner created concurrently.
- **TikTok OAuth**: 256-bit `state`, stored in `oauth_states` with a hash binding it to the admin
  (`code_verifier` column, unused by web login) and mirrored in an httpOnly SameSite=Lax cookie scoped to the
  callback. The callback deletes and reads the row in one statement (single use), rejects anything older than
  10 minutes, uses the exact `APP_URL/api/tiktok/callback` redirect URI, and redirects only to `APP_URL`.
- **Secrets**: service-role client (`lib/supabase/service.ts`), `lib/crypto.ts`, `lib/secrets.ts`, `lib/auth.ts`
  are `server-only`. AES-256-GCM, format `v1:` + base64(iv‖ct‖tag), 16-byte tag pinned; interop with
  `worker/studio/crypto.py` tested both ways. Only the last 4 characters (`hint`) ever reach the browser;
  `tiktok_accounts` token columns are never selected.
- **Headers** (`next.config.ts`): CSP (self + the Supabase project for REST/storage/realtime `wss:`, TikTok CDN
  images; `frame-ancestors 'none'`), HSTS, X-Frame-Options DENY, nosniff, Referrer-Policy, Permissions-Policy, COOP,
  `no-store` on `/api`, `/auth`, `/login`, `/setup`. Scripts still need `'unsafe-inline'` (no nonces yet).
  `images.remotePatterns` is empty (remote images are `unoptimized`), so `/_next/image` isn't an open proxy.
- Auth cookies are `Secure` when `APP_URL` is https. `output: "standalone"` for the Docker image.
