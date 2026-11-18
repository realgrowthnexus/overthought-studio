import { NextResponse, type NextRequest } from "next/server";
import { randomBytes } from "node:crypto";
import { getAdmin } from "@/lib/auth";
import { serviceClient } from "@/lib/supabase/service";
import { readSecret } from "@/lib/secrets";
import { appUrl } from "@/lib/env";

export const dynamic = "force-dynamic";

const SCOPES = "user.info.basic,user.info.profile,user.info.stats,video.list,video.upload,video.publish";

export async function GET(request: NextRequest) {
  const admin = await getAdmin();
  if (!admin) return NextResponse.redirect(new URL("/login", request.url));

  const clientKey = await readSecret("tiktok_client_key");
  if (!clientKey) return NextResponse.redirect(new URL("/accounts?error=no_app_keys", request.url));

  const channel = request.nextUrl.searchParams.get("channel");
  const channelId = channel && /^[0-9a-f-]{36}$/i.test(channel) ? channel : null;

  const state = randomBytes(24).toString("base64url");
  const db = serviceClient();
  // housekeeping: drop stale states
  await db.from("oauth_states").delete().lt("created_at", new Date(Date.now() - 30 * 60_000).toISOString());
  const { error } = await db.from("oauth_states").insert({ state, code_verifier: "-", channel_id: channelId });
  if (error) return NextResponse.redirect(new URL("/accounts?error=state", request.url));

  const url = new URL("https://www.tiktok.com/v2/auth/authorize/");
  url.searchParams.set("client_key", clientKey);
  url.searchParams.set("scope", SCOPES);
  url.searchParams.set("response_type", "code");
  url.searchParams.set("redirect_uri", `${appUrl()}/api/tiktok/callback`);
  url.searchParams.set("state", state);
  url.searchParams.set("disable_auto_auth", "1");
  return NextResponse.redirect(url.toString());
}
