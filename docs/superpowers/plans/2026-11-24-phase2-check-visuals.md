# Phase 2: check → visuals plan → images. Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Replace the slow web-search fact-check with a light one-call content check, draw scenes in parallel, and
fix stale restores on redo (A6) and RunPod error handling (A7).

**Architecture:** `content.policy_check` (one Claude call, no tools) plus a code-side length check;
`pipeline._visuals` uses a thread pool; `pipeline.produce`'s redo clearing deletes storage objects; `images.py` uses
the async `/run` endpoint and maps every network error to `ServiceDown`. Web: "Content check" panel and status label.

**Spec:** `docs/superpowers/specs/2026-11-24-production-line-design.md` (§7.2, §7.4b A6, A7)

## Global Constraints
- Sonnet/medium via `llm.structured` (already fixed). The check has **no web tools**.
- The check covers only: tone fits the channel (educational/motivating); nothing too graphic; TikTok Community
  Guidelines (dangerous acts/advice, harmful medical/financial misinformation, hate/harassment, graphic violence,
  sexual content, minors' safety). **Never** names, places, institutions, years or citations.
- Length: `content.word_count / wps ≥ max(61, min_seconds)` seconds (code).
- One targeted fix round, then one re-check. Still blocked → `PermanentError` with a plain reason.
- Images: at most 4 in parallel. The RunPod cap stays enforced per image (`spend.runpod_slot` is thread-safe).
- The `videos.factcheck` column and the `fact_checking` status keep their names (no migration).

## Review Focus
1. A redo from `script` must draw new scenes and never restore the old PNGs; the same for the voice → Task 3 test.
2. One failing image among 5 parallel ones must not lose the 4 that finished (they are uploaded, and a retry draws
   only the missing one) → Task 2 test.
3. The length-gate rewrite in the voice stage must use the new check, not the deleted fact-check → Task 1 test.
4. A RunPod network blip while polling parks the job (ServiceDown) instead of failing the video → Task 4 test.
5. Old videos whose `factcheck` holds the previous shape (`blocking`, `passes`) still count as done on resume →
   Task 1 test.

---

### Task 1: Light content check replaces the fact-check
**Files:** `worker/studio/content.py` (new `PolicyCheck`, `policy_check`; delete `FactCheck`, `Claim`,
`fact_check`), `worker/studio/pipeline.py` (factcheck stage, `_fc_done`, `_voice_with_length_gate`),
`worker/tests/fakes.py`, `worker/tests/test_pipeline_e2e.py`, `apps/web/lib/format.ts`,
`apps/web/app/(app)/videos/[id]/page.tsx`. Test: `worker/tests/test_policy_check.py`.

**Interfaces:**
- `content.PolicyProblem(line: Optional[int], issue: str, fix: str)`.
- `content.PolicyCheck(passed: bool, tone_ok: bool, graphic_ok: bool, policy_ok: bool,
  problems: list[PolicyProblem], summary: str)` with `ok() -> bool` (= `passed` and no problems).
- `content.policy_check(ch, script, *, video_id=None) -> tuple[PolicyCheck, float]`.
- `content.length_problem(script, ch) -> str | None`: the estimated seconds below `max(61, min_seconds)` →
  message.
- `pipeline._fc_done(fc)`: True when `fc.passed`, or (old shapes) `"blocking"` is empty, or `passes`.

- [ ] Write tests:
  - `test_check_passes_clean_script_with_one_call`: produce with `stop_after="factcheck"` → 3 claude calls total,
    `factcheck.passed`.
  - `test_check_problem_gets_one_fix_then_passes`: the fake returns a problem once → a rewrite happens → passes.
  - `test_check_still_blocked_fails_with_reason`: the fake always blocks → video `failed`, error starts
    "Content check failed".
  - `test_short_script_is_a_problem`: `length_problem` on a 100-word script (2.1 w/s, min 65) mentions seconds.
  - `test_old_factcheck_shape_counts_as_done`.
  - `test_length_rewrite_uses_policy_check`: the fake voice returns 120 s once → the rewrite and a `PolicyCheck`
    call follow; no `FactCheck` exists.
- [ ] RED → implement → GREEN → whole suite → commit.

### Task 2: Visuals plan + parallel images
**Files:** `worker/studio/pipeline.py` (visuals stage → `_draw_scenes`), test `worker/tests/test_visuals.py`.
**Interfaces:** `pipeline._draw_scenes(video, ch, script, sdir) -> None`. A `ThreadPoolExecutor(max_workers=4)`;
each worker generates, saves, uploads, and adds cost under a lock. After all workers finish, the first exception is
re-raised. A scene prompt is `description + ", props drawn as simple white outlines, no symbols, no text"`.
- [ ] Tests:
  - `test_scenes_are_drawn_in_parallel`: the fake `generate` sleeps 0.3 s; 5 scenes take < 1.2 s.
  - `test_one_failed_scene_keeps_the_others`: one scene raises → the 4 others are uploaded; a re-run calls
    `generate` once.
- [ ] RED → implement → GREEN → commit.

### Task 3: Redo never restores stale files (A6)
**Files:** `worker/studio/pipeline.py` (`produce` clearing). Test: in `test_visuals.py`.
**Interfaces:** When `from_stage <= visuals`, remove the storage objects `{slug}/{id}/scenes/*.png`. When
`from_stage <= voice`, remove `voice.mp3` + `words.json` and set `audio_path=None`. Use `db.list_objects` +
`db.remove`.
- [ ] Tests:
  - `test_redo_from_script_draws_new_scenes`: after a full run, redo from `script` → `generate` is called again
    for every scene.
  - `test_redo_from_voice_records_new_voice`: redo from `voice` → `synthesize` is called again.
- [ ] RED → implement → GREEN → commit.

### Task 4: RunPod errors and no double pay (A7)
**Files:** `worker/studio/images.py`. Test: `worker/tests/test_images_runpod.py` (httpx `MockTransport` via a
monkeypatched `httpx.Client`).
**Interfaces:**
- Submit with `/run` (async), then poll `/status/{id}` every 2 s up to 300 s. On timeout → `/cancel` + RuntimeError.
- Any `httpx.TransportError` anywhere → `ServiceDown("runpod", …)`.
- The image GET uses `raise_for_status`; ≥ 400 → `ServiceDown`.
- [ ] Tests:
  - `test_poll_network_error_is_service_down`;
  - `test_image_download_error_is_service_down`;
  - `test_completed_job_returns_image` (the happy path through `/run` + status).
- [ ] RED → implement → GREEN → commit.

### Task 5: Deploy and verify Phase 2 on the VPS
- [ ] Full suite + web tsc/lint; Opus whole-branch review; one fix pass.
- [ ] Bump the worker to v1.2.0; update ARCHITECTURE + BRAIN.
- [ ] Merge to main, push; wait for "Worker … started (v1.2.0)".
- [ ] Run 2× `plan_channel {force:true, stop_after:"visuals"}` and check:
  - the check verdicts and the visuals seconds;
  - the scene PNGs (download 2 from storage and look at them);
  - `spend` rows for RunPod vs the meter.
- [ ] Owner update (Roman Urdu). Keep the studio paused until Phase 3 is verified.
