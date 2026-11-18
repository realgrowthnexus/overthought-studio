import { notFound } from "next/navigation";
import { getAccounts, getChannelBySlug, getIdeas, getLatestStats, getStatsSeries, getVideos, getEvents, getChannels } from "@/lib/data";
import { Panel, PanelHeader, KV } from "@/components/ui/primitives";
import { TrendChart } from "@/components/charts/trend-chart";
import { VideoList } from "@/components/video-list";
import { EventFeed } from "@/components/event-feed";
import { LiveRefresh } from "@/components/live";
import { dailyTotals } from "@/lib/series";
import { num, pct } from "@/lib/format";

export const dynamic = "force-dynamic";

const MODE = { draft: "To TikTok drafts (you tap Post)", private: "Private post (only me)", public: "Public post" } as const;

export default async function ChannelOverview({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const channel = await getChannelBySlug(slug);
  if (!channel) notFound();
  const since = new Date(Date.now() - 30 * 86400000).toISOString();
  const [series, videos, ideas, accounts, events, channels] = await Promise.all([
    getStatsSeries(since, channel.id),
    getVideos({ channelId: channel.id, limit: 8 }),
    getIdeas(channel.id),
    getAccounts(),
    getEvents({ channelId: channel.id, limit: 10 }),
    getChannels(),
  ]);
  const stats = await getLatestStats(videos.map((v) => v.id));
  const data = dailyTotals(series.stats, 30);
  const account = accounts.find((a) => a.id === channel.tiktok_account_id);
  const freshIdeas = ideas.filter((i) => i.status === "new").length;
  const pillars = channel.content.pillars ?? [];
  const pillarTotal = pillars.reduce((s, p) => s + p.weight, 0) || 1;

  return (
    <>
      <LiveRefresh tables={["videos", "events"]} filter={`channel_id=eq.${channel.id}`} />
      <div className="grid grid-cols-1 items-start [&>*]:min-w-0 gap-6 lg:grid-cols-[1.6fr_1fr]">
        <Panel>
          <PanelHeader title="Last 30 days" description="Totals across every posted video on this channel." />
          <TrendChart data={data} />
          <div className="h-4" />
        </Panel>
        <Panel>
          <PanelHeader title="At a glance" />
          <dl className="divide-y divide-line px-5 pb-3">
            <KV k="Followers" v={account ? num(account.follower_count) : "—"} />
            <KV k="Schedule" v={`${channel.posts_per_day}/day at ${[...channel.post_times].sort().join(", ")}`} />
            <KV k="Length" v={`${channel.min_seconds}–${channel.max_seconds}s`} />
            <KV k="Delivery" v={MODE[channel.posting_mode]} />
            <KV k="Approval" v={channel.require_approval ? "You approve each video" : "Posts without review"} />
            <KV k="Ideas waiting" v={num(freshIdeas)} />
            <KV
              k="Content mix"
              v={pillars.length ? pillars.map((p) => `${p.name} ${pct(p.weight / pillarTotal)}`).join(" · ") : "—"}
            />
          </dl>
        </Panel>
      </div>
      <div className="mt-6 grid grid-cols-1 items-start [&>*]:min-w-0 gap-6 lg:grid-cols-[1.6fr_1fr]">
        <Panel className="overflow-hidden">
          <PanelHeader title="Latest videos" />
          <VideoList videos={videos} channels={channels} stats={stats} showChannel={false} emptyText="Switch the channel on, or press “Make a video now”." />
        </Panel>
        <Panel>
          <PanelHeader title="Activity" />
          <EventFeed events={events} channels={channels} compact />
        </Panel>
      </div>
    </>
  );
}
