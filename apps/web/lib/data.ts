import "server-only";
import { cache } from "react";
import { serviceClient } from "@/lib/supabase/service";
import type {
  Channel, GlobalSettings, Idea, Job, Report, Service, StudioEvent, TikTokAccount, Video, VideoStat, WorkerHeartbeat,
} from "@/lib/types";

// All reads run server-side after requireAdminPage(); the service client keeps them fast and RLS-independent.
const db = () => serviceClient();

const ACCOUNT_COLS =
  "id,open_id,username,display_name,avatar_url,access_expires_at,refresh_expires_at,scopes,status,status_message,follower_count,following_count,likes_count,video_count,is_verified,creator_info,last_synced_at,created_at,updated_at";

export const DEFAULT_SETTINGS: GlobalSettings = {
  paused: false, auto_publish: false, model: "claude-opus-5-5", effort: "high",
  daily_budget_usd: 15, monthly_budget_usd: 300, video_retention_days: 21, report_email: null,
};

export const getSettings = cache(async (): Promise<GlobalSettings> => {
  const { data } = await db().from("settings").select("value").eq("key", "global").maybeSingle();
  return { ...DEFAULT_SETTINGS, ...((data?.value as Partial<GlobalSettings>) ?? {}) };
});

export async function getAnthropicCredit(): Promise<{ balance_usd: number | null; set_at: string | null }> {
  const { data } = await db().from("settings").select("value").eq("key", "anthropic_credit").maybeSingle();
  const v = (data?.value ?? {}) as { balance_usd?: number | null; set_at?: string | null };
  return { balance_usd: v.balance_usd ?? null, set_at: v.set_at ?? null };
}

export const getServices = cache(async (): Promise<Service[]> => {
  const { data } = await db().from("services").select("*");
  const order = ["anthropic", "elevenlabs", "runpod", "tiktok", "storage", "worker"];
  return ((data ?? []) as Service[]).sort((a, b) => order.indexOf(a.name) - order.indexOf(b.name));
});

export const getWorkers = cache(async (): Promise<WorkerHeartbeat[]> => {
  const { data } = await db().from("worker_heartbeats").select("*").order("last_seen", { ascending: false });
  return (data ?? []) as WorkerHeartbeat[];
});

export const getChannels = cache(async (): Promise<Channel[]> => {
  const { data } = await db().from("channels").select("*").order("sort").order("created_at");
  return (data ?? []) as Channel[];
});

export async function getChannelBySlug(slug: string): Promise<Channel | null> {
  const { data } = await db().from("channels").select("*").eq("slug", slug).maybeSingle();
  return (data as Channel) ?? null;
}

export const getAccounts = cache(async (): Promise<TikTokAccount[]> => {
  const { data } = await db().from("tiktok_accounts").select(ACCOUNT_COLS).order("created_at");
  return (data ?? []) as TikTokAccount[];
});

export async function getVideos(opts: {
  channelId?: string; statuses?: string[]; limit?: number; order?: "created" | "posted" | "scheduled";
} = {}): Promise<Video[]> {
  let q = db().from("videos").select("*");
  if (opts.channelId) q = q.eq("channel_id", opts.channelId);
  if (opts.statuses?.length) q = q.in("status", opts.statuses);
  if (opts.order === "posted") q = q.order("posted_at", { ascending: false, nullsFirst: false });
  else if (opts.order === "scheduled") q = q.order("scheduled_for", { ascending: true, nullsFirst: false });
  else q = q.order("created_at", { ascending: false });
  const { data } = await q.limit(opts.limit ?? 200);
  return (data ?? []) as Video[];
}

export async function getVideo(id: string): Promise<Video | null> {
  if (!/^[0-9a-f-]{36}$/i.test(id)) return null;
  const { data } = await db().from("videos").select("*").eq("id", id).maybeSingle();
  return (data as Video) ?? null;
}

export async function getIdeas(channelId: string): Promise<Idea[]> {
  const { data } = await db().from("ideas").select("*").eq("channel_id", channelId)
    .order("status").order("score", { ascending: false }).limit(300);
  return (data ?? []) as Idea[];
}

export async function getEvents(opts: { channelId?: string; videoId?: string; level?: string; limit?: number } = {}) {
  let q = db().from("events").select("*").order("created_at", { ascending: false });
  if (opts.channelId) q = q.eq("channel_id", opts.channelId);
  if (opts.videoId) q = q.eq("video_id", opts.videoId);
  if (opts.level) q = q.eq("level", opts.level);
  const { data } = await q.limit(opts.limit ?? 50);
  return (data ?? []) as StudioEvent[];
}

export async function getJobs(opts: { status?: string; limit?: number } = {}) {
  let q = db().from("jobs").select("*").order("created_at", { ascending: false });
  if (opts.status) q = q.eq("status", opts.status);
  const { data } = await q.limit(opts.limit ?? 60);
  return (data ?? []) as Job[];
}

export async function getReports(channelId?: string) {
  let q = db().from("reports").select("*").order("created_at", { ascending: false });
  if (channelId) q = q.eq("channel_id", channelId);
  const { data } = await q.limit(50);
  return (data ?? []) as Report[];
}

/** Latest stats row per video, for the given videos. */
export async function getLatestStats(videoIds: string[]): Promise<Map<string, VideoStat>> {
  const map = new Map<string, VideoStat>();
  if (!videoIds.length) return map;
  const { data } = await db().from("video_stats").select("*").in("video_id", videoIds)
    .order("captured_at", { ascending: false }).limit(5000);
  for (const row of (data ?? []) as VideoStat[]) {
    const prev = map.get(row.video_id);
    if (!prev) map.set(row.video_id, { ...row });
    else {
      // fill gaps (e.g. completion from an import) without overwriting fresher API numbers
      for (const k of ["avg_watch_s", "completion_rate", "saves", "follows"] as const) {
        if (prev[k] == null && row[k] != null) (prev as unknown as Record<string, unknown>)[k] = row[k];
      }
    }
  }
  return map;
}

export async function getStatsSeries(sinceIso: string, channelId?: string) {
  let vq = db().from("videos").select("id,channel_id,title,posted_at").not("posted_at", "is", null);
  if (channelId) vq = vq.eq("channel_id", channelId);
  const { data: vids } = await vq.limit(1000);
  const ids = (vids ?? []).map((v) => v.id as string);
  if (!ids.length) return { videos: [], stats: [] as VideoStat[] };
  const { data: stats } = await db().from("video_stats").select("*").in("video_id", ids)
    .gte("captured_at", sinceIso).order("captured_at").limit(20000);
  return { videos: vids ?? [], stats: (stats ?? []) as VideoStat[] };
}

export async function getSpendSince(iso: string) {
  const { data } = await db().from("spend").select("service,amount_usd,created_at").gte("created_at", iso).limit(20000);
  return (data ?? []) as { service: string; amount_usd: number; created_at: string }[];
}

export async function getAccountStats(sinceIso: string) {
  const { data } = await db().from("account_stats").select("*").gte("captured_at", sinceIso).order("captured_at").limit(5000);
  return (data ?? []) as { tiktok_account_id: string; captured_at: string; follower_count: number | null }[];
}

export async function getSecretHints() {
  const { data } = await db().from("secrets").select("key,hint,updated_at");
  return (data ?? []) as { key: string; hint: string | null; updated_at: string }[];
}
