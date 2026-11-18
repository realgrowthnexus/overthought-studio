import Link from "next/link";
import type { Channel, StudioEvent } from "@/lib/types";
import { cn, relTime } from "@/lib/format";

const levelDot: Record<string, string> = {
  debug: "bg-ink-3", info: "bg-ink-3", warn: "bg-warn", error: "bg-bad", success: "bg-good",
};

export function EventFeed({ events, channels, compact }: { events: StudioEvent[]; channels: Channel[]; compact?: boolean }) {
  const byId = new Map(channels.map((c) => [c.id, c]));
  if (!events.length) {
    return <p className="px-5 pb-5 text-[13px] text-ink-3">No activity yet. Events from the worker and your actions show up here.</p>;
  }
  return (
    <ol className="relative px-5 pb-4">
      <span className="absolute top-2 bottom-6 left-[23px] w-px bg-line" aria-hidden />
      {events.map((e) => {
        const ch = e.channel_id ? byId.get(e.channel_id) : null;
        return (
          <li key={e.id} className="relative flex gap-3 py-2">
            <span className={cn("relative z-[1] mt-[6px] size-[7px] shrink-0 rounded-full ring-4 ring-[var(--bg-elev)]", levelDot[e.level] ?? "bg-ink-3")} aria-hidden />
            <div className="min-w-0 flex-1">
              <p className={cn("text-[13px] leading-snug", e.level === "error" ? "text-bad" : "text-ink")}>
                {e.video_id ? <Link href={`/videos/${e.video_id}`} className="hover:underline">{e.message}</Link> : e.message}
              </p>
              <p className="mt-0.5 text-[11px] text-ink-3">
                {relTime(e.created_at)}
                {ch && <> · {ch.name}</>}
                {!compact && e.scope !== "system" && <> · {e.scope}</>}
              </p>
            </div>
          </li>
        );
      })}
    </ol>
  );
}
