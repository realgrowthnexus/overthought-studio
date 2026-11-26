"use client";
import * as React from "react";
import { CalendarClock, Check, Copy, ImageIcon, Lock } from "lucide-react";
import type { Video } from "@/lib/types";
import { scheduleVideo, setCover, updateTitle } from "@/lib/actions";
import { useAction } from "@/components/use-action";
import { Button } from "@/components/ui/button";
import { Field, Input, Panel, PanelHeader } from "@/components/ui/primitives";

const SCHEDULABLE = ["ready", "approved", "scheduled"];
const ON_TIKTOK = ["uploading", "sent_to_drafts", "posted"];

/** ISO → the value a <input type="datetime-local"> wants, in the viewer's own time zone. */
function toLocalInput(iso: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  const p = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}T${p(d.getHours())}:${p(d.getMinutes())}`;
}

function inZone(iso: string, tz: string) {
  return new Intl.DateTimeFormat("en-US", {
    weekday: "short", month: "short", day: "numeric", hour: "numeric", minute: "2-digit", timeZone: tz, timeZoneName: "short",
  }).format(new Date(iso));
}

export function TitleEditor({ video }: { video: Video }) {
  const { pending, run } = useAction();
  const [title, setTitle] = React.useState(video.title ?? "");
  React.useEffect(() => setTitle(video.title ?? ""), [video.title]);
  const dirty = title.trim() !== (video.title ?? "").trim();
  return (
    <form
      className="flex flex-col gap-2 sm:flex-row sm:items-end"
      onSubmit={(e) => { e.preventDefault(); if (dirty) run(() => updateTitle(video.id, title)); }}
    >
      <div className="min-w-0 flex-1">
      <Field label="Title" htmlFor="video-title" hint="Only for the dashboard. TikTok uses the caption.">
        <Input id="video-title" value={title} maxLength={150} onChange={(e) => setTitle(e.target.value)} />
      </Field>
      </div>
      <Button type="submit" size="sm" variant={dirty ? "primary" : "secondary"} disabled={!dirty} loading={pending} className="sm:mb-[22px]">
        Save title
      </Button>
    </form>
  );
}

export function ScheduleEditor({ video, timezone }: { video: Video; timezone: string }) {
  const { pending, run } = useAction();
  const [value, setValue] = React.useState(toLocalInput(video.scheduled_for));
  React.useEffect(() => setValue(toLocalInput(video.scheduled_for)), [video.scheduled_for]);
  const can = SCHEDULABLE.includes(video.status) && Boolean(video.video_path);
  const iso = value ? new Date(value).toISOString() : null;
  const changed = iso !== (video.scheduled_for ? new Date(video.scheduled_for).toISOString() : null);
  const ready = video.status === "ready";
  const viewerTz = Intl.DateTimeFormat().resolvedOptions().timeZone;

  if (!can) {
    return (
      <p className="text-[13px] text-ink-3">
        {ON_TIKTOK.includes(video.status) ? "Already sent to TikTok." : "You can pick a post time once the video is finished."}
      </p>
    );
  }
  return (
    <div className="flex flex-col gap-3">
      <Field
        label="Post time"
        htmlFor="post-time"
        hint={viewerTz === timezone ? undefined : `In your time (${viewerTz}). The channel runs on ${timezone}.`}
      >
        <Input id="post-time" type="datetime-local" value={value} onChange={(e) => setValue(e.target.value)} />
      </Field>
      {iso && (
        <p className="text-[12px] text-ink-3">
          Channel time: <span className="text-ink-2">{inZone(iso, timezone)}</span>
        </p>
      )}
      {video.schedule_locked && video.scheduled_for && (
        <p className="inline-flex items-center gap-1.5 text-[12px] text-ink-3">
          <Lock className="size-3.5" aria-hidden />You set this time, so the planner won&apos;t move it.
        </p>
      )}
      <div className="flex flex-wrap gap-2">
        <Button size="sm" variant="primary" disabled={!iso || !changed} loading={pending} onClick={() => run(() => scheduleVideo(video.id, iso))}>
          <CalendarClock className="size-4" aria-hidden />{ready ? "Approve and schedule" : "Set post time"}
        </Button>
        {video.scheduled_for && (
          <Button size="sm" variant="ghost" loading={pending} onClick={() => run(() => scheduleVideo(video.id, null), { onOk: () => setValue("") })}>
            Clear (next free slot)
          </Button>
        )}
      </div>
    </div>
  );
}

export function CoverPicker({ video, videoUrl, draft }: { video: Video; videoUrl: string | null; draft: boolean }) {
  const { pending, run } = useAction();
  const ref = React.useRef<HTMLVideoElement>(null);
  const max = Math.max(0, Math.floor((video.duration_s ?? 0) * 1000) - 200);
  const [ms, setMs] = React.useState(video.cover_ms ?? 0);
  React.useEffect(() => setMs(video.cover_ms ?? 0), [video.cover_ms]);
  const locked = ON_TIKTOK.includes(video.status);

  const seek = (t: number) => {
    setMs(t);
    if (ref.current) ref.current.currentTime = t / 1000;
  };
  if (!videoUrl || !max) {
    return <p className="px-5 pb-5 text-[13px] text-ink-3">You can pick a cover once the video is finished.</p>;
  }
  return (
    <div className="flex flex-col gap-3 px-5 pb-5">
      <div className="dark relative mx-auto aspect-[9/16] w-full max-w-[180px] overflow-hidden rounded-[12px] border border-line bg-bg">
        <video
          ref={ref}
          src={videoUrl}
          onLoadedMetadata={(e) => { e.currentTarget.currentTime = (video.cover_ms ?? 0) / 1000; }}
          muted
          playsInline
          preload="auto"
          className="h-full w-full object-contain"
          aria-label="Cover preview"
        />
      </div>
      <label htmlFor="cover-ms" className="text-[12px] text-ink-3">
        Frame at <span className="text-ink tabular">{(ms / 1000).toFixed(1)}s</span>
      </label>
      <input
        id="cover-ms"
        type="range"
        min={0}
        max={max}
        step={100}
        value={ms}
        disabled={locked}
        onChange={(e) => seek(Number(e.target.value))}
        className="w-full accent-[var(--accent)]"
      />
      <p className="text-[12px] text-ink-3">
        {draft
          ? "This updates the dashboard thumbnail. TikTok drafts don't take a cover from us: pick it in the TikTok app before you post."
          : "TikTok uses this frame as the cover when it posts."}
      </p>
      <div className="flex justify-end">
        <Button size="sm" variant={ms !== (video.cover_ms ?? 0) ? "primary" : "secondary"} disabled={locked || ms === video.cover_ms} loading={pending} onClick={() => run(() => setCover(video.id, ms))}>
          <ImageIcon className="size-4" aria-hidden />Use this frame
        </Button>
      </div>
    </div>
  );
}

export function CopyCaption({ text }: { text: string }) {
  const [copied, setCopied] = React.useState(false);
  return (
    <Button
      size="sm"
      variant="secondary"
      disabled={!text.trim()}
      onClick={async () => {
        await navigator.clipboard.writeText(text);
        setCopied(true);
        setTimeout(() => setCopied(false), 1500);
      }}
    >
      {copied ? <Check className="size-4 text-good" aria-hidden /> : <Copy className="size-4" aria-hidden />}
      {copied ? "Copied" : "Copy caption"}
      <span className="sr-only" aria-live="polite">{copied ? "Caption copied" : ""}</span>
    </Button>
  );
}

export function PublishingPanel({ video, timezone }: { video: Video; timezone: string }) {
  return (
    <Panel>
      <PanelHeader title="Title and post time" />
      <div className="flex flex-col gap-5 px-5 pb-5">
        <TitleEditor video={video} />
        <ScheduleEditor video={video} timezone={timezone} />
      </div>
    </Panel>
  );
}
