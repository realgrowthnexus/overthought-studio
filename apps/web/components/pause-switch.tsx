"use client";
import * as React from "react";
import { Switch } from "@/components/ui/switch";
import { setGlobalPause } from "@/lib/actions";
import { useAction } from "@/components/use-action";

export function PauseSwitch({ paused }: { paused: boolean }) {
  const [running, setRunning] = React.useState(!paused);
  React.useEffect(() => setRunning(!paused), [paused]);
  const { pending, run } = useAction();
  return (
    <label className="flex items-center gap-3 rounded-[12px] border border-line bg-elev py-2 pr-2 pl-4">
      <span className="flex flex-col leading-tight">
        <span className="text-[13px] font-medium text-ink">{running ? "Studio running" : "Studio paused"}</span>
        <span className="text-[11px] text-ink-3">{running ? "Making and posting on schedule" : "Nothing new will start"}</span>
      </span>
      <Switch
        size="lg"
        label="Studio running"
        checked={running}
        disabled={pending}
        onCheckedChange={(v) => {
          setRunning(v);
          run(() => setGlobalPause(!v), { onOk: () => undefined });
        }}
      />
    </label>
  );
}
