"""REST contract specification; copy to partsiq.core.api_models during foundation01."""
from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID
from pydantic import BaseModel,Field,ConfigDict
try:
    from .contracts import *
except ImportError:
    from contracts import *

class RevisionOnly(Contract):
    expected_revision:int = Field(ge=1)

class PageQuery(Contract):
    cursor:str | None = None
    limit:int = Field(default=25,ge=1,le=100)

class HistoryQuery(Contract):
    cursor:str | None = None
    limit:int = Field(default=25,ge=1,le=100)
    status:str | None = None

class InboxQuery(Contract):
    cursor:str | None = None
    limit:int = Field(default=25,ge=1,le=100)
    status:str | None = None
    priority:Literal['normal','urgent'] | None = None
    overdue:bool = False
    query:str | None = Field(default=None,max_length=200)

class ScenarioList(Contract):
    items:list[DemoScenario]

class ExtractionView(Contract):
    revision:int
    intake:IntakeResult | None
    nameplate:NameplateResult | None
    confirmed:bool

class MessagePage(Contract):
    items:list[MessageView]
    next_cursor:str | None

class EnquiryPage(Contract):
    items:list[EnquiryView]
    next_cursor:str | None

class QualityView(Contract):
    attachment_id:UUID
    status:Literal['pending','valid','rejected']
    width:int | None
    height:int | None
    warnings:list[str]
    error_code:str | None

class ItemsEdit(Contract):
    expected_revision:int = Field(ge=1)
    items:list[ItemCorrection] = Field(min_length=1,max_length=20)

class ProgressView(Contract):
    enquiry_id:UUID
    revision:int
    step:WorkflowStep
    wait_reason:str | None
    updated_at:datetime

class MachineView(Contract):
    item_id:UUID
    revision:int
    state:Literal['resolved','needs_serial','ambiguous','mismatch','not_found']
    configuration_id:int | None
    model_text:str | None
    serial_text:str | None
    catalogue_version_id:UUID

class MismatchView(Contract):
    item_id:UUID
    revision:int
    mismatch:bool
    reason_code:str | None
    question_en:str | None
    question_ar:str | None

class CompatibilityView(Contract):
    item_id:UUID
    revision:int
    configuration_id:int
    part_ids:list[int]
    catalogue_version_id:UUID

class MatchEvidenceView(Contract):
    item_id:UUID
    revision:int
    normalized_query:str
    matched_aliases:list[str]
    removed_machine_terms:list[str]

class SearchCapabilities(Contract):
    lexical:bool
    semantic:bool
    embedding_model:str | None
    fallback_reason:str | None
    catalogue_source:Literal['snowflake','fixture']
    catalogue_version_id:UUID | None

class CandidateView(Contract):
    part_id:int
    part_number:str
    name_en:str
    name_ar:str
    score:float = Field(ge=0,le=1)
    reasons:list[str]
    source_reference:str
    catalogue_version_id:UUID

class CandidateList(Contract):
    item_id:UUID
    revision:int
    items:list[CandidateView]
    ambiguous:bool
    margin:float | None

class CandidateChoice(Contract):
    expected_revision:int = Field(ge=1)
    part_id:int = Field(gt=0)

class ExplanationView(Contract):
    item_id:UUID
    revision:int
    reasons:list[str]
    source_reference:str | None
    catalogue_version_id:UUID

class ReferenceView(Contract):
    evidence_id:UUID
    source_reference:str
    page_number:int
    synthetic:bool

class ReferenceList(Contract):
    items:list[ReferenceView]
    revision:int

class SupersessionView(Contract):
    requested_number:str
    chain:list[str]
    terminal_number:str | None
    active:bool

class ComparisonQuery(Contract):
    part_ids:list[int] = Field(min_length=2,max_length=3)

class StockRow(Contract):
    warehouse_id:int
    warehouse_name:str
    available:Decimal
    observed_at:datetime

class StockView(Contract):
    item_id:UUID
    revision:int
    part_id:int
    items:list[StockRow]
    snapshot_id:UUID | None
    stale:bool

class PlanView(Contract):
    enquiry_id:UUID
    revision:int
    items:list[VerifiedItem]
    stock_snapshot_id:UUID | None

class TransferRow(Contract):
    source_warehouse_id:int
    destination_warehouse_id:int
    transfer_days:int | None

class TransferView(Contract):
    revision:int
    routes:list[TransferRow]
    estimate_only:Literal[True] = True

class FreshnessView(Contract):
    revision:int
    fresh:bool
    observed_at:datetime | None
    max_age_seconds:int
    reason_code:str | None

class ApprovalState(Contract):
    revision:int
    approved:bool
    decision_id:UUID | None
    facts_sha256:str | None
    invalidated_reason:str | None

class NoteCreate(Contract):
    body:str = Field(min_length=1,max_length=4000)

class NoteView(Contract):
    id:UUID
    author_id:UUID
    body:str
    created_at:datetime

class NotePage(Contract):
    items:list[NoteView]
    next_cursor:str | None

class AssignRequest(Contract):
    expected_revision:int = Field(ge=1)
    assignee_id:UUID | None

class AssignmentView(Contract):
    enquiry_id:UUID
    assigned_to:UUID | None
    changed_at:datetime

class DeadlineView(Contract):
    due_at:datetime | None
    overdue:bool
    server_time:datetime

class SummaryView(Contract):
    revision:int
    summary:SummaryResult | None
    stale:bool

class DraftEdit(Contract):
    expected_revision:int = Field(ge=1)
    slots:ReplySlots

class DraftView(Contract):
    revision:int
    slots:ReplySlots
    rendered_preview:str
    verification_passed:bool

class PublishedView(Contract):
    message:MessageView | None
    decision_id:UUID | None
    approved_revision:int | None

class AuditPage(Contract):
    items:list[AuditEvent]
    next_cursor:str | None

class WorkflowView(Contract):
    enquiry_id:UUID
    revision:int
    step:WorkflowStep
    completed_steps:list[str]
    pending_job_id:UUID | None
    error_code:str | None

class JobView(Contract):
    id:UUID
    status:Literal['pending','running','succeeded','failed','cancelled']
    kind:str
    attempts:int
    error_code:str | None
    resource_id:UUID | None

class RetryRequest(Contract):
    expected_revision:int = Field(ge=1)

class IdentityView(Contract):
    id:UUID
    roles:list[str]
    is_anonymous:bool
    demo_session_id:UUID | None

class MachineSave(Contract):
    label:str = Field(min_length=1,max_length=120)
    model_text:str = Field(min_length=1,max_length=120)
    serial_text:str = Field(min_length=1,max_length=120)

class SavedMachineView(Contract):
    id:UUID
    label:str
    model_text:str
    serial_text:str
    created_at:datetime

class MachinePage(Contract):
    items:list[SavedMachineView]
    next_cursor:str | None

class ArchiveResult(Contract):
    id:UUID
    archived:Literal[True] = True

class RepeatRequest(Contract):
    locale:Locale
    destination_warehouse_id:int = Field(gt=0)

class CatalogueQuery(Contract):
    cursor:str | None = None
    limit:int = Field(default=25,ge=1,le=100)
    query:str | None = Field(default=None,max_length=200)
    model_id:int | None = None
    category:str | None = None

class CataloguePart(Contract):
    id:int
    part_number:str
    name_en:str
    name_ar:str
    category:str
    unit_of_measure:str
    is_active:bool
    catalogue_version_id:UUID

class CataloguePage(Contract):
    items:list[CataloguePart]
    next_cursor:str | None

class ImportCreate(Contract):
    filename:str = Field(min_length=1,max_length=160)
    format:Literal['csv','xlsx']
    size_bytes:int = Field(gt=0,le=10485760)

class ImportUpload(Contract):
    media_type:Literal['text/csv','application/vnd.openxmlformats-officedocument.spreadsheetml.sheet']

class ImportIssue(Contract):
    row_number:int
    field:str
    code:str
    message:str

class ImportView(Contract):
    id:UUID
    state:str
    row_count:int
    issues:list[ImportIssue]
    version_id:UUID | None
    content_sha256:str | None

class PublishRequest(Contract):
    content_sha256:str = Field(pattern='^[a-f0-9]{64}$')
    expected_active_version_id:UUID | None

class VersionView(Contract):
    id:UUID
    label:str
    state:str
    content_sha256:str
    published_at:datetime | None
    source:Literal['snowflake','fixture']

class VersionList(Contract):
    items:list[VersionView]

class MissingUpdate(Contract):
    expected_revision:int = Field(ge=1)
    state:Literal['investigating','resolved','unavailable']
    note:str = Field(min_length=1,max_length=2000)

class MissingView(Contract):
    item_id:UUID
    enquiry_id:UUID
    state:str
    note:str | None
    updated_at:datetime

class MissingPage(Contract):
    items:list[MissingView]
    next_cursor:str | None

class EvalRequest(Contract):
    suite:Literal['deterministic','live']
    include_demo:bool = True

class EvaluationView(Contract):
    run_id:UUID
    state:str
    total:int
    passed:int
    failed:int
    results:list[EvalResult]

class AllowanceView(Contract):
    enabled:bool
    confirmed_usd:Decimal
    consumed_usd:Decimal
    reserved_usd:Decimal
    expires_at:datetime | None
    model:str | None

class AllowanceSet(Contract):
    confirmed_usd:Decimal = Field(ge=0)
    expires_at:datetime
    model:str = Field(min_length=1,max_length=120)
    input_usd_per_million:Decimal = Field(ge=0)
    output_usd_per_million:Decimal = Field(ge=0)

class CurateRequest(Contract):
    case_id:str = Field(min_length=1,max_length=80)
    anonymized_text:str = Field(min_length=1,max_length=12000)
    expected_status:str
    expected_part_ids:list[int]

class CuratedView(Contract):
    case_id:str
    source_correction_id:UUID
    approved_by:UUID
    created_at:datetime

class TraceStage(Contract):
    stage:str
    started_at:datetime
    duration_ms:float | None
    status:str
    error_code:str | None

class TraceView(Contract):
    enquiry_id:UUID
    revision:int
    stages:list[TraceStage]

class AttachmentList(Contract):
    items:list[AttachmentView]

class AnalyticsSyncView(Contract):
    last_success_at:datetime | None
    pending_events:int
    source:Literal['snowflake','fixture']
    stale:bool

class Problem(Contract):
    type:str
    title:str
    status:int
    code:str
    detail:str
    request_id:UUID
    retryable:bool

class CatalogueRecord(Contract):
    entity_type: str
    entity_key: str
    payload: dict[str, object]
class CatalogueSnapshot(Contract):
    version_id: UUID
    source: Literal['snowflake','fixture']
    content_sha256: str
    records: list[CatalogueRecord]
class ValidationIssue(Contract):
    entity_type: str
    entity_key: str
    field: str
    code: str
    message: str
class SyncReceipt(Contract):
    version_id: UUID
    state: Literal['requested','remote_written','validated','activated','failed']
    record_count: int
    content_sha256: str
    query_id: str | None
class StepOutcome(Contract):
    step: WorkflowStep
    reason_code: str | None
    data: dict[str, object]
class ResolutionOutcome(Contract):
    items: list[MachineView]
    next_step: WorkflowStep
class ExtractionContext(Contract):
    enquiry_id: UUID
    revision: int
    messages: list[MessageView]
    confirmed_model: str | None
    confirmed_serial: str | None
class TestReceipt(Contract):
    name: str
    passed: bool
    command: str
    evidence_path: str
class GateResult(Contract):
    passed: bool
    blocked: list[str]
class AnalyticsSyncReceipt(Contract):
    run_id: UUID
    row_count: int
    query_id: str | None
    succeeded: bool

class FeatureContext(Contract):
    request_id: UUID
    actor: ActorContext
    enquiry_id: UUID | None
    revision: int | None
class FeatureOutcome(Contract):
    passed: bool
    code: str
    details: list[str]
