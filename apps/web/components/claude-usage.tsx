"use client";
import * as React from "react";
import type { Service } from "@/lib/types";
import { claudeView } from "@/lib/claude-usage";
import { useLiveServices } from "@/components/services";
import { Badge, Lamp, Progress } from "@/components/ui/primitives";
import { CopyField } from "@/components/copy-field";
import { cn } from "@/lib/format";

export const CONNECT_COMMAND = "sudo bash /opt/overthought-studio/src/infra/connect-claude.sh";

function Meter({ label, pct, resets }: { label: string; pct: number; resets: string | null }) {
  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex items-baseline justify-between gap-3 text-[13px]">
        <span className="text-ink">{label}</span>
        <span className="tabular text-ink-2">
          {pct}% used{resets ? <span className="text-ink-3"> · resets {resets}</span> : null}
        </span>
      </div>
      <Progress value={pct} tone={pct >= 90 ? "bad" : "accent"} />
    </div>
  );
}

/** Claude plan card: sign-in state, the 5-hour and weekly limits, and how many more videos fit this week. */
export function ClaudeUsageCard({ initial }: { initial: Service[] }) {
  const services = useLiveServices(initial);
  const v = claudeView(services.find((s) => s.name === "anthropic"), new Date());
  const tone = v.state === "connected" || v.state === "api" ? "good" : v.state === "problem" ? "bad" : "warn";
  return (
    <div className="flex flex-col gap-4 px-5 pb-5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex min-w-0 items-center gap-2.5">
          <Lamp tone={tone} />
          <span className="text-[14px] font-medium text-ink">{v.headline}</span>
        </div>
        {v.estimate && <Badge tone="neutral">Estimate</Badge>}
      </div>

      {v.state === "not_signed_in" ? (
        <div className="flex flex-col gap-2 text-[13px] leading-relaxed text-ink-2">
          <p>Run this once on the VPS. It prints a link: open it, sign in with your Claude account, then paste the code back. No API key needed.</p>
          <CopyField label="Command" value={CONNECT_COMMAND} />
        </div>
      ) : (
        <>
          {(v.fiveHour || v.week) ? (
            <div className="flex flex-col gap-3">
              {v.fiveHour && <Meter label="5-hour limit" pct={v.fiveHour.pct} resets={v.fiveHour.resets} />}
              {v.week && <Meter label="Weekly limit" pct={v.week.pct} resets={v.week.resets} />}
            </div>
          ) : (
            <p className="text-[13px] text-ink-3">{v.limitsNote}</p>
          )}
          {v.pacing && (
            <p className="rounded-[10px] border border-warn/30 bg-warn-soft px-3 py-2 text-[13px] text-ink">
              The weekly limit is running low, so evening videos are paused until it resets. Morning videos keep going.
            </p>
          )}
          {v.summary && <p className={cn("text-[13px]", v.estimate ? "text-ink-3" : "text-ink-2")}>{v.summary}</p>}
        </>
      )}
    </div>
  );
}
