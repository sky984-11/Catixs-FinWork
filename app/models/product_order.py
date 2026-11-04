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

    class Meta:
        table = "product_order_item"
        unique_together = (("order", "product"),)
