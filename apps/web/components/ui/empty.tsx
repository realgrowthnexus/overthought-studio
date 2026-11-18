import * as React from "react";
import { StickFigure } from "@/components/brand";
import { cn } from "@/lib/format";

export function EmptyState({
  title, children, action, figure = true, className,
}: { title: string; children?: React.ReactNode; action?: React.ReactNode; figure?: boolean; className?: string }) {
  return (
    <div className={cn("flex flex-col items-center px-6 py-12 text-center", className)}>
      {figure && <StickFigure className="mb-4 h-24 w-20" />}
      <h3 className="text-[16px] font-semibold tracking-[-0.01em] text-balance text-ink">{title}</h3>
      {children && <div className="mt-1.5 max-w-[48ch] text-[13.5px] leading-relaxed text-pretty text-ink-3">{children}</div>}
      {action && <div className="mt-5 flex flex-wrap items-center justify-center gap-2">{action}</div>}
    </div>
  );
}
