from tortoise import fields

from .base import BaseModel, TimestampMixin


class Ticket(BaseModel, TimestampMixin):
    """工单模型"""
    
    title = fields.CharField(max_length=200, description="工单标题", index=True)
    
    # 工单状态：0-已完成, 1-进行中, 2-未开始, 3-已关闭
    status = fields.IntField(default=2, description="工单状态", index=True)
    
    # 工单类型：0-故障工单(INC), 1-服务请求工单(REQ), 2-维护工单(MTN)
    type = fields.IntField(default=0, description="工单类型", index=True)
    
    # 外键，工单所属用户
    user_id = fields.BigIntField(null=True, description="工单所属用户ID", index=True)
    
    # 工单描述
    desc = fields.TextField(null=True, description="工单描述")
    
    # 发生地点
    location = fields.CharField(max_length=200, null=True, description="发生地点")
    
    # 开始时间
    start_time = fields.DatetimeField(null=True, description="开始时间")
    
    # 结束时间
    end_time = fields.DatetimeField(null=True, description="结束时间")
    
    # 附件链接
    attachment_url = fields.CharField(max_length=500, null=True, description="附件链接")
    
    # 工单编号，{工单类型}-{日期}-{序号}
    ticket_no = fields.CharField(max_length=50, description="工单编号", unique=True, index=True)
    
    # 当前处理人id
    assignee_id = fields.BigIntField(null=True, description="当前处理人ID", index=True)
    
    class Meta:
        table = "ticket"
        app = "models"
