import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { hasAnyAdmin } from "@/lib/auth";
import { SetupForm } from "./setup-form";

export const metadata: Metadata = { title: "Create owner account" };
export const dynamic = "force-dynamic";

export default async function SetupPage() {
  if (await hasAnyAdmin()) notFound();
  return (
    <>
      <h1 className="text-[26px] font-semibold tracking-[-0.02em] text-ink">Create the owner account</h1>
      <p className="mt-1.5 mb-7 text-[14px] leading-relaxed text-ink-3">
        This works once. Use the setup token from your Vercel environment variables (<code className="text-ink-2">SETUP_TOKEN</code>).
      </p>
      <SetupForm />
    </>
  );
}
