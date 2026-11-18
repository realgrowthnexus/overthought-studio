import { notFound } from "next/navigation";
import { getAccounts, getChannelBySlug, getChannels } from "@/lib/data";
import { readSecret } from "@/lib/secrets";
import { ChannelForm } from "@/components/channel-form";
import { ChannelAccount, DangerZone } from "@/components/channel-settings-extra";

export const dynamic = "force-dynamic";

export default async function ChannelSettings({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const channel = await getChannelBySlug(slug);
  if (!channel) notFound();
  const [accounts, channels, clientKey] = await Promise.all([getAccounts(), getChannels(), readSecret("tiktok_client_key")]);
  const takenBy = Object.fromEntries(
    channels.filter((c) => c.tiktok_account_id && c.id !== channel.id).map((c) => [c.tiktok_account_id as string, c.name]),
  );
  return (
    <div className="flex flex-col gap-6">
      <ChannelAccount channel={channel} accounts={accounts} takenBy={takenBy} appReady={Boolean(clientKey)} />
      <ChannelForm mode="edit" channel={channel} />
      <DangerZone id={channel.id} slug={channel.slug} name={channel.name} />
    </div>
  );
}
