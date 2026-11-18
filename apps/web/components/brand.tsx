import * as React from "react";
import { cn } from "@/lib/format";

/** The brand's tangled yellow scribble — the "overthinking" cloud. Hand-tuned path, not generated. */
export function Scribble({ className, strokeWidth = 2.2 }: { className?: string; strokeWidth?: number }) {
  return (
    <svg viewBox="0 0 48 32" fill="none" className={cn("text-accent", className)} aria-hidden>
      <path
        d="M8 20c-3-1-4-6 0-8 2-6 9-7 12-3 3-5 11-4 12 1 6-1 9 6 4 9 2 5-5 8-9 5-3 4-11 4-13-1-4 2-9 0-6-3m6-6c3-3 8 2 5 4-3 2-6-3-1-5 5-1 7 4 3 6m3-5c4-2 7 1 5 4-2 2-5 0-3-2 3-2 6 1 4 4"
        stroke="currentColor"
        strokeWidth={strokeWidth}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function Wordmark({ className, size = "md" }: { className?: string; size?: "sm" | "md" | "lg" }) {
  const text = size === "lg" ? "text-[34px]" : size === "sm" ? "text-[19px]" : "text-[23px]";
  const mark = size === "lg" ? "w-12" : size === "sm" ? "w-7" : "w-8";
  return (
    <span className={cn("inline-flex items-center gap-1.5 text-ink", className)}>
      <span className={cn("font-hand leading-none tracking-[-0.01em]", text)}>overthought</span>
      <Scribble className={cn(mark, "-mt-2")} />
    </span>
  );
}

/** Hand-drawn margin note with an arrow, echoing the "→ Gilovich · Cornell · 2000" source notes in the videos. */
export function MarginNote({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <span className={cn("inline-flex items-center gap-2 font-hand text-[15px] text-accent-text", className)}>
      <svg viewBox="0 0 36 14" className="h-3.5 w-9 shrink-0" fill="none" aria-hidden>
        <path d="M1 8c6-1 13 1 20-1 4-1 8 0 12 0m0 0-5-5m5 5-5 5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
      {children}
    </span>
  );
}

/** Wobbly hand-drawn underline for the single word that matters on a screen (used once per page at most). */
export function WobbleUnderline({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 120 8" preserveAspectRatio="none" className={cn("h-2 w-full text-accent", className)} aria-hidden>
      <path d="M2 5c12-2 22 1 34-1s22 2 34 0 24-2 36 1 10 0 12-1" stroke="currentColor" strokeWidth="2.6" strokeLinecap="round" fill="none" />
    </svg>
  );
}

/** Stick figure used in empty states. White-ink line drawing; the yellow lives in the scribble only. */
export function StickFigure({ className, thinking = true }: { className?: string; thinking?: boolean }) {
  return (
    <svg viewBox="0 0 120 140" fill="none" className={cn("text-ink", className)} aria-hidden>
      {thinking && (
        <g transform="translate(36 2) scale(1.05)" className="text-accent">
          <path
            d="M8 20c-3-1-4-6 0-8 2-6 9-7 12-3 3-5 11-4 12 1 6-1 9 6 4 9 2 5-5 8-9 5-3 4-11 4-13-1-4 2-9 0-6-3m6-6c3-3 8 2 5 4-3 2-6-3-1-5 5-1 7 4 3 6"
            stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
          />
        </g>
      )}
      <g stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="60" cy="50" r="11" />
        <path d="M60 61v38" />
        <path d="M60 72c-8 4-14 10-18 17" />
        <path d="M60 72c7 3 12 8 15 14" />
        <path d="M60 99l-12 30" />
        <path d="M60 99l11 30" />
      </g>
    </svg>
  );
}
