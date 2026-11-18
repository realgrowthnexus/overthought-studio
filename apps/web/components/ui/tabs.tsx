"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { motion } from "motion/react";
import { cn } from "@/lib/format";

export function LinkTabs({ tabs, layoutId = "tabs" }: { tabs: { href: string; label: string; count?: number }[]; layoutId?: string }) {
  const pathname = usePathname();
  const active = [...tabs].sort((a, b) => b.href.length - a.href.length).find((t) => pathname === t.href || pathname.startsWith(t.href + "/"))?.href ?? tabs[0]?.href;
  return (
    <nav className="-mx-1 mb-6 flex gap-1 overflow-x-auto border-b border-line px-1" aria-label="Sections">
      {tabs.map((t) => {
        const isActive = t.href === active;
        return (
          <Link
            key={t.href}
            href={t.href}
            aria-current={isActive ? "page" : undefined}
            className={cn(
              "relative shrink-0 px-3 pt-2 pb-3 text-[14px] transition-colors",
              isActive ? "text-ink font-medium" : "text-ink-3 hover:text-ink",
            )}
          >
            {t.label}
            {typeof t.count === "number" && <span className="ml-1.5 text-[12px] text-ink-3 tabular">{t.count}</span>}
            {isActive && (
              <motion.span layoutId={layoutId} className="absolute inset-x-2 -bottom-px h-[2px] rounded-full bg-accent" transition={{ type: "spring", stiffness: 500, damping: 40 }} />
            )}
          </Link>
        );
      })}
    </nav>
  );
}

export function SegmentedControl<T extends string>({
  value, onChange, options, label,
}: { value: T; onChange: (v: T) => void; options: { value: T; label: string }[]; label: string }) {
  return (
    <div role="radiogroup" aria-label={label} className="inline-flex rounded-[10px] border border-line bg-bg p-0.5">
      {options.map((o) => (
        <button
          key={o.value}
          role="radio"
          aria-checked={value === o.value}
          onClick={() => onChange(o.value)}
          className={cn(
            "relative h-8 rounded-[8px] px-3 text-[13px] transition-colors",
            value === o.value ? "text-ink" : "text-ink-3 hover:text-ink",
          )}
        >
          {value === o.value && (
            <motion.span layoutId={`seg-${label}`} className="absolute inset-0 rounded-[8px] border border-line bg-elev shadow-sm" transition={{ type: "spring", stiffness: 500, damping: 40 }} />
          )}
          <span className="relative">{o.label}</span>
        </button>
      ))}
    </div>
  );
}
