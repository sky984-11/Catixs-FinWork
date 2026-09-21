from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, allow_inf_nan=False)


class AccountInput(Input):
    id: int | None = None
    customer_id: int = Field(gt=0)
    signing_entity_id: int = Field(gt=0)
    company_id: int = Field(gt=0)
    user_ids: list[int] = Field(default_factory=list, max_length=100)
    active: bool = True


class LineInput(Input):
    product_code: str = Field(max_length=80)
    quantity: Decimal = Field(default=Decimal("1"), gt=0, le=1000000, max_digits=16, decimal_places=4)
    parameters: dict = Field(default_factory=dict)
    source_service_id: int | None = Field(default=None, gt=0)
    parent_index: int | None = Field(default=None, ge=0)


class OrderInput(Input):
    request_key: str = Field(min_length=16, max_length=80)
    account_id: int = Field(gt=0)
    title: str = Field(min_length=1, max_length=200)
    contact: str = Field(min_length=1, max_length=200)
    action: Literal[
        "quote", "new", "change", "renew", "suspend", "resume", "terminate", "one_time", "incident", "maintenance"
    ]
    requested_date: date | None = None
    reference: str = Field(default="", max_length=200)
    description: str = Field(default="", max_length=10000)
    lines: list[LineInput] = Field(min_length=1, max_length=30)


class LineUpdate(LineInput):
    revision: int = Field(gt=0)


class ChargeInput(Input):
    code: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_.-]+$")
    name: str = Field(min_length=1, max_length=160)
    kind: Literal["nrc", "recurring", "usage"]
    amount: Decimal = Field(ge=0, le=1000000000, max_digits=18, decimal_places=6)
    tax_rate: Decimal = Field(default=Decimal("0"), ge=0, le=1, max_digits=8, decimal_places=6)
    treatment: Literal["separate", "included", "free", "customer"] = "separate"
    unit: str = Field(default="项", min_length=1, max_length=30)
    interval: Literal[1, 3, 12] = 1
    proration: Literal["actual_days", "full_period", "30_days"] = "actual_days"
    timing: Literal["advance", "arrears"] = "arrears"
    usage_mode: Literal["quantity", "95th", "hours"] = "quantity"
    minimum: Decimal = Field(default=Decimal("0"), ge=0, le=1000000000)
    step: Decimal = Field(default=Decimal("1"), gt=0, le=1000000)
    allowance: Decimal = Field(default=Decimal("0"), ge=0, le=1000000000)
    cap: Decimal | None = Field(default=None, ge=0, le=1000000000)
    meter_rule: str = Field(default="", max_length=1000)

    @model_validator(mode="after")
    def check_rule(self):
        if self.kind == "usage" and not self.meter_rule:
            raise ValueError("用量收费必须说明采样、缺样、方向、单位和结算口径")
        if self.treatment != "separate" and self.amount:
            raise ValueError("已含、免费或客户自备项目的销售金额必须为0")
        return self


class QuoteInput(Input):
    revision: int = Field(gt=0)
    currency: Literal["USD", "CNY", "HKD", "EUR", "GBP", "SGD", "JPY"] = "USD"
    valid_until: date
    contract_months: int = Field(default=12, ge=1, le=120)
    payment_days: int = Field(default=15, ge=0, le=365)
    terms: str = Field(min_length=1, max_length=3000)
    procurement_reference: str = Field(default="", max_length=500)
    charges: list[ChargeInput] = Field(min_length=1, max_length=30)

    @model_validator(mode="after")
    def unique_codes(self):
        if len({item.code for item in self.charges}) != len(self.charges):
            raise ValueError("费用组件编码不能重复")
        return self


class DecisionInput(Input):
    version: int = Field(ge=0)
    action: Literal["approve", "confirm", "reject", "cancel", "revise"]
    evidence: str = Field(min_length=1, max_length=1000)


class ResourceInput(Input):
    kind: Literal["device", "vm", "cabinet", "ip", "circuit", "port"]
    key: str = Field(min_length=1, max_length=180)
    shared: bool = False
    details: dict = Field(default_factory=dict)


class TaskInput(Input):
    status: Literal["pending", "working", "done", "failed"]
    assignee_id: int | None = Field(default=None, gt=0)
    evidence: str = Field(min_length=1, max_length=3000)


class DeliveryInput(Input):
    revision: int = Field(gt=0)
    actual_parameters: dict
    values: dict
    evidence: str = Field(min_length=1, max_length=3000)
    resources: list[ResourceInput] = Field(default_factory=list, max_length=100)


class AcceptanceInput(Input):
    quote_version: int = Field(gt=0)
    revision: int = Field(gt=0)
    starts_on: date
    ends_before: date | None = None
    evidence: str = Field(min_length=1, max_length=1000)
    accept: bool = True

    @model_validator(mode="after")
    def valid_interval(self):
        if self.ends_before and self.ends_before <= self.starts_on:
            raise ValueError("结束边界必须晚于计费开始日")
        return self


class UsageInput(Input):
    charge_id: int = Field(gt=0)
    starts_on: date
    ends_before: date
    quantity: Decimal = Field(ge=0, le=1000000000, max_digits=20, decimal_places=6)
    evidence: str = Field(min_length=1, max_length=1000)


class BillingInput(Input):
    account_id: int = Field(gt=0)
    month: date
    dry_run: bool = True


class BillDecision(Input):
    action: Literal["approve", "reject", "void"]
    comment: str = Field(min_length=1, max_length=1000)


class EventInput(Input):
    request_key: str = Field(min_length=16, max_length=80)
    account_id: int = Field(gt=0)
    service_id: int | None = Field(default=None, gt=0)
    source_bill_id: int | None = Field(default=None, gt=0)
    currency: Literal["USD", "CNY", "HKD", "EUR", "GBP", "SGD", "JPY"]
    amount: Decimal = Field(ge=-1000000000, le=1000000000, max_digits=18, decimal_places=2)
    tax: Decimal = Field(default=Decimal("0"), ge=-1000000000, le=1000000000, max_digits=18, decimal_places=2)
    due_on: date
    kind: Literal["adjustment", "prepayment", "credit"]
    description: str = Field(min_length=1, max_length=500)
