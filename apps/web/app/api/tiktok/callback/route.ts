import { NextResponse, type NextRequest } from "next/server";
import { getAdmin } from "@/lib/auth";
import { serviceClient } from "@/lib/supabase/service";
import { readSecret } from "@/lib/secrets";
import { encrypt } from "@/lib/crypto";
import { appUrl } from "@/lib/env";

export const dynamic = "force-dynamic";

const USER_FIELDS = "open_id,avatar_url,display_name,username,is_verified,follower_count,following_count,likes_count,video_count";

function back(request: NextRequest, path: string) {
  return NextResponse.redirect(new URL(path, appUrl() || request.url));
}

export async function GET(request: NextRequest) {
  const sp = request.nextUrl.searchParams;
  const state = sp.get("state");
  const code = sp.get("code");
  const err = sp.get("error");

  const admin = await getAdmin();
  if (!admin) return back(request, "/login?next=/accounts");
  if (err) return back(request, `/accounts?error=${encodeURIComponent(sp.get("error_description") || err)}`);
  if (!state || !code) return back(request, "/accounts?error=missing_code");

  const db = serviceClient();
  const { data: st } = await db.from("oauth_states").select("*").eq("state", state).maybeSingle();
  await db.from("oauth_states").delete().eq("state", state);
  if (!st || Date.now() - new Date(st.created_at as string).getTime() > 15 * 60_000) {
    return back(request, "/accounts?error=expired_state");
  }

  const [clientKey, clientSecret] = await Promise.all([readSecret("tiktok_client_key"), readSecret("tiktok_client_secret")]);
  if (!clientKey || !clientSecret) return back(request, "/accounts?error=no_app_keys");

  // 1) exchange the code
  const tokenRes = await fetch("https://open.tiktokapis.com/v2/oauth/token/", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded", "Cache-Control": "no-cache" },
    body: new URLSearchParams({
      client_key: clientKey,
      client_secret: clientSecret,
      code: decodeURIComponent(code),
      grant_type: "authorization_code",
      redirect_uri: `${appUrl()}/api/tiktok/callback`,
    }),
    cache: "no-store",
  });
  const token = (await tokenRes.json().catch(() => ({}))) as Record<string, unknown>;
  if (!tokenRes.ok || !token.access_token) {
    const msg = String(token.error_description ?? token.error ?? `token exchange failed (${tokenRes.status})`);
    return back(request, `/accounts?error=${encodeURIComponent(msg)}`);
  }

  // 2) who is this?
  const userRes = await fetch(`https://open.tiktokapis.com/v2/user/info/?fields=${USER_FIELDS}`, {
    headers: { Authorization: `Bearer ${token.access_token}` },
    cache: "no-store",
  });
  const userJson = (await userRes.json().catch(() => ({}))) as { data?: { user?: Record<string, unknown> } };
  const u = userJson.data?.user ?? {};
  const openId = String(u.open_id ?? token.open_id ?? "");
  if (!openId) return back(request, "/accounts?error=no_open_id");

  const now = Date.now();
  const row = {
    open_id: openId,
    username: (u.username as string) ?? null,
    display_name: (u.display_name as string) ?? null,
    avatar_url: (u.avatar_url as string) ?? null,
    is_verified: (u.is_verified as boolean) ?? null,
    follower_count: (u.follower_count as number) ?? null,
    following_count: (u.following_count as number) ?? null,
    likes_count: (u.likes_count as number) ?? null,
    video_count: (u.video_count as number) ?? null,
    access_token_enc: encrypt(String(token.access_token)),
    refresh_token_enc: token.refresh_token ? encrypt(String(token.refresh_token)) : null,
    access_expires_at: new Date(now + Number(token.expires_in ?? 86400) * 1000).toISOString(),
    refresh_expires_at: new Date(now + Number(token.refresh_expires_in ?? 31536000) * 1000).toISOString(),
    scopes: String(token.scope ?? "").split(",").filter(Boolean),
    status: "connected",
    status_message: null,
    last_synced_at: new Date().toISOString(),
  };
  const { data: acct, error } = await db.from("tiktok_accounts").upsert(row, { onConflict: "open_id" }).select("id,username").single();
  if (error || !acct) return back(request, `/accounts?error=${encodeURIComponent(error?.message ?? "save_failed")}`);

  if (st.channel_id) {
    await db.from("channels").update({ tiktok_account_id: null }).eq("tiktok_account_id", acct.id);
    await db.from("channels").update({ tiktok_account_id: acct.id }).eq("id", st.channel_id);
  }
  await db.from("account_stats").insert({
    tiktok_account_id: acct.id, follower_count: row.follower_count, likes_count: row.likes_count, video_count: row.video_count,
  });
  await db.from("events").insert({
    scope: "tiktok", level: "success", message: `TikTok account connected: @${acct.username ?? openId}`, channel_id: st.channel_id ?? null,
  });
  // let the worker read creator info (privacy options, max duration) right away
  await db.from("jobs").insert({ type: "health_check", priority: 2 }).then(() => undefined, () => undefined);

  return back(request, `/accounts?connected=${encodeURIComponent(acct.username ?? "account")}`);
}
