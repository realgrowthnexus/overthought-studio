"use client";
import * as React from "react";
import { useRouter } from "next/navigation";
import { AnimatePresence, motion } from "motion/react";
import { Check, Plus, Trash2, X } from "lucide-react";
import type { Channel, Pillar } from "@/lib/types";
import { createChannel, updateChannel, type ChannelInput } from "@/lib/actions";
import { DEFAULT_VOICE, HOOK_STYLES, STYLE_PRESETS, TIMEZONES, VOICES, voiceSample } from "@/lib/presets";
import { useAction } from "@/components/use-action";
import { Button } from "@/components/ui/button";
import { Field, Input, Select, Textarea } from "@/components/ui/primitives";
import { Switch } from "@/components/ui/switch";
import { cn, slugify } from "@/lib/format";

type Mode = "create" | "edit";

function initial(ch?: Channel): ChannelInput {
  const preset = STYLE_PRESETS[0];
  return {
    name: ch?.name ?? "",
    slug: ch?.slug ?? "",
    niche: ch?.niche ?? "",
    description: ch?.description ?? "",
    color: ch?.color ?? "#FFD60A",
    posting_mode: ch?.posting_mode ?? "draft",
    require_approval: ch?.require_approval ?? true,
    posts_per_day: ch?.posts_per_day ?? 1,
    post_times: ch?.post_times ?? ["12:30", "19:30"],
    timezone: ch?.timezone ?? "America/New_York",
    buffer_days: ch?.buffer_days ?? 1,
    min_seconds: ch?.min_seconds ?? 65,
    max_seconds: ch?.max_seconds ?? 95,
    style: { ...preset.style, ...(ch?.style ?? {}) },
    voice: ch?.voice?.provider === "kokoro" ? { speed: 1, ...ch.voice, provider: "kokoro" as const } : { provider: "kokoro" as const, voice: DEFAULT_VOICE, speed: 1 },
    content: {
      audience: "US, English, ages 16–34",
      tone: "Calm, warm, slightly amused — a smart friend at 2 a.m.",
      pillars: [{ name: "Why you do that", weight: 0.7 }, { name: "Spot the trick", weight: 0.3 }],
      hook_styles: ["you-callout", "question", "number"],
      hashtags_core: ["#psychology", "#brainfacts"],
      rules: [
        "Every claim traces to a real study shown on screen as → Researcher · Institution · Year",
        "Flag effects that failed to replicate instead of presenting them as fact",
        "Never round a statistic into something false",
      ],
      banned: ["medical or legal advice"],
      ...(ch?.content ?? {}),
    },
  };
}

const STEPS = [
  { id: "basics", label: "Basics" },
  { id: "look", label: "Look & voice" },
  { id: "content", label: "Content" },
  { id: "schedule", label: "Schedule & posting" },
] as const;

export function ChannelForm({ mode, channel }: { mode: Mode; channel?: Channel }) {
  const router = useRouter();
  const [v, setV] = React.useState<ChannelInput>(() => initial(channel));
  const [step, setStep] = React.useState(0);
  const [slugTouched, setSlugTouched] = React.useState(mode === "edit");
  const { pending, run } = useAction();

  const set = <K extends keyof ChannelInput>(k: K, val: ChannelInput[K]) => setV((p) => ({ ...p, [k]: val }));
  const setNested = <K extends "style" | "voice" | "content">(k: K, patch: Partial<NonNullable<ChannelInput[K]>>) =>
    setV((p) => ({ ...p, [k]: { ...(p[k] as object), ...patch } }));

  function submit() {
    if (mode === "create") {
      run(() => createChannel(v), { onOk: (r) => router.push(`/channels/${r.data?.slug ?? v.slug}`) });
    } else if (channel) {
      run(() => updateChannel(channel.id, v), {
        onOk: (r) => {
          if (r.data?.slug && r.data.slug !== channel.slug) router.replace(`/channels/${r.data.slug}/settings`);
          else router.refresh();
        },
      });
    }
  }

  const sections = {
    basics: (
      <div className="grid grid-cols-1 [&>*]:min-w-0 gap-5 sm:grid-cols-2">
        <Field label="Channel name" htmlFor="name">
          <Input id="name" value={v.name} placeholder="Overthought" onChange={(e) => {
            set("name", e.target.value);
            if (!slugTouched) set("slug", slugify(e.target.value));
          }} />
        </Field>
        <Field label="Short name for links" htmlFor="slug" hint="Lowercase, used in the dashboard URL.">
          <Input id="slug" value={v.slug} onChange={(e) => { setSlugTouched(true); set("slug", slugify(e.target.value)); }} />
        </Field>
        <Field label="Topic in one line" htmlFor="niche" className="sm:col-span-2" hint="What every video is about. The script writer reads this first.">
          <Input id="niche" value={v.niche} placeholder="Why your brain does that — everyday psychology with real studies" onChange={(e) => set("niche", e.target.value)} />
        </Field>
        <Field label="Notes for the writer" htmlFor="description" className="sm:col-span-2" hint="Anything that makes this channel distinct: angle, references to use or avoid, running jokes.">
          <Textarea id="description" value={v.description} rows={4} onChange={(e) => set("description", e.target.value)} />
        </Field>
        <Field label="Dashboard colour" htmlFor="color" hint="Only used to tell channels apart here.">
          <div className="flex items-center gap-2">
            <input id="color" type="color" value={v.color} onChange={(e) => set("color", e.target.value.toUpperCase())} className="h-10 w-12 cursor-pointer rounded-[10px] border border-line bg-bg p-1" />
            <Input value={v.color} onChange={(e) => set("color", e.target.value)} className="font-mono" aria-label="Colour hex" />
          </div>
        </Field>
      </div>
    ),
    look: (
      <div className="flex flex-col gap-6">
        <div>
          <p className="mb-2 text-[13px] font-medium text-ink-2">Video look</p>
          <div className="grid grid-cols-1 [&>*]:min-w-0 gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {STYLE_PRESETS.map((p) => {
              const selected = v.style?.preset === p.id;
              return (
                <button
                  key={p.id}
                  type="button"
                  onClick={() => setNested("style", { ...p.style, seed: v.style?.seed ?? p.style.seed })}
                  className={cn(
                    "group relative flex flex-col overflow-hidden rounded-[12px] border text-left transition-[border-color,transform] duration-150 hover:-translate-y-px",
                    selected ? "border-ink" : "border-line hover:border-line-strong",
                  )}
                  aria-pressed={selected}
                >
                  <div className="relative flex h-24 items-center justify-center" style={{ background: p.style.bg }}>
                    <svg viewBox="0 0 60 70" className="h-16" fill="none" aria-hidden>
                      <g stroke={p.style.ink} strokeWidth="2" strokeLinecap="round">
                        <circle cx="30" cy="22" r="7" /><path d="M30 29v20M30 35l-9 8M30 35l8 7M30 49l-7 15M30 49l7 15" />
                      </g>
                      <path d="M38 8c2-4 8-3 8 1 4 0 4 6 0 6 1 4-6 5-7 1-4 2-7-3-3-5" stroke={p.style.accent} strokeWidth="1.8" strokeLinecap="round" />
                    </svg>
                    {selected && <span className="absolute top-2 right-2 flex size-5 items-center justify-center rounded-full bg-accent text-accent-ink"><Check className="size-3" /></span>}
                  </div>
                  <div className="bg-elev px-3 py-2.5">
                    <p className="text-[13px] font-medium text-ink">{p.name}</p>
                    <p className="mt-0.5 text-[12px] leading-snug text-ink-3">{p.description}</p>
                  </div>
                </button>
              );
            })}
          </div>
        </div>
        <div className="grid grid-cols-1 [&>*]:min-w-0 gap-5 sm:grid-cols-3">
          <Field label="Background" htmlFor="bg"><Input id="bg" className="font-mono" value={v.style?.bg ?? ""} onChange={(e) => setNested("style", { bg: e.target.value })} /></Field>
          <Field label="Line & text" htmlFor="ink"><Input id="ink" className="font-mono" value={v.style?.ink ?? ""} onChange={(e) => setNested("style", { ink: e.target.value })} /></Field>
          <Field label="Accent (glitch element only)" htmlFor="accent"><Input id="accent" className="font-mono" value={v.style?.accent ?? ""} onChange={(e) => setNested("style", { accent: e.target.value })} /></Field>
          <Field label="Corner tag" htmlFor="bug" hint="Small handwritten name in the corner of every frame.">
            <Input id="bug" value={v.style?.bug_text ?? ""} placeholder={v.name.toLowerCase() || "overthought"} onChange={(e) => setNested("style", { bug_text: e.target.value })} />
          </Field>
          <Field label="Image seed" htmlFor="seed" hint="Keep it fixed so the figure stays consistent.">
            <Input id="seed" type="number" value={Number(v.style?.seed ?? 7)} onChange={(e) => setNested("style", { seed: Number(e.target.value) })} />
          </Field>
        </div>
        <Field label="Figure prompt" htmlFor="fig" hint="Sent to the image model before every scene. Don't ask for colour or text here — accents and words are added in code.">
          <Textarea id="fig" rows={3} value={v.style?.figure_prompt ?? ""} onChange={(e) => setNested("style", { figure_prompt: e.target.value })} />
        </Field>
        <div className="grid grid-cols-1 [&>*]:min-w-0 gap-5 border-t border-line pt-5 sm:grid-cols-3">
          <Field label="Voice" htmlFor="voice" className="sm:col-span-2" hint="Free voice that runs on your server: no key, no bill. Keep one voice per channel so viewers recognise it.">
            <Select id="voice" value={v.voice?.voice ?? DEFAULT_VOICE} onChange={(e) => setNested("voice", { provider: "kokoro", voice: e.target.value })}>
              {VOICES.map((o) => <option key={o.id} value={o.id}>{o.label}</option>)}
            </Select>
          </Field>
          <Field label={`Speed · ${Number(v.voice?.speed ?? 1).toFixed(2)}×`} htmlFor="vspeed" hint="1.00 is natural. Slightly faster suits energetic channels.">
            <input id="vspeed" type="range" min={0.85} max={1.15} step={0.01} value={Number(v.voice?.speed ?? 1)} onChange={(e) => setNested("voice", { speed: Number(e.target.value) })} className="accent-[var(--accent)]" />
          </Field>
          <div className="sm:col-span-3">
            <p className="mb-2 text-sm text-ink-2">Listen to this voice</p>
            <audio key={v.voice?.voice ?? DEFAULT_VOICE} controls preload="none" className="w-full max-w-md" src={voiceSample(v.voice?.voice ?? DEFAULT_VOICE)} />
          </div>
        </div>
      </div>
    ),
    content: (
      <div className="flex flex-col gap-6">
        <div className="grid grid-cols-1 [&>*]:min-w-0 gap-5 sm:grid-cols-2">
          <Field label="Audience" htmlFor="aud"><Input id="aud" value={v.content?.audience ?? ""} onChange={(e) => setNested("content", { audience: e.target.value })} /></Field>
          <Field label="Tone of voice" htmlFor="tone"><Input id="tone" value={v.content?.tone ?? ""} onChange={(e) => setNested("content", { tone: e.target.value })} /></Field>
        </div>
        <PillarsEditor pillars={(v.content?.pillars as Pillar[]) ?? []} onChange={(pillars) => setNested("content", { pillars })} />
        <div>
          <p className="mb-1 text-[13px] font-medium text-ink-2">Hook styles to rotate</p>
          <p className="mb-3 text-[12px] text-ink-3">The weekly review shifts weight toward the styles that hold viewers longest.</p>
          <div className="flex flex-wrap gap-2">
            {HOOK_STYLES.map((h) => {
              const on = v.content?.hook_styles?.includes(h.id);
              return (
                <button
                  key={h.id}
                  type="button"
                  title={h.example}
                  aria-pressed={on}
                  onClick={() => {
                    const cur = new Set(v.content?.hook_styles ?? []);
                    if (on) cur.delete(h.id); else cur.add(h.id);
                    setNested("content", { hook_styles: [...cur] });
                  }}
                  className={cn(
                    "h-9 rounded-full border px-3.5 text-[13px] transition-colors",
                    on ? "border-ink bg-ink text-bg hover:bg-ink-2" : "border-line text-ink-2 hover:border-ink-3 hover:text-ink",
                  )}
                >
                  {h.label}
                </button>
              );
            })}
          </div>
        </div>
        <Field label="Core hashtags" htmlFor="tags" hint="Separate with spaces. 2–3 core tags; the writer adds 1–2 per video.">
          <Input id="tags" value={(v.content?.hashtags_core ?? []).join(" ")} onChange={(e) => setNested("content", { hashtags_core: e.target.value.split(/[\s,]+/).filter(Boolean).map((t) => (t.startsWith("#") ? t : `#${t}`)) })} />
        </Field>
        <Field label="Writer rules" htmlFor="rules" hint="One rule per line. Checked by the fact-check step.">
          <Textarea id="rules" rows={5} value={(v.content?.rules ?? []).join("\n")} onChange={(e) => setNested("content", { rules: e.target.value.split("\n") })} />
        </Field>
        <Field label="Never cover" htmlFor="banned" hint="One topic per line.">
          <Textarea id="banned" rows={2} value={(v.content?.banned ?? []).join("\n")} onChange={(e) => setNested("content", { banned: e.target.value.split("\n") })} />
        </Field>
      </div>
    ),
    schedule: (
      <div className="flex flex-col gap-6">
        <div className="grid grid-cols-1 [&>*]:min-w-0 gap-5 sm:grid-cols-3">
          <Field label="Posts per day" htmlFor="ppd">
            <Select id="ppd" value={String(v.posts_per_day)} onChange={(e) => set("posts_per_day", Number(e.target.value))}>
              {[0, 1, 2, 3].map((n) => <option key={n} value={n}>{n === 0 ? "None (paused schedule)" : `${n} a day`}</option>)}
            </Select>
          </Field>
          <Field label="Time zone" htmlFor="tz">
            <Select id="tz" value={v.timezone} onChange={(e) => set("timezone", e.target.value)}>
              {TIMEZONES.map((t) => <option key={t} value={t}>{t.replace("America/", "").replace("_", " ")}</option>)}
            </Select>
          </Field>
          <Field label="Make videos ahead" htmlFor="buf" hint="Days of finished videos to keep ready.">
            <Select id="buf" value={String(v.buffer_days)} onChange={(e) => set("buffer_days", Number(e.target.value))}>
              {[0, 1, 2, 3].map((n) => <option key={n} value={n}>{n === 0 ? "Same day" : `${n} day${n > 1 ? "s" : ""}`}</option>)}
            </Select>
          </Field>
        </div>
        <TimesEditor times={v.post_times as string[]} onChange={(t) => set("post_times", t)} />
        <div className="grid grid-cols-1 [&>*]:min-w-0 gap-5 sm:grid-cols-2">
          <Field label="Shortest video (seconds)" htmlFor="min" hint="Creator Rewards only counts videos over one minute. 65s leaves a safety margin.">
            <Input id="min" type="number" min={61} value={Number(v.min_seconds)} onChange={(e) => set("min_seconds", Number(e.target.value))} />
          </Field>
          <Field label="Longest video (seconds)" htmlFor="max">
            <Input id="max" type="number" value={Number(v.max_seconds)} onChange={(e) => set("max_seconds", Number(e.target.value))} />
          </Field>
        </div>
        <div>
          <p className="mb-2 text-[13px] font-medium text-ink-2">How videos reach TikTok</p>
          <div className="grid grid-cols-1 [&>*]:min-w-0 gap-3 sm:grid-cols-3">
            {([
              ["draft", "TikTok drafts", "Lands in the app's inbox. You tap Post. Works before TikTok approves your developer app."],
              ["private", "Private post", "Posts as 'Only me'. Good for testing the full flow."],
              ["public", "Public post", "Fully automatic. Needs TikTok's app audit and the global auto-publish switch."],
            ] as const).map(([id, label, desc]) => (
              <button
                key={id}
                type="button"
                aria-pressed={v.posting_mode === id}
                onClick={() => set("posting_mode", id)}
                className={cn(
                  "rounded-[12px] border p-3.5 text-left transition-colors",
                  v.posting_mode === id ? "border-ink bg-elev-2" : "border-line hover:border-line-strong",
                )}
              >
                <p className="text-[14px] font-medium text-ink">{label}</p>
                <p className="mt-1 text-[12px] leading-snug text-ink-3">{desc}</p>
              </button>
            ))}
          </div>
        </div>
        <label className="flex items-start justify-between gap-4 rounded-[12px] border border-line p-4">
          <span>
            <span className="block text-[14px] font-medium text-ink">I approve each video before it posts</span>
            <span className="mt-0.5 block text-[12px] text-ink-3">Recommended for the first month. Turn off for hands-free posting.</span>
          </span>
          <Switch label="Require approval" checked={v.require_approval} onCheckedChange={(x) => set("require_approval", x)} />
        </label>
      </div>
    ),
  };

  if (mode === "edit") {
    return (
      <div className="flex flex-col gap-6">
        {STEPS.map((s) => (
          <section key={s.id} className="rounded-[var(--radius-lg)] border border-line bg-elev p-5 sm:p-6">
            <h2 className="mb-5 text-[15px] font-semibold text-ink">{s.label}</h2>
            {sections[s.id]}
          </section>
        ))}
        <div className="sticky bottom-20 z-10 flex items-center justify-between gap-4 rounded-[14px] border border-line bg-elev/90 py-2.5 pr-2.5 pl-5 shadow-[var(--shadow)] backdrop-blur lg:bottom-4">
          <p className="text-[13px] text-ink-3">Changes apply to the next video this channel makes.</p>
          <Button variant="primary" loading={pending} onClick={submit}>Save changes</Button>
        </div>
      </div>
    );
  }

  const canNext = step === 0 ? v.name.length > 1 && v.slug.length > 1 && v.niche.length > 1 : true;
  return (
    <div className="grid grid-cols-1 [&>*]:min-w-0 gap-8 lg:grid-cols-[200px_1fr]">
      <ol className="scroll-fade-x flex gap-2 overflow-x-auto lg:flex-col lg:gap-1" aria-label="Steps">
        {STEPS.map((s, i) => (
          <li key={s.id}>
            <button
              type="button"
              onClick={() => i <= step && setStep(i)}
              disabled={i > step}
              className={cn(
                "flex items-center gap-3 rounded-[10px] px-2 py-2 text-left text-[14px] whitespace-nowrap transition-colors duration-150",
                i === step ? "text-ink" : i < step ? "text-ink-2 hover:bg-elev-2/60 hover:text-ink" : "text-ink-3 disabled:opacity-100",
              )}
              aria-current={i === step ? "step" : undefined}
            >
              <span className={cn(
                "flex size-6 shrink-0 items-center justify-center rounded-full border text-[12px] tabular",
                i < step ? "border-ink bg-ink text-bg" : i === step ? "border-accent bg-accent text-accent-ink" : "border-line-strong",
              )}>
                {i < step ? <Check className="size-3.5" /> : i + 1}
              </span>
              {s.label}
            </button>
          </li>
        ))}
      </ol>
      <div className="rounded-[var(--radius-lg)] border border-line bg-elev p-5 sm:p-7">
        <AnimatePresence mode="wait">
          <motion.div key={step} initial={{ opacity: 0, x: 12 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -12 }} transition={{ duration: 0.18 }}>
            <h2 className="mb-5 text-[17px] font-semibold text-ink">{STEPS[step].label}</h2>
            {sections[STEPS[step].id]}
          </motion.div>
        </AnimatePresence>
        <div className="mt-8 flex items-center justify-between border-t border-line pt-5">
          <Button variant="ghost" onClick={() => (step ? setStep(step - 1) : router.back())}>{step ? "Back" : "Cancel"}</Button>
          {step < STEPS.length - 1 ? (
            <Button variant="primary" disabled={!canNext} onClick={() => setStep(step + 1)}>Continue</Button>
          ) : (
            <Button variant="primary" loading={pending} onClick={submit}>Create channel</Button>
          )}
        </div>
      </div>
    </div>
  );
}

function PillarsEditor({ pillars, onChange }: { pillars: Pillar[]; onChange: (p: Pillar[]) => void }) {
  const total = pillars.reduce((s, p) => s + Number(p.weight || 0), 0) || 1;
  return (
    <div>
      <p className="mb-1 text-[13px] font-medium text-ink-2">Content pillars</p>
      <p className="mb-3 text-[12px] text-ink-3">The mix of video types. Weights are shares of all posts.</p>
      <div className="flex flex-col gap-2">
        {pillars.map((p, i) => (
          <div key={i} className="grid grid-cols-[1fr_120px_48px_36px] items-center gap-3">
            <Input aria-label="Pillar name" value={p.name} onChange={(e) => onChange(pillars.map((x, j) => (j === i ? { ...x, name: e.target.value } : x)))} />
            <input aria-label="Pillar weight" type="range" min={0} max={1} step={0.05} value={p.weight} onChange={(e) => onChange(pillars.map((x, j) => (j === i ? { ...x, weight: Number(e.target.value) } : x)))} className="accent-[var(--accent)]" />
            <span className="text-right text-[13px] text-ink-2 tabular">{Math.round((p.weight / total) * 100)}%</span>
            <button type="button" onClick={() => onChange(pillars.filter((_, j) => j !== i))} className="tap relative flex size-9 shrink-0 items-center justify-center rounded-[8px] text-ink-3 transition-colors hover:bg-elev-2 hover:text-bad" aria-label={`Remove ${p.name}`}>
              <Trash2 className="size-4" />
            </button>
          </div>
        ))}
        <Button type="button" size="sm" variant="ghost" className="self-start" onClick={() => onChange([...pillars, { name: "", weight: 0.2 }])}>
          <Plus className="size-4" />Add pillar
        </Button>
      </div>
    </div>
  );
}

function TimesEditor({ times, onChange }: { times: string[]; onChange: (t: string[]) => void }) {
  const [draft, setDraft] = React.useState("21:00");
  return (
    <div>
      <p className="mb-1 text-[13px] font-medium text-ink-2">Posting times</p>
      <p className="mb-3 text-[12px] text-ink-3">Local to the time zone above. US evenings and lunch breaks work best for this audience.</p>
      <div className="flex flex-wrap items-center gap-2">
        {[...times].sort().map((t) => (
          <span key={t} className="inline-flex h-9 items-center gap-1.5 rounded-full border border-line bg-bg pr-1.5 pl-3.5 text-[13px] text-ink tabular">
            {t}
            <button type="button" onClick={() => onChange(times.filter((x) => x !== t))} className="tap relative flex size-6 items-center justify-center rounded-full text-ink-3 transition-colors hover:bg-elev-2 hover:text-ink" aria-label={`Remove ${t}`}>
              <X className="size-3.5" />
            </button>
          </span>
        ))}
        <span className="inline-flex items-center gap-1.5">
          <Input type="time" aria-label="New posting time" value={draft} onChange={(e) => setDraft(e.target.value)} className="h-9 w-[120px]" />
          <Button type="button" size="sm" onClick={() => draft && !times.includes(draft) && onChange([...times, draft])}>Add</Button>
        </span>
      </div>
    </div>
  );
}
