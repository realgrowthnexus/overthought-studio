"use client";
import * as React from "react";
import { useRouter } from "next/navigation";
import { claimOwner } from "./actions";
import { Button } from "@/components/ui/button";
import { Field, Input } from "@/components/ui/primitives";

export function SetupForm() {
  const router = useRouter();
  const [state, action, pending] = React.useActionState(claimOwner, {});
  React.useEffect(() => {
    if (state.ok) {
      router.replace("/");
      router.refresh();
    }
  }, [state.ok, router]);
  return (
    <form action={action} className="flex flex-col gap-4">
      <Field label="Setup token" htmlFor="token">
        <Input id="token" name="token" type="password" autoComplete="off" required />
      </Field>
      <Field label="Your email" htmlFor="email">
        <Input id="email" name="email" type="email" autoComplete="email" required />
      </Field>
      <Field label="Password" htmlFor="password" hint="At least 10 characters. You'll use this to sign in from your phone too.">
        <Input id="password" name="password" type="password" autoComplete="new-password" required minLength={10} />
      </Field>
      {state.error && <p role="alert" className="rounded-[10px] bg-bad-soft px-3 py-2 text-[13px] text-bad">{state.error}</p>}
      <Button type="submit" variant="primary" size="lg" loading={pending} className="mt-1">Create account and sign in</Button>
    </form>
  );
}
