# Production line, phase by phase, plus owner features: design

Date: 2026-11-24 (session 6). The owner approved the phases, the features and the assistant-with-actions choice in chat.

## 1. Intent

The owner handed the project over. They want it ready to use: videos made end to end, without babysitting. The
most important rule: **build in phases, and do not start a phase until the one before it works on the real VPS.**

So far, no Claude-written video has ever finished. All three attempts (2026-11-23/24) failed, and the failures came
from our own pipeline, not from outside services:
- **Claude time.** Each video used 8–10 minutes of Claude time. The script was scored up to 3 times, and a
  web-search fact-check ran up to 3 rounds (about 75 s each). A length rewrite then ran yet another fact-check.
- **The fact-check blocked on nitpicks.** It blocked videos over things like author lists, affiliations and
  "unverified" wording. It also made the scripts timid: lines such as "Theory suggests it. I couldn't find a test of
  it." kill retention.
- **Model and effort are ignored.** The Settings page says `claude-sonnet-5-5` / `medium`, but the subscription path
  (`llm._sub_model`, `claude_cli.run`) ignores both. It runs the plan's default model with no `--effort`, and the
  fact-check asks for `high`.
- **The length target is wrong for Kokoro.** The word target assumes 2.6 words/s. The measured rate is about 2.1
  words/s on `am_michael+am_fenrir` (about 230 words came out as 110 s). So the scripts come out long, the pipeline
  rewrites them, the rewrite has to pass the fact-check again, and the video fails permanently.
- **Images are drawn one at a time.** Five scenes took about 100 s.
- **The dashboard has gaps.** The `scheduleVideo` action has no UI. Title and cover can't be edited. Channel editing
  is hidden in a tab. The channels page is a plain list.

## 2. Goals
1. **Phase 1: create → research → script.** A good script in **≤ 2 minutes of Claude time**, without hard-coded
   rule loops. Claude should think like a sharp writer, not run through a checklist.
2. **Phase 2: check → visuals plan → images.** The check is light and only covers what the owner asked for:
   - the tone suits the channel (educational/motivating) and nothing is too graphic;
   - the length will be over 60 s;
   - nothing breaks TikTok's Community Guidelines (dangerous advice, harmful medical/financial misinformation, hate,
     graphic content, etc.).
   Names, places, institutions, years and citation formatting are **not** checked. Scenes are drawn in parallel.
3. **Phase 3: voice → render → ready.** The Kokoro voice lands inside the length window without rewrites in the
   normal case. The render runs, and the video reaches `ready` (or `approved`) with a preview and a thumbnail.
4. **Model rule.** Claude always runs **Sonnet (the `sonnet` alias, Sonnet 5.5 today) at medium effort**, on both the
   subscription and the API path. Nothing in the app can pick Opus or Fable.
5. **Features, after the 3 phases:**
   - Video page: edit the title, caption + hashtags, the **post time** (or clear it so the video takes the next free
     slot), and the **cover** (a frame of the video + the cover text). Plus a "Copy caption" button for draft mode.
   - Channels page: a **card grid** (3 columns on desktop, 2 on tablet, 1 on phone), each card with an **Edit**
     button.
   - **AI assistant**, bottom-left on every dashboard page. It runs on the same Claude sign-in and knows the live
     state of the app (balances, jobs, errors, schedule, videos, settings). It can **propose actions as buttons**,
     and an action only runs when the owner clicks "Yes".
6. **Extra audit.** A deeper review of the scheduler, publishing, the job loop, images, voice and render. Every
   real bug it finds is fixed in the phase it belongs to.

## 3. Non-goals
- Direct Post / public posting, and the TikTok Direct Post audit (separate, phase 2 of the TikTok app).
- Niches for channels 2–5.
- Switching between Claude accounts to dodge limits (refused earlier; still refused).
- Re-recording the Roman Urdu video guide.

## 4. Anti-goals (a failure even if it "works")
- A video fails because of a citation or affiliation nitpick.
- The assistant changes anything without the owner clicking.
- Any path quietly runs a model above Sonnet, or spends unexpectedly (the RunPod $100/month cap and the API-fallback
  cap stay in force).
- Pushing a phase to `main` (which is production: the VPS pulls `main` every 10 min) before its local tests pass.
- Scripts that hedge every line. Accuracy comes from good research, not from disclaimers.

## 5. Constraints
- **Where Claude can run.** Claude runs only through the owner's sign-in on the VPS. The token in Supabase is
  encrypted with a `MASTER_KEY` that exists only on the VPS. So the Claude steps cannot run in the cloud sandbox,
  and real verification happens on the VPS:
  1. push to `main` (the VPS rebuilds itself within about 10 min);
  2. insert a test job through the Supabase connector;
  3. watch `events` / `videos` / `spend`.
- **One limit for everything.** The Claude plan limit is shared by video production, the assistant and the owner's
  own chats. Limit hits stay calm pauses.
- **TikTok draft (inbox) upload sends only the video file.** Caption, hashtags and cover are set by the owner in
  the TikTok app. Dashboard edits reach TikTok only through Direct Post (`post_info.title`,
  `video_cover_timestamp_ms`), which is not live yet. Through the API a cover can only be a **frame timestamp**,
  never an uploaded image.
- **Supabase is on the free plan** (1 GB storage). The worker has 4 CPUs.
- **Keep the existing architecture.** The dashboard and the worker never talk directly; they share DB tables. Every
  mutation is zod-validated and admin-checked. No secrets go to the client.

## 6. Approaches considered

**Phase 1 shape**
- A. **One Claude call** that researches with web tools and returns the script directly. Fastest (about 60–90 s, one
  CLI start). But the research is not stored separately, so "rewrite the script" has to research again, and the
  dashboard can't show two stages.
- B. **Two lean calls** (chosen). Research: one call, web tools, compact notes, told to keep to about 3–4 searches.
  Script: one call, no scorecard loop; the writer self-reviews inside the same call and returns a self-score for the
  dashboard. About 1.5–2 min. Research stays reusable for rewrites, and the stages stay visible and resumable.
- C. Keep today's loops and only tune the prompts. Rejected: the loops themselves are the time sink.

**The check (phase 2)**
- A. **One no-tools Claude call** at Sonnet medium (chosen). About 10–20 s. It returns
  `{ok, problems[{line, issue, fix}]}`, covering tone, graphic content and TikTok policy. Length is checked in code.
  If there are problems, the pipeline does one targeted rewrite of only the flagged lines, then one re-check.
  Still blocked → `failed` with a plain reason.
- B. Keep the web-search fact-check but loosen it. Rejected: still slow, and it is the thing the owner asked to
  remove.

**Length fit (phase 3)**
- A. **Calibrate and use speed** (chosen). The script target comes from a measured words/second per voice. Each
  real synthesis updates a running average stored on the channel row (`voice.wps`). If the voice still lands
  outside the window, re-synthesize at a speed within 0.92–1.10 (free, about 25 s). Only if that fails: one
  narration-only rewrite that keeps the scenes, then the light check (never the old fact-check).
- B. Keep the rewrite loop. Rejected: it is the cause of the last failure.

**Assistant transport**
- A. **Through the DB** (chosen). The web inserts the owner's message into `assistant_messages` and enqueues an
  `assistant_reply` job. A **dedicated `chat` lane** in the worker answers it, so chat never waits behind
  publish/sync. The reply arrives through Supabase realtime (the `LiveRefresh` pattern) or polling. This keeps the
  "dashboard and worker never talk directly" contract, and the token stays in the worker.
- B. Install the Claude CLI in the web container and decrypt the token there. Rejected: it doubles the secret
  surface and the image size.
- C. An HTTP endpoint on the worker. Rejected: new network exposure, and it breaks the architecture contract.

## 7. Design

### 7.0 Shared, done first (part of phase 1)
- `llm.py`:
  - Every subscription run passes `--model sonnet --effort medium`.
  - The API path uses `claude-sonnet-5-5` with effort medium.
  - `settings.model` / `subscription_model` values above Sonnet are coerced to Sonnet. The Settings UI offers only
    "Sonnet (recommended)" and "Haiku (cheapest)".
- `claude_cli.run` gains an `effort` argument. The CLI pin is 2.1.329 (it supports `--effort`; verify on the VPS
  image).
- Test hook: a `produce_video` payload may carry `stop_after: "script" | "visuals"`. The pipeline then stops after
  that stage, leaves the video in that stage's status with `stage_detail="Test stopped after <stage>"`, logs an
  event, and does **not** count as a failure for the planner's circuit breaker.
- Reset the planner's "3 failed in 24 h" stop once the phase 1 fixes are deployed. (How it resets comes from the
  audit.)

### 7.1 Phase 1: create → research → script
- **Create.** The planner picks an idea and creates the video. Keep what exists, and fix whatever the audit finds
  there.
- **Research** (`content.research_topic`):
  - One call. The prompt asks for compact notes: the core study (who, where, when, the real numbers), 2 extra
    facts or examples, the common myth to avoid, a practical takeaway, and how US viewers talk about it.
  - "Use about 3–4 searches; stop when you have enough." The prompt says to prefer saying less over guessing.
  - Target ≤ 45 s.
- **Script** (`content.write_script`):
  - One call with the CRAFT guidance kept as craft, not as gates.
  - Word target = `target_seconds × voice.wps` (default 2.1 until measured), a range of about ±8 %.
  - The writer is told to use only facts from the research notes and never invent names or numbers. It may say
    "a study at X" without heavy hedging.
  - It returns a short self-score, stored as the scorecard so the dashboard still shows it.
  - The external scorecard loop is removed. `score_script` stays available but is not called in the pipeline.
- **Code checks, no LLM:**
  - schema validity: 8–12 beats, the first beat is the hook, the last is the loop, 4–7 scenes, every beat's
    `scene_id` is valid;
  - word count inside the range.
  - On a miss: one repair call with the exact problem. If it misses again: retry later as a normal error.
- **Done when:** on the VPS, 3 test runs with `stop_after: "script"` succeed, each ≤ 2 min of Claude time
  (research + script), with valid scripts inside the word range. The scripts are read for quality and one is sent
  to the owner.

### 7.2 Phase 2: check → visuals plan → images
- **Check** (`content.policy_check`, replaces `fact_check` in the pipeline):
  - One call, no tools, as in approach A.
  - Length = word count / `voice.wps` ≥ 61 s (code).
  - The old `fact_check` is deleted along with its tests.
  - The `factcheck` column keeps storing the result (no rename, no migration). The status stays `fact_checking`,
    and the UI label says "Checking".
- **Visuals plan:** the script's `scenes` are the plan. Code validates them: 4–7 scenes, no text/letters requested
  in the image, the channel style prompt added. The dashboard shows them.
- **Images:**
  - All missing scenes are generated in parallel (a thread pool of up to 4), keeping each image's
    `spend.runpod_slot()` cap check and its existing retry/poll.
  - Each finished image is uploaded right away, so a resume never pays twice.
  - Target: 5 scenes in ≤ 45 s.
- **Done when:** 2 test runs with `stop_after: "visuals"` pass on the VPS, the images look right (sent to the
  owner), and the RunPod meter matches.

### 7.3 Phase 3: voice → render → ready
- **Voice.** Kokoro as approach A: calibrated wps, then a speed nudge, then (rarely) a narration-only rewrite plus
  the light check. Each run updates `channels.voice.wps` (a running average, last 5).
- **Render.** The existing compose path. Measure the render time on the VPS, and fix whatever the audit finds
  (hangs, timeouts, bad output). Then preview + thumbnail + library copy as today.
- **Ready.** `ready` (approval on) or `approved`. Auto-publish keeps posting mode `draft` only.
- **Done when:** 3 full videos finish end to end on the VPS (at least 2 different topics), and the owner gets them
  to watch. Report the Claude time per video and the real cost.

### 7.4 Features
**Video page** (`/videos/[id]`):
- An editable **title** (dashboard name; max 150).
- **Caption + hashtags** (exists).
- **Post time:** a date-time picker shown in the owner's local time and saved as UTC ISO, using the existing
  `scheduleVideo`. Allowed when the status is `ready`, `approved` or `scheduled`; it must be in the future.
  "Clear" means the next free slot. The scheduler must respect a manual time and never move it. The audit confirms
  how; fix if needed.
- **Cover:**
  - a slider over the preview picks a frame → `cover_ms`;
  - an editable cover text (`thumbnail_text`);
  - saving enqueues a light `make_thumb` job that rebuilds `thumb.jpg` from the library copy at that frame, with
    that text.
  - `cover_ms` is passed to TikTok on Direct Post.
  - Needs migration `0005`: `videos.cover_ms int`.
- In draft mode a note says "TikTok drafts don't take a caption or cover from us; tap Copy caption and paste it in
  the TikTok app", next to a **Copy caption** button.
- The videos list shows the post time.

**Channels page:**
- Cards in a responsive grid: `grid-cols-1 md:grid-cols-2 xl:grid-cols-3`.
- Each card shows the colour bar, name, niche, linked account, delivery mode, posts/day, last post, 7-day views,
  the status badge, the on/off toggle and an **Edit** button (`/channels/[slug]/settings`, the existing
  `updateChannel` form).

**AI assistant:**
- **UI:**
  - a round button fixed bottom-left (desktop: above the sidebar's foot; phone: above the bottom nav);
  - it opens a panel (a sheet on phones) with the message list, a typing indicator, an input and suggested
    questions;
  - WCAG AA, keyboard and Esc support, reduced motion.
  - If Claude is not signed in, the panel says so and links to Settings.
- **Data:** migration `0005` adds `assistant_messages`:
  - columns: `id, role ('user'|'assistant'), content, actions jsonb, status, created_at`;
  - RLS: admin only (same pattern as the other tables);
  - keep the last 200 messages.
- **Worker:**
  - The `assistant_reply` job runs on a new `chat` lane thread.
  - It builds a JSON **snapshot**:
    - service statuses + balances (RunPod balance + the month's meter vs the cap, Claude limit / resume time);
    - settings;
    - channels with status/blocked reason;
    - running/parked/failed jobs with errors;
    - the next 10 scheduled videos;
    - the last 20 videos with status/error;
    - the last 30 events;
    - spend today/month.
  - It runs `claude -p` (Sonnet medium, no tools) with that snapshot, the last 12 messages and a system prompt that
    explains the studio (from ARCHITECTURE/BRAIN-level facts, no secrets).
  - It answers in the owner's language (Roman Urdu or simple English, never Devanagari).
  - Output schema: `{reply, actions[]}`.
- **Actions:**
  - a whitelist, each mapped to an existing admin-checked server action:
    - pause/resume a channel;
    - global pause/resume;
    - make a video now for a channel;
    - retry/cancel a job;
    - approve/reject a video;
    - publish now;
    - set or clear a post time.
  - The worker validates each proposed action (the ids exist, the type is whitelisted) before saving it.
  - The UI shows each one as a button with a plain label. Clicking calls the server action. The result appears in
    the chat.
  - **Nothing runs without a click.**
- **Limits:**
  - it shares the plan's limit;
  - on `LimitReached` the reply says calmly when Claude is back;
  - one reply at a time (the input is disabled while waiting).

### 7.4b Extra audit findings (2026-11-24, code review of the worker): each is fixed in the phase listed
Checked: every `videos.status` the worker writes is allowed by the 0001 check constraint.

**Phase 1** (planner / create / job loop):
- **A1. `from_stage` is applied again on every retry and every resume.**
  - Where: `main.handle` → `pipeline.produce(…, from_stage)`.
  - Effect: after a limit park, the script is wiped and rewritten again.
  - Fix: clear `from_stage` from the job payload after the first pass.
- **A2. A killed worker leaves a video stuck in a production status forever.**
  - Effect: it blocks the channel's "≤ 2 in production" rule. The startup reset also requeues running jobs and
    ignores `max_attempts`.
  - Fix: a sweeper fails videos whose produce job is failed or missing. The startup reset honours `max_attempts`.
- **A3. Circuit breaker.**
  - Effect: any write to the channel row (park/resume, weekly review, settings save) forgives earlier failures. When
    the breaker does trip, the channel stays "active", so the owner has to Pause and then Start. The badge goes
    stale after 24 h.
  - Fix: an explicit `failures_forgiven_at`, written only by Start/Resume. Clear `blocked_reason` automatically once
    the count drops below 3.
- **A4. The planner spams failed jobs when the idea bank is empty.**
  - Effect: one failed job and one error event per minute.
  - Fix: `plan_channel` returns "skipped: no ideas" (and kicks off research) instead of raising.
- **A5. Failed or rejected videos burn their idea.**
  - Effect: the idea stays `queued` forever.
  - Fix: set it back to `new` on failure (with a fail count; retire it after 2).

**Phase 2** (visuals):
- **A6. A redo restores STALE files from storage.**
  - Effect: old scenes are reused for a new script, and old voice for a new script.
  - Fix: when redoing from a stage, delete that stage's storage objects, null `audio_path`, and never `_restore`
    for a stage being redone.
- **A7. RunPod: network errors while polling or downloading are not mapped to `ServiceDown`.**
  - Effect: the video fails instead of being parked.
  - The image GET has no status check.
  - A `runsync` read timeout re-pays on retry. Fix: keep the job id and poll it instead of re-submitting.

**Phase 3** (voice / render / ready → scheduled → publish, since auto-publish is ON):
- A6 also covers the voice files.
- **A8. Render.** `multiprocessing.Pool.map` hangs until the 60-min timeout if a child process is OOM-killed.
  - Fix: `ProcessPoolExecutor` plus a ~15-min timeout.
  - Also: `probe()` must assert that an audio stream exists.
- **A9. The TikTok rate-limit retry is silently dropped** (the same dedupe key is still held by the running job).
  - Effect: the video is re-published every minute.
  - Fix: set `scheduled_for = now + 3 h` instead of enqueueing.
- **A10. A permanently failing publish loops forever** (each scheduler tick makes a new job).
  - Fix: count publish failures. After 3, the video becomes `failed` with a plain error and the red bar shows it.

**Features** (post-time edit):
- **A11. Scheduler and manual times.**
  - A manual time must be kept: a flag `schedule_locked`, or the rule "never move a `scheduled_for` the owner set".
  - Step 1 must not overwrite a time set on an `approved` video.
  - Manual times reserve their slot.
  - The " ET" label must follow the channel's timezone. Use `ch.get('timezone') or 'America/New_York'`.

### 7.5 Verification and delivery
- Each phase:
  1. worker pytest (update/replace the tests for changed behaviour, TDD for new code);
  2. web `tsc`, lint, node tests;
  3. a local UI check (`tools/demo`) for UI work;
  4. push to `main`;
  5. a VPS test run as above;
  6. a short Roman Urdu update to the owner;
  7. BRAIN updated.
- An opus final review after phase 3 and after the features, then one fix pass.

## 7.6 Decisions after the builder check (Claude's calls; the owner handed over the how)
1. **Phase gate = Claude's own verification on the VPS** (the "done when" lines). Updates to the owner are
   informational; work does not stop to wait for a reply. The owner can still stop or redirect at any time.
2. **Cover = a frame only.** That is all TikTok supports.
   - A slider picks `cover_ms`, and a light `make_thumb` job extracts that frame from the library copy as `thumb.jpg`.
   - No cover text is burned in. `thumbnail_text` stays unused, so the "cover text" field is dropped from §7.4.
   - In draft mode the owner picks the cover in the TikTok app, and the UI says so.
3. **Setting a post time on a `ready` video also approves it.** The button reads "Approve and schedule".
   - Migration 0005 adds `videos.schedule_locked boolean default false`. The scheduler never moves or overwrites a
     locked time.
   - Overdue locked videos publish as soon as possible, one per channel per tick.
   - "Clear" unlocks the video, and it takes the next free slot.
4. **On-screen study label stays, made safe.**
   - The label is drawn only from sources the research step actually found (with a URL in the research sources),
     shortened to `→ Researcher · Year`; the institution is dropped because it was the most error-prone field.
   - The writer may cite only those sources.
   - `CRAFT` drops "SAY SO on screen" / heavy hedging. A failed replication can still be the twist when it makes the
     story better.
5. **Always Sonnet, medium.**
   - The Settings page shows "Claude: Sonnet · medium (fixed)", read-only.
   - No Haiku and no effort picker. Stored values are ignored or coerced.
6. **"≤ 2 min of Claude time" is a target, not a pass/fail line.** It is reported per run. Phase 1 passes on valid,
   good scripts. If runs are over 2.5 min, tune the searches before moving on.
7. **The assistant never uses the paid API fallback.** On a limit hit it replies calmly with the reset time
   (`structured(..., allow_fallback=False)`).
8. **Length target = the midpoint of the channel's `min_seconds..max_seconds`.** The word target is
   `midpoint × wps` (±8 %), with a hard floor of `max(61, min_seconds)` seconds. The new check's length rule uses
   the same floor.

## 8. Left to the builder
- Exact prompt wording; the thread-pool size (≤ 4); the snapshot field names; the panel's visual details (follow
  the existing design tokens).
- Where `stop_after` stops in the UI (it is a test-only payload, never shown as a button).
- Whether to drop `score_script` code entirely or keep it unused.
