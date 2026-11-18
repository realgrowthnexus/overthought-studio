import { notFound } from "next/navigation";
import { getChannelBySlug, getChannels, getLatestStats, getVideos } from "@/lib/data";
import { Panel } from "@/components/ui/primitives";
import { VideoList } from "@/components/video-list";
import { LiveRefresh } from "@/components/live";

export const dynamic = "force-dynamic";

export default async function ChannelVideos({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const channel = await getChannelBySlug(slug);
  if (!channel) notFound();
  const [videos, channels] = await Promise.all([getVideos({ channelId: channel.id, limit: 200 }), getChannels()]);
  const stats = await getLatestStats(videos.map((v) => v.id));
  return (
    <Panel className="overflow-hidden">
      <LiveRefresh tables={["videos"]} filter={`channel_id=eq.${channel.id}`} />
      <VideoList videos={videos} channels={channels} stats={stats} showChannel={false} />
    </Panel>
  );
}
