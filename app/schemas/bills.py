from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field


class BillItemIn(BaseModel):
    id: Optional[int] = None
    service_id: Optional[str] = ""
    service: Optional[str] = ""
    item: Optional[str] = ""
    location: Optional[str] = ""
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    nrc_amount: Optional[float] = None
    mrc_amount: Optional[float] = None
    amount: Optional[float] = None


class BaseBill(BaseModel):
    id: int
    company_id: int
    invoice_no: Optional[str] = None
    customer_name: Optional[str] = None
    bill_month: Optional[date] = None
    invoice_date: Optional[date] = None
    due_date: Optional[date] = None
    billing_start_date: Optional[date] = None
    billing_end_date: Optional[date] = None
    currency: Optional[str] = None
    conversion_currency: Optional[str] = None
    exchange_rate: Optional[float] = None
    net_amount: Optional[float] = None
    vat_amount: Optional[float] = None
    total_amount: Optional[float] = None
    paid_amount: Optional[float] = None
    unpaid_amount: Optional[float] = None
    is_settled: bool = False
    payment_voucher_url: Optional[str] = None
    owner: Optional[str] = None
    remark: Optional[str] = None
    bill_type: int = 1
    items: list[BillItemIn] = []
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class BillCreate(BaseModel):
    company_id: int = Field(..., example=1)
    invoice_no: str = Field("", example="269806")
    customer_name: str = Field("", example="Eons Data Communications Limited")
    bill_month: Optional[date] = Field(None, example="2025-04-01")
    invoice_date: Optional[date] = Field(None, example="2025-04-30")
    due_date: Optional[date] = Field(None, example="2025-05-31")
    billing_start_date: Optional[date] = Field(None, example="2026-05-01")
    billing_end_date: Optional[date] = Field(None, example="2026-05-31")
    currency: str = Field("USD", example="USD")
    conversion_currency: str = Field("USD", example="USD")
    exchange_rate: Optional[float] = Field(1, example=1)
    net_amount: Optional[float] = Field(None, example=9175)
    vat_amount: Optional[float] = Field(None, example=0)
    total_amount: Optional[float] = Field(None, example=9175)
    paid_amount: Optional[float] = Field(None, example=0)
    unpaid_amount: Optional[float] = Field(None, example=9175)
    is_settled: bool = Field(False, example=False)
    payment_voucher_url: str = Field("", example="/uploads/bills/voucher.png")
    owner: str = Field("", example="林凯恩")
    remark: str = Field("", example="")
    bill_type: int = Field(1, example=1)
    items: list[BillItemIn] = Field(default_factory=list)


class BillUpdate(BillCreate):
    id: int = Field(..., example=1)
