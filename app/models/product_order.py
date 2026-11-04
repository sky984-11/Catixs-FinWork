from tortoise import fields

from .base import BaseModel, TimestampMixin


class ProductOrder(BaseModel, TimestampMixin):
    order_no = fields.CharField(max_length=40, unique=True)
    name = fields.CharField(max_length=160)
    customer = fields.ForeignKeyField("models.CrmCustomer", related_name="product_orders", on_delete=fields.RESTRICT)
    remark = fields.TextField(null=True)

    class Meta:
        table = "product_order"


class ProductOrderItem(BaseModel):
    order = fields.ForeignKeyField("models.ProductOrder", related_name="items", on_delete=fields.CASCADE)
    product = fields.ForeignKeyField("models.ProductItem", related_name="order_items", on_delete=fields.RESTRICT)
    quantity = fields.IntField()
    position = fields.IntField(default=0)
    price_version_id = fields.BigIntField(null=True, description="来源价格版本ID快照")
    price_version_number = fields.IntField(null=True)
    currency = fields.CharField(max_length=12, null=True)
    period_months = fields.IntField(null=True)
    billing_unit = fields.CharField(max_length=40, null=True)
    base_mrc = fields.DecimalField(max_digits=16, decimal_places=2, null=True)
    base_nrc = fields.DecimalField(max_digits=16, decimal_places=2, null=True)
    mrc = fields.DecimalField(max_digits=16, decimal_places=2, null=True)
    nrc = fields.DecimalField(max_digits=16, decimal_places=2, null=True)

    class Meta:
        table = "product_order_item"
        unique_together = (("order", "product"),)
