# Run the worker on the owner's Claude Pro subscription instead of an API key

Date: 2026-11-20 · Status: approved in conversation (approach 1)

## Intent and why

The owner finds API keys messy: they have to create a key, buy credits and watch the balance. They want the studio to
use their **Claude account sign-in** (Claude Pro), the way Claude Code does. That means no key, no credit balance and
no per-token bill. The owner is not a developer. Their father only watches and approves videos.

## Goals

- The worker makes every Claude call (research with web search, script, scorecard, fact-check, idea research, weekly
  review, health check) through **Claude Code in headless mode, signed in with the owner's Pro account**. No Anthropic
  API key is needed anywhere.
- Signing in is **one command on the VPS**. The owner opens a link, signs in in the browser and pastes back one code.
  They never copy or handle a token. The sign-in survives worker restarts and image rebuilds.
- A **"Claude limit" card** on the Overview and Settings pages shows:
  - Connected / Sign in again;
  - 5-hour limit: % used and reset time;
  - weekly limit: % used and reset time;
  - videos made this week, and how many more fit, roughly.
- **Hitting a limit is normal, not an error.** Work parks and resumes on its own after the reset. The dashboard says
  "Claude limit reached — resumes at 3:40 PM" in calm (not red) styling.
- **Weekly pacing:** if the current pace would use up the weekly limit before it resets, the worker skips **evening**
  videos first. Every channel's morning video keeps going, so the week never stops halfway. The dashboard says plainly
  when pacing is on and why (owner agreed).
- The work order inside a window: every channel's morning video first, then the evening ones.

## Target load (owner's words)

5 TikTok channels × 2 videos a day (morning and evening) = 10 videos a day, about 70 a week. Nobody knows yet whether
Pro's weekly limit covers that. The first real video measures how much of the limits one video uses, and the card's
"how many more fit" number comes from that measurement. We do not promise capacity up front.

## Non-goals

- No API-key fallback when a limit is hit (approach 2 was declined for now). Keep the existing API code path working,
  so switching back later stays possible. It just isn't the default and isn't advertised.
- No using several Claude accounts to get around limits.
- No change to TikTok, ElevenLabs, RunPod or rendering.

## Anti-goals (a failure even if it technically works)

- The owner ever has to copy, paste or store a token or key for Claude.
- Limits show up as red errors, failed videos, or the 3-failures circuit breaker tripping.
- A half-made video is thrown away because a limit hit mid-pipeline. It must resume from the stage it reached.
- The usage card shows invented precision. If the real % can't be read, it says "estimate" and shows the worker's own
  count.
- Secrets end up in the repo, in logs or in the doctor.sh output.

## Constraints

- Claude Code in headless mode (`claude -p`, `--output-format json`, `--json-schema <schema>` for structured output;
  the built-in WebSearch tool for research). The CLI is v2.1.x in this container; pin a version in the worker image.
- The worker image is `python:3.13-slim` (worker/Dockerfile), so it needs Node and the Claude Code CLI added. It runs
  as user `studio` (uid 10001). Claude's sign-in state must live on a named Docker volume so rebuilds keep it.
- The limits are shared with the owner's own Claude chat use on the same Pro account.
- Every current Claude call goes through `worker/studio/llm.py` (`structured`, `research`, `ping`). Callers live in
  `content.py`, `ops.py` and `cli.py`. Keep those signatures so callers don't change.
- Typed service problems already park jobs (`services.py`: `ServiceProblem` → jobs wait). A limit is a new kind of
  problem with a known resume time.
- The scheduler (`scheduler.py`) already has `posts_per_day` and `post_times` per channel. Pacing works by excluding
  evening slots while pacing is on, not by editing the channel settings.
- Spend tracking: subscription calls cost $0 in `spend`. Record usage (runs, tokens if reported) for the
  capacity estimate instead.
- Owner-facing text is plain English in the UI (the existing style). Talk to the owner in Roman Urdu.

## Approaches considered

1. **Claude Code headless on the VPS, signed in with the Pro account. (Picked.)** No key and no bill. Capacity is
   bounded by Pro limits, so it needs pacing and a usage card.
2. Subscription first, with an API key as backup when a limit hits. Never stops, but brings back the key and credit
   hassle the owner wants gone. Declined for now; possible later.
3. Console sign-in (`ant auth login`). No pasted key, but it still bills API credits, so the real problem stays.
   Dropped.

The owner was told: if they later want many more videos a day, upgrading to Max is simpler than adding an API key.

## Decided how (my calls, stated to the owner)

- **Sign-in:** a script, `infra/connect-claude.sh`, runs the Claude Code sign-in inside the worker container. Its
  state goes on a `claude-home` volume. The owner runs `sudo bash /opt/overthought-studio/src/infra/connect-claude.sh`
  (or whatever path install.sh uses), opens the printed link, signs in and pastes the code. The Settings page shows
  that exact command whenever Claude isn't connected. doctor.sh reports "Claude: connected (Pro)" or "not signed in",
  without printing any secret. A dashboard-only sign-in (no SSH) was considered and left out for now: it is more
  fragile. Revisit later.
- **Backend switch:** `llm.py` picks the backend. Subscription is the default when Claude Code is signed in. The
  existing SDK path is used only if an API key is saved and the owner turned it on (hidden setting; not built into the
  UI now).
- **Model:** the main writing work (script, fact-check verdicts, research) uses the strongest model the Pro plan gives
  Claude Code. Light work (scorecard, health check) uses a cheaper model to save limit. Make this one small table in
  `llm.py`.
- **Health check:** a cheap "is the CLI signed in" status check that does not use limit (e.g. the CLI's own auth
  status), not a real prompt.
- **Usage reading:** prefer the limit data Claude Code itself reports: utilisation and `resetsAt` for the five-hour
  and seven-day windows (the CLI's `/usage` shows these). The builder verifies the exact source on the real CLI. If it
  can't be read reliably, fall back to the worker's own count: runs and videos per window. Then label the card
  "estimate".
- **Where usage is stored:** the existing `services` row for `anthropic`, in its `details` JSON (five_hour %, reset,
  seven_day %, reset, plan, source = reported|estimate), plus a per-video usage note so "one video ≈ X% of the week"
  can be computed. No new table unless the builder finds `details` too cramped.
- **Pacing rule:** after each Claude run, project the weekly use. Pacing turns ON when
  `used% + (videos_left_this_week × %_per_video) > 95%`, where `videos_left_this_week` counts the remaining slots
  until the weekly reset. Pacing turns OFF when the weekly limit resets. While ON, `scheduler.slots()` drops each
  channel's later post time(s) (keeps the first = morning). Videos already in production or approved are never
  dropped.
- **Limit hit mid-run:** map the CLI's limit/usage error to a new `LimitReached(service, message, resume_at)`. Jobs
  park until `resume_at` (+ a couple of minutes) and keep the stage they reached. It does not count toward the
  circuit breaker. Status `limited`, shown as calm amber/neutral.

## Settled after the builder check (my calls unless marked)

- **Pacing means making fewer videos.** It does not mean making the same number and posting fewer, which would not
  save any limit. While pacing is on, the buffer counts only each channel's first post time per day. Production order
  is round-robin: no channel gets a second video in production while another active channel has none. No new link
  between a video and a slot is needed.
- **Videos that already exist are never lost or moved backwards.** A video that is already `scheduled` for an evening
  slot keeps that time. Videos that are `ready` (waiting for father's approval) or `approved` take the next free slot
  the scheduler offers. While pacing is on, that slot is a morning one.
- **Measuring cost per video:** `%_per_video` is the weekly-% rise across one video's Claude runs. Only runs tagged
  with that video's `video_id` count. It is a running average of the last 5 videos. Owner chat and other jobs add
  noise; the average absorbs some of it, and pacing aims at 95%, which leaves headroom. **Pacing stays off** until at
  least one video has been measured with *reported* numbers. In estimate mode (no reported %), pacing stays off and the
  card shows counts only. Limit hits are still handled by park-and-resume.
- **Live VPS before sign-in:** no Anthropic key was ever saved (the owner skipped keys). So after deploy, until
  `connect-claude.sh` runs, Claude shows "Not signed in" with the command to run, and nothing is billed. The SDK path
  runs only when an API key is saved **and** the hidden opt-in is set. A saved key alone never turns it on.
- **Sign-in mechanism:** use the documented `claude setup-token` (made for "CI pipelines and scripts"). The connect
  script captures the token itself and stores it as `CLAUDE_CODE_OAUTH_TOKEN` in the worker's env file (mode 600).
  The owner never sees or copies it. Don't use `--bare`, which ignores that variable.
- **Terms (owner told, see below):** Anthropic's docs allow a subscriber to sign the unmodified Claude Code into their
  own subscription, including for scripts. They also say advertised limits assume "ordinary, individual usage", and
  they don't define where scheduled automation crosses that line. Stay in bounds: only the owner's own use, never
  offered to others, pacing on, and no attempts to get around limits.

## Left to the builder

- The exact CLI flags (structured output, which tools to allow: only WebSearch/WebFetch for research and none for the
  rest, no file or shell tools), timeouts, and parsing citations out of research output.
- Where to install Node and the CLI in the Dockerfile, and pinning the version.
- The UI details of the card, inside the existing design system (`components/ui/primitives.tsx`, Progress bar,
  skeletons).
- Tests: fake the CLI with a stub script in `worker/tests/fakes.py` style. No real Claude calls in tests.
- Updating docs/SETUP.md, docs/BRAIN.md and the video-guide script line that says "keys bete se kahein" (only if cheap).
