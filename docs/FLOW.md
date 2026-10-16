# Execution flow and function ownership

The primary enquiry flow is 08 intake persistence ->09 event/controller ->10 intake ->16 optional OCR ->19 confirmation ->11 search tools backed by06 ->13 draft ->12 verification ->20 review ->14 publication ->17 export. The build order differs: a function may be created before its caller is wired. Production readiness remains false until required handlers are registered.

## Function registry
Every entry below is created or explicitly preserved by its named prompt. Detailed file paths,request/result types and validation live in that prompt and CONTRACTS.md.

| Prompt | Owner | Entry contract | Build prerequisites |
|---|---|---|---|
| 00 | Repository | def verify_environment(env: Mapping[str,str]) -> list[str]: return missing or unsafe environment names without values; reject prod database URLs when APP_ENV is local. | start |
| 01 | Common | async def call_structured(request: AIRequest, budget: BudgetReservation) -> AIResult; async def append_audit(conn: AsyncConnection, event: AuditEvent) -> int; async def actor_transaction(actor: ActorContext) -> AsyncIterator[AsyncConnection]. | 00 |
| 02 | Database | async def apply_catalogue_schema(dsn: str) -> None; schema comparison is owned by collect_schema_receipt in prompt03. | 01 |
| 03 | Database | async def setup_checkpoints(dsn: str) -> None; async def collect_schema_receipt(dsn: str) -> SchemaReceipt; no application service invokes setup_checkpoints. | 02 |
| 04 | Gateway/worker | async def create_upload(actor: ActorContext, request: UploadRequest) -> UploadTicket; async def sign_download(request: DownloadRequest) -> DownloadTicket; async def remove_object(bucket: str, object_key: str) -> None. | 03 |
| 05 | Catalogue | def build_scenarios(dataset: CatalogDataset) -> list[DemoScenario]; def render_nameplate(model: str, serial: str, destination: Path) -> None; def validate_scenarios(scenarios: list[DemoScenario], dataset: CatalogDataset) -> list[str]. | 04 |
| 06 | Search | async def embed_version(version_id: UUID, batch_size: int=16) -> EmbeddingReceipt; preserve SearchService.identify(request: IdentifyRequest) -> IdentifyResponse and SearchService.search_parts(request: PartSearchRequest) -> PartSearchResponse. | 05 |
| 07 | Gateway | async def authenticate(token: str) -> ActorContext; async def require_access(actor: ActorContext, enquiry_id: UUID, action: AccessAction) -> None; async def create_demo(actor: ActorContext) -> DemoSession; async def reset_demo(actor: ActorContext, key: UUID) -> DemoSession. | 06 |
| 08 | Gateway | async def create_enquiry(actor: ActorContext, body: EnquiryCreate, key: UUID) -> EnquiryView; async def add_message(actor: ActorContext, enquiry_id: UUID, body: MessageCreate, key: UUID) -> MessageView; async def confirm_upload(actor: ActorContext, attachment_id: UUID) -> AttachmentView. | 07 |
| 09 | Orchestrator | def next_step(state: EnquiryState) -> WorkflowStep; def build_graph(handlers: WorkflowHandlers, checkpointer: AsyncPostgresSaver) -> CompiledStateGraph; async def consume_event(event_id: UUID) -> EventOutcome. | 08 |
| 10 | Orchestrator | async def extract_intake(messages: list[MessageView], previous: IntakeResult / None, actor: ActorContext) -> IntakeResult. | 09 |
| 11 | Orchestrator | async def run_parts(item: ItemState, context: ToolContext) -> PartsProposal; async def identify(request: IdentifyRequest) -> IdentifyResponse; async def search_parts(request: PartSearchRequest) -> PartSearchResponse; async def plan_fulfilment(request: FulfilmentRequest) -> FulfilmentResponse. | 10 |
| 12 | Orchestrator | def verify_facts(facts: VerifiedFacts, evidence: VerificationEvidence) -> VerificationResult; async def verify_current(enquiry_id: UUID, revision: int) -> VerificationResult. | 11 |
| 13 | Orchestrator | async def draft_reply(facts: VerifiedFacts, locale: Locale) -> ReplySlots; def render_reply(slots: ReplySlots, facts: VerifiedFacts, locale: Locale) -> str. | 12 |
| 14 | Orchestrator | async def approve(actor: ActorContext, request: ApprovalRequest, key: UUID) -> ApprovalResult; async def reject(actor: ActorContext, request: RejectionRequest, key: UUID) -> ReviewResult; async def revise(actor: ActorContext, request: RevisionRequest) -> EnquiryView. | 13 |
| 15 | Worker | async def claim_job(job_id: UUID, worker_id: str) -> JobLease / None; async def heartbeat(lease: JobLease) -> bool; async def finish_job(lease: JobLease, result: JobResult) -> bool; async def sweep_once(now: datetime) -> int. | 14 |
| 16 | Worker | async def read_nameplate(job: JobLease, image: bytes) -> NameplateResult; def validate_image(image: bytes, media_type: str) -> ImageInfo. | 15 |
| 17 | Worker | async def export_enquiry(job: JobLease, request: ExportRequest) -> ExportResult; def render_export_html(snapshot: ApprovedSnapshot) -> str. | 16 |
| 18 | Web | export function BrandLogo(props: {compact?: boolean}): React.JSX.Element; export async function api<T>(path: string, options: RequestInit): Promise<T>; export async function startAnonymousDemo(): Promise<DemoSession>. | 17 |
| 19 | Web | export function Chat(props: {enquiryId: string}): React.JSX.Element; export function OcrConfirmation(props: {extraction: NameplateResult; onConfirm: (value: ConfirmExtraction) => Promise<void>}): React.JSX.Element. | 18 |
| 20 | Web | export function Workspace(props: {enquiryId: string}): React.JSX.Element; export function ApprovalControls(props: {review: ReviewView; onChanged: () => Promise<void>}): React.JSX.Element. | 19 |
| F16 | worker | def assess_photo(request: F16Request) -> F16Result | 16, 19 |
| F17 | orchestrator | async def resolve_items(actor: ActorContext, request: F17Request) -> F17Result | 09, 10, 11, 12, 13, 14, 19, 20 |
| F19 | gateway | async def list_history(actor: ActorContext, request: F19Request) -> F19Result | 07, 08, 19 |
| F55 | gateway | async def save_machine(actor: ActorContext, request: F55Request) -> F55Result | 07, 19 |
| F56 | gateway | async def repeat_enquiry(actor: ActorContext, request: F56Request) -> F56Result | 09, 19, F19, F55 |
| F59 | catalog | async def publish_version(actor: ActorContext, request: F59Request) -> F59Result | 02, 05, 06 |
| F57 | gateway | async def browse_catalogue(actor: ActorContext, request: F57Request) -> F57Result | 02, 06, 18, F59 |
| F58 | worker | async def validate_import(actor: ActorContext, request: F58Request) -> F58Result | 02, 05, 15, F59, F57 |
| F60 | gateway | async def update_missing_part(actor: ActorContext, request: F60Request) -> F60Result | 03, 20 |
| F35 | search | async def check_stock_freshness(actor: ActorContext, request: F35Request) -> F35Result | 06, 12, 14, 20 |
| F29 | gateway | async def open_evidence(actor: ActorContext, request: F29Request) -> F29Result | 04, 06, 20 |
| F31 | web | export function compare_candidates(request: F31Request): F31Result | 06, 20 |
| F38 | orchestrator | async def correct_extraction(actor: ActorContext, request: F38Request) -> F38Result | 09, 14, 20 |
| F42 | gateway | async def assign_enquiry(actor: ActorContext, request: F42Request) -> F42Result | 03, 07, 20 |
| F41 | gateway | async def append_note(actor: ActorContext, request: F41Request) -> F41Result | 03, 07, 20 |
| F43 | gateway | async def classify_deadline(actor: ActorContext, request: F43Request) -> F43Result | 20 |
| F44 | orchestrator | async def summarize_enquiry(actor: ActorContext, request: F44Request) -> F44Result | 09, 13, 20 |
| F36 | gateway | async def list_inbox(actor: ActorContext, request: F36Request) -> F36Result | 07, 20, F42, F43 |
| F07 | web | export function resolve_locale(request: F07Request): F07Result | 18, 19, 20 |
| F08 | web | export function resolve_theme(request: F08Request): F08Result | 18 |
| F06 | web | export function get_layout(request: F06Request): F06Result | 18, 19, 20, F07, F08 |
| F48 | orchestrator | def validate_tool_call(request: F48Request) -> F48Result | 10, 11, 12, 13, 16 |
| 21 | Quality | def evaluate_case(case: EvalCase, actual: EvalOutput) -> EvalResult; async def run_suite(cases: list[EvalCase], live: bool=False) -> EvalRun. | F48 |
| 23 | Operations | async def get_metrics(actor: ActorContext, query: MetricsQuery) -> MetricsView; def validate_allowance(amount: Decimal, expires_at: datetime, paid_budget: Decimal) -> CreditAllowance; async def readiness_report() -> ReadinessReport. | 21 |
| F63 | gateway | async def metrics_dashboard(actor: ActorContext, request: F63Request) -> F63Result | 21, 23 |
| F65 | gateway | async def curate_correction(actor: ActorContext, request: F65Request) -> F65Result | 14, 21, 23, F63 |
| 22 | Quality | def assert_disposable_environment(config: TestConfig) -> None; test suites instantiate existing service entry points without new business logic. | F65 |
| 24 | Infrastructure | def verify_images(compose_file: Path) -> list[str]: reject mutable application tags,missing healthchecks,public internal ports and embedded credentials. | 22 |
| 25 | Infrastructure | def check_ci_configuration(root: Path) -> list[str]: inspect permissions,action pinning,prod-test protection and deployment guards. | 24 |
| 26 | Infrastructure | def preflight(account: AccountReceipt, sizing: SizingReceipt) -> DeploymentDecision; bootstrap.sh accepts a validated environment file path; deploy.sh accepts one hexadecimal release SHA. | 25 |
| 27 | Infrastructure | async def run_hosted_acceptance(base_url: str, api_url: str) -> HostedReceipt; reject non-HTTPS URLs outside localhost. | 26 |
| F68 | docs | Documentation contract: README.md and docs/RECRUITER_GUIDE.md | 21, 23, 22, 24, 25, 26, 27 |
| F69 | docs | Documentation contract: docs/DEMO_SCRIPT.md and docs/RECORDING_CHECKLIST.md | 27, F68 |

## Event and transaction boundaries
Intake transaction commits before dispatch. OCR completion transaction fences lease/revision/generation and inserts workflow event. Event consumer uses persisted checkpointer and ignores obsolete events. Approval transaction holds enquiry lock,rechecks permissions,current catalogue and latest stock,then inserts decision,recommendation and audit. Storage cleanup is asynchronous after demo invalidation; it is never described as a cross-system atomic delete.

## Status transitions
received -> processing; processing -> needs_information or awaiting_review or failed; needs_information -> processing after validated reply; awaiting_review -> approved or rejected; relevant correction -> processing with incremented revision. A failed dependency can return to processing through an authorized idempotent retry. Approved historical messages remain historical; a changed enquiry needs new review before another recommendation.
