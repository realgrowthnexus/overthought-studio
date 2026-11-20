// What the Claude card shows, from the worker's services row for "anthropic" (no imports: unit-tested with plain node).

export interface ClaudeWindowView { pct: number; resets: string | null }
export interface ClaudeView {
  state: "connected" | "not_signed_in" | "limited" | "api" | "problem";
  headline: string;
  fiveHour: ClaudeWindowView | null;
  week: ClaudeWindowView | null;
  estimate: boolean;
  pacing: boolean;
  summary: string | null;
}

interface ServiceLike { status: string; message: string | null; details?: Record<string, unknown> | null }
interface Win { pct?: number | null; resets_at?: string | null }

const TZ = "America/New_York";

export function whenLabel(iso: string | null | undefined, now: Date): string | null {
  if (!iso) return null;
  const t = new Date(iso);
  if (Number.isNaN(t.getTime())) return null;
  const sameDay = t.toLocaleDateString("en-US", { timeZone: TZ }) === now.toLocaleDateString("en-US", { timeZone: TZ });
  const time = t.toLocaleTimeString("en-US", { timeZone: TZ, hour: "numeric", minute: "2-digit" });
  return sameDay ? time : `${t.toLocaleDateString("en-US", { timeZone: TZ, weekday: "short" })} ${time}`;
}

function win(raw: unknown, now: Date): ClaudeWindowView | null {
  const w = (raw ?? null) as Win | null;
  if (!w || w.pct == null) return null;
  return { pct: Math.max(0, Math.min(100, Math.round(Number(w.pct)))), resets: whenLabel(w.resets_at, now) };
}

export function claudeView(s: ServiceLike | undefined, now: Date = new Date()): ClaudeView {
  const d = (s?.details ?? {}) as Record<string, unknown>;
  const base = {
    fiveHour: win(d.five_hour, now), week: win(d.seven_day, now),
    estimate: d.source === "estimate", pacing: d.pacing === true,
  };
  const made = typeof d.week_videos === "number" ? d.week_videos : null;
  const left = typeof d.videos_left === "number" && d.source === "reported" ? d.videos_left : null;
  const summary = made == null ? null
    : `This week: ${made} video${made === 1 ? "" : "s"} made${left != null ? ` · about ${left} more fit` : ""}`;

  if (!s || s.status === "unconfigured") {
    return { state: "not_signed_in", headline: "Not signed in to Claude", ...base, summary: null };
  }
  if (d.backend === "api") {
    return { state: "api", headline: "Using an Anthropic API key", ...base, summary };
  }
  const resume = typeof d.resume_at === "string" ? new Date(d.resume_at) : null;
  if (d.limited === true && (!resume || resume > now)) {
    const at = whenLabel(d.resume_at as string | undefined, now);
    return { state: "limited", headline: `Claude limit reached — work resumes${at ? ` at ${at}` : " on its own"}`, ...base, summary };
  }
  if (s.status === "down" || s.status === "out_of_credits") {
    return { state: "problem", headline: s.message ?? "Claude can't be reached right now", ...base, summary };
  }
  return { state: "connected", headline: "Connected to your Claude plan", ...base, summary };
}
