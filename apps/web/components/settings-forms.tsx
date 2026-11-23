"use client";
import * as React from "react";
import { Eye, EyeOff } from "lucide-react";
import type { GlobalSettings, SecretKey } from "@/lib/types";
import { deleteSecret, saveSecret, setAnthropicCredit, updateSettings } from "@/lib/actions";
import { useAction } from "@/components/use-action";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { Field, Input, Select } from "@/components/ui/primitives";
import { Switch } from "@/components/ui/switch";
import { relTime } from "@/lib/format";

const KEYS: { key: SecretKey; label: string; hint: string; where: string }[] = [
  { key: "anthropic_api_key", label: "Claude API key (optional)", hint: "Not needed: the studio uses your Claude sign-in. Only for switching to pay-per-use.", where: "console.anthropic.com → API keys" },
  { key: "runpod_api_key", label: "RunPod API key", hint: "Scene images (Flux). About $0.012 per image.", where: "runpod.io → Settings → API keys" },
  { key: "tiktok_client_key", label: "TikTok client key", hint: "From your TikTok developer app.", where: "developers.tiktok.com → your app" },
  { key: "tiktok_client_secret", label: "TikTok client secret", hint: "From the same app page.", where: "developers.tiktok.com → your app" },
  { key: "resend_api_key", label: "Resend API key (optional)", hint: "Emails you the weekly report.", where: "resend.com → API keys" },
];

export function SecretsForm({ hints }: { hints: { key: string; hint: string | null; updated_at: string }[] }) {
  return (
    <ul className="divide-y divide-line border-t border-line">
      {KEYS.map((k) => <SecretRow key={k.key} meta={k} stored={hints.find((h) => h.key === k.key)} />)}
    </ul>
  );
}

function SecretRow({ meta, stored }: { meta: (typeof KEYS)[number]; stored?: { hint: string | null; updated_at: string } }) {
  const [editing, setEditing] = React.useState(!stored);
  const [confirmOpen, setConfirmOpen] = React.useState(false);
  const [value, setValue] = React.useState("");
  const [show, setShow] = React.useState(false);
  const { pending, run } = useAction();
  React.useEffect(() => setEditing(!stored), [stored]);
  const id = `secret-${meta.key}`;

  return (
    <li className="px-5 py-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <label htmlFor={id} className="text-[14px] font-medium text-ink">{meta.label}</label>
          <p className="text-[12px] text-ink-3">{meta.hint} <span className="whitespace-nowrap">Get it at {meta.where}.</span></p>
        </div>
        {stored && !editing && (
          <div className="flex items-center gap-2">
            <span className="rounded-[8px] bg-elev-2 px-2.5 py-1 font-mono text-[12px] text-ink-2">•••• {stored.hint}</span>
            <span className="text-[12px] text-ink-3" suppressHydrationWarning>updated {relTime(stored.updated_at)}</span>
          </div>
        )}
      </div>
      {editing ? (
        <form
          className="mt-3 flex flex-col gap-2 sm:flex-row"
          onSubmit={(e) => {
            e.preventDefault();
            run(() => saveSecret(meta.key, value), { onOk: () => { setValue(""); setEditing(false); } });
          }}
        >
          <div className="relative flex-1">
            <Input
              id={id}
              type={show ? "text" : "password"}
              autoComplete="off"
              spellCheck={false}
              value={value}
              onChange={(e) => setValue(e.target.value)}
              placeholder="Paste the key"
              className="pr-10 font-mono"
            />
            <button type="button" onClick={() => setShow((s) => !s)} className="tap absolute top-1/2 right-1 flex size-8 -translate-y-1/2 items-center justify-center rounded-[8px] text-ink-3 transition-colors hover:bg-elev-2 hover:text-ink" aria-label={show ? "Hide key" : "Show key"}>
              {show ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
            </button>
          </div>
          <div className="flex gap-2">
            <Button type="submit" variant="primary" loading={pending} disabled={value.trim().length < 8}>Save</Button>
            {stored && <Button type="button" variant="ghost" onClick={() => setEditing(false)}>Cancel</Button>}
          </div>
        </form>
      ) : (
        <div className="mt-2 flex gap-1">
          <Button size="sm" variant="ghost" onClick={() => setEditing(true)}>Replace</Button>
          <Button size="sm" variant="quiet" onClick={() => setConfirmOpen(true)}>Remove</Button>
          <Dialog open={confirmOpen} onClose={() => setConfirmOpen(false)} title={`Remove the ${meta.label}?`} description="Work that needs this key stops until you add a key again. The key is deleted, not hidden.">
            <div className="flex justify-end gap-2">
              <Button variant="ghost" onClick={() => setConfirmOpen(false)}>Cancel</Button>
              <Button variant="danger" loading={pending} onClick={() => run(() => deleteSecret(meta.key), { onOk: () => setConfirmOpen(false) })}>Remove key</Button>
            </div>
          </Dialog>
        </div>
      )}
    </li>
  );
}

export function GlobalSettingsForm({ settings }: { settings: GlobalSettings }) {
  const [s, setS] = React.useState(settings);
  const { pending, run } = useAction();
  const set = <K extends keyof GlobalSettings>(k: K, v: GlobalSettings[K]) => setS((p) => ({ ...p, [k]: v }));
  return (
    <form
      className="flex flex-col gap-5 px-5 pb-5"
      onSubmit={(e) => {
        e.preventDefault();
        run(() => updateSettings({
          model: s.model, effort: s.effort as "high", daily_budget_usd: s.daily_budget_usd, monthly_budget_usd: s.monthly_budget_usd,
          video_retention_days: s.video_retention_days, report_email: s.report_email ?? "", auto_publish: s.auto_publish,
          api_fallback: Boolean(s.api_fallback), api_fallback_daily_usd: Number(s.api_fallback_daily_usd ?? 2),
        }));
      }}
    >
      <div className="grid grid-cols-1 [&>*]:min-w-0 gap-5 sm:grid-cols-2">
        <Field label="Claude model" htmlFor="model" hint="Used for research, scripts and reviews.">
          <Select id="model" value={s.model} onChange={(e) => set("model", e.target.value)}>
            <option value="claude-opus-5-5">Claude Opus 5.5 (best writing)</option>
            <option value="claude-sonnet-5-5">Claude Sonnet 5.5 (half the cost)</option>
          </Select>
        </Field>
        <Field label="Thinking effort" htmlFor="effort" hint="Higher is more careful and costs more.">
          <Select id="effort" value={s.effort} onChange={(e) => set("effort", e.target.value)}>
            <option value="medium">Medium</option>
            <option value="high">High (recommended)</option>
            <option value="xhigh">Extra high</option>
          </Select>
        </Field>
        <Field label="Daily spend limit (USD)" htmlFor="daily" hint="New videos pause for the day once reached.">
          <Input id="daily" type="number" min={0} step="1" value={s.daily_budget_usd} onChange={(e) => set("daily_budget_usd", Number(e.target.value))} />
        </Field>
        <Field label="Monthly budget (USD)" htmlFor="monthly">
          <Input id="monthly" type="number" min={0} step="5" value={s.monthly_budget_usd} onChange={(e) => set("monthly_budget_usd", Number(e.target.value))} />
        </Field>
        <Field label="Keep video files for (days)" htmlFor="retention" hint="Dashboard preview, kept this long after posting (7 keeps the free Supabase plan comfortable). The full-quality file lives on your server. Scripts and stats are kept forever.">
          <Input id="retention" type="number" min={3} value={s.video_retention_days} onChange={(e) => set("video_retention_days", Number(e.target.value))} />
        </Field>
        <Field label="Weekly report email" htmlFor="email" hint="Needs a Resend key.">
          <Input id="email" type="email" value={s.report_email ?? ""} onChange={(e) => set("report_email", e.target.value)} placeholder="you@example.com" />
        </Field>
      </div>
      <div className="flex flex-col gap-4 rounded-[12px] border border-line p-4">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-[14px] font-medium text-ink">When the Claude limit is reached</p>
            <p className="mt-0.5 max-w-[52ch] text-[12px] leading-relaxed text-ink-3">
              Off: work pauses calmly and resumes after the reset (free). On: work continues on your Claude API key (pay per use) until the daily cap, then pauses. Needs an API key under Advanced.
            </p>
          </div>
          <Switch label="Continue on the API key" checked={Boolean(s.api_fallback)} onCheckedChange={(v) => set("api_fallback", v)} />
        </div>
        {s.api_fallback && (
          <Field label="Max API spend per day (USD)" htmlFor="fbcap" hint="Hard stop. Roughly $0.20–0.50 per video on the API; measured after the first videos.">
            <Input id="fbcap" type="number" min={0} max={100} step="0.5" value={Number(s.api_fallback_daily_usd ?? 2)} onChange={(e) => set("api_fallback_daily_usd", Number(e.target.value))} />
          </Field>
        )}
      </div>
      <div className="flex items-start justify-between gap-4 rounded-[12px] border border-line p-4">
        <div>
          <p className="text-[14px] font-medium text-ink">Auto-publish publicly</p>
          <p className="mt-0.5 max-w-[52ch] text-[12px] leading-relaxed text-ink-3">
            Master switch for hands-free public posting. Only channels set to “Public post” with approval off will post on their own. Leave off until TikTok has audited your app and you trust the output.
          </p>
          {s.auto_publish && <p className="mt-2 text-[12px] font-medium text-warn">On: approved channels publish without you.</p>}
        </div>
        <Switch label="Auto-publish publicly" checked={s.auto_publish} onCheckedChange={(v) => set("auto_publish", v)} />
      </div>
      <div className="flex justify-end">
        <Button type="submit" variant="primary" loading={pending}>Save settings</Button>
      </div>
    </form>
  );
}

export function CreditForm() {
  const [v, setV] = React.useState("");
  const { pending, run } = useAction();
  return (
    <form
      className="flex items-end gap-2 px-5 py-4"
      onSubmit={(e) => {
        e.preventDefault();
        run(() => setAnthropicCredit(Number(v)), { onOk: () => setV("") });
      }}
    >
      <Field label="Current balance (USD)" htmlFor="credit" className="flex-1">
        <Input id="credit" type="number" min={0} step="0.01" value={v} onChange={(e) => setV(e.target.value)} placeholder="25.00" />
      </Field>
      <Button type="submit" loading={pending} disabled={!v}>Save balance</Button>
    </form>
  );
}
