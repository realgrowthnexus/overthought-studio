import type { Metadata } from "next";
import { getAnthropicCredit, getSecretHints, getSettings, getSpendSince, getWorkers } from "@/lib/data";
import { hasMasterKey } from "@/lib/crypto";
import { PageHeader, Panel, PanelHeader, KV, Badge } from "@/components/ui/primitives";
import { SecretsForm, GlobalSettingsForm, CreditForm } from "@/components/settings-forms";
import { JobButton } from "@/components/job-button";
import { relTime, usd } from "@/lib/format";

export const metadata: Metadata = { title: "Settings" };
export const dynamic = "force-dynamic";

export default async function SettingsPage() {
  const [hints, settings, credit, workers] = await Promise.all([getSecretHints(), getSettings(), getAnthropicCredit(), getWorkers()]);
  const spentSince = credit.set_at ? (await getSpendSince(credit.set_at)).filter((r) => r.service === "anthropic").reduce((s, r) => s + Number(r.amount_usd || 0), 0) : 0;
  const remaining = credit.balance_usd != null ? credit.balance_usd - spentSince : null;

  return (
    <>
      <PageHeader title="Settings" description="Keys, budgets and switches for the whole studio." actions={<JobButton type="health_check" payload={{}}>Run health check</JobButton>} />
      <div className="grid gap-6 xl:grid-cols-[1.25fr_1fr]">
        <div className="flex flex-col gap-6">
          <Panel id="keys" className="scroll-mt-24">
            <PanelHeader
              title="API keys"
              description="Encrypted before they're stored. Nobody, including this page, can read them back — you can only replace or remove them."
            />
            {!hasMasterKey() && (
              <p className="mx-5 mb-4 rounded-[10px] bg-bad-soft px-3 py-2 text-[13px] text-bad">
                MASTER_KEY isn&apos;t set on the server, so keys can&apos;t be saved yet. Add it in Vercel → Settings → Environment Variables.
              </p>
            )}
            <SecretsForm hints={hints} />
          </Panel>
          <Panel>
            <PanelHeader title="Studio settings" />
            <GlobalSettingsForm settings={settings} />
          </Panel>
        </div>
        <div className="flex flex-col gap-6">
          <Panel>
            <PanelHeader title="Claude API credit" description="Anthropic doesn't share your balance through the API. Enter it after each top-up; the studio subtracts what it spends." />
            <dl className="divide-y divide-line px-5">
              <KV k="Balance you entered" v={credit.balance_usd != null ? `${usd(credit.balance_usd)} · ${relTime(credit.set_at)}` : "Not set"} />
              <KV k="Spent since then" v={usd(spentSince)} />
              <KV k="Estimated remaining" v={remaining != null ? <span className={remaining < 3 ? "text-bad" : ""}>{usd(remaining)}</span> : "—"} />
            </dl>
            <CreditForm />
          </Panel>
          <Panel id="worker" className="scroll-mt-24">
            <PanelHeader title="Worker" description="The program on your VPS that makes and posts the videos." />
            {workers.length === 0 ? (
              <div className="px-5 pb-5 text-[13px] leading-relaxed text-ink-2">
                <p>No worker has checked in yet. Install it on your VPS with the one-line command in the setup guide (<code className="rounded bg-elev-2 px-1">docs/SETUP.md</code>). It needs the same <code className="rounded bg-elev-2 px-1">MASTER_KEY</code> as this dashboard.</p>
              </div>
            ) : (
              <ul className="divide-y divide-line px-5 pb-3">
                {workers.map((w) => {
                  const online = Date.now() - new Date(w.last_seen).getTime() < 3 * 60_000;
                  return (
                    <li key={w.worker_id} className="py-3">
                      <div className="flex items-center justify-between">
                        <span className="text-[14px] font-medium text-ink">{w.worker_id}</span>
                        {online ? <Badge tone="good" dot live>Online</Badge> : <Badge tone="bad" dot>Offline</Badge>}
                      </div>
                      <p className="mt-0.5 text-[12px] text-ink-3">
                        {w.host ?? "unknown host"} · version {w.version ?? "?"} · last seen {relTime(w.last_seen)} · up since {relTime(w.started_at)}
                      </p>
                    </li>
                  );
                })}
              </ul>
            )}
            <div className="flex flex-wrap gap-2 border-t border-line px-5 py-4">
              <JobButton type="backup_db" payload={{}} size="sm">Back up now</JobButton>
              <JobButton type="refresh_tokens" payload={{}} size="sm" variant="ghost">Refresh TikTok logins</JobButton>
              <JobButton type="sync_stats" payload={{}} size="sm" variant="ghost">Sync stats</JobButton>
            </div>
          </Panel>
        </div>
      </div>
    </>
  );
}
