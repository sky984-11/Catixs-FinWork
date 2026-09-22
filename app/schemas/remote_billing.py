from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class BillingTier(BaseModel):
    up_to_minutes: int | None = Field(default=None, gt=0, le=525600, strict=True)
    hourly_rate: Decimal = Field(ge=0, max_digits=12, decimal_places=2, allow_inf_nan=False)


class EngineerBillingRules(BaseModel):
    currency: Literal["CNY", "USD", "HKD", "EUR", "GBP", "SGD", "JPY"] = "CNY"
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
