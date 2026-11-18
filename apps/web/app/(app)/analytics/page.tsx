import type { Metadata } from "next";
import Link from "next/link";
import { getChannels, getLatestStats, getStatsSeries, getVideos } from "@/lib/data";
import { PageHeader, Panel, PanelHeader } from "@/components/ui/primitives";
import { TrendChart } from "@/components/charts/trend-chart";
import { ImportStats } from "@/components/import-stats";
import { EmptyState } from "@/components/ui/empty";
import { dailyTotals, median } from "@/lib/series";
import { cn, duration, num, pct, shortDate } from "@/lib/format";

export const metadata: Metadata = { title: "Analytics" };
export const dynamic = "force-dynamic";

const RANGES = [7, 30, 90] as const;

export default async function AnalyticsPage({ searchParams }: { searchParams: Promise<{ channel?: string; days?: string }> }) {
  const sp = await searchParams;
  const days = RANGES.find((d) => String(d) === sp.days) ?? 30;
  const channels = await getChannels();
  const channel = channels.find((c) => c.slug === sp.channel);
  const since = new Date(Date.now() - days * 86400000).toISOString();
  const [series, posted] = await Promise.all([
    getStatsSeries(since, channel?.id),
    getVideos({ statuses: ["posted", "sent_to_drafts"], channelId: channel?.id, order: "posted", limit: 300 }),
  ]);
  const inRange = posted.filter((v) => v.posted_at && v.posted_at >= since);
  const stats = await getLatestStats(inRange.map((v) => v.id));
  const data = dailyTotals(series.stats, days);

  // performance vs channel median: views, share rate, completion
  const rows = inRange.map((v) => {
    const s = stats.get(v.id);
    const views = Number(s?.views ?? 0);
    return {
      v, s, views,
      shareRate: views ? Number(s?.shares ?? 0) / views : 0,
      completion: s?.completion_rate ?? null,
    };
  });
  const medians = new Map<string, { views: number; share: number }>();
  for (const c of channels) {
    const mine = rows.filter((r) => r.v.channel_id === c.id);
    medians.set(c.id, { views: median(mine.map((r) => r.views)), share: median(mine.map((r) => r.shareRate)) });
  }
  const ranked = rows
    .map((r) => {
      const m = medians.get(r.v.channel_id) ?? { views: 0, share: 0 };
      const idx = m.views ? r.views / m.views : r.views ? 2 : 1;
      return { ...r, idx, m };
    })
    .sort((a, b) => b.idx - a.idx);

  const q = (patch: Record<string, string | null>) => {
    const p = new URLSearchParams();
    const merged = { channel: channel?.slug ?? null, days: String(days), ...patch };
    for (const [k, val] of Object.entries(merged)) if (val && !(k === "days" && val === "30")) p.set(k, val);
    const s = p.toString();
    return `/analytics${s ? `?${s}` : ""}`;
  };

  return (
    <>
      <PageHeader title="Analytics" description="Views and engagement from TikTok, plus watch-time from your Studio exports." />
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <div className="inline-flex rounded-[10px] border border-line bg-bg p-0.5" role="group" aria-label="Range">
          {RANGES.map((d) => (
            <Link key={d} href={q({ days: String(d) })} aria-current={d === days ? "true" : undefined}
              className={cn("h-8 rounded-[8px] px-3 text-[13px] leading-8", d === days ? "border border-line bg-elev text-ink shadow-sm" : "text-ink-3 hover:text-ink")}>
              {d} days
            </Link>
          ))}
        </div>
        <span className="mx-1 h-5 w-px bg-line" aria-hidden />
        <Link href={q({ channel: null })} className={cn("h-9 rounded-full px-3 text-[13px] leading-9", !channel ? "bg-elev-2 text-ink" : "text-ink-3 hover:text-ink")}>All channels</Link>
        {channels.map((c) => (
          <Link key={c.id} href={q({ channel: c.slug })} className={cn("inline-flex h-9 items-center gap-1.5 rounded-full px-3 text-[13px]", channel?.id === c.id ? "bg-elev-2 text-ink" : "text-ink-3 hover:text-ink")}>
            <span className="size-2 rounded-full" style={{ background: c.color }} aria-hidden />{c.name}
          </Link>
        ))}
      </div>

      <Panel className="mb-6">
        <PanelHeader title={channel ? channel.name : "All channels"} description={`Cumulative totals for videos posted, last ${days} days.`} />
        <TrendChart data={data} height={280} />
        <div className="h-4" />
      </Panel>

      <div className="grid grid-cols-1 items-start [&>*]:min-w-0 gap-6 xl:grid-cols-[1fr_340px]">
        <Panel className="overflow-hidden">
          <PanelHeader title="Video performance" description="Compared with each channel's median for this period. The weekly review doubles down on what beats it." />
          {ranked.length === 0 ? (
            <EmptyState title="No posted videos in this range" figure={false}>Stats sync from TikTok every six hours once videos are public.</EmptyState>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[720px] text-[13px]">
                <thead>
                  <tr className="border-b border-line text-left text-[12px] whitespace-nowrap text-ink-3">
                    <th className="px-5 py-2.5 font-medium">Video</th>
                    <th className="px-3 py-2.5 text-right font-medium">Views</th>
                    <th className="px-3 py-2.5 text-right font-medium">vs median</th>
                    <th className="px-3 py-2.5 text-right font-medium">Shares / 1k</th>
                    <th className="px-3 py-2.5 text-right font-medium">Watched full</th>
                    <th className="px-3 py-2.5 text-right font-medium">Avg watch</th>
                    <th className="px-5 py-2.5 text-right font-medium">Posted</th>
                  </tr>
                </thead>
                <tbody>
                  {ranked.map(({ v, s, views, idx, shareRate, completion }) => {
                    const ch = channels.find((c) => c.id === v.channel_id);
                    const above = idx >= 1.15;
                    const below = idx <= 0.85;
                    return (
                      <tr key={v.id} className="relative border-b border-line last:border-b-0 hover:bg-elev-2/50">
                        <td className="max-w-[320px] px-5 py-2.5">
                          <Link href={`/videos/${v.id}`} className="flex items-center gap-2 after:absolute after:inset-0">
                            <span className="size-2 shrink-0 rounded-full" style={{ background: ch?.color }} aria-hidden />
                            <span className="truncate text-ink">{v.title}</span>
                          </Link>
                        </td>
                        <td className="px-3 py-2.5 text-right text-ink tabular">{num(views)}</td>
                        <td className={cn("px-3 py-2.5 text-right tabular", above ? "text-good" : below ? "text-bad" : "text-ink-3")}>
                          {above ? "▲ " : below ? "▼ " : ""}{idx.toFixed(1)}×
                        </td>
                        <td className="px-3 py-2.5 text-right text-ink-2 tabular">{views ? (shareRate * 1000).toFixed(1) : "—"}</td>
                        <td className="px-3 py-2.5 text-right text-ink-2 tabular">{pct(completion)}</td>
                        <td className="px-3 py-2.5 text-right text-ink-2 tabular">{s?.avg_watch_s ? duration(Number(s.avg_watch_s)) : "—"}</td>
                        <td className="px-5 py-2.5 text-right text-ink-3">{shortDate(v.posted_at)}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </Panel>
        <ImportStats channels={channels.map((c) => ({ id: c.id, name: c.name }))} defaultChannel={channel?.id} />
      </div>
    </>
  );
}
