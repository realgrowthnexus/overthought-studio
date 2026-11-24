"use server";
import { revalidatePath } from "next/cache";
import { z } from "zod";
import { requireAdmin } from "@/lib/auth";
import { serviceClient } from "@/lib/supabase/service";
import { encrypt, hasMasterKey } from "@/lib/crypto";
import { SECRET_KEYS, type GlobalSettings } from "@/lib/types";
import { DEFAULT_SETTINGS } from "@/lib/data";

export type ActionResult<T = undefined> = { ok: true; data?: T; message?: string } | { ok: false; error: string };

const uuid = z.string().uuid();

async function guard<T>(fn: () => Promise<ActionResult<T>>): Promise<ActionResult<T>> {
  try {
    await requireAdmin();
    return await fn();
  } catch (e) {
    if (e instanceof z.ZodError) return { ok: false, error: e.issues.map((i) => `${i.path.join(".") || "value"}: ${i.message}`).join("; ") };
    return { ok: false, error: e instanceof Error ? e.message : "Something went wrong." };
  }
}

async function logEvent(message: string, extra: { channel_id?: string | null; video_id?: string | null; level?: string; data?: unknown } = {}) {
  await serviceClient().from("events").insert({
    scope: "dashboard", level: extra.level ?? "info", message,
    channel_id: extra.channel_id ?? null, video_id: extra.video_id ?? null, data: extra.data ?? null,
  });
}

function fail(error: { message: string } | null) {
  if (error) throw new Error(error.message);
}

/* ---------------- Jobs ---------------- */

// Job types the dashboard may enqueue. import_stats only goes through importStats() (it needs an uploaded file);
// check_publish is enqueued by the worker itself.
const JOB_TYPES = [
  "plan_channel", "produce_video", "research_ideas", "publish_video", "sync_stats",
  "weekly_review", "health_check", "refresh_tokens", "backup_db", "cleanup_storage",
] as const;
type JobType = (typeof JOB_TYPES)[number];

const JOB_LABEL: Record<JobType, string> = {
  plan_channel: "Video queued", produce_video: "Regeneration queued", research_ideas: "Idea research queued",
  publish_video: "Publish queued", sync_stats: "Stats sync queued",
  weekly_review: "Weekly review queued", health_check: "Health check queued",
  refresh_tokens: "Token refresh queued", backup_db: "Backup queued", cleanup_storage: "Cleanup queued",
};

// Must match worker/studio/pipeline.py STAGES.
const PRODUCTION_STAGES = ["research", "script", "factcheck", "visuals", "voice", "render"] as const;

/** Per-type payload shape (strict: unknown keys are rejected) and which target id it needs. */
const JOB_SPEC: Record<JobType, { target: "channel" | "video" | "optional_channel" | "none"; payload: z.ZodType<Record<string, unknown>> }> = {
  plan_channel: { target: "channel", payload: z.strictObject({ channel_id: uuid, force: z.boolean().optional() }) },
  research_ideas: { target: "channel", payload: z.strictObject({ channel_id: uuid, count: z.number().int().min(1).max(30).optional() }) },
  produce_video: { target: "video", payload: z.strictObject({ video_id: uuid, from_stage: z.enum(PRODUCTION_STAGES).optional() }) },
  publish_video: { target: "video", payload: z.strictObject({ video_id: uuid }) },
  sync_stats: { target: "optional_channel", payload: z.strictObject({ channel_id: uuid.optional() }) },
  weekly_review: { target: "optional_channel", payload: z.strictObject({ channel_id: uuid.optional() }) },
  health_check: { target: "none", payload: z.strictObject({}) },
  refresh_tokens: { target: "none", payload: z.strictObject({}) },
  backup_db: { target: "none", payload: z.strictObject({}) },
  cleanup_storage: { target: "none", payload: z.strictObject({}) },
};

export async function enqueueJob(input: {
  type: JobType; payload?: Record<string, unknown>; channel_id?: string | null; video_id?: string | null;
}): Promise<ActionResult> {
  return guard(async () => {
    const data = z.object({
      type: z.enum(JOB_TYPES),
      payload: z.record(z.string(), z.unknown()).default({}),
      channel_id: uuid.nullish(),
      video_id: uuid.nullish(),
    }).parse(input);
    const spec = JOB_SPEC[data.type];
    const payload = spec.payload.parse(data.payload);
    const db = serviceClient();
    let channelId: string | null = null;
    let videoId: string | null = null;

    // The row's target columns come from the validated payload and must point at real rows.
    if (spec.target === "video") {
      const { data: v } = await db.from("videos").select("id,channel_id,status").eq("id", payload.video_id as string).maybeSingle();
      if (!v) return { ok: false, error: "That video doesn't exist any more." };
      if (data.type === "publish_video" && !["ready", "approved", "scheduled", "failed"].includes(v.status as string)) {
        return { ok: false, error: "Only finished videos can be published." };
      }
      videoId = v.id as string;
      channelId = v.channel_id as string;
    } else if (spec.target === "channel" || (spec.target === "optional_channel" && payload.channel_id)) {
      const { data: c } = await db.from("channels").select("id").eq("id", payload.channel_id as string).maybeSingle();
      if (!c) return { ok: false, error: "That channel doesn't exist any more." };
      channelId = c.id as string;
    }
    if ((data.video_id && data.video_id !== videoId) || (data.channel_id && data.channel_id !== channelId)) {
      return { ok: false, error: "The job target doesn't match its payload." };
    }

    const dedupe = `${data.type}:${videoId ?? channelId ?? "global"}:manual`;
    const { error } = await db.from("jobs").insert({
      type: data.type, payload, channel_id: channelId, video_id: videoId, priority: 3, dedupe_key: dedupe,
    });
    if (error?.code === "23505") return { ok: true, message: "Already queued — the worker will pick it up shortly." };
    fail(error);
    revalidatePath("/", "layout");
    return { ok: true, message: `${JOB_LABEL[data.type]}. The worker picks it up within a minute.` };
  });
}

export async function retryJob(id: number): Promise<ActionResult> {
  return guard(async () => {
    z.number().int().positive().parse(id);
    const { error } = await serviceClient().from("jobs")
      .update({ status: "queued", run_after: new Date().toISOString(), last_error: null, waiting_on: null, locked_by: null, locked_at: null, attempts: 0 })
      .eq("id", id).in("status", ["failed", "cancelled", "waiting"]);
    fail(error);
    revalidatePath("/logs");
    return { ok: true, message: "Job requeued." };
  });
}

export async function cancelJob(id: number): Promise<ActionResult> {
  return guard(async () => {
    z.number().int().positive().parse(id);
    const { error } = await serviceClient().from("jobs")
      .update({ status: "cancelled", finished_at: new Date().toISOString() })
      .eq("id", id).in("status", ["queued", "waiting"]);
    fail(error);
    revalidatePath("/logs");
    return { ok: true, message: "Job cancelled." };
  });
}

/* ---------------- Global settings ---------------- */

async function readGlobal(): Promise<GlobalSettings> {
  const { data } = await serviceClient().from("settings").select("value").eq("key", "global").maybeSingle();
  return { ...DEFAULT_SETTINGS, ...((data?.value as Partial<GlobalSettings>) ?? {}) };
}

export async function setGlobalPause(paused: boolean): Promise<ActionResult> {
  return guard(async () => {
    z.boolean().parse(paused);
    const value = { ...(await readGlobal()), paused };
    const { error } = await serviceClient().from("settings").upsert({ key: "global", value });
    fail(error);
    await logEvent(paused ? "Studio paused from the dashboard" : "Studio resumed from the dashboard", { level: paused ? "warn" : "success" });
    revalidatePath("/", "layout");
    return { ok: true, message: paused ? "Studio paused. Nothing new will start." : "Studio resumed." };
  });
}

const settingsSchema = z.object({
  daily_budget_usd: z.coerce.number().min(0).max(10000),
  monthly_budget_usd: z.coerce.number().min(0).max(100000),
  video_retention_days: z.coerce.number().int().min(3).max(365),
  report_email: z.string().email().or(z.literal("")).nullish(),
  auto_publish: z.boolean(),
  api_fallback: z.boolean().default(false),
  api_fallback_daily_usd: z.coerce.number().min(0).max(100).default(2),
  runpod_monthly_cap_usd: z.coerce.number().min(0).max(1000).default(100),
});

export async function updateSettings(input: z.input<typeof settingsSchema>): Promise<ActionResult> {
  return guard(async () => {
    const parsed = settingsSchema.parse(input);
    const prev = await readGlobal();
    // The owner fixed Claude to Sonnet at medium effort; nothing in the dashboard can raise it.
    const value = { ...prev, ...parsed, model: "claude-sonnet-5-5", effort: "medium", report_email: parsed.report_email || null };
    const { error } = await serviceClient().from("settings").upsert({ key: "global", value });
    fail(error);
    if (Boolean(prev.api_fallback) !== value.api_fallback) {
      const cap = value.api_fallback_daily_usd.toFixed(2);
      await logEvent(value.api_fallback ? "API-key fallback ON (max $" + cap + " a day)" : "API-key fallback switched off", { level: "warn" });
    }
    if (prev.auto_publish !== value.auto_publish) {
      await logEvent(value.auto_publish ? "Auto-publish switched ON" : "Auto-publish switched off", { level: "warn" });
    }
    revalidatePath("/", "layout");
    return { ok: true, message: "Settings saved." };
  });
}

export async function setAnthropicCredit(balance: number): Promise<ActionResult> {
  return guard(async () => {
    const b = z.coerce.number().min(0).max(100000).parse(balance);
    const { error } = await serviceClient().from("settings")
      .upsert({ key: "anthropic_credit", value: { balance_usd: b, set_at: new Date().toISOString() } });
    fail(error);
    await logEvent(`Claude API credit balance set to $${b.toFixed(2)}`);
    revalidatePath("/", "layout");
    return { ok: true, message: "Credit balance saved. Remaining credit is now estimated from spend." };
  });
}

/* ---------------- Secrets ---------------- */

export async function saveSecret(key: string, value: string): Promise<ActionResult> {
  return guard(async () => {
    const k = z.enum(SECRET_KEYS).parse(key);
    const v = z.string().trim().min(8, "That key looks too short").max(4000).parse(value);
    if (!hasMasterKey()) return { ok: false, error: "MASTER_KEY is not configured on the server, so keys can't be stored safely." };
    const { error } = await serviceClient().from("secrets")
      .upsert({ key: k, ciphertext: encrypt(v), hint: v.slice(-4), updated_at: new Date().toISOString() });
    fail(error);
    await logEvent(`API key updated: ${k.replace(/_/g, " ")}`);
    // ask the worker to re-check services with the new key
    await serviceClient().from("jobs").insert({ type: "health_check", priority: 2, dedupe_key: "health_check:global:manual" }).then(() => undefined, () => undefined);
    revalidatePath("/settings");
    revalidatePath("/accounts");
    return { ok: true, message: "Saved and encrypted. Running a health check." };
  });
}

export async function deleteSecret(key: string): Promise<ActionResult> {
  return guard(async () => {
    const k = z.enum(SECRET_KEYS).parse(key);
    const { error } = await serviceClient().from("secrets").delete().eq("key", k);
    fail(error);
    await logEvent(`API key removed: ${k.replace(/_/g, " ")}`, { level: "warn" });
    revalidatePath("/settings");
    return { ok: true, message: "Key removed." };
  });
}

/* ---------------- Channels ---------------- */

const hhmm = z.string().regex(/^([01]\d|2[0-3]):[0-5]\d$/, "Use HH:MM (24h)");
const hex = z.string().regex(/^#[0-9a-fA-F]{6}$/, "Use a hex colour like #FFD60A");

/** Caps a free-form JSON object (passthrough keys included) so channel rows stay small. */
const jsonCap = <T extends z.ZodType>(schema: T, maxBytes: number) =>
  schema.refine((v) => JSON.stringify(v ?? {}).length <= maxBytes, { message: `Too much data (max ${maxBytes / 1000} KB)` });

const channelSchema = z.object({
  name: z.string().trim().min(2).max(60),
  slug: z.string().trim().regex(/^[a-z0-9-]{2,40}$/, "Lowercase letters, numbers and dashes"),
  niche: z.string().trim().min(2).max(120),
  description: z.string().max(2000).default(""),
  color: hex,
  posting_mode: z.enum(["draft", "private", "public"]),
  require_approval: z.boolean(),
  posts_per_day: z.coerce.number().int().min(0).max(6),
  post_times: z.array(hhmm).max(6),
  timezone: z.string().min(3).max(60).refine((tz) => {
    try {
      new Intl.DateTimeFormat("en-US", { timeZone: tz });
      return true;
    } catch {
      return false;
    }
  }, "Unknown time zone"),
  buffer_days: z.coerce.number().int().min(0).max(7),
  min_seconds: z.coerce.number().int().min(61, "TikTok Creator Rewards needs videos over 60 seconds").max(600),
  max_seconds: z.coerce.number().int().min(62).max(600),
  style: jsonCap(z.object({
    preset: z.string().max(40).optional(),
    bg: hex.optional(), ink: hex.optional(), accent: hex.optional(),
    body_font: z.string().max(80).optional(), key_font: z.string().max(80).optional(),
    figure_prompt: z.string().max(1200).optional(), seed: z.coerce.number().int().min(0).max(2 ** 31).optional(),
    bug_text: z.string().max(40).optional(),
  }).passthrough(), 8_000),
  voice: jsonCap(z.object({
    provider: z.literal("kokoro").optional(),
    voice: z.string().regex(/^[a-z]{2}_[a-z]+(\+[a-z]{2}_[a-z]+)?$/, "Pick a voice from the list").optional(),
    speed: z.coerce.number().min(0.7).max(1.3).optional(),
  }).passthrough(), 4_000),
  content: jsonCap(z.object({
    audience: z.string().max(400).optional(), tone: z.string().max(600).optional(),
    pillars: z.array(z.object({ name: z.string().min(1).max(80), weight: z.coerce.number().min(0).max(1) })).max(12).optional(),
    hook_styles: z.array(z.string().max(40)).max(20).optional(),
    hashtags_core: z.array(z.string().max(40)).max(20).optional(),
    rules: z.array(z.string().max(300)).max(30).optional(),
    banned: z.array(z.string().max(120)).max(30).optional(),
  }).passthrough(), 20_000),
}).refine((c) => c.max_seconds > c.min_seconds, { message: "Max length must be longer than min length", path: ["max_seconds"] });

export type ChannelInput = z.input<typeof channelSchema>;

export async function createChannel(input: ChannelInput): Promise<ActionResult<{ slug: string }>> {
  return guard(async () => {
    const c = channelSchema.parse(input);
    const { count } = await serviceClient().from("channels").select("id", { count: "exact", head: true });
    const { error } = await serviceClient().from("channels").insert({ ...c, status: "paused", sort: count ?? 0 });
    if (error?.code === "23505") return { ok: false, error: "That slug is taken — pick another." };
    fail(error);
    await logEvent(`Channel created: ${c.name}`, { level: "success" });
    revalidatePath("/channels");
    return { ok: true, data: { slug: c.slug }, message: "Channel created. It starts paused — switch it on when you're ready." };
  });
}

export async function updateChannel(id: string, input: ChannelInput): Promise<ActionResult<{ slug: string }>> {
  return guard(async () => {
    uuid.parse(id);
    const c = channelSchema.parse(input);
    const { error } = await serviceClient().from("channels").update(c).eq("id", id);
    if (error?.code === "23505") return { ok: false, error: "That slug is taken — pick another." };
    fail(error);
    await logEvent(`Channel settings saved: ${c.name}`, { channel_id: id });
    revalidatePath("/channels", "layout");
    return { ok: true, data: { slug: c.slug }, message: "Channel saved." };
  });
}

export async function setChannelStatus(id: string, status: "active" | "paused"): Promise<ActionResult> {
  return guard(async () => {
    uuid.parse(id);
    z.enum(["active", "paused"]).parse(status);
    const { data: ch, error } = await serviceClient().from("channels")
      .update({ status, ...(status === "active" ? { blocked_reason: null } : {}) })
      .eq("id", id).select("name").single();
    fail(error);
    await logEvent(status === "active" ? `Channel started: ${ch?.name}` : `Channel paused: ${ch?.name}`, { channel_id: id, level: status === "active" ? "success" : "warn" });
    revalidatePath("/", "layout");
    return { ok: true, message: status === "active" ? "Channel started." : "Channel paused." };
  });
}

export async function deleteChannel(id: string, confirmSlug: string): Promise<ActionResult> {
  return guard(async () => {
    uuid.parse(id);
    const { data: ch } = await serviceClient().from("channels").select("slug,name").eq("id", id).single();
    if (!ch || ch.slug !== confirmSlug) return { ok: false, error: "Type the channel slug exactly to confirm." };
    const { error } = await serviceClient().from("channels").delete().eq("id", id);
    fail(error);
    await logEvent(`Channel deleted: ${ch.name}`, { level: "warn" });
    revalidatePath("/", "layout");
    return { ok: true, message: "Channel deleted." };
  });
}

export async function linkAccount(channelId: string, accountId: string | null): Promise<ActionResult> {
  return guard(async () => {
    uuid.parse(channelId);
    if (accountId) {
      uuid.parse(accountId);
      await serviceClient().from("channels").update({ tiktok_account_id: null }).eq("tiktok_account_id", accountId);
    }
    const { error } = await serviceClient().from("channels").update({ tiktok_account_id: accountId }).eq("id", channelId);
    fail(error);
    revalidatePath("/", "layout");
    return { ok: true, message: accountId ? "Account linked to channel." : "Account unlinked." };
  });
}

export async function disconnectAccount(accountId: string): Promise<ActionResult> {
  return guard(async () => {
    uuid.parse(accountId);
    await serviceClient().from("channels").update({ tiktok_account_id: null }).eq("tiktok_account_id", accountId);
    const { data, error } = await serviceClient().from("tiktok_accounts").delete().eq("id", accountId).select("username").single();
    fail(error);
    await logEvent(`TikTok account disconnected: @${data?.username ?? "unknown"}`, { level: "warn" });
    revalidatePath("/", "layout");
    return { ok: true, message: "Account disconnected and its tokens deleted." };
  });
}

/* ---------------- Ideas ---------------- */

export async function addIdea(input: { channel_id: string; title: string; hook?: string; pillar?: string; summary?: string }): Promise<ActionResult> {
  return guard(async () => {
    const i = z.object({
      channel_id: uuid, title: z.string().trim().min(3).max(200), hook: z.string().max(300).optional(),
      pillar: z.string().max(80).optional(), summary: z.string().max(2000).optional(),
    }).parse(input);
    const { error } = await serviceClient().from("ideas").insert({ ...i, origin: "manual", score: 70 });
    fail(error);
    revalidatePath("/channels", "layout");
    return { ok: true, message: "Idea added to the bank." };
  });
}

export async function setIdeaStatus(id: string, status: "new" | "retired" | "rejected"): Promise<ActionResult> {
  return guard(async () => {
    uuid.parse(id);
    z.enum(["new", "retired", "rejected"]).parse(status);
    const { error } = await serviceClient().from("ideas").update({ status }).eq("id", id);
    fail(error);
    revalidatePath("/channels", "layout");
    return { ok: true, message: status === "new" ? "Idea restored." : "Idea retired." };
  });
}

export async function bumpIdea(id: string, delta: number): Promise<ActionResult> {
  return guard(async () => {
    uuid.parse(id);
    const d = z.number().min(-50).max(50).parse(delta);
    const { data } = await serviceClient().from("ideas").select("score").eq("id", id).single();
    const score = Math.max(0, Math.min(100, Number(data?.score ?? 0) + d));
    const { error } = await serviceClient().from("ideas").update({ score }).eq("id", id);
    fail(error);
    revalidatePath("/channels", "layout");
    return { ok: true };
  });
}

/* ---------------- Videos ---------------- */

export async function approveVideo(id: string): Promise<ActionResult> {
  return guard(async () => {
    uuid.parse(id);
    const { data, error } = await serviceClient().from("videos")
      .update({ approval: "approved", approved_at: new Date().toISOString(), status: "approved", rejection_note: null })
      .eq("id", id).in("status", ["ready", "rejected", "failed"]).select("channel_id,title").single();
    if (error?.code === "PGRST116") return { ok: false, error: "Only videos that are ready for review can be approved." };
    fail(error);
    await logEvent(`Approved: ${data?.title}`, { video_id: id, channel_id: data?.channel_id, level: "success" });
    revalidatePath("/", "layout");
    return { ok: true, message: "Approved. It will post at the next free slot." };
  });
}

export async function rejectVideo(id: string, note: string): Promise<ActionResult> {
  return guard(async () => {
    uuid.parse(id);
    const n = z.string().max(1000).parse(note ?? "");
    const { data, error } = await serviceClient().from("videos")
      .update({ approval: "rejected", status: "rejected", rejection_note: n || null })
      .eq("id", id).not("status", "in", "(uploading,sent_to_drafts,posted,rejected)").select("channel_id,title").single();
    if (error?.code === "PGRST116") return { ok: false, error: "This video can't be rejected any more (it's posting or already out)." };
    fail(error);
    await logEvent(`Rejected: ${data?.title}${n ? ` — ${n}` : ""}`, { video_id: id, channel_id: data?.channel_id, level: "warn" });
    revalidatePath("/", "layout");
    return { ok: true, message: "Rejected. The note is fed into the next script for this channel." };
  });
}

export async function updateCaption(id: string, caption: string, hashtags: string[]): Promise<ActionResult> {
  return guard(async () => {
    uuid.parse(id);
    const c = z.string().max(2200).parse(caption);
    const tags = z.array(z.string().regex(/^#[\p{L}\p{N}_]{1,60}$/u, "Hashtags look like #psychology")).max(10).parse(
      hashtags.map((t) => t.trim()).filter(Boolean).map((t) => (t.startsWith("#") ? t : `#${t}`)),
    );
    // The worker posts `${caption}\n\n${hashtags.join(" ")}` as the TikTok title, which TikTok caps at 2200.
    const title = `${c.trim()}\n\n${tags.join(" ")}`.trim();
    if (title.length > 2200) return { ok: false, error: `Caption plus hashtags is ${title.length} characters; TikTok allows 2200.` };
    const { error } = await serviceClient().from("videos").update({ caption: c, hashtags: tags }).eq("id", id);
    fail(error);
    revalidatePath(`/videos/${id}`);
    return { ok: true, message: "Caption saved." };
  });
}

export async function scheduleVideo(id: string, whenIso: string | null): Promise<ActionResult> {
  return guard(async () => {
    uuid.parse(id);
    const when = whenIso ? z.string().datetime({ offset: true }).parse(whenIso) : null;
    const { error } = await serviceClient().from("videos").update({ scheduled_for: when }).eq("id", id);
    fail(error);
    revalidatePath(`/videos/${id}`);
    return { ok: true, message: when ? "Post time set." : "Post time cleared — it will take the next free slot." };
  });
}

/* ---------------- Stats import ---------------- */

const IMPORT_TYPES: Record<string, { mime: string; accept: string[] }> = {
  csv: { mime: "text/csv", accept: ["text/csv", "text/plain", "application/csv", "application/vnd.ms-excel", ""] },
  xlsx: { mime: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", accept: ["application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "application/octet-stream", ""] },
  xls: { mime: "application/vnd.ms-excel", accept: ["application/vnd.ms-excel", "application/octet-stream", ""] },
};

export async function importStats(formData: FormData): Promise<ActionResult> {
  return guard(async () => {
    const channelId = uuid.parse(formData.get("channel_id"));
    const file = formData.get("file");
    if (!(file instanceof File) || file.size === 0) return { ok: false, error: "Choose a CSV or XLSX export from TikTok Studio." };
    if (file.size > 20 * 1024 * 1024) return { ok: false, error: "That file is over 20 MB." };
    const ext = (file.name.split(".").pop() ?? "").toLowerCase();
    const kind = IMPORT_TYPES[ext];
    if (!kind || !kind.accept.includes(file.type)) return { ok: false, error: "Upload a .csv or .xlsx file." };
    const { data: ch } = await serviceClient().from("channels").select("id").eq("id", channelId).maybeSingle();
    if (!ch) return { ok: false, error: "That channel doesn't exist any more." };
    // Storage path is built only from validated parts (uuid, timestamp, whitelisted extension) — never the file name.
    const path = `imports/${channelId}/${Date.now()}.${ext}`;
    const { error: upErr } = await serviceClient().storage.from("videos").upload(path, file, {
      contentType: kind.mime, upsert: false,
    });
    fail(upErr);
    const filename = file.name.replace(/[\u0000-\u001f/\\]/g, "_").slice(0, 120);
    const { error } = await serviceClient().from("jobs").insert({
      type: "import_stats", payload: { storage_path: path, channel_id: channelId, filename }, channel_id: channelId, priority: 3,
    });
    fail(error);
    await logEvent(`Stats file uploaded: ${filename}`, { channel_id: channelId });
    revalidatePath("/analytics");
    return { ok: true, message: "Uploaded. Watch-time and completion appear once the worker reads it." };
  });
}
