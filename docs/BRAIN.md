# BRAIN: project memory and handoff. Read all of it before doing anything.

> This is Claude's working memory for this project. The owner switches Claude accounts and sessions; whoever takes over
> continues with the same ownership and quality bar, and the owner should not notice a change.
> **Update this file after every significant step.** Never put secret values here.
> Last updated: 2026-11-23, session 4. **FRESH-START handoff** (see §0.0 first).

## 0. START HERE (next Claude)
1. Read this whole file, then `docs/ARCHITECTURE.md`. Skim `docs/WEB.md`, `docs/SETUP.md`, `docs/tiktok-api-notes.md`.
2. Talk to the owner in **Roman Urdu or simple English** (never Hindi/Devanagari). They are not a developer (§1).
3. A paste-ready prompt for a new session is in `docs/HANDOFF.md`. Do not start new feature work unprompted. Check §0.2 (what the owner still has to do), help them through it, then
   follow §6.

### 0.0 LATEST (2026-11-23): owner is taking it down and will redeploy step by step WITH you
- Owner: "project 1 zip file mein do, main khud dubara deploy karunga tumhare saath taaki mujhe samajh aaye; baaki
  VPS se ya jahan bhi hai har jagah se clean karo."
- Delivered: one zip of the whole repo (code + docs + git history, no secrets) with `START-HERE.txt`.
- VPS cleanup: **owner runs** `sudo bash /opt/overthought-studio/src/infra/uninstall.sh` in Hostinger's Browser
  terminal (cloud sessions cannot SSH). It removes only our cron line, `ots-*` containers/volumes/network/images, our
  block in the other app's Caddyfile (`juc-caddy-1`, backup `*.bak-ots-uninstall`) or Nginx site, and
  `/opt/overthought-studio`. It keeps `/root/overthought-studio-env-backup` (has MASTER_KEY; needed only if the
  same Supabase secrets are reused).
- **Owner decided (2026-11-23): KEEP** Supabase project `xkbgusqmdeocjwxaknjx` (owner login, channels, ideas,
  preview video, encrypted keys) and the GitHub repo. Only the VPS gets uninstalled. Redeploy reuses both; reuse the
  MASTER_KEY from `/root/overthought-studio-env-backup` (else saved keys in Supabase can't be decrypted and must be
  re-entered). The owner will say later what comes next; do not start work unprompted.
- If §0.1 below says "LIVE", that is the state *before* this cleanup. Ask the owner whether uninstall was run.
- **Redeploy together:** go one step at a time and explain *why* each step exists in simple Roman Urdu; let the owner
  type the commands. Order: Supabase (keep or new + `supabase/migrations/*` + `python -m studio.cli seed`) → DNS A
  record `studio → VPS IP` (domain is in the owner's OTHER Hostinger account) → `infra/install.sh` on the VPS →
  `/setup` login → `infra/connect-claude.sh` → keys in Settings → first real video → TikTok app.

### 0.1 Where things stand (2026-11-21)
- **LIVE on the VPS** ("JUC Vps", `2.24.74.240`): web `https://studio.getgrowthnexus.com` (behind the other app's
  Caddy `juc-caddy-1`, via `infra/caddy-attach.sh`) + worker `vps-srv2163482`. Supabase ok. The VPS pulls `main`
  every 10 minutes and rebuilds (`infra/install.sh` timer), so **anything pushed to `main` goes live by itself.**
- Owner login exists (created 2026-11-20). All 5 channels are PAUSED.
- `main` = `e7dd75e`. Tests: worker 75 pass (`cd worker && python -m pytest -q -p no:cacheprovider`); web 9 node
  tests (`cd apps/web && node --experimental-strip-types --test tests/claude-usage.test.mjs`), `npx tsc --noEmit`, `npx next lint` clean;
  infra `bash infra/tests/connect_claude_test.sh`.
- **Claude runs on the owner's Claude Pro sign-in, NOT an API key** (owner, 2026-11-20: "API is messy"). Built and
  pushed; **not yet connected** — the dashboard's Claude card says "Not signed in" until the owner runs the sign-in
  script (§0.2). Details §0.3.
- **No Claude-powered video has ever run end to end.** The only real video is the hand-written doorway preview (§3).
- Keys NOT added yet (owner: "keys skip, video zaroori"): ElevenLabs, RunPod. Nothing is being billed.

### 0.2 What the owner still has to do (walk them through it, one step at a time)
1. On the VPS (Hostinger Browser terminal): `sudo bash /opt/overthought-studio/src/infra/connect-claude.sh` — open
   the link, sign in to Claude, paste the code back. The script captures the token itself; card then says Connected.
   If anything fails: `sudo bash /opt/overthought-studio/src/infra/doctor.sh` and ask for the output (no secrets in it).
2. Supabase → Auth settings: turn OFF public sign-ups; set Site URL to `https://studio.getgrowthnexus.com`.
3. Dashboard → Settings: ElevenLabs key **with User: Read** permission, RunPod key.
4. Delete the Supabase access token named `claude-demo` (api.supabase.com) — not needed any more.
5. Change the VPS root password (it was pasted in chat once). Delete the stray empty Supabase project in the
   "hellowickettravels" org.

### 0.3 The Claude sign-in design (session 3, part 3)
Spec `docs/superpowers/specs/2026-11-20-claude-subscription-design.md`; plan
`docs/superpowers/plans/2026-11-20-claude-subscription.md` (all 8 tasks done, opus final review done, 6 important
findings fixed in `e7dd75e`).
- `worker/studio/claude_cli.py`: runs Claude Code headless (`claude -p … --output-format json --tools … --json-schema
  … --no-session-persistence --setting-sources "" --strict-mcp-config`), CLI pinned **2.1.329**, Node 22 copied from
  `public.ecr.aws/docker/library/node:22-slim` in `worker/Dockerfile`. Token = `claude setup-token` (`sk-ant-oat01-…`),
  stored encrypted as `secrets.claude_oauth_token`, passed only via env `CLAUDE_CODE_OAUTH_TOKEN` (never argv/logs);
  `HOME=$WORK/.claude-home`, empty temp cwd. Errors: limit text → `LimitReached` (resume time from `|epoch`, then
  "resets 3pm (TZ)", then the usage endpoint, else +1h); overload/5xx/network/timeout → `ServiceDown` (park+retry);
  auth → `NotConfigured`; else `RuntimeError` (token scrubbed).
- `llm.py`: `backend()` = "subscription" unless an API key is saved AND `settings.llm_backend == "api"`. Heavy work
  uses the plan's default model (or `settings.subscription_model`); scorecard/smoke use `sonnet`. Research uses
  WebSearch+WebFetch with a `{notes, sources[]}` schema; empty result → RuntimeError (retried). Spend recorded as $0.
- Limits: `LimitReached` parks the job (doesn't count to MAX_WAITS, never trips the circuit breaker); stored as
  services.status `warning` + `details.limited/resume_at` (**no DB migration**); `ops._resume_waiting` re-queues
  after `resume_at`. UI shows it amber/calm, never red.
- `usage.py`: reads `https://api.anthropic.com/api/oauth/usage` (same as Claude Code's /usage; header
  `anthropic-beta: oauth-2025-04-20`). **Unverified whether it accepts setup-token tokens** — if not, card shows
  "estimate", counts videos only, pacing stays off (park-and-resume still works). Per-video weekly-% = avg of last 5
  measured videos (settings row `claude_video_usage`). **Pacing**: if `week% + remaining_slots × per_video% ≥ 95`,
  the scheduler keeps only the first post time per day (evening slots dropped; existing videos never moved).
  Planning is round-robin across channels (stuck/blocked channels ignored).
- CLI: `python -m studio.cli claude-token` (reads stdin, validates with one tiny sonnet call before saving),
  `claude-status`. `infra/connect-claude.sh` wraps `setup-token` in `script`, strips ANSI, joins wrapped lines,
  shreds the temp file. `infra/doctor.sh` has a "Claude sign-in" section.
- Dashboard: Claude card on Overview + Settings (`#claude`), `components/claude-usage.tsx`, pure view model
  `lib/claude-usage.ts`. API-key path kept under Settings → "Advanced" (labelled optional). Money balance hidden for
  Claude on the plan.
- Told the owner: Pro limit is shared with their own Claude chats; 5 channels × 2/day may not fit Pro — the first
  real videos measure it (card shows per-video %); Anthropic's terms allow own-use scripts, volume line undefined;
  owner accepted ("goahead").
- **Not verified here:** the full worker image build (sandbox can't reach Debian apt); the Node/CLI stage was built
  and run separately. First VPS rebuild after `e7dd75e` is the real test — if it breaks, ask for `doctor.sh` output.
- **Deferred minors** (known, low impact): pacing has no hysteresis (can flip mid-week); lost-update race on the
  `claude_video_usage` settings row; `smoke` (run by doctor) spends a tiny bit of limit each time; an unavailable
  `subscription_model` fails as a plain RuntimeError; the token is visible once on screen/scrollback during sign-in;
  "out of extra usage"/"Opus limit" wordings are not matched as limits.

### 0.4 Earlier in session 3 (done)
- Production-readiness plan `docs/superpowers/plans/2026-11-20-production-readiness.md`: Tasks 0–4 done (env hosts +
  proxy secrets, offline e2e pipeline tests — fixed resume re-paying RunPod/ElevenLabs, Claude request-contract
  tests, `studio.cli smoke` + `infra/doctor.sh`, docs no longer mention Vercel). **Task 6 (first real video) is
  still open** — it is §6 step 3.
- Install went live 2026-11-20 08:30 UTC. Fixed on the way: pasted Supabase key had a stray char → installer/worker/
  web strip non-key chars; setup token + MASTER_KEY leaked in an owner screenshot → rotated; installer no longer
  prints MASTER_KEY.
- Audit + video guide plan `docs/superpowers/plans/2026-11-20-audit-and-video-guide.md`:
  - Local demo copy `tools/demo` (`up.sh` = local Supabase + dashboard on :3000; `seed_demo.py`; `login.cjs`;
    `ui-check.cjs --shots` = phone/laptop checks). **Claude may NOT log into the owner's real account** (safety check
    refused a magic-link session) — use the demo copy for UI work and screenshots.
  - Dashboard fixes LIVE (chart controls, idea bank on phones, scroll hints, confirm before removing a key, skeletons,
    CSP follows Supabase URL scheme).
  - Roman Urdu video guide delivered (5:18; 1080p + 720p + SRT). Pipeline `tools/guide`; re-run after UI changes:
    `bash tools/demo/up.sh && python tools/demo/seed_demo.py && node tools/demo/login.cjs && python tools/guide/tts.py
    build && node tools/guide/record.cjs && python tools/guide/compose.py`. **The guide predates the Claude card** —
    its Anthropic-key part is now outdated; re-record if the owner wants.
  - Audience: owner + their father. The father only watches and approves; money, keys, the red bar → "bete se kahein".
- Cloud env `overthought-studio` (env_01TJ5FBy4nZt3RRkNjTKNPPG) allows Supabase, studio domain, ElevenLabs, RunPod,
  TikTok, d2glxqk2uabbnd.cloudfront.net, speech.platform.bing.com, mcp.hostinger.com; proxy credential for the
  Supabase secret (`apikey`) and api.supabase.com.
- Git push from cloud sessions sometimes returns 403; GitHub MCP `push_files` to `main` works as a fallback.
- Workflow used: superpowers brainstorming → spec → plan → executing-plans (TDD, ledger in git-ignored
  `.superpowers/sdd/…`) → opus final review → one fix pass. Keep using it for new features.

## 1. The owner and how to work with them
- They write **Roman Urdu**. Voice-to-text sometimes shows it in Devanagari script, but it is NOT Hindi.
  **Reply only in Roman Urdu or simple English.**
- Not a developer. Give short, numbered, step-by-step directions and a clear "what I need from you" list.
- Claude has **full ownership**: plan → build → verify → audit → report. Use sub-agents for design, audits and
  reviews. Verify with real runs and screenshots. Send short progress pings, and report fully only when a piece is
  production-ready.
- The owner wants ~100% automation and pays only the tool bills. Two exceptions they agreed to:
  - approving videos at the start;
  - tapping Publish on TikTok drafts until the TikTok app audit passes.
- Secrets: never ask for them in chat. Use the `request_credential` form, or dashboard Settings. The Claude sign-in
  goes only through `infra/connect-claude.sh` on the VPS.
- Things I refused, and the owner accepted:
  - no proxy, static-IP or device masking to fake US presence (Creator Rewards needs a real US-eligible adult per
    monetised account);
  - only official TikTok APIs, no bots or browser automation.
- Ask before anything that posts publicly, spends more than a few dollars unexpectedly, or creates accounts.

## 2. Product: Overthought Studio
A self-running studio for **5 US TikTok channels** targeting the **Creator Rewards Program**.
- **Length:** every video must be **> 60 s**; target 65–90 s. A hard gate enforces this.
- **Look:** pattern-break dark style. Charcoal `#111`, thin white stick figure, one accent colour drawn **in code**
  (never by the image model). The style kit is in `assets/`, from brand repo `realgrowthnexus/overthoug-youtube`.
- **Script formula:** hook at second 0 → curiosity gap → question to the viewer → emotional "you" moment → real study
  on screen (`→ Researcher · Institution · Year`) → twist → payoff and fix → loop line.
- **Accuracy:**
  - real studies only;
  - flag failed replications;
  - correct myths;
  - never round stats into falsehoods;
  - "spot the trick" content is framed as self-protection.
- **Weekly:** an analytics review adjusts pillar and hook weights and tests ONE variable.
- **Dashboard** on `studio.getgrowthnexus.com` (domain confirmed). Live credit balances, and a red bar that always
  says **why** something stopped and how to fix it. This is critical to the owner.

Channels (seeded, all PAUSED; the owner wants to **discuss niches for 2–5 after the app is live**):

| slug | name | accent | ElevenLabs voice |
|---|---|---|---|
| overthought | Overthought: why your brain does that (37 seed ideas) | #FFD60A | Chris `iP95p4xoKVk53GoZ742B` |
| money-brain | Money Brain | #3DDC97 | Eric `cjVigY5qzO86Huf0OWal` |
| tiny-history | Tiny History | #FF7A59 | Brian `nPczCjzI2devNBz1zQrb` |
| how-it-works | How It Works | #4CC9F0 | River `SAz9YHcvj6GT2YYXdXww` |
| myth-busted | Myth Busted | #FF4D6D | Sarah `EXAVITQu4vr4xnSDxMaL` |

## 3. What exists (all on `main` of `realgrowthnexus/overthought-studio`)
- **`apps/web`:** Next.js 15.5 dashboard (App Router, React 19, Tailwind v4, Supabase SSR, `output: "standalone"`).
  - Pages: overview, channels (wizard + tabs), videos (player, approve/reject/regenerate/publish), analytics
    (CSV/XLSX import), reports, TikTok accounts (OAuth connect), settings (encrypted keys, budgets, auto-publish,
    Claude sign-in card + limits), logs (events + jobs), `/privacy`, `/terms`, `/setup` (one-time owner), `/login`.
  - Security-reviewed:
    - an admin check in every loader and action;
    - race-safe `/setup` plus a DB single-owner index;
    - session-bound single-use OAuth state;
    - CSP and HSTS;
    - zod validation.
  - Design-audited: WCAG AA, touch targets, mobile "More" sheet, empty states.
  - Env vars are in `apps/web/.env.example`.
- **`worker/`:** a Python 3.13 worker (`python -m studio.main`).
  - Job lanes: heavy = `produce_video`; light = everything else. Jobs are claimed via the `claim_job` RPC
    (SKIP LOCKED) with a lock heartbeat.
  - Scheduler: a 1-minute tick that keeps the buffer full, assigns slots, and runs periodic jobs once per period
    via `once_key`.
  - Pipeline (`pipeline.py`): research (Claude + web_search) → script (structured output) → scorecard, rewriting
    below 8/10 → fact-check, which is permanent-fail if it fails twice → RunPod Flux scenes → ElevenLabs voice with
    word timings and a length gate → render.
  - Render (`render/`): draw-on lines, accent pop, push-in, word captions, synthesized music bed, safe zones, loop
    crossfade. Output is H.264 1080×1920 at 30 fps, rendered in a subprocess.
  - Ops (`ops.py`):
    - publishing through the official Content Posting API, in draft, private or public mode;
    - stats sync, plus Studio CSV/XLSX import;
    - weekly review;
    - health and credit checks for Anthropic, ElevenLabs, RunPod, TikTok and storage, with auto-resume;
    - budget caps, a circuit breaker, nightly backups to the Supabase `backups` bucket, and cleanup.
  - Hardened by a 25-item code audit. 75 tests (`cd worker && python -m pytest -q -p no:cacheprovider`).
  - Needs **ffmpeg, about 3 CPU cores, about 4–6 GB RAM, and a long-running process**.
- **Supabase:** project `overthought-studio`, ref **`xkbgusqmdeocjwxaknjx`**, us-east-1, org "realgrowthnexus".
  - Migrations 0001–0003 applied.
  - Storage buckets: `videos`, `backups`.
  - The dashboard and worker never talk directly; they share DB tables (`jobs`, `videos`, `channels`, `services`,
    `events`, `spend`, `settings`, `secrets`).
  - Secrets: AES-256-GCM, format `v1:`+b64(iv|ct|tag), env `MASTER_KEY`. It must be identical for web and worker.
  - The owner still has to: turn **off public sign-ups** and set the Site URL (Auth settings).
  - A stray empty project with the same name exists in the "hellowickettravels" org. The owner was asked to delete
    it.
- **`infra/`:**
  - `docker-compose.yml`: worker + web + optional Caddy.
  - `install.sh`: a VPS installer that builds from GitHub, auto-updates every 10 minutes, generates `MASTER_KEY`
    and `SETUP_TOKEN`, and auto-detects Caddy, Nginx or a manual proxy.
  - Both Docker images were verified building and running. Base images come from `public.ecr.aws` because of
    Docker Hub rate limits.
- **Preview:** a real doorway-effect video, id `477ffdfb-06c3-434c-b398-3429e9e750dd` (status `ready`), built from
  the hand-written `worker/fixtures/doorway_script.json`.
  - **The Claude steps have NEVER run end-to-end yet.** That needs the owner's Claude sign-in (§0.2 step 1).

## 4. Known facts and gotchas
- **GitHub Actions are blocked:** the owner's GitHub account is billing-locked. Nothing depends on CI.
- Cloud-session proxy credentials (owner's Default environment): `api.runpod.ai`, `api.elevenlabs.io`
  (`xi-api-key`), and `xkbgusqmdeocjwxaknjx.supabase.co` (Supabase secret as `apikey`). Code sends a placeholder.
  - Outbound SSH is blocked.
  - Anthropic hosts can't be proxy-injected.
  - Docker builds in the sandbox need the proxy CA (temporary Dockerfile variant only).
- The ElevenLabs key saved in the cloud env lacks `user_read`, so it can't read the balance. The owner should create
  a key with User: Read.
- `docs/SETUP.md` describes the VPS flow, incl. Step 5a "Connect Claude". Remove everything: `infra/uninstall.sh`.
- The 5-hour Claude limit is expected to hit sometimes; that is a calm pause, not an error (owner agreed).

## 5. Hosting: DECIDED → VPS (2026-11-19)
- Owner reversed the Web App Hosting idea: "sab VPS par, purane decision ke mutabiq".
- VPS: "JUC Vps", `ssh root@2.24.74.240`. The owner pasted the root password in chat; told them to change it.
  Never store it. Outbound SSH from cloud sessions is blocked, so the **owner runs the installer** in Hostinger's
  Browser terminal: `curl -fsSL https://raw.githubusercontent.com/realgrowthnexus/overthought-studio/main/infra/install.sh | bash`
- Repo is public, so `install.sh` no longer needs a GitHub token (optional `GITHUB_TOKEN` env).
- The `MASTER_KEY` made for Web App Hosting is unused; the installer generates the real one into `/opt/overthought-studio/.env`.
- Domain `getgrowthnexus.com` lives in the owner's OTHER Hostinger account: add A record `studio → 2.24.74.240` there.
- Hostinger plugin is installed (needs owner OAuth sign-in in claude.ai Connectors); env `overthought-studio`
  (env_01TJ5FBy4nZt3RRkNjTKNPPG) allows `mcp.hostinger.com`. Not required for the VPS path.

History: on 2026-11-18 the owner briefly planned Hostinger Web App Hosting (zip upload); reversed on 2026-11-19. Details are in git history.

## 6. Next steps (in order)
1. ~~Installer, DNS, `/setup` owner login~~ — DONE 2026-11-20.
2. Owner tasks in §0.2 (Claude sign-in first).
3. Run a **real Claude-powered doorway video** through the full pipeline: dashboard → Overthought → "Make a video
   now", or `python -m studio.cli`.
   - Check script quality, fact-check, length and render, then send it to the owner.
   - **Ask before spending** (RunPod + ElevenLabs cost a little per video).
   - Read the Claude card's per-video weekly % → tell the owner honestly how many videos/day Pro can carry.
   - Also verify browser login works (it couldn't be tested in the sandbox).
4. TikTok developer app (guide on the dashboard's TikTok accounts page):
   - sandbox target users;
   - connect accounts;
   - test a draft upload;
   - submit for review, then apply for the Content Posting API audit.
5. Final report to the owner in Roman Urdu.
6. Then discuss niches for channels 2–5.

## 7. Quality bar (do not lower)
- Design: modern, custom, WCAG AA, proper touch targets, smooth motion with reduced-motion support, mobile, light and
  dark.
- Backend: every mutation validated and admin-checked, no secrets client-side, fast.
- Verify with real runs and screenshots. Report failures honestly.
