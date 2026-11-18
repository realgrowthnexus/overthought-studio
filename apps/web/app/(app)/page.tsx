import Link from "next/link";
import {
  getAccountStats, getAccounts, getChannels, getEvents, getLatestStats, getServices, getSettings, getSpendSince, getVideos,
} from "@/lib/data";
import { Panel, PanelHeader, PageHeader, Badge } from "@/components/ui/primitives";
import { ButtonLink } from "@/components/ui/button";
import { StatTile } from "@/components/stat";
import { PauseSwitch } from "@/components/pause-switch";
import { PipelineBoard } from "@/components/pipeline-board";
import { ServiceStrip } from "@/components/services";
import { EventFeed } from "@/components/event-feed";
import { LiveRefresh } from "@/components/live";
import { EmptyState } from "@/components/ui/empty";
import { IN_PROGRESS, STATUS_LABEL, dateTime, num, usd, videoTone } from "@/lib/format";

export const dynamic = "force-dynamic";

export default async function OverviewPage() {
  const now = Date.now();
  const weekAgo = new Date(now - 7 * 86400000).toISOString();
  const monthStart = new Date(new Date().getFullYear(), new Date().getMonth(), 1).toISOString();

  const [settings, services, channels, accounts, inProgress, upcoming, posted, events, spend, accountStats] = await Promise.all([
    getSettings(),
    getServices(),
    getChannels(),
    getAccounts(),
    getVideos({ statuses: [...IN_PROGRESS, "ready"], limit: 60 }),
    getVideos({ statuses: ["ready", "approved", "scheduled", "sent_to_drafts"], order: "scheduled", limit: 8 }),
    getVideos({ statuses: ["posted", "sent_to_drafts"], order: "posted", limit: 100 }),
    getEvents({ limit: 12 }),
    getSpendSince(monthStart),
    getAccountStats(new Date(now - 8 * 86400000).toISOString()),
  ]);

  const postedThisWeek = posted.filter((v) => v.posted_at && v.posted_at >= weekAgo);
  const stats = await getLatestStats(postedThisWeek.map((v) => v.id));
  const views7d = postedThisWeek.reduce((sum, v) => sum + (stats.get(v.id)?.views ?? 0), 0);

  const followers = accounts.reduce((s, a) => s + (a.follower_count ?? 0), 0);
  const followersWeekAgo = accounts.reduce((s, a) => {
    const old = accountStats.find((r) => r.tiktok_account_id === a.id);
    return s + (old?.follower_count ?? a.follower_count ?? 0);
  }, 0);
  const followerDelta = followers - followersWeekAgo;

  const spendMonth = spend.reduce((s, r) => s + Number(r.amount_usd || 0), 0);
  const active = channels.filter((c) => c.status === "active");
  const blocked = channels.filter((c) => c.blocked_reason);
  const nextPost = upcoming.find((v) => v.scheduled_for);
  const awaitingReview = inProgress.filter((v) => v.status === "ready").length;

  const summary = [
    `${active.length} of ${channels.length} channel${channels.length === 1 ? "" : "s"} running`,
    `${inProgress.filter((v) => v.status !== "ready").length} in production`,
    awaitingReview ? `${awaitingReview} waiting for your review` : null,
    nextPost ? `next post ${dateTime(nextPost.scheduled_for)} ET` : null,
  ].filter(Boolean).join(", ");

  return (
    <>
      <LiveRefresh tables={["videos", "events", "channels"]} />
      <PageHeader
        title="Overview"
        description={channels.length ? `${summary}.` : "Set up your first channel to get the line moving."}
        actions={<PauseSwitch paused={settings.paused} />}
      />

      {channels.length === 0 ? (
        <Panel className="mb-6">
          <EmptyState
            title="No channels yet"
            action={<ButtonLink href="/channels/new" variant="primary">Create a channel</ButtonLink>}
          >
            A channel is one TikTok account with its own topic, look and voice. Create it here, connect the TikTok account, then switch it on.
          </EmptyState>
        </Panel>
      ) : null}

      <Panel className="mb-6 grid grid-cols-2 gap-px overflow-hidden bg-line lg:grid-cols-4">
        <StatTile className="bg-elev" label="Views, last 7 days" value={num(views7d)} foot={`${postedThisWeek.length} video${postedThisWeek.length === 1 ? "" : "s"} posted this week`} />
        <StatTile
          className="bg-elev"
          label="Followers"
          value={num(followers)}
          delta={followerDelta ? `${followerDelta > 0 ? "+" : ""}${num(followerDelta)} this week` : undefined}
          deltaTone={followerDelta > 0 ? "good" : followerDelta < 0 ? "bad" : "neutral"}
          foot={`${accounts.length} account${accounts.length === 1 ? "" : "s"} connected`}
        />
        <StatTile
          className="bg-elev"
          label="Waiting for review"
          value={num(awaitingReview)}
          foot={awaitingReview ? <Link href="/videos?status=ready" className="underline decoration-accent decoration-2 underline-offset-4 hover:text-ink">Review now</Link> : "You're all caught up"}
        />
        <StatTile
          className="bg-elev"
          label="Spend this month"
          value={usd(spendMonth)}
          meter={{ value: spendMonth, max: settings.monthly_budget_usd }}
          foot={`Budget ${usd(settings.monthly_budget_usd, 0)}`}
        />
      </Panel>

      {blocked.length > 0 && (
        <Panel className="mb-6 border-bad/30">
          <PanelHeader title="Channels on hold" description="The worker stopped these for a reason it can't fix by itself." />
          <ul className="px-5 pb-4">
            {blocked.map((c) => (
              <li key={c.id} className="flex items-start justify-between gap-4 border-t border-line py-3 first:border-t-0">
                <div>
                  <Link href={`/channels/${c.slug}`} className="text-[14px] font-medium text-ink hover:underline">{c.name}</Link>
                  <p className="mt-0.5 text-[13px] text-bad">{c.blocked_reason}</p>
                </div>
                <ButtonLink href={`/channels/${c.slug}/settings`} size="sm">Open</ButtonLink>
              </li>
            ))}
          </ul>
        </Panel>
      )}

      <Panel className="mb-6">
        <PanelHeader
          title="Production line"
          description="Every video moves left to right. Updates live as the worker finishes each step."
          action={<ButtonLink href="/videos" size="sm" variant="ghost">All videos</ButtonLink>}
        />
        <PipelineBoard videos={inProgress} channels={channels} />
      </Panel>

      <div className="mb-6 grid grid-cols-1 [&>*]:min-w-0 items-start gap-6 lg:grid-cols-[1.25fr_1fr]">
        <Panel>
          <PanelHeader title="Up next" description="Ready, approved and scheduled posts in the order they'll go out." />
          {upcoming.length === 0 ? (
            <p className="px-5 pb-5 text-[13px] text-ink-3">Nothing queued to post. Finished videos land here first.</p>
          ) : (
            <ul className="px-2 pb-2">
              {upcoming.map((v) => {
                const ch = channels.find((c) => c.id === v.channel_id);
                return (
                  <li key={v.id}>
                    <Link href={`/videos/${v.id}`} className="flex items-center gap-3 rounded-[10px] px-3 py-2.5 transition-colors hover:bg-elev-2">
                      <span className="size-2 shrink-0 rounded-full" style={{ background: ch?.color }} aria-hidden />
                      <span className="min-w-0 flex-1">
                        <span className="block truncate text-[14px] text-ink">{v.title || "Untitled"}</span>
                        <span className="block text-[12px] text-ink-3">{ch?.name} · {v.scheduled_for ? `${dateTime(v.scheduled_for, ch?.timezone)} ET` : "next free slot"}</span>
                      </span>
                      <Badge tone={videoTone(v.status)}>{STATUS_LABEL[v.status]}</Badge>
                    </Link>
                  </li>
                );
              })}
            </ul>
          )}
        </Panel>
        <Panel>
          <PanelHeader title="Recent activity" action={<ButtonLink href="/logs" size="sm" variant="ghost">All activity</ButtonLink>} />
          <EventFeed events={events} channels={channels} compact />
        </Panel>
      </div>

      <Panel>
        <PanelHeader
          title="Services"
          description="What the studio depends on. If one stops, the red bar at the top says why and how to fix it."
          action={<ButtonLink href="/settings#keys" size="sm" variant="ghost">Manage keys</ButtonLink>}
        />
        <ServiceStrip initial={services} />
      </Panel>
    </>
  );
}
