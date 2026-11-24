# Phase 3: voice → render → ready (+ publish safety). Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax.

**Goal:** The voice lands in the channel's length window without rewrites in the normal case. The render can't hang.
A finished video reaches `ready`, and publishing can neither hammer TikTok nor loop forever.

**Spec:** `docs/superpowers/specs/2026-11-24-production-line-design.md` (§7.3, §7.4b A8–A10)

## Global Constraints
- `channels.voice.wps` = the measured words per second **at speed 1.0**: a running average over the last 5 voices
  (`wps_n` counts up to 5). The effective pace is `wps × voice.speed`, and `content.word_range` uses the effective
  pace.
- Speed nudge: the voice speed is changed within **0.92–1.10 ×** the channel's own speed. Only if that fails: one
  narration-only rewrite with the scenes kept, then the light check (never the old fact-check). A hard fail happens
  only below 61 s.
- Saving the channel form must keep `voice.wps` / `wps_n`.
- Render: `ProcessPoolExecutor` (a dead child raises instead of hanging); the render subprocess times out after
  25 min; a video without an audio stream is an error.
- Publish:
  - a TikTok rate limit moves `scheduled_for` to now + 3 h (never enqueues while the job holds the dedupe key);
  - after 3 failed publish attempts of a video, it becomes `failed` with a plain error. The count lives in
    `videos.publish_status.failures`.

## Review Focus
1. A channel whose owner set the speed slider to 1.1 must still get the right word target → Task 1.
2. A 110 s first voice must end inside the window after a speed nudge, with no rewrite → Task 1.
3. Two videos measuring `wps` at the same time must not crash, and a later form save must not wipe it → Task 1 + web.
4. A render child killed by the OOM killer must fail fast, not after 60 min → Task 2.
5. A rate-limited publish must not be retried every minute → Task 3.

### Task 1: Calibrated voice length (wps + speed nudge)
**Files:** `worker/studio/content.py` (`effective_wps`, `word_range`, `length_problem` use it),
`worker/studio/pipeline.py` (`_voice_with_length_gate`, new `_learn_wps`), `apps/web/lib/actions.ts`
(`updateChannel` keeps `wps`/`wps_n`). Test: `worker/tests/test_voice_fit.py`.
**Interfaces:**
- `content.effective_wps(ch) -> float` = `(voice.wps or 2.1) × (voice.speed or 1.0)`.
- `pipeline._learn_wps(ch, words: int, seconds: float, speed: float) -> None`: updates `channels.voice` with the
  new average (`x = words / seconds / speed`; `avg += (x - avg) / min(n + 1, 5)`).
- `voice.synthesize(text, voice_cfg, …)` already takes `voice_cfg["speed"]`. The gate passes a copy with the
  nudged speed.
- [ ] Tests:
  - `test_word_range_follows_speed`: wps 2.0 and speed 1.1 → the same as wps 2.2.
  - `test_long_voice_is_fixed_by_speed_not_rewrite`: the fake voice returns 110 s on the first call and honours
    speed afterwards → exactly 2 syntheses, no extra Script call, and the 2nd call's speed is ≤ 1.10.
  - `test_still_out_of_range_rewrites_once`: the voice stays long even when sped up → 1 rewrite + a PolicyCheck,
    and the video still reaches the render.
  - `test_wps_is_learned_and_averaged`: two voices → `channels.voice.wps` moves toward the measured value and
    `wps_n == 2`.
- [ ] RED → GREEN → commit.

### Task 2: Render cannot hang; audio required (A8)
**Files:** `worker/studio/render/compose.py` (pool), `worker/studio/pipeline.py` (`_render` timeout + audio check).
Test: `worker/tests/test_render_safety.py`.
- [ ] Tests:
  - `test_missing_audio_stream_is_an_error`: monkeypatched probe returns `acodec=None` → `RuntimeError` mentioning
    audio.
  - `test_render_timeout_is_25_minutes`: the `RENDER_TIMEOUT_S` constant is 1500 and is used by `_render`.
  - `test_dead_render_child_raises`: `compose._run_segments` with a job function that calls `os._exit(1)` →
    raises `BrokenProcessPool` quickly.
- [ ] RED → GREEN → commit.

### Task 3: Publish safety (A9, A10)
**Files:** `worker/studio/ops.py` (`publish_video`). Test: `worker/tests/test_publish_safety.py` (fake
`tiktok.post_video`).
- [ ] Tests:
  - `test_rate_limit_moves_the_post_3h_later`: `post_video` raises `TikTokError("spam_risk_too_many_posts")` →
    the video is `scheduled`, `scheduled_for` ≈ now + 3 h, no new `publish_video` job, and the job result is
    `{"retry": …}`.
  - `test_third_publish_failure_fails_the_video`: a generic `TikTokError` 3 times → the 3rd leaves the video
    `failed` with an error starting "Publishing failed 3 times".
- [ ] RED → GREEN → commit.

### Task 4: Deploy and verify Phase 3 on the VPS
- [ ] Full suite + web tsc/lint; Opus review; one fix pass; worker v1.3.0; docs + BRAIN.
- [ ] Merge to main (only after Phase 2 is verified on the VPS); wait for v1.3.0.
- [ ] 3 full videos: `plan_channel {force:true}` (no stop_after; the studio stays paused, so nothing is scheduled
  or posted). Check: status `ready`/`approved`, duration 61–98 s, the per-stage seconds, the learned `wps`, the
  real cost, and download one preview to watch.
- [ ] Owner update with the preview link; then unpause (the owner still approves each video).
