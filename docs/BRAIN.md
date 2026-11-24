# BRAIN: project memory and handoff. Read all of it before doing anything.

> This is Claude's working memory for this project. The owner switches Claude accounts and sessions; whoever takes over
> continues with the same ownership and quality bar, and the owner should not notice a change.
> **Update this file after every significant step.** Never put secret values here.
> Last updated: 2026-11-24, session 6. Read §0.00000 (current work) first, then the older sections.

## 0. START HERE (next Claude)
1. Read this whole file, then `docs/ARCHITECTURE.md`. Skim `docs/WEB.md`, `docs/SETUP.md`, `docs/tiktok-api-notes.md`.
2. Talk to the owner in **Roman Urdu or simple English** (never Hindi/Devanagari). They are not a developer (§1).
3. A paste-ready prompt for a new session is in `docs/HANDOFF.md`. Do not start new feature work unprompted. Check §0.2 (what the owner still has to do), help them through it, then
   follow §6.

### 0.00000 SESSION 6 (2026-11-24): THE CURRENT WORK. Read this first.
The owner handed the project over completely ("tum main ho meri jagah pe, take charge, take responsibility"). They
want the production line 100% working and ready to use. The owner may switch Claude accounts mid-work. Whoever
continues keeps the same quality bar and understanding, and works from the spec, the plan and this section.

**What the owner asked for, in their words, summarised:**
- **Phases.** Audit first, then fix the video line in phases. Never start the next phase until the current one works:
  audit → plan → execute → verify/test → only then the next phase.
  - **Phase 1:** create → research → script. Fast (about 1–2 min, like Claude would do it in chat). No strict or
    hard-coded rules.
  - **Phase 2:** check → visuals plan → images.
  - **Phase 3:** voice → render → ready.
- **The check is light.** It covers only three things:
  - the content is educational or motivating and not too graphic;
  - the video is longer than 1 minute;
  - nothing violates TikTok policy.
  - **No more checking of names, places, institutions or citations.** The old web-search fact-check is removed in
    Phase 2.
- **Claude is fixed to Sonnet (the `sonnet` alias) at medium effort.** Never higher.
- **Features, after the phases:**
  - edit a video's post time, title, caption and cover;
  - channels page as a 3-column card grid with an Edit button;
  - an AI assistant bottom-left that uses the same Claude sign-in, knows all app state (RunPod balance, jobs,
    errors…), and **can do things on command**. Owner: "agar perfectly handle kar sakte ho". Design: every action
    is a button, and it runs only after the owner clicks "Yes".
- The owner approved all of this ("haan"), and also: "mazeed dekho, aur kuch mile to woh bhi kar dena".

**Documents (the binding contract, read both):**
- Spec: `docs/superpowers/specs/2026-11-24-production-line-design.md`. It holds every finding, decision and calls I
  made: §6 approaches, §7.4b audit bugs A1–A11, §7.6 decisions after the builder check.
- Phase 1 plan: `docs/superpowers/plans/2026-11-24-phase1-research-script.md` (Tasks 1–7). Phases 2, 3 and the
  features each get their own plan, written only after the previous phase is verified on the VPS.
- Workflow: superpowers brainstorming → spec → writing-plans → executing-plans inline (TDD per task) → an Opus
  whole-branch review → one fix pass. The execution ledger is in git-ignored
  `.superpowers/sdd/2026-11-24-phase1-research-script/progress.md`. **It is lost in a new container**, so the
  progress list below is the record.

**Why it was broken (root causes found in the audit):**
- **Claude time.** 8–10 min per video: the scorecard loop ran up to 3×, and the web-search fact-check ran up to 3×
  (about 75 s each).
- **The fact-check failed videos on nitpicks** and made scripts hedge every line.
- **Settings said Sonnet/medium, but the subscription path ignored it.** It ran the plan default, and the
  fact-check ran on "high".
- **The word target assumed 2.6 words/s, but Kokoro really speaks about 2.1.** Scripts came out about 110 s, the
  pipeline rewrote them, the rewrite was fact-checked again, and the video failed.
- **Scenes are drawn one by one.**
- **Dashboard gaps.** The `scheduleVideo` action has no UI. Title and cover can't be edited. Channel edit is hidden.
- **11 more bugs (A1–A11 in the spec):**
  - stale voice/scene files are restored on a redo;
  - `from_stage` is re-applied on every retry;
  - videos stay stuck after a worker crash;
  - the breaker is forgiven by any row update;
  - planner spam when there are no ideas;
  - ideas burnt by failures;
  - RunPod network errors are not parked;
  - render hangs for 60 min on an OOM;
  - the TikTok rate-limit retry is dropped (re-posts every minute);
  - a failing publish loops forever;
  - the scheduler overwrites manual times.

**TikTok facts that shape the features:**
- A draft (inbox) upload sends only the file, so the caption and cover are set by the owner in the TikTok app.
- The API's cover can only be a frame timestamp.
- So the Cover feature is a frame picker. Draft mode shows "Copy caption".

**Progress (update after every task):**
- [x] Spec + builder check + deep audit, approved by the owner.
- [x] Phase 1 plan written.
- [x] P1 Task 1: Sonnet + `--effort medium` on every path. `llm.MODEL_ALIAS/API_MODEL/EFFORT`; Settings shows the
  model read-only. CLI 2.1.329 supports `--effort` (verified).
- [x] P1 Task 2: migration `0005_phase1.sql` written. **NOT applied yet.** It is applied in Task 7 with the
  Supabase connector.
- [x] P1 Tasks 3–6 done (TDD, ledger). Worker suite 109 passed. Rulings: a bad scene id is auto-fixed; the pacing
  test fixture now seeds ideas.
- [x] 2026-11-24 09:35 UTC: migration 0005 APPLIED. Global `paused=true` set by Claude (event logged), so only test
  jobs run. **Unpause after Phase 2 is live.** The 3 ideas from the failed videos were returned to `new`
  (`fail_count` 1).
- [x] **PHASE 1 VERIFIED ON THE VPS (2026-11-24 10:10 UTC, worker v1.1.0, main = 9889def).**
  - Opus review: no Critical findings, and the 4 Important ones were fixed: idea release now waits 6 h unless the
    idea is in use; parks keep their attempts; the sweeper is race-safe; `stop_after` is validated.
  - 114 tests pass.
  - 3 test runs (doorway, cocktail party, hypnic jerk), research + script time: **83 s, 80 s, 74 s** (was 8–10 min).
  - 169–174 words (range 150–176), 9–11 beats, 5–6 scenes, sources only from research URLs, self-score 7.5–8.1.
  - The test videos are `rejected` ("Test stopped after script"); their ideas went back to `new`.
  - Deferred minors:
    - a cancelled job counts as a failure;
    - `keep_found_sources` edge cases (dx.doi.org, empty URL);
    - the breaker message flickers;
    - the orphan text says "worker restarted" even after a cancel.
  - Possible tuning later: scripts still carry some soft hedges ("It's a theory, not proven").
- [x] **PHASE 2 VERIFIED ON THE VPS (2026-11-24 11:21 UTC, v1.2.0).**
  - Opus review: 5 Important fixed (no stale scenes after a failed delete, the poll retries the same RunPod job,
    61 s floor, only listed problems block, service errors win over plain errors).
  - 2 test runs (doorway, cocktail party):
    - check 10 s / 12 s, both "passed" with no nitpicks;
    - 6 scenes drawn in parallel in 48 s / 56 s;
    - RunPod $0.072 per video (6 images).
  - I could NOT view the PNGs from the sandbox (storage download needs a key). Sizes are normal (150–260 KB); the
    owner sees them on the dashboard.
- [x] **PHASE 3 VERIFIED ON THE VPS (2026-11-24 11:43 UTC, v1.3.0). The FIRST Claude-made videos ever finished end
  to end.**
  - Doorway: 79.1 s, $0.06, 171 words. Stages: research 45 s, script 30 s, check 5 s, 5 scenes 57 s, voice 28 s,
    render 96 s (~4.3 min in all).
  - Cocktail party: 87.9 s, $0.06, 176 words (~4.6 min).
  - Both are `ready`, waiting for the owner's approval. No speed nudge or rewrite was needed. The learned
    `voice.wps` is 2.08 (n=2).
  - The 3rd (hypnic jerk) hit the Claude Pro **5-hour limit** (resets 13:50 UTC). **Bug found:** the wording "hit
    your 5-hour limit" wasn't matched as a limit, so it was retried as an error.
    - Fixed in 8b9c0f5 (regex + tests).
    - I moved job 24428 to `run_after` 13:55 so it doesn't fail meanwhile.
  - Pro limit reality: about 8 test runs plus 2 full videos used one 5-hour window, together with the owner's own
    chats. Tell the owner honestly: Pro is roughly 4–6 videos per 5 h.
- [x] 12:03 UTC: the studio is UNPAUSED (approval stays ON). Channel `callaletheia` breaker forgiven
  (`failures_forgiven_at` = now), because the old failures came from the removed fact-check.
- [ ] Then Features (video edits, channels grid, assistant).
- Note: the Supabase connector sometimes points at the owner's OTHER Supabase account (Pak SMM). If
  `list_projects` doesn't show xkbgusqmdeocjwxaknjx, ask the owner to switch it back. A proxy secret for that host
  was also saved, but it returned "Invalid API key" (the key may be wrong); don't rely on it.

**Working rules for this session:**
- Develop on branch `claude/quirky-franklin-tiqm5r`. Merge to `main` only at a verified phase boundary: `main`
  deploys itself to the VPS.
- Claude steps can only run on the VPS (the MASTER_KEY is there). Verify with test jobs inserted through the
  Supabase connector, and watch `events` (`data.seconds`).
- Owner updates are short, in Roman Urdu. Don't wait for their reply between phases. Stop only for destructive,
  security-sensitive or money-surprising actions.

### 0.0000 PAUSED by owner (2026-11-24), superseded by §0.00000 above
State before session 6. All 3 Claude videos failed: 94f47cae, a11f686f, da3da7f5. The planner tripped "3 failed in
24h".
Owner said "save progress, stop everything, I will continue later". State at pause:
- All code is on `main` (last: b1278a4 fact-check severity). VPS auto-deploys from main. Demo copy is stopped.
- Retry job 21537 (video `da3da7f5-95be-4a06-ab88-146eddfc66be`, "In Labs, Roughly Two-Thirds Miss Their Own
  Name", from_stage factcheck, run_after 2026-11-24 00:36 UTC) was left queued: first check in the DB whether it
  passed fact-check and reached "ready". Also check the doorway video (was at voice stage after a length rewrite).
- Owner turned Auto-publish ON (2026-11-23 23:46). Posting mode is still "draft" and the sandbox only allows
  private, so nothing goes public. Do not switch to public without asking.
- Owner still has to: (1) record the REAL sandbox demo (Snipping Tool: login → TikTok accounts → connect
  @callaletheia → Publish now → show the draft in the TikTok app); the captioned product walkthrough
  `assets/brand/tiktok/demo-walkthrough.mp4` is only a helper, not the review video. (2) Submit app review with
  Direct Post OFF and the 5 scopes (text in `assets/brand/tiktok/APP_FORM.md`). (3) Keep RunPod auto-pay OFF.
- Open small items: `/voices/*.mp3` 307 in middleware; "Forgot password" page if the owner lost the password;
  make the Caddy↔ots-web network link survive restarts; phase 2 Direct Post consent screen + audit; niches for
  channels 2–5.

### 0.000 Session 5, later (2026-11-23): TikTok developer app, phase 1 = drafts only
- Owner is filling the TikTok developer app form. Answers (description, scope text, demo-video script) are in
  `assets/brand/tiktok/APP_FORM.md`; app icon + 5 channel profile pictures drawn in code by
  `tools/brand/make_tiktok_art.cjs` → `assets/brand/tiktok/*.png` (re-run to regenerate).
- Decision: first app review asks only for Login Kit + Upload to drafts. OAuth scopes are now
  user.info.basic, user.info.profile, user.info.stats, video.list, video.upload (video.publish removed from
  `api/tiktok/connect`; private/public posting modes are disabled in the channel form until then).
- Later (phase 2): add video.publish with TikTok's per-post consent screen (creator nickname, privacy chosen by the
  user with no default, comment/duet/stitch toggles, commercial-content disclosure, Music Usage Confirmation), then
  apply for the Direct Post audit. Fully unattended public posting is not what TikTok's guidelines allow.
- Owner asked how posting works with GenLogin: told them the studio posts via the official API (no browser), and
  warned again against proxy/fake-US-location accounts. Dashboard login email = the owner's getgrowthnexus Gmail;
  password unknown to us (hashed); no "forgot password" page yet — build one if they can't find it saved.
- developers.tiktok.com is not reachable from the cloud sandbox (DNS blocked).
- RunPod hard monthly cap (owner: "$100 max, never more"): setting `runpod_monthly_cap_usd` (default 100, Settings
  page). Counts max(our per-image ledger, real RunPod balance drops seen by the 10-min health check; top-ups
  ignored) — `spend.runpod_slot()` refuses an image before calling RunPod, jobs park on "budget" and resume on the
  1st or when the cap is raised. Our per-image price (0.012) is an unverified fallback: RunPod output has no
  "cost" field — the balance meter is the source of truth. Owner told to keep RunPod auto-pay OFF.
- Fact-check (2026-11-24): videos failed on nitpicks (affiliation, paper title). Now FactCheck has `blocking`
  (false/harmful claims, TikTok misinformation rules) vs `minor` (never blocks). Last rewrite round removes
  unconfirmable details instead of re-wording. Gate = `fc.ok()` (no blocking).
- 2026-11-23: sandbox connect works (@callaletheia, 5 scopes); first video uploaded to TikTok drafts; Claude
  sign-in OK; RunPod key added. Next: owner records the real sandbox demo → submit app review.


### 0.00 Session 5 (2026-11-23): free voice + Supabase free-plan storage
Owner said "GO, tumhari salah theek hai" to this plan:
- **ElevenLabs is gone** (owner: "itne paise nahi"). Voice = **Kokoro-82M** (Apache-2.0), CPU on the VPS, $0.
  - `worker/studio/voice.py`: the `onnx-community/Kokoro-82M-v1.0-ONNX-timestamped` export (outputs `durations`), each
    word phonemized separately so word → token spans are exact; sentence by sentence (≤500 tokens); "a+b" blends voices.
    Measured: RTF ≈ 0.3 on 4 CPUs (90 s audio ≈ 27 s), Whisper heard 52–53/53 words, first-word timing within 30 ms of
    the energy onset (Whisper itself is ~190 ms early — don't "correct" for it).
  - Model files are fetched at image build by `worker/fetch_models.py` (HF revision `dd4401a9…` + GitHub release
    `model-files-v1.0`, both sha256-pinned) into `/opt/kokoro`. Deps `kokoro-onnx==0.6.1`, `onnxruntime==1.32.0`.
  - Voices (owner accepted my picks): overthought `am_michael+am_fenrir`, money-brain `am_onyx`, tiny-history
    `bm_george`, how-it-works `af_heart`, myth-busted `af_bella`. 12-voice catalog in `voice.CATALOG` and
    `apps/web/lib/presets.ts` VOICES (keep in sync); samples in `apps/web/public/voices/`; channel form has a picker +
    speed slider + player. Service row `elevenlabs` → `voice`.
- **Storage fits Supabase FREE plan** (org "realgrowthnexus" is on free: 1 GB storage, 5 GB egress). The old preview video
  used 36 MB (final.mp4 32.6 MB) → 10/day would have filled 1 GB in 3 days. Now: full `final.mp4` on the VPS
  (`/data/work/library/{id}.mp4`, `pipeline.library_path`), Supabase gets `preview.mp4` (540×960, CRF 28), publish reads
  the disk copy (`pipeline.final_video`, re-renders from saved scenes+voice if missing). Cleanup: re-render inputs 1 day
  after posting, preview after `video_retention_days` (now default **7**), disk copy 2 days after posting.
- **Migration `0004_free_voice.sql`** (services row, channel voices, drop ElevenLabs key, retention 7): **APPLIED and
  verified** on 2026-11-23 (owner approved). Code was also made safe without it (worker creates a missing service row;
  dashboard hides retired services).
- Owner chose the **terminal path** for the VPS (no Hostinger connector). Before install, `studio.getgrowthnexus.com`
  answered 502 from the other app's Caddy, so DNS works and a studio block may still be in their Caddyfile.
- **Cost (owner asked):** per video was $0.64 ($0.55 voice + $0.084 for 7 Flux images). Now ≈ **$0.084**. 10 videos/day ≈
  **$25/month RunPod** + Claude plan. Claude Pro likely carries ~3–6 videos/day; 10/day probably needs Max — measure
  with the Claude card after the first real videos. VPS already paid, Supabase free, TikTok free.
- New cloud env for this repo: **`overthought-studio` (env_01GR3mSLKRLQ9GMKkGifsahm)**, hosts: HF + CDN, Supabase, studio
  domain, Hostinger MCP, RunPod, GitHub releases. (The env id in §0.4 is from the owner's other account.)
- Supabase connector is connected (full access, owner-approved). **Hostinger connector was NOT visible** to the session
  yet; owner said they would connect it. Owner says DNS `studio` A record is done.
- Owner wants to use a (testing) Claude account: after install run `infra/connect-claude.sh` and open the link in
  the browser signed in to that account. A `claude_oauth_token` from the earlier sign-in is still saved in Supabase.
- **Account switching to dodge limits: REFUSED** (owner asked for auto-switching between Claude accounts when a limit
  hits). Told them it breaks Anthropic's terms and risks banning both accounts. Moving the studio to a different
  account once (testing → main) is fine: re-run `connect-claude.sh`. Owner wants the studio on another account of
  theirs; steps given (Incognito window signed into that account → run connect-claude.sh → paste code).
- **Capped API-key fallback (owner chose this, "keep 1")**: settings `api_fallback` (default off) +
  `api_fallback_daily_usd` (default $2). `llm.backend()` returns "api" while the plan's limit is active and
  `fallback_room()`; a LimitReached mid-call switches to the API if allowed (`_fallback_or_raise`), else parks as before.
  Cap = rolling 24 h anthropic spend (subscription runs record $0). Dashboard shows the limit the whole time; parked
  jobs re-queue when the fallback has room. Settings → "When the Claude limit is reached" switch + cap. Needs an API
  key (Settings → Advanced) and credit at console.anthropic.com — not added yet. Tests: `tests/test_api_fallback.py`.
- VPS install DONE 2026-11-23 19:36 UTC (backup .env restored → same MASTER_KEY; Claude sign-in "connected" but the
  plan was at its limit; voice ok; RunPod unconfigured). **Open: https 502** — local :3100 is 200, so the other app's
  Caddy (`juc-caddy-1`) can't reach `ots-web`; Step 3 command (network connect + checks) sent to the owner. After the
  cause is confirmed, make it durable on OUR side (re-connect in update.sh/caddy-attach), never edit the juc app.
- Separate product idea: owner wants a voice-over SaaS in a NEW repo/session; I gave a paste-ready prompt
  (suggested repo name `narrato`). Not part of this repo.
- **UI audit + polish (owner: "lax mat chhodo, production ready")** — root causes found and fixed:
  - `globals.css` had `* { border-color }` and `:focus-visible { border-radius }` OUTSIDE `@layer base`. In Tailwind v4
    unlayered rules beat utilities, so every `border-*` / `hover:border-*` utility silently did nothing (incl. the
    WCAG `border-line-input` on form controls) and focused pills/switches turned square. Moved into `@layer base`.
  - Tailwind v4 has no pointer cursor on buttons → a layered base rule gives every clickable the hand and disabled
    ones "not-allowed".
  - Primary hover was invisible (#ffd60a → #ffdf3d). Now darker in light (#ebc300), brighter in dark (#ffe566) + a
    soft accent ring. Switches, logo, report cards, filter pills, chips, text links, wizard steps got hover states;
    wizard future steps are `disabled`. Stale "Vercel" texts on /setup and Settings fixed; model labels shortened.
  - New regression tools: `tools/demo/hover-check.cjs` (every clickable on 14 pages: cursor + visible hover; result
    0 problems light and dark, 555 controls) and `tools/demo/flow-check.cjs` (settings + fallback persist, channel
    voice + sample, wizard). `up.sh` now pulls Supabase images from public.ecr.aws (Docker Hub rate-limits); the env
    allows `public.ecr.aws` + `d2glxqk2uabbnd.cloudfront.net` for that.
  - Verified: worker 89 tests, web tsc/lint/9 tests, ui-check all pass, flow-check 8/8.
- Ideas not done yet: cheaper images (Flux schnell / reuse a scene library) could cut the $25/month further.

### 0.0 (2026-11-23): owner is taking it down and will redeploy step by step WITH you
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
- Keys NOT added yet: RunPod. Nothing is being billed. (ElevenLabs was dropped in session 5.)

### 0.2 What the owner still has to do (walk them through it, one step at a time)
1. On the VPS (Hostinger Browser terminal): `sudo bash /opt/overthought-studio/src/infra/connect-claude.sh` — open
   the link, sign in to Claude, paste the code back. The script captures the token itself; card then says Connected.
   If anything fails: `sudo bash /opt/overthought-studio/src/infra/doctor.sh` and ask for the output (no secrets in it).
2. Supabase → Auth settings: turn OFF public sign-ups; set Site URL to `https://studio.getgrowthnexus.com`.
3. Dashboard → Settings: RunPod key. (No ElevenLabs any more — voice is free, §0.00.)
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

| slug | name | accent | Kokoro voice |
|---|---|---|---|
| overthought | Overthought: why your brain does that (37 seed ideas) | #FFD60A | `am_michael+am_fenrir` (deep warm male) |
| money-brain | Money Brain | #3DDC97 | `am_onyx` (low calm male) |
| tiny-history | Tiny History | #FF7A59 | `bm_george` (British male) |
| how-it-works | How It Works | #4CC9F0 | `af_heart` (warm female) |
| myth-busted | Myth Busted | #FF4D6D | `af_bella` (confident female) |

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
    below 8/10 → fact-check, which is permanent-fail if it fails twice → RunPod Flux scenes → Kokoro voice (free, on
    the VPS) with word timings and a length gate → render.
  - Render (`render/`): draw-on lines, accent pop, push-in, word captions, synthesized music bed, safe zones, loop
    crossfade. Output is H.264 1080×1920 at 30 fps, rendered in a subprocess.
  - Ops (`ops.py`):
    - publishing through the official Content Posting API, in draft, private or public mode;
    - stats sync, plus Studio CSV/XLSX import;
    - weekly review;
    - health and credit checks for Claude, the voice engine, RunPod, TikTok and storage, with auto-resume;
    - budget caps, a circuit breaker, nightly backups to the Supabase `backups` bucket, and cleanup.
  - Hardened by a 25-item code audit. 75 tests (`cd worker && python -m pytest -q -p no:cacheprovider`).
  - Needs **ffmpeg, about 3 CPU cores, about 4–6 GB RAM, and a long-running process**.
- **Supabase:** project `overthought-studio`, ref **`xkbgusqmdeocjwxaknjx`**, us-east-1, org "realgrowthnexus".
  - Migrations 0001–0003 applied; 0004 written in session 5 (see §0.00 for whether it is applied).
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
