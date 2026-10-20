"use client";

import { ArrowRight, Bot, Cog, FileSearch, Fingerprint, MessageSquare, ScanLine, ShieldCheck, Truck, User, Workflow } from "lucide-react";
import { useMemo, useState, type JSX } from "react";

import type { Exchange } from "@/lib/workspace";

import { EmptyState, SourceBadge } from "./ui";

const AGENTS = new Set(["intake", "nameplate", "parts", "reply"]);
const SERVICES = new Set(["identification", "compatibility_search", "fulfilment", "verification"]);
const ERRORS = new Set(["action_rejected", "limit_reached", "provider_unavailable", "late_result_discarded"]);
const USER = new Set(["user_instruction", "user_answer", "consent_result", "control"]);

const ICONS: Record<string, typeof Bot> = {
  intake: MessageSquare, nameplate: ScanLine, parts: FileSearch, reply: Bot,
  identification: Fingerprint, compatibility_search: FileSearch, fulfilment: Truck, verification: ShieldCheck,
  controller: Cog, workflow: Workflow, customer: User, reviewer: User,
};

type Filter = "all" | "exchanges" | "tools" | "user" | "errors";
const FILTERS: [Filter, string][] = [["all", "All events"], ["exchanges", "Specialist exchanges"], ["tools", "Tools & evidence"], ["user", "User actions"], ["errors", "Errors"]];

function matches(e: Exchange, filter: Filter): boolean {
  if (filter === "all") return true;
  if (filter === "errors") return ERRORS.has(e.kind);
  if (filter === "tools") return e.kind === "tool_call" || e.kind === "tool_result" || e.kind === "step_completed" || SERVICES.has(e.sender);
  if (filter === "user") return USER.has(e.kind) || e.source === "user";
  return AGENTS.has(e.sender) && e.kind !== "tool_call";
}

export function ExchangeFeed({ events, newestFirst = false, freshFrom = 0 }: { events: Exchange[]; newestFirst?: boolean; freshFrom?: number }): JSX.Element {
  const [filter, setFilter] = useState<Filter>("all");
  const shown = useMemo(() => {
    const list = events.filter((e) => matches(e, filter));
    return newestFirst ? [...list].reverse() : list;
  }, [events, filter, newestFirst]);
  return (
    <div className="app-stack">
      <div className="app-seg" role="group" aria-label="Filter events">
        {FILTERS.map(([value, label]) => (
          <button key={value} type="button" aria-pressed={filter === value} onClick={() => setFilter(value)} data-testid={`filter-${value}`}>
            {label} <span className="app-muted">{events.filter((e) => matches(e, value)).length}</span>
          </button>
        ))}
      </div>
      {shown.length === 0 ? <EmptyState title="No events for this filter" body="Events appear here as the run records them." /> : (
        <ol className="app-feed" style={{ listStyle: "none", margin: 0, padding: 0 }} aria-live="polite" data-testid="exchange-feed">
          {shown.map((e) => <ExchangeItem key={e.id} e={e} fresh={e.seq > freshFrom && freshFrom > 0} />)}
        </ol>
      )}
    </div>
  );
}

function ExchangeItem({ e, fresh }: { e: Exchange; fresh: boolean }): JSX.Element {
  const Icon = ICONS[e.sender] ?? Cog;
  const avatar = AGENTS.has(e.sender) ? "" : SERVICES.has(e.sender) ? "service" : e.source === "user" ? "user" : "system";
  const payload = Object.keys(e.payload ?? {}).length ? JSON.stringify(e.payload, null, 2) : null;
  return (
    <li className={`app-ex ${fresh ? "app-ex-new" : ""}`} data-kind={e.kind} data-seq={e.seq} data-sender={e.sender} data-recipient={e.recipient ?? ""}>
      <span className={`app-ex-avatar ${avatar}`} aria-hidden="true"><Icon size={17} /></span>
      <div style={{ minWidth: 0 }}>
        <div className="app-ex-head">
          <strong>{e.sender_label}</strong>
          {e.recipient_label && <><ArrowRight size={13} aria-label="to" /><span>{e.recipient_label}</span></>}
          <span className="app-badge outline">{e.kind_label}</span>
          {e.status === "waiting" && <span className="app-badge warn">Waiting</span>}
          {(e.source === "fixture" || e.source === "live") && <SourceBadge source={e.source} />}
          <time dateTime={e.created_at}>#{e.seq} · {new Date(e.created_at).toLocaleTimeString()}</time>
        </div>
        <p dir="auto">{e.summary}</p>
        {e.evidence_refs.length > 0 && (
          <div className="app-row app-small" style={{ marginTop: 6 }}>
            <span className="app-muted">Evidence:</span>
            {e.evidence_refs.map((ref) => <span key={ref} className="app-badge info app-mono">{ref}</span>)}
          </div>
        )}
        {payload && (
          <details>
            <summary>Structured payload</summary>
            <pre>{payload}</pre>
          </details>
        )}
      </div>
    </li>
  );
}
