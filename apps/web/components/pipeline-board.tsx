import Link from "next/link";
import type { Channel, Video } from "@/lib/types";
import { PIPELINE, cn, relTime } from "@/lib/format";

/**
 * The studio's assembly line: every video in production sits in the column of its current stage.
 * This is the one bold element on the overview.
 */
export function PipelineBoard({ videos, channels }: { videos: Video[]; channels: Channel[] }) {
  const byId = new Map(channels.map((c) => [c.id, c]));
  const columns = PIPELINE.map((stage) => ({ ...stage, items: videos.filter((v) => v.status === stage.key) }));
  const total = videos.length;

  return (
    <div className="relative">
      <div className="overflow-x-auto pb-1">
        <ol className="grid min-w-[880px] grid-cols-8">
          {columns.map((col, i) => (
            <li key={col.key} className="relative flex min-h-[188px] flex-col px-2 first:pl-5 last:pr-5">
              <div className="mb-3 flex items-center gap-2 pt-1">
                <span
                  className={cn(
                    "flex size-5 items-center justify-center rounded-full border text-[10px] font-semibold tabular",
                    col.items.length ? "border-accent bg-accent text-accent-ink" : "border-line-strong text-ink-3",
                  )}
                  aria-hidden
                >
                  {i + 1}
                </span>
                <span className={cn("text-[12px]", col.items.length ? "text-ink" : "text-ink-3")}>{col.label}</span>
                {i < columns.length - 1 && <span className="ml-1 h-px flex-1 bg-line" aria-hidden />}
              </div>
              <div className="flex flex-col gap-2">
                {col.items.slice(0, 4).map((v) => {
                  const ch = byId.get(v.channel_id);
                  const live = v.status !== "ready" && v.status !== "queued";
                  return (
                    <Link
                      key={v.id}
                      href={`/videos/${v.id}`}
                      className="group rounded-[10px] border border-line bg-bg p-2.5 transition-[border-color,transform] duration-150 hover:-translate-y-px hover:border-line-strong"
                    >
                      <div className="flex items-center gap-1.5">
                        <span className="size-2 shrink-0 rounded-full" style={{ background: ch?.color ?? "var(--ink-3)" }} aria-hidden />
                        <span className="truncate text-[11px] text-ink-3">{ch?.name ?? "Channel"}</span>
                      </div>
                      <p className="mt-1 line-clamp-2 text-[12.5px] leading-snug text-ink">{v.title || "Untitled idea"}</p>
                      {live ? (
                        <div className="mt-2 h-1 overflow-hidden rounded-full bg-elev-2">
                          <div className="progress-live h-full rounded-full bg-accent-mark" style={{ width: `${Math.max(8, v.progress)}%` }} />
                        </div>
                      ) : (
                        <p className="mt-1.5 text-[11px] text-ink-3">{v.status === "ready" ? "Waiting for your review" : `Queued ${relTime(v.created_at)}`}</p>
                      )}
                    </Link>
                  );
                })}
                {col.items.length > 4 && <span className="px-1 text-[11px] text-ink-3">+{col.items.length - 4} more</span>}
              </div>
            </li>
          ))}
        </ol>
      </div>
      {total === 0 && (
        <p className="pointer-events-none absolute inset-x-0 top-[92px] text-center font-hand text-[17px] text-ink-3">
          nothing on the line right now. the worker fills it on schedule.
        </p>
      )}
    </div>
  );
}
