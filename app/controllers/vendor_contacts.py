import re
from typing import Literal

from fastapi import HTTPException
from pydantic import BaseModel, Field, field_validator, model_validator
from tortoise.transactions import in_transaction

from app.models.company import Company
from app.models.vendor_contact import VendorContact, VendorContactLink

ROLES = {
    "business": "商务联系人",
    "procurement": "采购联系人",
    "technical": "技术联系人",
    "finance": "财务联系人",
    "ops": "运维联系人",
    "emergency": "紧急联系人",
}
LEGACY = {
    "company_contact": ("business", ("company_email", "company_phone")),
    "sales_contact": ("business", ("sales_contact",)),
    "billing_contact": ("finance", ("billing_contact",)),
    "noc_contact": ("ops", ("noc_contact", "noc_email", "noc_phone")),
}


class ContactInput(BaseModel):
    vendor_ids: list[int] = Field(min_length=1, max_length=100)
    contact_type: Literal["person", "group"] = "person"
    name: str = Field("", max_length=100)
    roles: list[Literal["business", "procurement", "technical", "finance", "ops", "emergency"]] = Field(
        default_factory=lambda: ["business"], min_length=1, max_length=6
    )
    email: str = Field("", max_length=200)
    phone: str = Field("", max_length=100)
    address: str = Field("", max_length=500)
    remark: str = Field("", max_length=10000)

    @field_validator("name", "email", "phone", "address", "remark", mode="before")
    @classmethod
    def trim(cls, value):
        return value.strip() if isinstance(value, str) else value

    @model_validator(mode="after")
    def validate_contact(self):
        if not self.name and not self.email:
            raise ValueError("请填写联系人姓名/组名或邮箱")
        if self.email and not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", self.email):
            raise ValueError("邮箱格式错误")
        if any(value <= 0 for value in self.vendor_ids):
            raise ValueError("供应商ID无效")
        self.vendor_ids = list(dict.fromkeys(self.vendor_ids))
        self.roles = list(dict.fromkeys(self.roles))
        return self


class ContactUpdate(ContactInput):
    id: str = Field(min_length=1, max_length=80)


async def serialize(contact):
    data = await contact.to_dict()
    vendors = [link.vendor for link in await contact.links.all().prefetch_related("vendor")]
    data.update(
        id=str(contact.id), vendor_ids=[v.id for v in vendors], vendor_name="、".join(v.name or "" for v in vendors)
    )
    return data


def legacy_row(vendor, key):
    role, fields = LEGACY[key]
    if not any((getattr(vendor, field) or "").strip() for field in fields):
        return None
    email_field = "company_email" if key == "company_contact" else "noc_email" if key == "noc_contact" else None
    phone_field = "company_phone" if key == "company_contact" else "noc_phone" if key == "noc_contact" else None
    return {
        "id": f"legacy:{vendor.id}:{key}",
        "vendor_ids": [vendor.id],
        "vendor_name": vendor.name,
        "contact_type": "group",
        "name": ROLES[role],
        "roles": [role],
        "email": getattr(vendor, email_field) or "" if email_field else "",
        "phone": getattr(vendor, phone_field) or "" if phone_field else "",
        "address": "",
        "remark": getattr(vendor, key) or "" if key != "company_contact" else "",
        "legacy": True,
    }


async def list_contacts(vendor_id=None):
    query = VendorContact.all()
    vendors = Company.filter(role=2)
    if vendor_id is not None:
        query = query.filter(links__vendor_id=vendor_id)
        vendors = vendors.filter(id=vendor_id)
    rows = [await serialize(contact) for contact in await query.order_by("-id")]
    for vendor in await vendors.order_by("id"):
        rows.extend(row for key in LEGACY if (row := legacy_row(vendor, key)))
    return rows


async def legacy_source(identity):
    try:
        _, vendor_id, key = identity.split(":")
        vendor_id = int(vendor_id)
    except (ValueError, TypeError):
        raise HTTPException(404, "联系人不存在")
    if key not in LEGACY:
        raise HTTPException(404, "联系人不存在")
    vendor = await Company.filter(id=vendor_id, role=2).select_for_update().first()
    if vendor is None or legacy_row(vendor, key) is None:
        raise HTTPException(404, "联系人不存在或已更新，请刷新")
    return vendor, key


async def save_contact(payload, identity=None):
    async with in_transaction():
        vendors = await Company.filter(id__in=payload.vendor_ids, role=2)
        if len(vendors) != len(payload.vendor_ids):
            raise HTTPException(400, "请选择有效供应商")
        source = None
        if identity and identity.startswith("legacy:"):
            source = await legacy_source(identity)
            contact = VendorContact()
        elif identity:
            if not identity.isdigit():
                raise HTTPException(404, "联系人不存在")
            contact = await VendorContact.filter(id=int(identity)).select_for_update().first()
            if contact is None:
                raise HTTPException(404, "联系人不存在")
        else:
            contact = VendorContact()
        contact.update_from_dict(payload.model_dump(exclude={"vendor_ids", "id"}))
        await contact.save()
        await VendorContactLink.filter(contact_id=contact.id).delete()
        for vendor in vendors:
            await VendorContactLink.create(contact_id=contact.id, vendor_id=vendor.id)
        if source:
            vendor, key = source
            for field in LEGACY[key][1]:
                setattr(vendor, field, "")
            await vendor.save(update_fields=list(LEGACY[key][1]))
        return await serialize(contact)


async def delete_contact(identity):
    async with in_transaction():
        if identity.startswith("legacy:"):
            vendor, key = await legacy_source(identity)
            for field in LEGACY[key][1]:
                setattr(vendor, field, "")
            await vendor.save(update_fields=list(LEGACY[key][1]))
        elif not identity.isdigit() or not await VendorContact.filter(id=int(identity)).delete():
            raise HTTPException(404, "联系人不存在")
