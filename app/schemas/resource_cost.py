from datetime import date
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Category = Literal["ipt_dia", "ptp", "retail", "xc", "colo"]
Amount = Annotated[Decimal, Field(ge=0, max_digits=16, decimal_places=4, allow_inf_nan=False)]

# Shared metadata drives the editor, table and CSV template. No spreadsheet values are hard-coded.
FIELDS = {
    "service_resource": {"label": "Service Resource", "type": "select", "options": ["Onnet", "Offnet", "NA"]},
    "service": {"label": "Service", "type": "text"},
    "vendor_id": {"label": "Vendor", "type": "vendor"},
    "bandwidth": {"label": "B/W", "type": "text"},
    "burst": {"label": "Burst", "type": "text"},
    "site_a": {"label": "Site A", "type": "text"},
    "site_b": {"label": "Site B", "type": "text"},
    "protection": {"label": "Protection", "type": "select", "options": ["Protected", "Unprotected", "NA"]},
    "xc_cabling": {"label": "XC/Cabling", "type": "select", "options": ["Yes", "No", "NA"]},
    "contract_months": {"label": "Contract Terms（月）", "type": "integer"},
    "currency": {
        "label": "Currency",
        "type": "select",
        "options": ["USD", "HKD", "CNY", "EUR", "GBP", "JPY", "SGD", "MYR", "AUD"],
    },
    "nrc": {"label": "NRC（成本）", "type": "money"},
    "mrc": {"label": "MRC（成本）", "type": "money"},
    "mrc_unit": {"label": "MRC 计价单位", "type": "text"},
    "price_per_mbps": {"label": "Price/Mbps MRC", "type": "money"},
    "burst_price": {"label": "Burst Price/Mbps", "type": "money"},
    "dc_name": {"label": "DC Name", "type": "text"},
    "site_address": {"label": "Site Address", "type": "text"},
    "tax_rate": {"label": "Tax Rate（%）", "type": "money"},
    "note": {"label": "Note / Remarks", "type": "textarea"},
    "effective_date": {"label": "生效日", "type": "date"},
    "expiry_date": {"label": "失效日（不含）", "type": "date"},
}
COMMON = ["service_resource", "service", "vendor_id", "bandwidth"]
TERMS = ["protection", "xc_cabling", "contract_months", "currency", "nrc", "mrc", "mrc_unit"]
CATEGORIES = {
    "ipt_dia": {
        "label": "IPT / DIA (DC)",
        "fields": COMMON + ["burst", "site_a"] + TERMS + ["price_per_mbps", "burst_price", "note"],
    },
    "ptp": {"label": "PtP (DC)", "fields": COMMON + ["site_a", "site_b"] + TERMS + ["price_per_mbps", "note"]},
    "retail": {
        "label": "Retail Building",
        "fields": COMMON + ["burst", "site_a", "site_b"] + TERMS + ["price_per_mbps", "note"],
    },
    "xc": {
        "label": "XC",
        "fields": ["dc_name", "site_address", "vendor_id", "currency", "tax_rate", "nrc", "mrc", "mrc_unit", "note"],
    },
    "colo": {"label": "Colo", "fields": COMMON + ["site_a"] + TERMS + ["note"]},
}


class CostPayload(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    category: Category
    code: str | None = Field(None, max_length=80)
    expected_revision: int | None = Field(None, ge=1)
    enabled: bool = True
    vendor_id: int | None = Field(None, gt=0)
    service_resource: Literal["Onnet", "Offnet", "NA"] | None = None
    service: str | None = Field(None, max_length=120)
    bandwidth: str | None = Field(None, max_length=100)
    burst: str | None = Field(None, max_length=100)
    site_a: str | None = Field(None, max_length=500)
    site_b: str | None = Field(None, max_length=500)
    protection: Literal["Protected", "Unprotected", "NA"] | None = None
    xc_cabling: Literal["Yes", "No", "NA"] | None = None
    contract_months: int | None = Field(None, ge=1, le=1200)
    currency: Literal["USD", "HKD", "CNY", "EUR", "GBP", "JPY", "SGD", "MYR", "AUD"] | None = None
    nrc: Amount | None = None
    mrc: Amount | None = None
    mrc_unit: str | None = Field(None, max_length=40)
    price_per_mbps: Amount | None = None
    burst_price: Amount | None = None
    tax_rate: Decimal | None = Field(None, ge=0, le=100, max_digits=7, decimal_places=4, allow_inf_nan=False)
    dc_name: str | None = Field(None, max_length=200)
    site_address: str | None = Field(None, max_length=500)
    note: str | None = Field(None, max_length=4000)
    effective_date: date | None = None
    expiry_date: date | None = None

    @model_validator(mode="after")
    def validate_fields(self):
        permitted = set(CATEGORIES[self.category]["fields"]) | {"effective_date", "expiry_date"}
        for key in FIELDS:
            if key not in permitted and getattr(self, key) not in (None, ""):
                raise ValueError(f"该分类不支持字段 {key}")
        if self.enabled and self.category == "xc":
            if not self.dc_name:
                raise ValueError("XC 必须填写 DC Name")
        elif self.enabled and self.category != "xc" and (not self.service or not self.site_a):
            raise ValueError("必须填写 Service 和 Site A")
        if self.enabled and self.category == "ptp" and not self.site_b:
            raise ValueError("PtP 必须填写 Site B")
        if (
            self.enabled
            and any(getattr(self, key) is not None for key in ("nrc", "mrc", "price_per_mbps", "burst_price"))
            and not self.currency
        ):
            raise ValueError("填写成本时必须选择币种")
        if self.effective_date and self.expiry_date and self.expiry_date <= self.effective_date:
            raise ValueError("失效日必须晚于生效日")
        return self


class ImportPreview(BaseModel):
    category: Category
    csv_text: str = Field(min_length=1, max_length=2 * 1024 * 1024)


class CostImport(BaseModel):
    rows: list[CostPayload] = Field(min_length=1, max_length=500)


class CostLinkPayload(BaseModel):
    version_id: int = Field(gt=0)
