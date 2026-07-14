from tortoise import fields

from .base import BaseModel, TimestampMixin


class AssetRegion(BaseModel, TimestampMixin):
    name = fields.CharField(max_length=100, description="区域名称", index=True)
    code = fields.CharField(max_length=50, description="区域编码", unique=True, index=True)
    remark = fields.CharField(max_length=500, null=True, description="备注")
    status = fields.BooleanField(default=True, description="启用状态", index=True)

    class Meta:
        table = "asset_region"


class AssetLocation(BaseModel, TimestampMixin):
    region = fields.ForeignKeyField("models.AssetRegion", related_name="locations", description="所属区域")
    name = fields.CharField(max_length=100, description="位置名称", index=True)
    type = fields.IntField(default=1, description="位置类型：0-库存，1-机房", index=True)
    address = fields.CharField(max_length=255, null=True, description="地址")
    remark = fields.CharField(max_length=500, null=True, description="备注")
    status = fields.BooleanField(default=True, description="启用状态", index=True)

    class Meta:
        table = "asset_location"


class AssetCabinet(BaseModel, TimestampMixin):
    location = fields.ForeignKeyField("models.AssetLocation", related_name="cabinets", description="所属位置")
    name = fields.CharField(max_length=100, description="机柜名称", index=True)
    code = fields.CharField(max_length=50, null=True, description="机柜编码", index=True)
    row = fields.CharField(max_length=50, null=True, description="行")
    column = fields.CharField(max_length=50, null=True, description="列")
    capacity_u = fields.IntField(default=42, description="机柜容量U数")
    remark = fields.CharField(max_length=500, null=True, description="备注")
    status = fields.BooleanField(default=True, description="启用状态", index=True)

    class Meta:
        table = "asset_cabinet"


class AssetDevice(BaseModel, TimestampMixin):
    cabinet = fields.ForeignKeyField("models.AssetCabinet", related_name="devices", description="所属机柜")
    region = fields.ForeignKeyField("models.AssetRegion", related_name="devices", description="所属区域")
    location = fields.ForeignKeyField("models.AssetLocation", related_name="devices", description="所属位置")
    asset_no = fields.CharField(max_length=100, description="资产编号", unique=True, index=True)
    name = fields.CharField(max_length=100, description="设备名称", index=True)
    type = fields.IntField(default=0, description="设备类型", index=True)
    brand = fields.CharField(max_length=100, null=True, description="品牌")
    model = fields.CharField(max_length=100, null=True, description="型号")
    serial_no = fields.CharField(max_length=100, null=True, description="序列号", index=True)
    u_position = fields.IntField(null=True, description="起始U位")
    u_height = fields.IntField(default=1, description="占用U数")
    status = fields.IntField(default=0, description="设备状态：0-空闲，3-故障，1-使用，4-下线", index=True)
    mgmt_ip = fields.CharField(max_length=64, null=True, description="管理IP", index=True)
    business_ip = fields.CharField(max_length=64, null=True, description="业务IP", index=True)
    owner = fields.CharField(max_length=100, null=True, description="负责人")
    purchase_date = fields.DateField(null=True, description="采购日期")
    warranty_expire = fields.DateField(null=True, description="维保到期")
    attributes = fields.JSONField(default=dict, description="扩展配置")
    remark = fields.CharField(max_length=500, null=True, description="备注")

    class Meta:
        table = "asset_device"


class AssetDeviceBrand(BaseModel, TimestampMixin):
    name = fields.CharField(max_length=100, description="品牌名称", unique=True, index=True)
    sort = fields.IntField(default=0, description="排序")
    status = fields.BooleanField(default=True, description="启用状态", index=True)

    class Meta:
        table = "asset_device_brand"


class AssetDeviceModel(BaseModel, TimestampMixin):
    brand = fields.ForeignKeyField("models.AssetDeviceBrand", related_name="models", description="所属品牌")
    name = fields.CharField(max_length=100, description="型号名称", index=True)
    sort = fields.IntField(default=0, description="排序")
    status = fields.BooleanField(default=True, description="启用状态", index=True)

    class Meta:
        table = "asset_device_model"
        unique_together = (("brand", "name"),)


class AssetInventory(BaseModel, TimestampMixin):
    region = fields.ForeignKeyField("models.AssetRegion", related_name="inventory_items", description="所属区域")
    location = fields.ForeignKeyField("models.AssetLocation", related_name="inventory_items", description="所属库存位置")
    type = fields.CharField(max_length=100, description="分类", index=True)
    subtype = fields.CharField(max_length=100, null=True, description="子类", index=True)
    quantity = fields.IntField(default=1, description="数量")
    threshold = fields.IntField(default=0, description="库存告警阈值")
    cost_price = fields.FloatField(default=0, description="成本价")
    cost_price_currency = fields.CharField(max_length=10, default="USD", description="成本价币种")
    sale_price = fields.FloatField(default=0, description="默认售价")
    sale_price_currency = fields.CharField(max_length=10, default="USD", description="默认售价币种")
    attributes = fields.JSONField(default=dict, description="扩展属性")
    remark = fields.CharField(max_length=500, null=True, description="备注")
    status = fields.BooleanField(default=True, description="启用状态", index=True)

    class Meta:
        table = "asset_inventory"


class AssetInventoryCategory(BaseModel, TimestampMixin):
    name = fields.CharField(max_length=100, description="分类名称", index=True)
    parent_id = fields.IntField(null=True, description="父级分类ID", index=True)
    sort = fields.IntField(default=0, description="排序")
    status = fields.BooleanField(default=True, description="启用状态", index=True)

    class Meta:
        table = "asset_inventory_category"


class AssetInventorySaleOrder(BaseModel, TimestampMixin):
    sale_no = fields.CharField(max_length=100, unique=True, index=True, description="销售单号")
    customer_name = fields.CharField(max_length=100, description="客户名称", index=True)
    customer_contact = fields.CharField(max_length=100, null=True, description="客户联系人")
    sale_date = fields.DateField(null=True, description="销售日期")
    status = fields.IntField(default=1, description="状态：1-已确认，2-已取消", index=True)
    total_amount = fields.FloatField(default=0, description="销售总额")
    remark = fields.CharField(max_length=500, null=True, description="备注")
    created_by = fields.BigIntField(null=True, description="创建人ID", index=True)
    canceled_at = fields.DatetimeField(null=True, description="取消时间")
    canceled_by = fields.BigIntField(null=True, description="取消人ID")
    cancel_reason = fields.CharField(max_length=500, null=True, description="取消原因")

    class Meta:
        table = "asset_inventory_sale_order"


class AssetInventorySaleItem(BaseModel, TimestampMixin):
    sale_order = fields.ForeignKeyField("models.AssetInventorySaleOrder", related_name="items", description="销售单")
    inventory = fields.ForeignKeyField("models.AssetInventory", related_name="sale_items", description="库存项")
    type = fields.CharField(max_length=100, description="分类快照")
    subtype = fields.CharField(max_length=100, null=True, description="子类快照")
    quantity = fields.IntField(description="销售数量")
    cost_price = fields.FloatField(default=0, description="成本价快照")
    cost_price_currency = fields.CharField(max_length=10, default="USD", description="成本价币种快照")
    unit_price = fields.FloatField(default=0, description="单价")
    unit_price_currency = fields.CharField(max_length=10, default="USD", description="单价币种")
    amount = fields.FloatField(default=0, description="小计")
    remark = fields.CharField(max_length=500, null=True, description="备注")

    class Meta:
        table = "asset_inventory_sale_item"


class AssetInventoryStockFlow(BaseModel, TimestampMixin):
    inventory = fields.ForeignKeyField("models.AssetInventory", related_name="stock_flows", description="库存项")
    flow_type = fields.CharField(max_length=30, description="流水类型", index=True)
    quantity_before = fields.IntField(description="变更前数量")
    quantity_change = fields.IntField(description="变更数量")
    quantity_after = fields.IntField(description="变更后数量")
    biz_type = fields.CharField(max_length=50, description="业务类型", index=True)
    biz_id = fields.BigIntField(null=True, description="业务ID", index=True)
    remark = fields.CharField(max_length=500, null=True, description="备注")
    created_by = fields.BigIntField(null=True, description="创建人ID", index=True)

    class Meta:
        table = "asset_inventory_stock_flow"
