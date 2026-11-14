from tortoise import fields

from .base import BaseModel, TimestampMixin


class MonitorNotificationConfig(BaseModel, TimestampMixin):
    revision = fields.IntField(default=0)
    enabled = fields.BooleanField(default=False)
    recipient_ids = fields.JSONField(default=list)
    category_keys = fields.JSONField(default=list)
    minimum_severity = fields.IntField(default=2)
    notify_recovery = fields.BooleanField(default=True)
    skip_suppressed = fields.BooleanField(default=True)
    ai_enabled = fields.BooleanField(default=True)
    enabled_since = fields.BigIntField(default=0)
    lease_until = fields.BigIntField(default=0)
    lease_token = fields.CharField(max_length=36, default="")
    last_poll_at = fields.BigIntField(default=0)
    last_error = fields.CharField(max_length=300, default="")
    updated_by_id = fields.BigIntField(default=0)

    class Meta:
        table = "monitor_notification_config"


class MonitorNotificationDelivery(BaseModel, TimestampMixin):
    event_id = fields.CharField(max_length=20, index=True)
    phase = fields.CharField(max_length=10)
    user_id = fields.BigIntField(index=True)
    status = fields.CharField(max_length=16, default="pending", index=True)
    attempts = fields.IntField(default=0)
    message = fields.CharField(max_length=300, default="")
    event_name = fields.CharField(max_length=255, default="")
    advice = fields.TextField(default="")
    advice_source = fields.CharField(max_length=16, default="rule")
    sent_at = fields.BigIntField(default=0)
    recovery_done = fields.BooleanField(default=False)

    class Meta:
        table = "monitor_notification_delivery"
        unique_together = (("event_id", "phase", "user_id"),)
