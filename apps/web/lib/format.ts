import { isClaudePause } from "@/lib/claude-usage";
import type { ServiceName, ServiceStatus, VideoStatus } from "@/lib/types";

const compact = new Intl.NumberFormat("en-US", { notation: "compact", maximumFractionDigits: 1 });
const full = new Intl.NumberFormat("en-US");

export function num(n: number | null | undefined, opts?: { compact?: boolean }) {
  if (n === null || n === undefined || Number.isNaN(n)) return "—";
  if (opts?.compact || Math.abs(n) >= 10000) return compact.format(n);
  return full.format(n);
}

export function usd(n: number | null | undefined, digits = 2) {
  if (n === null || n === undefined || Number.isNaN(Number(n))) return "—";
  return new Intl.NumberFormat("en-US", {
    style: "currency", currency: "USD", minimumFractionDigits: digits, maximumFractionDigits: digits,
  }).format(Number(n));
}

export function pct(n: number | null | undefined, digits = 0) {
  if (n === null || n === undefined || Number.isNaN(n)) return "—";
  return `${(n * 100).toFixed(digits)}%`;
}

export function duration(s: number | null | undefined) {
  if (!s && s !== 0) return "—";
  const m = Math.floor(s / 60);
  const r = Math.round(s % 60);
  return m ? `${m}:${String(r).padStart(2, "0")}` : `${r}s`;
}

export function relTime(iso: string | null | undefined, now = Date.now()) {
  if (!iso) return "never";
  const diff = new Date(iso).getTime() - now;
  const abs = Math.abs(diff);
  const rtf = new Intl.RelativeTimeFormat("en", { numeric: "auto" });
  const units: [Intl.RelativeTimeFormatUnit, number][] = [
    ["day", 86400000], ["hour", 3600000], ["minute", 60000],
  ];
  for (const [unit, ms] of units) {
    if (abs >= ms) return rtf.format(Math.round(diff / ms), unit);
  }
  return diff < 0 ? "just now" : "in a moment";
}

export function dateTime(iso: string | null | undefined, tz = "America/New_York") {
  if (!iso) return "—";
  return new Intl.DateTimeFormat("en-US", {
    month: "short", day: "numeric", hour: "numeric", minute: "2-digit", timeZone: tz,
  }).format(new Date(iso));
}

export function shortDate(iso: string | null | undefined) {
  if (!iso) return "—";
  return new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric" }).format(new Date(iso));
}

export const PIPELINE: { key: VideoStatus; label: string }[] = [
  { key: "queued", label: "Queued" },
  { key: "researching", label: "Research" },
  { key: "scripting", label: "Script" },
  { key: "fact_checking", label: "Fact-check" },
  { key: "visuals", label: "Visuals" },
  { key: "voice", label: "Voice" },
  { key: "rendering", label: "Render" },
  { key: "ready", label: "Ready" },
];

export const STATUS_LABEL: Record<VideoStatus, string> = {
  queued: "Queued", researching: "Researching", scripting: "Writing script", fact_checking: "Fact-checking",
  visuals: "Drawing scenes", voice: "Recording voice", rendering: "Rendering", ready: "Ready for review",
  approved: "Approved", scheduled: "Scheduled", uploading: "Uploading", sent_to_drafts: "In TikTok drafts",
  posted: "Posted", rejected: "Rejected", failed: "Failed", blocked: "Blocked",
};

export const IN_PROGRESS: VideoStatus[] = [
  "queued", "researching", "scripting", "fact_checking", "visuals", "voice", "rendering", "uploading",
];

export type Tone = "neutral" | "good" | "warn" | "bad" | "accent" | "info";

export function videoTone(s: VideoStatus, error?: string | null): Tone {
  if (s === "blocked" && isClaudePause(error)) return "warn";      // waiting for the Claude limit to reset
  if (s === "posted" || s === "sent_to_drafts") return "good";
  if (s === "failed" || s === "blocked") return "bad";
  if (s === "rejected") return "neutral";
  if (s === "ready") return "accent";
  if (s === "approved" || s === "scheduled") return "info";
  return "warn";
}

export const SERVICE_LABEL: Record<ServiceName, string> = {
  anthropic: "Claude", voice: "Voice", runpod: "RunPod", tiktok: "TikTok", storage: "Storage", worker: "Worker",
};

export const SERVICE_ROLE: Record<ServiceName, string> = {
  anthropic: "Research, scripts and fact-checks",
  voice: "Voiceover (free, on your server)",
  runpod: "Scene images",
  tiktok: "Posting and stats",
  storage: "Videos and backups",
  worker: "The VPS that does the work",
};

export function serviceTone(s: ServiceStatus): Tone {
  if (s === "ok") return "good";
  if (s === "warning") return "warn";
  if (s === "unconfigured") return "neutral";
  return "bad";
}

export const SERVICE_STATUS_LABEL: Record<ServiceStatus, string> = {
  ok: "Working", warning: "Running low", down: "Down", out_of_credits: "Out of credits", unconfigured: "Not set up",
};

/** Plain-English fix instructions shown in the alert banner. */
export function serviceFix(name: ServiceName, status: ServiceStatus): { text: string; href: string } {
  const settings = { href: "/settings#keys" };
  if (status === "unconfigured") {
    if (name === "worker") return { text: "Install the worker on your VPS — see the setup guide.", href: "/settings#worker" };
    if (name === "tiktok") return { text: "Add your TikTok app keys, then connect an account.", href: "/accounts" };
    if (name === "anthropic") return { text: "Sign in to Claude once on the VPS — Settings shows the command.", href: "/settings#claude" };
    if (name === "voice") return { text: "The voice model is missing from the worker. On the VPS run: /opt/overthought-studio/update.sh --force", href: "/settings#worker" };
    return { text: `Add your ${SERVICE_LABEL[name]} API key in Settings.`, ...settings };
  }
  if (status === "out_of_credits") {
    const where: Partial<Record<ServiceName, string>> = {
      anthropic: "console.anthropic.com → Billing", runpod: "runpod.io → Billing",
    };
    return { text: `Top up at ${where[name] ?? SERVICE_LABEL[name]}. Paused work resumes on its own once credit is back.`, ...settings };
  }
  if (name === "worker") return { text: "The VPS worker stopped checking in. Check the server is on and Docker is running.", href: "/settings#worker" };
  if (name === "tiktok") return { text: "Reconnect the TikTok account whose login expired.", href: "/accounts" };
  return { text: "Check the key in Settings, then run a health check.", ...settings };
}

export function slugify(s: string) {
  return s.toLowerCase().normalize("NFKD").replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "").slice(0, 40);
}

export function cn(...parts: (string | false | null | undefined)[]) {
  return parts.filter(Boolean).join(" ");
}

/** Badge label for a video: a Claude-limit hold reads as a pause, not as "Blocked". */
export function videoStatusLabel(s: VideoStatus, error?: string | null): string {
  return s === "blocked" && isClaudePause(error) ? "Paused (Claude limit)" : STATUS_LABEL[s];
}

/** Tone for a channel's "On hold" reason: a Claude-limit pause is amber, everything else red. */
export function holdTone(reason: string | null | undefined): Tone {
  return isClaudePause(reason) ? "warn" : "bad";
}
