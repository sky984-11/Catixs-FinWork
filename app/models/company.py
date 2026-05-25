from tortoise import fields

from .base import BaseModel, TimestampMixin


class Company(BaseModel, TimestampMixin):
    # 0=internal, 1=customer, 2=vendor
    role = fields.IntField(default=0, description="角色", index=True)
    name = fields.CharField(max_length=100, null=True, description="公司简称", index=True)
    legal_name = fields.CharField(max_length=200, null=True, description="公司全称", index=True)
    logo_url = fields.CharField(max_length=255, null=True, description="公司Logo")
    code = fields.CharField(max_length=50, null=True, description="公司编号", index=True, unique=True)
    country = fields.CharField(max_length=50, null=True, description="国家/地区", index=True)
    address = fields.CharField(max_length=255, null=True, description="地址")
    noc_email = fields.CharField(max_length=100, null=True, description="NOC邮箱")
    noc_phone = fields.CharField(max_length=50, null=True, description="NOC电话")
    remark = fields.CharField(max_length=500, null=True, description="备注")
    status = fields.BooleanField(default=True, description="状态", index=True)
    tax_no = fields.CharField(max_length=50, null=True, description="税号")
    company_email = fields.CharField(max_length=100, null=True, description="公司邮箱")
    bill_email = fields.CharField(max_length=100, null=True, description="财务邮箱")
    contact_person = fields.CharField(max_length=100, null=True, description="财务联系人")
    company_phone = fields.CharField(max_length=50, null=True, description="公司电话")
    registration_no = fields.CharField(max_length=50, null=True, description="公司注册号")
    contract_company = fields.ForeignKeyField(
        "models.Company",
        related_name="contract_companies",
        null=True,
        on_delete=fields.SET_NULL,
        description="签约主体公司",
    )

    class Meta:
        table = "company"


class Bank(BaseModel, TimestampMixin):
    name = fields.CharField(max_length=100, description="银行名称", index=True)
    country = fields.CharField(max_length=50, null=True, description="银行所在国家")
    swift_code = fields.CharField(max_length=50, null=True, description="银行国际代码")
    bank_address = fields.CharField(max_length=255, null=True, description="银行地址")

    class Meta:
        table = "bank"


class BankAccount(BaseModel, TimestampMixin):
    company = fields.ForeignKeyField(
        "models.Company",
        related_name="bank_accounts",
        on_delete=fields.CASCADE,
    )
    bank = fields.ForeignKeyField(
        "models.Bank",
        related_name="bank_accounts",
        null=True,
        on_delete=fields.SET_NULL,
    )
    bank_code = fields.CharField(max_length=50, null=True, description="银行编号")
    branch_code = fields.CharField(max_length=50, null=True, description="分行编号")
    account_name = fields.CharField(max_length=100, null=True, description="账户名")
    account_number = fields.CharField(max_length=100, null=True, description="账号")
    swift_code = fields.CharField(max_length=50, null=True, description="SWIFT")
    iban = fields.CharField(max_length=50, null=True, description="IBAN")
    sort_code = fields.CharField(max_length=50, null=True, description="SORT CODE")
    currency = fields.CharField(max_length=10, null=True, description="币种")

    class Meta:
        table = "bank_account"


class Bill(BaseModel, TimestampMixin):
    company = fields.ForeignKeyField(
        "models.Company",
        related_name="bills",
        on_delete=fields.CASCADE,
    )
    invoice_no = fields.CharField(max_length=100, null=True, description="账单编号", index=True)
    customer_name = fields.CharField(max_length=100, null=True, description="客户名")
    bill_month = fields.DateField(null=True, description="月份")
    invoice_date = fields.DateField(null=True, description="账单日期")
    due_date = fields.DateField(null=True, description="截止日期")
    billing_start_date = fields.DateField(null=True, description="计费开始日期")
    billing_end_date = fields.DateField(null=True, description="计费结束日期")
    currency = fields.CharField(max_length=10, null=True, description="币种")
    conversion_currency = fields.CharField(max_length=10, null=True, description="折算币种")
    exchange_rate = fields.FloatField(null=True, description="折算汇率")
    net_amount = fields.FloatField(null=True, description="Net Amount")
    vat_amount = fields.FloatField(null=True, description="VAT Amount")
    total_amount = fields.FloatField(null=True, description="账单金额")
    paid_amount = fields.FloatField(null=True, description="已付金额")
    unpaid_amount = fields.FloatField(null=True, description="欠费金额")
    is_settled = fields.BooleanField(default=False, description="是否结清", index=True)
    payment_voucher_url = fields.CharField(max_length=255, null=True, description="付款凭证")
    owner = fields.CharField(max_length=100, null=True, description="负责人")
    remark = fields.CharField(max_length=500, null=True, description="备注")
    # 1=customer bill, 2=vendor bill
    bill_type = fields.IntField(default=1, description="账单类型", index=True)

    class Meta:
        table = "bill"


class BillItem(BaseModel, TimestampMixin):
    bill = fields.ForeignKeyField(
        "models.Bill",
        related_name="items",
        on_delete=fields.CASCADE,
    )
    service_id = fields.CharField(max_length=100, null=True, description="服务ID")
    service = fields.CharField(max_length=100, null=True, description="服务")
    item = fields.CharField(max_length=100, null=True, description="项目")
    location = fields.CharField(max_length=100, null=True, description="位置")
    start_date = fields.DateField(null=True, description="开始日期")
    end_date = fields.DateField(null=True, description="结束日期")
    nrc_amount = fields.FloatField(null=True, description="NRC金额")
    mrc_amount = fields.FloatField(null=True, description="MRC金额")
    amount = fields.FloatField(null=True, description="金额")

    class Meta:
        table = "bill_item"
