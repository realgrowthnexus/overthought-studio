"use client";
import * as React from "react";
import Link from "next/link";
import { AnimatePresence, motion } from "motion/react";
import { AlertTriangle, ChevronRight } from "lucide-react";
import { browserClient } from "@/lib/supabase/browser";
import type { Service } from "@/lib/types";
import {
  SERVICE_LABEL, SERVICE_ROLE, SERVICE_STATUS_LABEL, cn, num, relTime, serviceFix, serviceTone, usd,
} from "@/lib/format";
import { Lamp } from "@/components/ui/primitives";

export function useLiveServices(initial: Service[]) {
  const [services, setServices] = React.useState(initial);
  React.useEffect(() => setServices(initial), [initial]);
  React.useEffect(() => {
    const supabase = browserClient();
    const ch = supabase
      .channel(`services-${Math.random().toString(36).slice(2, 7)}`)
      .on("postgres_changes", { event: "*", schema: "public", table: "services" }, (p) => {
        const row = p.new as Service;
        if (!row?.name) return;
        setServices((prev) => prev.map((s) => (s.name === row.name ? { ...s, ...row } : s)));
      })
      .subscribe();
    return () => {
      supabase.removeChannel(ch);
    };
  }, []);
  return services;
}

const BLOCKING = new Set(["down", "out_of_credits"]);

/** Global red bar. Always says WHY production stopped and what fixes it. */
export function ServiceAlertBar({ initial, paused }: { initial: Service[]; paused: boolean }) {
  const services = useLiveServices(initial);
  const broken = services.filter((s) => BLOCKING.has(s.status));
  return (
    <AnimatePresence initial={false}>
      {(broken.length > 0 || paused) && (
        <motion.div
          initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }} exit={{ height: 0, opacity: 0 }}
          className="overflow-hidden"
          role="alert"
        >
          <div className="space-y-2 px-4 pt-4 sm:px-8">
            {paused && (
              <div className="flex items-center gap-3 rounded-[12px] border border-warn/30 bg-warn-soft px-4 py-2.5 text-[13px] text-ink">
                <Lamp tone="warn" />
                <span className="flex-1"><strong className="font-semibold">Studio is paused.</strong> Nothing new starts until you resume it on the Overview page.</span>
              </div>
            )}
            {broken.map((s) => {
              const fix = serviceFix(s.name, s.status);
              return (
                <Link
                  key={s.name}
                  href={fix.href}
                  className="group flex items-start gap-3 rounded-[12px] border border-bad/30 bg-bad-soft px-4 py-2.5 text-[13px] text-ink transition-colors hover:border-bad/60"
                >
                  <AlertTriangle className="mt-0.5 size-4 shrink-0 text-bad" aria-hidden />
                  <span className="flex-1 leading-relaxed">
                    <strong className="font-semibold">{SERVICE_LABEL[s.name]}: {SERVICE_STATUS_LABEL[s.status].toLowerCase()}.</strong>{" "}
                    {s.message ? `${s.message} ` : ""}
                    <span className="text-ink-2">{fix.text}</span>
                  </span>
                  <ChevronRight className="mt-0.5 size-4 shrink-0 text-ink-3 transition-transform group-hover:translate-x-0.5" aria-hidden />
                </Link>
              );
            })}
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

function balanceText(s: Service): string | null {
  if (s.balance == null) return null;
  const unit = (s.balance_unit ?? "").toLowerCase();
  if (unit === "usd" || unit === "$") {
    return s.balance_limit != null ? `${usd(s.balance)} of ${usd(s.balance_limit, 0)}` : `${usd(s.balance)} left`;
  }
  if (unit === "chars" || unit === "characters") {
    return s.balance_limit != null ? `${num(s.balance)} / ${num(s.balance_limit)} chars left` : `${num(s.balance)} chars left`;
  }
  if (unit === "gb" || unit === "mb") {
    return s.balance_limit != null ? `${s.balance} / ${s.balance_limit} ${s.balance_unit} used` : `${s.balance} ${s.balance_unit}`;
  }
  return s.balance_limit != null ? `${num(s.balance)} / ${num(s.balance_limit)} ${s.balance_unit ?? ""}` : `${num(s.balance)} ${s.balance_unit ?? ""}`;
}

function ratio(s: Service): number | null {
  if (s.balance == null || s.balance_limit == null || s.balance_limit <= 0) return null;
  const unit = (s.balance_unit ?? "").toLowerCase();
  // storage reports usage, the rest report what's left
  if (unit === "gb" || unit === "mb") return 1 - s.balance / s.balance_limit;
  return s.balance / s.balance_limit;
}

/** Overview strip: one row per dependency with live status, balance and last check. */
export function ServiceStrip({ initial }: { initial: Service[] }) {
  const services = useLiveServices(initial);
  return (
    <ul className="grid grid-cols-1 gap-px overflow-hidden rounded-b-[var(--radius-lg)] bg-line sm:grid-cols-2 xl:grid-cols-3">
      {services.map((s) => {
        const limited = s.name === "anthropic" && (s.details as { limited?: boolean } | null)?.limited === true;
        const tone = limited ? "warn" : serviceTone(s.status);
        // on the Claude plan there is no money balance: an old API-credit number would only mislead
        const onPlan = s.name === "anthropic" && (s.details as { backend?: string } | null)?.backend !== "api";
        const bal = onPlan ? null : balanceText(s);
        const r = onPlan ? null : ratio(s);
        return (
          <li key={s.name} className="flex flex-col gap-2 bg-elev px-5 py-4">
            <div className="flex items-center justify-between gap-3">
              <div className="flex items-center gap-2.5">
                <Lamp tone={tone} live={s.status === "ok" && s.name === "worker"} />
                <span className="text-[14px] font-medium text-ink">{SERVICE_LABEL[s.name]}</span>
              </div>
              <span className={cn("text-[12px]", tone === "bad" ? "text-bad" : tone === "warn" ? "text-warn" : tone === "good" ? "text-good" : "text-ink-3")}>
                {limited ? "Limit reached" : s.name === "anthropic" && s.status === "unconfigured" ? "Not signed in" : SERVICE_STATUS_LABEL[s.status]}
              </span>
            </div>
            <p className="text-[12px] text-ink-3">{s.message || SERVICE_ROLE[s.name]}</p>
            {(bal || r != null) && (
              <div className="flex items-center gap-3">
                {r != null && (
                  <div className="h-1 flex-1 overflow-hidden rounded-full bg-elev-2">
                    <div
                      className={cn("h-full rounded-full", r < 0.1 ? "bg-bad" : r < 0.25 ? "bg-warn" : "bg-ink-3")}
                      style={{ width: `${Math.max(2, Math.min(100, r * 100))}%` }}
                    />
                  </div>
                )}
                {bal && <span className="shrink-0 text-[12px] text-ink-2 tabular">{bal}</span>}
              </div>
            )}
            <p className="text-[11px] text-ink-3" suppressHydrationWarning>{s.checked_at ? `Checked ${relTime(s.checked_at)}` : "Not checked yet"}</p>
          </li>
        );
      })}
    </ul>
  );
}
