from pydantic import BaseModel, Field


class TGAssistantConfigUpdate(BaseModel):
    is_enabled: bool = Field(False, description="是否启用")
    source_user_keywords: list[str] = Field(default_factory=list, description="通知用户/发送人关键词")
    content_keywords: list[str] = Field(default_factory=list, description="内容关键词")
    mention_keywords: list[str] = Field(default_factory=list, description="@关键词")
    ignored_keywords: list[str] = Field(default_factory=list, description="忽略关键词")
    event_types: list[str] = Field(default_factory=list, description="Chatwoot事件")
    message_types: list[str] = Field(default_factory=list, description="消息类型")
    include_private: bool = Field(False, description="是否包含私密消息")
    show_message_detail: bool = Field(True, description="是否展示消息内容")
