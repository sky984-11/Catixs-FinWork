from tortoise import fields

from .base import BaseModel, TimestampMixin


class MonitorEventConfig(BaseModel, TimestampMixin):
    revision = fields.IntField(default=1)
    category_tag = fields.CharField(max_length=255, default="business_category")
    categories = fields.JSONField(default=list)
    hosts = fields.JSONField(default=list)
    updated_by_id = fields.BigIntField()

    class Meta:
        table = "monitor_event_config"
