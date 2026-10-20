"use client";

import Link from "next/link";
import { useEffect, useState, type JSX } from "react";
import { ArrowLeft, ArrowUpRight, Bot, CheckCheck, ChevronRight, CircleHelp, ClipboardCheck, Database, Fingerprint, GitBranch, LayoutDashboard, MessageSquare, Plus, Radio, ShieldCheck, Workflow } from "lucide-react";
import { ensureDemoToken } from "@/lib/live";
import { RoleSwitch, type Role } from "./RoleSwitch";
import { CustomerLive } from "./CustomerLive";
import { ReviewerInbox } from "./ReviewerInbox";
import { ReviewWorkspaceLive } from "./ReviewWorkspaceLive";
import { SpecialistTimeline } from "@/components/visibility/SpecialistTimeline";
import { ThemeControl } from "@/components/ui/ThemeControl";
import { LocaleControl } from "@/components/ui/LocaleControl";
import { BrandLogo } from "@/components/BrandLogo";
import type { Locale } from "@/lib/features/f07_arabic_and_english_interface";

type Screen = "overview" | "enquiry" | "activity" | "access";
const NAV = [
  { id: "overview", label: "Overview", icon: LayoutDashboard },
  { id: "enquiry", label: "Enquiries", icon: MessageSquare },
  { id: "activity", label: "Specialist activity", icon: Workflow },
  { id: "access", label: "Access & controls", icon: ShieldCheck },
] as const;
const SPECIALISTS = [
  { name: "Intake", detail: "Understands Arabic and English requests", icon: MessageSquare },
  { name: "Identification", detail: "Checks model, serial and configuration", icon: Fingerprint },
  { name: "Parts", detail: "Retrieves compatible catalogue evidence", icon: Database },
  { name: "Reply", detail: "Drafts a response for your approval", icon: Bot },
];

/** One anonymous identity; navigation never grants staff authority. */
export function LiveDemo(): JSX.Element {
  const [ready, setReady] = useState(false);
  const [role, setRole] = useState<Role>("customer");
  const [screen, setScreen] = useState<Screen>("enquiry");
  const [enquiryId, setEnquiryId] = useState<string | null>(null);
  const [openReview, setOpenReview] = useState<string | null>(null);
  // The site header (which normally hosts the EN/AR control) is hidden on this full-screen
  // workspace, so the console carries its own locale control, seeded from the server-set <html lang>.
  const [locale, setLocale] = useState<Locale | null>(null);
  useEffect(() => {
    ensureDemoToken();
    // eslint-disable-next-line react-hooks/set-state-in-effect -- <html lang> and sessionStorage are browser-only; read once after hydration so SSR stays deterministic
    setLocale(document.documentElement.lang === "ar" ? "ar" : "en");
    try { setEnquiryId(sessionStorage.getItem("pq-active-enquiry")); } catch { /* storage optional */ }
    const sync = () => {
      const value = new URLSearchParams(window.location.search).get("view");
      setScreen(NAV.some(n => n.id === value) ? value as Screen : "enquiry");
    };
    sync(); setReady(true);
    window.addEventListener("popstate", sync);
    return () => window.removeEventListener("popstate", sync);
  }, []);
  function navigate(next: Screen) {
    setScreen(next);
    // Skip duplicate history entries so Back always leaves the current screen.
    if (new URLSearchParams(window.location.search).get("view") !== next) {
      window.history.pushState(null, "", `?view=${next}`);
    }
  }
  function remember(id: string) {
    setEnquiryId(id);
    try { sessionStorage.setItem("pq-active-enquiry", id); } catch { /* storage optional */ }
  }
  function newEnquiry() {
    setEnquiryId(null); setRole("customer"); setOpenReview(null); navigate("enquiry");
    try { sessionStorage.removeItem("pq-active-enquiry"); } catch { /* storage optional */ }
  }
  return <div className="pq-console">
    <a className="pq-skip-link" href="#pq-console-content">Skip to workspace content</a>
    <aside className="pq-console-rail">
      <Link href="/" className="pq-console-brand" aria-label="PartsIQ home"><BrandLogo compact /><span className="pq-console-beta">WORKSPACE</span></Link>
      <div className="pq-console-org"><span className="pq-console-avatar">P</span><div><strong>Demo workspace</strong><small>Independent portfolio project</small></div></div>
      <p className="pq-console-label">WORKSPACE</p>
      <nav aria-label="Workspace">{NAV.map(({id,label,icon:Icon}) => <button key={id} aria-current={screen === id ? "page" : undefined} onClick={() => navigate(id)}><Icon size={18}/>{label}{screen === id && <ChevronRight size={15}/>}</button>)}</nav>
      <p className="pq-console-label">EXPLORE</p>
      <nav aria-label="Resources"><Link href="/demo"><GitBranch size={18}/>Guided scenarios<ArrowUpRight size={14}/></Link><a href="/architecture"><CircleHelp size={18}/>Architecture<ArrowUpRight size={14}/></a><a href="/login"><ShieldCheck size={18}/>Staff sign in<ArrowUpRight size={14}/></a></nav>
      <div className="pq-console-rail-note"><ShieldCheck size={20}/><strong>You have the final say.</strong><p>Recommendations stay in review until a human approves.</p></div>
      <Link href="/" className="pq-console-back"><ArrowLeft size={15}/> Back to website</Link>
    </aside>
    <div className="pq-console-main">
      <header className="pq-console-top"><span>Workspace <ChevronRight size={14}/> <strong>{NAV.find(n => n.id === screen)?.label}</strong></span><div><span className="pq-console-status"><Radio size={13}/>Synthetic demo</span>{locale && <LocaleControl initial={locale}/>}<ThemeControl/></div></header>
      <div className="pq-console-content" id="pq-console-content" tabIndex={-1}>
        <div className="pq-console-heading"><div><span className="pq-console-kicker">PARTS INTELLIGENCE / HUMAN CONTROL</span><h1>{screen === "overview" ? "Your operations, in focus." : screen === "activity" ? "Follow the evidence." : screen === "access" ? "Clear roles. Clear boundaries." : role === "reviewer" ? "The decision is yours." : "Find the right part."}</h1><p>{screen === "enquiry" ? "From a customer request to a verified recommendation, in one workspace." : "A transparent view of the people, specialists and checks behind each enquiry."}</p></div><button className="pq-btn pq-btn-primary" onClick={newEnquiry}><Plus size={17}/>New enquiry</button></div>
        <div className="pq-console-mode"><div><Workflow size={19}/><strong>Guided workflow</strong><span>Code coordinates · specialists assist · you approve</span></div><span className="pq-console-pill">Available</span></div>
        {!ready ? <p data-testid="session-loading">Starting your demo session…</p> : screen === "enquiry" ? <>
          <div className="pq-console-toolbar"><RoleSwitch role={role} onChange={next => {setRole(next); if(next === "customer") setOpenReview(null);}}/><span>Views share your own demo session</span></div>
          <div className="pq-console-grid"><div>{role === "customer" ? <CustomerLive enquiryId={enquiryId} onCreated={remember}/> : openReview ? <ReviewWorkspaceLive enquiryId={openReview} onBack={() => setOpenReview(null)}/> : <ReviewerInbox onOpen={id => {setOpenReview(id); remember(id);}}/>}</div><aside className="pq-console-context"><div className="pq-console-card"><span className="pq-console-kicker">HOW IT WORKS</span><h2>A team behind every request</h2>{SPECIALISTS.map(({name,detail,icon:Icon},i)=><div className="pq-console-specialist" key={name}><span><Icon size={18}/></span><div><strong>{name}</strong><p>{detail}</p></div><small>0{i+1}</small></div>)}<div className="pq-console-gate"><CheckCheck size={18}/><span>Verification gate<strong>Then human approval</strong></span></div></div><div className="pq-console-note"><CircleHelp size={16}/><p>This demo uses synthetic catalogue data and fixture responses. No live AI calls are claimed.</p></div></aside></div>
        </> : screen === "activity" ? <>{enquiryId ? <SpecialistTimeline enquiryId={enquiryId}/> : <div className="pq-console-empty"><Workflow size={36}/><h2>Every run leaves a trail.</h2><p>Create an enquiry to see its recorded specialist stages and outcomes.</p><button className="pq-btn pq-btn-primary" onClick={()=>navigate("enquiry")}>Open enquiries<ArrowUpRight size={16}/></button></div>}</> : screen === "overview" ? <>
          <div className="pq-console-overview"><div className="pq-console-feature"><span className="pq-console-kicker">FROM REQUEST TO RESOLUTION</span><h2>Less searching.<br/>More certainty.</h2><p>Describe the machine and the part. Inspect the evidence. Review the response before it reaches the customer.</p><button className="pq-btn pq-btn-primary" onClick={()=>navigate("enquiry")}>Open workspace<ArrowUpRight size={17}/></button></div><div className="pq-console-card"><h2>Your active enquiry</h2><p>{enquiryId ? "An enquiry is saved in this browser session." : "No active enquiry yet. Start with a part request."}</p>{enquiryId && <code className="pq-console-id">{enquiryId}</code>}<button className="pq-btn pq-btn-ghost" onClick={()=>navigate("activity")}>View activity<ChevronRight size={16}/></button></div></div>
          <div className="pq-console-card"><div className="pq-console-section-title"><Bot size={22}/><h2>Agent collaboration</h2><span className="pq-console-pill">Not connected</span></div><p>The current engine runs a fixed specialist workflow. Agent-to-agent requests, user pause/resume and delegated tasks need a separate backend contract. This workspace does not simulate that capability or label fixture events as agent conversations.</p></div>
        </> : <div className="pq-console-card"><h2>Access model</h2><p>Switching demo views changes the presentation only. The API checks access on each request.</p><div className="pq-scroll-x"><table className="pq-console-table"><thead><tr><th>Identity</th><th>Scope</th><th>Allowed work</th></tr></thead><tbody><tr><td>Demo visitor</td><td>Own active session</td><td>Create, inspect and review synthetic enquiries</td></tr><tr><td>Customer</td><td>Own enquiries</td><td>Submit requests and answer clarification</td></tr><tr><td>Assigned staff</td><td>Assigned enquiries</td><td>Inspect evidence and approve or reject</td></tr><tr><td>Administrator</td><td>Authorized administration</td><td>Assignment, catalogue and evaluation controls</td></tr></tbody></table></div><a className="pq-btn pq-btn-ghost" href="/login"><ClipboardCheck size={17}/>Sign in with a staff account</a></div>}
        <footer className="pq-console-foot"><span>PARTSIQ / INDEPENDENT SYNTHETIC DEMONSTRATION</span><span>Compatibility checked in code. Approval stays human.</span></footer>
      </div>
    </div>
  </div>;
}
