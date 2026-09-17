from tortoise import fields

from .base import BaseModel, TimestampMixin


class VendorContact(BaseModel, TimestampMixin):
    contact_type = fields.CharField(max_length=20, default="person")
    name = fields.CharField(max_length=100, default="")
    roles = fields.JSONField(default=list)
    email = fields.CharField(max_length=200, default="")
    phone = fields.CharField(max_length=100, default="")
    address = fields.CharField(max_length=500, default="")
    remark = fields.TextField(default="")

    class Meta:
        table = "vendor_contact"


class VendorContactLink(BaseModel):
    contact = fields.ForeignKeyField("models.VendorContact", related_name="links", on_delete=fields.CASCADE)
    vendor = fields.ForeignKeyField("models.Company", related_name="contact_links", on_delete=fields.RESTRICT)

    class Meta:
        table = "vendor_contact_link"
        unique_together = (("contact", "vendor"),)
