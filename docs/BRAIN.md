# BRAIN: project memory and handoff. Read all of it before doing anything.

> This is Claude's working memory for this project. The owner switches Claude accounts and sessions; whoever takes over
> continues with the same ownership and quality bar, and the owner should not notice a change.
> **Update this file after every significant step.** Never put secret values here.
> Last updated: 2026-11-20, session 3.

## 0. START HERE (next Claude)
1. Read this file, then `docs/ARCHITECTURE.md`. Skim `docs/WEB.md` and `docs/tiktok-api-notes.md`.
2. **Hosting is DECIDED (2026-11-19, owner):** everything (web + worker) goes on the Hostinger **VPS "JUC Vps"**
   (IP `2.24.74.240`) with `infra/install.sh`, exactly as originally designed. Web App Hosting is NOT used. See §5.
3. Then follow §6 (next steps) in order.
4. **Session 3 (2026-11-20):** owner said "take charge, make it production ready end to end" and left the method to me
   (Native/inline). Plan: `docs/superpowers/plans/2026-11-20-production-readiness.md`; ledger (git-ignored):
   `.superpowers/sdd/2026-11-20-production-readiness/progress.md`.
   - DONE: Task 0 (env `overthought-studio` now allows Supabase, studio domain, ElevenLabs, RunPod, TikTok hosts; Supabase
     secret saved as proxy `apikey`), Task 1 (offline e2e pipeline tests; fixed: resume on a fresh machine re-paid
     RunPod/ElevenLabs), Task 2 (Claude request-contract tests; no fix needed), Task 3 (`studio.cli smoke`,
     `infra/doctor.sh`), Task 4 (docs no longer mention Vercel). 24 worker tests pass.
   - NEXT: Task 5. Owner was given the installer + DNS steps on 2026-11-20 and is running them. Live state then:
     channels seeded and paused, no worker heartbeat, no secrets saved, dashboard not reachable yet.

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
1. Owner runs the installer on the VPS (§5), adds DNS A record, sends me the installer output (NOT the keys).
2. Owner tasks:
   - DNS;
   - Supabase Auth settings;
   - `/setup` to create the owner login;
   - keys in Settings: Anthropic (plus credit balance), ElevenLabs (with User: Read), RunPod.
3. Run a **real Claude-powered doorway video** through the full pipeline: dashboard → Overthought → "Make a video
   now", or `python -m studio.cli`.
   - Check script quality, fact-check, length and render, then send it to the owner.
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
