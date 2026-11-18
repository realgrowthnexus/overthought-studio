"use client";
import * as React from "react";
import { Check, RefreshCw, Send, X } from "lucide-react";
import type { Video } from "@/lib/types";
import { approveVideo, enqueueJob, rejectVideo, updateCaption } from "@/lib/actions";
import { useAction } from "@/components/use-action";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { Field, Panel, PanelHeader, Select, Textarea, Input } from "@/components/ui/primitives";

const STAGES = [
  { value: "research", label: "From the start (new research)" },
  { value: "script", label: "Rewrite the script" },
  { value: "visuals", label: "Redraw the scenes" },
  { value: "voice", label: "Re-record the voice" },
  { value: "render", label: "Re-render only" },
];

export function VideoActions({ video }: { video: Video }) {
  const { pending, run } = useAction();
  const [rejectOpen, setRejectOpen] = React.useState(false);
  const [regenOpen, setRegenOpen] = React.useState(false);
  const [publishOpen, setPublishOpen] = React.useState(false);
  const [note, setNote] = React.useState("");
  const [stage, setStage] = React.useState(video.status === "failed" ? "script" : "visuals");

  const canApprove = ["ready", "rejected", "failed"].includes(video.status) && Boolean(video.video_path);
  const canPublish = ["ready", "approved", "scheduled"].includes(video.status) && Boolean(video.video_path);
  const canReject = !["posted", "sent_to_drafts", "rejected"].includes(video.status);

  return (
    <div className="flex flex-col gap-2">
      {canApprove && (
        <Button variant="primary" size="lg" loading={pending} onClick={() => run(() => approveVideo(video.id))}>
          <Check className="size-4" aria-hidden />Approve
        </Button>
      )}
      <div className="grid grid-cols-2 gap-2">
        {canPublish && (
          <Button onClick={() => setPublishOpen(true)}><Send className="size-4" aria-hidden />Publish now</Button>
        )}
        <Button onClick={() => setRegenOpen(true)}><RefreshCw className="size-4" aria-hidden />Make again</Button>
        {canReject && (
          <Button variant="ghost" onClick={() => setRejectOpen(true)} className={canPublish ? "col-span-2" : ""}><X className="size-4" aria-hidden />Reject</Button>
        )}
      </div>

      <Dialog open={rejectOpen} onClose={() => setRejectOpen(false)} title="Reject this video" description="It won't post. Your note teaches the writer what to avoid next time.">
        <Field label="What's wrong? (optional)" htmlFor="reject-note">
          <Textarea id="reject-note" rows={4} value={note} onChange={(e) => setNote(e.target.value)} placeholder="Hook is too slow; the stat on screen is rounded up." />
        </Field>
        <div className="mt-4 flex justify-end gap-2">
          <Button variant="ghost" onClick={() => setRejectOpen(false)}>Cancel</Button>
          <Button variant="danger" loading={pending} onClick={() => run(() => rejectVideo(video.id, note), { onOk: () => setRejectOpen(false) })}>Reject video</Button>
        </div>
      </Dialog>

      <Dialog open={regenOpen} onClose={() => setRegenOpen(false)} title="Make this video again" description="Keeps everything before the step you pick and redoes the rest.">
        <Field label="Start from" htmlFor="regen-stage">
          <Select id="regen-stage" value={stage} onChange={(e) => setStage(e.target.value)}>
            {STAGES.map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
          </Select>
        </Field>
        <div className="mt-4 flex justify-end gap-2">
          <Button variant="ghost" onClick={() => setRegenOpen(false)}>Cancel</Button>
          <Button variant="primary" loading={pending} onClick={() => run(() => enqueueJob({ type: "produce_video", payload: { video_id: video.id, from_stage: stage }, video_id: video.id, channel_id: video.channel_id }), { onOk: () => setRegenOpen(false) })}>
            Make again
          </Button>
        </div>
      </Dialog>

      <Dialog open={publishOpen} onClose={() => setPublishOpen(false)} title="Publish now" description="Sends it to TikTok right away, using this channel's delivery mode (drafts, private or public). It skips the schedule.">
        <div className="mt-2 flex justify-end gap-2">
          <Button variant="ghost" onClick={() => setPublishOpen(false)}>Cancel</Button>
          <Button variant="primary" loading={pending} onClick={() => run(() => enqueueJob({ type: "publish_video", payload: { video_id: video.id }, video_id: video.id, channel_id: video.channel_id }), { onOk: () => setPublishOpen(false) })}>
            Publish now
          </Button>
        </div>
      </Dialog>
    </div>
  );
}

export function CaptionEditor({ video }: { video: Video }) {
  const { pending, run } = useAction();
  const [caption, setCaption] = React.useState(video.caption ?? "");
  const [tags, setTags] = React.useState((video.hashtags ?? []).join(" "));
  const dirty = caption !== (video.caption ?? "") || tags !== (video.hashtags ?? []).join(" ");
  const full = `${caption}${tags ? `\n\n${tags}` : ""}`;
  return (
    <Panel>
      <PanelHeader
        title="Caption"
        description="First line works like a search title on TikTok."
        action={<span className="text-[12px] text-ink-3 tabular">{full.length}/2200</span>}
      />
      <div className="flex flex-col gap-3 px-5 pb-5">
        <Textarea aria-label="Caption" rows={3} value={caption} onChange={(e) => setCaption(e.target.value)} placeholder="Written by the studio after the script is approved." />
        <Field label="Hashtags" htmlFor="tags-input" hint="3–5, mixing niche and broad.">
          <Input id="tags-input" value={tags} onChange={(e) => setTags(e.target.value)} placeholder="#psychology #brainfacts #didyouknow" />
        </Field>
        <div className="flex justify-end">
          <Button size="sm" variant={dirty ? "primary" : "secondary"} disabled={!dirty} loading={pending} onClick={() => run(() => updateCaption(video.id, caption, tags.split(/\s+/)))}>
            Save caption
          </Button>
        </div>
      </div>
    </Panel>
  );
}
