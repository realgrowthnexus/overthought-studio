"use client";
import * as React from "react";
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { DayPoint, Metric } from "@/lib/series";
import { SegmentedControl } from "@/components/ui/tabs";
import { num } from "@/lib/format";

const LABEL: Record<Metric, string> = { views: "Views", likes: "Likes", shares: "Shares", comments: "Comments" };

function fmtDay(d: string) {
  return new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric", timeZone: "UTC" }).format(new Date(d + "T00:00:00Z"));
}

/** Single-series cumulative trend with a metric switcher (one axis, no legend — the switcher names the series). */
export function TrendChart({ data, height = 240, initial = "views" }: { data: DayPoint[]; height?: number; initial?: Metric }) {
  const [metric, setMetric] = React.useState<Metric>(initial);
  const [showTable, setShowTable] = React.useState(false);
  const id = React.useId().replace(/:/g, "");
  const last = data.at(-1)?.[metric] ?? 0;
  const first = data[0]?.[metric] ?? 0;
  const empty = data.every((d) => d[metric] === 0);

  return (
    <div>
      <div className="mb-3 flex flex-wrap items-center justify-between gap-3 px-5">
        <div>
          <p className="text-[24px] leading-none font-semibold tracking-[-0.02em] text-ink tabular">{num(last)}</p>
          <p className="mt-1 text-[12px] text-ink-3">
            {LABEL[metric].toLowerCase()} total · {last - first >= 0 ? "+" : ""}{num(last - first)} in {data.length} days
          </p>
        </div>
        <div className="flex min-w-0 flex-wrap items-center gap-2">
          <SegmentedControl
            label="Metric"
            layoutKey={`metric-${id}`}
            value={metric}
            onChange={setMetric}
            options={(Object.keys(LABEL) as Metric[]).map((m) => ({ value: m, label: LABEL[m] }))}
          />
          <button type="button" aria-pressed={showTable} onClick={() => setShowTable((s) => !s)} className="tap relative h-9 rounded-[8px] px-2.5 text-[12px] text-ink-3 transition-colors hover:bg-elev-2 hover:text-ink">
            {showTable ? "Chart" : "Table"}
          </button>
        </div>
      </div>
      {showTable ? (
        <div className="max-h-[260px] overflow-auto px-5 pb-4">
          <table className="w-full text-[13px]">
            <thead className="sticky top-0 bg-elev text-left text-ink-3">
              <tr><th className="py-1.5 font-medium">Day</th>{(Object.keys(LABEL) as Metric[]).map((m) => <th key={m} className="py-1.5 text-right font-medium">{LABEL[m]}</th>)}</tr>
            </thead>
            <tbody className="tabular">
              {[...data].reverse().map((d) => (
                <tr key={d.date} className="border-t border-line">
                  <td className="py-1.5 text-ink-2">{fmtDay(d.date)}</td>
                  {(Object.keys(LABEL) as Metric[]).map((m) => <td key={m} className="py-1.5 text-right text-ink">{num(d[m])}</td>)}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        empty ? (
          <p className="flex items-center justify-center px-6 text-center font-hand text-[16px] text-ink-3" style={{ height }}>
            numbers appear after the first posts get views.
          </p>
        ) : (
        <div className="relative px-2" style={{ height }}>
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={data} margin={{ top: 8, right: 16, bottom: 0, left: 0 }}>
              <defs>
                <linearGradient id={`fill-${id}`} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="var(--series-1)" stopOpacity={0.14} />
                  <stop offset="100%" stopColor="var(--series-1)" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid vertical={false} stroke="var(--chart-grid)" strokeWidth={1} />
              <XAxis
                dataKey="date" tickFormatter={fmtDay} tickLine={false} axisLine={false}
                tick={{ fill: "var(--chart-axis)", fontSize: 11 }} minTickGap={28} dy={6}
              />
              <YAxis
                tickFormatter={(v) => num(v, { compact: v >= 10000 })} tickLine={false} axisLine={false}
                tick={{ fill: "var(--chart-axis)", fontSize: 11 }} width={48} allowDecimals={false}
              />
              <Tooltip
                cursor={{ stroke: "var(--line-strong)", strokeWidth: 1 }}
                content={({ active, payload, label }) =>
                  active && payload?.length ? (
                    <div className="rounded-[10px] border border-line bg-elev px-3 py-2 text-[12px] shadow-[var(--shadow)]">
                      <p className="text-ink-3">{fmtDay(String(label))}</p>
                      <p className="mt-0.5 font-medium text-ink tabular">{num(Number(payload[0].value))} {LABEL[metric].toLowerCase()}</p>
                    </div>
                  ) : null
                }
              />
              <Area
                type="monotone" dataKey={metric} stroke="var(--series-1)" strokeWidth={2} fill={`url(#fill-${id})`}
                dot={false} activeDot={{ r: 4.5, stroke: "var(--bg-elev)", strokeWidth: 2, fill: "var(--series-1)" }}
                isAnimationActive={false}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
        )
      )}
    </div>
  );
}
