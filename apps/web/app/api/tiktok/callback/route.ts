import { NextResponse, type NextRequest } from "next/server";
import { timingSafeEqual } from "node:crypto";
import { getAdmin } from "@/lib/auth";
import { serviceClient } from "@/lib/supabase/service";
import { readSecret } from "@/lib/secrets";
import { encrypt } from "@/lib/crypto";
import { appUrl } from "@/lib/env";
import { OAUTH_CALLBACK_PATH, OAUTH_COOKIE, OAUTH_TTL_MS, stateBinding } from "@/lib/oauth";

export const dynamic = "force-dynamic";

const USER_FIELDS = "open_id,avatar_url,display_name,username,is_verified,follower_count,following_count,likes_count,video_count";

function back(_request: NextRequest, path: string) {
  // Always back to our own origin; the state cookie is single-use, so clear it on every exit.
  const res = NextResponse.redirect(new URL(path, appUrl()));
  res.headers.set("Cache-Control", "no-store");
  res.cookies.set(OAUTH_COOKIE, "", { httpOnly: true, sameSite: "lax", path: OAUTH_CALLBACK_PATH, maxAge: 0 });
  return res;
}

function errParam(msg: string) {
  return encodeURIComponent(msg.replace(/[\u0000-\u001f]/g, " ").slice(0, 200));
}

function sameState(a: string, b: string) {
  const x = Buffer.from(a);
  const y = Buffer.from(b);
  return x.length === y.length && timingSafeEqual(x, y);
}

// TikTok's samples decode the code once more after the query-string decode; keep that, but never throw on bad input.
function safeDecode(v: string) {
  try {
    return decodeURIComponent(v);
  } catch {
    return v;
  }
}

const str = (v: unknown, max = 200) => (typeof v === "string" && v ? v.slice(0, max) : null);
const int = (v: unknown) => (typeof v === "number" && Number.isFinite(v) ? Math.trunc(v) : null);

export async function GET(request: NextRequest) {
  const sp = request.nextUrl.searchParams;
  const state = sp.get("state");
  const code = sp.get("code");
  const err = sp.get("error");
  const cookieState = request.cookies.get(OAUTH_COOKIE)?.value ?? "";

  const admin = await getAdmin();
  if (!admin) return back(request, "/login?next=/accounts");
  if (!state || state.length > 128 || !cookieState || !sameState(state, cookieState)) {
    return back(request, "/accounts?error=expired_state");
  }

  // Single use: delete and read in one statement, so a replayed state finds nothing.
  const db = serviceClient();
  const { data: st } = await db.from("oauth_states").delete().eq("state", state).select("*").maybeSingle();
  if (
    !st ||
    st.code_verifier !== stateBinding(state, admin.id) ||
    Date.now() - new Date(st.created_at as string).getTime() > OAUTH_TTL_MS
  ) {
    return back(request, "/accounts?error=expired_state");
  }
  if (err) return back(request, `/accounts?error=${errParam(sp.get("error_description") || err)}`);
  if (!code || code.length > 2048) return back(request, "/accounts?error=missing_code");

  const [clientKey, clientSecret] = await Promise.all([readSecret("tiktok_client_key"), readSecret("tiktok_client_secret")]);
  if (!clientKey || !clientSecret) return back(request, "/accounts?error=no_app_keys");

  // 1) exchange the code
  const tokenRes = await fetch("https://open.tiktokapis.com/v2/oauth/token/", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded", "Cache-Control": "no-cache" },
    body: new URLSearchParams({
      client_key: clientKey,
      client_secret: clientSecret,
      code: safeDecode(code),
      grant_type: "authorization_code",
      redirect_uri: `${appUrl()}${OAUTH_CALLBACK_PATH}`,
    }),
    cache: "no-store",
    signal: AbortSignal.timeout(15_000),
  });
  const token = (await tokenRes.json().catch(() => ({}))) as Record<string, unknown>;
  if (!tokenRes.ok || !token.access_token) {
    const msg = String(token.error_description ?? token.error ?? `token exchange failed (${tokenRes.status})`);
    return back(request, `/accounts?error=${errParam(msg)}`);
  }

  // 2) who is this?
  const userRes = await fetch(`https://open.tiktokapis.com/v2/user/info/?fields=${USER_FIELDS}`, {
    headers: { Authorization: `Bearer ${token.access_token}` },
    cache: "no-store",
    signal: AbortSignal.timeout(15_000),
  });
  const userJson = (await userRes.json().catch(() => ({}))) as { data?: { user?: Record<string, unknown> } };
  const u = userJson.data?.user ?? {};
  const openId = str(u.open_id) ?? str(token.open_id) ?? "";
  if (!openId) return back(request, "/accounts?error=no_open_id");
  const avatar = str(u.avatar_url, 2000);

  const now = Date.now();
  const row = {
    open_id: openId,
    username: str(u.username, 100),
    display_name: str(u.display_name, 200),
    avatar_url: avatar && avatar.startsWith("https://") ? avatar : null,
    is_verified: typeof u.is_verified === "boolean" ? u.is_verified : null,
    follower_count: int(u.follower_count),
    following_count: int(u.following_count),
    likes_count: int(u.likes_count),
    video_count: int(u.video_count),
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
  if (error || !acct) return back(request, "/accounts?error=save_failed");

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
