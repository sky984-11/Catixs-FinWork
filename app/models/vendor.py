from tortoise import fields

from .base import BaseModel, TimestampMixin


class Vendor(BaseModel, TimestampMixin):
    name = fields.CharField(max_length=100, description="供应商名称", index=True)
    country = fields.CharField(max_length=50, null=True, description="国家/地区", index=True)
    code = fields.CharField(max_length=50, null=True, description="供应商编号", index=True, unique=True)
    role = fields.IntField(default=0, description="角色")
    address = fields.CharField(max_length=255, null=True, description="地址")
    noc_email = fields.CharField(max_length=100, null=True, description="NOC邮箱")
    noc_phone = fields.CharField(max_length=50, null=True, description="NOC电话")
    remark = fields.CharField(max_length=500, null=True, description="备注")
    status = fields.BooleanField(default=True, description="启用状态", index=True)

    class Meta:
        table = "vendor"

