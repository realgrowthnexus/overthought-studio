import type { VideoStat } from "@/lib/types";

export type Metric = "views" | "likes" | "shares" | "comments";
export interface DayPoint { date: string; views: number; likes: number; shares: number; comments: number }

/**
 * Cumulative totals per day across videos: for each day, each video contributes its most recent
 * snapshot taken on or before that day. Produces a smooth growth curve even with sparse snapshots.
 */
export function dailyTotals(stats: VideoStat[], days: number, now = new Date()): DayPoint[] {
  const byVideo = new Map<string, VideoStat[]>();
  for (const s of stats) {
    if (s.source !== "api" && s.views == null) continue;
    const list = byVideo.get(s.video_id) ?? [];
    list.push(s);
    byVideo.set(s.video_id, list);
  }
  for (const list of byVideo.values()) list.sort((a, b) => a.captured_at.localeCompare(b.captured_at));

  const out: DayPoint[] = [];
  for (let i = days - 1; i >= 0; i--) {
    const d = new Date(now);
    d.setHours(23, 59, 59, 999);
    d.setDate(d.getDate() - i);
    const cutoff = d.toISOString();
    const p: DayPoint = { date: d.toISOString().slice(0, 10), views: 0, likes: 0, shares: 0, comments: 0 };
    for (const list of byVideo.values()) {
      let last: VideoStat | undefined;
      for (const s of list) {
        if (s.captured_at <= cutoff) last = s;
        else break;
      }
      if (!last) continue;
      p.views += Number(last.views ?? 0);
      p.likes += Number(last.likes ?? 0);
      p.shares += Number(last.shares ?? 0);
      p.comments += Number(last.comments ?? 0);
    }
    out.push(p);
  }
  return out;
}

export function median(values: number[]): number {
  const v = values.filter((x) => Number.isFinite(x)).sort((a, b) => a - b);
  if (!v.length) return 0;
  const m = Math.floor(v.length / 2);
  return v.length % 2 ? v[m] : (v[m - 1] + v[m]) / 2;
}
