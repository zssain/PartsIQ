"use client";

import { Bot, Camera, ImagePlus, Send, Workflow } from "lucide-react";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState, type JSX } from "react";

import { Alert, ErrorState, PageHeader, PermissionDenied, Skeleton, useToast } from "@/components/app/ui";
import { useLocale } from "@/lib/app-i18n";
import { errorMessage, useIdempotentAction, useLoad } from "@/lib/hooks";
import { useSession } from "@/lib/session";
import { ws, type RunMode } from "@/lib/workspace";

const DRAFT_KEY = "pq-new-enquiry-draft";
const EXAMPLES = [
  "Need 2 oil filters for a Veltrano Power VP-20, serial 120000",
  "I need a hydraulic filter for a Corvane Air CA-110.",
  "Need a filter for VP-60 serial 210000",
  "محتاج 2 فلتر زيت لمولد VP-20 رقم تسلسلي 120000",
  "Need 1 CA-AF-1828 for my Corvane Air CA-110 (A)",
];
const MAX_IMAGE = 10 * 1024 * 1024;

function siblingKey(key: string, suffix: "a" | "b"): string {
  return `${key.slice(0, 34)}${suffix}${suffix}`;
}

export default function NewEnquiryPage(): JSX.Element {
  const { can, identity } = useSession();
  const router = useRouter();
  const toast = useToast();
  const uiLocale = useLocale();
  const warehouses = useLoad(() => ws.warehouses());
  const [text, setText] = useState("");
  const [locale, setLocale] = useState<"en" | "ar">(uiLocale);
  const [destination, setDestination] = useState<number>(1);
  const [mode, setMode] = useState<RunMode>("guided");
  const [photo, setPhoto] = useState<File | null>(null);
  const [sample, setSample] = useState(false);
  const [touched, setTouched] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  // Preserve unsent input across reloads and failures (cleared only after a committed create).
  useEffect(() => {
    try {
      const saved = JSON.parse(window.localStorage.getItem(DRAFT_KEY) ?? "null");
      // eslint-disable-next-line react-hooks/set-state-in-effect -- restores the unsent draft from localStorage, readable only after hydration (a lazy initializer would mismatch the server render)
      if (saved?.text) setText(saved.text);
    } catch { /* storage optional */ }
  }, []);
  useEffect(() => {
    try { window.localStorage.setItem(DRAFT_KEY, JSON.stringify({ text })); } catch { /* optional */ }
  }, [text]);

  const submit = useCallback(async (key: string) => {
    const withPhoto = sample || Boolean(photo);
    // With a photo: commit the enquiry first without processing, attach the validated image, then
    // start the run so the nameplate is read at intake (no race with an already-running run).
    const created = await ws.create({ text: text.trim(), locale, destination_warehouse_id: destination }, mode, key, withPhoto);
    if (withPhoto) {
      // Sibling keys derived from the action key: a retry of the whole submit reuses all three.
      if (sample) await ws.attachSample(created.id, siblingKey(key, "a"));
      else if (photo) await ws.upload(created.id, photo, siblingKey(key, "a"));
      await ws.startRun(created.id, mode, created.revision, siblingKey(key, "b"));
    }
    return created;
  }, [text, locale, destination, mode, sample, photo]);
  const action = useIdempotentAction(submit);

  if (!can("enquiry.create")) return <PermissionDenied />;
  const textError = touched && !text.trim() ? "Describe the part you need." : text.length > 12000 ? "Keep the request under 12,000 characters." : null;
  const photoError = photo && photo.size > MAX_IMAGE ? "The photo must be 10 MB or smaller." : photo && !["image/jpeg", "image/png", "image/webp"].includes(photo.type) ? "Use a JPEG, PNG or WebP photo." : null;

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setTouched(true);
    if (!text.trim() || textError || photoError) return;
    const created = await action.run();
    if (created) {
      try { window.localStorage.removeItem(DRAFT_KEY); } catch { /* optional */ }
      toast("ok", "Enquiry sent. Watch its progress here.");
      router.push(`/workspace/enquiries/${created.id}`);
    }
  };

  return (
    <>
      <PageHeader title="New enquiry" description="Describe the part in English, Arabic or both. Include the machine model and the serial number from the nameplate if you have it." />
      <form className="app-split" onSubmit={onSubmit} noValidate>
        <div className="app-card app-stack">
          <label className="app-field">
            <span>What do you need?</span>
            <textarea className="app-textarea" data-testid="enquiry-text" value={text} onChange={(e) => setText(e.target.value)} onBlur={() => setTouched(true)} aria-invalid={Boolean(textError)} aria-describedby="text-help" dir="auto" maxLength={12000} placeholder="e.g. Need 2 oil filters for a Veltrano Power VP-20, serial 120000" />
            <small id="text-help">Quantities, model and serial help us match the exact part. Nothing is sent to anyone until a reviewer approves it.</small>
            {textError && <span className="app-field-error" role="alert">{textError}</span>}
          </label>
          <div className="app-row app-small">
            <span className="app-muted">Try:</span>
            {EXAMPLES.map((example) => <button key={example} type="button" className="app-btn ghost small" onClick={() => setText(example)} dir="auto">{example.length > 42 ? `${example.slice(0, 42)}…` : example}</button>)}
          </div>
          <div className="app-grid cols-2">
            <label className="app-field"><span>Reply language</span>
              <select value={locale} onChange={(e) => setLocale(e.target.value as "en" | "ar")}><option value="en">English</option><option value="ar">العربية</option></select>
            </label>
            <label className="app-field"><span>Deliver to</span>
              {warehouses.error ? <ErrorState error={warehouses.error} onRetry={warehouses.reload} /> : !warehouses.data ? <Skeleton lines={1} /> : (
                <select data-testid="destination" value={destination} onChange={(e) => setDestination(Number(e.target.value))}>
                  {warehouses.data.map((w) => <option key={w.id} value={w.id}>{w.name}</option>)}
                </select>
              )}
            </label>
          </div>
          <fieldset className="app-stack" style={{ border: 0, padding: 0, margin: 0 }}>
            <legend className="app-label" style={{ marginBottom: 6 }}>How should it be processed?</legend>
            <div className="app-choice" role="radiogroup">
              <label>
                <input type="radio" name="mode" value="guided" checked={mode === "guided"} onChange={() => setMode("guided")} data-testid="mode-guided" />
                <strong><Workflow size={15} />Guided workflow</strong>
                <span>Fixed steps run by code: identify → compatible search → stock → draft → verify → human review.</span>
              </label>
              <label>
                <input type="radio" name="mode" value="collaboration" checked={mode === "collaboration"} onChange={() => setMode("collaboration")} disabled={!identity?.collaboration_enabled} data-testid="mode-collaboration" />
                <strong><Bot size={15} />Agent collaboration</strong>
                <span>Specialists exchange requests and evidence under a controller. You can pause, instruct and approve delegations.</span>
              </label>
            </div>
            <small className="app-muted">The mode is fixed once a run starts. To switch, start a new run from the enquiry page; earlier runs stay in the history.</small>
          </fieldset>
          <div className="app-field">
            <span>Nameplate photo (optional)</span>
            <div className="app-row">
              <input ref={fileRef} type="file" accept="image/jpeg,image/png,image/webp" hidden onChange={(e) => { setPhoto(e.target.files?.[0] ?? null); setSample(false); }} />
              <button type="button" className="app-btn small" onClick={() => fileRef.current?.click()}><ImagePlus size={15} />Choose photo</button>
              <button type="button" className="app-btn small" aria-pressed={sample} onClick={() => { setSample(!sample); setPhoto(null); }} data-testid="use-sample-plate"><Camera size={15} />{sample ? "Sample nameplate attached" : "Use the synthetic sample nameplate"}</button>
              {photo && <span className="app-small">{photo.name} · {(photo.size / 1024).toFixed(0)} KB</span>}
            </div>
            <small>Read identifiers always need your confirmation before they are used. In fixture mode only the synthetic sample can be read; other photos are reported unreadable so you can type the details.</small>
            {photoError && <span className="app-field-error" role="alert">{photoError}</span>}
          </div>
          {action.error && <Alert tone="danger" title="Not sent">{errorMessage(action.error)} Your text is kept — you can retry safely; a retry reuses the same request key.</Alert>}
          <div className="app-row">
            <button className="app-btn primary" type="submit" disabled={action.pending} data-testid="enquiry-submit"><Send size={15} />{action.pending ? "Sending…" : "Send enquiry"}</button>
          </div>
        </div>
        <aside className="app-card sunken app-stack">
          <h2 className="app-card-title">What happens next</h2>
          <ol className="app-small" style={{ margin: 0, paddingInlineStart: 18, display: "grid", gap: 6 }}>
            <li>Your request is read and the machine identified from model and serial.</li>
            <li>Only parts listed as compatible for that exact configuration are considered.</li>
            <li>Stock and transfer estimates come from warehouse data; nothing is reserved.</li>
            <li>A reply is drafted from verified facts and checked by seven deterministic rules.</li>
            <li>A staff reviewer approves or returns it. Only then do you see a recommendation.</li>
          </ol>
          <p className="app-small app-muted">If something is missing (for example the serial) you will be asked here before anything is guessed.</p>
        </aside>
      </form>
    </>
  );
}
