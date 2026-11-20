# Final UI/UX audit and Roman Urdu video guide: implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Polish every dashboard screen (layout, loading, empty and error states), ship it live, then produce a
~9-minute Roman Urdu video guide recorded on a demo copy of the app.

**Architecture:**
- **Demo copy:** local Supabase (CLI and Docker), the real migrations, demo data seeded by a committed script, and the
  real dashboard built against it.
- **Audit:** a committed Playwright checker (`tools/demo/ui-check.cjs`) turns each finding into an assertion that
  fails before the fix and passes after it.
- **Guide:** a script file drives three stages:
  - edge-tts narration with sentence timings;
  - Playwright scene recordings with highlight boxes;
  - a Remotion composition, rendered to MP4 plus SRT.

**Tech Stack:** Next.js 15.5 / React 19 / Tailwind v4 dashboard; Python 3.13 (worker `studio.db`, `edge-tts`, pytest);
Playwright (pre-installed, global `require('playwright')`); Remotion; ffmpeg; Supabase CLI 2.x with Docker.

**Spec:** `docs/superpowers/specs/2026-11-20-audit-and-video-guide-design.md`

## Global Constraints

- Viewports to check: **375 px** (phone) and **1280 px** (laptop).
- Brand unchanged: charcoal `#111`, white ink, yellow `#FFD60A`.
- No new product features. No worker pipeline changes.
- Guide video:
  - 1920×1080, 30 fps, H.264 and AAC, **8–11 min**;
  - voice `ur-PK-AsadNeural` at rate `-8%`;
  - 0.4 s pause between sentences, 0.8 s between scenes;
  - subtitles in Roman Urdu, at least 48 px at 1080p, at most 2 lines, white on a translucent charcoal band;
  - no music.
- Narration is in Urdu script and subtitles are in Roman Urdu: **same sentence count per scene, mapped 1:1**.
- The father only watches and approves. For money, keys, the red bar or a forgotten password, the line is
  "bete se kahein".
- Publishing is taught as today's behaviour: draft mode, then tap Post in the TikTok app. One line mentions public
  posting after the TikTok audit.
- The demo copy is only ever local (`http://localhost:3000`, `owner@demo.local`). No real key, email or account data
  appears in any frame.
- Delivery: 1080p MP4 at or below about **120 MB**, 720p copy at or below about **60 MB**, an `.srt`, and a chapter
  list.
- edge-tts runs with `--proxy "$HTTPS_PROXY"` and `SSL_CERT_FILE=/root/.ccr/ca-bundle.crt`. Supabase CLI runs with
  `SUPABASE_INTERNAL_IMAGE_REGISTRY=docker.io`. Start Docker with `dockerd &` if `docker info` fails.
- Owner checkpoints, where work stops for the owner's "haan":
  1. the Roman Urdu script (Task 6);
  2. the chapter 1 draft plus the full narration audio (Task 9).
- Commit to `main` with the session attribution lines. Use GitHub MCP `push_files` if git push returns 403. Update
  `docs/BRAIN.md` after every task.

## Review Focus

1. **Real build vs demo build.** `.next` built against localhost must never reach the VPS. The VPS builds from
   source, so the risk is only a committed `.env`. Task 1 adds `tools/demo/*.env` to `.gitignore` and the ui-check
   asserts no `localhost` origin appears in the live CSP header.
2. **A subtitle drifts from the voice** when an Urdu sentence has no matching Roman line, for example when edge-tts
   splits on a comma the script didn't count. Task 7 makes `cues_from_boundaries` raise on a count mismatch, and the
   script uses only `۔ ؟ !` as sentence ends.
3. **Scene video shorter than its audio**, so the screen freezes or cuts early. Task 8 asserts each recorded clip is at
   least as long as its audio plus 0.8 s.
4. **Long titles or Urdu-looking channel names overflow on phone.** The demo seed includes one 90-character video title
   and one 60-character idea, and ui-check runs with them present.
5. **Reduced motion.** The new skeleton shimmer must stop under `prefers-reduced-motion`. Task 4's ui-check case emulates
   `reducedMotion: 'reduce'` and asserts the computed `animation-name` is `none`.

---

### Task 1: Demo copy and demo data

**Files:**
- Create: `tools/demo/README.md` (how to start and stop the demo copy, 10 lines).
- Create: `tools/demo/up.sh`, which:
  - starts dockerd if needed;
  - runs `supabase start` with exclusions `studio,imgproxy,edge-runtime,logflare,vector,supavisor,mailpit,postgres-meta`
    in a scratch project dir that copies `supabase/migrations`;
  - writes `tools/demo/demo.env`;
  - builds and starts the web app on port 3000.
- Create: `tools/demo/seed_demo.py`.
- Create: `tools/demo/test_seed_demo.py`.
- Modify: `.gitignore` to add `tools/demo/demo.env` and `tools/demo/.supabase/`.

**Interfaces:**
- Produces:
  - `seed_demo.run(render_dir: Path) -> dict[str, int]`, which returns counts per table. It is idempotent: it deletes
    rows with `experiment->>'demo' = 'true'` first.
  - The demo owner `owner@demo.local` with password `DemoPass!2026x`, created through `/setup` using token
    `demo-setup-token`.
  - The Playwright storage state at `tools/demo/.state.json`, git-ignored.
  - `seed_demo.set_red_bar(on: bool) -> None`, which sets the `elevenlabs` service to `out_of_credits` with message
    "ElevenLabs quota used up. Top up at elevenlabs.io → Subscription. Work resumes automatically." when on, and to
    `ok` when off.

- [ ] **Step 1: Write the failing test** `tools/demo/test_seed_demo.py::test_seed_has_full_lifecycle`. It skips
  unless `http://127.0.0.1:54321` answers. After `run()` it asserts:
  - the videos table has statuses ⊇ {`ready`, `scheduled`, `posted`, `failed`, `voice`, `rejected`};
  - at least 5 `posted` videos;
  - each posted video has at least 20 rows in `video_stats` (use the stats table name from `0001_init.sql`);
  - exactly 1 `ready` video with `approval == "pending"`;
  - the spend sum is greater than 0;
  - one `reports` row (use the table from `0001_init.sql`);
  - Overthought has a non-empty `strategy`;
  - at least 8 `events`;
  - at least 3 `jobs` in `queued` or `done`;
  - every service row is `ok`;
  - one video title is at least 90 characters long;
  - `run()` twice gives the same counts.
- [ ] **Step 2:** Run `python -m pytest -q tools/demo/test_seed_demo.py`. Expected: FAIL (no module).
- [ ] **Step 3: Implement `seed_demo.py`.**
  - Reuse `studio.db` with the `demo.env` values.
  - Two real ~70 s renders come from `worker/tests/fakes.py` (`install` plus `pipeline.produce`), uploaded to the local
    `videos` bucket. The other videos point at those two files.
  - Overthought is `status='active'`; the other channels stay paused.
  - Each video's `cost_usd` is between $0.50 and $1.50.
- [ ] **Step 4:** Run the test. Expected: PASS. Then run `NO_PROXY=localhost node tools/demo/ui-check.cjs --login-only`
  (from Task 2) once Task 2 exists. Until then, open `/videos` in Playwright and confirm the rows render.
- [ ] **Step 5:** Commit: `feat(demo): local demo copy with seeded lifecycle data`.

### Task 2: The UI checker and the first findings

**Files:**
- Create: `tools/demo/ui-check.cjs`.
- Modify: `apps/web/next.config.ts:13-14`, the CSP scheme.
- Modify, owned by the findings: `components/ui/tabs.tsx` (`SegmentedControl`), `components/charts/trend-chart.tsx`,
  `components/idea-bank.tsx`, `components/pipeline-board.tsx`.

**Interfaces:**
- Produces `node tools/demo/ui-check.cjs [--only <case>] [--login-only] [--shots <dir>]`, with exit code 0 on success.
- Every check prints one line: `PASS|FAIL <case> <viewport> <route> <detail>`.
- Later tasks add cases to the `CASES` array, using the signature
  `{ name, routes: string[], viewports: ('m'|'d')[], check: async (page) => string|null }`, where `null` means pass.

- [ ] **Step 1: Write the failing cases.** Routes are the 14 from the design audit plus `/videos/<ready id>`.
  - `no-h-overflow`: `document.documentElement.scrollWidth <= innerWidth` at 375 and 1280.
  - `scrollers-show-fade`: every element with `scrollWidth > clientWidth + 2` and `overflow-x: auto|scroll` has the
    class `scroll-fade-x`, at 375.
  - `empty-chart-no-axes`: on a channel with no stats, the `TrendChart` empty message is visible and no axis tick
    text is rendered.
  - `idea-title-width`: at 375, each idea title element in `/channels/overthought/ideas` is at least 180 px wide.
  - `pipeline-steps-visible`: at 375, each step label on `/` is fully inside its scroll container's visible box, or
    the container passes `scrollers-show-fade`.
  - `no-console-errors`: no console errors or page errors on any route.
  - `csp-ws-scheme`: the local CSP `connect-src` contains `ws://127.0.0.1:54321`.
- [ ] **Step 2:** Run `NO_PROXY=localhost,127.0.0.1 node tools/demo/ui-check.cjs`. Expected: FAIL lines for at least
  `scrollers-show-fade`, `empty-chart-no-axes`, `idea-title-width`, `pipeline-steps-visible`, `csp-ws-scheme` and
  `no-console-errors`. Record the full list in the ledger.
- [ ] **Step 3: Fix each finding.** Fixes:
  - **CSP:** derive the scheme from the Supabase URL, so `http:` gives `http://host` plus `ws://host` and `https:`
    gives `https://host` plus `wss://host`.
  - **`SegmentedControl`:** add `scroll-fade-x` to its scroller.
  - **`TrendChart`:** when every value is 0, render the empty message in place of the chart.
  - **`IdeaBank` row:** at width below `sm`, stack the score and controls under the title.
  - **`PipelineBoard`:** add `scroll-fade-x` and `scroll-snap`.
- [ ] **Step 4: Verify.** Run ui-check, `cd apps/web && npx tsc --noEmit && npm run lint && npm run build`. Expected:
  all PASS. Look at the 375 px screenshots of the changed pages.
- [ ] **Step 5:** Commit: `fix(web): phone layout of tabs, charts, idea bank, production line; CSP scheme`.

### Task 3: The full UX-skill audit

**Files:** whatever each finding owns, under `apps/web/components/**` and `apps/web/app/**`.

- [ ] **Step 1:** Run `vectorlab-ux-skills:ux-audit`, then `design:accessibility-review`, over the 375 and 1280
  screenshots (`--shots tools/demo/.shots/before`). Write each finding as one ledger line:
  `Task 3: finding <id>: <page> <issue>`.
- [ ] **Step 2: Add a check for each finding.** Where a finding can be measured, add a ui-check case and watch it
  FAIL. Measurable examples: contrast below 4.5:1, a touch target below 44 px, an input without a label, a button
  label from {OK, Submit, Proceed}, an icon button without `aria-label`. Where it can't be measured, write a ledger
  ruling with a before/after screenshot.
- [ ] **Step 3:** Fix in priority order: errors and blockers first, then phone layout, then copy.
- [ ] **Step 4: Verify.** Run ui-check, tsc, lint and build. Expected: all PASS. Save the after screenshots to
  `.shots/after`.
- [ ] **Step 5:** Commit per area: `fix(web): <area> from UX audit`.

### Task 4: Loading system

**Files:**
- Create: `loading.tsx` in each of `app/(app)/channels`, `app/(app)/channels/[slug]`, `app/(app)/videos`,
  `app/(app)/videos/[id]`, `app/(app)/analytics`, `app/(app)/reports`, `app/(app)/accounts`, `app/(app)/settings`
  and `app/(app)/logs`.
- Modify: `app/(app)/loading.tsx`, which becomes the overview shape.
- Modify: `components/ui/primitives.tsx` (`Skeleton`), and buttons that call `useAction().run` without using
  `pending`.

**Interfaces:**
- Consumes `Skeleton` from `@/components/ui/primitives`.
- Every `loading.tsx` root is `<div role="status" aria-busy="true">` with an sr-only "Loading…".

- [ ] **Step 1: Write the failing cases.**
  - `route-skeleton-shape`: for each route above, delay the RSC response by 1.5 s with `page.route` on requests that
    carry an `RSC` header, navigate from `/` by clicking the nav link, and assert a `[role=status][aria-busy=true]`
    appears within 300 ms and holds at least 2 `Skeleton` blocks.
  - `pending-buttons`: on `/channels/overthought`, click "Make a video now" with the server action delayed 1 s, and
    assert the button is `disabled` or `aria-busy` within 150 ms.
  - `reduced-motion-skeleton`: with `reducedMotion: 'reduce'`, `getComputedStyle(skeleton).animationName === 'none'`.
- [ ] **Step 2:** Run `ui-check --only route-skeleton-shape,pending-buttons,reduced-motion-skeleton`. Expected: FAIL.
- [ ] **Step 3: Implement.** One skeleton per route, mirroring that page's real grid: header, filter row, list or
  cards. Wire `pending` into every `useAction` button (the `disabled` and `aria-busy` attributes plus a 14 px inline
  spinner). Add a `motion-reduce:animate-none` class on `Skeleton`.
- [ ] **Step 4: Verify.** Run ui-check (all cases), tsc, lint and build. Expected: PASS.
- [ ] **Step 5:** Commit: `feat(web): page-shaped loading skeletons and pending buttons`.

### Task 5: Ship and verify live

- [ ] **Step 1:** Run `python -m pytest -q worker/tests`. Expected: all pass.
- [ ] **Step 2:** Push to `main` (git, or MCP `push_files` on a 403). Wait for the VPS auto-update: the
  `update.log` line appears within 10 minutes.
- [ ] **Step 3: Verify.** Run the live smoke from `scratchpad/live-smoke.mjs`: `/login` returns 200 on phone and
  desktop, the CSP still contains `wss://xkbgusqmdeocjwxaknjx.supabase.co`, and no `localhost` origin appears in it.
- [ ] **Step 4:** Update BRAIN §0 and §3 with the audit summary. Commit and push.
- [ ] **Step 5:** Send the owner a Roman Urdu message: what was fixed, with before and after phone screenshots of 3
  pages.

### Task 6: Guide script (owner checkpoint 1)

**Files:**
- Create: `tools/guide/script.yaml`.
- Create: `tools/guide/check_script.py` and `tools/guide/test_check_script.py`.

**Interfaces:**
- `script.yaml` schema is `chapters: [{id, title_roman, scenes: [scene]}]`. Each scene is
  `{id, route, viewport?: 'm'|'d' (default 'd'), actions: [{do: goto|click|hover|scroll|wait, target?: css,
  ms?: int}], highlight?: css, roman: [str], urdu: [str]}`. Chapter 10 scenes use `viewport: 'm'`.
- Produces `check_script.load(path) -> dict`, which raises `ValueError(scene_id)` when `len(roman) != len(urdu)`, when
  any Urdu sentence lacks an end mark in `۔؟!`, or when a Roman line is over 84 characters, since 2 lines of about
  42 characters fit.

- [ ] **Step 1: Write the failing tests:** `test_count_mismatch_raises`, `test_missing_end_mark_raises`,
  `test_long_roman_line_raises`, and `test_real_script_is_valid` (loads `script.yaml`).
- [ ] **Step 2:** Run `python -m pytest -q tools/guide/test_check_script.py`. Expected: FAIL.
- [ ] **Step 3:** Implement `check_script.py`. Write `script.yaml` for the 10 chapters in the design, about 1,150
  spoken words in total, with the selectors taken from the demo copy.
- [ ] **Step 4:** Run the tests. Expected: PASS. Export the Roman Urdu text as `scratchpad/guide/script-roman.md`
  (chapter headings plus lines).
- [ ] **Step 5:** Commit: `feat(guide): Roman Urdu / Urdu script with scene actions`. **Send `script-roman.md` to the
  owner and stop until they say "haan" or send changes.** Apply the changes, re-run the tests, and commit.

### Task 7: Narration and subtitles

**Files:**
- Create: `tools/guide/tts.py`, `tools/guide/srt.py` and `tools/guide/test_tts_srt.py`.

**Interfaces:**
- `Cue = dataclass(start: float, end: float, roman: str)`.
- `cues_from_boundaries(bounds: list[tuple[float, float]], roman: list[str], offset: float) -> list[Cue]`. It
  raises `ValueError` when the lengths differ. `bounds` are the per-sentence (start, end) pairs in seconds.
- `synthesize_scene(scene: dict, out_dir: Path) -> tuple[Path, list[Cue], float]` returns the mp3 path, the cues
  relative to the scene start, and the duration.
  - It runs edge-tts once per Urdu sentence, with voice `ur-PK-AsadNeural` and rate `-8%`.
  - It joins the sentences with 0.4 s of silence and adds 0.8 s at the end of the scene.
  - Each sentence's own duration gives its bounds, so the timings are exact with no boundary parsing.
- `to_srt(cues: list[Cue]) -> str`, with standard `HH:MM:SS,mmm` timestamps and 1-based indices.
- `build_all(script_path, out_dir) -> Path` writes `narration.json`, which maps scene id to mp3, cues and duration.

- [ ] **Step 1: Write the failing tests.**
  - `test_cues_offset_and_count`: bounds `[(0, 2.0), (2.4, 5.1)]` with offset `10` give starts `[10.0, 12.4]`.
  - `test_cues_mismatch_raises`.
  - `test_srt_format`: the first block is `"1\n00:00:10,000 --> 00:00:12,000\n<line>\n"`.
- [ ] **Step 2:** Run `python -m pytest -q tools/guide/test_tts_srt.py`. Expected: FAIL.
- [ ] **Step 3:** Implement the module.
- [ ] **Step 4:** Run the tests. Expected: PASS. Then run `python tools/guide/tts.py build` and check that the total
  narration is 8–11 min (sum of durations).
- [ ] **Step 5:** Commit: `feat(guide): edge-tts narration with exact sentence cues`.

### Task 8: Scene recorder

**Files:**
- Create: `tools/guide/record.cjs`.

**Interfaces:**
- Consumes `narration.json` (Task 7), `script.yaml` (Task 6) and `tools/demo/.state.json` (Task 1).
- `node tools/guide/record.cjs [--chapter <id>]` writes `scratchpad/guide/clips/<scene>.webm` and
  `clips/<scene>.json` = `{duration, box: {x, y, w, h} | null, viewport: {w: 1920, h: 1080}}`.
- Each scene:
  - opens a fresh context at 1920×1080 with `recordVideo`, or at 390×844 when `viewport: 'm'`; the clip JSON then
    has `viewport: {w: 390, h: 844}`, and Task 9's `ScreenScene` shows it centred in a rounded phone frame on charcoal;
  - injects a 22 px yellow-ringed cursor dot that follows mouse events;
  - spreads its actions across the scene's audio duration (each action gets about duration / actions, at least 600 ms);
  - moves the mouse to a click target over 500 ms;
  - captures the `highlight` element's box after the actions run.
- The red-bar scene calls `seed_demo.set_red_bar(True)` before it and `False` after it, through a small Python CLI
  hook: `python tools/demo/seed_demo.py red-bar on|off`.

- [ ] **Step 1:** Run `node tools/guide/record.cjs --chapter 1`. Expected: it fails because the module is missing.
- [ ] **Step 2:** Implement the recorder.
- [ ] **Step 3: Verify.** For every chapter 1 scene, `ffprobe` duration is at least the audio duration plus 0.8 s.
  Every `box` with a `highlight` is non-null and inside 1920×1080. Look at 3 frames.
- [ ] **Step 4:** Commit: `feat(guide): Playwright scene recorder with cursor and highlight boxes`.

### Task 9: Remotion composition, then chapter 1 draft (owner checkpoint 2)

**Files:**
- Create: the `tools/guide/video/` Remotion project (follow `remotion:remotion-create`, then
  `remotion-best-practices`).
- Create: `tools/guide/video/src/manifest.ts`, which loads `manifest.json` built from `narration.json` plus the clip
  JSONs.
- Create: `tools/guide/build_manifest.py`.

**Interfaces:**
- `build_manifest.py` writes `public/manifest.json` = `{fps: 30, chapters: [{id, title, scenes: [{clip, audio, cues,
  box, durationInFrames}]}]}`. Clips and audio are copied into `public/`.
- Compositions:
  - `Guide`: all chapters, 1920×1080, 30 fps.
  - `Chapter`: props `{chapterId}`.
- Components:
  - `TitleCard`: 2.5 s, charcoal background, chapter number and Roman title in Kalam and Caveat from
    `assets/style/fonts`.
  - `ScreenScene`: the clip as `<OffthreadVideo>`. With a box, it scales smoothly to 1.35× centred on the box from
    about 20% to 80% of the scene, eased with `spring`, and shows a yellow `#FFD60A` 4 px rounded ring that pulses
    gently.
  - `Subtitles`: at least 48 px, white on `rgba(17,17,17,0.78)`, 2 lines at most, timed by the cues.

- [ ] **Step 1: Write the failing test.** `tools/guide/test_manifest.py::test_frames_match_audio`: each scene's
  `durationInFrames == ceil(audio_duration * 30)`, and the cue times are inside the scene.
- [ ] **Step 2:** Run it. Expected: FAIL.
- [ ] **Step 3:** Implement `build_manifest.py` and the Remotion components.
- [ ] **Step 4: Verify.** The test passes. Render `Chapter` for chapter 1 to `scratchpad/guide/draft-ch1.mp4`.
  `ffprobe` shows 1920×1080, 30 fps, h264 and aac. Look at frames from the title card, the zoom and a subtitle.
- [ ] **Step 5:** Commit: `feat(guide): Remotion composition`. Concatenate all narration mp3s into
  `scratchpad/guide/narration-full.mp3`. **Send `draft-ch1.mp4` and `narration-full.mp3` to the owner and stop for
  "haan" or changes.** Apply the changes (script or voice), then re-run Tasks 7–9 for the affected scenes.

### Task 10: Full render, delivery and cleanup

- [ ] **Step 1:** Record all chapters, then render `Guide` to `scratchpad/guide/overthought-guide-ur-master.mp4`.
- [ ] **Step 2: Encode the deliverables.**
  - 1080p: `ffmpeg -c:v libx264 -preset slow -crf 26 -tune stillimage -c:a aac -b:a 96k`. Target at or below 120 MB;
    raise CRF by 2 until it fits.
  - 720p: `-vf scale=1280:720 -crf 28`, at or below 60 MB.
  - `overthought-guide-ur.srt` from all cues, with offsets after the title cards.
  - `chapters.txt` in the form `00:00 Studio kya hai`.
- [ ] **Step 3: Verify.**
  - The duration is 8–11 min.
  - Spot-check 10 subtitle cues against the audio (±0.3 s) by extracting frames at cue start plus 0.2 s.
  - Grep the SRT and step through 20 sampled frames for `@`, `sk-` and `getgrowthnexus`. Only `owner@demo.local` is
    allowed.
- [ ] **Step 4:** Send the two MP4s, the SRT and the chapters to the owner with a Roman Urdu note.
- [ ] **Step 5:** Final whole-branch review (executing-plans). Update BRAIN, commit and push. Stop the demo copy
  (`supabase stop`, kill the web server). Remind the owner to delete the Supabase `claude-demo` token if they haven't.
