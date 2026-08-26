from datetime import datetime
from typing import Any

from tortoise import fields
from tortoise.fields.data import parse_datetime

from .base import BaseModel, TimestampMixin


LOCAL_TIMEZONE = datetime.now().astimezone().tzinfo


def _to_naive_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, int):
        value = datetime.fromtimestamp(value)
    elif not isinstance(value, datetime):
        value = parse_datetime(value)
    if value is not None and value.tzinfo:
        value = value.astimezone(LOCAL_TIMEZONE)
    return value.replace(tzinfo=None) if value else None


class NaiveDatetimeField(fields.DatetimeField):
    def to_db_value(self, value: Any, instance: Any) -> datetime | None:
        if hasattr(instance, "_saved_in_db") and (
            self.auto_now
            or (self.auto_now_add and getattr(instance, self.model_field_name) is None)
        ):
            value = datetime.now().replace(tzinfo=None)
            setattr(instance, self.model_field_name, value)
            return value
        return _to_naive_datetime(value)

    def to_python_value(self, value: Any) -> datetime | None:
        return _to_naive_datetime(value)


class RemoteEngineer(BaseModel, TimestampMixin):
    created_at = NaiveDatetimeField(auto_now_add=True, index=True)
    updated_at = NaiveDatetimeField(auto_now=True, index=True)

    source_id = fields.BigIntField(null=True, unique=True, description="external source id", index=True)
    name = fields.CharField(max_length=100, description="engineer name", index=True)
    contact = fields.CharField(max_length=180, null=True, description="contact")
    wechat_id = fields.CharField(max_length=180, null=True, description="wechat")
    wechat_group = fields.CharField(max_length=180, null=True, description="wechat group")
    region = fields.CharField(max_length=500, null=True, description="region", index=True)
    is_active = fields.IntField(default=1, description="is active", index=True)
    note = fields.TextField(null=True, description="note")

    class Meta:
        table = "remote_engineer"


class RemoteHands(BaseModel, TimestampMixin):
    created_at = NaiveDatetimeField(auto_now_add=True, index=True)
    updated_at = NaiveDatetimeField(auto_now=True, index=True)

    source_id = fields.BigIntField(null=True, unique=True, description="external source id", index=True)
    customer = fields.CharField(max_length=200, description="customer", index=True)
    ticket = fields.CharField(max_length=120, null=True, description="ticket", index=True)
    engineer = fields.ForeignKeyField(
        "models.RemoteEngineer",
        related_name="remote_hands",
        null=True,
        on_delete=fields.SET_NULL,
        description="engineer",
    )
    engineer_name = fields.CharField(max_length=100, null=True, description="engineer name", index=True)
    engineer_contact = fields.CharField(max_length=180, null=True, description="engineer contact")
    engineer_wechat = fields.CharField(max_length=180, null=True, description="engineer wechat")
    engineer_group = fields.CharField(max_length=180, null=True, description="engineer group")
    region = fields.CharField(max_length=180, null=True, description="region", index=True)
    site = fields.CharField(max_length=180, null=True, description="site", index=True)
    rack = fields.CharField(max_length=100, null=True, description="rack")
    timezone = fields.CharField(max_length=80, default="Asia/Shanghai", description="timezone")
    arrived_at = NaiveDatetimeField(null=True, description="arrived at", index=True)
    left_at = NaiveDatetimeField(null=True, description="left at", index=True)
    work_minutes = fields.IntField(default=0, description="work minutes")
    status = fields.CharField(max_length=30, default="scheduled", description="status", index=True)
    is_settled = fields.BooleanField(default=False, description="is settled", index=True)
    ops_settlement_status = fields.CharField(max_length=30, default="unbilled", description="ops settlement status", index=True)
    customer_settlement_status = fields.CharField(max_length=30, default="unbilled", description="customer settlement status", index=True)
    note = fields.TextField(null=True, description="note")

    class Meta:
        table = "remote_hands"


class RemoteHandsPlan(BaseModel, TimestampMixin):
    created_at = NaiveDatetimeField(auto_now_add=True, index=True)
    updated_at = NaiveDatetimeField(auto_now=True, index=True)

    customer = fields.CharField(max_length=200, description="customer", index=True)
    ticket = fields.CharField(max_length=120, null=True, description="ticket", index=True)
    engineer = fields.ForeignKeyField(
        "models.RemoteEngineer",
        related_name="remote_hands_plans",
        null=True,
        on_delete=fields.SET_NULL,
        description="engineer",
    )
    engineer_name = fields.CharField(max_length=100, null=True, description="engineer name", index=True)
    engineer_contact = fields.CharField(max_length=180, null=True, description="engineer contact")
    engineer_wechat = fields.CharField(max_length=180, null=True, description="engineer wechat")
    engineer_group = fields.CharField(max_length=180, null=True, description="engineer group")
    assignee_id = fields.BigIntField(null=True, description="assignee id", index=True)
    assignee_ids = fields.JSONField(default=list, description="assignee ids")
    assignee_name = fields.CharField(max_length=100, null=True, description="assignee name")
    assignee_names = fields.CharField(max_length=500, null=True, description="assignee names")
    created_by_id = fields.BigIntField(null=True, description="creator user id")
    created_by_name = fields.CharField(max_length=100, null=True, description="creator user name")
    region = fields.CharField(max_length=180, null=True, description="region", index=True)
    site = fields.CharField(max_length=180, null=True, description="site", index=True)
    rack = fields.CharField(max_length=100, null=True, description="rack")
    timezone = fields.CharField(max_length=80, default="Asia/Shanghai", description="timezone")
    planned_at = NaiveDatetimeField(null=True, description="planned at", index=True)
    status = fields.CharField(max_length=30, default="pending", description="status", index=True)
    notify_status = fields.CharField(max_length=20, default="pending", description="notify status", index=True)
    notify_message = fields.CharField(max_length=500, null=True, description="notify message")
    notified_at = NaiveDatetimeField(null=True, description="notified at")
    reminder_notified_at = NaiveDatetimeField(null=True, description="reminder notified at", index=True)
    remote_hands_id = fields.BigIntField(null=True, description="remote hands id", index=True)
    note = fields.TextField(null=True, description="note")

    class Meta:
        table = "remote_hands_plan"
