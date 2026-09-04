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
    source_type = fields.CharField(max_length=40, null=True, description="配置来源类型", index=True)
    source_id = fields.BigIntField(null=True, description="配置来源ID", index=True)
    source_key = fields.CharField(max_length=160, null=True, description="配置来源唯一键", index=True)
    spec_name = fields.CharField(max_length=200, null=True, description="规格配置名称", index=True)
    sync_hash = fields.CharField(max_length=64, null=True, description="同步内容哈希")
    auto_sync = fields.BooleanField(default=False, description="是否自动同步", index=True)
    synced_at = fields.DatetimeField(null=True, description="最近同步时间")
    product_display_name = fields.CharField(max_length=160, null=True, description="产品名称快照", index=True)
    product_category_name = fields.CharField(max_length=120, null=True, description="产品分类快照", index=True)
    product_category_sort = fields.CharField(max_length=120, null=True, description="产品分类排序键", index=True)
    product_region_name = fields.CharField(max_length=100, null=True, description="产品地区快照", index=True)

    class Meta:
        table = "product_spec_config"


class ProductPrice(BaseModel, TimestampMixin):
    product = fields.ForeignKeyField(
        "models.ProductItem",
        related_name="prices",
        on_delete=fields.CASCADE,
        description="关联产品",
    )
    spec_config_key = fields.CharField(max_length=200, null=True, description="规格配置组键", index=True)
    spec_config_name = fields.CharField(max_length=200, null=True, description="规格配置名称", index=True)
    price_type = fields.CharField(max_length=30, default="standard", description="价格类型", index=True)
    inherited_from_price_id = fields.BigIntField(null=True, description="继承来源价格ID", index=True)
    cloud_vm_remote = fields.CharField(max_length=100, null=True, description="关联云主机远端")
    cloud_vm_vmid = fields.IntField(null=True, description="关联云主机VMID")
    cloud_vm_name = fields.CharField(max_length=160, null=True, description="关联云主机名称")
    physical_device_id = fields.BigIntField(null=True, description="关联物理服务器ID")
    physical_device_name = fields.CharField(max_length=160, null=True, description="关联物理服务器名称")
    physical_device_node = fields.CharField(max_length=100, null=True, description="关联四合一服务器节点")
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
    notify_enabled = fields.BooleanField(default=False, description="飞书提醒启用", index=True)
    notify_user_ids = fields.JSONField(null=True, description="飞书提醒接收人")
    notify_schedule = fields.CharField(max_length=20, default="once", description="提醒周期")
    notify_at = fields.DatetimeField(null=True, description="提醒时间")
    notify_next_at = fields.DatetimeField(null=True, description="下次提醒时间", index=True)
    notify_last_at = fields.DatetimeField(null=True, description="最近提醒时间")
    status = fields.CharField(max_length=30, default="active", description="价格状态", index=True)
    remark = fields.TextField(null=True, description="备注")

    class Meta:
        table = "product_price"


class ProductPriceHistory(BaseModel, TimestampMixin):
    source_price_id = fields.BigIntField(null=True, description="原价格记录ID", index=True)
    product_id = fields.BigIntField(description="关联产品ID", index=True)
    product_name = fields.CharField(max_length=160, null=True, description="产品名称")
    spec_config_key = fields.CharField(max_length=200, null=True, description="规格配置组键")
    spec_config_name = fields.CharField(max_length=200, null=True, description="规格配置名称")
    price_type = fields.CharField(max_length=30, default="customer", description="价格类型")
    cloud_vm_remote = fields.CharField(max_length=100, null=True)
    cloud_vm_vmid = fields.IntField(null=True)
    cloud_vm_name = fields.CharField(max_length=160, null=True)
    physical_device_id = fields.BigIntField(null=True)
    physical_device_name = fields.CharField(max_length=160, null=True)
    physical_device_node = fields.CharField(max_length=100, null=True)
    customer_id = fields.BigIntField(null=True, index=True)
    customer_name = fields.CharField(max_length=160, null=True)
    billing_mode = fields.CharField(max_length=40, default="fixed")
    billing_unit = fields.CharField(max_length=40, default="month")
    currency = fields.CharField(max_length=12, default="USD")
    amount = fields.DecimalField(max_digits=16, decimal_places=2, default=0)
    effective_date = fields.DateField(null=True)
    expiry_date = fields.DateField(null=True)
    remark = fields.TextField(null=True)
    off_shelf_at = fields.DatetimeField(description="下架时间", index=True)

    class Meta:
        table = "product_price_history"


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
