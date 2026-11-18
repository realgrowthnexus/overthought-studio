"use server";
import { createHash, timingSafeEqual } from "node:crypto";
import { redirect } from "next/navigation";
import { z } from "zod";
import { serviceClient } from "@/lib/supabase/service";
import { createClient } from "@/lib/supabase/server";
import { hasAnyAdmin } from "@/lib/auth";

const schema = z.object({
  token: z.string().min(1, "Enter the setup token").max(512),
  email: z.string().trim().email("Enter a valid email").max(254),
  password: z.string().min(10, "Use at least 10 characters").max(200),
});

/** Constant-time compare that also hides the token length (both sides hashed to 32 bytes first). */
function sameToken(a: string, b: string) {
  const x = createHash("sha256").update(a, "utf8").digest();
  const y = createHash("sha256").update(b, "utf8").digest();
  return timingSafeEqual(x, y);
}

// One claim at a time per server process (the VPS runs a single Next process). The DB check below makes it safe
// across processes too.
let claiming: Promise<unknown> = Promise.resolve();

type Result = { error?: string; ok?: boolean };

export async function claimOwner(_: unknown, formData: FormData): Promise<Result> {
  const run = claiming.then(() => claim(formData));
  claiming = run.catch(() => undefined);
  const res = await run;
  if (res.ok) redirect("/");
  return res;
}

async function claim(formData: FormData): Promise<Result> {
  if (!(formData instanceof FormData)) return { error: "Check the form" };
  // Fail closed: once an owner exists (or the DB can't be read) /setup does nothing, whatever the token.
  const claimed = await hasAnyAdmin().catch(() => null);
  if (claimed === null) return { error: "The dashboard can't reach the database. Check SUPABASE_SERVICE_ROLE_KEY." };
  if (claimed) return { error: "An owner account already exists. Sign in instead." };
  const expected = process.env.SETUP_TOKEN ?? "";
  if (!expected) return { error: "SETUP_TOKEN isn't configured on the server yet." };
  if (expected.length < 12) return { error: "SETUP_TOKEN on the server is too short. Use a long random string (openssl rand -hex 24)." };

  const parsed = schema.safeParse({
    token: formData.get("token"), email: formData.get("email"), password: formData.get("password"),
  });
  if (!parsed.success) return { error: parsed.error.issues[0]?.message ?? "Check the form" };
  if (!sameToken(parsed.data.token, expected)) return { error: "That setup token is wrong." };

  const admin = serviceClient();
  const { data, error } = await admin.auth.admin.createUser({
    email: parsed.data.email, password: parsed.data.password, email_confirm: true,
  });
  if (error || !data.user) return { error: "Couldn't create the account. If it already exists, sign in instead." };
  const userId = data.user.id;
  const { error: insErr } = await admin.from("admins").insert({ user_id: userId, email: parsed.data.email });
  if (insErr) {
    await admin.auth.admin.deleteUser(userId);
    return { error: "Couldn't save the owner account. Try again." };
  }

  // Race guard across processes: if two claims slipped past the check above, both rows are now committed and every
  // claimant sees the same earliest row. Only that one keeps its account; the rest roll themselves back.
  const { data: first, error: firstErr } = await admin.from("admins")
    .select("user_id").order("created_at", { ascending: true }).order("user_id", { ascending: true }).limit(1).maybeSingle();
  if (firstErr || !first || first.user_id !== userId) {
    await admin.from("admins").delete().eq("user_id", userId);
    await admin.auth.admin.deleteUser(userId);
    return { error: "An owner account already exists. Sign in instead." };
  }

  await admin.from("events").insert({ scope: "dashboard", level: "success", message: "Owner account created" });

  const supabase = await createClient();
  await supabase.auth.signInWithPassword({ email: parsed.data.email, password: parsed.data.password });
  return { ok: true };
}
