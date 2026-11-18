import "server-only";
import { createHash } from "node:crypto";

/** Cookie that binds a TikTok OAuth state to the browser that started it (double-submit, httpOnly). */
export const OAUTH_COOKIE = "tt_oauth_state";
export const OAUTH_TTL_MS = 10 * 60_000;
export const OAUTH_CALLBACK_PATH = "/api/tiktok/callback";

/**
 * Value stored in oauth_states.code_verifier (TikTok web login doesn't use PKCE, so the column is free): ties the
 * state to the admin who started the flow. Hashed so the row doesn't reveal the user id + state pairing in clear.
 */
export function stateBinding(state: string, adminId: string): string {
  return "bind:" + createHash("sha256").update(`${state}:${adminId}`).digest("base64url");
}
