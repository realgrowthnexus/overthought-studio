// node --experimental-strip-types --test tests/   (no test framework needed)
import { test } from "node:test";
import assert from "node:assert/strict";
import { claudeView } from "../lib/claude-usage.ts";

const NOW = new Date("2026-11-20T15:00:00Z");
const svc = (status, details = {}, message = null) => ({ name: "anthropic", status, message, details });

test("not signed in when the service is unconfigured or missing", () => {
  assert.equal(claudeView(undefined, NOW).state, "not_signed_in");
  assert.equal(claudeView(svc("unconfigured"), NOW).state, "not_signed_in");
});

test("connected with both windows, reset labels and the capacity estimate", () => {
  const v = claudeView(svc("ok", {
    backend: "subscription", source: "reported", per_video_pct: 2, videos_left: 40, week_videos: 18,
    five_hour: { pct: 78.4, resets_at: "2026-11-20T20:40:00+00:00" },
    seven_day: { pct: 31, resets_at: "2026-11-23T14:00:00+00:00" },
  }), NOW);
  assert.equal(v.state, "connected");
  assert.equal(v.fiveHour.pct, 78);
  assert.match(v.fiveHour.resets, /3:40\s?PM/);
  assert.equal(v.week.pct, 31);
  assert.equal(v.estimate, false);
  assert.equal(v.summary, "This week: 18 videos made · about 40 more fit");
});

test("an active limit is calm and says when work resumes", () => {
  const v = claudeView(svc("warning", { limited: true, resume_at: "2026-11-20T20:40:00+00:00" }), NOW);
  assert.equal(v.state, "limited");
  assert.match(v.headline, /resumes .*3:40\s?PM/);
});

test("a limit whose reset time passed is no longer shown as limited", () => {
  const v = claudeView(svc("warning", { limited: true, resume_at: "2026-11-20T14:00:00+00:00" }), NOW);
  assert.notEqual(v.state, "limited");
});

test("estimate readings are labelled and give no capacity promise", () => {
  const v = claudeView(svc("ok", { source: "estimate", week_videos: 3, seven_day: { pct: 10, resets_at: null } }), NOW);
  assert.equal(v.estimate, true);
  assert.equal(v.summary, "This week: 3 videos made");
});

test("pacing is surfaced", () => {
  const v = claudeView(svc("ok", { pacing: true, source: "reported" }), NOW);
  assert.equal(v.pacing, true);
});

test("api-key mode is named as such", () => {
  assert.equal(claudeView(svc("ok", { backend: "api" }), NOW).state, "api");
});

import { isClaudePause } from "../lib/claude-usage.ts";

test("a Claude limit pause is recognised so it can be shown calmly, other holds are not", () => {
  assert.equal(isClaudePause("Claude limit reached — resumes at Fri 3:40 PM"), true);
  assert.equal(isClaudePause("Claude limit reached — resumes at Fri 3:40 PM — raise it in Settings"), true);
  assert.equal(isClaudePause("Elevenlabs: quota used up"), false);
  assert.equal(isClaudePause(null), false);
});

test("no readable limits: the card says so plainly instead of waiting forever", () => {
  const v = claudeView({ status: "ok", message: null, details: { backend: "subscription", source: "estimate", week_videos: 4 } }, new Date());
  assert.equal(v.estimate, true);
  assert.equal(v.limitsNote, "Claude doesn't share the limit numbers for this sign-in, so the studio counts videos instead.");
});
