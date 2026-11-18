import type { Metadata } from "next";
import Link from "next/link";
import { getChannels, getEvents, getJobs } from "@/lib/data";
import { PageHeader, Panel, PanelHeader, Badge } from "@/components/ui/primitives";
import { EventFeed } from "@/components/event-feed";
import { LiveRefresh } from "@/components/live";
import { JobRowActions } from "@/components/job-row-actions";
import { cn, relTime, type Tone } from "@/lib/format";
import type { JobStatus } from "@/lib/types";

export const metadata: Metadata = { title: "Activity" };
export const dynamic = "force-dynamic";

const LEVELS = ["all", "error", "warn", "success", "info"] as const;
const JOB_TONE: Record<JobStatus, Tone> = { queued: "neutral", running: "warn", done: "good", failed: "bad", cancelled: "neutral", waiting: "info" };
const JOB_NAME: Record<string, string> = {
  plan_channel: "Plan next video", produce_video: "Make video", research_ideas: "Research ideas", publish_video: "Publish",
  check_publish: "Check publish status", sync_stats: "Sync stats", import_stats: "Import stats", weekly_review: "Weekly review",
  health_check: "Health check", refresh_tokens: "Refresh TikTok logins", backup_db: "Back up database", cleanup_storage: "Clean up storage",
};

export default async function LogsPage({ searchParams }: { searchParams: Promise<{ level?: string; channel?: string; jobs?: string }> }) {
  const sp = await searchParams;
  const level = LEVELS.find((l) => l === sp.level) ?? "all";
  const channels = await getChannels();
  const channel = channels.find((c) => c.slug === sp.channel);
  const jobFilter = sp.jobs === "problems" ? "problems" : "all";
  const [events, jobs] = await Promise.all([
    getEvents({ level: level === "all" ? undefined : level, channelId: channel?.id, limit: 120 }),
    getJobs({ limit: 80 }),
  ]);
  const shownJobs = jobFilter === "problems" ? jobs.filter((j) => j.status === "failed" || j.status === "waiting") : jobs;

  const q = (patch: Record<string, string | null>) => {
    const p = new URLSearchParams();
    const merged = { level: level === "all" ? null : level, channel: channel?.slug ?? null, jobs: jobFilter === "all" ? null : jobFilter, ...patch };
    for (const [k, v] of Object.entries(merged)) if (v && v !== "all") p.set(k, v);
    const s = p.toString();
    return `/logs${s ? `?${s}` : ""}`;
  };

  return (
    <>
      <LiveRefresh tables={["events", "jobs"]} />
      <PageHeader title="Activity" description="What the worker and you did, and the queue of work it's doing next." />
      <div className="grid gap-6 xl:grid-cols-[1fr_1.15fr]">
        <Panel>
          <PanelHeader title="Events" />
          <div className="flex flex-wrap gap-1 px-5 pb-3">
            {LEVELS.map((l) => (
              <Link key={l} href={q({ level: l })} className={cn("h-8 rounded-full px-3 text-[12px] leading-8 capitalize", l === level ? "bg-elev-2 text-ink" : "text-ink-3 hover:text-ink")}>
                {l === "warn" ? "Warnings" : l === "error" ? "Errors" : l === "success" ? "Successes" : l === "info" ? "Info" : "All"}
              </Link>
            ))}
            {channels.length > 1 && <span className="mx-1 my-1.5 w-px bg-line" aria-hidden />}
            {channels.length > 1 && channels.map((c) => (
              <Link key={c.id} href={q({ channel: channel?.id === c.id ? null : c.slug })} className={cn("inline-flex h-8 items-center gap-1.5 rounded-full px-3 text-[12px]", channel?.id === c.id ? "bg-elev-2 text-ink" : "text-ink-3 hover:text-ink")}>
                <span className="size-2 rounded-full" style={{ background: c.color }} aria-hidden />{c.name}
              </Link>
            ))}
          </div>
          <EventFeed events={events} channels={channels} />
        </Panel>
        <Panel className="overflow-hidden">
          <PanelHeader
            title="Work queue"
            description="Jobs the worker claims one by one. “Waiting” means a service is out of credit or down; it resumes by itself."
            action={
              <div className="flex gap-1">
                <Link href={q({ jobs: null })} className={cn("h-8 rounded-full px-3 text-[12px] leading-8", jobFilter === "all" ? "bg-elev-2 text-ink" : "text-ink-3 hover:text-ink")}>All</Link>
                <Link href={q({ jobs: "problems" })} className={cn("h-8 rounded-full px-3 text-[12px] leading-8", jobFilter === "problems" ? "bg-elev-2 text-ink" : "text-ink-3 hover:text-ink")}>Problems</Link>
              </div>
            }
          />
          {shownJobs.length === 0 ? (
            <p className="px-5 pb-5 text-[13px] text-ink-3">The queue is empty.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[620px] text-[13px]">
                <thead>
                  <tr className="border-y border-line text-left text-[12px] text-ink-3">
                    <th className="px-5 py-2 font-medium">Job</th>
                    <th className="px-3 py-2 font-medium">Status</th>
                    <th className="px-3 py-2 text-right font-medium">Tries</th>
                    <th className="px-3 py-2 text-right font-medium">When</th>
                    <th className="px-5 py-2"><span className="sr-only">Actions</span></th>
                  </tr>
                </thead>
                <tbody>
                  {shownJobs.map((j) => {
                    const ch = channels.find((c) => c.id === j.channel_id);
                    return (
                      <tr key={j.id} className="border-b border-line align-top last:border-b-0">
                        <td className="px-5 py-2.5">
                          <p className="text-ink">{JOB_NAME[j.type] ?? j.type}</p>
                          <p className="text-[12px] text-ink-3">
                            #{j.id}{ch ? ` · ${ch.name}` : ""}{j.video_id ? <> · <Link href={`/videos/${j.video_id}`} className="hover:underline">video</Link></> : null}
                          </p>
                          {j.last_error && <p className="mt-1 line-clamp-2 text-[12px] text-bad">{j.last_error}</p>}
                          {j.waiting_on && <p className="mt-1 text-[12px] text-info">Waiting on {j.waiting_on}</p>}
                        </td>
                        <td className="px-3 py-2.5"><Badge tone={JOB_TONE[j.status]} dot live={j.status === "running"}>{j.status}</Badge></td>
                        <td className="px-3 py-2.5 text-right text-ink-2 tabular">{j.attempts}/{j.max_attempts}</td>
                        <td className="px-3 py-2.5 text-right whitespace-nowrap text-ink-3">
                          {j.status === "queued" && new Date(j.run_after).getTime() > Date.now() ? `runs ${relTime(j.run_after)}` : relTime(j.finished_at ?? j.started_at ?? j.created_at)}
                        </td>
                        <td className="px-5 py-2.5 text-right"><JobRowActions id={j.id} status={j.status} /></td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </Panel>
      </div>
    </>
  );
}
