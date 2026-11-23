import type { Metadata } from "next";
import Link from "next/link";
import { Plus } from "lucide-react";
import { getAccounts, getChannels, getLatestStats, getVideos } from "@/lib/data";
import { PageHeader, Panel, Badge } from "@/components/ui/primitives";
import { ButtonLink } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty";
import { ChannelToggle } from "@/components/channel-toggle";
import { LiveRefresh } from "@/components/live";
import { cn, holdTone, num, relTime } from "@/lib/format";

export const metadata: Metadata = { title: "Channels" };
export const dynamic = "force-dynamic";

const MODE_LABEL = { draft: "Sends to TikTok drafts", private: "Posts privately", public: "Posts publicly" } as const;

export default async function ChannelsPage() {
  const [channels, accounts, posted] = await Promise.all([
    getChannels(),
    getAccounts(),
    getVideos({ statuses: ["posted", "sent_to_drafts"], order: "posted", limit: 300 }),
  ]);
  const weekAgo = new Date(Date.now() - 7 * 86400000).toISOString();
  const recent = posted.filter((v) => v.posted_at && v.posted_at >= weekAgo);
  const stats = await getLatestStats(recent.map((v) => v.id));

  return (
    <>
      <LiveRefresh tables={["channels"]} />
      <PageHeader
        title="Channels"
        description="Each channel is one TikTok account with its own topic, look, voice and schedule."
        actions={<ButtonLink href="/channels/new" variant="primary"><Plus className="size-4" aria-hidden />New channel</ButtonLink>}
      />
      {channels.length === 0 ? (
        <Panel>
          <EmptyState title="No channels yet" action={<ButtonLink href="/channels/new" variant="primary">Create your first channel</ButtonLink>}>
            Start with Overthought: psychology explained with stick figures. You can add up to five more later.
          </EmptyState>
        </Panel>
      ) : (
        <Panel as="div" className="overflow-hidden">
          <ul className="divide-y divide-line">
            {channels.map((c) => {
              const account = accounts.find((a) => a.id === c.tiktok_account_id);
              const last = posted.find((v) => v.channel_id === c.id);
              const views = recent.filter((v) => v.channel_id === c.id).reduce((s, v) => s + (stats.get(v.id)?.views ?? 0), 0);
              return (
                <li key={c.id} className="group relative grid grid-cols-[auto_1fr_auto] items-center gap-x-4 gap-y-3 px-5 py-4 transition-colors hover:bg-elev-2/40 md:grid-cols-[auto_minmax(0,1.6fr)_repeat(3,minmax(0,1fr))_auto]">
                  <span className="h-10 w-1.5 rounded-full" style={{ background: c.color }} aria-hidden />
                  <div className="min-w-0">
                    <Link href={`/channels/${c.slug}`} className="text-[15px] font-semibold text-ink after:absolute after:inset-0 hover:underline">
                      {c.name}
                    </Link>
                    <p className="truncate text-[13px] text-ink-3">{c.niche}</p>
                    {c.blocked_reason && <p className={cn("mt-1 text-[12px]", holdTone(c.blocked_reason) === "bad" ? "text-bad" : "text-warn")}>On hold: {c.blocked_reason}</p>}
                  </div>
                  <div className="hidden text-[13px] md:block">
                    <p className="text-ink">{account ? `@${account.username ?? account.display_name}` : <span className="text-ink-3">No account linked</span>}</p>
                    <p className="text-ink-3">{MODE_LABEL[c.posting_mode]}</p>
                  </div>
                  <div className="hidden text-[13px] md:block">
                    <p className="text-ink tabular">{c.posts_per_day}/day</p>
                    <p className="text-ink-3">Last post {relTime(last?.posted_at)}</p>
                  </div>
                  <div className="hidden text-[13px] md:block">
                    <p className="text-ink tabular">{num(views)}</p>
                    <p className="text-ink-3">views, 7 days</p>
                  </div>
                  <div className="relative z-[1] flex items-center gap-3">
                    {c.blocked_reason ? <Badge tone={holdTone(c.blocked_reason)} dot>On hold</Badge> : c.status === "active" ? <Badge tone="good" dot live>Running</Badge> : <Badge dot>Paused</Badge>}
                    <ChannelToggle id={c.id} status={c.status} />
                  </div>
                </li>
              );
            })}
          </ul>
        </Panel>
      )}
    </>
  );
}
