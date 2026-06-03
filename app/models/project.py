from tortoise import fields

from .base import BaseModel, TimestampMixin


class CustomerProject(BaseModel, TimestampMixin):
    name = fields.CharField(max_length=120, description="项目名称", index=True)
    code = fields.CharField(max_length=50, null=True, description="项目编号", index=True, unique=True)
    customer = fields.ForeignKeyField(
        "models.Company",
        related_name="customer_projects",
        null=True,
        on_delete=fields.SET_NULL,
        description="客户",
    )
    status = fields.CharField(max_length=30, default="planning", description="项目状态", index=True)
    priority = fields.CharField(max_length=20, default="medium", description="优先级", index=True)
    health = fields.CharField(max_length=20, default="green", description="健康度", index=True)
    owner = fields.CharField(max_length=100, null=True, description="负责人", index=True)
    contract_no = fields.CharField(max_length=100, null=True, description="合同编号", index=True)
    start_date = fields.DateField(null=True, description="开始日期")
    due_date = fields.DateField(null=True, description="截止日期", index=True)
    progress = fields.IntField(default=0, description="进度")
    budget_amount = fields.FloatField(null=True, description="预算金额")
    budget_currency = fields.CharField(max_length=10, default="USD", description="预算币种")
    description = fields.TextField(null=True, description="项目说明")
    next_action = fields.CharField(max_length=255, null=True, description="下一步动作")
    sort_order = fields.IntField(default=0, description="看板排序")

    class Meta:
        table = "customer_project"


class CustomerProjectDiscussion(BaseModel, TimestampMixin):
    project = fields.ForeignKeyField(
        "models.CustomerProject",
        related_name="discussions",
        on_delete=fields.CASCADE,
        description="项目",
    )
    author_id = fields.BigIntField(null=True, description="讨论人ID", index=True)
    content = fields.TextField(description="讨论内容")
    task = fields.ForeignKeyField(
        "models.CustomerProjectTask",
        related_name="referenced_discussions",
        null=True,
        on_delete=fields.SET_NULL,
        description="引用任务",
    )
    attachment = fields.ForeignKeyField(
        "models.CustomerProjectAttachment",
        related_name="referenced_discussions",
        null=True,
        on_delete=fields.SET_NULL,
        description="引用截图",
    )

    class Meta:
        table = "customer_project_discussion"


class CustomerProjectTask(BaseModel, TimestampMixin):
    project = fields.ForeignKeyField(
        "models.CustomerProject",
        related_name="tasks",
        on_delete=fields.CASCADE,
        description="项目",
    )
    title = fields.CharField(max_length=200, description="任务标题", index=True)
    assignee = fields.CharField(max_length=100, null=True, description="负责人", index=True)
    due_date = fields.DateField(null=True, description="截止日期", index=True)
    is_done = fields.BooleanField(default=False, description="是否完成", index=True)
    sort_order = fields.IntField(default=0, description="排序")
    remark = fields.CharField(max_length=500, null=True, description="备注")

    class Meta:
        table = "customer_project_task"


class CustomerProjectAttachment(BaseModel, TimestampMixin):
    project = fields.ForeignKeyField(
        "models.CustomerProject",
        related_name="attachments",
        on_delete=fields.CASCADE,
        description="项目",
    )
    task = fields.ForeignKeyField(
        "models.CustomerProjectTask",
        related_name="attachments",
        null=True,
        on_delete=fields.CASCADE,
        description="关联任务",
    )
    uploader_id = fields.BigIntField(null=True, description="上传人ID", index=True)
    name = fields.CharField(max_length=200, description="资料名称")
    file_url = fields.CharField(max_length=255, description="文件地址")
    content_type = fields.CharField(max_length=100, null=True, description="文件类型")
    remark = fields.CharField(max_length=500, null=True, description="备注")

    class Meta:
        table = "customer_project_attachment"
