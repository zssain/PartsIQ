"use client";

import { use, useCallback, useState, type JSX } from "react";

import { ApiError } from "@/lib/api";
import { StockFreshness } from "@/components/features/StockFreshness";
import { EvidenceViewer } from "@/components/features/EvidenceViewer";
import { CandidateComparison } from "@/components/features/CandidateComparison";
import { CorrectionEditor } from "@/components/features/CorrectionEditor";
import { AssignmentControl } from "@/components/features/AssignmentControl";
import { InternalNotes } from "@/components/features/InternalNotes";
import { Workspace } from "@/components/review/Workspace";
import { assignEnquiry, type F42Request, type F42Result } from "@/lib/features/f42_assignments";
import { appendNote, type F41Request, type F41Result } from "@/lib/features/f41_internal_notes";
import type { F31Request, F31Result } from "@/lib/features/f31_candidate_comparison";
import { correctExtraction, type F38Request, type F38Result } from "@/lib/features/f38_correct_extracted_details";
import type { F35Request, F35Result } from "@/lib/features/f35_stock_freshness";
import { openEvidence, type F29Request, type F29Result } from "@/lib/features/f29_evidence_page_viewer";

// F35: the reviewer can re-check stock freshness for the enquiry under review. The freshness
// verdict is computed server-side (gateway attaches the verified facts and calls the search
// /internal/stock/check route); the live call is BLOCKED here, so the panel stays empty rather
// than fabricate a fresh/stale result.
export default function StaffEnquiryPage({
  params,
}: {
  params: Promise<{ id: string }>;
}): JSX.Element {
  const { id } = use(params);
  const [freshness, setFreshness] = useState<F35Result | null>(null);
  const [error, setError] = useState<ApiError | null>(null);

  const recheck = useCallback(async (_request: F35Request) => {
    setError(null);
    // Server-side freshness check is wired by the gateway/search owners (BLOCKED here).
    setFreshness(null);
  }, []);

  // F29: open a cited (synthetic) evidence document behind a short-lived signed URL.
  const [evidence, setEvidence] = useState<F29Result | null>(null);
  const [evidenceError, setEvidenceError] = useState<ApiError | null>(null);
  const openCited = useCallback(async (request: F29Request) => {
    setEvidenceError(null);
    try {
      setEvidence(await openEvidence(request));
    } catch (err) {
      setEvidenceError(err instanceof ApiError ? err : null);
    }
  }, []);

  // F31: candidate comparison island. Candidates are loaded by the Workspace from the review;
  // choosing a candidate here would POST its id to the gateway (wired by the review owner).
  const [comparison] = useState<F31Result | null>(null);
  const chooseCandidate = useCallback(async (_request: F31Request) => {
    // Selecting sends the candidate id only; server re-derives facts (BLOCKED here).
  }, []);

  // F38: correct typed extracted details; the server locks + increments + re-runs the pipeline.
  const [correction, setCorrection] = useState<F38Result | null>(null);
  const [correctionError, setCorrectionError] = useState<ApiError | null>(null);
  const applyCorrection = useCallback(async (request: F38Request) => {
    setCorrectionError(null);
    try {
      setCorrection(await correctExtraction(request));
    } catch (err) {
      setCorrectionError(err instanceof ApiError ? err : null);
    }
  }, []);

  // F42: admin assignment control.
  const [assignment, setAssignment] = useState<F42Result | null>(null);
  const [assignmentError, setAssignmentError] = useState<ApiError | null>(null);
  const assign = useCallback(async (request: F42Request) => {
    setAssignmentError(null);
    try {
      setAssignment(await assignEnquiry(request));
    } catch (err) {
      setAssignmentError(err instanceof ApiError ? err : null);
    }
  }, []);

  // F41: append a staff-only internal note.
  const [note, setNote] = useState<F41Result | null>(null);
  const [noteError, setNoteError] = useState<ApiError | null>(null);
  const addNote = useCallback(async (request: F41Request) => {
    setNoteError(null);
    try {
      setNote(await appendNote(request));
    } catch (err) {
      setNoteError(err instanceof ApiError ? err : null);
    }
  }, []);

  return (
    <main>
      <h1>Review enquiry</h1>
      <StockFreshness
        value={freshness}
        loading={false}
        error={error}
        onAction={recheck}
        enquiryId={id}
        expectedRevision={1}
      />
      <EvidenceViewer value={evidence} loading={false} error={evidenceError} onAction={openCited} enquiryId={id} />
      <CandidateComparison value={comparison} loading={false} error={null} onAction={chooseCandidate} />
      <CorrectionEditor value={correction} loading={false} error={correctionError} onAction={applyCorrection} enquiryId={id} />
      <AssignmentControl value={assignment} loading={false} error={assignmentError} onAction={assign} enquiryId={id} />
      <InternalNotes value={note} loading={false} error={noteError} onAction={addNote} enquiryId={id} />
      <Workspace enquiryId={id} />
    </main>
  );
}
