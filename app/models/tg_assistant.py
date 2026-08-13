from tortoise import fields

from .base import BaseModel, TimestampMixin


class TGAssistantConfig(BaseModel, TimestampMixin):
    user = fields.ForeignKeyField("models.User", related_name="tg_assistant_configs", on_delete=fields.CASCADE)
    is_enabled = fields.BooleanField(default=False, description="是否启用", index=True)
    source_user_keywords = fields.JSONField(default=list, description="通知用户/发送人关键词")
    content_keywords = fields.JSONField(default=list, description="内容关键词")
    mention_keywords = fields.JSONField(default=list, description="@关键词")
    ignored_keywords = fields.JSONField(default=list, description="忽略关键词")
    event_types = fields.JSONField(default=list, description="Chatwoot事件")
    message_types = fields.JSONField(default=list, description="消息类型")
    include_private = fields.BooleanField(default=False, description="是否包含私密消息")
    show_message_detail = fields.BooleanField(default=True, description="是否展示消息内容")

    class Meta:
        table = "tg_assistant_config"


class TGAssistantDeliveryLog(BaseModel, TimestampMixin):
    user = fields.ForeignKeyField("models.User", related_name="tg_assistant_logs", null=True, on_delete=fields.SET_NULL)
    event = fields.CharField(max_length=50, default="", description="Chatwoot事件", index=True)
    message_type = fields.CharField(max_length=30, default="", description="消息类型", index=True)
    conversation_id = fields.CharField(max_length=100, default="", description="会话ID", index=True)
    sender_name = fields.CharField(max_length=200, default="", description="发送人")
    contact_name = fields.CharField(max_length=200, default="", description="联系人")
    status = fields.CharField(max_length=30, default="", description="投递状态", index=True)
    reason = fields.CharField(max_length=500, default="", description="原因")
    matched_rule = fields.CharField(max_length=500, default="", description="命中规则")
    content_excerpt = fields.TextField(null=True, description="内容摘要")

    class Meta:
        table = "tg_assistant_delivery_log"
