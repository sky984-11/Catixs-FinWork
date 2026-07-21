from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator


PROJECT_STATUSES = {"planning", "active", "acceptance", "completed", "archived"}
PROJECT_PRIORITIES = {"low", "medium", "high", "urgent"}
PROJECT_HEALTH = {"green", "yellow", "red"}


class BaseCustomerProject(BaseModel):
    id: int
    name: str
    code: Optional[str] = None
    customer_id: Optional[int] = None
    status: str = "planning"
    priority: str = "medium"
    health: str = "green"
    owner: Optional[str] = None
    contract_no: Optional[str] = None
    start_date: Optional[date] = None
    due_date: Optional[date] = None
    progress: int = 0
    budget_amount: Optional[float] = None
    budget_currency: str = "USD"
    description: Optional[str] = None
    sort_order: int = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class CustomerProjectCreate(BaseModel):
    name: str = Field(..., max_length=120)
    code: Optional[str] = Field(None, max_length=50)
    customer_id: Optional[int] = None
    status: str = "planning"
    priority: str = "medium"
    health: str = "green"
    owner: str = Field(..., min_length=1, max_length=100)
    contract_no: Optional[str] = Field("", max_length=100)
    start_date: Optional[date] = None
    due_date: Optional[date] = None
    progress: int = Field(0, ge=0, le=100)
    budget_amount: Optional[float] = Field(None, ge=0)
    budget_currency: str = Field("USD", max_length=10)
    description: Optional[str] = ""
    sort_order: int = 0

    @field_validator("status")
    @classmethod
    def validate_status(cls, value):
        if value not in PROJECT_STATUSES:
            raise ValueError("invalid project status")
        return value

    @field_validator("priority")
    @classmethod
    def validate_priority(cls, value):
        if value not in PROJECT_PRIORITIES:
            raise ValueError("invalid project priority")
        return value

    @field_validator("health")
    @classmethod
    def validate_health(cls, value):
        if value not in PROJECT_HEALTH:
            raise ValueError("invalid project health")
        return value

    @field_validator("owner")
    @classmethod
    def validate_owner(cls, value):
        value = str(value or "").strip()
        if not value:
            raise ValueError("owner is required")
        return value


class CustomerProjectUpdate(CustomerProjectCreate):
    id: int


class CustomerProjectStatusUpdate(BaseModel):
    id: int
    status: str
    sort_order: int = 0

    @field_validator("status")
    @classmethod
    def validate_status(cls, value):
        if value not in PROJECT_STATUSES:
            raise ValueError("invalid project status")
        return value


class ProjectDiscussionCreate(BaseModel):
    project_id: int
    content: str = Field(..., min_length=1)
    task_id: Optional[int] = None
    attachment_id: Optional[int] = None


class ProjectTaskCreate(BaseModel):
    project_id: int
    title: str = Field(..., max_length=200)
    assignee: Optional[str] = Field("", max_length=100)
    due_date: Optional[datetime] = None
    is_done: bool = False
    sort_order: int = 0
    remark: Optional[str] = Field("", max_length=500)

    @field_validator("due_date", mode="before")
    @classmethod
    def parse_due_datetime(cls, value):
        if not value:
            return None
        if isinstance(value, datetime):
            return value
        if isinstance(value, date):
            return datetime.combine(value, datetime.min.time())
        text = str(value).strip().replace("T", " ")
        if len(text) == 10:
            text = f"{text} 00:00"
        return datetime.strptime(text[:16], "%Y-%m-%d %H:%M")


class ProjectTaskUpdate(ProjectTaskCreate):
    id: int


class ProjectAttachmentUpload(BaseModel):
    project_id: int
    task_id: Optional[int] = None
    filename: str = Field("", description="原始文件名")
    content_type: str = Field("", description="文件 MIME 类型")
    data: str = Field("", description="Base64 内容，支持纯 base64 或 data URL")
    link_url: Optional[str] = Field("", max_length=1000, description="外部文件或文件夹链接")
    remark: Optional[str] = Field("", max_length=500)
