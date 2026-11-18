import type { Metadata } from "next";
import Link from "next/link";
import { hasAnyAdmin } from "@/lib/auth";
import { LoginForm } from "./login-form";

export const metadata: Metadata = { title: "Sign in" };
export const dynamic = "force-dynamic";

export default async function LoginPage({ searchParams }: { searchParams: Promise<{ next?: string }> }) {
  const { next } = await searchParams;
  const claimed = await hasAnyAdmin().catch(() => true);
  return (
    <>
      <h1 className="text-[26px] font-semibold tracking-[-0.02em] text-ink">Sign in to the studio</h1>
      <p className="mt-1.5 mb-7 text-[14px] text-ink-3">Your channels keep running while you&apos;re away.</p>
      <LoginForm next={next && next.startsWith("/") && !next.startsWith("//") ? next : "/"} />
      {!claimed && (
        <p className="mt-6 rounded-[12px] border border-line bg-elev px-4 py-3 text-[13px] text-ink-2">
          First time here? <Link href="/setup" className="font-medium text-ink underline decoration-accent decoration-2 underline-offset-4">Create the owner account</Link>.
        </p>
      )}
    </>
  );
}
