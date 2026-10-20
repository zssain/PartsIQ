import { afterEach, expect, it, vi } from "vitest";
import { api } from "@/lib/api";

afterEach(() => { vi.unstubAllEnvs(); vi.unstubAllGlobals(); });
it.each([
  [undefined, undefined, "/v1/enquiries", "/v1/enquiries"],
  [undefined, "https://api.example.test", "/v1/enquiries", "https://api.example.test/v1/enquiries"],
  ["https://api.example.test/v1/", undefined, "/enquiries", "https://api.example.test/v1/enquiries"],
  ["https://api.example.test", undefined, "/v1/enquiries", "https://api.example.test/v1/enquiries"],
])("normalizes canonical and legacy routes (%s, %s, %s)", async (base, origin, path, expected) => {
  vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", base);
  vi.stubEnv("NEXT_PUBLIC_API_ORIGIN", origin);
  const fetcher = vi.fn().mockResolvedValue(new Response("{}", {status:200}));
  vi.stubGlobal("fetch", fetcher);
  await api(path);
  expect(fetcher.mock.calls[0][0]).toBe(expected);
});
