import type { Report } from "@/lib/types";
import { Panel } from "@/components/ui/primitives";
import { Markdown } from "@/components/markdown";
import { shortDate } from "@/lib/format";

type Change = { what?: string; why?: string; area?: string; [k: string]: unknown } | string;

export function ReportCard({ report, channelName, defaultOpen }: { report: Report; channelName?: string; defaultOpen?: boolean }) {
  const changes = (report.changes ?? []) as Change[];
  return (
    <Panel as="article" className="overflow-hidden">
      <details open={defaultOpen} className="group">
        <summary className="flex cursor-pointer list-none items-start justify-between gap-4 px-5 py-4 transition-colors duration-150 hover:bg-elev-2/50 [&::-webkit-details-marker]:hidden">
          <div>
            <h3 className="text-[15px] font-semibold text-ink">{report.title}</h3>
            <p className="mt-0.5 text-[12px] text-ink-3">
              {shortDate(report.period_start)} – {shortDate(report.period_end)}
              {channelName ? ` · ${channelName}` : ""}
              {changes.length ? ` · ${changes.length} change${changes.length === 1 ? "" : "s"} made` : ""}
            </p>
          </div>
          <span className="mt-1 text-[12px] text-ink-3 underline-offset-4 group-open:hidden group-hover:text-ink group-hover:underline">Show</span>
          <span className="mt-1 hidden text-[12px] text-ink-3 underline-offset-4 group-open:inline group-hover:text-ink group-hover:underline">Hide</span>
        </summary>
        <div className="border-t border-line px-5 py-4">
          {changes.length > 0 && (
            <div className="mb-4 rounded-[12px] border border-line bg-bg p-4">
              <p className="mb-2 text-[13px] font-medium text-ink">What the studio changed</p>
              <ul className="flex flex-col gap-1.5 text-[13px] text-ink-2">
                {changes.map((c, i) => (
                  <li key={i} className="flex gap-2">
                    <span className="mt-[7px] size-1.5 shrink-0 rounded-full bg-accent-mark" aria-hidden />
                    <span>{typeof c === "string" ? c : <>{c.what}{c.why ? <span className="text-ink-3"> — {c.why}</span> : null}</>}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
          <Markdown>{report.summary_md}</Markdown>
        </div>
      </details>
    </Panel>
  );
}
