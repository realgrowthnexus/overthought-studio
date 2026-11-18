"use client";
import * as React from "react";
import { Check, Copy } from "lucide-react";

export function CopyField({ label, value }: { label: string; value: string }) {
  const [copied, setCopied] = React.useState(false);
  return (
    <div className="flex min-w-0 items-center gap-3 rounded-[10px] border border-line bg-bg py-1.5 pr-1.5 pl-3">
      <span className="hidden w-32 shrink-0 text-[12px] text-ink-3 sm:block">{label}</span>
      <span className="min-w-0 flex-1"><span className="block text-[11px] text-ink-3 sm:hidden">{label}</span><code className="block truncate font-mono text-[12.5px] text-ink">{value}</code></span>
      <button
        type="button"
        onClick={async () => {
          await navigator.clipboard.writeText(value);
          setCopied(true);
          setTimeout(() => setCopied(false), 1400);
        }}
        className="flex size-8 shrink-0 items-center justify-center rounded-[8px] text-ink-3 hover:bg-elev-2 hover:text-ink"
        aria-label={`Copy ${label}`}
      >
        {copied ? <Check className="size-4 text-good" /> : <Copy className="size-4" />}
      </button>
    </div>
  );
}
