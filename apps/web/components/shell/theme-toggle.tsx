"use client";
import * as React from "react";
import { useTheme } from "next-themes";
import { Moon, Sun, Monitor } from "lucide-react";

const ORDER = ["dark", "light", "system"] as const;

export function ThemeToggle() {
  const { theme, setTheme } = useTheme();
  const [mounted, setMounted] = React.useState(false);
  React.useEffect(() => setMounted(true), []);
  const current = (mounted ? theme : "dark") as (typeof ORDER)[number];
  const next = ORDER[(ORDER.indexOf(current) + 1) % ORDER.length];
  const Icon = current === "light" ? Sun : current === "system" ? Monitor : Moon;
  const label = `Theme: ${current}. Switch to ${next}`;
  return (
    <button
      type="button"
      onClick={() => setTheme(next)}
      className="inline-flex size-9 items-center justify-center rounded-[9px] text-ink-3 transition-colors hover:bg-elev-2 hover:text-ink"
      aria-label={label}
      title={label}
    >
      <Icon className="size-[17px]" strokeWidth={1.8} />
    </button>
  );
}
