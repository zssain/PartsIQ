// Offline demo engine. Produces deterministic, auditable walkthroughs for the four seed-42
// synthetic scenarios — the same outcomes the real pipeline would reach — so the UI is fully
// functional without a backend. Facts (part numbers, stock, citations) come from the exported
// seed slice (lib/demo/seed.json), never invented in the browser.

import seed from "./seed.json";

type Seed = {
  model: { brand: string; model_code: string; display_name: string; rated_output: string;
    configurations: { config_code: string; description: string; serial_start: number; serial_end: number }[] };
  air_filter: { part_number: string; name_en: string; name_ar: string; category: string; description_en: string };
  incompatible: { part_number: string; name_en: string; name_ar: string; category: string; description_en: string };
  stock: { warehouse: string; on_hand: number; reserved: number }[];
  compatibility: { part_number: string; brand: string; model_code: string; config_code: string; source_reference: string }[];
  warehouses: { code: string; name: string; region: string }[];
  transfer_routes: { from_code: string; to_code: string; transfer_days: number }[];
};
export const SEED = seed as Seed;

export type Outcome = "awaiting_review" | "needs_information" | "rejected";
export interface ChatMsg { role: "customer" | "system"; text: string; lang?: "en" | "ar" | "mixed"; note?: string }
export interface Candidate {
  part_number: string; name_en: string; name_ar: string; score: number; compatible: boolean;
  reason: string; source_reference: string | null; config: string | null;
}
export interface Allocation { warehouse: string; name: string; qty: number; available: number; transfer_days: number }
export interface Check { name: string; passed: boolean; detail: string }
export interface Scenario {
  id: string; title: string; icon: string; blurb: string; tags: string[];
  chat: ChatMsg[]; needsOcr: boolean;
  machine: { display_name: string; config: string | null };
  candidates: Candidate[];
  plan: { requested: number; allocations: Allocation[]; shortage: number } | null;
  checks: Check[];
  reply: { en: string; ar: string } | null;
  clarification: string | null;
  outcome: Outcome;
}

const CITATION = SEED.compatibility[0]?.source_reference ?? "SYNTH-CA-PB-CA-110 rev 1, section FILTERS";
const JED = SEED.stock.find((s) => s.warehouse === "JED")!;
const netJED = JED.on_hand - JED.reserved; // 41
const whName = (code: string) => SEED.warehouses.find((w) => w.code === code)?.name ?? code;
const route = (code: string) => SEED.transfer_routes.find((r) => r.to_code === code)?.transfer_days ?? 0;

const AF = SEED.air_filter;
const BAD = SEED.incompatible;

function okChecks(extra: Check[] = []): Check[] {
  return [
    { name: "current_revision", passed: true, detail: "plan matches the current enquiry revision" },
    { name: "catalogue_version", passed: true, detail: "built against the active catalogue version" },
    { name: "candidate_membership", passed: true, detail: "chosen part is a surfaced compatible candidate" },
    { name: "configuration_membership", passed: true, detail: `compatible under ${SEED.model.model_code} (A)` },
    { name: "source_evidence", passed: true, detail: CITATION },
    ...extra,
  ];
}

export const SCENARIOS: Scenario[] = [
  {
    id: "mixed_photo",
    title: "Mixed-language photo",
    icon: "📸",
    blurb: "Arabic/English enquiry with a nameplate photo → OCR confirmation → compatible part.",
    tags: ["bilingual", "OCR", "happy path"],
    needsOcr: true,
    chat: [
      { role: "customer", lang: "mixed", text: "محتاج هذا الجزء CA-AF-8973 for my Corvane Air CA-110 — see photo / شوف الصورة" },
      { role: "system", lang: "en", text: "Reading the nameplate photo… please confirm the extracted model and serial.", note: "nameplate OCR" },
      { role: "system", lang: "en", text: `Confirmed: ${SEED.model.model_code}, serial 800000 → configuration A.` },
    ],
    machine: { display_name: SEED.model.display_name, config: "A" },
    candidates: [
      { part_number: AF.part_number, name_en: AF.name_en, name_ar: AF.name_ar, score: 0.96, compatible: true,
        reason: "exact part-number match · compatible under CA-110 (A)", source_reference: CITATION, config: "A" },
    ],
    plan: { requested: 2, allocations: [{ warehouse: "JED", name: whName("JED"), qty: 2, available: netJED, transfer_days: 0 }], shortage: 0 },
    checks: okChecks([
      { name: "quantity", passed: true, detail: "requested 2 · allocated 2 · shortage 0" },
      { name: "allocation", passed: true, detail: `2 ≤ ${netJED} available at Jeddah` },
    ]),
    reply: {
      en: `Your ${AF.name_en} (${AF.part_number}) fits ${SEED.model.model_code} (A). 2 units are available in Jeddah now. A reviewer will confirm before this is sent.`,
      ar: `فلتر الهواء (${AF.part_number}) متوافق مع ${SEED.model.model_code} (A). يوجد قطعتان في جدة الآن. سيؤكد المراجع قبل الإرسال.`,
    },
    clarification: null,
    outcome: "awaiting_review",
  },
  {
    id: "missing_serial",
    title: "Missing serial",
    icon: "❓",
    blurb: "A hydraulic filter request with no serial → the system asks, it never guesses.",
    tags: ["clarify", "no guessing"],
    needsOcr: false,
    chat: [
      { role: "customer", lang: "en", text: "I need a hydraulic filter for a Corvane Air CA-110." },
      { role: "system", lang: "en", text: "The CA-110 has two configurations (A/B) with different filters. What is the serial number, or which configuration?" },
    ],
    machine: { display_name: SEED.model.display_name, config: null },
    candidates: [],
    plan: null,
    checks: [
      { name: "current_revision", passed: true, detail: "revision current" },
      { name: "catalogue_version", passed: true, detail: "active catalogue version" },
      { name: "configuration_membership", passed: false, detail: "configuration not yet identified — serial required" },
    ],
    reply: null,
    clarification: "Serial number (or configuration A/B) is required before a compatible filter can be recommended.",
    outcome: "needs_information",
  },
  {
    id: "incompatible_number",
    title: "Incompatible part number",
    icon: "🚫",
    blurb: "A requested part that does not fit → refused with a version-specific citation.",
    tags: ["compatibility gate", "evidence"],
    needsOcr: false,
    chat: [
      { role: "customer", lang: "en", text: `Does part ${BAD.part_number} fit my Corvane Air CA-110 (A)?` },
      { role: "system", lang: "en", text: `${BAD.part_number} is a ${BAD.name_en} for frame S — it is NOT compatible with ${SEED.model.model_code} (A).` },
    ],
    machine: { display_name: SEED.model.display_name, config: "A" },
    candidates: [
      { part_number: BAD.part_number, name_en: BAD.name_en, name_ar: BAD.name_ar, score: 0.0, compatible: false,
        reason: "frame S element — not listed for CA-110 (A)", source_reference: null, config: "S" },
      { part_number: AF.part_number, name_en: AF.name_en, name_ar: AF.name_ar, score: 0.94, compatible: true,
        reason: "the compatible alternative for CA-110 (A)", source_reference: CITATION, config: "A" },
    ],
    plan: null,
    checks: [
      { name: "current_revision", passed: true, detail: "revision current" },
      { name: "catalogue_version", passed: true, detail: "active catalogue version" },
      { name: "configuration_membership", passed: false, detail: `${BAD.part_number} is not compatible under CA-110 (A)` },
      { name: "source_evidence", passed: true, detail: CITATION },
    ],
    reply: null,
    clarification: `${BAD.part_number} does not fit CA-110 (A). The compatible air filter is ${AF.part_number} — confirm to proceed.`,
    outcome: "needs_information",
  },
  {
    id: "local_shortage",
    title: "Local stock shortage",
    icon: "📦",
    blurb: "Urgent Jeddah delivery for more than local stock → split + honest back-order.",
    tags: ["fulfilment", "shortfall shown"],
    needsOcr: false,
    chat: [
      { role: "customer", lang: "en", text: `Need 50× ${AF.part_number} for Corvane Air CA-110 delivered to Jeddah urgently.` },
      { role: "system", lang: "en", text: `${AF.part_number} is compatible. Jeddah has ${netJED} available; the rest is back-ordered (not hidden).` },
    ],
    machine: { display_name: SEED.model.display_name, config: "A" },
    candidates: [
      { part_number: AF.part_number, name_en: AF.name_en, name_ar: AF.name_ar, score: 0.96, compatible: true,
        reason: "exact part-number match · compatible under CA-110 (A)", source_reference: CITATION, config: "A" },
    ],
    plan: {
      requested: 50,
      allocations: [
        { warehouse: "JED", name: whName("JED"), qty: netJED, available: netJED, transfer_days: 0 },
      ],
      shortage: 50 - netJED,
    },
    checks: okChecks([
      { name: "quantity", passed: true, detail: `requested 50 · allocated ${netJED} · shortage ${50 - netJED}` },
      { name: "allocation", passed: true, detail: `${netJED} ≤ ${netJED} available at Jeddah; remainder back-ordered` },
    ]),
    reply: {
      en: `${netJED} units of ${AF.part_number} are available in Jeddah now; the remaining ${50 - netJED} will follow as a back-order. Transfer estimates are not guaranteed. A reviewer will confirm.`,
      ar: `يتوفر ${netJED} قطعة من ${AF.part_number} في جدة الآن، والباقي ${50 - netJED} سيتم تحويله لاحقًا. مدد التحويل تقديرية غير مضمونة. سيؤكد المراجع.`,
    },
    clarification: null,
    outcome: "awaiting_review",
  },
];

export function getScenario(id: string): Scenario | undefined {
  return SCENARIOS.find((s) => s.id === id);
}

export { route, netJED };
