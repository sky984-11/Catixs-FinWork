from tortoise import fields

from .base import BaseModel, TimestampMixin


class ProductCategory(BaseModel, TimestampMixin):
    name = fields.CharField(max_length=120, description="产品分类名称", index=True)
    code = fields.CharField(max_length=80, null=True, description="产品分类编码", index=True, unique=True)
    parent = fields.ForeignKeyField(
        "models.ProductCategory",
        related_name="children",
        null=True,
        on_delete=fields.CASCADE,
        description="上级分类",
    )
    level = fields.IntField(default=1, description="分类层级", index=True)
    order = fields.IntField(default=0, description="排序")
    description = fields.CharField(max_length=500, null=True, description="分类说明")
    status = fields.BooleanField(default=True, description="状态", index=True)

    class Meta:
        table = "product_category"


class ProductItem(BaseModel, TimestampMixin):
    name = fields.CharField(max_length=160, description="产品名称", index=True)
    code = fields.CharField(max_length=80, null=True, description="产品编码", index=True, unique=True)
    category = fields.ForeignKeyField(
        "models.ProductCategory",
        related_name="products",
        null=True,
        on_delete=fields.SET_NULL,
        description="产品分类",
    )
    status = fields.CharField(max_length=30, default="active", description="产品状态", index=True)
    region = fields.CharField(max_length=100, null=True, description="地区", index=True)
    billing_mode = fields.CharField(max_length=40, default="fixed", description="计费模式", index=True)
    description = fields.TextField(null=True, description="产品说明")

    class Meta:
        table = "product_item"


class ProductSpecAttribute(BaseModel, TimestampMixin):
    name = fields.CharField(max_length=120, description="属性名称", index=True)
    code = fields.CharField(max_length=80, description="属性编码", index=True, unique=True)
    category = fields.ForeignKeyField(
        "models.ProductCategory",
        related_name="spec_attributes",
        null=True,
        on_delete=fields.SET_NULL,
        description="适用产品分类",
    )
    category_ids = fields.JSONField(default=list, description="适用产品分类ID列表")
    attr_type = fields.CharField(max_length=30, default="text", description="属性类型", index=True)
    unit = fields.CharField(max_length=40, null=True, description="单位")
    required = fields.BooleanField(default=False, description="是否必填", index=True)
    options = fields.TextField(null=True, description="可选值")
    description = fields.CharField(max_length=500, null=True, description="属性说明")
    status = fields.BooleanField(default=True, description="状态", index=True)

    class Meta:
        table = "product_spec_attribute"


class ProductSpecConfig(BaseModel, TimestampMixin):
    product = fields.ForeignKeyField(
        "models.ProductItem",
        related_name="spec_configs",
        on_delete=fields.CASCADE,
        description="关联产品",
    )
    attribute = fields.ForeignKeyField(
        "models.ProductSpecAttribute",
        related_name="spec_configs",
        on_delete=fields.CASCADE,
        description="规格属性",
    )
    order = fields.IntField(default=0, description="参数顺序")
    default_value = fields.CharField(max_length=255, null=True, description="默认值")
    value_range = fields.CharField(max_length=500, null=True, description="可选范围")
    required = fields.BooleanField(default=False, description="是否必填", index=True)

    class Meta:
        table = "product_spec_config"


class ProductPrice(BaseModel, TimestampMixin):
    product = fields.ForeignKeyField(
        "models.ProductItem",
        related_name="prices",
        on_delete=fields.CASCADE,
        description="关联产品",
    )
    price_type = fields.CharField(max_length=30, default="standard", description="价格类型", index=True)
    customer_id = fields.BigIntField(null=True, description="客户ID", index=True)
    customer_name = fields.CharField(max_length=160, null=True, description="客户名称", index=True)
    billing_mode = fields.CharField(max_length=40, default="fixed", description="计费模式", index=True)
    billing_unit = fields.CharField(max_length=40, default="month", description="计费单位", index=True)
    currency = fields.CharField(max_length=12, default="USD", description="币种", index=True)
    amount = fields.DecimalField(max_digits=16, decimal_places=2, default=0, description="价格")
    min_amount = fields.DecimalField(max_digits=16, decimal_places=2, null=True, description="最低售价")
    tier_rules = fields.TextField(null=True, description="阶梯规则")
    bandwidth_rule = fields.TextField(null=True, description="带宽规则")
    effective_date = fields.DateField(null=True, description="生效日期", index=True)
    expiry_date = fields.DateField(null=True, description="失效日期", index=True)
    status = fields.CharField(max_length=30, default="active", description="价格状态", index=True)
    remark = fields.TextField(null=True, description="备注")

    class Meta:
        table = "product_price"


class ProductTemplate(BaseModel, TimestampMixin):
    name = fields.CharField(max_length=120, description="模板名称", index=True)
    category = fields.ForeignKeyField(
        "models.ProductCategory",
        related_name="templates",
        null=True,
        on_delete=fields.SET_NULL,
        description="适用分类",
    )
    template_type = fields.CharField(max_length=40, default="product", description="模板类型", index=True)
    description = fields.TextField(null=True, description="模板说明")
    config = fields.TextField(null=True, description="模板配置")
    status = fields.BooleanField(default=True, description="状态", index=True)

    class Meta:
        table = "product_template"
