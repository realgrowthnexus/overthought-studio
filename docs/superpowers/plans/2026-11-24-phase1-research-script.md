# Phase 1: create → research → script — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the first half of the line (planner creates a video → research → script) fast (~2 min of Claude time),
always on Sonnet/medium, testable on the VPS without spending on images, and fix the planner/job-loop bugs A1–A5.

**Architecture:** Python worker changes in `llm.py`/`claude_cli.py` (model + effort), `content.py` (lean research and
script, code-side script checks, source filtering), `pipeline.py` (no scorecard loop, `stop_after`, `on_cleared`),
`scheduler.py`/`ops.py`/`main.py` (breaker, no-ideas, idea release, sweeper, startup reset). Small dashboard changes
(fixed model line, Resume button, `failures_forgiven_at`). One additive migration `0005_phase1.sql`.

**Tech Stack:** Python 3.13 + pytest (fake world in `worker/tests/fakes.py`), Claude Code CLI headless, Next.js 15 /
Supabase.

**Spec:** `docs/superpowers/specs/2026-11-24-production-line-design.md` (§7.0, §7.1, §7.4b A1–A5, §7.6 #4 #5 #6 #8)

## Global Constraints
- Claude always runs **`--model sonnet --effort medium`** (subscription) / **`claude-sonnet-5-5` + effort `medium`**
  (API). No path picks Opus or Fable. No Haiku, no effort picker in Settings.
- Length: target = midpoint of `min_seconds..max_seconds`; floor = `max(61, min_seconds)` seconds; default
  `voice.wps` = **2.1** words/s.
- On-screen source label = `→ Researcher · Year`, only for sources whose URL the research step returned.
- Never write secrets to the repo. Every web mutation stays zod-validated and admin-checked (`guard`).
- `main` is production (VPS pulls it every 10 min). Push to `main` only in Task 7 after all tests pass.
- Worker tests: `cd worker && python -m pytest -q -p no:cacheprovider`. Web: `cd apps/web && npx tsc --noEmit && npx next lint`.

## Review Focus
1. Old scripts saved before this change (no `self_review` field) must still load on resume → `Script.self_review` is
   optional; test in Task 3.
2. A research step that returns sources whose URLs the writer re-formats (trailing slash, `http` vs `https`) — URL
   matching must normalise these, not drop real sources; test in Task 3.
3. A redo ("Make again" from `script`) that hits the Claude limit and resumes must not rewrite the script a second
   time; test in Task 4.
4. A channel tripped by the breaker whose failures age out must un-trip by itself, and pressing Resume must forgive;
   test in Task 5.
5. A worker crash loop must not retry a job forever, and a video whose job is gone must not block the channel; test
   in Task 6.

---

### Task 1: Sonnet + medium everywhere

**Files:**
- Modify: `worker/studio/claude_cli.py` (`run`), `worker/studio/llm.py` (`_sub_model`, `_sub_run`, `model_cfg`,
  `LIGHT_PURPOSES`), `worker/studio/settings.py` (`DEFAULTS`)
- Modify: `apps/web/components/settings-forms.tsx:114-126`, `apps/web/lib/actions.ts:158-159` (settings schema)
- Test: `worker/tests/test_llm_subscription.py`, `worker/tests/test_llm_contract.py` (if it asserts the model)

**Interfaces:**
- Produces: `claude_cli.run(prompt, *, system, schema, tools, model, effort: str | None = None, timeout=TIMEOUT,
  with_token=None)` → adds `--effort <effort>` when given. `llm.MODEL_ALIAS = "sonnet"`, `llm.API_MODEL =
  "claude-sonnet-5-5"`, `llm.EFFORT = "medium"`. `llm.model_cfg()` always returns `(API_MODEL, EFFORT)`.

- [ ] **Step 1: Verify the pinned CLI accepts `--effort`.** Run
  `cd "$SCRATCH" && npm i --prefix cli329 @anthropic-ai/claude-code@2.1.329 >/dev/null && cli329/node_modules/.bin/claude --help | grep -- --effort`.
  Expected: a `--effort <level>` line. If missing, bump the pin in `worker/Dockerfile:19` to `2.1.331` (verified
  locally) and note it in BRAIN.
- [ ] **Step 2: Write failing tests** in `test_llm_subscription.py`:
  - replace `test_heavy_work_uses_the_plans_default_model` with `test_every_run_is_sonnet_medium`: for
    `llm.research(...)` and `llm.structured(content.Scorecard, ...)` with `sets["model"]="claude-opus-5-5"`,
    `sets["effort"]="max"`, `sets["subscription_model"]="opus"`, the argv has `--model sonnet` and `--effort medium`.
  - `test_api_model_is_fixed`: `llm.model_cfg()` returns `("claude-sonnet-5-5", "medium")` with the same settings.
  - In `test_structured_goes_through_cli_and_costs_nothing` keep the `--model sonnet` assert.
- [ ] **Step 3: Run** `python -m pytest -q -p no:cacheprovider tests/test_llm_subscription.py` → FAIL.
- [ ] **Step 4: Implement.** `_sub_model` returns `MODEL_ALIAS`; `_sub_run` passes `effort=EFFORT`; the API calls in
  `structured`/`research` use `EFFORT` (ignore the `effort=` argument callers pass; keep the parameter for
  compatibility); `settings.DEFAULTS` `model="claude-sonnet-5-5"`, `effort="medium"`; drop `LIGHT_PURPOSES`.
- [ ] **Step 5: Web.** Replace the two Selects with a read-only `Field` "Claude" showing "Sonnet · medium effort
  (fixed)" and hint "Same model for research, scripts, checks and the assistant." Make `model`/`effort` optional in
  the zod schema; `updateSettings` always writes `model: "claude-sonnet-5-5", effort: "medium"`. Remove them from
  the form payload.
- [ ] **Step 6: Run** worker tests for llm files → PASS; `cd apps/web && npx tsc --noEmit && npx next lint` → clean.
- [ ] **Step 7: Commit** "Claude fixed to Sonnet, medium effort on every path".

### Task 2: Migration 0005 (phase 1 columns)

**Files:**
- Create: `supabase/migrations/0005_phase1.sql`

**Interfaces:**
- Produces: `channels.failures_forgiven_at timestamptz null`, `ideas.fail_count int not null default 0`.

- [ ] **Step 1:** Write the migration (`alter table … add column if not exists …`; comment each column's purpose).
- [ ] **Step 2:** Commit "Migration 0005: breaker forgiveness time, idea fail count". (Applied to Supabase in Task 7.)

### Task 3: Lean research and script, code-side checks

**Files:**
- Modify: `worker/studio/content.py` (`CRAFT`, `Source`, `Script`, `research_topic`, `write_script`, new helpers)
- Modify: `worker/studio/pipeline.py:54-55` (`_source_label`), `:91-113` (script stage)
- Modify: `worker/tests/fakes.py` (`research` returns a citation; `clean_script` inside the word range)
- Test: `worker/tests/test_script_stage.py` (new), `worker/tests/test_pipeline_e2e.py`

**Interfaces:**
- Produces:
  - `content.word_range(ch: dict) -> tuple[int, int]` — `wps = float((ch.get("voice") or {}).get("wps") or 2.1)`,
    `mid = (min_s + max_s) / 2` (defaults 65/95), `lo = max(round(mid*wps*0.92), ceil(max(61, min_s)*wps))`,
    `hi = max(round(mid*wps*1.08), round(lo*1.15))` (so a high floor never makes `lo > hi`).
  - `content.script_problems(script: Script, ch: dict) -> list[str]` — plain-English problems: beats not 8–12;
    first beat kind ≠ `hook`; last ≠ `loop`; scenes not 4–7 or ids not `0..n-1`; a beat `scene_id` not a scene id;
    word count outside `word_range`. Empty list = fine.
  - `content.keep_found_sources(script: Script, citations: list[dict]) -> Script` — keeps sources whose normalised
    URL (lowercase scheme+host, strip `www.`, trailing `/`, `http`→`https`, drop query/fragment except DOI paths) is
    in the citation URLs; remaps `beat.source_index` (dropped → `None`).
  - `Script.self_review: Optional[Scorecard] = None` (writer's own scoring, stored as `videos.scorecard`).
  - `Source.institution: str = ""` (optional now).
  - `pipeline._source_label(s) -> "→ {researcher} · {year}"`.
- Consumes: `llm.research` / `llm.structured` (unchanged signatures).

- [ ] **Step 1: Write failing tests** in `test_script_stage.py`:
  - `test_word_range_uses_midpoint_and_wps`: ch `min_seconds=65, max_seconds=95`, no wps → `(155, 181)`; with
    `voice={"wps": 2.5}` → `(184, 216)`; `min_seconds=50, max_seconds=60` → `(129, 148)` (floor 61 s × 2.1 = 128.1 → ceil 129;
    hi lifted to round(129 × 1.15)).
  - `test_script_problems_flags_structure_and_length`: `fakes.clean_script()` on the seed channel → `[]`; a script
    with 6 beats, last beat kind `payoff`, a beat with `scene_id=9` → 3 problems mentioning "beats", "loop", "scene".
  - `test_keep_found_sources_normalises_urls`: citation `https://www.doi.org/10.1/x/` keeps source url
    `http://doi.org/10.1/x`; a source with an unknown URL is dropped and beats pointing at it get `source_index=None`.
  - `test_old_script_without_self_review_still_loads`: `Script.model_validate` of `clean_script().model_dump()` minus
    `self_review` works.
  - `test_source_label_is_researcher_and_year`: `pipeline._source_label({"researcher": "Radvansky", "institution": "X",
    "year": 2011})` → `"→ Radvansky · 2011"`.
- [ ] **Step 2: Run** `python -m pytest -q -p no:cacheprovider tests/test_script_stage.py` → FAIL.
- [ ] **Step 3: Implement prompts.**
  - `research_topic`: compact notes prompt — core study (who, where, when, real numbers), 2 extra facts or examples,
    the myth to avoid, one practical takeaway, how US viewers 16–34 talk about it. Add: "Use about 3–4 searches and
    stop when you have enough. If you are unsure of a detail, leave it out." Keep `max_searches=4` on the API path.
  - `CRAFT`: keep the retention craft; replace the "Accuracy is the brand" block with: use only facts in the research
    notes, never invent names/numbers/years; cite sources only from the numbered research source list, copying the
    URL exactly; a contested or failed replication may be the twist when it makes the story better; **do not hedge
    line by line** ("might", "reportedly", "I couldn't find" kill retention); no medical/legal/financial advice beyond
    general education; "spot the trick" framed as self-protection.
  - `write_script(ch, idea, research, *, hook_style, feedback=None, previous=None, video_id=None)`: words from
    `word_range(ch)`; the research block lists notes and then `SOURCES` numbered `[i] title — url`; asks the writer to
    self-review hook (stop a scrolling 20-year-old in second 1), curiosity gap, emotional moment, loop, then fill
    `self_review` honestly and fix weak spots before answering.
- [ ] **Step 4: Implement the script stage** (`pipeline.py`): one `write_script`; `keep_found_sources(script,
  video["research"]["citations"])`; `problems = script_problems(script, ch)`; if problems → one repair
  `write_script(..., feedback=problems, previous=script.model_dump())` + `keep_found_sources` again; after the repair
  raise `RuntimeError("Script still has problems: …")` only if a structural problem remains or the word count is
  outside `[0.85·lo, 1.15·hi]`. Save `scorecard=script.self_review.model_dump() if script.self_review else None`.
  Remove the `score_script` loop (leave `score_script` defined, unused).
- [ ] **Step 5: Update fakes:** `FakeWorld.research` returns citations
  `[{"url": "https://doi.org/10.1080/17470218.2011.571267", "title": "Radvansky 2011", "cited_text": ""}]`;
  `clean_script` beats sized so the narration lands inside `word_range(seed channel)` (≈ 17 words per beat) and still
  > 65 s at the fake's 2.6 w/s (fake voice) — adjust the fake voice `WORDS_PER_SECOND` to `2.1` if needed so the
  length gate still passes.
- [ ] **Step 6: Run the whole worker suite** → all PASS (fix e2e expectations that counted scorecard calls).
- [ ] **Step 7: Commit** "Lean research + one-pass script with self-review, code-side checks, found-sources only".

### Task 4: `stop_after` test hook and A1 (`from_stage` applied once)

**Files:**
- Modify: `worker/studio/pipeline.py` (`produce`), `worker/studio/main.py` (`handle`), `worker/studio/ops.py`
  (`plan_channel` passes `stop_after` through)
- Test: `worker/tests/test_pipeline_e2e.py`

**Interfaces:**
- Produces: `pipeline.produce(video_id, from_stage=None, *, stop_after: str | None = None,
  on_cleared: Callable[[], None] | None = None) -> dict`. `stop_after` ∈ `STAGES`. After that stage the video is
  set to `status="rejected", approval="rejected", rejection_note="Test run: stopped after <stage>",
  stage_detail="Test stopped after <stage>", progress=PROGRESS[stage]`, an event `"Test run stopped after <stage>"`
  with `data={"seconds": {stage: secs, ...}}` is written, and the function returns. `on_cleared` is called once,
  right after the `from_stage` clearing.
- `ops.plan_channel(channel_id, force=False, stop_after=None)`; `main.handle` reads `payload.stop_after` for
  `plan_channel` and `produce_video`, and passes `on_cleared` that rewrites the job's payload without `from_stage`.
- Every stage records its wall-clock seconds; the "Ready" event (and the test-stop event) carry
  `data={"seconds": {...}}`.

- [ ] **Step 1: Write failing tests:**
  - `test_stop_after_script_makes_two_claude_calls_and_spends_nothing_else`: `produce(vid, stop_after="script")` →
    status `rejected`, `world.calls == {"claude": 2}` on the clean path, an event "Test run stopped after script" with
    `data["seconds"]` having `research` and `script`.
  - `test_plan_channel_passes_stop_after`: seed one idea; `ops.plan_channel(ch_id, force=True, stop_after="script")`
    → the inserted `produce_video` job payload has `stop_after == "script"`.
  - `test_from_stage_is_applied_once`: a `produce_video` job with `payload={"video_id": v, "from_stage": "script"}`
    on a video that already has research+script; make the fake `generate` raise `RuntimeError` once; `main.run_one`
    → job requeued and its payload has no `from_stage`; run again → `world.calls["claude"]` grew by exactly the one
    script call of the first run (no second rewrite).
- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement** per Interfaces.
- [ ] **Step 4: Run the worker suite** → PASS.
- [ ] **Step 5: Commit** "Test hook stop_after, stage timings, redo stage applied only once".

### Task 5: Breaker forgiveness (A3) and no-ideas planning (A4)

**Files:**
- Modify: `worker/studio/scheduler.py` (`_channel` step 3 and 4)
- Modify: `apps/web/lib/actions.ts` (`setChannelStatus`), `apps/web/components/channel-toggle.tsx`, its callers
  (`app/(app)/channels/page.tsx`, `app/(app)/channels/[slug]/layout.tsx`)
- Test: `worker/tests/test_scheduler_breaker.py` (new)

**Interfaces:**
- Consumes: `channels.failures_forgiven_at` (Task 2).
- Produces: breaker cutoff = `max(t - 24h, failures_forgiven_at)`; `channels.updated_at` no longer used. When
  `blocked_reason` starts with `"Stopped making new videos"` and the count is now < 3 → `blocked_reason=None` + event
  `"Planning resumed: recent failures are older than 24h"`. Step 4 checks `ideas` (`status="new"`, limit 1) before
  enqueueing `plan_channel`; with none it enqueues `research_ideas` with the same once-key as `plan_channel` uses and
  does not enqueue `plan_channel`.
- Web: `setChannelStatus(id, "active")` also writes `failures_forgiven_at: new Date().toISOString()`.
  `ChannelToggle({ id, status, blockedReason? })` shows a small "Resume" button (calls `setChannelStatus(id,
  "active")`) when `blockedReason?.startsWith("Stopped making new videos")`.

- [ ] **Step 1: Write failing tests** (fake world + a fixed `t`):
  - `test_channel_row_updates_do_not_forgive_failures`: 3 failed videos 2 h ago, channel `updated_at` = 1 h ago,
    `failures_forgiven_at=None` → after `_channel`, `blocked_reason` starts "Stopped making new videos".
  - `test_resume_forgives`: same, `failures_forgiven_at` = 30 min ago → not blocked, `plan_channel` enqueued.
  - `test_breaker_untrips_when_failures_age_out`: channel already blocked with that message, failures 25 h ago →
    `blocked_reason is None` and the event exists.
  - `test_no_ideas_means_no_plan_job`: no `new` ideas → no `plan_channel` job; a `research_ideas` job exists.
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement.** **Step 4: Run** worker suite → PASS; web tsc + lint clean.
- [ ] **Step 5: Commit** "Breaker forgiven only by Resume, un-trips by itself; no planning without ideas".

### Task 6: Idea release (A5), stuck-video sweeper and startup reset (A2)

**Files:**
- Modify: `worker/studio/pipeline.py` (the `stop_after` exit calls `ops.release_idea(vid, failed=False)`),
  `worker/studio/ops.py` (new `release_idea`, new `sweep_stuck_videos`), `worker/studio/main.py`
  (failure branches of `run_one`, new `reset_stale_jobs()` used by `main()`), `worker/studio/scheduler.py` (`tick`
  calls `ops.sweep_stuck_videos()` every tick)
- Test: `worker/tests/test_job_recovery.py` (new)

**Interfaces:**
- Produces:
  - `ops.release_idea(video_id: str, failed: bool) -> None` — reads `idea_id`; failed → `fail_count += 1`, status
    `retired` if `fail_count >= 2` else `new`; not failed (test stop) → status `new`, count unchanged. No-op without
    an idea.
  - `ops.sweep_stuck_videos(now: datetime) -> int` — videos in `IN_PRODUCTION` (except `blocked`) with
    `updated_at` older than 15 min and **no** `produce_video` job for that `video_id` in `queued|running|waiting` →
    `status="failed", error="Production stopped unexpectedly (the worker restarted mid-job). Press Make again."`,
    `release_idea(..., failed=True)`, one event each. Returns the count.
  - `main.reset_stale_jobs() -> None` — this worker's `running` jobs: `attempts >= max_attempts` → `failed` (+ video
    `failed` and `release_idea` for production jobs); else back to `queued`.
- Consumes: `ideas.fail_count` (Task 2); the `stop_after` exit from Task 4.

- [ ] **Step 1: Write failing tests:**
  - `test_failed_video_returns_its_idea_then_retires_it`: a produce job raising `PermanentError` twice for two videos
    of the same idea → after the 1st the idea is `new` with `fail_count 1`; after the 2nd it is `retired`.
  - `test_sweeper_fails_orphaned_videos_only`: video `rendering`, updated 20 min ago, no job → failed; same with a
    `running` job → untouched; updated 5 min ago, no job → untouched.
  - `test_startup_reset_honours_max_attempts`: running job with `attempts=3, max_attempts=3` → `failed` + video
    `failed`; `attempts=1` → `queued`.
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement.** **Step 4: Run** worker suite → PASS.
- [ ] **Step 5: Commit** "Failed videos give their idea back; sweep orphaned videos; startup reset respects max attempts".

### Task 7: Deploy and verify Phase 1 on the VPS

**Files:**
- Modify: `worker/studio/__init__.py` (`__version__ = "1.1.0"`), `docs/BRAIN.md`, `docs/ARCHITECTURE.md` (pipeline
  section: no scorecard loop, Sonnet/medium, stop_after)

- [ ] **Step 1:** Full worker suite + web `tsc`/lint → all green. Opus code review of the phase diff
  (`superpowers:requesting-code-review`); fix what it confirms.
- [ ] **Step 2:** Apply `0005_phase1.sql` with the Supabase connector (`apply_migration`); verify both columns exist.
- [ ] **Step 3:** Set `settings.global.paused = true` (keeps the scheduler from starting normal videos that would hit
  the old fact-check before Phase 2); log an event saying why.
- [ ] **Step 4:** Merge the branch into `main`, push `main` and the branch.
- [ ] **Step 5:** Wait for the VPS rebuild: poll `events` for `"Worker … started (v1.1.0)"` (up to ~20 min; check
  with a scheduled wake-up, not a sleep loop).
- [ ] **Step 6:** Insert 3 jobs, spaced so they run one after another: `plan_channel` with
  `payload={"channel_id": <overthought channel id>, "force": true, "stop_after": "script"}`.
- [ ] **Step 7:** For each: read the stop event's `data.seconds` (research + script), the saved script (beats, word
  count vs `word_range`, sources with URLs, self_review), and `spend` rows (model must be Sonnet). Pass = 3 valid
  scripts, typical research + script ≤ ~2 min (target, not hard; > 2.5 min → tune searches and re-run).
- [ ] **Step 8:** Send the owner a short Roman Urdu update with timings and one script's narration; update BRAIN §0
  (phase 1 done, global pause on and why, next = Phase 2 plan). Commit + push.
