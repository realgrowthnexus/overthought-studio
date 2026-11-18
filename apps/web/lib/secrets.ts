import "server-only";
import { serviceClient } from "@/lib/supabase/service";
import { decrypt } from "@/lib/crypto";
import type { SecretKey } from "@/lib/types";

export async function readSecret(key: SecretKey): Promise<string | null> {
  const { data } = await serviceClient().from("secrets").select("ciphertext").eq("key", key).maybeSingle();
  if (!data?.ciphertext) return null;
  try {
    return decrypt(data.ciphertext as string);
  } catch {
    return null;
  }
}
