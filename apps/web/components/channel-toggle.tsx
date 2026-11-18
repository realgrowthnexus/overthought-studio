"use client";
import * as React from "react";
import { Switch } from "@/components/ui/switch";
import { setChannelStatus } from "@/lib/actions";
import { useAction } from "@/components/use-action";

export function ChannelToggle({ id, status }: { id: string; status: "active" | "paused" }) {
  const [on, setOn] = React.useState(status === "active");
  React.useEffect(() => setOn(status === "active"), [status]);
  const { pending, run } = useAction();
  return (
    <Switch
      label={on ? "Pause channel" : "Start channel"}
      checked={on}
      disabled={pending}
      onCheckedChange={(v) => {
        setOn(v);
        run(() => setChannelStatus(id, v ? "active" : "paused"));
      }}
    />
  );
}
