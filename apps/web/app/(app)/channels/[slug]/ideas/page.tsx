import { notFound } from "next/navigation";
import { getChannelBySlug, getIdeas } from "@/lib/data";
import { IdeaBank } from "@/components/idea-bank";

export const dynamic = "force-dynamic";

export default async function ChannelIdeas({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const channel = await getChannelBySlug(slug);
  if (!channel) notFound();
  const ideas = await getIdeas(channel.id);
  return <IdeaBank channelId={channel.id} ideas={ideas} pillars={(channel.content.pillars ?? []).map((p) => p.name)} />;
}
