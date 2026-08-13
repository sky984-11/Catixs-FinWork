from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator


REQUIREMENT_STATUSES = {
    "lead",
    "qualified",
    "solution",
    "quotation",
    "negotiation",
    "won",
    "lost",
    "shelved",
    "pool",
    "reviewing",
    "planned",
    "designing",
    "developing",
    "testing",
    "released",
    "rejected",
}
REQUIREMENT_PRIORITIES = {"low", "medium", "high", "urgent"}
REQUIREMENT_SOURCES = {"customer", "sales", "support", "internal", "ops", "market", "feishu", "other"}
REQUIREMENT_TYPES = {
    "colocation",
    "server",
    "bandwidth",
    "ip",
    "cloud",
    "managed",
    "security",
    "feature",
    "improvement",
    "bug",
    "research",
    "ops",
    "other",
}


class CustomerRequirementCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    code: Optional[str] = Field(None, max_length=50)
    customer_id: Optional[int] = None
    project_id: Optional[int] = None
    source: str = "customer"
    source_record_id: Optional[str] = Field(None, max_length=100)
    source_detail: Optional[str] = Field("", max_length=200)
    requirement_type: str = "colocation"
    status: str = "lead"
    priority: str = "medium"
    owner: Optional[str] = Field("", max_length=100)
    requester: Optional[str] = Field("", max_length=100)
    service_type: Optional[str] = Field("", max_length=50)
    a_end: Optional[str] = Field("", max_length=200)
    z_end: Optional[str] = Field("", max_length=200)
    region: Optional[str] = Field("", max_length=100)
    datacenter: Optional[str] = Field("", max_length=120)
    bandwidth: Optional[str] = Field("", max_length=100)
    ip_count: int = Field(0, ge=0)
    cabinet_count: float = Field(0, ge=0)
    server_count: int = Field(0, ge=0)
    contract_term: Optional[str] = Field("", max_length=50)
    budget_amount: Optional[float] = Field(None, ge=0)
    budget_currency: str = Field("USD", max_length=10)
    nrc_amount: Optional[float] = Field(None, ge=0)
    expected_mrr: Optional[float] = Field(None, ge=0)
    target_price: Optional[str] = Field("", max_length=500)
    probability: int = Field(30, ge=0, le=100)
    competitor: Optional[str] = Field("", max_length=200)
    next_action: Optional[str] = Field("", max_length=255)
    expected_at: Optional[date] = None
    planned_at: Optional[date] = None
    released_at: Optional[date] = None
    value_score: int = Field(0, ge=0, le=100)
    effort_score: int = Field(0, ge=0, le=100)
    confidence_score: int = Field(0, ge=0, le=100)
    reach_score: int = Field(0, ge=0, le=100)
    vote_count: int = Field(0, ge=0)
    tags: list[str] = Field(default_factory=list)
    related_links: list[str] = Field(default_factory=list)
    description: Optional[str] = ""
    acceptance_criteria: Optional[str] = ""
    solution: Optional[str] = ""
    sort_order: int = 0

    @field_validator("status")
    @classmethod
    def validate_status(cls, value):
        value = str(value or "").strip()
        if value not in REQUIREMENT_STATUSES:
            raise ValueError("invalid requirement status")
        return value

    @field_validator("priority")
    @classmethod
    def validate_priority(cls, value):
        value = str(value or "").strip()
        if value not in REQUIREMENT_PRIORITIES:
            raise ValueError("invalid requirement priority")
        return value

    @field_validator("source")
    @classmethod
    def validate_source(cls, value):
        value = str(value or "").strip()
        if value not in REQUIREMENT_SOURCES:
            raise ValueError("invalid requirement source")
        return value

    @field_validator("requirement_type")
    @classmethod
    def validate_type(cls, value):
        value = str(value or "").strip()
        if value not in REQUIREMENT_TYPES:
            raise ValueError("invalid requirement type")
        return value

    @field_validator("title")
    @classmethod
    def validate_title(cls, value):
        value = str(value or "").strip()
        if not value:
            raise ValueError("title is required")
        return value


class CustomerRequirementUpdate(CustomerRequirementCreate):
    id: int


class CustomerRequirementStatusUpdate(BaseModel):
    id: int
    status: str
    sort_order: int = 0

    @field_validator("status")
    @classmethod
    def validate_status(cls, value):
        value = str(value or "").strip()
        if value not in REQUIREMENT_STATUSES:
            raise ValueError("invalid requirement status")
        return value


class FeishuRequirementSyncPayload(BaseModel):
    url: str = Field(
        "",
        example="https://coretiers.feishu.cn/base/RyIVbsOmjaVX0eswSmRcPc6fnJb?table=tbltCdcOxisznJut&view=vewglxWnz6",
    )
    app_token: str = Field("", example="RyIVbsOmjaVX0eswSmRcPc6fnJb")
    table_id: str = Field("", example="tbltCdcOxisznJut")
    view_id: str = Field("", example="vewglxWnz6")
    dry_run: bool = Field(False, example=False)
    update_existing: bool = Field(True, example=True)
    create_missing_customers: bool = Field(False, example=False)


class BaseCustomerRequirement(BaseModel):
    id: int
    title: str
    code: Optional[str] = None
    customer_id: Optional[int] = None
    project_id: Optional[int] = None
    source: str = "customer"
    source_record_id: Optional[str] = None
    source_detail: Optional[str] = None
    requirement_type: str = "colocation"
    status: str = "lead"
    priority: str = "medium"
    owner: Optional[str] = None
    requester: Optional[str] = None
    service_type: Optional[str] = None
    a_end: Optional[str] = None
    z_end: Optional[str] = None
    region: Optional[str] = None
    datacenter: Optional[str] = None
    bandwidth: Optional[str] = None
    ip_count: int = 0
    cabinet_count: float = 0
    server_count: int = 0
    contract_term: Optional[str] = None
    budget_amount: Optional[float] = None
    budget_currency: str = "USD"
    nrc_amount: Optional[float] = None
    expected_mrr: Optional[float] = None
    target_price: Optional[str] = None
    probability: int = 30
    competitor: Optional[str] = None
    next_action: Optional[str] = None
    expected_at: Optional[date] = None
    planned_at: Optional[date] = None
    released_at: Optional[date] = None
    value_score: int = 0
    effort_score: int = 0
    confidence_score: int = 0
    reach_score: int = 0
    vote_count: int = 0
    tags: list[str] = Field(default_factory=list)
    related_links: list[str] = Field(default_factory=list)
    description: Optional[str] = None
    acceptance_criteria: Optional[str] = None
    solution: Optional[str] = None
    sort_order: int = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
