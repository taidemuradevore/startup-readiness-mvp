import { createClient } from "@/lib/supabase/server";

export async function getAccessToken() {
  if (
    !process.env.NEXT_PUBLIC_SUPABASE_URL ||
    !process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY
  ) {
    return null;
  }

  const supabase = await createClient();
  const { data } = await supabase.auth.getSession();

  return data.session?.access_token ?? null;
}
