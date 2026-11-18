"use client";
import * as React from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { toast } from "sonner";
import { disconnectAccount } from "@/lib/actions";
import { useAction } from "@/components/use-action";
import { Button, ButtonLink } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";

const ERRORS: Record<string, string> = {
  no_app_keys: "Add your TikTok client key and secret in Settings first.",
  expired_state: "That sign-in link expired. Try connecting again.",
  missing_code: "TikTok didn't send back a code. Try connecting again.",
  state: "Couldn't start the TikTok sign-in. Try again.",
  no_open_id: "TikTok didn't return an account ID. Check the app's scopes.",
};

export function FlashFromQuery() {
  const sp = useSearchParams();
  const router = useRouter();
  React.useEffect(() => {
    const ok = sp.get("connected");
    const err = sp.get("error");
    if (ok) toast.success(`@${ok} connected.`);
    if (err) toast.error(ERRORS[err] ?? `TikTok said: ${err}`);
    if (ok || err) router.replace("/accounts");
  }, [sp, router]);
  return null;
}

export function AccountRowActions({ accountId, username, needsReconnect }: { accountId: string; username: string; needsReconnect: boolean }) {
  const [open, setOpen] = React.useState(false);
  const { pending, run } = useAction();
  return (
    <>
      {needsReconnect && <ButtonLink href="/api/tiktok/connect" size="sm" variant="primary" prefetch={false}>Reconnect</ButtonLink>}
      <Button size="sm" variant="ghost" onClick={() => setOpen(true)}>Disconnect</Button>
      <Dialog open={open} onClose={() => setOpen(false)} title={`Disconnect @${username}?`} description="The studio deletes its tokens and stops posting to this account. Videos already on TikTok stay up.">
        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={() => setOpen(false)}>Cancel</Button>
          <Button variant="danger" loading={pending} onClick={() => run(() => disconnectAccount(accountId), { onOk: () => setOpen(false) })}>Disconnect</Button>
        </div>
      </Dialog>
    </>
  );
}
