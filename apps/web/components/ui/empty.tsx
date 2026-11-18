import * as React from "react";
import { StickFigure } from "@/components/brand";
import { cn } from "@/lib/format";

export function EmptyState({
  title, children, action, figure = true, className,
}: { title: string; children?: React.ReactNode; action?: React.ReactNode; figure?: boolean; className?: string }) {
  return (
    <div className={cn("flex flex-col items-center px-6 py-10 text-center", className)}>
      {figure && <StickFigure className="mb-3 h-24 w-20 opacity-90" />}
      <h3 className="text-[15px] font-semibold text-ink">{title}</h3>
      {children && <div className="mt-1.5 max-w-[46ch] text-[13px] leading-relaxed text-ink-3">{children}</div>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}
