import * as React from "react";
import { cn } from "@/lib/format";

export function StatTile({
  label, value, delta, deltaTone = "neutral", foot, meter, className,
}: {
  label: string;
  value: React.ReactNode;
  delta?: React.ReactNode;
  deltaTone?: "good" | "bad" | "neutral";
  foot?: React.ReactNode;
  meter?: { value: number; max: number };
  className?: string;
}) {
  const pct = meter && meter.max > 0 ? Math.min(1, meter.value / meter.max) : null;
  return (
    <div className={cn("flex flex-col gap-1 px-5 py-4", className)}>
      <span className="text-[13px] text-ink-3">{label}</span>
      <div className="flex items-baseline gap-2">
        <span className="text-[28px] leading-none font-semibold tracking-[-0.03em] text-ink tabular">{value}</span>
        {delta && (
          <span className={cn("text-[12px] tabular", deltaTone === "good" ? "text-good" : deltaTone === "bad" ? "text-bad" : "text-ink-3")}>
            {delta}
          </span>
        )}
      </div>
      {pct !== null && (
        <div className="mt-2 h-1 overflow-hidden rounded-full bg-elev-2" aria-hidden>
          <div
            className={cn("h-full rounded-full", pct > 0.9 ? "bg-bad" : pct > 0.75 ? "bg-warn" : "bg-accent-mark")}
            style={{ width: `${Math.max(2, pct * 100)}%` }}
          />
        </div>
      )}
      {foot && <span className="mt-1 text-[12px] text-ink-3">{foot}</span>}
    </div>
  );
}
