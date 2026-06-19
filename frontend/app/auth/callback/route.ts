import { NextResponse, type NextRequest } from "next/server";

import { createClient } from "@/lib/supabase/server";

function getRedirectOrigin(request: NextRequest) {
  if (process.env.NODE_ENV === "development") {
    return request.nextUrl.origin;
  }

  const forwardedHost = request.headers.get("x-forwarded-host");
  if (forwardedHost) {
    return `https://${forwardedHost}`;
  }

  return request.nextUrl.origin;
}

export async function GET(request: NextRequest) {
  const code = request.nextUrl.searchParams.get("code");
  const next = request.nextUrl.searchParams.get("next") ?? "/";
  const safeNext = next.startsWith("/") ? next : "/";

  if (code) {
    const supabase = await createClient();
    const { error } = await supabase.auth.exchangeCodeForSession(code);

    if (!error) {
      return NextResponse.redirect(`${getRedirectOrigin(request)}${safeNext}`);
    }
  }

  return NextResponse.redirect(`${getRedirectOrigin(request)}/auth/error`);
}
