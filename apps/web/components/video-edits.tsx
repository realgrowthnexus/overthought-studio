"use client";
import * as React from "react";
import { CalendarClock, Image as ImageIcon, Lock } from "lucide-react";
import type { Video } from "@/lib/types";
import { scheduleVideo, setCover, updateVideoTitle } from "@/lib/actions";
import { useAction } from "@/components/use-action";
import { Button } from "@/components/ui/button";
import { Field, Input, Panel, PanelHeader } from "@/components/ui/primitives";

const CAN_TIME = ["ready", "approved", "scheduled"];

/** ISO (UTC) → the value a <input type="datetime-local"> shows in the viewer's own time zone. */
function toLocalInput(iso: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

export function VideoDetails({ video }: { video: Video }) {
  const title = useAction();
  const time = useAction();
  const [t, setT] = React.useState(video.title ?? "");
  const [when, setWhen] = React.useState(toLocalInput(video.scheduled_for));
  React.useEffect(() => setWhen(toLocalInput(video.scheduled_for)), [video.scheduled_for]);
  const canTime = CAN_TIME.includes(video.status);
  const zone = Intl.DateTimeFormat().resolvedOptions().timeZone;
  const saveTime = () => {
    const iso = when ? new Date(when).toISOString() : null;
    time.run(() => scheduleVideo(video.id, iso));
  };
  return (
    <Panel>
      <PanelHeader title="Details" description="Edit the title and choose when it posts." />
      <div className="flex flex-col gap-4 px-5 pb-5">
        <Field label="Title" htmlFor="video-title" hint="Shown in the dashboard. The TikTok caption is below.">
          <div className="flex gap-2">
            <Input id="video-title" value={t} maxLength={150} onChange={(e) => setT(e.target.value)} />
            <Button size="md" variant={t !== (video.title ?? "") ? "primary" : "secondary"} disabled={!t.trim() || t === (video.title ?? "")}
              loading={title.pending} onClick={() => title.run(() => updateVideoTitle(video.id, t))}>Save</Button>
          </div>
        </Field>
        <Field label="Post time" htmlFor="video-when"
          hint={canTime ? `Your time (${zone}). A time you set is kept — the studio won't move it.` : "Available once the video is finished."}>
          <div className="flex flex-wrap gap-2">
            <Input id="video-when" type="datetime-local" value={when} disabled={!canTime} onChange={(e) => setWhen(e.target.value)}
              className="min-w-0 flex-1" />
            <Button variant="primary" disabled={!canTime || !when} loading={time.pending} onClick={saveTime}>
              <CalendarClock className="size-4" aria-hidden />{video.status === "ready" ? "Approve and schedule" : "Set time"}
            </Button>
            {video.scheduled_for && canTime && (
              <Button variant="ghost" loading={time.pending} onClick={() => time.run(() => scheduleVideo(video.id, null))}>Clear</Button>
            )}
          </div>
        </Field>
        {video.schedule_locked && video.scheduled_for && (
          <p className="flex items-center gap-1.5 text-[12px] text-ink-3"><Lock className="size-3.5" aria-hidden />You set this time; it stays fixed.</p>
        )}
      </div>
    </Panel>
  );
}

export function CoverPicker({ video, src }: { video: Video; src: string | null }) {
  const ref = React.useRef<HTMLVideoElement>(null);
  const { pending, run } = useAction();
  const dur = Number(video.duration_s || 0);
  const [ms, setMs] = React.useState(Number(video.cover_ms ?? 0));
  React.useEffect(() => {
    const el = ref.current;
    if (el && Number.isFinite(ms)) el.currentTime = ms / 1000;
  }, [ms]);
  if (!src || !dur) return null;
  return (
    <Panel>
      <PanelHeader title="Cover" description="Pick the frame people see before they tap. TikTok drafts let you pick it in the app too." />
      <div className="flex flex-col gap-3 px-5 pb-5 sm:flex-row sm:items-start">
        <video ref={ref} src={src} muted playsInline preload="auto" aria-label="Cover preview"
          className="dark mx-auto aspect-[9/16] w-[120px] shrink-0 rounded-[10px] border border-line bg-bg object-cover" />
        <div className="flex min-w-0 flex-1 flex-col gap-3">
          <label htmlFor="cover-at" className="text-[13px] text-ink-2">Frame at <span className="tabular text-ink">{(ms / 1000).toFixed(1)}s</span></label>
          <input id="cover-at" type="range" min={0} max={Math.floor(dur * 1000)} step={100} value={ms}
            onChange={(e) => setMs(Number(e.target.value))} className="w-full accent-[var(--color-accent)]" />
          <div className="flex justify-end">
            <Button size="sm" variant={ms !== Number(video.cover_ms ?? 0) ? "primary" : "secondary"} loading={pending}
              disabled={ms === Number(video.cover_ms ?? 0)} onClick={() => run(() => setCover(video.id, ms))}>
              <ImageIcon className="size-4" aria-hidden />Save cover
            </Button>
          </div>
        </div>
      </div>
    </Panel>
  );
}
