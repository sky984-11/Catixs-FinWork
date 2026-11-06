from datetime import date
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Currency = Literal["CNY", "USD", "EUR", "JPY", "HKD"]
Money = Annotated[Decimal, Field(ge=0, max_digits=16, decimal_places=2, allow_inf_nan=False)]


class BillingBase(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid", validate_default=True)


class BillingTerms(BillingBase):
    title: str = Field(min_length=1, max_length=160)
    bill_date: date
    due_date: date
    discount: Money = Decimal("0")
    adjustment: Decimal = Field(default=0, max_digits=16, decimal_places=2, allow_inf_nan=False)
    tax_rate: Decimal = Field(default=0, ge=0, le=100, max_digits=7, decimal_places=4, allow_inf_nan=False)
    adjustment_reason: str = Field(default="", max_length=500)
    remark: str = Field(default="", max_length=2000)
    local_currency: Currency = "USD"
    fx_rate: Decimal = Field(default=1, gt=0, max_digits=18, decimal_places=8, allow_inf_nan=False)
    fx_source: str = Field(default="同币种", min_length=1, max_length=160)
    fx_date: date

    @model_validator(mode="after")
    def validate_terms(self):
        if self.due_date < self.bill_date:
            raise ValueError("到期日期不得早于账单日期")
        if (self.discount or self.adjustment) and not self.adjustment_reason:
            raise ValueError("折扣或变更差额必须填写原因")
        return self


class BillingGenerate(BillingTerms):
    customer_id: int = Field(gt=0)
    order_ids: list[Annotated[int, Field(gt=0)]] = Field(min_length=1, max_length=100)
    currency: Currency
    period_start: date
    months: Literal[1, 3, 6, 12, 24, 36] = 1
    calendar_mode: Literal["calendar", "anniversary"] = "calendar"
    service_start: date
    service_end: date | None = None
    payment_timing: Literal["prepaid", "postpaid"] = "prepaid"
    include_nrc: bool = True
    request_key: str = Field(min_length=8, max_length=80, pattern=r"^[a-zA-Z0-9_-]+$")
    preview_token: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")

    @model_validator(mode="after")
    def validate_period(self):
        if len(set(self.order_ids)) != len(self.order_ids):
            raise ValueError("订单不可重复选择")
        if self.service_end and self.service_end < self.service_start:
            raise ValueError("服务结束日期不得早于开始日期")
        if self.calendar_mode == "calendar" and self.period_start.day != 1:
            raise ValueError("自然月计费的账期开始日必须为每月 1 日")
        if self.local_currency == self.currency and self.fx_rate != 1:
            raise ValueError("同币种汇率必须为 1")
        return self


class BillingAction(BillingBase):
    action: Literal["issue", "void", "remind"]
    comment: str = Field(min_length=1, max_length=500)


class BillingPaymentIn(BillingBase):
    reference: str = Field(min_length=1, max_length=100)
    payment_date: date
    amount: Money
    currency: Currency
    method: str = Field(min_length=1, max_length=80)
    remark: str = Field(default="", max_length=500)

    @model_validator(mode="after")
    def positive(self):
        if self.amount <= 0:
            raise ValueError("收款金额必须大于零")
        return self


class BillingReversal(BillingBase):
    reason: str = Field(min_length=1, max_length=500)
