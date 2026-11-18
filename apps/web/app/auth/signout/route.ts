import { NextResponse, type NextRequest } from "next/server";
import { createClient } from "@/lib/supabase/server";
import { appUrl } from "@/lib/env";

export async function POST(request: NextRequest) {
  // Same-origin form posts only (route handlers don't get Next's server-action Origin check).
  const origin = request.headers.get("origin");
  if (origin && origin !== request.nextUrl.origin && origin !== appUrl()) {
    return new NextResponse("Forbidden", { status: 403 });
  }
  const supabase = await createClient();
  await supabase.auth.signOut();
  return NextResponse.redirect(new URL("/login", appUrl()), { status: 303 });
}
