import { NextResponse, type NextRequest } from "next/server";

import { createClient } from "@/lib/supabase/server";

function dummyLoginEnabled() {
  return process.env.NODE_ENV !== "production" || process.env.ENABLE_DUMMY_LOGIN === "true";
}

export async function POST(request: NextRequest) {
  if (!dummyLoginEnabled()) {
    const redirectUrl = new URL("/auth/error", request.url);
    redirectUrl.searchParams.set("message", "Dummy account login is disabled.");
    return NextResponse.redirect(redirectUrl, { status: 303 });
  }

  const formData = await request.formData();
  const email = String(formData.get("email") ?? "");
  const password = String(formData.get("password") ?? "");
  const next = String(formData.get("next") ?? "/");
  const safeNext = next.startsWith("/") ? next : "/";

  const supabase = await createClient();
  const { error } = await supabase.auth.signInWithPassword({ email, password });

  if (error) {
    const redirectUrl = new URL("/auth/error", request.url);
    redirectUrl.searchParams.set("message", error.message);
    return NextResponse.redirect(redirectUrl, { status: 303 });
  }

  return NextResponse.redirect(new URL(safeNext, request.url), { status: 303 });
}
