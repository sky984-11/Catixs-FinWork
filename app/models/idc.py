"""IDC order, service and billing records. Existing ticket/bill IDs remain authoritative."""

from tortoise import fields

from .base import BaseModel, TimestampMixin


class IdcAccount(BaseModel, TimestampMixin):
    customer = fields.ForeignKeyField("models.CrmCustomer", on_delete=fields.RESTRICT)
    signing_entity = fields.ForeignKeyField("models.CrmSigningEntity", on_delete=fields.RESTRICT)
    company = fields.ForeignKeyField("models.Company", on_delete=fields.RESTRICT)
    user_ids = fields.JSONField(default=list)
    active = fields.BooleanField(default=True)

    class Meta:
        table = "idc_account"
        unique_together = (("customer", "signing_entity"),)


class IdcOrder(BaseModel, TimestampMixin):
    ticket = fields.OneToOneField("models.Ticket", on_delete=fields.RESTRICT, related_name="idc_order")
    account = fields.ForeignKeyField("models.IdcAccount", on_delete=fields.RESTRICT)
    action = fields.CharField(max_length=24)
    contact = fields.CharField(max_length=200)
    requested_date = fields.DateField(null=True)
    reference = fields.CharField(max_length=200, default="")
    request_key = fields.CharField(max_length=80, unique=True)

    class Meta:
        table = "idc_order"


class CustomerService(BaseModel, TimestampMixin):
    account = fields.ForeignKeyField("models.IdcAccount", on_delete=fields.RESTRICT)
    service_no = fields.CharField(max_length=64, unique=True)
    product = fields.ForeignKeyField("models.ProductItem", on_delete=fields.RESTRICT)
    product_code = fields.CharField(max_length=80)
    name = fields.CharField(max_length=200)
    parent = fields.ForeignKeyField("models.CustomerService", null=True, on_delete=fields.RESTRICT)
    anchor = fields.DateField()

    class Meta:
        table = "idc_customer_service"


class IdcOrderLine(BaseModel, TimestampMixin):
    order = fields.ForeignKeyField("models.IdcOrder", on_delete=fields.RESTRICT, related_name="lines")
    product = fields.ForeignKeyField("models.ProductItem", on_delete=fields.RESTRICT)
    product_code = fields.CharField(max_length=80)
    parent = fields.ForeignKeyField("models.IdcOrderLine", null=True, on_delete=fields.RESTRICT)
    service = fields.ForeignKeyField("models.CustomerService", null=True, on_delete=fields.RESTRICT)
    quantity = fields.DecimalField(max_digits=16, decimal_places=4, default=1)
    parameters = fields.JSONField(default=dict)
    schema_snapshot = fields.JSONField(default=dict)
    stage = fields.CharField(max_length=24, default="draft", index=True)
    revision = fields.IntField(default=1)
    quote_version = fields.IntField(default=0)
    delivery = fields.JSONField(default=dict)
    acceptance = fields.JSONField(default=dict)

    class Meta:
        table = "idc_order_line"


class IdcQuote(BaseModel, TimestampMixin):
    line = fields.ForeignKeyField("models.IdcOrderLine", on_delete=fields.RESTRICT, related_name="quotes")
    version = fields.IntField()
    line_revision = fields.IntField()
    currency = fields.CharField(max_length=8)
    charges = fields.JSONField(default=list)
    terms = fields.JSONField(default=dict)
    valid_until = fields.DateField()
    status = fields.CharField(max_length=24, default="draft")
    author_id = fields.BigIntField()
    approved_by = fields.BigIntField(null=True)
    confirmed_by = fields.BigIntField(null=True)
    confirmation = fields.CharField(max_length=1000, default="")

    class Meta:
        table = "idc_quote"
        unique_together = (("line", "version"),)


class IdcDeliveryTask(BaseModel, TimestampMixin):
    line = fields.ForeignKeyField("models.IdcOrderLine", on_delete=fields.RESTRICT)
    department = fields.CharField(max_length=40)
    assignee_id = fields.BigIntField(null=True)
    status = fields.CharField(max_length=24, default="pending")
    evidence = fields.TextField(default="")

    class Meta:
        table = "idc_delivery_task"
        unique_together = (("line", "department"),)


class ServiceVersion(BaseModel, TimestampMixin):
    service = fields.ForeignKeyField("models.CustomerService", on_delete=fields.RESTRICT, related_name="versions")
    source_line = fields.OneToOneField("models.IdcOrderLine", on_delete=fields.RESTRICT)
    quote = fields.ForeignKeyField("models.IdcQuote", on_delete=fields.RESTRICT)
    starts_on = fields.DateField(index=True)
    ends_before = fields.DateField(null=True, index=True)
    state = fields.CharField(max_length=24, default="active")
    quantity = fields.DecimalField(max_digits=16, decimal_places=4)
    parameters = fields.JSONField(default=dict)
    delivery = fields.JSONField(default=dict)

    class Meta:
        table = "idc_service_version"
        unique_together = (("service", "starts_on"),)


class ServiceResourceBinding(BaseModel, TimestampMixin):
    line = fields.ForeignKeyField("models.IdcOrderLine", on_delete=fields.RESTRICT)
    service = fields.ForeignKeyField("models.CustomerService", null=True, on_delete=fields.RESTRICT)
    kind = fields.CharField(max_length=30)
    resource_key = fields.CharField(max_length=180, index=True)
    exclusive_key = fields.CharField(max_length=220, unique=True, null=True)
    details = fields.JSONField(default=dict)
    state = fields.CharField(max_length=24, default="reserved")

    class Meta:
        table = "idc_resource_binding"


class ServiceCharge(BaseModel, TimestampMixin):
    version = fields.ForeignKeyField("models.ServiceVersion", on_delete=fields.RESTRICT, related_name="charges")
    code = fields.CharField(max_length=64)
    kind = fields.CharField(max_length=24)
    name = fields.CharField(max_length=160)
    unit_price = fields.DecimalField(max_digits=18, decimal_places=6)
    tax_rate = fields.DecimalField(max_digits=8, decimal_places=6, default=0)
    rule = fields.JSONField(default=dict)
    included = fields.BooleanField(default=False)

    class Meta:
        table = "idc_service_charge"
        unique_together = (("version", "code"),)


class IdcUsage(BaseModel, TimestampMixin):
    charge = fields.ForeignKeyField("models.ServiceCharge", on_delete=fields.RESTRICT)
    starts_on = fields.DateField()
    ends_before = fields.DateField()
    quantity = fields.DecimalField(max_digits=20, decimal_places=6)
    evidence = fields.CharField(max_length=1000)
    recorded_by = fields.BigIntField()

    class Meta:
        table = "idc_usage"
        unique_together = (("charge", "starts_on", "ends_before"),)


class IdcBillingEvent(BaseModel, TimestampMixin):
    account = fields.ForeignKeyField("models.IdcAccount", on_delete=fields.RESTRICT)
    service = fields.ForeignKeyField("models.CustomerService", null=True, on_delete=fields.RESTRICT)
    event_key = fields.CharField(max_length=200, unique=True)
    currency = fields.CharField(max_length=8)
    amount = fields.DecimalField(max_digits=18, decimal_places=2)
    tax = fields.DecimalField(max_digits=18, decimal_places=2, default=0)
    due_on = fields.DateField()
    kind = fields.CharField(max_length=24)
    description = fields.CharField(max_length=500)
    source = fields.JSONField(default=dict)

    class Meta:
        table = "idc_billing_event"


class IdcBillingRun(BaseModel, TimestampMixin):
    account = fields.ForeignKeyField("models.IdcAccount", on_delete=fields.RESTRICT)
    month = fields.DateField()
    currency = fields.CharField(max_length=8)
    bill = fields.OneToOneField("models.Bill", null=True, on_delete=fields.RESTRICT)
    revision = fields.IntField(default=1)

    class Meta:
        table = "idc_billing_run"
        unique_together = (("account", "month", "currency"),)


class IdcBillAllocation(BaseModel, TimestampMixin):
    run = fields.ForeignKeyField("models.IdcBillingRun", on_delete=fields.RESTRICT)
    item = fields.OneToOneField("models.BillItem", on_delete=fields.RESTRICT)
    allocation_key = fields.CharField(max_length=220, unique=True)
    amount = fields.DecimalField(max_digits=18, decimal_places=2)
    tax = fields.DecimalField(max_digits=18, decimal_places=2)
    snapshot = fields.JSONField(default=dict)

    class Meta:
        table = "idc_bill_allocation"


class IdcAudit(BaseModel, TimestampMixin):
    actor_id = fields.BigIntField()
    action = fields.CharField(max_length=64)
    object_type = fields.CharField(max_length=30)
    object_id = fields.BigIntField()
    data = fields.JSONField(default=dict)

    class Meta:
        table = "idc_audit"
