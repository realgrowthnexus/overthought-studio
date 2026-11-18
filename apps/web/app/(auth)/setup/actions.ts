"use server";
import { timingSafeEqual } from "node:crypto";
import { redirect } from "next/navigation";
import { z } from "zod";
import { serviceClient } from "@/lib/supabase/service";
import { createClient } from "@/lib/supabase/server";
import { hasAnyAdmin } from "@/lib/auth";

const schema = z.object({
  token: z.string().min(1, "Enter the setup token"),
  email: z.string().email("Enter a valid email"),
  password: z.string().min(10, "Use at least 10 characters"),
});

function sameToken(a: string, b: string) {
  const x = Buffer.from(a);
  const y = Buffer.from(b);
  return x.length === y.length && timingSafeEqual(x, y);
}

export async function claimOwner(_: unknown, formData: FormData): Promise<{ error?: string; ok?: boolean }> {
  const parsed = schema.safeParse(Object.fromEntries(formData));
  if (!parsed.success) return { error: parsed.error.issues[0]?.message ?? "Check the form" };
  const expected = process.env.SETUP_TOKEN ?? "";
  if (!expected) return { error: "SETUP_TOKEN isn't configured on the server yet." };
  if (!sameToken(parsed.data.token, expected)) return { error: "That setup token is wrong." };
  const claimed = await hasAnyAdmin().catch(() => null);
  if (claimed === null) return { error: "The dashboard can't reach the database. Check SUPABASE_SERVICE_ROLE_KEY." };
  if (claimed) return { error: "An owner account already exists. Sign in instead." };

  const admin = serviceClient();
  const { data, error } = await admin.auth.admin.createUser({
    email: parsed.data.email, password: parsed.data.password, email_confirm: true,
  });
  if (error || !data.user) return { error: error?.message ?? "Couldn't create the account." };
  const { error: insErr } = await admin.from("admins").insert({ user_id: data.user.id, email: parsed.data.email });
  if (insErr) {
    await admin.auth.admin.deleteUser(data.user.id);
    return { error: insErr.message };
  }
  await admin.from("events").insert({ scope: "dashboard", level: "success", message: "Owner account created" });

  const supabase = await createClient();
  await supabase.auth.signInWithPassword({ email: parsed.data.email, password: parsed.data.password });
  redirect("/");
}
