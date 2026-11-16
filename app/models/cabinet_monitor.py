from tortoise import fields

from .base import BaseModel, TimestampMixin


class CabinetMonitorConfig(BaseModel, TimestampMixin):
    enabled = fields.BooleanField(default=False)
    revision = fields.IntField(default=0)
    template_id = fields.CharField(max_length=20, default="")
    group_id = fields.CharField(max_length=20, default="")
    proxy_id = fields.CharField(max_length=20, default="")
    overrides = fields.JSONField(default=dict)
    host_policies = fields.JSONField(default=dict, null=True)
    lease_until = fields.BigIntField(default=0)
    lease_token = fields.CharField(max_length=36, default="")
    last_checked = fields.BigIntField(default=0)
    last_error = fields.CharField(max_length=300, default="")

    class Meta:
        table = "cabinet_monitor_config"


class CabinetMonitorTarget(BaseModel, TimestampMixin):
    target_key = fields.CharField(max_length=64, unique=True)
    metadata = fields.JSONField(default=dict)
    host_id = fields.CharField(max_length=20, default="")
    item_ids = fields.JSONField(default=list)
    status = fields.CharField(max_length=20, default="pending")
    reason = fields.CharField(max_length=300, default="")
    active = fields.BooleanField(default=True)
    notified = fields.JSONField(default=dict)
    notification_error = fields.CharField(max_length=300, default="")
    checked_at = fields.BigIntField(default=0)

    class Meta:
        table = "cabinet_monitor_target"
