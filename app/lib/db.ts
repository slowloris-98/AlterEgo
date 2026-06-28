import { createClient, type SupabaseClient } from "@supabase/supabase-js";

/**
 * Server-only Supabase client built from the service-role key. Returns null when
 * env vars are absent so the app runs and logs gracefully no-op locally.
 * The service-role key must NEVER be exposed to the client (no NEXT_PUBLIC_).
 */

let cached: SupabaseClient | null | undefined;

export function getSupabase(): SupabaseClient | null {
  if (cached !== undefined) return cached;

  const url = process.env.SUPABASE_URL;
  const key = process.env.SUPABASE_SERVICE_ROLE_KEY;

  if (!url || !key) {
    cached = null;
    return cached;
  }

  cached = createClient(url, key, {
    auth: { persistSession: false, autoRefreshToken: false },
  });
  return cached;
}
