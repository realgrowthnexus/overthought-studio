"use client";
import * as React from "react";
import { Button, type ButtonProps } from "@/components/ui/button";
import { enqueueJob } from "@/lib/actions";
import { useAction } from "@/components/use-action";

type JobType = Parameters<typeof enqueueJob>[0]["type"];

export function JobButton({
  type, payload, channelId, videoId, children, ...rest
}: {
  type: JobType; payload?: Record<string, unknown>; channelId?: string | null; videoId?: string | null; children: React.ReactNode;
} & Omit<ButtonProps, "onClick" | "type">) {
  const { pending, run } = useAction();
  return (
    <Button
      {...rest}
      loading={pending}
      onClick={() => run(() => enqueueJob({ type, payload, channel_id: channelId ?? null, video_id: videoId ?? null }))}
    >
      {children}
    </Button>
  );
}
