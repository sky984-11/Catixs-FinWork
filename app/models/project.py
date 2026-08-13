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
    shared_users = fields.JSONField(default=list, description="共享用户")
    contract_no = fields.CharField(max_length=100, null=True, description="合同编号", index=True)
    start_date = fields.DateField(null=True, description="开始日期")
    due_date = fields.DateField(null=True, description="截止日期", index=True)
    progress = fields.IntField(default=0, description="进度")
    budget_amount = fields.FloatField(null=True, description="预算金额")
    budget_currency = fields.CharField(max_length=10, default="USD", description="预算币种")
    description = fields.TextField(null=True, description="项目说明")
    next_action = fields.CharField(max_length=255, null=True, description="下一步动作")
    sort_order = fields.IntField(default=0, description="看板排序")
    due_soon_notified_at = fields.DatetimeField(null=True, description="提前一天通知时间")
    due_notified_at = fields.DatetimeField(null=True, description="到期通知时间")

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
    due_date = fields.DatetimeField(null=True, description="截止时间", index=True)
    is_done = fields.BooleanField(default=False, description="是否完成", index=True)
    sort_order = fields.IntField(default=0, description="排序")
    remark = fields.CharField(max_length=500, null=True, description="备注")
    due_soon_notified_at = fields.DatetimeField(null=True, description="提前一天通知时间")
    due_notified_at = fields.DatetimeField(null=True, description="到期通知时间")

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
    file_url = fields.CharField(max_length=1000, description="文件地址")
    content_type = fields.CharField(max_length=100, null=True, description="文件类型")
    remark = fields.CharField(max_length=500, null=True, description="备注")

    class Meta:
        table = "customer_project_attachment"


class CustomerProjectDailySummary(BaseModel, TimestampMixin):
    summary_date = fields.DateField(unique=True, description="汇总日期", index=True)
    sent_at = fields.DatetimeField(null=True, description="发送时间")
    status = fields.CharField(max_length=20, default="pending", description="发送状态", index=True)
    message = fields.CharField(max_length=500, null=True, description="发送结果")

    class Meta:
        table = "customer_project_daily_summary"


class CustomerRequirement(BaseModel, TimestampMixin):
    title = fields.CharField(max_length=200, description="Requirement title", index=True)
    code = fields.CharField(max_length=50, null=True, description="Requirement code", index=True, unique=True)
    customer = fields.ForeignKeyField(
        "models.Company",
        related_name="customer_requirements",
        null=True,
        on_delete=fields.SET_NULL,
        description="Customer",
    )
    project = fields.ForeignKeyField(
        "models.CustomerProject",
        related_name="requirements",
        null=True,
        on_delete=fields.SET_NULL,
        description="Related project",
    )
    source = fields.CharField(max_length=30, default="customer", description="Requirement source", index=True)
    source_record_id = fields.CharField(max_length=100, null=True, description="Source record ID", index=True)
    source_detail = fields.CharField(max_length=200, null=True, description="Source detail")
    requirement_type = fields.CharField(max_length=30, default="feature", description="Requirement type", index=True)
    status = fields.CharField(max_length=30, default="pool", description="Requirement status", index=True)
    priority = fields.CharField(max_length=20, default="medium", description="Priority", index=True)
    owner = fields.CharField(max_length=100, null=True, description="Owner", index=True)
    requester = fields.CharField(max_length=100, null=True, description="Requester", index=True)
    service_type = fields.CharField(max_length=50, null=True, description="IDC service type", index=True)
    a_end = fields.CharField(max_length=200, null=True, description="A end")
    z_end = fields.CharField(max_length=200, null=True, description="Z end")
    region = fields.CharField(max_length=100, null=True, description="Service region", index=True)
    datacenter = fields.CharField(max_length=120, null=True, description="Datacenter")
    bandwidth = fields.CharField(max_length=100, null=True, description="Bandwidth requirement")
    ip_count = fields.IntField(default=0, description="IP count")
    cabinet_count = fields.FloatField(default=0, description="Cabinet count")
    server_count = fields.IntField(default=0, description="Server count")
    contract_term = fields.CharField(max_length=50, null=True, description="Contract term")
    budget_amount = fields.FloatField(null=True, description="Customer budget")
    budget_currency = fields.CharField(max_length=10, default="USD", description="Budget currency")
    nrc_amount = fields.FloatField(null=True, description="Expected NRC")
    expected_mrr = fields.FloatField(null=True, description="Expected MRR")
    target_price = fields.CharField(max_length=500, null=True, description="Target price")
    probability = fields.IntField(default=30, description="Win probability")
    competitor = fields.CharField(max_length=200, null=True, description="Competitor")
    next_action = fields.CharField(max_length=255, null=True, description="Next action")
    expected_at = fields.DateField(null=True, description="Expected date", index=True)
    planned_at = fields.DateField(null=True, description="Planned date")
    released_at = fields.DateField(null=True, description="Released date")
    value_score = fields.IntField(default=0, description="Value score")
    effort_score = fields.IntField(default=0, description="Effort score")
    confidence_score = fields.IntField(default=0, description="Confidence score")
    reach_score = fields.IntField(default=0, description="Reach score")
    vote_count = fields.IntField(default=0, description="Vote count")
    tags = fields.JSONField(default=list, description="Tags")
    related_links = fields.JSONField(default=list, description="Related links")
    description = fields.TextField(null=True, description="Description")
    acceptance_criteria = fields.TextField(null=True, description="Acceptance criteria")
    solution = fields.TextField(null=True, description="Solution")
    sort_order = fields.IntField(default=0, description="Sort order")

    class Meta:
        table = "customer_requirement"
