"use client";
import * as React from "react";
import { Upload } from "lucide-react";
import { importStats } from "@/lib/actions";
import { useAction } from "@/components/use-action";
import { Button } from "@/components/ui/button";
import { Field, Panel, PanelHeader, Select } from "@/components/ui/primitives";
import { cn } from "@/lib/format";

export function ImportStats({ channels, defaultChannel }: { channels: { id: string; name: string }[]; defaultChannel?: string }) {
  const { pending, run } = useAction();
  const [file, setFile] = React.useState<File | null>(null);
  const [drag, setDrag] = React.useState(false);
  const [channel, setChannel] = React.useState(defaultChannel ?? channels[0]?.id ?? "");
  const inputRef = React.useRef<HTMLInputElement>(null);

  return (
    <Panel>
      <PanelHeader title="Add watch-time data" description="TikTok's API doesn't share watch time. Export it from TikTok Studio once a week and drop it here." />
      <form
        className="flex flex-col gap-4 px-5 pb-5"
        onSubmit={(e) => {
          e.preventDefault();
          if (!file || !channel) return;
          const fd = new FormData();
          fd.set("file", file);
          fd.set("channel_id", channel);
          run(() => importStats(fd), { onOk: () => { setFile(null); if (inputRef.current) inputRef.current.value = ""; } });
        }}
      >
        {channels.length > 1 && (
          <Field label="Channel" htmlFor="imp-ch">
            <Select id="imp-ch" value={channel} onChange={(e) => setChannel(e.target.value)}>
              {channels.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </Select>
          </Field>
        )}
        <label
          onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
          onDragLeave={() => setDrag(false)}
          onDrop={(e) => { e.preventDefault(); setDrag(false); const f = e.dataTransfer.files?.[0]; if (f) setFile(f); }}
          className={cn(
            "flex cursor-pointer flex-col items-center justify-center gap-2 rounded-[12px] border border-dashed px-4 py-7 text-center transition-colors",
            drag ? "border-ink bg-elev-2" : "border-line-strong hover:border-ink-3",
          )}
        >
          <Upload className="size-5 text-ink-3" aria-hidden />
          <span className="text-[13px] text-ink">{file ? file.name : "Choose or drop a .csv / .xlsx file"}</span>
          <span className="text-[12px] text-ink-3">TikTok Studio → Analytics → Content → Download data</span>
          <input ref={inputRef} type="file" accept=".csv,.xlsx,.xls" className="sr-only" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
        </label>
        <Button type="submit" variant="primary" disabled={!file || !channel} loading={pending}>Upload export</Button>
      </form>
    </Panel>
  );
}
