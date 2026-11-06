from tortoise import fields

from .base import BaseModel, TimestampMixin


class CrmBillingDocument(BaseModel, TimestampMixin):
    bill = fields.OneToOneField("models.CrmCustomerBill", related_name="document", on_delete=fields.RESTRICT)
    request_key = fields.CharField(max_length=80, unique=True)
    request_hash = fields.CharField(max_length=64)
    created_by_id = fields.BigIntField()
    customer_snapshot = fields.JSONField(default=dict)
    lines = fields.JSONField(default=list)
    settings = fields.JSONField(default=dict)
    period_start = fields.DateField()
    period_end = fields.DateField()
    subtotal = fields.DecimalField(max_digits=16, decimal_places=2)
    discount = fields.DecimalField(max_digits=16, decimal_places=2, default=0)
    adjustment = fields.DecimalField(max_digits=16, decimal_places=2, default=0)
    tax_rate = fields.DecimalField(max_digits=7, decimal_places=4, default=0)
    tax_amount = fields.DecimalField(max_digits=16, decimal_places=2, default=0)
    paid_amount = fields.DecimalField(max_digits=16, decimal_places=2, default=0)
    local_currency = fields.CharField(max_length=12)
    fx_rate = fields.DecimalField(max_digits=18, decimal_places=8, default=1)
    fx_source = fields.CharField(max_length=160)
    fx_date = fields.DateField()
    local_amount = fields.DecimalField(max_digits=16, decimal_places=2)
    issued_at = fields.DatetimeField(null=True)
    reminder_level = fields.IntField(default=0)

    class Meta:
        table = "crm_billing_document"


class CrmBillingPlan(BaseModel, TimestampMixin):
    name = fields.CharField(max_length=160)
    customer = fields.ForeignKeyField("models.CrmCustomer", related_name="billing_plans", on_delete=fields.RESTRICT)
    created_by_id = fields.BigIntField()
    template = fields.JSONField()
    order_snapshot = fields.JSONField()
    next_period = fields.DateField()
    next_run = fields.DateField(index=True)
    enabled = fields.BooleanField(default=True)
    last_attempt = fields.DateField(null=True)
    last_error = fields.CharField(max_length=500, default="")

    class Meta:
        table = "crm_billing_plan"


class CrmBillingPlanOrder(BaseModel):
    plan = fields.ForeignKeyField("models.CrmBillingPlan", related_name="orders", on_delete=fields.RESTRICT)
    order = fields.ForeignKeyField("models.ProductOrder", related_name="billing_plans", on_delete=fields.RESTRICT)

    class Meta:
        table = "crm_billing_plan_order"
        unique_together = (("plan", "order"),)


class CrmBillingAllocation(BaseModel):
    document = fields.ForeignKeyField(
        "models.CrmBillingDocument", related_name="allocations", on_delete=fields.RESTRICT
    )
    order = fields.ForeignKeyField("models.ProductOrder", related_name="billing_allocations", on_delete=fields.RESTRICT)
    currency = fields.CharField(max_length=12)
    period_start = fields.DateField()
    period_end = fields.DateField()
    includes_nrc = fields.BooleanField(default=False)

    class Meta:
        table = "crm_billing_allocation"
        unique_together = (("document", "order", "currency"),)


class CrmBillingPayment(BaseModel, TimestampMixin):
    document = fields.ForeignKeyField("models.CrmBillingDocument", related_name="payments", on_delete=fields.RESTRICT)
    reference = fields.CharField(max_length=100)
    payment_date = fields.DateField()
    amount = fields.DecimalField(max_digits=16, decimal_places=2)
    currency = fields.CharField(max_length=12)
    method = fields.CharField(max_length=80)
    remark = fields.CharField(max_length=500, default="")
    reversed = fields.BooleanField(default=False)
    operator_id = fields.BigIntField()

    class Meta:
        table = "crm_billing_payment"
        unique_together = (("document", "reference"),)


class CrmBillingAudit(BaseModel, TimestampMixin):
    document = fields.ForeignKeyField("models.CrmBillingDocument", related_name="audits", on_delete=fields.RESTRICT)
    action = fields.CharField(max_length=40)
    operator_id = fields.BigIntField()
    operator_name = fields.CharField(max_length=100)
    before = fields.JSONField(default=dict)
    after = fields.JSONField(default=dict)
    comment = fields.CharField(max_length=500, default="")

    class Meta:
        table = "crm_billing_audit"
