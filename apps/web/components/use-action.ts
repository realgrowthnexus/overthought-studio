"use client";
import * as React from "react";
import { toast } from "sonner";
import type { ActionResult } from "@/lib/actions";

/** Runs a server action inside a transition and reports the result as a toast. */
export function useAction() {
  const [pending, start] = React.useTransition();
  const run = React.useCallback(
    <T,>(fn: () => Promise<ActionResult<T>>, opts?: { onOk?: (r: ActionResult<T> & { ok: true }) => void; quiet?: boolean }) => {
      start(async () => {
        try {
          const r = await fn();
          if (r.ok) {
            if (!opts?.quiet && r.message) toast.success(r.message);
            opts?.onOk?.(r);
          } else {
            toast.error(r.error);
          }
        } catch (e) {
          toast.error(e instanceof Error ? e.message : "Something went wrong.");
        }
      });
    },
    [],
  );
  return { pending, run };
}
