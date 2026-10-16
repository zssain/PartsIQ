import type { NextConfig } from "next";

// Prompt 18 base config. Locale/i18n wiring (next-intl) is added by F07.
// Business API calls go through the gateway (NEXT_PUBLIC_API_BASE_URL); only Supabase Auth
// and authorized private Storage transfer bypass it. No secret is ever exposed here.
const nextConfig: NextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  env: {
    NEXT_PUBLIC_API_BASE_URL: process.env.NEXT_PUBLIC_API_BASE_URL,
  },
};

export default nextConfig;
