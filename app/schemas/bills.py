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
    status: str = "issued"
    term: Optional[str] = None
    approved_at: Optional[datetime] = None
    sent_at: Optional[datetime] = None
    approval_comment: Optional[str] = None
    local_currency: Optional[str] = None
    fx_rate: Optional[float] = None
    local_amount: Optional[float] = None
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
    status: str = Field("issued", example="issued")
    term: str = Field("Net 30", example="Net 30")
    approval_comment: str = Field("", example="")
    local_currency: str = Field("", example="CNY")
    fx_rate: Optional[float] = Field(None, example=7.215)
    local_amount: Optional[float] = Field(None, example=66180.0)
    items: list[BillItemIn] = Field(default_factory=list)


class BillUpdate(BillCreate):
    id: int = Field(..., example=1)


class BillingTemplatePayload(BaseModel):
    id: Optional[int] = None
    name: str = Field("", example="SG1-DIA-10G")
    product_code: str = Field("", example="10G")
    region_id: Optional[int] = Field(None, example=1)
    target_region_id: Optional[int] = Field(None, example=2)
    service_type: str = Field("", example="DIA")
    billing_rule: str = Field("monthly", example="monthly")
    price_model: str = Field("fixed", example="commit_burst")
    nrc_price: float = Field(0, example=0)
    mrc_price: float = Field(0, example=1600)
    unit_price: float = Field(0, example=1600)
    currency: str = Field("USD", example="USD")
    unit: str = Field("", example="Gbps·月")
    default_quantity: float = Field(1, example=1)
    included_ip_quantity: float = Field(0, example=2)
    ip_unit_price: float = Field(0, example=5)
    default_tax_rate: float = Field(0, example=0)
    status: bool = Field(True, example=True)
    remark: str = Field("", example="")


class BillingSubscriptionPayload(BaseModel):
    id: Optional[int] = None
    company_id: int = Field(..., example=1)
    template_id: Optional[int] = Field(None, example=1)
    product_code: str = Field("", example="10G")
    service_type: str = Field("", example="DIA")
    service_name: str = Field("", example="SG1-DIA-10G")
    service_location: str = Field("", example="Equinix SG1")
    billing_start_date: Optional[date] = Field(None, example="2025-10-01")
    billing_end_date: Optional[date] = Field(None, example="2025-10-31")
    contract_months: int = Field(12, example=12)
    unit_price: float = Field(0, example=1600)
    quantity: float = Field(1, example=1)
    currency: str = Field("USD", example="USD")
    unit: str = Field("", example="Gbps·月")
    vat_rate: float = Field(0, example=0)
    is_active: bool = Field(True, example=True)
    last_billed_month: Optional[date] = Field(None, example="2025-09-01")
    remark: str = Field("", example="")


class BillingPriceAdjustmentPayload(BaseModel):
    id: Optional[int] = None
    company_id: int = Field(..., example=1)
    template_id: Optional[int] = Field(None, example=1)
    service_type: str = Field("", example="DIA")
    region_id: Optional[int] = Field(None, example=1)
    adjustment_type: str = Field("fixed_price", example="discount")
    target_field: str = Field("mrc", example="mrc")
    adjustment_value: float = Field(0, example=0.9)
    currency: str = Field("USD", example="USD")
    priority: int = Field(100, example=100)
    effective_date: Optional[date] = Field(None, example="2026-08-01")
    expiry_date: Optional[date] = Field(None, example="2026-12-31")
    status: bool = Field(True, example=True)
    remark: str = Field("", example="")


class BillGeneratePayload(BaseModel):
    bill_month: Optional[date] = Field(None, example="2025-10-01")
    company_id: Optional[int] = Field(None, example=1)
    subscription_ids: list[int] = Field(default_factory=list)
    owner: str = Field("", example="KYRA")
    term: str = Field("Net 30", example="Net 30")
    due_days: int = Field(30, example=30)
    local_currency: str = Field("", example="CNY")
    fx_rate: Optional[float] = Field(None, example=7.215)
    dry_run: bool = Field(False, example=False)


class BillStatusPayload(BaseModel):
    action: str = Field(..., example="submit")
    comment: str = Field("", example="")
    operator: str = Field("", example="finance")


class BillPaymentPayload(BaseModel):
    payment_id: str = Field("", example="PAY202510001")
    payment_date: Optional[date] = Field(None, example="2025-10-10")
    amount: float = Field(..., example=9175)
    currency: str = Field("USD", example="USD")
    method: str = Field("", example="Wire Transfer")
    fx_rate: Optional[float] = Field(None, example=7.215)
    voucher_url: str = Field("", example="/uploads/bills/voucher.png")
    remark: str = Field("", example="")


class FeishuBillSyncPayload(BaseModel):
    url: str = Field("", example="https://coretiers.feishu.cn/base/TbyPbBZJWafmcgsIyEocRorTnxh?table=tblaU90ppqwjOfta&view=vew8xyI8DE")
    app_token: str = Field("", example="TbyPbBZJWafmcgsIyEocRorTnxh")
    table_id: str = Field("", example="tblaU90ppqwjOfta")
    view_id: str = Field("", example="vew8xyI8DE")
    bill_type: int = Field(1, example=1)
    dry_run: bool = Field(False, example=False)
    update_existing: bool = Field(True, example=True)
    create_missing_companies: bool = Field(True, example=True)
