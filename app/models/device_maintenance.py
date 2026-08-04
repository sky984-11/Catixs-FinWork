from tortoise import fields

from .base import BaseModel, TimestampMixin


class DeviceMaintenanceTask(BaseModel, TimestampMixin):
    device = fields.ForeignKeyField(
        "models.AssetDevice",
        related_name="maintenance_tasks",
        on_delete=fields.CASCADE,
        description="关联设备",
        index=True,
    )
    device_ids = fields.JSONField(default=list, description="关联设备ID列表")
    title = fields.CharField(max_length=200, description="维护任务标题", index=True)
    description = fields.TextField(null=True, description="维护说明")
    assignee_id = fields.BigIntField(null=True, description="负责人ID", index=True)
    assignee_ids = fields.JSONField(default=list, description="负责人ID列表")
    assignee_name = fields.CharField(max_length=100, null=True, description="负责人名称", index=True)
    assignee_names = fields.CharField(max_length=500, null=True, description="负责人名称列表")
    due_at = fields.DatetimeField(null=True, description="计划维护时间", index=True)
    status = fields.CharField(max_length=20, default="pending", description="任务状态", index=True)
    priority = fields.CharField(max_length=20, default="medium", description="优先级", index=True)
    notified_at = fields.DatetimeField(null=True, description="飞书通知时间")
    reminder_notified_at = fields.DatetimeField(null=True, description="计划前一天提醒时间", index=True)
    notify_status = fields.CharField(max_length=20, default="pending", description="通知状态", index=True)
    notify_message = fields.CharField(max_length=500, null=True, description="通知结果")
    remark = fields.CharField(max_length=500, null=True, description="备注")

    class Meta:
        table = "device_maintenance_task"
