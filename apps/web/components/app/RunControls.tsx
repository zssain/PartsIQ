"use client";

import { Ban, CheckCircle2, MessageSquarePlus, Pause, Play, RotateCcw, ShieldQuestion, XCircle } from "lucide-react";
import { useCallback, useState, type JSX } from "react";

import { useLabel, useT } from "@/lib/app-i18n";
import { errorMessage, useIdempotentAction } from "@/lib/hooks";
import { ws, type PendingAction, type Run } from "@/lib/workspace";

import { Alert, ConfirmDialog, RunStatusBadge, SourceBadge, useToast } from "./ui";

/**
 * Master controls for a run. Every button is an authenticated backend command carrying the
 * enquiry's expected revision and an idempotency key; what the server says is what we show
 * ("pausing after current step" until the server reaches a safe boundary).
 */
export function RunControls({ run, onChanged, compact = false }: { run: Run; onChanged: () => void; compact?: boolean }): JSX.Element {
  const toast = useToast();
  const t = useT();
  const [instruction, setInstruction] = useState("");
  const [confirmCancel, setConfirmCancel] = useState(false);
  const send = useCallback(async (key: string, type: string, payload: Record<string, unknown> = {}) => ws.command(run.id, { type, expected_revision: run.current_revision, payload }, key), [run.id, run.current_revision]);
  const command = useIdempotentAction(send);
  const can = (action: string) => run.available_actions.includes(action);
  const act = async (type: string, payload?: Record<string, unknown>) => {
    const result = await command.run(type, payload ?? {});
    if (result) {
      toast("ok", t("ctl.server", { result: result.result }));
      if (type === "instruct") setInstruction("");
      onChanged();
    }
  };
  const limit = (name: string) => Number(run.limits[name] ?? 0);
  return (
    <div className="app-stack" data-testid="run-controls">
      <div className="app-row">
        <RunStatusBadge status={run.status} />
        <SourceBadge source={run.execution_source} />
        {run.stale && <span className="app-badge outline">{t("ctl.staleRev")}</span>}
      </div>
      {run.status === "pausing" && <Alert tone="warn">{t("ctl.pausing")}</Alert>}
      {run.blocked_reason && <Alert tone="danger" title={t("ctl.blocked")}>{run.terminal_reason}</Alert>}
      {run.terminal_reason && !run.blocked_reason && ["cancelled", "superseded", "failed", "needs_staff"].includes(run.status) && <p className="app-small app-muted">{run.terminal_reason}</p>}
      <div className="app-row">
        {can("pause") && <button className="app-btn small" onClick={() => act("pause")} disabled={command.pending} data-testid="run-pause"><Pause size={14} />{t("ctl.pause")}</button>}
        {can("resume") && <button className="app-btn small primary" onClick={() => act("resume")} disabled={command.pending} data-testid="run-resume"><Play size={14} />{t("ctl.resume")}</button>}
        {can("cancel") && <button className="app-btn small danger" onClick={() => setConfirmCancel(true)} disabled={command.pending} data-testid="run-cancel"><Ban size={14} />{t("ctl.cancelRun")}</button>}
        {can("fixture_replay") && <button className="app-btn small" onClick={() => act("fixture_replay")} disabled={command.pending} data-testid="run-replay"><RotateCcw size={14} />{t("ctl.replay")}</button>}
      </div>
      {can("instruct") && !compact && (
        <form className="app-stack" onSubmit={(e) => { e.preventDefault(); if (instruction.trim()) act("instruct", { text: instruction.trim() }); }}>
          <label className="app-field">
            <span><MessageSquarePlus size={14} /> {t("ctl.instruct")}</span>
            <textarea className="app-textarea" style={{ minHeight: 70 }} value={instruction} onChange={(e) => setInstruction(e.target.value)} maxLength={Number(run.limits.max_instruction_chars ?? 500)} placeholder={t("ctl.instructPlaceholder")} data-testid="run-instruction" dir="auto" />
            <small>{t("ctl.instructHelp")}</small>
          </label>
          <div><button className="app-btn small" type="submit" disabled={command.pending || !instruction.trim()}>{t("ctl.sendInstruction")}</button></div>
        </form>
      )}
      {command.error && <Alert tone="danger" title={t("ctl.rejected")}>{errorMessage(command.error)}</Alert>}
      {!compact && (
        <dl className="app-kv app-small">
          <dt>{t("ctl.turns")}</dt><dd>{run.usage.agent_turns} / {limit("max_agent_turns")}</dd>
          <dt>{t("ctl.tools")}</dt><dd>{run.usage.tool_calls} / {limit("max_tool_calls")}</dd>
          <dt>{t("ctl.tokens")}</dt><dd>{run.usage.output_tokens ?? t("ctl.tokensNone")}</dd>
          <dt>{t("ctl.activeTime")}</dt><dd>{t("ctl.seconds", { used: run.usage.active_seconds, max: limit("max_wall_seconds") })}</dd>
          <dt>{t("ctl.retries")}</dt><dd>{run.usage.retries}</dd>
        </dl>
      )}
      <ConfirmDialog
        open={confirmCancel}
        title={t("ctl.cancelTitle")}
        body={t("ctl.cancelBody")}
        confirmLabel={t("ctl.cancelRun")}
        tone="danger"
        pending={command.pending}
        onCancel={() => setConfirmCancel(false)}
        onConfirm={async () => { setConfirmCancel(false); await act("cancel"); }}
      />
    </div>
  );
}

/** Customer / overseer action requested by the run: answer, confirm identifiers, or consent. */
export function PendingPanel({ pending, run, onChanged }: { pending: PendingAction; run: Run; onChanged: () => void }): JSX.Element {
  const toast = useToast();
  const t = useT();
  const label = useLabel();
  const [text, setText] = useState("");
  const [model, setModel] = useState(pending.options.find((o) => o.value === "model")?.label ?? "");
  const [serial, setSerial] = useState(pending.options.find((o) => o.value === "serial")?.label ?? "");
  const send = useCallback(async (key: string, type: string, payload: Record<string, unknown>) => ws.command(run.id, { type, expected_revision: run.current_revision, payload }, key), [run.id, run.current_revision]);
  const command = useIdempotentAction(send);
  const go = async (type: string, payload: Record<string, unknown>) => {
    const result = await command.run(type, payload);
    if (result) {
      toast("ok", result.result);
      setText("");
      onChanged();
    }
  };
  return (
    <div className="app-card" style={{ borderColor: "var(--app-warn)" }} data-testid="pending-action" data-kind={pending.kind}>
      <h3 className="app-card-title"><ShieldQuestion size={16} />{pending.kind === "delegation_consent" ? t("pending.consentTitle") : pending.kind === "nameplate_confirmation" ? t("pending.nameplateTitle") : t("pending.clarTitle")}<span className="app-badge outline">{label("participant", pending.requested_by, pending.requested_by_label)}</span></h3>
      <p dir="auto">{pending.prompt}</p>
      {pending.kind === "clarification" && (
        <form className="app-stack" onSubmit={(e) => { e.preventDefault(); if (text.trim()) go("answer", { text: text.trim() }); }}>
          {pending.options.length > 0 && (
            <div className="app-row">
              {pending.options.map((option, index) => (
                <button key={option.value} type="button" className="app-btn small" onClick={() => go("answer", { text: option.part_number ?? option.label ?? String(index + 1) })} data-testid="pending-option">{option.label}</button>
              ))}
            </div>
          )}
          <label className="app-field">
            <span>{t("pending.yourAnswer")}</span>
            <input className="app-input" value={text} onChange={(e) => setText(e.target.value)} placeholder={pending.code === "needs_serial" ? t("pending.serialPlaceholder") : pending.code === "quantity" ? t("pending.qtyPlaceholder") : t("pending.answerPlaceholder")} data-testid="pending-answer" dir="auto" maxLength={2000} />
          </label>
          <div><button className="app-btn primary small" type="submit" disabled={command.pending || !text.trim()} data-testid="pending-submit">{t("pending.sendAnswer")}</button></div>
          <small className="app-muted">{t("pending.answerNote")}</small>
        </form>
      )}
      {pending.kind === "nameplate_confirmation" && (
        <form className="app-stack" onSubmit={(e) => { e.preventDefault(); go("confirm_nameplate", { model_text: model.trim(), serial_text: serial.trim() || null }); }}>
          <div className="app-grid cols-2">
            <label className="app-field"><span>{t("pending.model")}</span><input className="app-input" value={model} onChange={(e) => setModel(e.target.value)} required maxLength={120} dir="ltr" /></label>
            <label className="app-field"><span>{t("pending.serial")}</span><input className="app-input" value={serial} onChange={(e) => setSerial(e.target.value)} maxLength={120} inputMode="numeric" dir="ltr" /></label>
          </div>
          <div className="app-row">
            <button className="app-btn primary small" type="submit" disabled={command.pending || !model.trim()} data-testid="confirm-nameplate"><CheckCircle2 size={14} />{t("common.confirm")}</button>
          </div>
        </form>
      )}
      {pending.kind === "delegation_consent" && (
        <div className="app-row">
          <button className="app-btn primary small" onClick={() => go("resolve_delegation", { decision: "approve" })} disabled={command.pending} data-testid="consent-approve"><CheckCircle2 size={14} />{t("pending.allow")}</button>
          <button className="app-btn small" onClick={() => go("resolve_delegation", { decision: "deny" })} disabled={command.pending} data-testid="consent-deny"><XCircle size={14} />{t("pending.decline")}</button>
        </div>
      )}
      {command.error && <div style={{ marginTop: 10 }}><Alert tone="danger" title={t("pending.notAccepted")}>{errorMessage(command.error)}</Alert></div>}
    </div>
  );
}
