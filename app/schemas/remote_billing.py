from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
import pytz

Money = Annotated[Decimal, Field(ge=0, max_digits=12, decimal_places=2, allow_inf_nan=False)]
Currency = Literal["CNY", "USD", "HKD", "EUR", "GBP", "SGD", "JPY"]


class BillingTier(BaseModel):
    up_to_minutes: int | None = Field(default=None, gt=0, le=525600, strict=True)
    hourly_rate: Decimal = Field(ge=0, max_digits=12, decimal_places=2, allow_inf_nan=False)


class EngineerBillingRules(BaseModel):
    model_config = ConfigDict(extra="forbid")

    currency: Currency = "CNY"
    tiers: list[BillingTier] = Field(min_length=1, max_length=20)

    @model_validator(mode="after")
    def validate_tiers(self):
        previous = 0
        for index, tier in enumerate(self.tiers):
            if tier.up_to_minutes is None:
                if index != len(self.tiers) - 1:
                    raise ValueError("仅最后一档可以不设工时上限")
            elif tier.up_to_minutes <= previous:
                raise ValueError("阶梯工时上限必须严格递增")
            else:
                previous = tier.up_to_minutes
        if self.tiers[-1].up_to_minutes is not None:
            raise ValueError("最后一档必须不设上限")
        return self


class PackageBillingTier(BaseModel):
    model_config = ConfigDict(extra="forbid")

    up_to_minutes: int = Field(gt=0, le=525600, strict=True)
    total_fee: Money


class MaintenanceBillingRules(BaseModel):
    """Fixed total prices by duration, followed by hourly overtime; legacy hourly rules stay valid."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    mode: Literal["package"]
    currency: Currency = "CNY"
    tiers: list[PackageBillingTier] = Field(min_length=1, max_length=20)
    overtime_hourly_rate: Money
    overtime_threshold_minutes: int = Field(default=30, ge=1, le=60, strict=True)
    overtime_rounding: Literal["half_hour_round", "ceil_after_threshold", "actual_after_threshold"] = "half_hour_round"
    night_multiplier: Decimal = Field(default=Decimal("1.25"), ge=1, le=10, decimal_places=2, allow_inf_nan=False)
    night_applies_to_emergency: bool = False
    emergency_fee: Money = Decimal("500.00")
    emergency_response_minutes: int = Field(default=240, gt=0, le=10080, strict=True)
    emergency_region: str = Field(default="东京", min_length=1, max_length=100)
    emergency_confirmation_region: str = Field(default="大阪", min_length=1, max_length=100)
    transport_included_region: str = Field(default="东京都", min_length=1, max_length=100)
    project_services: list[Annotated[str, Field(min_length=1, max_length=100)]] = Field(
        default_factory=lambda: ["设备上架", "综合布线"], min_length=1, max_length=20
    )
    settlement_cycles: list[Literal["daily", "weekly"]] = Field(
        default_factory=lambda: ["daily", "weekly"], min_length=1, max_length=2
    )
    domestic_payment: str = Field(default="国内个人微信账号收款", min_length=1, max_length=500)
    japan_payment: str = Field(default="日本可公对公，需另加税，税率及税额另行确认", min_length=1, max_length=500)

    @model_validator(mode="after")
    def validate_packages(self):
        previous_minutes, previous_fee = 0, Decimal("0")
        for tier in self.tiers:
            if tier.up_to_minutes <= previous_minutes:
                raise ValueError("档位工时上限必须严格递增")
            if tier.total_fee < previous_fee:
                raise ValueError("档位总价不能低于前一档")
            previous_minutes, previous_fee = tier.up_to_minutes, tier.total_fee
        if self.emergency_region == self.emergency_confirmation_region:
            raise ValueError("紧急服务区域与待确认区域不能相同")
        if len(set(self.settlement_cycles)) != len(self.settlement_cycles):
            raise ValueError("结算周期不能重复")
        return self


class PaymentRule(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=100)
    tax_mode: Literal["none", "included", "extra", "confirm"] = "none"
    tax_rate: Decimal | None = Field(default=None, ge=0, le=100, decimal_places=2, allow_inf_nan=False)
    tax_base: Literal["labor", "subtotal"] = "subtotal"
    note: str = Field(default="", max_length=500)


class AdditionalFeeRule(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    id: str = Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9_-]+$")
    name: str = Field(min_length=1, max_length=100)
    mode: Literal["fixed", "hourly"] = "fixed"
    amount: Money | None = None
    minutes_source: Literal["fixed", "actual", "work"] = "actual"
    minutes: int = Field(default=60, ge=0, le=10080, strict=True)
    increment_minutes: int = Field(default=30, ge=1, le=1440, strict=True)
    excluded_regions: list[Annotated[str, Field(min_length=1, max_length=100)]] = Field(
        default_factory=list, max_length=100
    )


class GeneralBillingRules(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    mode: Literal["general"]
    currency: Currency = "CNY"
    pricing: Literal["hourly", "package", "tiered_hourly"] = "hourly"
    hourly_rate: Money | None = None
    additional_fees: list[AdditionalFeeRule] = Field(default_factory=list, max_length=30)
    tiers: list[PackageBillingTier] = Field(default_factory=list, max_length=20)
    hourly_tiers: list[BillingTier] = Field(default_factory=list, max_length=20)
    minimum_minutes: int = Field(default=0, ge=0, le=10080, strict=True)
    billing_increment_minutes: int = Field(default=1, ge=1, le=1440, strict=True)
    overtime_enabled: bool = False
    overtime_hourly_rate: Money | None = None
    overtime_threshold_minutes: int = Field(default=1, ge=1, le=60, strict=True)
    overtime_rounding: Literal["half_hour_round", "ceil_after_threshold", "actual_after_threshold"] = (
        "actual_after_threshold"
    )
    night_enabled: bool = False
    night_start: str | None = Field(default=None, pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")
    night_end: str | None = Field(default=None, pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")
    night_multiplier: Decimal = Field(default=Decimal("1"), ge=1, le=10, decimal_places=2, allow_inf_nan=False)
    night_basis: Literal["proportional", "any_overlap"] = "proportional"
    night_applies_to_emergency: bool = False
    emergency_fee: Money | None = None
    emergency_response_minutes: int | None = Field(default=None, gt=0, le=10080, strict=True)
    emergency_regions: list[Annotated[str, Field(min_length=1, max_length=100)]] = Field(
        default_factory=list, max_length=100
    )
    emergency_confirmation_regions: list[Annotated[str, Field(min_length=1, max_length=100)]] = Field(
        default_factory=list, max_length=100
    )
    transport_mode: Literal["none", "fixed", "hourly", "reimburse"] = "none"
    transport_fee: Money | None = None
    commute_minutes: int = Field(default=60, ge=1, le=10080, strict=True)
    commute_mode: Literal["fixed", "actual"] = "fixed"
    commute_increment_minutes: int = Field(default=30, ge=1, le=1440, strict=True)
    commute_hourly_rate: Money | None = None
    transport_included_regions: list[Annotated[str, Field(min_length=1, max_length=100)]] = Field(
        default_factory=list, max_length=100
    )
    project_services: list[Annotated[str, Field(min_length=1, max_length=100)]] = Field(
        default_factory=list, max_length=20
    )
    settlement_cycles: list[Annotated[str, Field(min_length=1, max_length=50)]] = Field(
        default_factory=list, max_length=20
    )
    payment_methods: list[PaymentRule] = Field(default_factory=list, max_length=20)
    note: str = Field(default="", max_length=2000)

    @model_validator(mode="after")
    def validate_rules(self):
        ids = [fee.id for fee in self.additional_fees]
        if len(set(ids)) != len(ids):
            raise ValueError("附加费用标识不能重复")
        if self.pricing == "package":
            if not self.tiers:
                raise ValueError("请配置固定档位")
            previous, fee = 0, Decimal("0")
            for tier in self.tiers:
                if tier.up_to_minutes <= previous or tier.total_fee < fee:
                    raise ValueError("档位上限须递增，总价不能低于前一档")
                previous, fee = tier.up_to_minutes, tier.total_fee
        if self.pricing == "tiered_hourly":
            EngineerBillingRules(currency=self.currency, tiers=self.hourly_tiers)
        if bool(self.night_start) != bool(self.night_end) or (self.night_start and self.night_start == self.night_end):
            raise ValueError("夜班起止时间须同时填写且不能相同")
        if set(self.emergency_regions) & set(self.emergency_confirmation_regions):
            raise ValueError("紧急服务区域与待确认区域不能重叠")
        names = [method.name for method in self.payment_methods]
        if len(set(names)) != len(names):
            raise ValueError("收款方式名称不能重复")
        return self


class ReimbursedExpense(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=100)
    amount: Money | None = None
    currency: Currency
    note: str = Field(default="", max_length=500)


class BillingContext(BaseModel):
    model_config = ConfigDict(extra="forbid")
    emergency: bool = False
    service_type: Literal["standard", "project"] = "standard"
    payment_method: str | None = Field(default=None, max_length=100)
    reimbursed_transport: Money | None = None
    actual_commute_minutes: int | None = Field(default=None, ge=0, le=10080, strict=True)
    expenses: list[ReimbursedExpense] = Field(default_factory=list, max_length=50)
    additional_fee_minutes: dict[str, Annotated[int | None, Field(ge=0, le=10080, strict=True)]] = Field(
        default_factory=dict, max_length=30
    )
    excluded_fee_ids: list[Annotated[str, Field(max_length=80)]] = Field(default_factory=list, max_length=30)


def validate_billing_timezone(value: str) -> str:
    try:
        pytz.timezone(value)
    except pytz.UnknownTimeZoneError as exc:
        raise ValueError("请使用有效的 IANA 时区，例如 Asia/Shanghai") from exc
    return value


class CustomerMaintenancePrice(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["internal", "hourly", "fixed", "pending"] = "pending"
    hourly_rate: Money | None = None
    fixed_fee: Money | None = None
    currency: Currency = "USD"
    expenses_included: bool = False
    note: str = Field(default="", max_length=1000)


class BillingPreviewPayload(BaseModel):
    rules: GeneralBillingRules | EngineerBillingRules | MaintenanceBillingRules | None = None
    arrived_at: str = ""
    left_at: str = ""
    timezone: str = "Asia/Shanghai"
    region: str = Field(default="", max_length=180)
    context: BillingContext = Field(default_factory=BillingContext)
    customer_pricing: CustomerMaintenancePrice | None = None

    _timezone = field_validator("timezone")(validate_billing_timezone)
