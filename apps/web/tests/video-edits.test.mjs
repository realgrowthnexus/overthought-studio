// node --experimental-strip-types --test tests/
import { test } from "node:test";
import assert from "node:assert/strict";
import { postTimeError, scheduleChange, coverError } from "../lib/video-edits.ts";
import { parseAction, actionNeeds, ASSISTANT_ACTIONS } from "../lib/assistant-actions.ts";

const NOW = new Date("2026-11-24T12:00:00Z");

test("post time must be in the future and within 60 days", () => {
  assert.equal(postTimeError("2026-11-24T12:30:00Z", NOW), null);
  assert.match(postTimeError("2026-11-24T11:00:00Z", NOW), /future/);
  assert.match(postTimeError("2027-03-01T00:00:00Z", NOW), /60 days/);
  assert.match(postTimeError("not a date", NOW), /date/);
});

test("setting a time on a ready video approves and locks it", () => {
  const u = scheduleChange("ready", "2026-11-25T09:00:00Z", NOW);
  assert.equal(u.status, "approved");
  assert.equal(u.approval, "approved");
  assert.equal(u.schedule_locked, true);
  assert.equal(u.scheduled_for, "2026-11-25T09:00:00Z");
  assert.ok(u.approved_at);
});

test("setting a time on a scheduled video keeps the status and locks it", () => {
  const u = scheduleChange("scheduled", "2026-11-25T09:00:00Z", NOW);
  assert.equal(u.status, undefined);
  assert.equal(u.schedule_locked, true);
});

test("clearing unlocks and sends a scheduled video back to the slot queue", () => {
  assert.deepEqual(scheduleChange("scheduled", null, NOW), { scheduled_for: null, schedule_locked: false, status: "approved" });
  assert.deepEqual(scheduleChange("approved", null, NOW), { scheduled_for: null, schedule_locked: false });
});

test("only ready, approved or scheduled videos can get a post time", () => {
  assert.throws(() => scheduleChange("rendering", "2026-11-25T09:00:00Z", NOW), /finished/);
});

test("cover frame must be inside the video", () => {
  assert.equal(coverError(1500, 80), null);
  assert.match(coverError(-1, 80), /inside/);
  assert.match(coverError(90_000, 80), /inside/);
});

test("assistant actions: whitelist and required ids", () => {
  assert.ok(ASSISTANT_ACTIONS.includes("approve_video"));
  assert.equal(actionNeeds("pause_studio"), null);
  assert.equal(actionNeeds("retry_job"), "job");
  assert.equal(parseAction({ type: "delete_everything", label: "x" }), null);
  assert.equal(parseAction({ type: "approve_video", label: "x" }), null);   // missing video_id
  const ok = parseAction({ type: "approve_video", label: "Approve", video_id: "3f2b1c9e-1d2a-4b5c-8d9e-0a1b2c3d4e5f" });
  assert.equal(ok.type, "approve_video");
});
