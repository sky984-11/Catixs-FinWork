from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field


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
    total_amount: Optional[float] = None
    paid_amount: Optional[float] = None
    unpaid_amount: Optional[float] = None
    is_settled: bool = False
    invoice_url: Optional[str] = None
    bill_type: int = 1
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class BillCreate(BaseModel):
    company_id: int = Field(..., example=1)
    invoice_no: str = Field("", example="267711")
    customer_name: str = Field("", example="Customer A")
    bill_month: Optional[date] = Field(None, example="2026-03-01")
    invoice_date: Optional[date] = Field(None, example="2026-03-01")
    due_date: Optional[date] = Field(None, example="2026-03-15")
    billing_start_date: Optional[date] = Field(None, example="2026-03-01")
    billing_end_date: Optional[date] = Field(None, example="2026-03-31")
    currency: str = Field("", example="USD")
    total_amount: Optional[float] = Field(None, example=98.23)
    paid_amount: Optional[float] = Field(None, example=0)
    unpaid_amount: Optional[float] = Field(None, example=98.23)
    is_settled: bool = Field(False, example=False)
    invoice_url: str = Field("", example="/mock.pdf")
    bill_type: int = Field(2, example=2)


class BillUpdate(BaseModel):
    id: int = Field(..., example=1)
    company_id: int = Field(..., example=1)
    invoice_no: Optional[str] = Field(None, example="267711")
    customer_name: Optional[str] = Field(None, example="Customer A")
    bill_month: Optional[date] = Field(None, example="2026-03-01")
    invoice_date: Optional[date] = Field(None, example="2026-03-01")
    due_date: Optional[date] = Field(None, example="2026-03-15")
    billing_start_date: Optional[date] = Field(None, example="2026-03-01")
    billing_end_date: Optional[date] = Field(None, example="2026-03-31")
    currency: Optional[str] = Field(None, example="USD")
    total_amount: Optional[float] = Field(None, example=98.23)
    paid_amount: Optional[float] = Field(None, example=0)
    unpaid_amount: Optional[float] = Field(None, example=98.23)
    is_settled: Optional[bool] = Field(None, example=False)
    invoice_url: Optional[str] = Field(None, example="/mock.pdf")
    bill_type: Optional[int] = Field(None, example=2)

