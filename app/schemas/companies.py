from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class BaseCompany(BaseModel):
    id: int
    role: Optional[int] = 0
    name: Optional[str] = None
    legal_name: Optional[str] = None
    logo_url: Optional[str] = None
    code: Optional[str] = None
    country: Optional[str] = None
    address: Optional[str] = None
    noc_email: Optional[str] = None
    noc_phone: Optional[str] = None
    remark: Optional[str] = None
    status: bool = True
    tax_no: Optional[str] = None
    company_email: Optional[str] = None
    bill_email: Optional[str] = None
    contact_person: Optional[str] = None
    company_phone: Optional[str] = None
    registration_no: Optional[str] = None
    contract_company_id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class CompanyCreate(BaseModel):
    role: Optional[int] = Field(0, description="角色: 0=内部, 1=客户, 2=供应商, 3=客户+供应商")
    name: str = Field(..., example="263", description="公司简称")
    legal_name: Optional[str] = Field("", example="263 Global Communications Limited", description="公司全称")
    logo_url: Optional[str] = Field("", example="/logos/catixs.svg", description="公司Logo")
    code: Optional[str] = Field(None, example=None)
    country: Optional[str] = Field("", example="中国")
    address: Optional[str] = Field("", example="")
    noc_email: Optional[str] = Field("", example="")
    noc_phone: Optional[str] = Field("", example="")
    remark: Optional[str] = Field("", example="")
    tax_no: Optional[str] = Field("", example="")
    company_email: Optional[str] = Field("", example="")
    bill_email: Optional[str] = Field("", example="", description="财务邮箱")
    contact_person: Optional[str] = Field("", example="", description="财务联系人")
    company_phone: Optional[str] = Field("", example="")
    registration_no: Optional[str] = Field("", example="")
    contract_company_id: Optional[int] = Field(None, description="签约主体公司ID")
    status: bool = Field(True, example=True)


class CompanyUpdate(BaseModel):
    id: int = Field(..., example=1)
    role: Optional[int] = Field(0, description="角色: 0=内部, 1=客户, 2=供应商, 3=客户+供应商")
    name: str = Field(..., example="263", description="公司简称")
    legal_name: Optional[str] = Field("", example="263 Global Communications Limited", description="公司全称")
    logo_url: Optional[str] = Field("", example="/logos/catixs.svg", description="公司Logo")
    code: Optional[str] = Field(None, example="CP00001")
    country: Optional[str] = Field("", example="中国")
    address: Optional[str] = Field("", example="")
    noc_email: Optional[str] = Field("", example="")
    noc_phone: Optional[str] = Field("", example="")
    remark: Optional[str] = Field("", example="")
    tax_no: Optional[str] = Field("", example="")
    company_email: Optional[str] = Field("", example="")
    bill_email: Optional[str] = Field("", example="", description="财务邮箱")
    contact_person: Optional[str] = Field("", example="", description="财务联系人")
    company_phone: Optional[str] = Field("", example="")
    registration_no: Optional[str] = Field("", example="")
    contract_company_id: Optional[int] = Field(None, description="签约主体公司ID")
    status: bool = Field(True, example=True)
