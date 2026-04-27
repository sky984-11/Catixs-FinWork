from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class BaseVendor(BaseModel):
    id: int
    name: Optional[str] = None
    code: Optional[str] = None
    country: Optional[str] = None
    address: Optional[str] = None
    noc_email: Optional[str] = None
    noc_phone: Optional[str] = None
    remark: Optional[str] = None
    tax_no: Optional[str] = None
    status: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class VendorCreate(BaseModel):
    # 供应商管理默认 role=2，由后端写入，不在弹窗展示
    name: str = Field(..., example="Chief Telecom Inc")
    code: str = Field("", example="VU00024")
    country: str = Field("", example="台湾")
    address: str = Field("", example="台北市內湖區阳光街250号")
    noc_email: str = Field("", example="noc@example.com")
    noc_phone: str = Field("", example="886-70-1017-1777")
    remark: str = Field("", example="备注")
    tax_no: str = Field("", example="")
    status: bool = Field(True, example=True)


class VendorUpdate(BaseModel):
    id: int = Field(..., example=1)
    name: str = Field(..., example="Chief Telecom Inc")
    code: str = Field("", example="VU00024")
    country: str = Field("", example="台湾")
    address: str = Field("", example="台北市內湖區阳光街250号")
    noc_email: str = Field("", example="noc@example.com")
    noc_phone: str = Field("", example="886-70-1017-1777")
    remark: str = Field("", example="备注")
    tax_no: str = Field("", example="")
    status: bool = Field(True, example=True)
