from tortoise import fields

from .base import BaseModel, TimestampMixin


class FinanceQuote(BaseModel, TimestampMixin):
    quote_type = fields.CharField(max_length=30, default="server", description="报价类型", index=True)
    service_resource = fields.CharField(max_length=80, null=True, description="资源类型")
    region = fields.CharField(max_length=100, null=True, description="地区", index=True)
    service_name = fields.CharField(max_length=120, null=True, description="产品/服务名称", index=True)
    cpu_model = fields.CharField(max_length=120, null=True, description="CPU型号")
    cpu_cores = fields.CharField(max_length=80, null=True, description="逻辑核心数")
    memory = fields.CharField(max_length=80, null=True, description="内存")
    disk = fields.CharField(max_length=160, null=True, description="硬盘")
    bandwidth = fields.CharField(max_length=80, null=True, description="带宽")
    burst = fields.CharField(max_length=80, null=True, description="突发带宽")
    traffic = fields.CharField(max_length=80, null=True, description="流量")
    site_a = fields.CharField(max_length=120, null=True, description="站点A")
    protection = fields.CharField(max_length=80, null=True, description="保护方式")
    xc_cabling = fields.CharField(max_length=80, null=True, description="交叉/布线")
    contract_terms = fields.CharField(max_length=80, null=True, description="合同周期")
    delivery_time = fields.CharField(max_length=80, null=True, description="开通时间")
    ip_count = fields.CharField(max_length=80, null=True, description="IP")
    provider = fields.CharField(max_length=120, null=True, description="供应商")
    currency = fields.CharField(max_length=10, default="CNY", description="币种")
    nrc = fields.FloatField(default=0, description="一次性费用")
    mrc = fields.FloatField(default=0, description="月费")
    usd_per_mbps_nrc = fields.CharField(max_length=80, null=True, description="每Mbps一次性费用")
    usd_per_mbps_mrc = fields.FloatField(default=0, description="每Mbps月费")
    cost_price = fields.FloatField(default=0, description="成本价")
    target_price = fields.FloatField(default=0, description="目标价")
    sale_price = fields.FloatField(default=0, description="报价")
    status = fields.IntField(default=1, description="状态", index=True)
    sort = fields.IntField(default=0, description="排序")
    note = fields.CharField(max_length=500, null=True, description="备注")
    remark = fields.CharField(max_length=500, null=True, description="备注")

    class Meta:
        table = "finance_quote"
