import type { Metadata } from "next";
import { Suspense } from "react";
import Image from "next/image";
import Link from "next/link";
import { AtSign } from "lucide-react";
import { getAccounts, getChannels } from "@/lib/data";
import { readSecret } from "@/lib/secrets";
import { appUrl } from "@/lib/env";
import { Badge, PageHeader, Panel, PanelHeader } from "@/components/ui/primitives";
import { ButtonLink } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty";
import { AccountRowActions, FlashFromQuery } from "@/components/account-actions";
import { CopyField } from "@/components/copy-field";
import { num, relTime } from "@/lib/format";

export const metadata: Metadata = { title: "TikTok accounts" };
export const dynamic = "force-dynamic";

export default async function AccountsPage() {
  const [accounts, channels, clientKey, clientSecret] = await Promise.all([
    getAccounts(), getChannels(), readSecret("tiktok_client_key"), readSecret("tiktok_client_secret"),
  ]);
  const appReady = Boolean(clientKey && clientSecret);
  const base = appUrl();

  return (
    <>
      <Suspense fallback={null}><FlashFromQuery /></Suspense>
      <PageHeader
        title="TikTok accounts"
        description="Accounts connect through TikTok's official Login Kit. Tokens are encrypted and refreshed automatically."
        actions={appReady ? <ButtonLink href="/api/tiktok/connect" variant="primary" prefetch={false}><AtSign className="size-4" aria-hidden />Connect account</ButtonLink> : null}
      />

      {!appReady && (
        <Panel className="mb-6">
          <PanelHeader title="Set up your TikTok developer app first" description="A one-time job, about 15 minutes. TikTok reviews the app before public posting is allowed." />
          <ol className="flex flex-col gap-4 px-5 pb-6 text-[14px] text-ink-2">
            {[
              <>Go to <a className="text-ink underline decoration-accent decoration-2 underline-offset-4" href="https://developers.tiktok.com/apps" target="_blank" rel="noreferrer">developers.tiktok.com</a>, sign in and create an app called <strong className="text-ink">Overthought Studio</strong>.</>,
              <>Add the products <strong className="text-ink">Login Kit</strong> and <strong className="text-ink">Content Posting API</strong> (turn on Direct Post). Request the scopes user.info.basic, user.info.profile, user.info.stats, video.list, video.upload and video.publish.</>,
              <>Use these URLs in the app form:
                <div className="mt-3 grid gap-2">
                  <CopyField label="Redirect URI" value={`${base}/api/tiktok/callback`} />
                  <CopyField label="Privacy policy" value={`${base}/privacy`} />
                  <CopyField label="Terms of service" value={`${base}/terms`} />
                  <CopyField label="Website / domain to verify" value={base} />
                </div>
              </>,
              <>Copy the <strong className="text-ink">Client key</strong> and <strong className="text-ink">Client secret</strong> into <Link href="/settings#keys" className="text-ink underline decoration-accent decoration-2 underline-offset-4">Settings → API keys</Link>.</>,
              <>Come back here and press <strong className="text-ink">Connect account</strong> while logged in to the TikTok account in your browser.</>,
            ].map((step, i) => (
              <li key={i} className="grid grid-cols-[1.75rem_minmax(0,1fr)] gap-3">
                <span className="flex size-7 items-center justify-center rounded-full border border-line-strong text-[12px] text-ink-2 tabular">{i + 1}</span>
                <div className="pt-0.5 leading-relaxed">{step}</div>
              </li>
            ))}
          </ol>
        </Panel>
      )}

      <Panel className="overflow-hidden">
        <PanelHeader title="Connected accounts" description={`${accounts.length} of up to 5 while the app is unaudited.`} />
        {accounts.length === 0 ? (
          <EmptyState title="No accounts connected">
            {appReady ? "Press “Connect account” and approve the permissions on TikTok." : "Finish the app setup above, then connect your first account."}
          </EmptyState>
        ) : (
          <ul className="divide-y divide-line border-t border-line">
            {accounts.map((a) => {
              const ch = channels.find((c) => c.tiktok_account_id === a.id);
              const expiring = a.refresh_expires_at && new Date(a.refresh_expires_at).getTime() - Date.now() < 14 * 86400000;
              return (
                <li key={a.id} className="flex flex-col gap-4 px-5 py-4 sm:flex-row sm:items-center">
                  <div className="flex min-w-0 flex-1 items-center gap-3">
                    {a.avatar_url ? (
                      <Image src={a.avatar_url} alt="" width={44} height={44} className="rounded-full" unoptimized />
                    ) : (
                      <span className="flex size-11 items-center justify-center rounded-full bg-elev-2"><AtSign className="size-4 text-ink-3" /></span>
                    )}
                    <div className="min-w-0">
                      <p className="flex items-center gap-2 text-[15px] font-medium text-ink">
                        @{a.username ?? a.display_name ?? a.open_id.slice(0, 8)}
                        {a.status === "connected" ? (expiring ? <Badge tone="warn" dot>Login expires soon</Badge> : <Badge tone="good" dot>Connected</Badge>) : <Badge tone="bad" dot>{a.status}</Badge>}
                      </p>
                      <p className="text-[13px] text-ink-3">
                        {num(a.follower_count)} followers · {num(a.likes_count)} likes · {num(a.video_count)} videos · synced {relTime(a.last_synced_at)}
                      </p>
                      {a.status_message && <p className="mt-0.5 text-[12px] text-bad">{a.status_message}</p>}
                    </div>
                  </div>
                  <div className="flex items-center gap-3 text-[13px]">
                    <span className="text-ink-3">{ch ? <>Channel: <Link href={`/channels/${ch.slug}`} className="text-ink hover:underline">{ch.name}</Link></> : "Not linked to a channel"}</span>
                    <AccountRowActions accountId={a.id} username={a.username ?? "account"} needsReconnect={a.status !== "connected" || Boolean(expiring)} />
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </Panel>
    </>
  );
}
