import { NextResponse, type NextRequest } from "next/server";

import { createClient } from "@/lib/supabase/server";

export async function POST(request: NextRequest) {
  try {
    const supabase = await createClient();
    await supabase.auth.signOut();
  } catch {
    // If auth env is missing or invalid, still move the user out of the app
    // surface instead of failing the sign-out request.
  }

  return NextResponse.redirect(new URL("/auth/sign-in", request.url), {
    status: 303,
  });
}

export async function GET(request: NextRequest) {
  return POST(request);
}
