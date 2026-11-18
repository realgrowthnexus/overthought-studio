import { NextResponse, type NextRequest } from "next/server";
import { randomBytes } from "node:crypto";
import { getAdmin } from "@/lib/auth";
import { serviceClient } from "@/lib/supabase/service";
import { readSecret } from "@/lib/secrets";
import { appUrl } from "@/lib/env";
import { OAUTH_CALLBACK_PATH, OAUTH_COOKIE, OAUTH_TTL_MS, stateBinding } from "@/lib/oauth";

export const dynamic = "force-dynamic";

const SCOPES = "user.info.basic,user.info.profile,user.info.stats,video.list,video.upload,video.publish";
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

function back(path: string) {
  return NextResponse.redirect(new URL(path, appUrl()));
}

export async function GET(request: NextRequest) {
  const admin = await getAdmin();
  if (!admin) return back("/login?next=/accounts");

  const clientKey = await readSecret("tiktok_client_key");
  if (!clientKey) return back("/accounts?error=no_app_keys");

  const db = serviceClient();
  const channel = request.nextUrl.searchParams.get("channel");
  let channelId: string | null = null;
  if (channel && UUID.test(channel)) {
    const { data } = await db.from("channels").select("id").eq("id", channel).maybeSingle();
    channelId = (data?.id as string | undefined) ?? null;
  }

  const state = randomBytes(32).toString("base64url");
  // housekeeping: drop expired states
  await db.from("oauth_states").delete().lt("created_at", new Date(Date.now() - OAUTH_TTL_MS).toISOString());
  const { error } = await db.from("oauth_states").insert({
    state, code_verifier: stateBinding(state, admin.id), channel_id: channelId,
  });
  if (error) return back("/accounts?error=state");

  const url = new URL("https://www.tiktok.com/v2/auth/authorize/");
  url.searchParams.set("client_key", clientKey);
  url.searchParams.set("scope", SCOPES);
  url.searchParams.set("response_type", "code");
  url.searchParams.set("redirect_uri", `${appUrl()}${OAUTH_CALLBACK_PATH}`);
  url.searchParams.set("state", state);
  url.searchParams.set("disable_auto_auth", "1");
  const res = NextResponse.redirect(url.toString());
  res.headers.set("Cache-Control", "no-store");
  // SameSite=Lax is sent on the top-level GET redirect back from TikTok.
  res.cookies.set(OAUTH_COOKIE, state, {
    httpOnly: true, sameSite: "lax", secure: appUrl().startsWith("https://"),
    path: OAUTH_CALLBACK_PATH, maxAge: OAUTH_TTL_MS / 1000,
  });
  return res;
}
