import { createClient } from "@/lib/supabase/server";

function hasSupabaseConfig() {
  return Boolean(
    process.env.NEXT_PUBLIC_SUPABASE_URL?.trim() &&
      process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY?.trim(),
  );
}

export async function getAccessToken() {
  if (!hasSupabaseConfig()) {
    return null;
  }

  try {
    const supabase = await createClient();
    const { data } = await supabase.auth.getSession();

    return data.session?.access_token ?? null;
  } catch {
    return null;
  }
}
