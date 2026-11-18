import "server-only";
import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import { serviceClient } from "@/lib/supabase/service";

export class NotAuthorizedError extends Error {
  constructor() {
    super("You need to sign in as the studio owner to do that.");
  }
}

/** Returns the signed-in admin user or null. Uses the user's JWT, then confirms admin via service role. */
export async function getAdmin() {
  const supabase = await createClient();
  const { data, error } = await supabase.auth.getUser();
  if (error || !data.user) return null;
  const { data: row } = await serviceClient()
    .from("admins")
    .select("user_id,email")
    .eq("user_id", data.user.id)
    .maybeSingle();
  if (!row) return null;
  return { id: data.user.id, email: row.email as string };
}

/** For pages: redirect to /login when not an admin. */
export async function requireAdminPage() {
  const admin = await getAdmin();
  if (!admin) redirect("/login");
  return admin;
}

/** For server actions / route handlers: throw when not an admin. */
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
