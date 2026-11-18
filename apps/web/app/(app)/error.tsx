"use client";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty";

export default function Error({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return (
    <EmptyState
      title="This page couldn't load"
      action={<Button variant="primary" onClick={reset}>Try again</Button>}
    >
      {error.message?.includes("SUPABASE") || error.message?.includes("MASTER_KEY")
        ? error.message
        : "The database didn't answer in time or returned an error. Your channels keep running on the worker regardless."}
      {error.digest && <span className="mt-2 block text-[11px]">Reference: {error.digest}</span>}
    </EmptyState>
  );
}
