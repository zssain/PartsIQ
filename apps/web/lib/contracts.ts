// TypeScript mirrors of the shared Python contracts (docs/CONTRACTS.md). Field names match
// exactly and optional fields are explicit null, so the wire shape is identical both ways.

export type Locale = "en" | "ar";

export interface DemoSession {
  id: string;
  generation: number;
  expires_at: string;
}

export interface MessageView {
  id: string;
  enquiry_id: string;
  revision: number;
  kind: "customer" | "clarification" | "status" | "recommendation";
  body: string;
  created_at: string;
}

export interface EnquiryView {
  id: string;
  revision: number;
  status: "received" | "processing" | "needs_information" | "awaiting_review" | "approved" | "rejected" | "failed";
  messages: MessageView[];
  item_ids: string[];
  catalogue_version_id: string | null;
  updated_at: string;
}

export interface StockEvidence {
  part_id: number;
  warehouse_id: number;
  available: string;
  updated_at: string;
}

export interface CandidateView {
  item_id: string;
  revision: number;
  part_id: number;
  part_number: string;
  name_en: string;
  name_ar: string;
  score: number;
  reasons: string[];
  source_reference: string;
  evidence_id: string;
  stock: StockEvidence[];
}

export interface ComparisonRow {
  field: string;
  values: (string | null)[];
}

export interface ReplySlots {
  greeting: string;
  explanation: string;
  closing: string;
}

export interface VerificationFailure {
  code: string;
  item_id: string | null;
  detail: string;
}

export interface VerificationResult {
  passed: boolean;
  failures: VerificationFailure[];
  facts_sha256: string;
}

export interface ReviewView {
  enquiry: EnquiryView;
  facts: unknown | null;
  draft: ReplySlots | null;
  verification: VerificationResult | null;
  assigned_to: string | null;
}

export interface NameplateResult {
  attachment_id: string;
  model_text: string | null;
  serial_text: string | null;
  issues: ("unreadable" | "blur" | "low_resolution" | "glare" | "partial_plate")[];
  confirmation_required: true;
}

export interface ConfirmExtraction {
  extraction_id: string;
  expected_revision: number;
  model_text: string;
  serial_text: string;
}
