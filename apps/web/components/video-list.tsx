import Link from "next/link";
import type { Channel, Video, VideoStat } from "@/lib/types";
import { Badge } from "@/components/ui/primitives";
import { STATUS_LABEL, dateTime, duration, num, relTime, videoTone } from "@/lib/format";
import { EmptyState } from "@/components/ui/empty";

export function VideoList({
  videos, channels, stats, showChannel = true, emptyText,
}: { videos: Video[]; channels: Channel[]; stats?: Map<string, VideoStat>; showChannel?: boolean; emptyText?: string }) {
  const byId = new Map(channels.map((c) => [c.id, c]));
  if (!videos.length) {
    return <EmptyState title="No videos here" figure={false}>{emptyText ?? "Videos appear as soon as the worker starts one."}</EmptyState>;
  }
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[720px] text-[13px]">
        <thead>
          <tr className="border-b border-line text-left text-[12px] whitespace-nowrap text-ink-3">
            <th className="px-5 py-2.5 font-medium">Video</th>
            {showChannel && <th className="px-3 py-2.5 font-medium">Channel</th>}
            <th className="px-3 py-2.5 font-medium">Status</th>
            <th className="px-3 py-2.5 text-right font-medium">Length</th>
            <th className="px-3 py-2.5 text-right font-medium">Views</th>
            <th className="px-3 py-2.5 text-right font-medium">Cost</th>
            <th className="px-5 py-2.5 text-right font-medium">When</th>
          </tr>
        </thead>
        <tbody>
          {videos.map((v) => {
            const ch = byId.get(v.channel_id);
            const s = stats?.get(v.id);
            const when = v.posted_at ? `Posted ${dateTime(v.posted_at, ch?.timezone)}` : v.scheduled_for ? `Due ${dateTime(v.scheduled_for, ch?.timezone)}` : `Started ${relTime(v.created_at)}`;
            return (
              <tr key={v.id} className="group relative border-b border-line last:border-b-0 hover:bg-elev-2/50">
                <td className="max-w-[360px] px-5 py-3">
                  <Link href={`/videos/${v.id}`} className="block truncate font-medium text-ink after:absolute after:inset-0">
                    {v.title || "Untitled idea"}
                  </Link>
                  {v.error && v.status === "failed" && <p className="mt-0.5 truncate text-[12px] text-bad">{v.error}</p>}
                  {v.stage_detail && v.status !== "failed" && v.status !== "posted" && <p className="mt-0.5 truncate text-[12px] text-ink-3">{v.stage_detail}</p>}
                </td>
                {showChannel && (
                  <td className="px-3 py-3">
                    <span className="inline-flex items-center gap-1.5 text-ink-2">
                      <span className="size-2 rounded-full" style={{ background: ch?.color }} aria-hidden />{ch?.name ?? "—"}
                    </span>
                  </td>
                )}
                <td className="px-3 py-3"><Badge tone={videoTone(v.status)} dot live={["researching", "scripting", "fact_checking", "visuals", "voice", "rendering", "uploading"].includes(v.status)}>{STATUS_LABEL[v.status]}</Badge></td>
                <td className="px-3 py-3 text-right text-ink-2 tabular">{duration(v.duration_s)}</td>
                <td className="px-3 py-3 text-right text-ink tabular">{s ? num(s.views) : "—"}</td>
                <td className="px-3 py-3 text-right text-ink-2 tabular">{v.cost_usd ? `$${Number(v.cost_usd).toFixed(2)}` : "—"}</td>
                <td className="px-5 py-3 text-right whitespace-nowrap text-ink-3">{when}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
