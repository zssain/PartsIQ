// Typed gateway client. ALL business API calls go through the gateway base URL; the bearer
// token rides in the Authorization header (never in the URL), and the server-displayed
// request id is surfaced on every error for support. No secret is ever read here — only the
// public NEXT_PUBLIC_API_BASE_URL and a session access token provided by the auth layer.

export class ApiError extends Error {
  readonly code: string;
  readonly status: number;
  readonly requestId: string | null;

  constructor(code: string, status: number, message: string, requestId: string | null) {
    super(message);
    this.name = "ApiError";
    this.code = code;
    this.status = status;
    this.requestId = requestId;
  }
}

type TokenProvider = () => Promise<string | null>;

let tokenProvider: TokenProvider = async () => null;

// The auth layer registers how to fetch the current access token, so api.ts never imports
// the Supabase client directly (and never couples the request path to a session module).
export function setTokenProvider(provider: TokenProvider): void {
  tokenProvider = provider;
}

// The single-package backend (build-kit edition) publishes one FastAPI app whose only public
// surface is `/v1`. NEXT_PUBLIC_API_ORIGIN is the backend origin (per spec/environment.json);
// NEXT_PUBLIC_API_BASE_URL stays supported for the legacy gateway wiring. Either may be set.
function baseUrl(): string {
  const explicit = process.env.NEXT_PUBLIC_API_BASE_URL;
  if (explicit) return explicit;
  const origin = process.env.NEXT_PUBLIC_API_ORIGIN;
  return origin ? `${origin.replace(/\/$/, "")}/v1` : "/v1";
}

// Fixture-mode demo identity: the anonymous browser session presents an opaque demo token the
// backend's fixture verifier accepts (X-Demo-Token). It only ever scopes a caller to its own
// synthetic session; it never grants a staff role. No-op once a real Supabase bearer is present.
let demoToken: string | null = null;
export function setDemoToken(token: string | null): void {
  demoToken = token;
}

export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers);
  if (!headers.has("content-type") && options.body) {
    headers.set("content-type", "application/json");
  }
  const token = await tokenProvider();
  if (token) {
    headers.set("authorization", `Bearer ${token}`); // bearer in header, not the URL
  } else if (demoToken) {
    headers.set("x-demo-token", demoToken); // anonymous fixture-mode identity
  }

  const base = baseUrl().replace(/\/$/, "");
  // Callers support both legacy relative paths and canonical /v1 paths.
  const suffix = base.endsWith("/v1") && (path === "/v1" || path.startsWith("/v1/"))
    ? path.slice(3) : path;
  const response = await fetch(`${base}${suffix}`, { ...options, headers });
  let requestId = response.headers.get("x-request-id");

  if (!response.ok) {
    let code = "DEPENDENCY_UNAVAILABLE";
    let message = response.statusText || "Request failed";
    try {
      // The backend returns an RFC9457 Problem ({code, detail, request_id, ...}); the legacy
      // gateway returned {error:{code,message,request_id}}. Accept either shape.
      const body = (await response.json()) as {
        code?: string;
        detail?: string;
        request_id?: string;
        error?: { code?: string; message?: string; request_id?: string };
      };
      if (body?.code) {
        code = body.code;
        message = body.detail ?? message;
        requestId = requestId ?? body.request_id ?? null;
      } else if (body?.error) {
        code = body.error.code ?? code;
        message = body.error.message ?? message;
        requestId = requestId ?? body.error.request_id ?? null;
      }
    } catch {
      // Non-JSON error body: keep the safe defaults; never surface a raw stack trace.
    }
    throw new ApiError(code, response.status, message, requestId);
  }

  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}
