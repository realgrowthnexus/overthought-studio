import type { Metadata } from "next";
import Link from "next/link";
import { Pencil, Plus } from "lucide-react";
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
        <ul className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
          {channels.map((c) => {
            const account = accounts.find((a) => a.id === c.tiktok_account_id);
            const last = posted.find((v) => v.channel_id === c.id);
            const views = recent.filter((v) => v.channel_id === c.id).reduce((s, v) => s + (stats.get(v.id)?.views ?? 0), 0);
            return (
              <li key={c.id}>
                <Panel as="div" className="group relative flex h-full flex-col gap-4 overflow-hidden p-5 transition-colors hover:border-line-input">
                  <span className="absolute inset-x-0 top-0 h-1" style={{ background: c.color }} aria-hidden />
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <Link href={`/channels/${c.slug}`} className="text-[16px] font-semibold text-ink after:absolute after:inset-0 hover:underline">
                        {c.name}
                      </Link>
                      <p className="mt-0.5 line-clamp-2 text-[13px] text-ink-3">{c.niche}</p>
                    </div>
                    {c.blocked_reason ? <Badge tone={holdTone(c.blocked_reason)} dot>On hold</Badge> : c.status === "active" ? <Badge tone="good" dot live>Running</Badge> : <Badge dot>Paused</Badge>}
                  </div>
                  {c.blocked_reason && <p className={cn("text-[12px]", holdTone(c.blocked_reason) === "bad" ? "text-bad" : "text-warn")}>On hold: {c.blocked_reason}</p>}
                  <dl className="grid grid-cols-2 gap-x-4 gap-y-3 text-[13px]">
                    <div className="min-w-0"><dt className="text-ink-3">Account</dt><dd className="truncate text-ink">{account ? `@${account.username ?? account.display_name}` : "Not linked"}</dd></div>
                    <div className="min-w-0"><dt className="text-ink-3">Delivery</dt><dd className="truncate text-ink">{MODE_LABEL[c.posting_mode]}</dd></div>
                    <div><dt className="text-ink-3">Per day</dt><dd className="text-ink tabular">{c.posts_per_day}</dd></div>
                    <div><dt className="text-ink-3">Views, 7 days</dt><dd className="text-ink tabular">{num(views)}</dd></div>
                    <div className="col-span-2"><dt className="text-ink-3">Last post</dt><dd className="text-ink">{relTime(last?.posted_at)}</dd></div>
                  </dl>
                  <div className="relative z-[1] mt-auto flex items-center justify-between gap-3 border-t border-line pt-4">
                    <ButtonLink href={`/channels/${c.slug}/settings`} size="sm"><Pencil className="size-4" aria-hidden />Edit</ButtonLink>
                    <ChannelToggle id={c.id} status={c.status} blockedReason={c.blocked_reason} />
                  </div>
                </Panel>
              </li>
            );
          })}
        </ul>
      )}
    </>
  );
}
