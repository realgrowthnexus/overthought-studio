import Link from "next/link";
import { holdTone } from "@/lib/format";
import { notFound } from "next/navigation";
import { ChevronLeft, Sparkles, Lightbulb, LineChart } from "lucide-react";
import { getAccounts, getChannelBySlug } from "@/lib/data";
import { Badge, PageHeader } from "@/components/ui/primitives";
import { LinkTabs } from "@/components/ui/tabs";
import { JobButton } from "@/components/job-button";
import { ChannelToggle } from "@/components/channel-toggle";

export default async function ChannelLayout({ children, params }: { children: React.ReactNode; params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const channel = await getChannelBySlug(slug);
  if (!channel) notFound();
  const accounts = await getAccounts();
  const account = accounts.find((a) => a.id === channel.tiktok_account_id);
  const base = `/channels/${channel.slug}`;

  return (
    <>
      <PageHeader
        back={<Link href="/channels" className="inline-flex items-center gap-1 text-[13px] text-ink-3 hover:text-ink"><ChevronLeft className="size-4" />Channels</Link>}
        title={
          <span className="flex flex-wrap items-center gap-3">
            <span className="h-7 w-1.5 rounded-full" style={{ background: channel.color }} aria-hidden />
            {channel.name}
            {channel.blocked_reason ? <Badge tone={holdTone(channel.blocked_reason)} dot>On hold</Badge> : channel.status === "active" ? <Badge tone="good" dot live>Running</Badge> : <Badge dot>Paused</Badge>}
          </span>
        }
        description={
          <>
            {channel.niche}
            <span className="block text-[13px]">{account ? <>Posting as <span className="text-ink-2">@{account.username ?? account.display_name}</span></> : <Link href={`${base}/settings#account`} className="underline decoration-accent-mark decoration-2 underline-offset-4 hover:text-ink">Connect a TikTok account</Link>}</span>
          </>
        }
        actions={
          <>
            <JobButton type="plan_channel" channelId={channel.id} payload={{ channel_id: channel.id, force: true }} variant="primary"><Sparkles className="size-4" aria-hidden />Make a video now</JobButton>
            <JobButton type="research_ideas" channelId={channel.id} payload={{ channel_id: channel.id }}><Lightbulb className="size-4" aria-hidden />Research ideas</JobButton>
            <JobButton type="weekly_review" channelId={channel.id} payload={{ channel_id: channel.id }} variant="ghost"><LineChart className="size-4" aria-hidden />Run review</JobButton>
            <span className="ml-1 inline-flex h-10 items-center gap-2.5 rounded-[10px] border border-line bg-elev pr-2 pl-3 text-[13px] text-ink-2">
              {channel.status === "active" ? "On" : "Off"}
              <ChannelToggle id={channel.id} status={channel.status} blockedReason={channel.blocked_reason} />
            </span>
          </>
        }
      />
      {channel.blocked_reason && (
        <p className={holdTone(channel.blocked_reason) === "bad" ? "mb-6 rounded-[12px] border border-bad/30 bg-bad-soft px-4 py-3 text-[13px] text-ink" : "mb-6 rounded-[12px] border border-warn/30 bg-warn-soft px-4 py-3 text-[13px] text-ink"}>
          <strong className={holdTone(channel.blocked_reason) === "bad" ? "font-semibold text-bad" : "font-semibold text-warn"}>On hold:</strong> {channel.blocked_reason}
        </p>
      )}
      <LinkTabs
        layoutId="channel-tabs"
        tabs={[
          { href: base, label: "Overview" },
          { href: `${base}/videos`, label: "Videos" },
          { href: `${base}/ideas`, label: "Idea bank" },
          { href: `${base}/strategy`, label: "Strategy" },
          { href: `${base}/settings`, label: "Settings" },
        ]}
      />
      {children}
    </>
  );
}
