"use client";
import * as React from "react";
import { useRouter } from "next/navigation";
import { browserClient } from "@/lib/supabase/browser";

/**
 * Re-renders the current server page when any of the given tables change.
 * Debounced so a burst of worker updates becomes one refresh.
 */
export function LiveRefresh({ tables, filter }: { tables: string[]; filter?: string }) {
  const router = useRouter();
  const key = tables.join(",") + (filter ?? "");
  React.useEffect(() => {
    const supabase = browserClient();
    let timer: ReturnType<typeof setTimeout> | null = null;
    const bump = () => {
      if (timer) clearTimeout(timer);
      timer = setTimeout(() => router.refresh(), 600);
    };
    const channel = supabase.channel(`live:${key}:${Math.random().toString(36).slice(2, 8)}`);
    for (const table of tables) {
      channel.on(
        "postgres_changes",
        { event: "*", schema: "public", table, ...(filter ? { filter } : {}) },
        bump,
      );
    }
    channel.subscribe();
    return () => {
      if (timer) clearTimeout(timer);
      supabase.removeChannel(channel);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, router]);
  return null;
}
