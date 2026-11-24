import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { ChevronLeft, ExternalLink } from "lucide-react";
import { getChannels, getEvents, getLatestStats, getVideo } from "@/lib/data";
import { serviceClient } from "@/lib/supabase/service";
import { requireAdmin } from "@/lib/auth";
import { Badge, KV, PageHeader, Panel, PanelHeader, Progress } from "@/components/ui/primitives";
import { EventFeed } from "@/components/event-feed";
import { LiveRefresh } from "@/components/live";
import { VideoActions, CaptionEditor } from "@/components/video-actions";
import { MarginNote } from "@/components/brand";
import { IN_PROGRESS, SERVICE_LABEL, dateTime, duration, num, pct, usd, videoStatusLabel, videoTone } from "@/lib/format";
import type { ScriptBeat, ServiceName, Source } from "@/lib/types";

export const metadata: Metadata = { title: "Video" };
export const dynamic = "force-dynamic";

async function signed(path: string | null) {
  if (!path) return null;
  await requireAdmin();
  const { data } = await serviceClient().storage.from("videos").createSignedUrl(path, 60 * 60);
  return data?.signedUrl ?? null;
}

const sentence = (k: string) => {
  const t = k.replace(/_/g, " ");
  return t.charAt(0).toUpperCase() + t.slice(1);
};
const costLabel = (k: string) => SERVICE_LABEL[k as ServiceName] ?? sentence(k);

function sourceLine(s: Source) {
  return s.citation || [s.researcher, s.institution, s.year].filter(Boolean).join(" · ");
}

function onScreenText(v: unknown): string | null {
  if (!v) return null;
  if (typeof v === "string") return v;
  if (Array.isArray(v)) return v.map(onScreenText).filter(Boolean).join(" / ");
  if (typeof v === "object") {
    const o = v as Record<string, unknown>;
    return ["top", "text", "line", "bottom", "punchline"].map((k) => o[k]).filter((x) => typeof x === "string").join(" / ") || null;
  }
  return String(v);
}

export default async function VideoPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const video = await getVideo(id);
  if (!video) notFound();
  const [channels, events, statsMap, videoUrl, thumbUrl] = await Promise.all([
    getChannels(),
    getEvents({ videoId: video.id, limit: 40 }),
    getLatestStats([video.id]),
    signed(video.video_path),
    signed(video.thumb_path),
  ]);
  const channel = channels.find((c) => c.id === video.channel_id);
  const stats = statsMap.get(video.id);
  const beats = (video.script?.beats ?? []) as ScriptBeat[];
  const sources = (video.script?.sources ?? (video.research?.sources as Source[] | undefined) ?? []) as Source[];
  const scorecard = (video.scorecard ?? {}) as Record<string, unknown>;
  const factcheck = (video.factcheck ?? {}) as Record<string, unknown>;
  const claims = (Array.isArray(factcheck.claims) ? factcheck.claims : []) as Record<string, unknown>[];
  const problems = (Array.isArray(factcheck.problems) ? factcheck.problems : []) as Record<string, unknown>[];
  const fcPassed = factcheck.passed ?? factcheck.pass ?? (typeof factcheck.verdict === "string" ? /pass/i.test(factcheck.verdict as string) : undefined);
  const inProgress = IN_PROGRESS.includes(video.status);
  const costs = Object.entries(video.cost_breakdown ?? {}).filter(([, v]) => Number(v) > 0);

  return (
    <>
      <LiveRefresh tables={["videos", "events"]} filter={`id=eq.${video.id}`} />
      <PageHeader
        back={<Link href={channel ? `/channels/${channel.slug}/videos` : "/videos"} className="inline-flex items-center gap-1 text-[13px] text-ink-3 hover:text-ink"><ChevronLeft className="size-4" />{channel?.name ?? "Videos"}</Link>}
        title={video.title || "Untitled idea"}
        description={
          <span className="flex flex-wrap items-center gap-2">
            <Badge tone={videoTone(video.status, video.error)} dot live={inProgress}>{videoStatusLabel(video.status, video.error)}</Badge>
            {video.duration_s ? <span>{duration(video.duration_s)}</span> : null}
            {video.script_version ? <span>· script v{video.script_version}</span> : null}
            {video.tiktok_url && (
              <a href={video.tiktok_url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-ink-2 underline decoration-accent-mark decoration-2 underline-offset-4 hover:text-ink">
                View on TikTok<ExternalLink className="size-3.5" aria-hidden />
              </a>
            )}
          </span>
        }
      />

      {video.status === "failed" && video.error && (
        <div className="mb-6 rounded-[12px] border border-bad/30 bg-bad-soft px-4 py-3 text-[13px] text-ink">
          <strong className="font-semibold text-bad">Failed:</strong> {video.error}
          <span className="mt-1 block text-ink-3">Use “Make again” to retry from the step that failed, or from the start.</span>
        </div>
      )}
      {video.rejection_note && video.status === "rejected" && (
        <div className="mb-6 rounded-[12px] border border-line bg-elev px-4 py-3 text-[13px] text-ink-2">
          <strong className="font-semibold text-ink">Your note:</strong> {video.rejection_note}
        </div>
      )}

      <div className="grid grid-cols-1 [&>*]:min-w-0 gap-6 lg:grid-cols-[minmax(280px,360px)_1fr]">
        <div className="flex flex-col gap-4 lg:sticky lg:top-6 lg:self-start">
          <div className="dark relative mx-auto aspect-[9/16] w-full max-w-[360px] overflow-hidden rounded-[18px] border border-line bg-bg shadow-[var(--shadow)]">
            {videoUrl ? (
              <video src={videoUrl} poster={thumbUrl ?? undefined} controls playsInline preload="metadata" className="h-full w-full object-contain" />
            ) : thumbUrl ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={thumbUrl} alt="" className="h-full w-full object-cover" />
            ) : (
              <div className="flex h-full flex-col items-center justify-center gap-4 p-8 text-center">
                <p className="font-hand text-[18px] text-ink">{inProgress ? "still being made…" : "no video file"}</p>
                {inProgress && <Progress value={video.progress} live className="max-w-[200px]" />}
                {video.stage_detail && <p className="text-[12px] text-ink-3">{video.stage_detail}</p>}
              </div>
            )}
          </div>
          <VideoActions video={video} />
        </div>

        <div className="flex min-w-0 flex-col gap-6">
          {stats && (
            <Panel className="grid grid-cols-3 gap-px overflow-hidden bg-line sm:grid-cols-6">
              {([
                ["Views", num(stats.views)], ["Likes", num(stats.likes)], ["Comments", num(stats.comments)],
                ["Shares", num(stats.shares)], ["Avg watch", stats.avg_watch_s ? `${Number(stats.avg_watch_s).toFixed(1)}s` : "—"],
                ["Watched full", pct(stats.completion_rate)],
              ] as const).map(([k, val]) => (
                <div key={k} className="bg-elev px-4 py-3">
                  <p className="text-[12px] text-ink-3">{k}</p>
                  <p className="mt-0.5 text-[18px] font-semibold text-ink tabular">{val}</p>
                </div>
              ))}
            </Panel>
          )}

          <CaptionEditor video={video} />

          <Panel>
            <PanelHeader title="Script" description={video.script?.hook || beats.length ? undefined : "Appears once the writer finishes."} />
            {video.script?.hook && (
              <div className="px-5 pb-2">
                <p className="text-[12px] text-ink-3">Hook</p>
                <p className="mt-0.5 text-[17px] leading-snug font-medium text-ink">“{video.script.hook}”</p>
              </div>
            )}
            {beats.length > 0 && (
              <ol className="px-5 pt-2 pb-4">
                {beats.map((b, i) => {
                  const screen = onScreenText(b.on_screen);
                  return (
                    <li key={i} className="grid grid-cols-[2.5rem_1fr] gap-3 border-t border-line py-3 first:border-t-0">
                      <span className="pt-0.5 text-[12px] text-ink-3 tabular">
                        {typeof b.start === "number" ? duration(b.start) : `#${i + 1}`}
                      </span>
                      <div className="min-w-0">
                        {b.kind && <p className="mb-0.5 text-[11px] text-ink-3">{String(b.kind)}</p>}
                        {b.narration && <p className="text-[14px] leading-relaxed text-ink">{b.narration}</p>}
                        {(screen || b.keyword) && (
                          <p className="mt-1 text-[12px] text-ink-3">
                            On screen: <span className="text-ink-2">{screen}</span>
                            {b.keyword && <> · keyword <span className="font-medium text-accent-text">{String(b.keyword)}</span></>}
                          </p>
                        )}
                        {b.scene && <p className="mt-1 text-[12px] text-ink-3">Scene: {b.scene}</p>}
                      </div>
                    </li>
                  );
                })}
              </ol>
            )}
            {video.script?.loop_line && (
              <div className="border-t border-line px-5 py-3">
                <p className="text-[12px] text-ink-3">Loop line</p>
                <p className="mt-0.5 text-[14px] text-ink">“{video.script.loop_line}”</p>
              </div>
            )}
          </Panel>

          <div className="grid grid-cols-1 [&>*]:min-w-0 gap-6 xl:grid-cols-2">
            <Panel>
              <PanelHeader title="Sources" description="Shown on screen as a margin note." />
              {sources.length ? (
                <ul className="flex flex-col gap-3 px-5 pb-5">
                  {sources.map((s, i) => (
                    <li key={i}>
                      <MarginNote>{sourceLine(s)}</MarginNote>
                      {s.title && <p className="mt-1 pl-11 text-[12px] text-ink-3">{s.url ? <a href={s.url} target="_blank" rel="noreferrer" className="hover:text-ink hover:underline">{s.title}</a> : s.title}</p>}
                      {s.replicated === false && <p className="mt-1 pl-11 text-[12px] text-warn">Didn&apos;t replicate — flagged in the video.</p>}
                    </li>
                  ))}
                </ul>
              ) : <p className="px-5 pb-5 text-[13px] text-ink-3">No sources yet.</p>}
            </Panel>
            <Panel>
              <PanelHeader
                title="Content check"
                description="Tone, graphic content, TikTok rules and length. Facts are not re-checked."
                action={fcPassed === undefined ? null : fcPassed ? <Badge tone="good" dot>Passed</Badge> : <Badge tone="bad" dot>Failed</Badge>}
              />
              {problems.length ? (
                <ul className="flex flex-col divide-y divide-line px-5 pb-4">
                  {problems.map((p, i) => (
                    <li key={i} className="py-2.5 text-[13px]">
                      <p className="text-ink">{String(p.issue ?? "")}</p>
                      {p.fix ? <p className="mt-0.5 text-ink-3">Fix: {String(p.fix)}</p> : null}
                    </li>
                  ))}
                </ul>
              ) : claims.length ? (
                <ul className="flex flex-col divide-y divide-line px-5 pb-4">
                  {claims.map((c, i) => {
                    const ok = c.ok ?? c.supported ?? (typeof c.verdict === "string" ? /support|pass|ok|true/i.test(c.verdict as string) : undefined);
                    return (
                      <li key={i} className="py-2.5 text-[13px]">
                        <p className="text-ink">{String(c.claim ?? c.text ?? "")}</p>
                        <p className={ok === false ? "mt-0.5 text-bad" : "mt-0.5 text-ink-3"}>
                          {ok === false ? "Not supported" : ok ? "Supported" : String(c.verdict ?? "")}
                          {c.note ? ` — ${String(c.note)}` : ""}
                        </p>
                      </li>
                    );
                  })}
                </ul>
              ) : (
                <p className="px-5 pb-5 text-[13px] text-ink-3">{typeof factcheck.summary === "string" ? factcheck.summary : "Runs after the script is written."}</p>
              )}
            </Panel>
          </div>

          <div className="grid grid-cols-1 [&>*]:min-w-0 gap-6 xl:grid-cols-2">
            <Panel>
              <PanelHeader title="Script score" description="Graded before production. Below the bar, the script is rewritten." />
              {Object.keys(scorecard).length ? (
                <dl className="divide-y divide-line px-5 pb-3">
                  {Object.entries(scorecard).filter(([, v]) => typeof v === "number" || typeof v === "string").map(([k, v]) => (
                    <KV key={k} k={sentence(k)} v={typeof v === "number" ? (v <= 10 ? `${v}/10` : String(v)) : String(v)} />
                  ))}
                </dl>
              ) : <p className="px-5 pb-5 text-[13px] text-ink-3">Not scored yet.</p>}
            </Panel>
            <Panel>
              <PanelHeader title="Cost" description={`Total ${usd(video.cost_usd)}`} />
              {!costs.length && <p className="px-5 pb-1 text-[13px] text-ink-3">No spend recorded yet.</p>}
              <dl className="divide-y divide-line px-5 pb-3">
                {costs.map(([k, v]) => <KV key={k} k={costLabel(k)} v={usd(Number(v), 3)} />)}
                <KV k="Created" v={dateTime(video.created_at, channel?.timezone)} />
                {video.scheduled_for && <KV k="Scheduled" v={dateTime(video.scheduled_for, channel?.timezone)} />}
                {video.posted_at && <KV k="Posted" v={dateTime(video.posted_at, channel?.timezone)} />}
              </dl>
            </Panel>
          </div>

          <Panel>
            <PanelHeader title="Timeline" />
            <EventFeed events={events} channels={channels} />
          </Panel>
        </div>
      </div>
    </>
  );
}
