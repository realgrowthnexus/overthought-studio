// The assistant's action whitelist (mirrors worker/studio/assistant.py NEEDS). Pure, shared by the runner and tests.

export const ASSISTANT_ACTIONS = [
  "pause_channel", "resume_channel", "pause_studio", "resume_studio", "make_video", "retry_job", "cancel_job",
  "approve_video", "reject_video", "publish_video", "set_post_time", "clear_post_time",
] as const;
export type AssistantActionType = (typeof ASSISTANT_ACTIONS)[number];

export type AssistantAction = {
  type: AssistantActionType; label: string; channel_id?: string; video_id?: string; job_id?: number | string;
  when_iso?: string;
};

const NEEDS: Record<AssistantActionType, "channel" | "video" | "job" | null> = {
  pause_channel: "channel", resume_channel: "channel", make_video: "channel", pause_studio: null, resume_studio: null,
  retry_job: "job", cancel_job: "job", approve_video: "video", reject_video: "video", publish_video: "video",
  set_post_time: "video", clear_post_time: "video",
};
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export function actionNeeds(type: AssistantActionType) {
  return NEEDS[type];
}

/** A stored action, checked again before it may run (the worker already filtered it; never trust it blindly). */
export function parseAction(raw: unknown): AssistantAction | null {
  if (!raw || typeof raw !== "object") return null;
  const a = raw as Record<string, unknown>;
  if (typeof a.type !== "string" || !(ASSISTANT_ACTIONS as readonly string[]).includes(a.type)) return null;
  const type = a.type as AssistantActionType;
  const label = typeof a.label === "string" ? a.label.slice(0, 120) : type;
  const need = NEEDS[type];
  const out: AssistantAction = { type, label };
  if (need === "channel") { if (typeof a.channel_id !== "string" || !UUID.test(a.channel_id)) return null; out.channel_id = a.channel_id; }
  if (need === "video") { if (typeof a.video_id !== "string" || !UUID.test(a.video_id)) return null; out.video_id = a.video_id; }
  if (need === "job") {
    const id = Number(a.job_id);
    if (!Number.isInteger(id) || id <= 0) return null;
    out.job_id = id;
  }
  if (type === "set_post_time") { if (typeof a.when_iso !== "string") return null; out.when_iso = a.when_iso; }
  return out;
}
