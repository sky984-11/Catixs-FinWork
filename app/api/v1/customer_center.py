import re
import csv
import io
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from tortoise.expressions import Q

from app.models.customer_center import (
    CrmCustomer,
    CrmCustomerBill,
    CrmCustomerContact,
    CrmCustomerContract,
    CrmSigningEntity,
)
from app.schemas.base import Fail, Success, SuccessExtra

router = APIRouter()

ENTITY_TYPES = [
    {"label": "企业", "value": "enterprise"},
    {"label": "个人", "value": "personal"},
    {"label": "其他组织", "value": "other"},
]
LIFECYCLES = [
    {"label": "潜在客户", "value": "prospect"},
    {"label": "正式客户", "value": "active"},
    {"label": "暂停合作", "value": "paused"},
    {"label": "已终止", "value": "terminated"},
]
LEVELS = [
    {"label": "S 战略客户", "value": "S"},
    {"label": "A 核心客户", "value": "A"},
    {"label": "B 重点客户", "value": "B"},
    {"label": "C 普通客户", "value": "C"},
    {"label": "D 低价值/风险客户", "value": "D"},
]
CONTACT_ROLES = [
    {"label": "商务联系人", "value": "business"},
    {"label": "采购联系人", "value": "procurement"},
    {"label": "技术联系人", "value": "technical"},
    {"label": "财务联系人", "value": "finance"},
    {"label": "运维联系人", "value": "ops"},
    {"label": "紧急联系人", "value": "emergency"},
]
CONTACT_TYPES = [
    {"label": "个人", "value": "person"},
    {"label": "组邮箱", "value": "group"},
]
CONTRACT_STATUSES = [
    {"label": "草稿", "value": "draft"},
    {"label": "待签署", "value": "pending_signature"},
    {"label": "生效中", "value": "active"},
    {"label": "即将到期", "value": "expiring"},
    {"label": "已到期", "value": "expired"},
    {"label": "已终止", "value": "terminated"},
]
BILL_STATUSES = [
    {"label": "草稿", "value": "draft"},
    {"label": "待结算", "value": "pending"},
    {"label": "已结算", "value": "settled"},
    {"label": "已作废", "value": "void"},
]


class CustomerPayload(BaseModel):
    customer_code: str | None = Field(None, max_length=60)
    name: str = Field(..., max_length=120)
    legal_name: str | None = Field(None, max_length=240)
    alias: str | None = Field(None, max_length=120)
    entity_type: str = "enterprise"
    signing_entity_id: int | None = None
    customer_level: str = "C"
    lifecycle: str = "active"
    sales_owner: str | None = Field(None, max_length=100)
    region: str | None = Field(None, max_length=100)
    address: str | None = Field(None, max_length=255)
    invoice_info: str | None = None
    finance_info: str | None = None
    basic_info: str | None = None
    remark: str | None = None
    status: bool = True


class ContactPayload(BaseModel):
    customer_id: int | None = None
    customer_ids: list[int] = Field(default_factory=list)
    contact_type: str = "person"
    name: str | None = Field(None, max_length=100)
    role: list[str] | str = Field(default_factory=lambda: ["business"])
    title: str | None = Field(None, max_length=100)
    email: str | None = Field(None, max_length=160)
    phone: str | None = Field(None, max_length=80)
    address: str | None = Field(None, max_length=255)
    remark: str | None = Field(None, max_length=500)
    status: bool = True


class ContractPayload(BaseModel):
    customer_id: int
    signing_entity_id: int | None = None
    contract_no: str | None = Field(None, max_length=100)
    name: str = Field(..., max_length=240)
    status: str = "draft"
    effective_date: date | None = None
    expiry_date: date | None = None
    amount: Decimal | float | int | str = 0
    currency: str = Field("USD", max_length=12)
    attachment_url: str | None = Field(None, max_length=500)
    reminder_days: int = 30
    reminder_enabled: bool = True
    remark: str | None = None


class BillPayload(BaseModel):
    customer_id: int
    bill_no: str | None = Field(None, max_length=100)
    title: str = Field(..., max_length=160)
    status: str = "draft"
    amount: Decimal | float | int | str = 0
    currency: str = Field("USD", max_length=12)
    bill_date: date | None = None
    due_date: date | None = None
    is_settled: bool = False
    business_closed: bool = False
    remark: str | None = None


def compact(values: dict[str, Any]) -> dict[str, Any]:
    return {key: (None if value == "" else value) for key, value in values.items()}


def normalize_contact_data(values: dict[str, Any]) -> dict[str, Any]:
    data = compact(values)
    if data.get("contact_type") not in {"person", "group"}:
        data["contact_type"] = "person"
    if not data.get("name"):
        email = str(data.get("email") or "").strip()
        data["name"] = email.split("@", 1)[0] if email else "未命名联系人"
    if "role" in data:
        data["role"] = ",".join(normalize_contact_roles(data["role"]))
    return data


def normalize_contact_roles(value: list[str] | str | None) -> list[str]:
    values = value if isinstance(value, list) else str(value or "").split(",")
    allowed = {item["value"] for item in CONTACT_ROLES}
    roles = list(dict.fromkeys(str(item).strip() for item in values if str(item).strip() in allowed))
    return roles or ["business"]


def normalize_customer_ids(customer_ids: list[int] | None, customer_id: int | None = None) -> list[int]:
    values = [int(item) for item in (customer_ids or []) if item]
    if customer_id and customer_id not in values:
        values.insert(0, customer_id)
    return list(dict.fromkeys(values))


async def customer_selectable(customer_id: int | None) -> bool:
    if not customer_id:
        return False
    return await CrmCustomer.filter(id=customer_id, status=True).exclude(lifecycle="terminated").exists()


async def customer_full_name_exists(
    legal_name: str | None,
    signing_entity_id: int | None,
    exclude_customer_id: int | None = None,
) -> bool:
    normalized_name = str(legal_name or "").strip()
    if not normalized_name or not signing_entity_id:
        return False
    query = CrmCustomer.filter(legal_name=normalized_name, signing_entity_id=signing_entity_id)
    if exclude_customer_id:
        query = query.exclude(id=exclude_customer_id)
    return await query.exists()


def customer_code_prefix(signing_entity: CrmSigningEntity) -> str:
    """Return the customer-number prefix assigned to the signing entity."""
    entity_name = " ".join(
        str(value or "") for value in (signing_entity.name, signing_entity.legal_name, signing_entity.code)
    ).lower()
    if "77" in entity_name:
        return "H"
    if "catixs" in entity_name and ("cn" not in entity_name and "科特思" not in entity_name):
        return "U"
    if "科特思" in entity_name or "catixs-cn" in entity_name:
        return "C"

    # Keep custom signing entities usable while the three standard entities retain their fixed prefixes.
    letters = re.findall(r"[A-Za-z]", str(signing_entity.code or signing_entity.name or ""))
    return letters[0].upper() if letters else "C"


async def next_customer_code(signing_entity_id: int | None) -> str | None:
    if not signing_entity_id:
        return None
    signing_entity = await CrmSigningEntity.get_or_none(id=signing_entity_id)
    if not signing_entity:
        return None
    prefix = customer_code_prefix(signing_entity)
    pattern = re.compile(rf"^{re.escape(prefix)}(\d{{5}})$")
    codes = await CrmCustomer.filter(customer_code__startswith=prefix).values_list("customer_code", flat=True)
    sequences = [int(match.group(1)) for code in codes if (match := pattern.match(str(code or "")))]
    return f"{prefix}{(max(sequences, default=0) + 1):05d}"


def label_of(options: list[dict[str, str]], value: str | None) -> str:
    return next((item["label"] for item in options if item["value"] == value), value or "-")


async def customer_dict(customer: CrmCustomer, include_counts: bool = False) -> dict[str, Any]:
    data = await customer.to_dict()
    signing_entity = await customer.signing_entity if customer.signing_entity_id else None
    data["signing_entity_name"] = signing_entity.name if signing_entity else ""
    data["entity_type_label"] = label_of(ENTITY_TYPES, data.get("entity_type"))
    data["lifecycle_label"] = label_of(LIFECYCLES, data.get("lifecycle"))
    data["customer_level_label"] = label_of(LEVELS, data.get("customer_level"))
    if include_counts:
        data["contact_count"] = await CrmCustomerContact.filter(customers__id=customer.id).distinct().count()
        data["contract_count"] = await CrmCustomerContract.filter(customer_id=customer.id).count()
        data["bill_count"] = await CrmCustomerBill.filter(customer_id=customer.id).count()
    return data


async def contact_dict(contact: CrmCustomerContact) -> dict[str, Any]:
    data = await contact.to_dict()
    customers = await contact.customers.all().order_by("name")
    data["customer_ids"] = [customer.id for customer in customers]
    data["customer_name"] = " / ".join(customer.name for customer in customers)
    data["contact_type_label"] = label_of(CONTACT_TYPES, data.get("contact_type"))
    data["role"] = normalize_contact_roles(data.get("role"))
    data["role_label"] = " / ".join(label_of(CONTACT_ROLES, role) for role in data["role"])
    return data


async def contract_dict(contract: CrmCustomerContract) -> dict[str, Any]:
    data = await contract.to_dict()
    customer = await contract.customer
    signing_entity = await contract.signing_entity if contract.signing_entity_id else None
    data["customer_name"] = customer.name
    data["signing_entity_name"] = signing_entity.name if signing_entity else ""
    data["status_label"] = label_of(CONTRACT_STATUSES, data.get("status"))
    data["amount"] = float(data.get("amount") or 0)
    return data


async def bill_dict(bill: CrmCustomerBill) -> dict[str, Any]:
    data = await bill.to_dict()
    customer = await bill.customer
    data["customer_name"] = customer.name
    data["status_label"] = label_of(BILL_STATUSES, data.get("status"))
    data["amount"] = float(data.get("amount") or 0)
    return data


@router.get("/options", summary="客户中心选项")
async def options():
    signing_entities = await CrmSigningEntity.filter(status=True).order_by("name")
    customers = (
        await CrmCustomer.filter(status=True)
        .exclude(lifecycle="terminated")
        .order_by("name")
        .values("id", "customer_code", "name", "legal_name", "signing_entity__name")
    )
    return Success(
        data={
            "signing_entities": [await item.to_dict() for item in signing_entities],
            "customers": [
                {
                    "label": item["legal_name"] or item["name"],
                    "value": item["id"],
                    "name": item["name"],
                    "customer_code": item.get("customer_code") or "",
                    "short_name": item["name"],
                    "signing_entity_name": item.get("signing_entity__name") or "",
                }
                for item in customers
            ],
            "entity_types": ENTITY_TYPES,
            "lifecycles": LIFECYCLES,
            "levels": LEVELS,
            "contact_roles": CONTACT_ROLES,
            "contact_types": CONTACT_TYPES,
            "contract_statuses": CONTRACT_STATUSES,
            "bill_statuses": BILL_STATUSES,
            "currencies": [{"label": item, "value": item} for item in ["USD", "CNY", "HKD", "EUR", "GBP", "SGD"]],
        }
    )


@router.get("/dashboard", summary="客户中心概览")
async def dashboard():
    today = date.today()
    soon = today + timedelta(days=30)
    return Success(
        data={
            "customers": await CrmCustomer.all().count(),
            "active_customers": await CrmCustomer.filter(lifecycle="active").count(),
            "contracts": await CrmCustomerContract.all().count(),
            "expiring_contracts": await CrmCustomerContract.filter(
                expiry_date__gte=today,
                expiry_date__lte=soon,
                status__in=["active", "expiring"],
            ).count(),
            "contacts": await CrmCustomerContact.all().count(),
            "unsettled_bills": await CrmCustomerBill.filter(is_settled=False).count(),
        }
    )


@router.get("/signing-entities", summary="签约主体列表")
async def signing_entities():
    rows = await CrmSigningEntity.filter(status=True).order_by("name")
    return Success(data=[await item.to_dict() for item in rows])


@router.get("/customers", summary="客户列表")
async def list_customers(
    page: int = Query(1),
    page_size: int = Query(20),
    keyword: str = Query(""),
    lifecycle: str = Query(""),
    customer_level: str = Query(""),
    entity_type: str = Query(""),
    sales_owner: str = Query(""),
    region: str = Query(""),
    signing_entity_id: int | None = Query(None),
    customer_code_order: str = Query(""),
):
    q = Q()
    if keyword:
        q &= (
            Q(name__contains=keyword)
            | Q(legal_name__contains=keyword)
            | Q(alias__contains=keyword)
            | Q(customer_code__contains=keyword)
            | Q(sales_owner__contains=keyword)
            | Q(region__contains=keyword)
        )
    if lifecycle:
        q &= Q(lifecycle=lifecycle)
    if customer_level:
        q &= Q(customer_level=customer_level)
    if entity_type:
        q &= Q(entity_type=entity_type)
    if sales_owner:
        q &= Q(sales_owner__contains=sales_owner)
    if region:
        q &= Q(region__contains=region)
    if signing_entity_id:
        q &= Q(signing_entity_id=signing_entity_id)
    total = await CrmCustomer.filter(q).count()
    if customer_code_order == "ascend":
        order_by = ("customer_code", "customer_level", "name")
    elif customer_code_order == "descend":
        order_by = ("-customer_code", "customer_level", "name")
    else:
        order_by = ("customer_level", "name")
    rows = await CrmCustomer.filter(q).order_by(*order_by).offset((page - 1) * page_size).limit(page_size)
    return SuccessExtra(data=[await customer_dict(item, include_counts=True) for item in rows], total=total, page=page, page_size=page_size)


@router.get("/customers/export", summary="导出客户列表")
async def export_customers(
    keyword: str = Query(""),
    lifecycle: str = Query(""),
    customer_level: str = Query(""),
    entity_type: str = Query(""),
    sales_owner: str = Query(""),
    region: str = Query(""),
    signing_entity_id: int | None = Query(None),
    customer_code_order: str = Query(""),
):
    q = Q()
    if keyword:
        q &= (
            Q(name__contains=keyword)
            | Q(legal_name__contains=keyword)
            | Q(alias__contains=keyword)
            | Q(customer_code__contains=keyword)
            | Q(sales_owner__contains=keyword)
            | Q(region__contains=keyword)
        )
    if lifecycle:
        q &= Q(lifecycle=lifecycle)
    if customer_level:
        q &= Q(customer_level=customer_level)
    if entity_type:
        q &= Q(entity_type=entity_type)
    if sales_owner:
        q &= Q(sales_owner__contains=sales_owner)
    if region:
        q &= Q(region__contains=region)
    if signing_entity_id:
        q &= Q(signing_entity_id=signing_entity_id)
    if customer_code_order == "ascend":
        order_by = ("customer_code", "customer_level", "name")
    elif customer_code_order == "descend":
        order_by = ("-customer_code", "customer_level", "name")
    else:
        order_by = ("customer_level", "name")

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "客户编号",
            "客户简称",
            "客户全称",
            "主体类型",
            "签约主体",
            "等级",
            "生命周期",
            "所属销售",
            "所属地区",
            "联系人",
            "合同",
            "账单",
        ]
    )
    for customer in await CrmCustomer.filter(q).order_by(*order_by):
        data = await customer_dict(customer, include_counts=True)
        writer.writerow(
            [
                data.get("customer_code") or "",
                data.get("name") or "",
                data.get("legal_name") or "",
                data.get("entity_type_label") or "",
                data.get("signing_entity_name") or "",
                data.get("customer_level_label") or "",
                data.get("lifecycle_label") or "",
                data.get("sales_owner") or "",
                data.get("region") or "",
                data.get("contact_count") or 0,
                data.get("contract_count") or 0,
                data.get("bill_count") or 0,
            ]
        )
    return StreamingResponse(
        iter(["\ufeff" + output.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=customers.csv"},
    )


@router.get("/customers/next-code", summary="预览下一个客户编号")
async def preview_next_customer_code(signing_entity_id: int = Query(...)):
    customer_code = await next_customer_code(signing_entity_id)
    if not customer_code:
        return Fail(msg="签约主体不存在，无法生成客户编号")
    return Success(data={"customer_code": customer_code})


@router.get("/customers/{customer_id}", summary="客户详情")
async def get_customer(customer_id: int):
    customer = await CrmCustomer.get(id=customer_id)
    data = await customer_dict(customer, include_counts=True)
    contacts = await CrmCustomerContact.filter(customers__id=customer_id).distinct().order_by("role", "name")
    contracts = await CrmCustomerContract.filter(customer_id=customer_id).order_by("-expiry_date", "-id")
    bills = await CrmCustomerBill.filter(customer_id=customer_id).order_by("-bill_date", "-id")
    data["contacts"] = [await contact_dict(item) for item in contacts]
    data["contracts"] = [await contract_dict(item) for item in contracts]
    data["bills"] = [await bill_dict(item) for item in bills]
    return Success(data=data)


@router.post("/customers", summary="新增客户")
async def create_customer(payload: CustomerPayload):
    data = compact(payload.model_dump())
    if data.get("legal_name"):
        data["legal_name"] = str(data["legal_name"]).strip() or None
    data["customer_level"] = str(data.get("customer_level") or "C").upper()
    data["lifecycle"] = data.get("lifecycle") or "active"
    data["alias"] = data.get("name")
    if not data.get("signing_entity_id"):
        return Fail(msg="请选择签约主体后再生成客户编号")
    if await customer_full_name_exists(data.get("legal_name"), data.get("signing_entity_id")):
        return Fail(msg="该签约主体下已存在相同客户全称，请勿重复添加")
    if not data.get("customer_code"):
        data["customer_code"] = await next_customer_code(data.get("signing_entity_id"))
    if not data.get("customer_code"):
        return Fail(msg="签约主体不存在，无法生成客户编号")
    if await CrmCustomer.filter(customer_code=data["customer_code"]).exists():
        return Fail(msg="客户编号已存在，请修改后重试")
    customer = await CrmCustomer.create(**data)
    return Success(msg="客户已创建", data=await customer_dict(customer, include_counts=True))


@router.put("/customers/{customer_id}", summary="编辑客户")
async def update_customer(customer_id: int, payload: CustomerPayload):
    data = compact(payload.model_dump(exclude_unset=True))
    if data.get("legal_name"):
        data["legal_name"] = str(data["legal_name"]).strip() or None
    customer = await CrmCustomer.get(id=customer_id)
    legal_name = data.get("legal_name", customer.legal_name)
    signing_entity_id = data.get("signing_entity_id", customer.signing_entity_id)
    if await customer_full_name_exists(legal_name, signing_entity_id, exclude_customer_id=customer_id):
        return Fail(msg="该签约主体下已存在相同客户全称，请勿重复添加")
    if "customer_level" in data:
        data["customer_level"] = str(data.get("customer_level") or "C").upper()
    if "name" in data:
        data["alias"] = data.get("name")
    if data.get("customer_code") and await CrmCustomer.filter(customer_code=data["customer_code"]).exclude(id=customer_id).exists():
        return Fail(msg="客户编号已存在，请修改后重试")
    await CrmCustomer.filter(id=customer_id).update(**data)
    customer = await CrmCustomer.get(id=customer_id)
    return Success(msg="客户已更新", data=await customer_dict(customer, include_counts=True))


@router.delete("/customers/{customer_id}", summary="删除客户")
async def delete_customer(customer_id: int):
    await CrmCustomer.filter(id=customer_id).delete()
    return Success(msg="客户已删除")


@router.get("/contacts", summary="联系人列表")
async def list_contacts(page: int = Query(1), page_size: int = Query(20), keyword: str = Query(""), customer_id: int | None = Query(None), role: str = Query("")):
    q = Q()
    if keyword:
        customer_ids = await CrmCustomer.filter(Q(name__contains=keyword) | Q(legal_name__contains=keyword)).values_list("id", flat=True)
        q &= Q(name__contains=keyword) | Q(email__contains=keyword) | Q(phone__contains=keyword) | Q(customers__id__in=customer_ids)
    if customer_id:
        q &= Q(customers__id=customer_id)
    if role:
        q &= Q(role__contains=role)
    contacts = CrmCustomerContact.filter(q).distinct()
    total = await contacts.count()
    rows = await contacts.order_by("role", "name").offset((page - 1) * page_size).limit(page_size)
    return SuccessExtra(data=[await contact_dict(item) for item in rows], total=total, page=page, page_size=page_size)


@router.post("/contacts", summary="新增联系人")
async def create_contact(payload: ContactPayload):
    data = normalize_contact_data(payload.model_dump())
    customer_ids = normalize_customer_ids(data.pop("customer_ids", []), data.get("customer_id"))
    valid_customer_count = await CrmCustomer.filter(id__in=customer_ids, status=True).exclude(lifecycle="terminated").count()
    if not customer_ids or valid_customer_count != len(customer_ids):
        return Fail(msg="请选择有效客户，已终止客户不能继续维护联系人")
    data["customer_id"] = customer_ids[0]
    contact = await CrmCustomerContact.create(**data)
    customers = await CrmCustomer.filter(id__in=customer_ids)
    await contact.customers.add(*customers)
    return Success(msg="联系人已创建", data=await contact_dict(contact))


@router.put("/contacts/{contact_id}", summary="编辑联系人")
async def update_contact(contact_id: int, payload: ContactPayload):
    data = normalize_contact_data(payload.model_dump(exclude_unset=True))
    has_customer_update = "customer_ids" in data or "customer_id" in data
    customer_ids = normalize_customer_ids(data.pop("customer_ids", []), data.get("customer_id")) if has_customer_update else []
    if has_customer_update:
        valid_customer_count = await CrmCustomer.filter(id__in=customer_ids, status=True).exclude(lifecycle="terminated").count()
        if not customer_ids or valid_customer_count != len(customer_ids):
            return Fail(msg="请选择有效客户，已终止客户不能继续维护联系人")
        data["customer_id"] = customer_ids[0]
    await CrmCustomerContact.filter(id=contact_id).update(**data)
    contact = await CrmCustomerContact.get(id=contact_id)
    if has_customer_update:
        await contact.customers.clear()
        customers = await CrmCustomer.filter(id__in=customer_ids)
        await contact.customers.add(*customers)
    return Success(msg="联系人已更新", data=await contact_dict(contact))


@router.delete("/contacts/{contact_id}", summary="删除联系人")
async def delete_contact(contact_id: int):
    await CrmCustomerContact.filter(id=contact_id).delete()
    return Success(msg="联系人已删除")


@router.get("/contracts", summary="合同列表")
async def list_contracts(page: int = Query(1), page_size: int = Query(20), keyword: str = Query(""), customer_id: int | None = Query(None), status: str = Query(""), signing_entity_id: int | None = Query(None)):
    q = Q()
    if keyword:
        customer_ids = await CrmCustomer.filter(Q(name__contains=keyword) | Q(legal_name__contains=keyword)).values_list("id", flat=True)
        q &= Q(name__contains=keyword) | Q(contract_no__contains=keyword) | Q(customer_id__in=customer_ids)
    if customer_id:
        q &= Q(customer_id=customer_id)
    if status:
        q &= Q(status=status)
    if signing_entity_id:
        q &= Q(signing_entity_id=signing_entity_id)
    total = await CrmCustomerContract.filter(q).count()
    rows = await CrmCustomerContract.filter(q).order_by("-expiry_date", "-id").offset((page - 1) * page_size).limit(page_size)
    return SuccessExtra(data=[await contract_dict(item) for item in rows], total=total, page=page, page_size=page_size)


@router.post("/contracts", summary="新增合同")
async def create_contract(payload: ContractPayload):
    data = compact(payload.model_dump())
    if not await customer_selectable(data.get("customer_id")):
        return Fail(msg="请选择有效客户，已终止客户不能继续维护合同")
    contract = await CrmCustomerContract.create(**data)
    return Success(msg="合同已创建", data=await contract_dict(contract))


@router.put("/contracts/{contract_id}", summary="编辑合同")
async def update_contract(contract_id: int, payload: ContractPayload):
    data = compact(payload.model_dump(exclude_unset=True))
    if data.get("customer_id") and not await customer_selectable(data.get("customer_id")):
        return Fail(msg="请选择有效客户，已终止客户不能继续维护合同")
    await CrmCustomerContract.filter(id=contract_id).update(**data)
    contract = await CrmCustomerContract.get(id=contract_id)
    return Success(msg="合同已更新", data=await contract_dict(contract))


@router.delete("/contracts/{contract_id}", summary="删除合同")
async def delete_contract(contract_id: int):
    await CrmCustomerContract.filter(id=contract_id).delete()
    return Success(msg="合同已删除")


@router.get("/bills", summary="客户账单列表")
async def list_bills(page: int = Query(1), page_size: int = Query(20), customer_id: int | None = Query(None)):
    q = Q()
    if customer_id:
        q &= Q(customer_id=customer_id)
    total = await CrmCustomerBill.filter(q).count()
    rows = await CrmCustomerBill.filter(q).order_by("-bill_date", "-id").offset((page - 1) * page_size).limit(page_size)
    return SuccessExtra(data=[await bill_dict(item) for item in rows], total=total, page=page, page_size=page_size)


@router.post("/bills", summary="新增账单")
async def create_bill(payload: BillPayload):
    data = compact(payload.model_dump())
    if not await customer_selectable(data.get("customer_id")):
        return Fail(msg="请选择有效客户，已终止客户不能继续维护账单")
    bill = await CrmCustomerBill.create(**data)
    return Success(msg="账单已创建", data=await bill_dict(bill))


@router.put("/bills/{bill_id}", summary="编辑账单")
async def update_bill(bill_id: int, payload: BillPayload):
    data = compact(payload.model_dump(exclude_unset=True))
    if data.get("customer_id") and not await customer_selectable(data.get("customer_id")):
        return Fail(msg="请选择有效客户，已终止客户不能继续维护账单")
    await CrmCustomerBill.filter(id=bill_id).update(**data)
    bill = await CrmCustomerBill.get(id=bill_id)
    return Success(msg="账单已更新", data=await bill_dict(bill))


@router.delete("/bills/{bill_id}", summary="删除账单")
async def delete_bill(bill_id: int):
    await CrmCustomerBill.filter(id=bill_id).delete()
    return Success(msg="账单已删除")
