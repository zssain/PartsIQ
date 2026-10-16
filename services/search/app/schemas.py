"""Request and response contracts for the search API."""

from pydantic import BaseModel, ConfigDict, Field, model_validator


class _Request(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class IdentifyRequest(_Request):
    query: str = Field(default="", max_length=500, description="Free text describing the machine")
    serial: str | None = Field(default=None, max_length=64, description="Serial number from the nameplate")

    @model_validator(mode="after")
    def _require_input(self) -> "IdentifyRequest":
        if not self.query and not self.serial:
            raise ValueError("Provide a machine description, a serial number, or both")
        return self


class PartSearchRequest(_Request):
    configuration_id: int = Field(gt=0)
    query: str = Field(min_length=1, max_length=500)
    limit: int | None = Field(default=None, ge=1, le=10)


class FulfilmentRequest(_Request):
    part_number: str = Field(min_length=3, max_length=64)
    quantity: int = Field(ge=1, le=10_000)
    destination_warehouse: str = Field(pattern=r"^[A-Z0-9_]{2,16}$")


class ConfigurationOut(BaseModel):
    id: int
    config_code: str
    description: str
    serial_start: int
    serial_end: int


class ModelOut(BaseModel):
    id: int
    brand: str
    model_code: str
    display_name: str
    rated_output: str | None
    family_code: str
    family_name_en: str
    family_name_ar: str
    configurations: list[ConfigurationOut]


class ModelCandidateOut(BaseModel):
    model: ModelOut
    score: float


class IdentifyResponse(BaseModel):
    status: str
    message: str
    model: ModelOut | None
    configuration: ConfigurationOut | None
    candidates: list[ModelCandidateOut]


class PartOut(BaseModel):
    id: int
    part_number: str
    name_en: str
    name_ar: str
    description_en: str
    category: str
    unit_of_measure: str
    is_active: bool


class WarehouseStockOut(BaseModel):
    warehouse_code: str
    warehouse_name: str
    region: str
    available: int


class CandidateOut(BaseModel):
    rank: int
    part: PartOut
    score: float
    lexical_score: float
    semantic_score: float | None
    matched_terms: list[str]
    match_reasons: list[str]
    quantity_per_unit: float
    source_reference: str
    superseded_from: list[str]
    stock: list[WarehouseStockOut]


class PartNumberMatchOut(BaseModel):
    queried_part_number: str
    current_part: PartOut
    superseded_chain: list[str]
    compatible_with_configuration: bool
    stock: list[WarehouseStockOut]


class ConfidenceOut(BaseModel):
    top_score: float
    margin: float


class PartSearchResponse(BaseModel):
    model: ModelOut
    configuration: ConfigurationOut
    detected_language: str | None
    semantic_search_enabled: bool
    part_number_matches: list[PartNumberMatchOut]
    candidates: list[CandidateOut]
    confidence: ConfidenceOut


class CompatibleMachineOut(BaseModel):
    configuration_id: int
    brand: str
    model_code: str
    display_name: str
    config_code: str
    quantity_per_unit: float


class PartDetailResponse(BaseModel):
    queried_part_number: str
    current_part: PartOut
    superseded_chain: list[str]
    stock: list[WarehouseStockOut]
    compatible_machines: list[CompatibleMachineOut]


class FulfilmentLineOut(BaseModel):
    warehouse_code: str
    quantity: int
    transfer_days: int


class FulfilmentResponse(BaseModel):
    part: PartOut
    superseded_chain: list[str]
    strategy: str
    lines: list[FulfilmentLineOut]
    estimated_transfer_days: int | None
    shortfall: int
    message: str


class WarehouseOut(BaseModel):
    code: str
    name: str
    region: str
