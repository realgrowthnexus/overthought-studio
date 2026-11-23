# BRAIN: project memory and handoff. Read all of it before doing anything.

> This is Claude's working memory for this project. The owner switches Claude accounts and sessions; whoever takes over
> continues with the same ownership and quality bar, and the owner should not notice a change.
> **Update this file after every significant step.** Never put secret values here.
> Last updated: 2026-11-23, end of session 1 (FINAL handoff, fresh-start package).

## 0. START HERE (next Claude)
1. Read this file, then `docs/ARCHITECTURE.md`. Skim `docs/WEB.md` and `docs/tiktok-api-notes.md`.
2. **Status 2026-11-23: FRESH START.** The owner asked for the whole project as ONE zip on their own PC. They will
   **redeploy it themselves, step by step, together with you, so they understand every step.** Nothing is live:
   the VPS installer was never run, and no dashboard is confirmed deployed anywhere.
   - Go slowly. One step at a time, explain *why* in simple Roman Urdu, wait for the owner to confirm each step.
   - Ask the owner first which pieces still exist (see §5): GitHub repo, Supabase project, Hostinger upload.
3. Then follow §6 (next steps) in order.

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
- Secrets: never ask for them in chat. Use the `request_credential` form, or dashboard Settings. Anthropic keys
  can't go through the form, so they go only in dashboard Settings.
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
    Claude credit), logs (events + jobs), `/privacy`, `/terms`, `/setup` (one-time owner), `/login`.
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
  - Hardened by a 25-item code audit. 10 unit tests (`cd worker && python -m pytest -q tests`).
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
  - **The Claude-API steps have NEVER run end-to-end yet.** That needs the owner's Anthropic key in Settings.

## 4. Known facts and gotchas
- **GitHub Actions are blocked:** the owner's GitHub account is billing-locked. Nothing depends on CI.
- Cloud-session proxy credentials (owner's Default environment): `api.runpod.ai`, `api.elevenlabs.io`
  (`xi-api-key`), and `xkbgusqmdeocjwxaknjx.supabase.co` (Supabase secret as `apikey`). Code sends a placeholder.
  - Outbound SSH is blocked.
  - Anthropic hosts can't be proxy-injected.
  - Docker builds in the sandbox need the proxy CA (temporary Dockerfile variant only).
- The ElevenLabs key saved in the cloud env lacks `user_read`, so it can't read the balance. The owner should create
  a key with User: Read.
- `docs/SETUP.md` currently describes the **VPS** flow. Rewrite it once the hosting decision in §5 is made.

## 5. Hosting plan and what may still exist
**Target hosting:**
- **Dashboard (`apps/web`)** → Hostinger **Web App Hosting** (owner's 12-month plan). It currently offers zip
  upload only (no GitHub connect). Settings: Framework Next.js · Node 22 (or 20) · install `npm install` ·
  build `npm run build` · start `npm start` · root = folder with `package.json` (zip `apps/web` alone).
  Env vars: `apps/web/.env.example`. Generate fresh `MASTER_KEY` (`openssl rand -base64 32`) and `SETUP_TOKEN`
  (`openssl rand -hex 16`) together with the owner; the owner keeps them in a password manager.
- **Worker (`worker/`)** CANNOT run on web-app hosting (ffmpeg, multi-minute renders, 24/7 process). Options:
  (a) the owner's Hostinger KVM 4 VPS, worker only (`infra/install.sh`, drop web/caddy services);
  (b) a small container host (Railway/Render/Fly/Hetzner) with `worker/Dockerfile`; (c) RunPod CPU pod.
  Recommend (a) if the owner still has the VPS. **Same `MASTER_KEY` on web and worker.**

**What existed at handoff (2026-11-23), check with the owner before reusing or deleting:**
- GitHub repo `realgrowthnexus/overthought-studio` (code on `main`).
- Supabase project ref `xkbgusqmdeocjwxaknjx` (realgrowthnexus org): migrations 0001–0003 applied, 5 paused
  channels + 37 ideas seeded, one preview video. If it was deleted, create a new project, run
  `supabase/migrations/0001..0003` in order, then `python -m studio.cli seed`, and update the URL/publishable key
  in `infra/install.sh` and env files.
- Earlier-delivered files (`hostinger-env-variables.txt` etc.) are superseded; generate fresh keys on redeploy.
- Cloud-session proxy credentials for RunPod/ElevenLabs/Supabase lived in the owner's Claude cloud environment
  only (not in the zip).

## 6. Next steps (in order, together with the owner)
1. Supabase: confirm or recreate the project (see §5). Auth: sign-ups OFF, Site URL
   `https://studio.getgrowthnexus.com`.
2. Dashboard on Hostinger Web App Hosting (zip of `apps/web`), env vars, domain `studio.getgrowthnexus.com`
   (follow Hostinger's DNS instructions), then `/setup` with the SETUP_TOKEN to create the owner login.
3. Worker host (§5), same MASTER_KEY.
4. Keys in dashboard Settings: Anthropic (plus credit balance), ElevenLabs (with User: Read), RunPod.
5. Run a **real Claude-powered doorway video** end to end (dashboard → Overthought → "Make a video now").
   Check script quality, fact-check, length, render; verify browser login.
6. TikTok developer app (guide on the dashboard's TikTok accounts page): sandbox users → connect accounts →
   draft upload test → review → Content Posting API audit.
7. Rewrite `docs/SETUP.md` for the final hosting. Final report in Roman Urdu. Then discuss niches for channels 2–5.

## 7. Quality bar (do not lower)
- Design: modern, custom, WCAG AA, proper touch targets, smooth motion with reduced-motion support, mobile, light and
  dark.
- Backend: every mutation validated and admin-checked, no secrets client-side, fast.
- Verify with real runs and screenshots. Report failures honestly.
