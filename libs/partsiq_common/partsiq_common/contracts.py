"""Executable contract specification copied by foundation 01; no provider or database side effects."""
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field

class Contract(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)

Locale = Literal['en', 'ar']
class AccessAction(StrEnum):
    READ='read'
    REVIEW='review'
    ASSIGN='assign'
    IMPORT='import'
class ActorContext(Contract):
    user_id: UUID
    request_id: UUID
    roles: list[Literal['reviewer','catalogue_admin','admin']]
    session_id: UUID | None = None
    session_generation: int | None = None
class DemoSession(Contract):
    id: UUID
    generation: int = Field(ge=1)
    expires_at: datetime
class ItemInput(Contract):
    description: str = Field(min_length=1,max_length=1000)
    quantity: Decimal | None = Field(default=None,gt=0,le=100000)
    model_text: str | None = None
    serial_text: str | None = None
    source_message_id: UUID
    source_start: int = Field(ge=0)
    source_end: int = Field(ge=0)
class IntakeResult(Contract):
    language: Literal['en','ar','mixed']
    preferred_locale: Locale
    urgency: Literal['normal','urgent']
    items: list[ItemInput] = Field(min_length=1,max_length=20)
class EnquiryCreate(Contract):
    text: str = Field(min_length=1,max_length=12000)
    locale: Locale
    destination_warehouse_id: int = Field(gt=0)
    session_id: UUID | None = None
class MessageCreate(Contract):
    text: str = Field(min_length=1,max_length=12000)
    expected_revision: int = Field(ge=1)
    item_id: UUID | None = None
class MessageView(Contract):
    id: UUID
    enquiry_id: UUID
    revision: int
    kind: Literal['customer','clarification','status','recommendation']
    body: str
    created_at: datetime
class EnquiryView(Contract):
    id: UUID
    revision: int
    status: Literal['received','processing','needs_information','awaiting_review','approved','rejected','failed']
    messages: list[MessageView]
    item_ids: list[UUID]
    catalogue_version_id: UUID | None
    updated_at: datetime
class UploadRequest(Contract):
    enquiry_id: UUID
    expected_revision: int = Field(ge=1)
    media_type: Literal['image/jpeg','image/png','image/webp']
    size_bytes: int = Field(gt=0,le=10485760)
class UploadTicket(Contract):
    attachment_id: UUID
    upload_url: str
    expires_at: datetime
class AttachmentView(Contract):
    id: UUID
    status: Literal['pending','validated','rejected','deleted']
    error_code: str | None = None
class DownloadRequest(Contract):
    actor: ActorContext
    resource_type: Literal['evidence','export','attachment']
    resource_id: UUID
class DownloadTicket(Contract):
    url: str
    expires_at: datetime
class ImageInfo(Contract):
    width: int = Field(gt=0,le=12000)
    height: int = Field(gt=0,le=12000)
    media_type: str
    sha256: str = Field(pattern='^[a-f0-9]{64}$')
class NameplateResult(Contract):
    attachment_id: UUID
    model_text: str | None
    serial_text: str | None
    issues: list[Literal['unreadable','blur','low_resolution','glare','partial_plate']]
    confirmation_required: Literal[True] = True
class ConfirmExtraction(Contract):
    extraction_id: UUID
    expected_revision: int = Field(ge=1)
    model_text: str = Field(min_length=1,max_length=120)
    serial_text: str = Field(min_length=1,max_length=120)
class Allocation(Contract):
    warehouse_id: int = Field(gt=0)
    quantity: Decimal = Field(gt=0)
    transfer_days: int = Field(ge=0,le=60)
    stock_updated_at: datetime
class VerifiedItem(Contract):
    item_id: UUID
    configuration_id: int
    part_id: int
    part_number: str
    name_en: str
    name_ar: str
    requested_quantity: Decimal = Field(gt=0)
    allocations: list[Allocation]
    shortage: Decimal = Field(ge=0)
    source_reference: str
    evidence_id: UUID
class VerifiedFacts(Contract):
    enquiry_id: UUID
    revision: int
    catalogue_version_id: UUID
    items: list[VerifiedItem] = Field(min_length=1,max_length=20)
class CandidateEvidence(Contract):
    item_id: UUID
    part_id: int
    configuration_id: int
    evidence_id: UUID
    source_reference: str
class StockEvidence(Contract):
    part_id: int
    warehouse_id: int
    available: Decimal = Field(ge=0)
    updated_at: datetime
class VerificationEvidence(Contract):
    current_revision: int
    active_catalogue_version_id: UUID
    candidates: list[CandidateEvidence]
    stock: list[StockEvidence]
class VerificationFailure(Contract):
    code: Literal['STALE_REVISION','STALE_CATALOGUE','INCOMPATIBLE','MISSING_EVIDENCE','INVALID_QUANTITY','OVERALLOCATION','STALE_STOCK','UNRESOLVED_ITEM','UNSAFE_PROSE']
    item_id: UUID | None
    detail: str
class VerificationResult(Contract):
    passed: bool
    failures: list[VerificationFailure]
    facts_sha256: str
class ReplySlots(Contract):
    greeting: str = Field(max_length=200)
    explanation: str = Field(max_length=1500)
    closing: str = Field(max_length=300)
class ApprovalRequest(Contract):
    enquiry_id: UUID
    expected_revision: int = Field(ge=1)
    draft_id: UUID
    edited_slots: ReplySlots | None = None
class RejectionRequest(Contract):
    enquiry_id: UUID
    expected_revision: int = Field(ge=1)
    reason: str = Field(min_length=1,max_length=1000)
class ApprovalResult(Contract):
    decision_id: UUID
    message_id: UUID
    revision: int
    already_applied: bool
class ReviewResult(Contract):
    decision_id: UUID
    revision: int
    status: Literal['approved','rejected']
class ItemCorrection(Contract):
    item_id: UUID
    description: str | None = None
    quantity: Decimal | None = Field(default=None,gt=0,le=100000)
    model_text: str | None = None
    serial_text: str | None = None
class RevisionRequest(Contract):
    enquiry_id: UUID
    expected_revision: int
    corrections: list[ItemCorrection] = Field(min_length=1,max_length=20)
    reason: str = Field(min_length=1,max_length=1000)
class JobLease(Contract):
    id: UUID
    kind: Literal['nameplate','export_pdf','catalog_import','catalog_publish','storage_cleanup']
    enquiry_id: UUID | None
    revision: int | None
    session_generation: int | None
    lease_token: UUID
    expires_at: datetime
    attempt: int
    payload: dict[str,str | int | bool | None]
class JobResult(Contract):
    status: Literal['succeeded','failed','cancelled']
    result_id: UUID | None
    error_code: str | None
class ExportRequest(Contract):
    enquiry_id: UUID
    revision: int
    decision_id: UUID
class ExportResult(Contract):
    export_id: UUID
    storage_key: str
    sha256: str
class ApprovedSnapshot(Contract):
    decision_id: UUID
    approved_at: datetime
    locale: Locale
    facts: VerifiedFacts
    reply: str
    synthetic: bool
class AuditEvent(Contract):
    actor_type: Literal['system','ai','user']
    actor_id: str
    action: str
    entity_type: str
    entity_id: str
    request_id: UUID
    enquiry_id: UUID | None
    revision: int | None
    payload: dict[str,str | int | bool | None]
class AIRequest(Contract):
    request_key: UUID
    enquiry_id: UUID | None
    stage: Literal['intake','nameplate','parts','reply','summary']
    model: str
    trusted_instructions: str
    untrusted_text: str
    image_base64: str | None = None
    output_schema_name: Literal['IntakeResult','NameplateResult','PartsProposal','ReplySlots','SummaryResult']
    max_output_tokens: int = Field(ge=1,le=2048)
class AIResult(Contract):
    output_json: str
    input_tokens: int
    output_tokens: int
    provider_request_id: str
class BudgetReservation(Contract):
    id: UUID
    account_id: str
    reserved_usd: Decimal
class CreditAllowance(Contract):
    amount_usd: Decimal = Field(ge=0)
    expires_at: datetime
    paid_budget_usd: Decimal = Field(ge=0,le=0)
class ItemState(Contract):
    id: UUID
    request: ItemInput
    configuration_id: int | None
    candidate_part_ids: list[int]
    selected_part_id: int | None
    status: Literal['unresolved','needs_information','ready','unavailable']
class EnquiryState(Contract):
    enquiry_id: UUID
    revision: int
    session_generation: int | None
    catalogue_version_id: UUID | None
    items: list[ItemState]
    step_count: int = Field(ge=0)
    pending_question: str | None
    draft_id: UUID | None
    verification_id: UUID | None
    phase: str
class ToolContext(Contract):
    enquiry_id: UUID
    revision: int
    catalogue_version_id: UUID
    item_id: UUID
    max_calls: int = Field(ge=0,le=4)
class PartsProposal(Contract):
    explanation: str
    clarification_code: Literal['needs_serial','needs_model','ambiguous_part','mismatch','none']
    candidate_part_ids: list[int]
class SummaryResult(Contract):
    summary: str = Field(max_length=2000)
    source_message_ids: list[UUID]
class MetricsQuery(Contract):
    start: datetime
    end: datetime
    include_demo: bool = False
class MetricsView(Contract):
    enquiry_count: int
    approved_count: int
    clarification_count: int
    evaluated_count: int
    correct_count: int
    median_review_seconds: float | None
    p95_latency_ms: float | None
    estimated_cost_usd: Decimal
class ReviewView(Contract):
    enquiry: EnquiryView
    facts: VerifiedFacts | None
    draft: ReplySlots | None
    verification: VerificationResult | None
    assigned_to: UUID | None
class DemoScenario(Contract):
    id: Literal['mixed_photo','missing_serial','incompatible_number','local_shortage']
    text: str
    attachment_path: str | None
    expected_status: str
    expected_configuration_id: int | None
    expected_part_ids: list[int]
class WorkflowStep(StrEnum):
    INTAKE='intake'
    AWAIT_OCR='await_ocr'
    CONFIRM='confirm'
    IDENTIFY='identify'
    CLARIFY='clarify'
    SEARCH='search'
    CHOOSE='choose'
    PLAN='plan'
    DRAFT='draft'
    VERIFY='verify'
    REVIEW='review'
    COMPLETE='complete'
    NEEDS_STAFF='needs_staff'
class EmbeddingReceipt(Contract):
    version_id: UUID
    embedded_count: int
    model_revision: str
class EventOutcome(Contract):
    event_id: UUID
    state: Literal['processed','obsolete','retry','failed']
class EvalCase(Contract):
    id: str
    scenario: str
    input_text: str
    expected_status: str
    expected_part_ids: list[int]
class EvalOutput(Contract):
    status: str
    part_ids: list[int]
    clarification_code: str | None
class EvalResult(Contract):
    case_id: str
    passed: bool
    actual: EvalOutput
class EvalRun(Contract):
    id: UUID
    dataset_sha256: str
    results: list[EvalResult]
class SchemaReceipt(Contract):
    postgres_version: str
    extensions: dict[str,str]
    columns: dict[str,list[str]]
    indexes: dict[str,list[str]]
    policies: dict[str,list[str]]
class TestConfig(Contract):
    app_env: Literal['local','test']
    database_url: str
    production_project_ref: str
class ReadinessReport(Contract):
    database: bool
    redis: bool
    search_lexical: bool
    search_semantic: bool
    ai_credit_enabled: bool
    storage: bool
class AccountReceipt(Contract):
    account_id: str
    plan: Literal['free']
    region: str
    credit_usd: Decimal
    expires_at: datetime
class SizingReceipt(Contract):
    instance_type: str
    peak_memory_mib: int
    instance_memory_mib: int
    measured_at: datetime
class DeploymentDecision(Contract):
    allowed: bool
    reasons: list[str]
class HostedReceipt(Contract):
    base_url: str
    api_url: str
    scenarios_passed: list[str]
    scenarios_failed: list[str]
    checked_at: datetime
