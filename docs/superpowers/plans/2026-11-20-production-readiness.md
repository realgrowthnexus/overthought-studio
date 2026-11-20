# Production Readiness (end to end) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Take Overthought Studio from "built and unit-tested" to "running live on the VPS, with a real Claude-made video produced end to end and a TikTok draft delivered", with proof at every step.

**Architecture:** No redesign. The dashboard (`apps/web`) and worker (`worker/`) talk only through Supabase tables. Work goes in four layers:
- offline proof: fake services drive the real pipeline and the real render;
- a request-contract test for the Claude calls;
- operator tools: a `smoke` CLI command, plus `infra/doctor.sh` for the owner to paste back;
- live verification: inject a job through Supabase REST, then watch `jobs`, `videos` and `events`.

**Tech Stack:** Python 3.13 worker (`anthropic==2.10.0`, httpx, pydantic, pytest), Next.js 15.5 dashboard, Supabase, Docker Compose on the Hostinger VPS, Playwright (pre-installed) for the live web smoke.

**Spec:** `docs/BRAIN.md` §2 (product rules), §6 (next steps), §7 (quality bar); `docs/ARCHITECTURE.md` (system contract). Owner request, 2026-11-20: "take charge … make it production ready end to end".

## Global Constraints

- Every video must be **> 60 s** (`HARD_MIN_SECONDS = 61.0`); target 65–90 s.
- Model default is `claude-opus-5-5`, effort default `"high"` (Opus 5.5's API default is `medium`, so it is always sent explicitly), `thinking={"type":"adaptive"}`, `betas=["server-side-fallback-2026-07-01"]` with `fallbacks="default"`, web search tool `web_search_20260209`.
- Only official TikTok APIs. No bots, browser automation, proxies or device masking.
- Never write secret values into the repo, the plan, commits or chat. Use `request_credential` for proxy keys; Anthropic keys go only in dashboard Settings.
- Ask the owner before anything that posts publicly, spends more than a few dollars unexpectedly, or creates accounts. A full live video costs roughly $1–3; Task 6 asks once before running it.
- Owner messages are in Roman Urdu or simple English: short, numbered steps, a clear "what I need from you" list.
- Commit to `main` on `realgrowthnexus/overthought-studio` with the session attribution lines. Update `docs/BRAIN.md` after every task.
- No GitHub Actions (the account is billing-locked). All checks run locally or in this session.

## Review Focus

1. **Claude request rejected (400) on the first live call.** The worker has never called the API. Expected: the request matches the SDK and API contract, so the first call succeeds. This is pinned by Task 2's request-body assertions.
2. **Non-streaming `research()` with `max_tokens=32000`.** The SDK may refuse a long non-streaming request, or time out during a long web-search turn. Expected: research completes. Task 2 tests it; switch to streaming if needed.
3. **Structured output that is schema-valid but unusable.** Examples: a `scene_id` that isn't in `scenes`, more than one `key` part, an empty `beats` list. Expected: the render still produces a > 61 s video, not a crash. Task 1 covers this with a deliberately messy fake script.
4. **A service out of credits in the middle of a video**, such as an ElevenLabs quota error. Expected: the job parks as `waiting`, the red bar names ElevenLabs, and the job resumes when the service is `ok`. Task 1 has a park-and-resume test.
5. **The worker restarts in the middle of a video**, so the work directory is gone. Expected: `produce(from_stage=None)` resumes from storage without redoing paid stages. Task 1 deletes the work dir between stages and asserts no second Claude or RunPod call.

---

### Task 0: Restore live access for this session (no code)

The current cloud environment `overthought-studio` (env_01TJ5FBy4nZt3RRkNjTKNPPG) allows only Hostinger hosts. A call to Supabase returned a proxy 403.

- [ ] **Step 1:** Run `get_environment`. Then propose `update_environment` with:
  - `add_allowed_hosts`: `xkbgusqmdeocjwxaknjx.supabase.co`, `studio.getgrowthnexus.com`, `api.elevenlabs.io`, `api.runpod.ai`, `open.tiktokapis.com`.
  - Reason: "Live checks of the deployed studio."
- [ ] **Step 2:** `request_credential` for `xkbgusqmdeocjwxaknjx.supabase.co`: header `apikey`, no prefix, the Supabase secret key.
- [ ] **Step 3: Verify.** Run `curl -s -H "apikey: x" "https://xkbgusqmdeocjwxaknjx.supabase.co/rest/v1/channels?select=slug"`. Expected: a JSON array with 5 slugs.
- [ ] **Step 4:** Record the env change in `docs/BRAIN.md` §4.

### Task 1: Offline end-to-end pipeline test with fake services

**Files:**
- Create: `worker/tests/fakes.py`. It holds an in-memory fake for `studio.db` (`select`, `insert`, `update`, `upload`, `download`, `rpc`), plus fake `llm.structured` / `llm.research`, `images.generate` and `voice.synthesize`.
- Create: `worker/tests/test_pipeline_e2e.py`.
- Modify: only what the test exposes as broken (`worker/studio/pipeline.py`, `content.py`, `render/*`).

**Interfaces:**
- Consumes the real modules:
  - `pipeline.produce(video_id: str, from_stage: str | None = None) -> dict`;
  - `main.run_one(job: dict) -> None`;
  - `content.Script / Scorecard / FactCheck`.
- Produces `fakes.install(monkeypatch) -> FakeWorld`. `FakeWorld` has these fields:
  - `.tables: dict[str, list[dict]]`;
  - `.storage: dict[str, bytes]`;
  - `.calls: collections.Counter` (keys `"claude"`, `"runpod"`, `"elevenlabs"`);
  - `.fail_next: dict[str, Exception]`.

  Fake voice builds ~70 s of word timings at 2.6 words/s from the narration, and writes a silent mp3 of that length with ffmpeg (`anullsrc`). Fake images return a 1024×1024 dark PNG with a white stick figure drawn by PIL.

- [ ] **Step 1: Write the failing tests.**
  - `test_produce_reaches_ready_and_video_is_over_60s`. Seed a channel from `seed.CHANNELS[0]` and a video `status="queued"`, then call `produce`. Assert:
    - `video["status"] == "ready"`;
    - `video["approval"] == "pending"`;
    - `ffprobe(storage[".../final.mp4"]).duration > 61`;
    - the stream is H.264 1080×1920 at 30 fps;
    - `thumb.jpg` exists;
    - `cost_usd > 0`.
  - `test_messy_script_still_renders`. The fake `write_script` returns a script with: one beat whose `scene_id=99` (no such scene), one beat with two `key` parts, and one `source_index=7` (out of range). Assert `status == "ready"`.
  - `test_resume_after_restart_does_not_repay`. Run until after `voice` by making the fake render raise once. Delete `config.WORK/videos/<id>`, then call `produce(id)`. Assert:
    - `calls["claude"]` is unchanged;
    - `calls["runpod"]` is unchanged;
    - `calls["elevenlabs"]` is unchanged;
    - the status is `ready`.
  - `test_out_of_credits_parks_job`. Set `fail_next["elevenlabs"] = OutOfCredits("elevenlabs", "quota")` and call `main.run_one(job)`. Assert:
    - the job `status == "waiting"` and `waiting_on == "elevenlabs"`;
    - the `services` row for elevenlabs has status `out_of_credits`.
  - `test_factcheck_fails_twice_is_permanent`. The fake fact-check always returns `passes=False`. Assert:
    - the video status is `failed`;
    - the error starts with `"Fact-check failed"`;
    - the job isn't retried.
- [ ] **Step 2: Run them.** Run: `cd worker && python -m pytest -q tests/test_pipeline_e2e.py`. Expected: FAIL. Record each real failure: this is the first time these paths have run together.
- [ ] **Step 3: Fix each failure in the owning module.** Fix the code, not the test, unless the test contradicts `ARCHITECTURE.md`.
- [ ] **Step 4: Verify.** Run: `python -m pytest -q tests`. Expected: all tests pass, the old 10 plus 5 new.
- [ ] **Step 5:** Extract 3 frames from the fake-run mp4 at 1 s, 30 s and 60 s with ffmpeg. Look at them. Check: captions are inside the safe zones, the accent pop shows, the source line is readable.
- [ ] **Step 6: Commit.** `test(worker): offline end-to-end pipeline with fake services` plus any fixes.

### Task 2: Claude request-contract test

**Files:**
- Create: `worker/tests/test_llm_contract.py`.
- Modify: `worker/studio/llm.py` if the test shows a mismatch.

**Interfaces:**
- Consumes:
  - `llm.structured(schema, system, prompt, *, purpose, ...) -> tuple[T, float]`;
  - `llm.research(...) -> tuple[str, list[dict], float]`;
  - `llm.ping() -> dict`.
- Test seam: monkeypatch `llm._get_client` to return `anthropic.Anthropic(api_key="test", http_client=httpx.Client(transport=httpx.MockTransport(handler)))`. The handler records each request's JSON body and headers, and returns canned Messages API JSON.

- [ ] **Step 1: Write the failing tests.**
  - `test_structured_request_shape`. Assert the body has:
    - `model == "claude-opus-5-5"`;
    - `thinking == {"type": "adaptive"}`;
    - `output_config["effort"] == "high"`;
    - `output_config["format"]["type"] == "json_schema"`;
    - `fallbacks == "default"`;
    - `system[0]["cache_control"] == {"type": "ephemeral"}`;
    - the header `anthropic-beta` contains `server-side-fallback-2026-07-01`;
    - no `temperature`, `top_p` or `budget_tokens`.

    Assert the parsed object round-trips into `content.Scorecard`.
  - `test_research_handles_pause_turn_and_citations`. The handler first returns `stop_reason="pause_turn"`, then `end_turn` with a text block carrying 2 citations, one with a duplicate URL. Assert:
    - 2 requests were made;
    - the second request's `messages[-1]["role"] == "assistant"`;
    - the result has 1 unique citation, and `usd` includes `WEB_SEARCH_USD`;
    - `tools[0]["type"] == "web_search_20260209"`.
  - `test_research_large_max_tokens_is_allowed`. Call `research()` with the real `max_tokens=32000`. Assert no SDK exception about streaming. If it raises, change `research()` to `client.beta.messages.stream(...)` + `.get_final_message()` with the same params, and keep this test.
  - `test_refusal_raises_readable_error`: `stop_reason="refusal"` with `stop_details.category="cyber"` → `RuntimeError` matching `"declined"`.
  - `test_low_credit_maps_to_out_of_credits`: HTTP 400 with `"Your credit balance is too low"` → `OutOfCredits`.
  - `test_bad_key_maps_to_not_configured`: HTTP 401 → `NotConfigured`.
- [ ] **Step 2: Run them.** Run: `python -m pytest -q tests/test_llm_contract.py`. Expected: FAIL where the code and the contract differ.
- [ ] **Step 3: Fix `llm.py`.** Make it match `/claude-api` skill docs (`python/claude-api/README.md`, `tool-use.md` § Structured Outputs).
- [ ] **Step 4: Verify.** Run: `python -m pytest -q tests`. Expected: all pass.
- [ ] **Step 5: Commit.** `test(worker): pin Claude request contract`.

### Task 3: Operator smoke command and VPS doctor

**Files:**
- Modify: `worker/studio/cli.py`. Add `smoke`.
- Create: `infra/doctor.sh`.
- Modify: `infra/install.sh` so it copies `doctor.sh` to `/opt/overthought-studio/doctor.sh` and prints its usage at the end.

**Interfaces:**
- `cli.smoke() -> dict` returns `{"anthropic": {...}, "elevenlabs": {...}, "runpod": {...}, "supabase": {...}, "ffmpeg": str, "usd": float}`. In order, it runs:
  1. `llm.ping()`;
  2. one `llm.structured(content.Scorecard, ...)` call at `effort="low"` on a fixed 3-line script;
  3. `voice.subscription()`;
  4. a RunPod balance query (reuse the function `ops.health_check` uses);
  5. `db.select("channels", columns="slug")`;
  6. `ffmpeg -version`.

  Each part is caught separately. The output is one JSON line, with no secrets: only the last 4 characters of a key hint.
- `infra/doctor.sh` prints, without any secret values:
  - `docker compose ps`;
  - the age of the newest `worker_heartbeats` row (through `docker compose exec worker python -c ...`);
  - `curl -sI http://127.0.0.1:3100/login | head -1`;
  - the DNS result of `getent hosts studio.getgrowthnexus.com`;
  - the TLS check `curl -sI https://studio.getgrowthnexus.com/login`;
  - `python -m studio.cli smoke` inside the worker;
  - the last 30 worker log lines with lines matching `(?i)key|secret|token` redacted.

- [ ] **Step 1: Write the failing test.** `test_smoke_reports_each_part_independently`. With `llm.ping` raising `NotConfigured` and everything else faked OK, assert:
  - `result["anthropic"]["ok"] is False`, and the error says "No Anthropic API key saved";
  - `result["supabase"]["ok"] is True`;
  - the process exit code is 1.
- [ ] **Step 2: Run it.** Run: `python -m pytest -q tests/test_cli_smoke.py`. Expected: FAIL.
- [ ] **Step 3: Implement** `smoke` and `doctor.sh`.
- [ ] **Step 4: Verify.** Run:
  - `python -m pytest -q tests`;
  - `bash -n infra/install.sh infra/doctor.sh`;
  - `shellcheck infra/*.sh` (install with `apt-get install -y shellcheck` if missing).

  Expected: tests pass, no syntax errors, no shellcheck errors at warning level or above.
- [ ] **Step 5: Commit.** `feat(ops): smoke check and VPS doctor script`. Update `docs/SETUP.md` Step 4 with: "after install, run `/opt/overthought-studio/doctor.sh` and send me the output".

### Task 4: Docs that contradict the decision

**Files:**
- Modify: `docs/ARCHITECTURE.md`. The diagram says "Vercel"; it becomes "Docker on the VPS". "Same value on Vercel and VPS" becomes "web and worker containers share `/opt/overthought-studio/.env`". Drop "CI" from the `infra/` line.
- Modify: `docs/BRAIN.md`. Collapse §5 "Old notes (superseded)" to one line.

- [ ] **Step 1:** Make the edits.
- [ ] **Step 2: Verify.** Run `grep -n -i "vercel\|web app hosting" docs/*.md`. Expected: only the one-line history note in BRAIN.
- [ ] **Step 3: Commit.** `docs: align architecture with the VPS decision`. Push `main`.

### Task 5: Owner deploys; verify the live install (owner + me)

Gate: Tasks 1–4 are pushed, so the VPS auto-update and the installer pull the fixed code.

- [ ] **Step 1:** Send the owner a short Roman Urdu checklist:
  - run the installer (or, if it was already run, `/opt/overthought-studio/update.sh --force`);
  - add the DNS A record `studio → 2.24.74.240`;
  - Supabase Auth: turn sign-ups off and set the Site URL;
  - create the login at `/setup`;
  - Settings: Anthropic key plus the credit balance, ElevenLabs (with User: Read), RunPod;
  - run `doctor.sh` and paste the output. No keys in chat.
- [ ] **Step 2: Verify from here (needs Task 0).**
  - `rest/v1/worker_heartbeats` is newer than 2 minutes.
  - `rest/v1/services`: `anthropic`, `elevenlabs`, `runpod`, `storage` and `worker` are all `ok`, or a warning has a stated reason.
  - `doctor.sh`: `smoke` shows every part `ok`.
- [ ] **Step 3: Live web smoke.** Write `scratchpad/live-smoke.mjs`: Playwright with `chromium.launch()` and `deviceScaleFactor: 1`, against `https://studio.getgrowthnexus.com`. Assert:
  - `/login` returns 200 and the email field is visible;
  - `/setup` doesn't offer a form once the owner exists;
  - `/privacy` and `/terms` return 200 (TikTok review needs them);
  - the response headers include `content-security-policy` and `strict-transport-security`;
  - `/` without a session redirects to `/login`.

  Take screenshots at 375 px and 1280 px.
- [ ] **Step 4: Ask the owner** to log in once on their phone and confirm the overview loads. Browser login with a real session can't be tested without their password.
- [ ] **Step 5:** Record the results in `docs/BRAIN.md` §3 and §6, then commit.

### Task 6: First real Claude-made video, end to end

Gate: Task 5 is green. Ask the owner once: "Pehli asli video ~$1–3 ki banegi, chalaoon?"

- [ ] **Step 1:** Insert the job through REST:

  `POST rest/v1/jobs {"type":"plan_channel","payload":{"channel_id":"<overthought id>","force":true},"status":"queued"}`

  This is the same row the "Make a video now" button writes. Check `apps/web/lib/actions.ts` for the exact columns before inserting.
- [ ] **Step 2: Watch.** Poll `videos?id=eq.<id>&select=status,stage_detail,progress,error,cost_usd`, and the newest `events`, every few minutes. Use a Monitor until-loop, not a sleep. Expected stage order: `researching → scripting → fact_checking → visuals → voice → rendering → ready`.
- [ ] **Step 3: On failure,** use superpowers:systematic-debugging. Then:
  - reproduce offline with the Task 1 fakes, seeded with the real failing payload;
  - fix it;
  - push and let auto-update deploy (or ask the owner to run `update.sh --force`);
  - resume with a `produce_video` job carrying `from_stage`.
- [ ] **Step 4: Review the output.**
  - Download `final.mp4` via a signed URL.
  - `ffprobe`: duration > 61 s, 1080×1920, 30 fps, H.264.
  - Look at 6 frames.
  - Read `script`, `scorecard` and `factcheck`. Check that every on-screen source exists by searching each `Researcher · Institution · Year`. Check that the hook is at second 0 and that the loop line closes back into the hook.
  - Record the cost per stage from `cost_breakdown`.
- [ ] **Step 5:** Send the owner the video plus a short Roman Urdu note: quality, cost, anything weak. Record the results in BRAIN and commit.

### Task 7: TikTok sandbox draft (owner + me)

Gate: Task 6 has a `ready` video. The owner creates the developer app using the guide on the dashboard's TikTok accounts page and `docs/SETUP.md` Step 6.

- [ ] **Step 1:** Owner tasks:
  - paste the client key and secret into Settings;
  - add the TikTok accounts as sandbox target users;
  - press Connect on the TikTok accounts page.
- [ ] **Step 2: Verify.** `tiktok_accounts` has a row with `status` ok and a token expiry in the future, and `services.tiktok` is `ok`.
- [ ] **Step 3:** Set the Overthought channel `posting_mode="draft"`. Approve the Task 6 video in the dashboard; this is the owner's tap. Insert a `publish_video` job.
- [ ] **Step 4: Verify.** `check_publish` ends with status `SEND_TO_USER_INBOX`. The owner confirms the draft is in their TikTok inbox.
- [ ] **Step 5:** Guide the owner through Submit for review, then the Content Posting API audit request. Record the dates in BRAIN.

### Task 8: Final production audit and handoff

- [ ] **Step 1:** Dispatch a fresh reviewer, using superpowers:requesting-code-review, over everything changed since `b2c53ac`. Fix the confirmed findings.
- [ ] **Step 2: Verify.** Run:
  - `cd worker && python -m pytest -q tests`;
  - `cd apps/web && npx tsc --noEmit && npm run lint && npm run build`.

  Expected: all green. Paste the output in BRAIN.
- [ ] **Step 3:** Rewrite BRAIN §0, §3 and §6 to the new state: what is live, what is owner-only, what's next (the niches for channels 2–5).
- [ ] **Step 4:** Send the final report to the owner in Roman Urdu: what works, what it costs per video, what they still tap, what's next. Commit and push.
