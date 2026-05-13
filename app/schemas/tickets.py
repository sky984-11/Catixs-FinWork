from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class BaseTicket(BaseModel):
    """工单基础模型"""
    id: int
    title: Optional[str] = None
    status: Optional[int] = None
    type: Optional[int] = None
    user_id: Optional[int] = None
    desc: Optional[str] = None
    location: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    attachment_url: Optional[str] = None
    ticket_no: Optional[str] = None
    assignee_id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class TicketCreate(BaseModel):
    """创建工单请求模型"""
    title: str = Field(..., example="服务器磁盘空间不足")
    type: int = Field(0, description="工单类型：0-故障工单, 1-服务请求, 2-变更工单, 3-维护工单", example=0)
    user_id: Optional[int] = Field(None, description="工单所属用户ID", example=1)
    desc: str = Field("", description="工单描述", example="服务器磁盘使用率达到95%，需要清理空间")
    location: str = Field("", description="发生地点", example="数据中心A区")
    start_time: Optional[datetime] = Field(None, description="开始时间")
    end_time: Optional[datetime] = Field(None, description="结束时间")
    attachment_url: str = Field("", description="附件链接")
    assignee_id: Optional[int] = Field(None, description="处理人ID")


class TicketUpdate(BaseModel):
    """更新工单请求模型"""
    id: Optional[int] = Field(None, example=1)
    ticket_no: Optional[str] = Field(None, description="工单编号")
    title: Optional[str] = Field(None, example="服务器磁盘空间不足")
    status: Optional[int] = Field(None, description="工单状态：0-已完成, 1-进行中, 2-未开始, 3-已关闭", example=1)
    type: Optional[int] = Field(None, description="工单类型：0-故障工单, 1-服务请求, 2-变更工单, 3-维护工单", example=0)
    user_id: Optional[int] = Field(None, description="工单所属用户ID", example=1)
    desc: Optional[str] = Field(None, description="工单描述")
    location: Optional[str] = Field(None, description="发生地点")
    start_time: Optional[datetime] = Field(None, description="开始时间")
    end_time: Optional[datetime] = Field(None, description="结束时间")
    attachment_url: Optional[str] = Field(None, description="附件链接")
    assignee_id: Optional[int] = Field(None, description="处理人ID")


class TicketQuery(BaseModel):
    """工单查询参数"""
    title: Optional[str] = Field(None, description="工单标题")
    status: Optional[int] = Field(None, description="工单状态")
    type: Optional[int] = Field(None, description="工单类型")
    user_id: Optional[int] = Field(None, description="用户ID")
    assignee_id: Optional[int] = Field(None, description="处理人ID")
