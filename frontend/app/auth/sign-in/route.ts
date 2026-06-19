import { NextResponse, type NextRequest } from "next/server";

import { createClient } from "@/lib/supabase/server";

function getOrigin(request: NextRequest) {
  return process.env.NEXT_PUBLIC_SITE_URL ?? request.nextUrl.origin;
}

export async function GET(request: NextRequest) {
  const next = request.nextUrl.searchParams.get("next") ?? "/";
  const safeNext = next.startsWith("/") ? next : "/";
  const supabase = await createClient();

  const { data, error } = await supabase.auth.signInWithOAuth({
    provider: "google",
    options: {
      redirectTo: `${getOrigin(request)}/auth/callback?next=${encodeURIComponent(safeNext)}`,
    },
  });

  if (error || !data.url) {
    const redirectUrl = request.nextUrl.clone();
    redirectUrl.pathname = "/auth/error";
    redirectUrl.searchParams.set("message", error?.message ?? "Google sign-in could not be started.");
    return NextResponse.redirect(redirectUrl);
  }

  return NextResponse.redirect(data.url);
}
