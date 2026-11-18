import type { Metadata } from "next";
import Link from "next/link";
import { ChevronLeft } from "lucide-react";
import { PageHeader } from "@/components/ui/primitives";
import { ChannelForm } from "@/components/channel-form";

export const metadata: Metadata = { title: "New channel" };

export default function NewChannelPage() {
  return (
    <>
      <PageHeader
        back={<Link href="/channels" className="inline-flex items-center gap-1 text-[13px] text-ink-3 hover:text-ink"><ChevronLeft className="size-4" />Channels</Link>}
        title="New channel"
        description="Four short steps. The channel starts paused, so nothing is made until you switch it on."
      />
      <ChannelForm mode="create" />
    </>
  );
}
