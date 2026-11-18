"use client";
import { cancelJob, retryJob } from "@/lib/actions";
import { useAction } from "@/components/use-action";
import { Button } from "@/components/ui/button";
import type { JobStatus } from "@/lib/types";

export function JobRowActions({ id, status }: { id: number; status: JobStatus }) {
  const { pending, run } = useAction();
  if (status === "failed" || status === "cancelled" || status === "waiting") {
    return (
      <div className="flex justify-end gap-1">
        <Button size="sm" variant="ghost" loading={pending} onClick={() => run(() => retryJob(id))}>Retry</Button>
        {status === "waiting" && <Button size="sm" variant="quiet" onClick={() => run(() => cancelJob(id))}>Cancel</Button>}
      </div>
    );
  }
  if (status === "queued") {
    return <Button size="sm" variant="quiet" loading={pending} onClick={() => run(() => cancelJob(id))}>Cancel</Button>;
  }
  return null;
}
