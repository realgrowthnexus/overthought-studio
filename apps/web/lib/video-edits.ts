// Pure rules for the video page edits (shared by server actions and tests).

const DAY = 86_400_000;
export const EDITABLE_POST_TIME = ["ready", "approved", "scheduled"] as const;

/** null when the time is fine, else a plain message. */
export function postTimeError(iso: string, now: Date = new Date()): string | null {
  const t = new Date(iso).getTime();
  if (!iso || Number.isNaN(t)) return "That isn't a valid date and time.";
  if (t <= now.getTime() + 60_000) return "Pick a time in the future.";
  if (t > now.getTime() + 60 * DAY) return "Pick a time within the next 60 days.";
  return null;
}

export type ScheduleUpdate = {
  scheduled_for: string | null; schedule_locked: boolean;
  status?: "approved"; approval?: "approved"; approved_at?: string; rejection_note?: null;
};

/** The row change for setting (or clearing) an owner-chosen post time. Throws a plain message when not allowed. */
export function scheduleChange(status: string, iso: string | null, now: Date = new Date()): ScheduleUpdate {
  if (!(EDITABLE_POST_TIME as readonly string[]).includes(status)) {
    throw new Error("Only finished videos (ready, approved or scheduled) can get a post time.");
  }
  if (iso === null) {
    return status === "scheduled"
      ? { scheduled_for: null, schedule_locked: false, status: "approved" }
      : { scheduled_for: null, schedule_locked: false };
  }
  const err = postTimeError(iso, now);
  if (err) throw new Error(err);
  const when = new Date(iso).toISOString().replace(".000Z", "Z");
  if (status === "ready") {
    return { scheduled_for: when, schedule_locked: true, status: "approved", approval: "approved",
             approved_at: now.toISOString(), rejection_note: null };
  }
  return { scheduled_for: when, schedule_locked: true };
}

/** Cover frame (ms) must be inside the video (seconds). */
export function coverError(ms: number, durationS: number | null): string | null {
  if (!Number.isFinite(ms) || ms < 0 || (durationS != null && ms > durationS * 1000)) {
    return "Pick a frame inside the video.";
  }
  return null;
}
