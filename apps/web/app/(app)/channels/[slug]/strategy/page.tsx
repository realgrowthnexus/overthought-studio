import { notFound } from "next/navigation";
import { getChannelBySlug, getReports } from "@/lib/data";
import { Panel, PanelHeader } from "@/components/ui/primitives";
import { EmptyState } from "@/components/ui/empty";
import { ReportCard } from "@/components/report-card";
import { HOOK_STYLES } from "@/lib/presets";
import { MarginNote } from "@/components/brand";
import { shortDate } from "@/lib/format";

export const dynamic = "force-dynamic";

function Weights({ title, weights, labels }: { title: string; weights?: Record<string, number>; labels?: Record<string, string> }) {
  const entries = Object.entries(weights ?? {}).sort((a, b) => b[1] - a[1]);
  const total = entries.reduce((s, [, w]) => s + w, 0) || 1;
  if (!entries.length) return null;
  return (
    <div>
      <p className="mb-3 text-[13px] font-medium text-ink-2">{title}</p>
      <ul className="flex flex-col gap-2.5">
        {entries.map(([k, w]) => (
          <li key={k} className="grid grid-cols-[minmax(0,10rem)_1fr_3rem] items-center gap-3 text-[13px]">
            <span className="truncate text-ink">{labels?.[k] ?? k}</span>
            <span className="h-2 overflow-hidden rounded-full bg-elev-2">
              <span className="block h-full rounded-full bg-[var(--series-1)]" style={{ width: `${(w / total) * 100}%` }} />
            </span>
            <span className="text-right text-ink-2 tabular">{Math.round((w / total) * 100)}%</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export default async function ChannelStrategy({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const channel = await getChannelBySlug(slug);
  if (!channel) notFound();
  const reports = await getReports(channel.id);
  const s = channel.strategy ?? {};
  const hasStrategy = Object.keys(s).length > 0;
  const hookLabels = Object.fromEntries(HOOK_STYLES.map((h) => [h.id, h.label]));

  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_1.3fr]">
      <Panel>
        <PanelHeader
          title="Current strategy"
          description={s.week_of ? `Set by the weekly review for the week of ${shortDate(s.week_of)}.` : "Updated every Monday from the last 7 days of results."}
        />
        {hasStrategy ? (
          <div className="flex flex-col gap-6 px-5 pb-5">
            {s.test?.variable && (
              <div className="rounded-[12px] border border-line bg-bg p-4">
                <p className="text-[12px] text-ink-3">This week&apos;s single test</p>
                <p className="mt-1 text-[15px] font-medium text-ink">
                  {s.test.variable}{s.test.variant ? `: ${s.test.variant}` : ""}
                </p>
                {s.test.hypothesis && <p className="mt-1 text-[13px] text-ink-2">{s.test.hypothesis}</p>}
              </div>
            )}
            <Weights title="Pillar mix" weights={s.pillar_weights} />
            <Weights title="Hook styles" weights={s.hook_weights} labels={hookLabels} />
            {s.notes && <MarginNote className="text-[16px]">{s.notes}</MarginNote>}
          </div>
        ) : (
          <EmptyState title="No strategy yet" figure={false}>
            After the first week of posts, the review sets the pillar mix, hook styles and one test, and writes them here.
          </EmptyState>
        )}
      </Panel>
      <div className="flex flex-col gap-4">
        {reports.length === 0 ? (
          <Panel><EmptyState title="No weekly reports yet">Reports arrive every Monday morning, US Eastern.</EmptyState></Panel>
        ) : (
          reports.map((r, i) => <ReportCard key={r.id} report={r} defaultOpen={i === 0} />)
        )}
      </div>
    </div>
  );
}
