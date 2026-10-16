// Supabase browser auth. Only the public URL and publishable key are used here (both are
// browser-safe, CONSTRAINTS rule 10); the service key and JWT verification stay server-side
// in the gateway (prompt 07). Anonymous sign-in powers the public synthetic demo; invited
// staff sign in with a password. Real-client self-signup is NOT exposed.
import { createBrowserClient } from "@supabase/ssr";
import type { SupabaseClient } from "@supabase/supabase-js";

import { api, setTokenProvider } from "@/lib/api";
import type { DemoSession } from "@/lib/contracts";

let client: SupabaseClient | null = null;

export function browserClient(): SupabaseClient {
  if (client === null) {
    const url = process.env.NEXT_PUBLIC_SUPABASE_URL ?? "";
    const key = process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY ?? "";
    client = createBrowserClient(url, key);
    setTokenProvider(async () => {
      const { data } = await client!.auth.getSession();
      return data.session?.access_token ?? null;
    });
  }
  return client;
}

export async function getAccessToken(): Promise<string | null> {
  const { data } = await browserClient().auth.getSession();
  return data.session?.access_token ?? null;
}

// Public demo: sign in anonymously, then create a server-side demo session via the gateway.
export async function startAnonymousDemo(): Promise<DemoSession> {
  const supabase = browserClient();
  const { error } = await supabase.auth.signInAnonymously();
  if (error) {
    throw new Error("Could not start a demo session.");
  }
  return api<DemoSession>("/v1/demo/session", { method: "POST" });
}

// Invited staff only; there is deliberately no real-client signup path.
export async function signInStaff(email: string, password: string): Promise<void> {
  const { error } = await browserClient().auth.signInWithPassword({ email, password });
  if (error) {
    throw new Error("Sign in failed. Check your invited staff credentials.");
  }
}
