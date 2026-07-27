from tortoise import fields

from .base import BaseModel, TimestampMixin


class RemoteEngineer(BaseModel, TimestampMixin):
    source_id = fields.BigIntField(null=True, unique=True, description="外部系统原始ID", index=True)
    name = fields.CharField(max_length=100, description="工程师姓名", index=True)
    contact = fields.CharField(max_length=180, null=True, description="联系方式")
    wechat_id = fields.CharField(max_length=180, null=True, description="微信")
    wechat_group = fields.CharField(max_length=180, null=True, description="联系群")
    region = fields.CharField(max_length=500, null=True, description="负责地区", index=True)
    is_active = fields.IntField(default=1, description="是否启用", index=True)
    note = fields.TextField(null=True, description="备注")

    class Meta:
        table = "remote_engineer"


class RemoteHands(BaseModel, TimestampMixin):
    source_id = fields.BigIntField(null=True, unique=True, description="外部系统原始ID", index=True)
    customer = fields.CharField(max_length=200, description="客户名称", index=True)
    ticket = fields.CharField(max_length=120, null=True, description="工单号", index=True)
    engineer = fields.ForeignKeyField(
        "models.RemoteEngineer",
        related_name="remote_hands",
        null=True,
        on_delete=fields.SET_NULL,
        description="工程师",
    )
    engineer_name = fields.CharField(max_length=100, null=True, description="工程师姓名", index=True)
    engineer_contact = fields.CharField(max_length=180, null=True, description="工程师联系方式")
    engineer_wechat = fields.CharField(max_length=180, null=True, description="工程师微信")
    engineer_group = fields.CharField(max_length=180, null=True, description="工程师联系群")
    region = fields.CharField(max_length=180, null=True, description="地区", index=True)
    site = fields.CharField(max_length=180, null=True, description="机房", index=True)
    rack = fields.CharField(max_length=100, null=True, description="机柜")
    timezone = fields.CharField(max_length=80, default="Asia/Shanghai", description="时区")
    arrived_at = fields.DatetimeField(null=True, description="到场时间", index=True)
    left_at = fields.DatetimeField(null=True, description="离场时间", index=True)
    work_minutes = fields.IntField(default=0, description="工时分钟")
    status = fields.CharField(max_length=30, default="scheduled", description="任务状态", index=True)
    ops_settlement_status = fields.CharField(max_length=30, default="unbilled", description="运维结算状态", index=True)
    customer_settlement_status = fields.CharField(max_length=30, default="unbilled", description="客户结算状态", index=True)
    note = fields.TextField(null=True, description="备注")

    class Meta:
        table = "remote_hands"
