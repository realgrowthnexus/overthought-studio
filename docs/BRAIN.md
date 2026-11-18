# BRAIN: project memory and handoff (read fully before doing anything)

> This file is Claude's working memory for this project. The owner may switch Claude accounts/sessions at any time;
> the next Claude must continue **with the same understanding, ownership and quality bar**, so the owner feels no
> difference. **Update this file after every significant step** (decisions, state changes, new IDs, open issues).
> Never put secret values here (keys, tokens, passwords). Last updated: 2026-11-18.

## 1. Who the owner is and how to work with them
- They write in **Roman Urdu** (sometimes via voice-to-text that renders as Devanagari script). It is NOT Hindi.
  **Always reply in Roman Urdu or simple English**, never Hindi or Devanagari.
- Not a developer. Wants **simple, step-by-step directions** and short lists of "what I need from you".
- Has handed Claude **full ownership**: "take over, you are in charge, plan → build → verify → audit → report".
  Work like a senior team at Anthropic: plan big, split into phases, use sub-agents (design, design audit, dev,
  code review), verify everything yourself (tests, screenshots, real renders), then report.
  **Report back only when a chunk is truly finished and production-ready**, with brief progress pings in between.
- Owner pays the tool bills only and wants **~100% automation** with no monthly manual work.
  Owner-approved exceptions: approving videos at the start, and tapping Publish on TikTok drafts until the TikTok
  app audit passes.
- Owner will provide any tool or account needed (RunPod, ElevenLabs, Higgsfield, Claude API, VPS, domains). Ask for
  things as a **simple numbered list**.
- Secrets: owner said pasting in chat is "ok", but **never ask for that**. Use the secure credential form
  (`request_credential`) or the dashboard Settings page. Anthropic keys can't use the credential form, so they
  go in dashboard Settings.

## 2. The product (what we are building)
**Overthought Studio**: a self-running system for **5 US TikTok channels** aimed at the **Creator Rewards Program**.
- Every video **must be > 60 s** (target 65–90 s); CRP pays only on 1 min+ videos. A hard gate in code checks this.
- **Pattern-break style**: dark charcoal background with a thin white stick figure. Competitors use white
  backgrounds; ours is dark. Yellow `#FFD60A` accent only on the "glitch" element, added in code. The full style
  kit is in `assets/` (copied from the brand repo `realgrowthnexus/overthoug-youtube`). Don't redesign the
  locked style.
- **Scripts must be researched**: SEO/search phrases, audience interest, targeting. Strong hook in second 0 →
  curiosity gap → a question to the viewer → emotional "you" connection → real study on screen
  (`→ Researcher · Institution · Year`) → twist → payoff and fix → loop line.
- **Accuracy is the brand**:
  - Real studies only.
  - Flag failed replications (ego depletion, power posing).
  - Correct myths (Kitty Genovese "38 witnesses").
  - Never round stats into falsehoods.
  - "Spot the trick" content is framed as self-protection.
- **Every 7 days**: analytics → weekly review → adjust pillar and hook weights, test ONE variable at a time.
- **Dashboard on the owner's domain**:
  - See and track everything.
  - Connect TikTok accounts (official OAuth).
  - Start, stop or edit any channel; add accounts.
  - See **live credit balances and WHY anything stopped**. This is critical: the owner must never be left
    guessing that credits ran out.
- **Guardrails we agreed**:
  - Only the official TikTok APIs. No bots, browser automation or unofficial posting.
  - **I refused to build any proxy, static-IP or device-masking setup** to fake US presence. Creator Rewards needs
    a real US-eligible adult per monetised account. The owner agreed.
  - Ask before anything that posts publicly, spends more than a few dollars unexpectedly, or creates accounts.

### The 5 channels (seeded, editable in the dashboard; all start PAUSED)
| slug | name | accent | voice (ElevenLabs id) |
|---|---|---|---|
| overthought | Overthought: why your brain does that | #FFD60A | Chris `iP95p4xoKVk53GoZ742B` |
| money-brain | Money Brain: psychology of money (US) | #3DDC97 | Eric `cjVigY5qzO86Huf0OWal` |
| tiny-history | Tiny History: strange true history | #FF7A59 | Brian `nPczCjzI2devNBz1zQrb` |
| how-it-works | How It Works: everyday science and tech | #4CC9F0 | River `SAz9YHcvj6GT2YYXdXww` |
| myth-busted | Myth Busted: famous facts that are wrong | #FF4D6D | Sarah `EXAVITQu4vr4xnSDxMaL` |

The owner said **niche selection will be discussed after the app is finished**, so these 5 are placeholders.
Overthought has 37 seed ideas.

## 3. Architecture (details in `docs/ARCHITECTURE.md`)
- `apps/web`: Next.js 15 dashboard, deployed on **Vercel** at **studio.getgrowthnexus.com** (confirmed by the owner
  2026-11-18). The owner was told to add DNS `CNAME studio → cname.vercel-dns.com` (DNS-only if on Cloudflare).
- `worker/`: a Python worker in Docker on the owner's **Hostinger KVM 4 VPS** (Ubuntu 24, 4 vCPU, 16 GB RAM,
  200 GB disk).
  - **Another app already runs on that VPS**. Ours is isolated: no published ports, cpus 3.0, mem 6g.
  - The VPS **builds from source** (GitHub fine-grained read token) and auto-updates every 10 minutes via cron
    (`infra/install.sh`).
  - The VPS is stateless; all data lives in Supabase, so moving to a new VPS means re-running the installer.
- **Supabase** project `overthought-studio`, ref **`xkbgusqmdeocjwxaknjx`**, region us-east-1, org
  "realgrowthnexus". Schema: `supabase/migrations/0001_init.sql` (applied).
  - The dashboard ↔ worker contract runs entirely through DB tables: jobs queue + `claim_job` RPC with
    SKIP LOCKED, services, events, spend, settings, secrets.
  - (A stray empty project with the same name was accidentally created in the "hellowickettravels" org while the
    connector pointed there. The owner was told to delete it.)
- **Secrets**: `secrets` table, AES-256-GCM, format `v1:`+b64(iv|ct|tag), env `MASTER_KEY` (same on Vercel and
  VPS). The worker falls back to env vars.
- **External APIs**:
  - Claude API (default `claude-opus-5-5`, adaptive thinking, server-side fallbacks, web_search_20260209,
    structured outputs via `client.beta.messages.parse`).
  - RunPod Flux dev (`api.runpod.ai/v2/black-forest-labs-flux-1-dev/runsync`, ~$0.012/image).
  - ElevenLabs `with-timestamps` (word timings → captions).
  - TikTok Content Posting API + Display API; facts in `docs/tiktok-api-notes.md`.
- **Render engine** (`worker/studio/render/`), all original code:
  - Geodesic "draw-on" line animation.
  - Code-drawn accents with pop.
  - Push-in toward the figure.
  - Word captions.
  - Synthesized music bed (no licensing).
  - Safe zones (text centred at x=500).
  - Loop crossfade.
  - Output H.264 1080×1920 30 fps.
  - Rendering runs in a subprocess (fork-safe).

## 4. Current state (keep this section current)
- ✅ Schema applied; 5 channels + 37 Overthought ideas seeded.
- ✅ Worker built: pipeline, scheduler, ops, TikTok, health/credits, backups. 8 unit tests pass. Docker image
  builds.
- ✅ Real preview video rendered: doorway effect, 90 s, $0.64 total. Video id
  `477ffdfb-06c3-434c-b398-3429e9e750dd`, script from `worker/fixtures/doorway_script.json`, hand-written. Sent
  to the owner.
- 🔄 Dashboard being built by a sub-agent on a worktree branch; it must be merged into main.
- 🔄 Worker code audit running (sub-agent). Apply its fixes.
- ⏳ **Claude-API steps not yet run end-to-end.** The Anthropic key will be entered in dashboard Settings after
  deploy. Then run a real doorway video through the full pipeline and verify the fact-check quality.
- ⏳ Deploy:
  - Vercel: the Vercel MCP disconnected. Either the owner imports the repo in the Vercel UI (`docs/SETUP.md`
    step 1), or ask for a Vercel token via the credential form for `api.vercel.com` and deploy with the CLI.
  - VPS: the owner pastes the installer.
  - TikTok developer app: owner, per the guide.
- ⚠ **GitHub Actions blocked**: the owner's GitHub account is locked for billing. The CI workflow
  (`.github/workflows/tests.yml`) won't run until that is fixed. Nothing depends on it.
- ⚠ The ElevenLabs key currently saved in this cloud env lacks `user_read`, so balance can't be read. The owner
  should create a key with User: Read when entering it in Settings.
- `MASTER_KEY` and `SETUP_TOKEN` for production were generated in the old session's scratchpad (not in the
  repo). **If they are lost before deploy, generate new ones** (`openssl rand -base64 32`, `openssl rand -hex 16`).
  Nothing is encrypted with them yet.

## 5. Cloud-session facts (Claude Code on the web)
- Proxy-injected credentials in the owner's Default environment: `api.runpod.ai` (RunPod),
  `api.elevenlabs.io` (`xi-api-key`), `xkbgusqmdeocjwxaknjx.supabase.co` (Supabase secret as `apikey`). Code
  sends a placeholder; the proxy replaces it.
  - The worker's `db.py` only sends `apikey`, so it works with the proxy.
  - Anthropic hosts can't be proxy-injected.
- Outbound SSH (port 22) is blocked from the cloud container, so the VPS can't be reached directly. The owner
  runs commands in the Hostinger browser terminal.
- Docker builds in this container need the proxy CA for pip (temporary Dockerfile variant); the production
  Dockerfile is clean.
- Run worker code with `cd worker && . .venv/bin/activate && python -m studio.cli …`. Create the venv from
  `worker/requirements.txt` if it's missing.

## 6. Next steps (in order)
1. Merge the dashboard branch; run the design audit (contrast, button sizes, type, motion, scroll, dark/light),
   the code/security audit, and the performance pass; fix everything.
2. Apply the worker audit fixes; re-run tests and a render.
3. Deploy the dashboard (Vercel) and give the owner exact env values plus the paste-ready VPS installer command.
4. The owner enters keys in Settings. Run a full Claude-powered doorway video, check script quality, fact-check
   and length, then send it to the owner.
5. TikTok app setup with the owner (sandbox target users), connect accounts, test a draft upload.
6. Final report to the owner in Roman Urdu: what's live, how to use it, costs, what is left for them.
7. Then discuss niche selection for channels 2–5 with the owner.

## 7. Quality bar (do not lower)
- Design: modern, custom (no generic templates), WCAG AA contrast, proper button sizes, smooth motion with
  reduced-motion support, responsive on mobile, light and dark.
- Backend: fast (RSC, minimal JS), every mutation validated and admin-checked, no secrets in client bundles.
- Verify with real runs and screenshots before claiming anything works. Report failures honestly.
