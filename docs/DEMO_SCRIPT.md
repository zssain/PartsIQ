# PartsIQ — demo walkthrough scripts

Two scripts for walking a recruiter through the product on the hosted demo (or a local run). All
data is **synthetic** — fabricated brands, models and part numbers. No video exists yet; record
one with [docs/RECORDING_CHECKLIST.md](RECORDING_CHECKLIST.md) and only then link it.

Every path uses the four seed-42 demo scenarios and ends by showing that a human must approve
before anything is published.

---

## 3-minute script (the essentials)

1. **0:00 — Framing (20s).** "PartsIQ turns a messy spare-parts enquiry into an approved,
   bilingual reply. The model reads and writes language; the database and code decide facts.
   Everything here is synthetic."
2. **0:20 — Happy path (50s).** Start the demo, pick the mixed-language photo scenario. Show the
   machine identified, only catalogue-compatible parts retrieved, and a drafted reply.
3. **1:10 — A refusal (40s).** Open the incompatibility scenario. Show the requested part being
   **refused with evidence** rather than a guess — this is the compatibility gate.
4. **1:50 — Human review (50s).** Switch to the staff workspace. Show the verification results,
   the match score (never a probability), then **approve** the current revision.
5. **2:40 — Reset (20s).** Run the demo reset to show isolation, and note failure handling: a
   dependency outage surfaces a typed error, never a fabricated answer.

Caption track (3-min): one caption per step above, each naming the guarantee being shown
(compatibility gate, evidence, human approval, reset/isolation).

---

## 8-minute script (the full tour)

1. **0:00 — Framing + architecture (60s).** The four services (gateway, search, orchestrator,
   worker) and the web app; the deterministic verification gate; read-only specialist tools.
2. **1:00 — Happy path (90s).** Mixed-language photo scenario: nameplate OCR, the mandatory OCR
   confirmation step, machine identification, compatible-set retrieval, bilingual draft.
3. **2:30 — Missing serial (60s).** Missing-serial scenario: the system asks a **clarifying
   question** instead of guessing; show the conversation stays in the customer's language.
4. **3:30 — Incompatibility (60s).** Incompatible-number scenario: the part is **refused with a
   version-specific citation**; open the evidence viewer on the exact cited page.
5. **4:30 — Stock split (75s).** Local-shortage scenario: fulfilment is **planned across
   warehouses**; a shortfall is shown as a back-order, not hidden; transfer times are labelled
   non-guaranteed estimates.
6. **5:45 — Human review (90s).** Staff workspace: assignment, internal notes (staff-only),
   overdue indicator, stock-freshness re-check, then **approve** — show the approved PDF export.
7. **7:15 — Failure handling + reset (45s).** Trigger a recoverable failure (e.g. provider
   unavailable) to show a typed error and preserved input; then run the demo reset and show prior
   session data is gone (isolation).

Caption track (8-min): a caption per step, plus on-screen labels for "synthetic data", "match
score — not a probability", and "human approval required".

---

## Notes for the presenter

- Show both English and Arabic (RTL) at least once; identifiers stay LTR-isolated.
- Keep secrets off screen; the demo uses only public, synthetic values.
- Do **not** announce a recording until one is actually captured and its link verified.
