"use client";
import * as React from "react";
import { ChevronDown, ChevronUp, Plus, RotateCcw, Archive } from "lucide-react";
import type { Idea } from "@/lib/types";
import { addIdea, bumpIdea, setIdeaStatus } from "@/lib/actions";
import { useAction } from "@/components/use-action";
import { Button } from "@/components/ui/button";
import { Badge, Field, Input, Panel, PanelHeader, Select, Textarea } from "@/components/ui/primitives";
import { Dialog } from "@/components/ui/dialog";
import { SegmentedControl } from "@/components/ui/tabs";
import { EmptyState } from "@/components/ui/empty";
import { cn } from "@/lib/format";

const ORIGIN: Record<Idea["origin"], string> = { seed: "Starter", research: "Research", review: "Weekly review", manual: "You" };
type Filter = "waiting" | "used" | "retired";

export function IdeaBank({ channelId, ideas, pillars }: { channelId: string; ideas: Idea[]; pillars: string[] }) {
  const [filter, setFilter] = React.useState<Filter>("waiting");
  const [open, setOpen] = React.useState(false);
  const { pending, run } = useAction();

  const groups: Record<Filter, Idea[]> = {
    waiting: ideas.filter((i) => i.status === "new" || i.status === "queued").sort((a, b) => b.score - a.score),
    used: ideas.filter((i) => i.status === "used"),
    retired: ideas.filter((i) => i.status === "retired" || i.status === "rejected"),
  };
  const list = groups[filter];

  return (
    <Panel className="overflow-hidden">
      <PanelHeader
        title="Idea bank"
        description="Ranked by expected interest, search demand, novelty and how similar videos performed. The worker takes the top idea each time."
        action={<Button size="sm" variant="primary" onClick={() => setOpen(true)}><Plus className="size-4" />Add idea</Button>}
      />
      <div className="px-5 pb-3">
        <SegmentedControl
          label="Idea filter"
          value={filter}
          onChange={setFilter}
          options={[
            { value: "waiting", label: `Waiting · ${groups.waiting.length}` },
            { value: "used", label: `Made · ${groups.used.length}` },
            { value: "retired", label: `Retired · ${groups.retired.length}` },
          ]}
        />
      </div>
      {list.length === 0 ? (
        <EmptyState title={filter === "waiting" ? "The bank is empty" : "Nothing here yet"} figure={filter === "waiting"}>
          {filter === "waiting" ? "Press “Research ideas” above, or add one yourself. The worker also refills the bank when it drops below ten." : null}
        </EmptyState>
      ) : (
        <ol className="divide-y divide-line border-t border-line">
          {list.map((idea, idx) => (
            <li key={idea.id} className="flex flex-wrap gap-x-4 gap-y-2 px-5 py-3.5 sm:flex-nowrap">
              {filter === "waiting" && <span className="w-6 pt-0.5 text-right text-[13px] text-ink-3 tabular">{idx + 1}</span>}
              <div className="min-w-0 flex-1 basis-[calc(100%-2.5rem)] sm:basis-auto">
                <div className="flex flex-wrap items-center gap-2">
                  <p className="text-[14px] font-medium text-ink">{idea.title}</p>
                  {idea.pillar && <Badge>{idea.pillar}</Badge>}
                  {idea.status === "queued" && <Badge tone="warn" dot live>In production</Badge>}
                </div>
                {idea.hook && <p className="mt-1 text-[13px] text-ink-2">“{idea.hook}”</p>}
                {idea.summary && <p className="mt-1 line-clamp-2 text-[13px] text-ink-3">{idea.summary}</p>}
                <p className="mt-1.5 text-[11px] text-ink-3">
                  From {ORIGIN[idea.origin]}
                  {idea.sources?.[0] && <> · → {[idea.sources[0].researcher, idea.sources[0].institution, idea.sources[0].year].filter(Boolean).join(" · ")}</>}
                </p>
              </div>
              <div className={cn("flex shrink-0 items-start gap-1 sm:ml-0", filter === "waiting" && "ml-10")}>
                <span className={cn("mr-2 inline-flex h-8 min-w-11 items-center justify-center rounded-[8px] px-2 text-[13px] font-semibold tabular", idea.score >= 75 ? "bg-accent-soft text-accent-text" : "bg-elev-2 text-ink-2")} title="Score out of 100">
                  {Math.round(idea.score)}
                </span>
                {filter === "waiting" ? (
                  <>
                    <IconBtn label="Move up" onClick={() => run(() => bumpIdea(idea.id, 5), { quiet: true })} disabled={pending}><ChevronUp className="size-4" /></IconBtn>
                    <IconBtn label="Move down" onClick={() => run(() => bumpIdea(idea.id, -5), { quiet: true })} disabled={pending}><ChevronDown className="size-4" /></IconBtn>
                    <IconBtn label="Retire idea" onClick={() => run(() => setIdeaStatus(idea.id, "retired"))} disabled={pending || idea.status === "queued"}><Archive className="size-4" /></IconBtn>
                  </>
                ) : filter === "retired" ? (
                  <IconBtn label="Restore idea" onClick={() => run(() => setIdeaStatus(idea.id, "new"))} disabled={pending}><RotateCcw className="size-4" /></IconBtn>
                ) : null}
              </div>
            </li>
          ))}
        </ol>
      )}
      <AddIdeaDialog open={open} onClose={() => setOpen(false)} channelId={channelId} pillars={pillars} />
    </Panel>
  );
}

function IconBtn({ label, children, ...rest }: { label: string; children: React.ReactNode } & React.ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button {...rest} aria-label={label} title={label} className="tap relative flex size-8 items-center justify-center rounded-[8px] text-ink-3 transition-colors hover:bg-elev-2 hover:text-ink disabled:cursor-not-allowed disabled:opacity-40">
      {children}
    </button>
  );
}

function AddIdeaDialog({ open, onClose, channelId, pillars }: { open: boolean; onClose: () => void; channelId: string; pillars: string[] }) {
  const { pending, run } = useAction();
  const [title, setTitle] = React.useState("");
  const [hook, setHook] = React.useState("");
  const [pillar, setPillar] = React.useState(pillars[0] ?? "");
  const [summary, setSummary] = React.useState("");
  return (
    <Dialog open={open} onClose={onClose} title="Add an idea" description="It joins the bank with a high score, so it's made soon.">
      <form
        className="flex flex-col gap-4"
        onSubmit={(e) => {
          e.preventDefault();
          run(() => addIdea({ channel_id: channelId, title, hook: hook || undefined, pillar: pillar || undefined, summary: summary || undefined }), {
            onOk: () => { setTitle(""); setHook(""); setSummary(""); onClose(); },
          });
        }}
      >
        <Field label="Topic" htmlFor="idea-title"><Input id="idea-title" value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Why you forget names right after hearing them" required /></Field>
        <Field label="Hook line (optional)" htmlFor="idea-hook"><Input id="idea-hook" value={hook} onChange={(e) => setHook(e.target.value)} /></Field>
        {pillars.length > 0 && (
          <Field label="Pillar" htmlFor="idea-pillar">
            <Select id="idea-pillar" value={pillar} onChange={(e) => setPillar(e.target.value)}>{pillars.map((p) => <option key={p}>{p}</option>)}</Select>
          </Field>
        )}
        <Field label="Notes or study to use (optional)" htmlFor="idea-sum"><Textarea id="idea-sum" rows={3} value={summary} onChange={(e) => setSummary(e.target.value)} /></Field>
        <div className="flex justify-end gap-2 pt-1">
          <Button type="button" variant="ghost" onClick={onClose}>Cancel</Button>
          <Button type="submit" variant="primary" loading={pending} disabled={title.trim().length < 3}>Add idea</Button>
        </div>
      </form>
    </Dialog>
  );
}
