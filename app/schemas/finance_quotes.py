from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class FinanceQuoteBase(BaseModel):
    quote_type: str = Field("server", example="server", description="报价类型")
    service_resource: str = Field("", example="Offnet", description="资源类型")
    region: str = Field("", example="硅谷", description="地区")
    service_name: str = Field("", example="银牌4116", description="服务类型")
    cpu_model: str = Field("", example="银牌4116", description="CPU型号")
    cpu_cores: str = Field("", example="24核心", description="逻辑核心数")
    memory: str = Field("", example="96G", description="内存")
    disk: str = Field("", example="2*1.92T SSD", description="硬盘")
    bandwidth: str = Field("", example="2G", description="带宽")
    burst: str = Field("", example="100G", description="突发带宽")
    traffic: str = Field("", example="不限", description="流量")
    site_a: str = Field("", example="中国 / 香港 / HK01", description="机房")
    protection: str = Field("", example="NA", description="保护方式")
    xc_cabling: str = Field("", example="No", description="交叉/布线")
    contract_terms: str = Field("", example="12 Months", description="合同周期")
    delivery_time: str = Field("", example="立即", description="交付周期")
    ip_count: str = Field("", example="1个", description="IP数量")
    provider: str = Field("", example="", description="供应商")
    currency: str = Field("CNY", example="CNY", description="币种")
    nrc: float = Field(0, example=500, description="一次性费用")
    mrc: float = Field(0, example=3000, description="月费")
    usd_per_mbps_nrc: str = Field("", example="0", description="每Mbps一次性费用")
    usd_per_mbps_mrc: float = Field(0, example=0.3, description="每Mbps月费")
    cost_price: float = Field(0, example=900, description="成本价")
    target_price: float = Field(0, example=1200, description="目标价")
    sale_price: float = Field(0, example=1300, description="报价")
    status: int = Field(1, example=1, description="状态")
    sort: int = Field(0, example=10, description="排序")
    note: str = Field("", example="USD 0.3/M, Port 100G", description="备注兼容字段")
    remark: str = Field("", example="", description="备注")


class FinanceQuoteCreate(FinanceQuoteBase):
    pass


class FinanceQuoteUpdate(FinanceQuoteBase):
    id: int = Field(..., example=1)


class FinanceQuoteOut(FinanceQuoteBase):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
