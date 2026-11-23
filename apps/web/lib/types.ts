// Hand-written row types mirroring supabase/migrations/0001_init.sql

export type ChannelStatus = "active" | "paused";
export type PostingMode = "draft" | "private" | "public";

export type VideoStatus =
  | "queued" | "researching" | "scripting" | "fact_checking" | "visuals" | "voice" | "rendering"
  | "ready" | "approved" | "scheduled" | "uploading" | "sent_to_drafts" | "posted"
  | "rejected" | "failed" | "blocked";

export type ServiceName = "anthropic" | "voice" | "runpod" | "tiktok" | "storage" | "worker";
export type ServiceStatus = "ok" | "warning" | "down" | "out_of_credits" | "unconfigured";
export type JobStatus = "queued" | "running" | "done" | "failed" | "cancelled" | "waiting";
export type EventLevel = "debug" | "info" | "warn" | "error" | "success";

export interface ChannelStyle {
  preset?: string; bg?: string; ink?: string; accent?: string;
  body_font?: string; key_font?: string; figure_prompt?: string; seed?: number; bug_text?: string;
}
export interface ChannelVoice {
  provider?: string; voice?: string; speed?: number;
}
export interface Pillar { name: string; weight: number }
export interface ChannelContent {
  audience?: string; tone?: string; pillars?: Pillar[]; hook_styles?: string[];
  hashtags_core?: string[]; rules?: string[]; banned?: string[];
}
export interface ChannelStrategy {
  week_of?: string;
  pillar_weights?: Record<string, number>;
  hook_weights?: Record<string, number>;
  test?: { variable?: string; variant?: string; hypothesis?: string };
  notes?: string;
  [k: string]: unknown;
}

export interface Channel {
  id: string; slug: string; name: string; niche: string; description: string; color: string;
  status: ChannelStatus; blocked_reason: string | null; posting_mode: PostingMode;
  require_approval: boolean; posts_per_day: number; post_times: string[]; timezone: string;
  buffer_days: number; min_seconds: number; max_seconds: number;
  style: ChannelStyle; voice: ChannelVoice; content: ChannelContent; strategy: ChannelStrategy;
  tiktok_account_id: string | null; sort: number; created_at: string; updated_at: string;
}

export interface TikTokAccount {
  id: string; open_id: string; username: string | null; display_name: string | null; avatar_url: string | null;
  access_expires_at: string | null; refresh_expires_at: string | null; scopes: string[];
  status: "connected" | "expired" | "revoked" | "error"; status_message: string | null;
  follower_count: number | null; following_count: number | null; likes_count: number | null;
  video_count: number | null; is_verified: boolean | null; creator_info: Record<string, unknown> | null;
  last_synced_at: string | null; created_at: string; updated_at: string;
}

export interface Idea {
  id: string; channel_id: string; title: string; angle: string | null; pillar: string | null; hook: string | null;
  summary: string | null; sources: Source[]; keywords: string[]; score: number; scores: Record<string, number>;
  status: "new" | "queued" | "used" | "rejected" | "retired"; origin: "seed" | "research" | "review" | "manual";
  notes: string | null; created_at: string; updated_at: string;
}

export interface Source {
  researcher?: string; institution?: string; year?: number | string; title?: string; url?: string;
  citation?: string; replicated?: boolean | string | null; note?: string;
}

export interface ScriptBeat {
  id?: string | number; kind?: string; narration?: string; on_screen?: unknown; scene?: string;
  keyword?: string; accent?: string; start?: number; end?: number; [k: string]: unknown;
}
export interface Script {
  title?: string; hook?: string; loop_line?: string; beats?: ScriptBeat[]; sources?: Source[];
  word_count?: number; est_seconds?: number; [k: string]: unknown;
}

export interface Video {
  id: string; channel_id: string; idea_id: string | null; title: string; status: VideoStatus;
  stage_detail: string | null; progress: number; error: string | null; attempts: number;
  script: Script | null; script_version: number; scorecard: Record<string, unknown> | null;
  factcheck: Record<string, unknown> | null; research: Record<string, unknown> | null;
  caption: string | null; hashtags: string[]; duration_s: number | null;
  video_path: string | null; thumb_path: string | null; audio_path: string | null; file_size: number | null;
  cost_usd: number; cost_breakdown: Record<string, number>; experiment: Record<string, unknown> | null;
  approval: "pending" | "approved" | "rejected" | null; approved_at: string | null; rejection_note: string | null;
  scheduled_for: string | null; posted_at: string | null; tiktok_publish_id: string | null;
  tiktok_video_id: string | null; tiktok_url: string | null; publish_status: Record<string, unknown> | null;
  created_at: string; updated_at: string;
}

export interface VideoStat {
  id: number; video_id: string; captured_at: string; source: "api" | "import";
  views: number | null; likes: number | null; comments: number | null; shares: number | null; saves: number | null;
  avg_watch_s: number | null; completion_rate: number | null; follows: number | null;
}

export interface Job {
  id: number; type: string; payload: Record<string, unknown>; status: JobStatus; priority: number;
  attempts: number; max_attempts: number; run_after: string; dedupe_key: string | null;
  locked_by: string | null; locked_at: string | null; waiting_on: string | null; last_error: string | null;
  result: Record<string, unknown> | null; channel_id: string | null; video_id: string | null;
  created_at: string; started_at: string | null; finished_at: string | null;
}

export interface StudioEvent {
  id: number; level: EventLevel; scope: string; message: string; data: Record<string, unknown> | null;
  channel_id: string | null; video_id: string | null; created_at: string;
}

export interface Service {
  name: ServiceName; status: ServiceStatus; message: string | null; balance: number | null;
  balance_unit: string | null; balance_limit: number | null; details: Record<string, unknown>;
  checked_at: string | null; updated_at: string;
}

export interface Report {
  id: string; channel_id: string | null; kind: string; period_start: string; period_end: string;
  title: string; summary_md: string; data: Record<string, unknown>; changes: unknown[]; created_at: string;
}

export interface WorkerHeartbeat {
  worker_id: string; version: string | null; host: string | null; info: Record<string, unknown>;
  started_at: string; last_seen: string;
}

export interface GlobalSettings {
  paused: boolean; auto_publish: boolean; model: string; effort: string;
  daily_budget_usd: number; monthly_budget_usd: number; video_retention_days: number; report_email: string | null;
}

export const SECRET_KEYS = [
  "anthropic_api_key", "runpod_api_key",
  "tiktok_client_key", "tiktok_client_secret", "resend_api_key",
] as const;
export type SecretKey = (typeof SECRET_KEYS)[number];
