"use client";

import { useEffect, useState, type JSX } from "react";

import { ensureDemoToken } from "@/lib/live";
import { FixtureBanner } from "@/components/visibility/FixtureBanner";
import { RoleSwitch, type Role } from "@/components/live/RoleSwitch";
import { CustomerLive } from "@/components/live/CustomerLive";
import { ReviewerInbox } from "@/components/live/ReviewerInbox";
import { ReviewWorkspaceLive } from "@/components/live/ReviewWorkspaceLive";

// LIVE demo orchestrator (F03 role switch + F04 isolation). ONE anonymous session: a single
// X-Demo-Token is generated once (crypto.randomUUID) and persisted in sessionStorage, registered
// via ensureDemoToken() on mount so every api<T> call carries it. Role switching is PURELY
// presentational — the same session toggles between the Customer view and the Reviewer view; the
// reviewer sees ONLY this session's own enquiries (scope enforced server-side). The FixtureBanner
// stays visible so the synthetic mode is never mistaken for a live one.
export function LiveDemo(): JSX.Element {
  const [ready, setReady] = useState(false);
  const [role, setRole] = useState<Role>("customer");
  // The one live enquiry this session created (null until the customer submits one).
  const [enquiryId, setEnquiryId] = useState<string | null>(null);
  // The enquiry the reviewer currently has open (null = show the inbox list).
  const [openReview, setOpenReview] = useState<string | null>(null);

  useEffect(() => {
    ensureDemoToken();
    setReady(true);
  }, []);

  return (
    <div style={{ display: "grid", gap: 20 }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
        <RoleSwitch
          role={role}
          onChange={(next) => {
            setRole(next);
            if (next === "customer") setOpenReview(null);
          }}
        />
        <FixtureBanner />
      </div>

      {!ready ? (
        <section className="pq-card">
          <p data-testid="session-loading">Starting your demo session…</p>
        </section>
      ) : role === "customer" ? (
        <CustomerLive enquiryId={enquiryId} onCreated={setEnquiryId} />
      ) : openReview ? (
        <ReviewWorkspaceLive enquiryId={openReview} onBack={() => setOpenReview(null)} />
      ) : (
        <ReviewerInbox onOpen={setOpenReview} />
      )}
    </div>
  );
}
