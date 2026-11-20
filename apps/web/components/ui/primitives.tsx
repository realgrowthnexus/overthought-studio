import * as React from "react";
import { cn, type Tone } from "@/lib/format";

/* ---------- Panel: the one container. Hierarchy comes from padding + title, not from more boxes. ---------- */
export function Panel({
  className, children, as: As = "section", ...rest
}: React.HTMLAttributes<HTMLElement> & { as?: "section" | "div" | "article" }) {
  return (
    <As
      className={cn("rounded-[var(--radius-lg)] border border-line bg-elev shadow-[var(--shadow)]", className)}
      {...rest}
    >
      {children}
    </As>
  );
}

export function PanelHeader({
  title, description, action, className,
}: { title: React.ReactNode; description?: React.ReactNode; action?: React.ReactNode; className?: string }) {
  return (
    <div className={cn("flex items-start justify-between gap-4 px-5 pt-4 pb-3", className)}>
      <div className="min-w-0">
        <h2 className="text-[15px] font-semibold tracking-[-0.01em] text-ink">{title}</h2>
        {description && <p className="mt-0.5 text-[13px] text-ink-3">{description}</p>}
      </div>
      {action && <div className="shrink-0">{action}</div>}
    </div>
  );
}

/* ---------- Page header ---------- */
export function PageHeader({
  title, description, actions, back,
}: { title: React.ReactNode; description?: React.ReactNode; actions?: React.ReactNode; back?: React.ReactNode }) {
  return (
    <header className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
      <div className="min-w-0">
        {back && <div className="mb-2">{back}</div>}
        <h1 className="text-[26px] leading-[1.15] font-semibold tracking-[-0.025em] text-ink sm:text-[30px]">{title}</h1>
        {description && <p className="mt-1.5 max-w-[62ch] text-[14px] leading-relaxed text-ink-3">{description}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </header>
  );
}

/* ---------- Badge ---------- */
const toneClass: Record<Tone, string> = {
  neutral: "bg-elev-2 text-ink-2",
  good: "bg-good-soft text-good",
  warn: "bg-warn-soft text-warn",
  bad: "bg-bad-soft text-bad",
  accent: "bg-accent-soft text-accent-text",
  info: "bg-info-soft text-info",
};
const dotClass: Record<Tone, string> = {
  neutral: "bg-ink-3", good: "bg-good", warn: "bg-warn", bad: "bg-bad", accent: "bg-accent-mark", info: "bg-info",
};

export function Badge({
  tone = "neutral", children, dot, live, className,
}: { tone?: Tone; children: React.ReactNode; dot?: boolean; live?: boolean; className?: string }) {
  return (
    <span
      className={cn(
        "inline-flex h-6 items-center gap-1.5 rounded-full px-2.5 text-[12px] font-medium whitespace-nowrap",
        toneClass[tone], className,
      )}
    >
      {dot && <span className={cn("size-1.5 rounded-full", dotClass[tone], live && "lamp-live")} aria-hidden />}
      {children}
    </span>
  );
}

export function Lamp({ tone, live, className }: { tone: Tone; live?: boolean; className?: string }) {
  return <span className={cn("inline-block size-2 rounded-full", dotClass[tone], live && "lamp-live", className)} aria-hidden />;
}

/* ---------- Form ---------- */
export const inputClass =
  "w-full rounded-[10px] border border-line-input bg-bg px-3 text-[14px] text-ink placeholder:text-ink-3 " +
  "transition-[border-color,box-shadow] duration-150 hover:border-ink-3 " +
  "focus:border-ink focus:outline-none focus:ring-4 focus:ring-[var(--accent-soft)] " +
  "aria-invalid:border-bad disabled:cursor-not-allowed disabled:opacity-60";

export const Input = React.forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(
  function Input({ className, ...props }, ref) {
    return <input ref={ref} className={cn(inputClass, "h-10", className)} {...props} />;
  },
);

export const Textarea = React.forwardRef<HTMLTextAreaElement, React.TextareaHTMLAttributes<HTMLTextAreaElement>>(
  function Textarea({ className, ...props }, ref) {
    return <textarea ref={ref} className={cn(inputClass, "min-h-24 py-2.5 leading-relaxed", className)} {...props} />;
  },
);

export const Select = React.forwardRef<HTMLSelectElement, React.SelectHTMLAttributes<HTMLSelectElement>>(
  function Select({ className, children, ...props }, ref) {
    return (
      <div className="relative">
        <select ref={ref} className={cn(inputClass, "h-10 appearance-none pr-9", className)} {...props}>
          {children}
        </select>
        <svg className="pointer-events-none absolute top-1/2 right-3 size-4 -translate-y-1/2 text-ink-3" viewBox="0 0 16 16" fill="none" aria-hidden>
          <path d="M4 6l4 4 4-4" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </div>
    );
  },
);

export function Field({
  label, hint, error, htmlFor, children, className,
}: { label: React.ReactNode; hint?: React.ReactNode; error?: string; htmlFor?: string; children: React.ReactNode; className?: string }) {
  return (
    <div className={cn("flex flex-col gap-1.5", className)}>
      <label htmlFor={htmlFor} className="text-[13px] font-medium text-ink-2">{label}</label>
      {children}
      {error ? <p className="text-[12px] text-bad" role="alert">{error}</p> : hint ? <p className="text-[12px] leading-snug text-ink-3">{hint}</p> : null}
    </div>
  );
}

/* ---------- Skeleton ---------- */
export function Skeleton({ className }: { className?: string }) {
  return <div className={cn("skeleton", className)} aria-hidden />;
}

/* ---------- Progress ---------- */
export function Progress({ value, live, tone = "accent", className }: { value: number; live?: boolean; tone?: "accent" | "good" | "bad"; className?: string }) {
  const fill = tone === "good" ? "bg-good" : tone === "bad" ? "bg-bad" : "bg-accent-mark";
  return (
    <div className={cn("h-1.5 w-full overflow-hidden rounded-full bg-elev-2", className)} role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(value)}>
      <div
        className={cn("h-full w-full rounded-full transition-transform duration-700 ease-[var(--ease-out-soft)]", fill, live && "progress-live")}
        style={{ transform: `translateX(${Math.max(3, Math.min(100, value)) - 100}%)` }}
      />
    </div>
  );
}

/* ---------- Key/value ---------- */
export function KV({ k, v, className }: { k: React.ReactNode; v: React.ReactNode; className?: string }) {
  return (
    <div className={cn("flex items-baseline justify-between gap-4 py-2 text-[13px]", className)}>
      <dt className="text-ink-3">{k}</dt>
      <dd className="text-right text-ink tabular">{v}</dd>
    </div>
  );
}
