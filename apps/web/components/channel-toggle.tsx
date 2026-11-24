"use client";
import * as React from "react";
import { Switch } from "@/components/ui/switch";
import { Button } from "@/components/ui/button";
import { setChannelStatus } from "@/lib/actions";
import { useAction } from "@/components/use-action";

const BREAKER = "Stopped making new videos";

export function ChannelToggle({ id, status, blockedReason }: { id: string; status: "active" | "paused"; blockedReason?: string | null }) {
  const [on, setOn] = React.useState(status === "active");
  React.useEffect(() => setOn(status === "active"), [status]);
  const { pending, run } = useAction();
  const stopped = status === "active" && Boolean(blockedReason?.startsWith(BREAKER));
  return (
    <div className="flex items-center gap-2">
      {stopped && (
        <Button size="sm" variant="primary" loading={pending} onClick={() => run(() => setChannelStatus(id, "active"))}>
          Resume
        </Button>
      )}
      <Switch
        label={on ? "Pause channel" : "Start channel"}
        checked={on}
        disabled={pending}
        onCheckedChange={(v) => {
          setOn(v);
          run(() => setChannelStatus(id, v ? "active" : "paused"));
        }}
      />
    </div>
  );
}
