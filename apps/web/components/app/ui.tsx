"use client";

import { AlertTriangle, CheckCircle2, Info, Inbox, Lock, RefreshCw, ShieldAlert, X, XCircle } from "lucide-react";
import { createContext, useCallback, useContext, useEffect, useRef, useState, type JSX, type ReactNode } from "react";

import { ApiError } from "@/lib/api";
import { useT, type TKey } from "@/lib/app-i18n";
import { errorMessage } from "@/lib/hooks";
import type { EnquiryStatus, RunStatus } from "@/lib/workspace";

export function PageHeader({ title, description, actions, kicker }: { title: string; description?: ReactNode; actions?: ReactNode; kicker?: ReactNode }): JSX.Element {
  return (
    <div className="app-page-head">
      <div>
        {kicker && <div className="app-row app-small app-muted" style={{ marginBottom: 6 }}>{kicker}</div>}
        <h1>{title}</h1>
        {description && <p>{description}</p>}
      </div>
      {actions && <div className="app-page-actions">{actions}</div>}
    </div>
  );
}

const STATUS_TONE: Record<EnquiryStatus, string> = {
  received: "", processing: "info", needs_information: "warn", awaiting_review: "accent", approved: "ok", rejected: "danger", failed: "danger",
};

export function StatusBadge({ status }: { status: EnquiryStatus }): JSX.Element {
  const t = useT();
  return <span className={`app-badge ${STATUS_TONE[status] ?? ""}`} data-status={status}><span className="app-dot" aria-hidden="true" />{t(`status.${status}` as TKey)}</span>;
}

const RUN_LABEL: Record<RunStatus, [string, string]> = {
  queued: ["Queued", "info"], running: ["Running", "info"], pausing: ["Pausing after current step", "warn"], paused: ["Paused", "warn"],
  waiting_user: ["Waiting for customer", "warn"], waiting_consent: ["Waiting for consent", "warn"], blocked: ["Blocked", "danger"],
  awaiting_review: ["Ready for human review", "accent"], completed: ["Completed", "ok"], cancelled: ["Cancelled", ""],
  failed: ["Failed", "danger"], superseded: ["Superseded (stale)", ""], needs_staff: ["Handed to staff", "warn"],
};

export function RunStatusBadge({ status }: { status: RunStatus }): JSX.Element {
  const [label, tone] = RUN_LABEL[status] ?? [status, ""];
  return <span className={`app-badge ${tone}`} data-run-status={status}><span className="app-dot" aria-hidden="true" />{label}</span>;
}

export function SourceBadge({ source }: { source: string | null | undefined }): JSX.Element | null {
  if (!source) return null;
  if (source === "live") return <span className="app-badge accent" title="Live model calls against the synthetic catalogue">Live AI · synthetic catalogue</span>;
  if (source === "fixture") return <span className="app-badge outline" title="Deterministic replay; no model calls">Fixture replay · no model calls</span>;
  if (source === "user") return <span className="app-badge warn">User</span>;
  return <span className="app-badge outline">System</span>;
}

export function EmptyState({ title, body, action, icon }: { title: string; body?: ReactNode; action?: ReactNode; icon?: ReactNode }): JSX.Element {
  return (
    <div className="app-empty" role="status">
      {icon ?? <Inbox size={28} aria-hidden="true" />}
      <h3>{title}</h3>
      {body && <p>{body}</p>}
      {action}
    </div>
  );
}

export function ErrorState({ error, onRetry, title }: { error: unknown; onRetry?: () => void; title?: string }): JSX.Element {
  const t = useT();
  const status = error instanceof ApiError ? error.status : 0;
  if (status === 403) return <PermissionDenied />;
  if (status === 404) {
    return <EmptyState icon={<ShieldAlert size={28} aria-hidden="true" />} title="Not available" body="This item does not exist in your workspace, or you do not have access to it." />;
  }
  return (
    <div className="app-alert danger" role="alert">
      <XCircle size={18} aria-hidden="true" />
      <div>
        <strong>{title ?? "Could not load this"}</strong>
        <div className="app-small">{errorMessage(error)}</div>
        {onRetry && <button className="app-btn small" style={{ marginTop: 8 }} onClick={onRetry}><RefreshCw size={14} />{t("common.retry")}</button>}
      </div>
    </div>
  );
}

export function PermissionDenied({ detail }: { detail?: string }): JSX.Element {
  return (
    <EmptyState
      icon={<Lock size={28} aria-hidden="true" />}
      title="You don't have access to this"
      body={detail ?? "Your account does not include the permission this screen needs. Ask an administrator if you need it."}
    />
  );
}

export function Alert({ tone = "info", children, title }: { tone?: "info" | "warn" | "danger" | "ok"; children?: ReactNode; title?: ReactNode }): JSX.Element {
  const Icon = tone === "danger" ? XCircle : tone === "warn" ? AlertTriangle : tone === "ok" ? CheckCircle2 : Info;
  return (
    <div className={`app-alert ${tone}`} role={tone === "danger" ? "alert" : "status"}>
      <Icon size={18} aria-hidden="true" />
      <div>{title && <strong style={{ display: "block" }}>{title}</strong>}{children}</div>
    </div>
  );
}

export function Skeleton({ lines = 3, height = 14 }: { lines?: number; height?: number }): JSX.Element {
  return (
    <div className="app-stack" aria-busy="true" aria-label="Loading">
      {Array.from({ length: lines }).map((_, i) => <div key={i} className="app-skeleton" style={{ height, width: `${92 - i * 11}%` }} />)}
    </div>
  );
}

export function ConfirmDialog({ open, title, body, confirmLabel, tone, onConfirm, onCancel, pending, children }: { open: boolean; title: string; body?: ReactNode; confirmLabel: string; tone?: "danger" | "primary"; onConfirm: () => void; onCancel: () => void; pending?: boolean; children?: ReactNode }): JSX.Element | null {
  const t = useT();
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const previous = document.activeElement as HTMLElement | null;
    ref.current?.querySelector<HTMLElement>("button, textarea, input")?.focus();
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onCancel(); };
    window.addEventListener("keydown", onKey);
    return () => { window.removeEventListener("keydown", onKey); previous?.focus(); };
  }, [open, onCancel]);
  if (!open) return null;
  return (
    <div className="app-dialog-backdrop" onMouseDown={(e) => { if (e.target === e.currentTarget) onCancel(); }}>
      <div className="app-dialog" role="dialog" aria-modal="true" aria-labelledby="app-dialog-title" ref={ref}>
        <h2 id="app-dialog-title">{title}</h2>
        {body && <div className="app-muted">{body}</div>}
        {children}
        <div className="app-dialog-actions">
          <button className="app-btn" onClick={onCancel} disabled={pending}>{t("common.cancel")}</button>
          <button className={`app-btn ${tone === "danger" ? "danger solid" : "primary"}`} onClick={onConfirm} disabled={pending}>{confirmLabel}</button>
        </div>
      </div>
    </div>
  );
}

interface Toast { id: number; tone: "ok" | "danger" | "info"; text: string }
const ToastContext = createContext<(tone: Toast["tone"], text: string) => void>(() => undefined);

export function ToastProvider({ children }: { children: ReactNode }): JSX.Element {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const push = useCallback((tone: Toast["tone"], text: string) => {
    const id = Date.now() + Math.random();
    setToasts((prev) => [...prev.slice(-3), { id, tone, text }]);
    setTimeout(() => setToasts((prev) => prev.filter((t) => t.id !== id)), 5000);
  }, []);
  return (
    <ToastContext.Provider value={push}>
      {children}
      <div className="app-toasts" aria-live="polite">
        {toasts.map((toast) => (
          <div key={toast.id} className={`app-toast ${toast.tone}`} role="status">
            {toast.tone === "danger" ? <XCircle size={16} /> : toast.tone === "ok" ? <CheckCircle2 size={16} /> : <Info size={16} />}
            <span style={{ flex: 1 }}>{toast.text}</span>
            <button className="app-btn ghost small" aria-label="Dismiss" onClick={() => setToasts((prev) => prev.filter((t) => t.id !== toast.id))}><X size={14} /></button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast() {
  return useContext(ToastContext);
}

export function Pager({ cursor, total, limit, onChange }: { cursor: number; total: number; limit: number; onChange: (next: number) => void }): JSX.Element | null {
  const t = useT();
  if (total <= limit) return total ? <div className="app-pager"><span>{total} result{total === 1 ? "" : "s"}</span></div> : null;
  return (
    <div className="app-pager">
      <span>{cursor + 1}–{Math.min(cursor + limit, total)} of {total}</span>
      <span className="app-row">
        <button className="app-btn small" disabled={cursor === 0} onClick={() => onChange(Math.max(0, cursor - limit))}>{t("common.previous")}</button>
        <button className="app-btn small" disabled={cursor + limit >= total} onClick={() => onChange(cursor + limit)}>{t("common.next")}</button>
      </span>
    </div>
  );
}

export function formatTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  try {
    return new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(new Date(iso));
  } catch {
    return iso;
  }
}

export function Ident({ children }: { children: ReactNode }): JSX.Element {
  return <bdi className="app-mono">{children}</bdi>;
}
