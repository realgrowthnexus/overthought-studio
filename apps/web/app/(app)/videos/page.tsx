import type { Metadata } from "next";
import Link from "next/link";
import { getChannels, getLatestStats, getVideos } from "@/lib/data";
import { PageHeader, Panel } from "@/components/ui/primitives";
import { VideoList } from "@/components/video-list";
import { LiveRefresh } from "@/components/live";
import { IN_PROGRESS, cn } from "@/lib/format";

export const metadata: Metadata = { title: "Videos" };
export const dynamic = "force-dynamic";

const GROUPS: { id: string; label: string; statuses?: string[] }[] = [
  { id: "all", label: "All" },
  { id: "making", label: "In production", statuses: IN_PROGRESS },
  { id: "ready", label: "Needs review", statuses: ["ready"] },
  { id: "queued", label: "Queued to post", statuses: ["approved", "scheduled"] },
  { id: "out", label: "Out", statuses: ["posted", "sent_to_drafts"] },
  { id: "problems", label: "Problems", statuses: ["failed", "blocked", "rejected"] },
];

export default async function VideosPage({ searchParams }: { searchParams: Promise<{ status?: string; channel?: string }> }) {
  const sp = await searchParams;
  const group = GROUPS.find((g) => g.id === sp.status) ?? GROUPS[0];
  const channels = await getChannels();
  const channel = channels.find((c) => c.slug === sp.channel);
  const videos = await getVideos({ statuses: group.statuses, channelId: channel?.id, limit: 300 });
  const stats = await getLatestStats(videos.filter((v) => v.posted_at).map((v) => v.id));

  const href = (patch: { status?: string; channel?: string | null }) => {
    const p = new URLSearchParams();
    const status = patch.status ?? group.id;
    const ch = patch.channel === undefined ? channel?.slug : patch.channel;
    if (status !== "all") p.set("status", status);
    if (ch) p.set("channel", ch);
    const s = p.toString();
    return `/videos${s ? `?${s}` : ""}`;
  };

  return (
    <>
      <LiveRefresh tables={["videos"]} />
      <PageHeader title="Videos" description="Everything the studio has made or is making, newest first." />
      <div className="mb-4 flex flex-col gap-2">
        <nav className="-mx-1 flex gap-1 overflow-x-auto px-1" aria-label="Filter by status">
          {GROUPS.map((g) => (
            <Link
              key={g.id}
              href={href({ status: g.id })}
              aria-current={g.id === group.id ? "page" : undefined}
              className={cn(
                "h-9 shrink-0 rounded-full border px-3.5 text-[13px] leading-[34px] transition-colors",
                g.id === group.id ? "border-ink bg-ink text-bg" : "border-line text-ink-2 hover:border-line-strong",
              )}
            >
              {g.label}
            </Link>
          ))}
        </nav>
        {channels.length > 1 && (
          <nav className="-mx-1 flex gap-1 overflow-x-auto px-1" aria-label="Filter by channel">
            <Link href={href({ channel: null })} className={cn("h-9 shrink-0 rounded-full px-3 text-[13px] leading-9", !channel ? "bg-elev-2 text-ink" : "text-ink-3 hover:text-ink")}>All channels</Link>
            {channels.map((c) => (
              <Link key={c.id} href={href({ channel: c.slug })} className={cn("inline-flex h-9 shrink-0 items-center gap-1.5 rounded-full px-3 text-[13px]", channel?.id === c.id ? "bg-elev-2 text-ink" : "text-ink-3 hover:text-ink")}>
                <span className="size-2 rounded-full" style={{ background: c.color }} aria-hidden />{c.name}
              </Link>
            ))}
          </nav>
        )}
      </div>
      <Panel className="overflow-hidden">
        <VideoList videos={videos} channels={channels} stats={stats} emptyText={group.id === "ready" ? "Nothing waiting for review. Nice." : undefined} />
      </Panel>
    </>
  );
}
