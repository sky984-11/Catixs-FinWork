from tortoise import fields

from .base import BaseModel, TimestampMixin


class AssetRegion(BaseModel, TimestampMixin):
    name = fields.CharField(max_length=100, description="区域名称", index=True)
    code = fields.CharField(max_length=50, description="区域编码", unique=True, index=True)
    country = fields.CharField(max_length=100, null=True, description="国家", index=True)
    city = fields.CharField(max_length=100, null=True, description="城市", index=True)
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
    rental_start_u = fields.IntField(default=1, description="租用起始U位")
    rental_end_u = fields.IntField(default=42, description="租用结束U位")
    width_mm = fields.IntField(default=600, description="机柜宽度mm")
    depth_mm = fields.IntField(default=1000, description="机柜深度mm")
    power_allocation_kw = fields.FloatField(default=0, description="电力分配kW")
    power_overage_rate = fields.CharField(max_length=100, null=True, description="超额电力计费")
    pdu_spec = fields.CharField(max_length=500, null=True, description="rPDU配置")
    power_socket_spec = fields.CharField(max_length=500, null=True, description="电源插座")
    rack_tray = fields.CharField(max_length=100, null=True, description="机柜托盘")
    pdu_socket_types = fields.CharField(max_length=255, null=True, description="PDU插槽类型")
    front_image_url = fields.CharField(max_length=255, null=True, description="机柜正面图片")
    back_image_url = fields.CharField(max_length=255, null=True, description="机柜反面图片")
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
    status = fields.IntField(default=0, description="设备状态：0-空闲，1-使用，2-待维护，3-故障，4-下架", index=True)
    mgmt_ip = fields.CharField(max_length=64, null=True, description="管理IP", index=True)
    business_ip = fields.CharField(max_length=64, null=True, description="业务IP", index=True)
    owner = fields.CharField(max_length=100, null=True, description="负责人")
    purchase_date = fields.DateField(null=True, description="采购日期")
    warranty_expire = fields.DateField(null=True, description="维保到期")
    attributes = fields.JSONField(default=dict, description="扩展配置")
    remark = fields.CharField(max_length=500, null=True, description="备注")

    class Meta:
        table = "asset_device"


class PveNodeBinding(BaseModel, TimestampMixin):
    remote = fields.CharField(max_length=100, unique=True, description="PDM Remote ID", index=True)
    region = fields.ForeignKeyField(
        "models.AssetRegion",
        related_name="pve_node_bindings",
        null=True,
        on_delete=fields.SET_NULL,
        description="关联地区",
    )
    location = fields.ForeignKeyField(
        "models.AssetLocation",
        related_name="pve_node_bindings",
        null=True,
        on_delete=fields.SET_NULL,
        description="关联机房",
    )
    device = fields.ForeignKeyField(
        "models.AssetDevice",
        related_name="pve_node_bindings",
        null=True,
        on_delete=fields.SET_NULL,
        description="关联物理设备",
    )
    remark = fields.CharField(max_length=500, null=True, description="关联备注")

    class Meta:
        table = "pve_node_binding"


class CloudDhcpPool(BaseModel, TimestampMixin):
    name = fields.CharField(max_length=120, description="DHCP pool name", index=True)
    region = fields.ForeignKeyField(
        "models.AssetRegion",
        related_name="cloud_dhcp_pools",
        null=True,
        on_delete=fields.SET_NULL,
        description="Related region",
    )
    location = fields.ForeignKeyField(
        "models.AssetLocation",
        related_name="cloud_dhcp_pools",
        null=True,
        on_delete=fields.SET_NULL,
        description="Related location",
    )
    region_code = fields.CharField(max_length=40, description="Region code", index=True)
    region_name = fields.CharField(max_length=120, null=True, description="Region name", index=True)
    vlan = fields.IntField(description="VLAN", index=True)
    gateway = fields.CharField(max_length=64, description="Gateway")
    cidr = fields.CharField(max_length=64, description="CIDR")
    start_ip = fields.CharField(max_length=64, description="Start IP")
    end_ip = fields.CharField(max_length=64, description="End IP")
    dns = fields.CharField(max_length=120, null=True, description="DNS")
    status = fields.BooleanField(default=True, description="Enabled", index=True)
    remark = fields.CharField(max_length=500, null=True, description="Remark")

    class Meta:
        table = "cloud_dhcp_pool"


class CloudDhcpLease(BaseModel, TimestampMixin):
    pool = fields.ForeignKeyField("models.CloudDhcpPool", related_name="leases", on_delete=fields.CASCADE)
    product = fields.ForeignKeyField(
        "models.ProductItem",
        related_name="dhcp_leases",
        null=True,
        on_delete=fields.SET_NULL,
    )
    price = fields.ForeignKeyField(
        "models.ProductPrice",
        related_name="dhcp_leases",
        null=True,
        on_delete=fields.SET_NULL,
    )
    ip = fields.CharField(max_length=64, description="Allocated IP", index=True)
    remote = fields.CharField(max_length=100, null=True, description="PVE remote", index=True)
    vmid = fields.IntField(null=True, description="VMID", index=True)
    lease_source = fields.CharField(max_length=40, default="manual", description="Lease source", index=True)
    vlan = fields.IntField(description="VLAN", index=True)
    gateway = fields.CharField(max_length=64, description="Gateway")
    cidr = fields.CharField(max_length=64, description="CIDR")
    os_type = fields.CharField(max_length=40, null=True, description="OS type")
    os_version = fields.CharField(max_length=40, null=True, description="OS version")
    cpu_cores = fields.IntField(default=2, description="CPU cores")
    memory_gb = fields.IntField(default=2, description="Memory GB")
    disk_gb = fields.IntField(default=20, description="Disk GB")
    expiry_date = fields.DateField(null=True, description="Expiry date", index=True)
    status = fields.CharField(max_length=30, default="reserved", description="Lease status", index=True)
    remark = fields.CharField(max_length=500, null=True, description="Remark")

    class Meta:
        table = "cloud_dhcp_lease"
        unique_together = (("pool", "ip"),)


class PveVmMetadata(BaseModel, TimestampMixin):
    remote = fields.CharField(max_length=100, description="PVE remote", index=True)
    vmid = fields.IntField(description="VMID", index=True)
    vm_name = fields.CharField(max_length=160, null=True, description="VM name", index=True)
    customer_id = fields.BigIntField(null=True, description="Customer ID", index=True)
    customer_name = fields.CharField(max_length=160, null=True, description="Customer name", index=True)
    remark = fields.CharField(max_length=500, null=True, description="Remark")

    class Meta:
        table = "pve_vm_metadata"
        unique_together = (("remote", "vmid"),)


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
