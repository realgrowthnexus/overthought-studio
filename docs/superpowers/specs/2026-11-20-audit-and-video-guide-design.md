# Final UI/UX check and Roman Urdu video guide: design

Date: 2026-11-20. Owner request, in their words: "final check verify, ui ux improvision, loading system, sab kuch dekh lo
fix kro … roman urdu nice smooth voiceover sath smooth video guide … pury app ka use … screens along subtitles".

## Intent and the why
The dashboard is live at `https://studio.getgrowthnexus.com`. The owner wants two things:
1. **Final polish.** Every screen should be checked and fixed before daily use: UI/UX, loading states and errors.
2. **A video guide** that teaches the whole app. The owner will watch it and use it to explain the app to **their
   father**. The father is older and not technical, and Roman Urdu or simple Urdu is his language.

**The father's role (owner, 2026-11-20): he only watches and approves videos.** Money, keys and top-ups stay with the
owner. When something needs money, the father's step is "tell your son".

Success means the father can watch the guide once and then:
- open the dashboard;
- read the red bar;
- approve a video;
- understand what each page is for.

## Goals
- G1: Every dashboard page works and looks right at 375 px (phone) and 1280 px (laptop). This covers layout, loading
  states, empty states, error states, focus and labels.
- G2: Loading feels immediate and specific. Each page group shows a skeleton shaped like that page. Buttons show
  their own pending state. No spinner appears for actions under 100 ms.
- G3: A video guide in 1920×1080 MP4 (H.264 + AAC, 30 fps), about **8–10 minutes** long:
  - voice in Urdu, read by the free Microsoft Edge neural voice **ur-PK-AsadNeural** (owner chose it after hearing
    samples), at rate −8%;
  - **Roman Urdu subtitles** on screen, large and easy to read;
  - screen recordings with each click visible, plus a zoom and yellow highlight on the thing being explained;
  - a title card at the start of each chapter.
- G4: The fixes ship to the live site, through a push to `main` and the VPS auto-update.

## Non-goals
- No new product features and no brand redesign. The charcoal, white and yellow brand stays.
- No changes to the worker pipeline.
- No real API keys, no real TikTok account and no owner data in the guide.
- No paid text-to-speech. The owner said: free TTS.

## Anti-goals: failure even if it "works"
- A guide that is too fast, too technical, or full of English jargon for the father.
- A guide that shows anything secret: real keys, real email, the real account.
- A guide recorded before the fixes, so it no longer matches the live UI.
- Fixes that break the live site. Every change passes `tsc`, lint, build, the worker tests and a screenshot pass
  before it is pushed.

## Constraints
- Claude cannot log into the owner's real account. A safety check refused that. Everything runs on a **local demo
  copy**:
  - Supabase CLI local stack, images from `docker.io` (`SUPABASE_INTERNAL_IMAGE_REGISTRY=docker.io`; ECR is
    rate-limited here);
  - migrations `supabase/migrations/0001–0003`;
  - the dashboard built against it at `http://localhost:3000`;
  - demo owner `owner@demo.local`.
- Text-to-speech uses `edge-tts` through the session proxy. Pass `--proxy` and `SSL_CERT_FILE=/root/.ccr/ca-bundle.crt`.
  The host `speech.platform.bing.com` is allowed.
- The voice is given text in **Urdu script**, because Roman Urdu read by TTS sounds wrong. Subtitles are Roman Urdu,
  so the two scripts map **sentence to sentence**, not word to word.
- Git push from this cloud session sometimes returns 403. If it does, use the GitHub MCP `push_files` to `main`.
- Owner messages are in Roman Urdu or simple English. The owner is not a developer.

## Approaches considered (owner picked A)
- **A. Scripted screen recording, voice and an edited video (chosen).** Playwright drives the demo copy, Remotion
  composes the video with zooms, highlights, title cards and subtitles. It is the clearest for a non-technical viewer
  and can be re-rendered when the UI changes.
- B. Screenshots with voice, as a slideshow. Faster, but no clicks or motion, so it is harder for the father to follow.
- C. The owner records the screen and I add voice and subtitles. It costs the owner's time, and the real account is
  empty.

Voice: ElevenLabs was offered at $1–2. The owner chose free TTS, then picked **Asad** over Uzma after samples.

## Part 1: audit and fixes

### Demo data
Committed script: `tools/demo/seed_demo.py`, reusing the worker's `studio.db` against the local stack. It is
idempotent, so it re-runs cleanly. It seeds:
- the 5 seeded channels, with Overthought active and the rest paused;
- **about 8 videos** across the lifecycle:
  - 1 ready and waiting for approval;
  - 1 approved and scheduled;
  - 2 posted, with 30 days of stats;
  - 1 failed, with a readable error;
  - 1 in production at the "voice" stage;
  - 1 rejected.

  Two are real 70 s renders made offline with the worker's fake services (`worker/tests/fakes.py`). The others reuse
  those files.
- one weekly report and a strategy for Overthought;
- recent events, and a work queue with a few jobs;
- service statuses all `ok`, plus a toggle that sets `elevenlabs` to `out_of_credits` to show the red bar.
- **Builder's call:** if the 30-day analytics series looks empty with 2 posted videos, add posted videos (about 5) so
  the charts have a shape. The video count is not fixed.
- **Builder's call:** `cost_usd` and `cost_breakdown` on demo videos get plausible values ($0.50–$1.50) so the
  overview spend card is not $0.00.
- **Builder's call:** the "in production at voice" video is static: status `voice`, progress 70, a stage detail.
  The worker is not run in the demo, and the guide narrates the production line rather than showing it move live.

### Audit method
Run the installed UX skills over every route at 375 and 1280 px, with screenshots before and after. Skills:
- `vectorlab-ux-skills:ux-audit` (umbrella), plus `viewports`, `loaders`, `empty-states`, `errors`, `labels`,
  `verbs` and `keyboard`;
- `design:accessibility-review` for WCAG AA.

Known findings from the first pass, all on phone:
- tab rows (chart metric tabs, channel tabs) are clipped at the edge with no sign they scroll;
- the empty-chart message overlaps the axis lines;
- Idea bank rows are cramped: the title squeezed by the score and controls;
- the overview "Production line" steps are cut off;
- locally, the CSP blocks the realtime websocket, because `next.config.ts` hard-codes `https`/`wss`. Derive the
  scheme from `NEXT_PUBLIC_SUPABASE_URL` so `http` maps to `ws`. Production is unaffected.

### Loading system
- One `loading.tsx` per route group (overview, channels list, channel detail, videos, video detail, analytics,
  reports, accounts, settings, logs), shaped like that page and built from the existing `Skeleton` primitive.
- Every mutating button uses a pending state through `use-action.ts`. Inline toggles are optimistic.
- Respect `prefers-reduced-motion`.

### Acceptance
- Every finding is fixed or recorded as a ruling.
- `npx tsc --noEmit`, `npm run lint`, `npm run build` and the worker `pytest` all pass.
- After screenshots: no horizontal overflow at 375 px, no clipped controls, no console errors except the known
  local-only cases.
- Pushed to `main`; `doctor.sh` or the live smoke shows the new build is served.

## Part 2: the video guide

### Chapters
Roughly 30–80 s each, about 9 minutes in total:
1. **Studio kya hai.** What it does by itself, and what you do: watch and approve. Money and keys are your son's job.
2. **Login.** The address, email and password. If you forget the password: "bete se kahein", and the owner resets it
   in Supabase. The app gets no forgot-password feature (owner, 2026-11-20).
3. **Overview.** The cards, the production line, "waiting for review", and the **red bar**: what it says, and that
   the fix is to tell your son.
4. **Channels.** The 5 channels, the on/off switch, the channel page (Make a video now, Research ideas), the Idea bank.
5. **Video approve karna.** The Videos page, filters, opening a video, play, approve, reject, regenerate.
6. **Publish aur TikTok.** Teach **today's** behaviour: posting mode is `draft`, so an approved video arrives as a
   draft in the TikTok app's inbox and you tap Post there. One line says public auto-posting comes after TikTok's
   audit. The TikTok accounts page is covered in short. (Builder's call, from BRAIN §1 and §6.)
7. **Analytics aur weekly report.** What the numbers mean and where the weekly report appears.
8. **Settings, in short.** "Yeh bete ka hissa hai." Show only where keys and budgets live. About 30 s.
9. **Roz ka kaam.** A 1-minute daily routine: open the app, approve the waiting videos, glance at the red bar. And "jab
   kuch ruk jaye": read the red bar, tell your son; after his top-up the work resumes by itself.
10. **Mobile.** The same app on a phone, with the bottom tabs and the More menu. This chapter is short.

### Script
- File: `tools/guide/script.yaml`, committed.
- Each scene holds:
  - the Roman Urdu subtitle sentences;
  - the matching Urdu-script narration sentences (same count, 1:1);
  - the actions to perform (goto, click, scroll, hover, with a selector);
  - the zoom or highlight target selectors.
- Vocabulary: everyday Urdu. Common English UI words that appear on screen stay as they are, for example "Settings",
  "Approve" and "Channel". The narration names the exact button text the father will see.
- **Approval checkpoint:** the owner reads the Roman Urdu script and approves it before any rendering.

### Production pipeline
All of it lives in `tools/guide/` and can be reproduced.
1. **TTS.**
   - `edge-tts` renders one mp3 per scene, with sentence boundary events.
   - Each subtitle line gets its own start and end time.
   - Asad voice, rate −8%.
   - A 0.4 s pause between sentences and 0.8 s between scenes.
2. **Recording.**
   - Playwright runs at 1920×1080 with `recordVideo` against the demo copy, logged in from saved storage state.
   - Each action waits so the screen matches the narration timing: the scene length comes from its audio length.
   - A visible cursor dot is injected, because headless recordings show no cursor.
   - Playwright saves the bounding box of each highlight target per scene to JSON.
3. **Composition.**
   - Remotion, using the installed `remotion:*` skills.
   - Per scene: the screen clip, a smooth zoom and pan to the target box when one is set, a yellow rounded
     highlight ring with a gentle pulse, and the subtitle bar.
   - Chapter title cards use the brand charcoal background with Kalam and Caveat fonts from `assets/`.
   - Subtitles: Roman Urdu, at least 48 px at 1080p, white on a translucent charcoal band, at most 2 lines.
   - **Builder's call:** if the screen recordings come out at a lower fps, Remotion re-times them to 30 fps.
4. **Output.** These live in the scratchpad and are sent to the owner; they are not committed:
   - `overthought-guide-ur.mp4`;
   - `overthought-guide-ur.srt` with the Roman Urdu subtitles;
   - a chapter list with timestamps, as text the owner can paste into a description.
5. **Draft checkpoint:** render chapter 1 alone first, about 1 minute, and send it to the owner to approve pace,
   voice and look. Send the **full narration audio** (all chapters, mp3) at the same time, so the Urdu-script text
   the owner never reads is still heard and checked before the full render. Then render the full guide.
6. **Delivery** (builder's call):
   - one 1080p file for the laptop, encoded to stay at or below about 120 MB (screen content compresses well);
   - a 720p phone copy at or below about 60 MB, for WhatsApp;
   - the chapter timestamps as text.

### Acceptance
- The duration is 8–11 min, at 1920×1080, 30 fps, H.264 and AAC.
- Subtitle timing stays within ±0.3 s of each spoken sentence. Spot-check 10 sentences.
- No frame shows a real key, the real email or the real domain's data.
- The owner approves the chapter 1 draft before the full render.

## Left to the builder
- The exact Remotion version and project layout under `tools/guide/`.
- The exact skeleton shapes per page, and the order the audit fixes ship in.
- The demo data's exact titles and numbers. They should be plausible and fit the Overthought niche.
- Music: off by default, because voice clarity comes first for the father.

## Order
1. Part 1 (audit and fixes), deployed.
2. Part 2 (guide script, then the owner approves the script, then chapter 1 draft, then the owner approves it, then
   the full render).
