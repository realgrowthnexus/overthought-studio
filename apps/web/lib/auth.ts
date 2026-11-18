import "server-only";
import { cache } from "react";
import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import { serviceClient } from "@/lib/supabase/service";

export class NotAuthorizedError extends Error {
  constructor() {
    super("You need to sign in as the studio owner to do that.");
  }
}

type AuthState = { user: null; admin: null } | { user: { id: string }; admin: { id: string; email: string } | null };

/**
 * Verifies the session with Supabase Auth (getUser, not getSession — the JWT is checked server-side), then confirms
 * the user is in public.admins with the service role. Cached per request so pages, data loaders and actions can all
 * call it without extra round trips. Any error → not an admin (fail closed).
 */
const authState = cache(async (): Promise<AuthState> => {
  try {
    const supabase = await createClient();
    const { data, error } = await supabase.auth.getUser();
    if (error || !data.user) return { user: null, admin: null };
    const { data: row, error: dbErr } = await serviceClient()
      .from("admins")
      .select("user_id,email")
      .eq("user_id", data.user.id)
      .maybeSingle();
    if (dbErr || !row) return { user: { id: data.user.id }, admin: null };
    return { user: { id: data.user.id }, admin: { id: data.user.id, email: row.email as string } };
  } catch {
    return { user: null, admin: null };
  }
});

/** Returns the signed-in admin user or null. */
export async function getAdmin() {
  return (await authState()).admin;
}

/** For pages: redirect to /login when not an admin. */
export async function requireAdminPage() {
  const { user, admin } = await authState();
  if (admin) return admin;
  // Signed in but not an owner: send to /login with a reason so middleware doesn't bounce back to / (loop).
  redirect(user ? "/login?error=not_admin" : "/login");
}

/** For server actions / route handlers / data loaders: throw when not an admin. */
export async function requireAdmin() {
  const admin = await getAdmin();
  if (!admin) throw new NotAuthorizedError();
  return admin;
}

export async function hasAnyAdmin(): Promise<boolean> {
  // Fail closed: if the database can't be read (bad key, outage), treat the studio as claimed.
  const { count, error } = await serviceClient().from("admins").select("user_id", { count: "exact", head: true });
  if (error) throw new Error(`Couldn't reach the database: ${error.message}`);
  return (count ?? 0) > 0;
}

/** Same-origin relative path for post-login redirects; anything else (//host, /\host, schemes) becomes "/". */
export function safeNextPath(next: string | null | undefined): string {
  if (!next || typeof next !== "string" || !next.startsWith("/") || next.length > 512) return "/";
  if (/[\\\u0000-\u001f]/.test(next) || next.startsWith("//")) return "/";
  try {
    const u = new URL(next, "http://studio.invalid");
    if (u.origin !== "http://studio.invalid") return "/";
    return u.pathname + u.search + u.hash;
  } catch {
    return "/";
  }
}
