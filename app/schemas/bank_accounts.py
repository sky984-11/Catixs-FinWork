from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class BaseBankAccount(BaseModel):
    id: int
    company_id: int
    bank_id: Optional[int] = None
    bank_name: Optional[str] = None
    bank_code: Optional[str] = None
    branch_code: Optional[str] = None
    account_name: Optional[str] = None
    account_number: Optional[str] = None
    swift_code: Optional[str] = None
    iban: Optional[str] = None
    sort_code: Optional[str] = None
    currency: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class BankAccountCreate(BaseModel):
    company_id: int = Field(..., example=1)
    bank_id: int | None = Field(None, example=1)
    bank_code: str = Field("", example="053")
    branch_code: str = Field("", example="005")
    account_name: str = Field("", example="Chief Telecom Inc")
    account_number: str = Field("", example="053007505008")
    swift_code: str = Field("", example="BKTWTWTP053")
    iban: str = Field("", example="")
    sort_code: str = Field("", example="")
    currency: str = Field("", example="USD")


class BankAccountUpdate(BaseModel):
    id: int = Field(..., example=1)
    company_id: int = Field(..., example=1)
    bank_id: int | None = Field(None, example=1)
    bank_code: str = Field("", example="053")
    branch_code: str = Field("", example="005")
    account_name: str = Field("", example="Chief Telecom Inc")
    account_number: str = Field("", example="053007505008")
    swift_code: str = Field("", example="BKTWTWTP053")
    iban: str = Field("", example="")
    sort_code: str = Field("", example="")
    currency: str = Field("", example="USD")
