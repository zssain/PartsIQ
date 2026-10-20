"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { ApiError } from "@/lib/api";
import { useSession } from "@/lib/session";
import { TERMINAL_RUN, ws, type Exchange, type Run } from "@/lib/workspace";

export interface Loaded<T> {
  data: T | null;
  error: ApiError | Error | null;
  loading: boolean;
  reload: () => void;
}

/** Load server data for the current identity; aborts on unmount and refetches when identity changes. */
export function useLoad<T>(fetcher: (signal: AbortSignal) => Promise<T>, deps: unknown[] = []): Loaded<T> {
  const { epoch, status } = useSession();
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<ApiError | Error | null>(null);
  const [loading, setLoading] = useState(true);
  const [tick, setTick] = useState(0);
  const lastEpoch = useRef(epoch);
  useEffect(() => {
    if (status !== "ready") return;
    if (lastEpoch.current !== epoch) {
      lastEpoch.current = epoch;
      setData(null); // never show the previous identity's data
    }
    const controller = new AbortController();
    setLoading(true);
    fetcher(controller.signal)
      .then((value) => {
        if (!controller.signal.aborted) {
          setData(value);
          setError(null);
        }
      })
      .catch((err: unknown) => {
        if (!controller.signal.aborted && !(err instanceof DOMException && err.name === "AbortError")) {
          setError(err instanceof Error ? err : new Error("Request failed"));
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [epoch, status, tick, ...deps]);
  const reload = useCallback(() => setTick((n) => n + 1), []);
  return { data, error, loading, reload };
}

export interface ActionState<R> {
  run: (...args: never[]) => Promise<R | undefined>;
  pending: boolean;
  error: ApiError | Error | null;
  result: R | undefined;
  reset: () => void;
  key: string;
}

/**
 * Run a mutation with an Idempotency-Key that is REUSED for retries of the same logical action.
 * The key is renewed only after a definitive server answer (2xx or 4xx). A network failure or a
 * 5xx keeps the key, so pressing "Retry" after a timeout cannot apply the action twice.
 */
export function useIdempotentAction<A extends unknown[], R>(fn: (key: string, ...args: A) => Promise<R>): {
  run: (...args: A) => Promise<R | undefined>;
  pending: boolean;
  error: ApiError | Error | null;
  result: R | undefined;
  reset: () => void;
} {
  const keyRef = useRef<string>("");
  const argsRef = useRef<string>("");
  const inFlight = useRef(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<ApiError | Error | null>(null);
  const [result, setResult] = useState<R | undefined>(undefined);
  if (!keyRef.current && typeof crypto !== "undefined") keyRef.current = crypto.randomUUID();
  const run = useCallback(async (...args: A) => {
    if (inFlight.current) return undefined; // double-click guard
    inFlight.current = true;
    setPending(true);
    setError(null);
    // A DIFFERENT logical action (other arguments) after an unresolved failure gets a new key;
    // the same action retried keeps its key so the server can de-duplicate it.
    let signature = "";
    try { signature = JSON.stringify(args); } catch { signature = String(Date.now()); }
    if (argsRef.current && argsRef.current !== signature) keyRef.current = crypto.randomUUID();
    argsRef.current = signature;
    try {
      const value = await fn(keyRef.current, ...args);
      setResult(value);
      keyRef.current = crypto.randomUUID();
      return value;
    } catch (err) {
      const definitive = err instanceof ApiError && err.status >= 400 && err.status < 500;
      if (definitive) keyRef.current = crypto.randomUUID();
      setError(err instanceof Error ? err : new Error("Request failed"));
      return undefined;
    } finally {
      inFlight.current = false;
      setPending(false);
    }
  }, [fn]);
  const reset = useCallback(() => {
    setError(null);
    setResult(undefined);
  }, []);
  return { run, pending, error, result, reset };
}

/**
 * Poll a run's ordered exchanges with a sequence cursor. Bounded exponential backoff while idle,
 * paused when the tab is hidden, aborted on unmount, stopped on terminal permission errors, and
 * de-duplicated by sequence number so reconnects never repeat events.
 */
export function useRunEvents(runId: string | null) {
  const { status } = useSession();
  const [events, setEvents] = useState<Exchange[]>([]);
  const [run, setRun] = useState<Run | null>(null);
  const [error, setError] = useState<ApiError | Error | null>(null);
  const [stopped, setStopped] = useState(false);
  const cursor = useRef(0);
  const seen = useRef(new Set<number>());
  const [nudge, setNudge] = useState(0);

  useEffect(() => {
    cursor.current = 0;
    seen.current = new Set();
    setEvents([]);
    setRun(null);
    setStopped(false);
    setError(null);
  }, [runId]);

  useEffect(() => {
    if (!runId || status !== "ready") return;
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | null = null;
    let delay = 600;
    let controller: AbortController | null = null;
    let idleTerminal = 0;

    const schedule = (ms: number) => {
      if (cancelled) return;
      timer = setTimeout(tick, ms);
    };
    const tick = async () => {
      if (cancelled) return;
      if (typeof document !== "undefined" && document.hidden) {
        schedule(1500);
        return;
      }
      controller = new AbortController();
      try {
        const page = await ws.events(runId, cursor.current, controller.signal);
        if (cancelled) return;
        const fresh = page.items.filter((e) => !seen.current.has(e.seq));
        fresh.forEach((e) => seen.current.add(e.seq));
        if (fresh.length) setEvents((prev) => [...prev, ...fresh].sort((a, b) => a.seq - b.seq));
        cursor.current = Math.max(cursor.current, page.next_after);
        setRun(page.run);
        setError(null);
        const terminal = TERMINAL_RUN.includes(page.run.status) || ["waiting_user", "waiting_consent", "blocked", "paused"].includes(page.run.status);
        if (fresh.length) {
          delay = 600;
          idleTerminal = 0;
        } else {
          delay = Math.min(delay * 1.6, 8000);
          if (terminal) idleTerminal += 1;
        }
        if (terminal && idleTerminal >= 2) {
          setStopped(true); // nothing more will happen until the user acts
          return;
        }
        schedule(delay);
      } catch (err) {
        if (cancelled || (err instanceof DOMException && err.name === "AbortError")) return;
        if (err instanceof ApiError && [401, 403, 404].includes(err.status)) {
          setError(err);
          setStopped(true); // terminal permission error: stop polling
          return;
        }
        setError(err instanceof Error ? err : new Error("Connection lost"));
        delay = Math.min(delay * 2, 10000);
        schedule(delay);
      }
    };
    setStopped(false);
    tick();
    const onVisible = () => {
      if (!document.hidden && timer) {
        clearTimeout(timer);
        tick();
      }
    };
    document.addEventListener("visibilitychange", onVisible);
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
      controller?.abort();
      document.removeEventListener("visibilitychange", onVisible);
    };
  }, [runId, status, nudge]);

  /** Resume polling after the user acts (a command changes what will happen next). */
  const wake = useCallback(() => setNudge((n) => n + 1), []);
  return { events, run, error, stopped, wake };
}

export function errorMessage(err: unknown): string {
  if (err instanceof ApiError) {
    const id = err.requestId ? ` (request ${err.requestId.slice(0, 8)})` : "";
    return `${err.message}${id}`;
  }
  if (err instanceof Error) return err.message;
  return "Something went wrong.";
}
