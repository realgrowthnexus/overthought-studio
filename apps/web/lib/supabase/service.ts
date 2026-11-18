import "server-only";
import { createClient, type SupabaseClient } from "@supabase/supabase-js";
import { publicEnv, serverEnv } from "@/lib/env";

let cached: SupabaseClient | null = null;

/** Service-role client. Bypasses RLS — only use after requireAdmin() or in trusted server routes. */
export function serviceClient(): SupabaseClient {
  if (cached) return cached;
  cached = createClient(publicEnv.supabaseUrl, serverEnv().serviceRoleKey, {
    auth: { persistSession: false, autoRefreshToken: false, detectSessionInUrl: false },
  });
  return cached;
}
