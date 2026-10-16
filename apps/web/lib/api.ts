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

function baseUrl(): string {
  return process.env.NEXT_PUBLIC_API_BASE_URL ?? "";
}

export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers);
  if (!headers.has("content-type") && options.body) {
    headers.set("content-type", "application/json");
  }
  const token = await tokenProvider();
  if (token) {
    headers.set("authorization", `Bearer ${token}`); // bearer in header, not the URL
  }

  const response = await fetch(`${baseUrl()}${path}`, { ...options, headers });
  const requestId = response.headers.get("x-request-id");

  if (!response.ok) {
    let code = "DEPENDENCY_UNAVAILABLE";
    let message = response.statusText || "Request failed";
    try {
      const body = (await response.json()) as { error?: { code?: string; message?: string; request_id?: string } };
      if (body?.error) {
        code = body.error.code ?? code;
        message = body.error.message ?? message;
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
