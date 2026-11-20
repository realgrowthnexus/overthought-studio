# Plan — worker on the owner's Claude Pro sign-in

Spec: `docs/superpowers/specs/2026-11-20-claude-subscription-design.md` (binding).
Execution: inline (superpowers:executing-plans), TDD per task, one final review.

## Global constraints
- No real Claude calls in tests: a fake `claude` executable on PATH (`worker/tests/fake_claude.py`).
- The secrets never get logged: the token is stored encrypted in `secrets` (key `claude_oauth_token`) and is passed to the
  CLI only through the subprocess env (`CLAUDE_CODE_OAUTH_TOKEN`).
- The public signatures of `llm.structured`, `llm.research` and `llm.ping` don't change.
- Test command (worker): `cd worker && python -m pytest -q -p no:cacheprovider`.
- Web check: `cd apps/web && npx tsc --noEmit && npx next lint` (if lint is configured).

## Interfaces
- `services.LimitReached(ServiceProblem)`: `status="limited"`, attribute `resume_at: datetime`. (T1 → T3, T4, T5)
- `claude_cli.run(prompt, *, system, schema: dict | None, tools: list[str], model: str, timeout: int) -> dict` returns
  `{"text", "structured", "usage", "model"}`. It raises `LimitReached`, `NotConfigured` or `RuntimeError`. (T2 → T3)
- `usage.read() -> dict | None`: `{five_hour:{pct,resets_at}, seven_day:{pct,resets_at}, source}`;
  `usage.record_run(video_id)`, `usage.pacing_on() -> bool`. (T4 → T5, T7)
- `services.details` for `anthropic`, as JSON:
  `{backend, plan, five_hour, seven_day, source, pacing, per_video_pct, week_videos, resume_at}`. (T4 → T7)

## Tasks

### Task 1 — `limited` status + `LimitReached`
- Migration `supabase/migrations/0004_claude_subscription.sql`: allow `'limited'` in the `services.status` and
  `jobs.parked_status` checks (if a check exists).
- `services.py`: add `class LimitReached(ServiceProblem)` with `status="limited"` and `__init__(service, message, resume_at)`.
  `report_problem` puts `resume_at` in `details`.
- `main.run_one`: a `LimitReached` parks the job with `waiting_on="anthropic"`, does **not** add to `waits` (so the
  24-hour give-up never fires for limits), logs an event at level `warn` (not `error`), and sets the channel
  `blocked_reason` to "Claude limit reached — resumes at HH:MM".
- `ops._resume_waiting`: a service with status `limited` counts as healthy once now ≥ `details.resume_at`.
- Tests: in `test_core.py` style, (a) a job raising LimitReached parks with waits unchanged and the video blocked with its
  previous status kept; (b) resume re-queues only after `resume_at`.

### Task 2 — `claude_cli.py` (headless Claude Code runner)
- Command: `claude -p <prompt> --output-format json --system-prompt <system> --model <model>`. Add
  `--json-schema <json>` when there is a schema. Pass `--allowedTools <tools>` when tools are given. Add
  `--disallowedTools` for Bash, Edit, Write, Read, Glob, Grep, NotebookEdit, Task. Add `--max-turns`.
  `cwd` = an empty scratch dir.
- env: copy the worker env minus `ANTHROPIC_API_KEY`. `HOME=$STUDIO_WORK/.claude-home`.
  `CLAUDE_CODE_OAUTH_TOKEN=<secret>`.
- Parse the result JSON. `is_error` or `subtype != success`:
  - a limit message (`limit` together with `reset`, `usage limit reached`, or an `|<epoch>` suffix) → `LimitReached`.
    `resume_at` comes from the epoch, the usage endpoint, or +1h;
  - auth or login text (`/login`, `invalid api key`, `OAuth`, `401`) → `NotConfigured("anthropic", "Claude is not signed in")`;
  - anything else → `RuntimeError`.
- No token → `NotConfigured`.
- `auth_ok()`: the token exists, and a call to the CLI's own auth status (no model call) succeeds. If no such command
  works, return "token present" (best-effort).
- Tests: a fake CLI covering success, structured output, limit, auth error and garbage output. Also check the argv the
  fake received: no forbidden tools, schema passed, and the token not in argv.

### Task 3 — `llm.py` backend switch
- `backend()`: returns `"subscription"` unless an API key is saved **and** `settings.get("llm_backend") == "api"`.
- `structured` on subscription: `claude_cli.run(..., schema=schema.model_json_schema())`, then `schema.model_validate`.
  USD = 0. Record spend with usd 0 and units = output tokens if known. Call `usage.record_run(video_id)`.
- `research` on subscription: the prompt asks for notes plus sources. A structured schema
  `{notes: str, sources: [{url,title,quote}]}` is used with tools `WebSearch, WebFetch`. Return
  `(notes, [{url,title,cited_text}], 0.0)`.
- `ping` on subscription: `claude_cli.auth_ok()`, which does not use limit.
- Model table: `heavy` = the settings model, default `opus`, applies to research/script/factcheck/idea/weekly.
  `light` = `sonnet`, applies to scorecard/smoke. Use the CLI aliases.
- `ops._health_anthropic`:
  - subscription → `ping` → set_status `ok` with message "Connected (Claude subscription)", unless the service is
    `limited` and `resume_at` is still in the future;
  - also call `usage.refresh()`;
  - not signed in → `NotConfigured`, with SETUP_HINTS text "Sign in to Claude: run sudo bash
    /opt/overthought-studio/src/infra/connect-claude.sh on the VPS".
- Tests: existing LLM contract tests still pass on the api backend; new tests cover the subscription backend with the
  fake CLI.

### Task 4 — `usage.py` (reading limits, cost per video, pacing)
- `read()`: GET `https://api.anthropic.com/api/oauth/usage` with `Authorization: Bearer <token>` and
  `anthropic-beta: oauth-2025-04-20`, timeout 10s. Parse `five_hour`/`seven_day` → `{pct (0-100), resets_at ISO}`
  defensively. Any failure → None.
- `refresh()`: read → merge into `services.details` (source `reported`), or keep the old reading and set source
  `estimate`. Count `week_videos` (videos that reached `ready` since the last weekly reset, or else in the last 7 days).
- Per-video cost: before the first and after the last Claude run of a video, record the weekly %. Store it on the video
  (`videos.experiment.claude_week_pct` or a small json). `per_video_pct` = mean of the last 5 videos. Only reported
  readings count.
- `pacing_on()`: false unless there is a reported reading and `per_video_pct` is set. True when
  `used + remaining_slots_until_reset × per_video_pct > 95`. `remaining_slots_until_reset` counts each active channel's
  slots between now and `seven_day.resets_at` (all post times). Persist the `pacing` flag in details, and log an event
  when it flips.
- Tests: parse the sample response; a failure gives None; the pacing maths at the threshold edges; pacing off without a
  reported reading.

### Task 5 — scheduler: pacing + round-robin
- `slots(ch, days, pacing=False)`: when pacing, keep only the earliest post time per day.
- `_channel`: get `pacing = usage.pacing_on()` once per tick (cached for the tick). Scheduled videos keep their times
  (no change). Planning is round-robin: only plan for a channel if its in-production count is ≤ the minimum
  in-production count among active channels whose buffer is short.
- Tests: pacing drops evening slots; scheduled evening videos stay put; round-robin blocks a second video while another
  channel has none.

### Task 6 — Packaging and sign-in
- `worker/Dockerfile`: install Node (nodesource or Debian `nodejs`, at least 18) and `npm i -g @anthropic-ai/claude-code@2.1.329`.
- `cli.py`:
  - `claude-token`: read the token from stdin, validate `^sk-ant-oat[0-9A-Za-z_-]+$`, encrypt it, and upsert it into
    `secrets`, then clear the cache and run a health check;
  - `claude-status`: one line, connected / not signed in, plus the limit %.
- `infra/connect-claude.sh`:
  - run `docker compose exec -it worker claude setup-token` under `script -q` into a temp file (mode 600);
  - pull out the `sk-ant-oat…` token, strip ANSI codes, and pipe it to `docker compose exec -T worker python -m studio.cli claude-token`;
  - shred the temp file and clear the screen;
  - print "Claude connected ✓".
- `infra/doctor.sh`: add a line `Claude: <claude-status>`, with no secrets.
- `smoke` uses a light-model structured call (it still costs limit, but only a little; document this).
- Tests: claude-token rejects garbage and stores a valid token encrypted (with the fake world); a shellcheck-style
  test runs `connect-claude.sh` token extraction on a sample transcript (`infra/tests`).

### Task 7 — Dashboard
- `types.ts`: add `limited` to the service status type. Service details are typed.
- Shared `ClaudeUsageCard` (components/claude-usage.tsx):
  - shows Connected / Not signed in;
  - two Progress bars (5-hour, weekly) with "resets <time>";
  - "This week: N videos · about M more fit";
  - a pacing notice;
  - a "estimate" label when the source isn't reported;
  - when not signed in, a copyable command (CopyField).
- Overview page: the card next to the Services strip. Settings: the card at the top of the Claude section. The API key
  field moves under a collapsed "Advanced: use an API key instead".
- The services strip shows `limited` in amber/neutral with "resumes HH:MM", not red.
- Check: tsc, plus the demo ui-check if the demo copy is running (optional).

### Task 8 — Docs
- docs/SETUP.md: a "Connect Claude" step replaces the Anthropic key step. docs/WEB.md mentions the card. docs/BRAIN.md
  gets the decisions and next steps.

## Review focus
- The token must never reach argv, logs, events, doctor output or exceptions.
- Limit parks must never trip the 24-hour give-up or the 3-failure circuit breaker.
- Pacing must never move or drop videos that exist already.
