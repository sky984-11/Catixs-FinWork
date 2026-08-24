from tortoise import fields

from .base import BaseModel, TimestampMixin


class CrmSigningEntity(BaseModel, TimestampMixin):
    name = fields.CharField(max_length=120, description="签约主体名称", index=True, unique=True)
    legal_name = fields.CharField(max_length=200, null=True, description="签约主体全称", index=True)
    code = fields.CharField(max_length=50, null=True, description="主体编号", index=True, unique=True)
    country = fields.CharField(max_length=80, null=True, description="国家/地区", index=True)
    address = fields.CharField(max_length=255, null=True, description="注册地址")
    tax_no = fields.CharField(max_length=80, null=True, description="税号")
    registration_no = fields.CharField(max_length=80, null=True, description="注册号")
    logo_url = fields.CharField(max_length=255, null=True, description="Logo")
    status = fields.BooleanField(default=True, description="状态", index=True)
    remark = fields.CharField(max_length=500, null=True, description="备注")

    class Meta:
        table = "crm_signing_entity"


class CrmCustomer(BaseModel, TimestampMixin):
    customer_code = fields.CharField(max_length=60, null=True, description="客户编号", index=True, unique=True)
    name = fields.CharField(max_length=120, description="客户简称", index=True)
    legal_name = fields.CharField(max_length=240, null=True, description="客户全称", index=True)
    alias = fields.CharField(max_length=120, null=True, description="客户别名", index=True)
    entity_type = fields.CharField(max_length=30, default="enterprise", description="主体类型", index=True)
    signing_entity = fields.ForeignKeyField(
        "models.CrmSigningEntity",
        related_name="customers",
        null=True,
        on_delete=fields.SET_NULL,
        description="签约主体",
    )
    customer_level = fields.CharField(max_length=10, default="C", description="客户等级", index=True)
    lifecycle = fields.CharField(max_length=30, default="active", description="客户生命周期", index=True)
    sales_owner = fields.CharField(max_length=100, null=True, description="所属销售", index=True)
    region = fields.CharField(max_length=100, null=True, description="所属地区", index=True)
    address = fields.CharField(max_length=255, null=True, description="联系地址")
    invoice_info = fields.TextField(null=True, description="开票信息")
    finance_info = fields.TextField(null=True, description="财务信息")
    basic_info = fields.TextField(null=True, description="基本信息")
    remark = fields.TextField(null=True, description="备注")
    status = fields.BooleanField(default=True, description="状态", index=True)

    class Meta:
        table = "crm_customer"


class CrmCustomerContact(BaseModel, TimestampMixin):
    customer = fields.ForeignKeyField(
        "models.CrmCustomer",
        related_name="contacts",
        on_delete=fields.CASCADE,
        description="客户",
    )
    contact_type = fields.CharField(max_length=30, default="person", description="联系人类型", index=True)
    name = fields.CharField(max_length=100, description="联系人姓名", index=True)
    role = fields.CharField(max_length=30, default="business", description="联系人角色", index=True)
    title = fields.CharField(max_length=100, null=True, description="职位")
    email = fields.CharField(max_length=160, null=True, description="邮箱", index=True)
    phone = fields.CharField(max_length=80, null=True, description="电话", index=True)
    address = fields.CharField(max_length=255, null=True, description="联系地址")
    remark = fields.CharField(max_length=500, null=True, description="备注")
    status = fields.BooleanField(default=True, description="状态", index=True)

    class Meta:
        table = "crm_customer_contact"


class CrmCustomerContract(BaseModel, TimestampMixin):
    customer = fields.ForeignKeyField(
        "models.CrmCustomer",
        related_name="contracts",
        on_delete=fields.CASCADE,
        description="签约客户",
    )
    signing_entity = fields.ForeignKeyField(
        "models.CrmSigningEntity",
        related_name="contracts",
        null=True,
        on_delete=fields.SET_NULL,
        description="签约主体",
    )
    contract_no = fields.CharField(max_length=100, null=True, description="合同编号", index=True, unique=True)
    name = fields.CharField(max_length=240, description="合同名称", index=True)
    status = fields.CharField(max_length=40, default="draft", description="合同状态", index=True)
    effective_date = fields.DateField(null=True, description="生效日期", index=True)
    expiry_date = fields.DateField(null=True, description="到期日期", index=True)
    amount = fields.DecimalField(max_digits=16, decimal_places=2, default=0, description="合同金额")
    currency = fields.CharField(max_length=12, default="USD", description="币种", index=True)
    attachment_url = fields.CharField(max_length=500, null=True, description="合同附件")
    reminder_days = fields.IntField(default=30, description="到期提醒天数")
    reminder_enabled = fields.BooleanField(default=True, description="是否提醒", index=True)
    remark = fields.TextField(null=True, description="备注")

    class Meta:
        table = "crm_customer_contract"


class CrmCustomerBill(BaseModel, TimestampMixin):
    customer = fields.ForeignKeyField(
        "models.CrmCustomer",
        related_name="bills",
        on_delete=fields.CASCADE,
        description="客户",
    )
    bill_no = fields.CharField(max_length=100, null=True, description="账单编号", index=True, unique=True)
    title = fields.CharField(max_length=160, description="账单名称", index=True)
    status = fields.CharField(max_length=40, default="draft", description="账单状态", index=True)
    amount = fields.DecimalField(max_digits=16, decimal_places=2, default=0, description="账单金额")
    currency = fields.CharField(max_length=12, default="USD", description="币种", index=True)
    bill_date = fields.DateField(null=True, description="账单日期", index=True)
    due_date = fields.DateField(null=True, description="到期日期", index=True)
    is_settled = fields.BooleanField(default=False, description="已结算", index=True)
    business_closed = fields.BooleanField(default=False, description="无后续业务往来", index=True)
    remark = fields.TextField(null=True, description="备注")

    class Meta:
        table = "crm_customer_bill"
