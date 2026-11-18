"use client";
import * as React from "react";
import Image from "next/image";
import { useRouter } from "next/navigation";
import { AtSign } from "lucide-react";
import type { Channel, TikTokAccount } from "@/lib/types";
import { deleteChannel, linkAccount } from "@/lib/actions";
import { useAction } from "@/components/use-action";
import { Button, ButtonLink } from "@/components/ui/button";
import { Field, Input, Select } from "@/components/ui/primitives";
import { num } from "@/lib/format";

export function ChannelAccount({
  channel, accounts, takenBy, appReady,
}: { channel: Channel; accounts: TikTokAccount[]; takenBy: Record<string, string>; appReady: boolean }) {
  const { pending, run } = useAction();
  const current = accounts.find((a) => a.id === channel.tiktok_account_id);
  return (
    <section id="account" className="scroll-mt-24 rounded-[var(--radius-lg)] border border-line bg-elev p-5 sm:p-6">
      <h2 className="text-[15px] font-semibold text-ink">TikTok account</h2>
      <p className="mt-1 mb-5 text-[13px] text-ink-3">One account per channel. Videos and stats go through TikTok&apos;s official API.</p>
      {current ? (
        <div className="flex flex-wrap items-center justify-between gap-4 rounded-[12px] border border-line bg-bg p-4">
          <div className="flex items-center gap-3">
            {current.avatar_url ? (
              <Image src={current.avatar_url} alt="" width={40} height={40} className="rounded-full" unoptimized />
            ) : (
              <span className="flex size-10 items-center justify-center rounded-full bg-elev-2"><AtSign className="size-4 text-ink-3" /></span>
            )}
            <div>
              <p className="text-[14px] font-medium text-ink">@{current.username ?? current.display_name}</p>
              <p className="text-[12px] text-ink-3">{num(current.follower_count)} followers · {current.status === "connected" ? "login valid" : `login ${current.status}`}</p>
            </div>
          </div>
          <Button variant="ghost" size="sm" loading={pending} onClick={() => run(() => linkAccount(channel.id, null))}>Unlink</Button>
        </div>
      ) : !appReady ? (
        <p className="rounded-[12px] border border-line bg-bg p-4 text-[13px] text-ink-2">
          Add your TikTok developer app keys in <a href="/settings#keys" className="underline decoration-accent-mark decoration-2 underline-offset-4">Settings</a> first. Then you can connect the account here.
        </p>
      ) : (
        <div className="flex flex-col gap-4 sm:flex-row sm:items-end">
          {accounts.length > 0 && (
            <Field label="Use a connected account" htmlFor="acct" className="flex-1">
              <Select id="acct" defaultValue="" onChange={(e) => e.target.value && run(() => linkAccount(channel.id, e.target.value))} disabled={pending}>
                <option value="" disabled>Choose an account…</option>
                {accounts.map((a) => (
                  <option key={a.id} value={a.id}>@{a.username ?? a.display_name}{takenBy[a.id] ? ` (moves from ${takenBy[a.id]})` : ""}</option>
                ))}
              </Select>
            </Field>
          )}
          <ButtonLink href={`/api/tiktok/connect?channel=${channel.id}`} variant="primary" prefetch={false}>
            <AtSign className="size-4" aria-hidden />Connect a new TikTok account
          </ButtonLink>
        </div>
      )}
    </section>
  );
}

export function DangerZone({ id, slug, name }: { id: string; slug: string; name: string }) {
  const router = useRouter();
  const [confirm, setConfirm] = React.useState("");
  const { pending, run } = useAction();
  return (
    <section className="rounded-[var(--radius-lg)] border border-bad/30 p-5 sm:p-6">
      <h2 className="text-[15px] font-semibold text-ink">Delete channel</h2>
      <p className="mt-1 mb-4 max-w-[64ch] text-[13px] text-ink-3">
        Removes {name}, its idea bank, videos and stats from the studio. Videos already on TikTok stay there. This can&apos;t be undone.
      </p>
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
        <Field label={`Type ${slug} to confirm`} htmlFor="confirm-del" className="sm:w-72">
          <Input id="confirm-del" value={confirm} onChange={(e) => setConfirm(e.target.value)} autoComplete="off" />
        </Field>
        <Button
          variant="danger"
          disabled={confirm !== slug}
          loading={pending}
          onClick={() => run(() => deleteChannel(id, confirm), { onOk: () => router.push("/channels") })}
        >
          Delete channel
        </Button>
      </div>
    </section>
  );
}
