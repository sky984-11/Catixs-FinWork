from tortoise import fields

from .base import BaseModel, TimestampMixin


class ResourceCost(BaseModel, TimestampMixin):
    code = fields.CharField(max_length=80, unique=True)
    category = fields.CharField(max_length=30, index=True)
    title = fields.CharField(max_length=255)
    vendor = fields.ForeignKeyField(
        "models.Company", null=True, related_name="resource_costs", on_delete=fields.RESTRICT
    )
    revision = fields.IntField(default=1)
    enabled = fields.BooleanField(default=True)

    class Meta:
        table = "resource_cost"


class ResourceCostVersion(BaseModel, TimestampMixin):
    resource = fields.ForeignKeyField("models.ResourceCost", related_name="versions", on_delete=fields.RESTRICT)
    revision = fields.IntField()
    data = fields.JSONField()
    created_by_id = fields.BigIntField()

    class Meta:
        table = "resource_cost_version"
        unique_together = (("resource", "revision"),)


class ProductCostLink(BaseModel, TimestampMixin):
    product = fields.ForeignKeyField("models.ProductItem", related_name="cost_links", on_delete=fields.CASCADE)
    resource = fields.ForeignKeyField("models.ResourceCost", related_name="product_links", on_delete=fields.RESTRICT)
    version = fields.ForeignKeyField(
        "models.ResourceCostVersion", related_name="product_links", on_delete=fields.RESTRICT
    )

    class Meta:
        table = "product_cost_link"
        unique_together = (("product", "resource"),)
