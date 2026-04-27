from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class BaseBank(BaseModel):
    id: int
    name: str
    country: Optional[str] = None
    swift_code: Optional[str] = None
    bank_address: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class BankCreate(BaseModel):
    name: str = Field(..., example="BANK OF TAIWAN")
    country: str = Field("", example="台湾")
    swift_code: str = Field("", example="BKTWTWTP053")
    bank_address: str = Field("", example="地址")


class BankUpdate(BaseModel):
    id: int = Field(..., example=1)
    name: str = Field(..., example="BANK OF TAIWAN")
    country: str = Field("", example="台湾")
    swift_code: str = Field("", example="BKTWTWTP053")
    bank_address: str = Field("", example="地址")

