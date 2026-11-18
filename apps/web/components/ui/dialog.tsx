"use client";
import * as React from "react";
import { AnimatePresence, motion } from "motion/react";
import { X } from "lucide-react";
import { cn } from "@/lib/format";

export function Dialog({
  open, onClose, title, description, children, className, wide,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  description?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
  wide?: boolean;
}) {
  const ref = React.useRef<HTMLDivElement>(null);
  const titleId = React.useId();
  const descId = React.useId();

  React.useEffect(() => {
    if (!open) return;
    const prev = document.activeElement as HTMLElement | null;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
      // keep Tab inside the dialog while it is open
      if (e.key === "Tab" && ref.current) {
        const items = ref.current.querySelectorAll<HTMLElement>(
          'a[href],button:not([disabled]),input:not([disabled]),select:not([disabled]),textarea:not([disabled]),[tabindex]:not([tabindex="-1"])',
        );
        if (!items.length) return;
        const first = items[0];
        const last = items[items.length - 1];
        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault();
          last.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault();
          first.focus();
        }
      }
    };
    document.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    const t = setTimeout(() => {
      const el = ref.current?.querySelector<HTMLElement>("input,textarea,select,button[data-autofocus]");
      el?.focus();
    }, 50);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = "";
      clearTimeout(t);
      prev?.focus?.();
    };
  }, [open, onClose]);

  return (
    <AnimatePresence>
      {open && (
        <div className="fixed inset-0 z-50 flex items-end justify-center sm:items-center sm:p-6">
          <motion.div
            className="absolute inset-0 bg-black/55 backdrop-blur-[2px]"
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            onClick={onClose}
          />
          <motion.div
            ref={ref}
            role="dialog"
            aria-modal="true"
            aria-labelledby={titleId}
            aria-describedby={description ? descId : undefined}
            className={cn(
              "relative z-10 max-h-[92dvh] w-full overflow-y-auto rounded-t-[20px] border border-line bg-elev shadow-[var(--shadow)] sm:rounded-[18px]",
              wide ? "sm:max-w-2xl" : "sm:max-w-md",
              className,
            )}
            initial={{ opacity: 0, y: 24, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 16, scale: 0.98 }}
            transition={{ type: "spring", stiffness: 420, damping: 34 }}
          >
            <div className="sticky top-0 z-10 flex items-start justify-between gap-4 border-b border-line bg-elev px-5 py-4">
              <div>
                <h2 id={titleId} className="text-[16px] font-semibold text-ink">{title}</h2>
                {description && <p id={descId} className="mt-0.5 text-[13px] leading-relaxed text-ink-3">{description}</p>}
              </div>
              <button
                type="button"
                onClick={onClose}
                className="tap relative -mt-1 -mr-2 flex size-9 shrink-0 items-center justify-center rounded-[9px] text-ink-3 transition-colors hover:bg-elev-2 hover:text-ink"
                aria-label="Close"
              >
                <X className="size-4" aria-hidden />
              </button>
            </div>
            <div className="px-5 py-4">{children}</div>
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );
}
