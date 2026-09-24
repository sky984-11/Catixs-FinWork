from __future__ import annotations

import asyncio
import base64
import binascii
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from fastapi import APIRouter, File, Request, UploadFile
from tortoise.transactions import in_transaction
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from app.log import logger
from app.core.dependency import DependAuth, has_admin_role
from app.models.asset import AssetLocation
from app.models.customer_center import CrmCustomer
from app.models.admin import User
from app.models.remote_assistance import RemoteEngineer, RemoteHands, RemoteHandsPlan
from app.schemas.base import Fail, Success
from app.schemas.remote_billing import (
    BillingContext, BillingPreviewPayload, CustomerMaintenancePrice, EngineerBillingRules, GeneralBillingRules,
    MaintenanceBillingRules, validate_billing_timezone,
)
from app.services.remote_billing import calculate_record_fee
from app.services.remote_timezone import region_timezone
from app.services.remote_hands_plan_notifier import int_list, notify_remote_hands_plan

router = APIRouter()
auth_router = APIRouter()
LOCAL_TIMEZONE = timezone(timedelta(hours=8))
PLAN_ATTACHMENT_DIR = Path(__file__).resolve().parents[4] / "uploads" / "remote-plans"
MAX_ATTACHMENT_SIZE = 20 * 1024 * 1024


class AttachmentUploadPayload(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    content_type: str = Field(default="application/octet-stream", max_length=255)
    data: str = Field(max_length=((MAX_ATTACHMENT_SIZE + 2) // 3) * 4 + 512)


ATTACHMENT_UPLOAD_OPENAPI = {
    "requestBody": {
        "required": True,
        "content": {"application/json": {"schema": AttachmentUploadPayload.model_json_schema()}},
    }
}


class PlanAttachment(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    url: str = Field(pattern=r"^/uploads/remote-plans/[0-9a-f]{32}\.bin$")
    size: int = Field(gt=0, le=MAX_ATTACHMENT_SIZE)


class AttachmentDeletePayload(BaseModel):
    url: str = Field(pattern=r"^/uploads/remote-plans/[0-9a-f]{32}\.bin$")


class RemoteHandsPayload(BaseModel):
    model_config = ConfigDict(extra="allow")

    customer: str = ""
    customer_id: int | None = Field(default=None, gt=0)
    customer_pricing: CustomerMaintenancePrice | None = None
    ticket: str = ""
    engineer_id: int | None = None
    engineer_name: str = ""
    engineer_contact: str = ""
    engineer_wechat: str = ""
    engineer_group: str = ""
    region: str = ""
    site: str = ""
    rack: str = ""
    timezone: str = "Asia/Shanghai"
    arrived_at: str | None = ""
    left_at: str | None = ""
    work_minutes: int = 0
    status: Literal["scheduled", "arrived", "done", "cancelled"] = "scheduled"
    is_settled: bool | None = None
    ops_settlement_status: Literal["unbilled", "billed", "settled"] = "unbilled"
    customer_settlement_status: Literal["unbilled", "billed", "settled"] = "unbilled"
    note: str = ""
    attachments: list[PlanAttachment] = Field(default_factory=list, max_length=50)
    billing_context: BillingContext | None = None
    refresh_billing_rules: bool = False
    _valid_timezone = field_validator("timezone")(validate_billing_timezone)


class EngineerPayload(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str = ""
    contact: str = ""
    wechat_id: str = ""
    wechat_group: str = ""
    region: str = ""
    is_active: int = 1
    note: str = ""
    billing_rules: GeneralBillingRules | EngineerBillingRules | MaintenanceBillingRules | None = None


class RemoteHandsPlanPayload(BaseModel):
    model_config = ConfigDict(extra="allow")

    customer: str = ""
    customer_id: int | None = Field(default=None, gt=0)
    customer_pricing: CustomerMaintenancePrice | None = None
    ticket: str = ""
    engineer_id: int | None = None
    engineer_name: str = ""
    engineer_contact: str = ""
    engineer_wechat: str = ""
    engineer_group: str = ""
    assignee_id: int | None = None
    assignee_ids: list[int] = Field(default_factory=list)
    region: str = ""
    site: str = ""
    rack: str = ""
    timezone: str = "Asia/Shanghai"
    planned_at: str | None = ""
    status: Literal["pending", "done", "cancelled"] = "pending"
    note: str = ""
    notify: bool = False
    attachments: list[PlanAttachment] = Field(default_factory=list, max_length=50)
    _valid_timezone = field_validator("timezone")(validate_billing_timezone)


class RemoteHandsPlanCompletePayload(BaseModel):
    model_config = ConfigDict(extra="allow")

    arrived_at: str | None = ""
    left_at: str | None = ""
    note: str = ""


def _naive_datetime(value: datetime | None) -> datetime | None:
    if not value:
        return None
    if value.tzinfo:
        value = value.astimezone(LOCAL_TIMEZONE)
    return value.replace(tzinfo=None)


def _parse_datetime(value: str | datetime | None) -> datetime | None:
    if isinstance(value, datetime):
        return _naive_datetime(value)
    text = str(value or "").strip()
    if not text:
        return None
    if text.isdigit():
        try:
            timestamp = int(text)
            if len(text) == 10:
                timestamp *= 1000
            return _naive_datetime(datetime.fromtimestamp(timestamp / 1000, tz=LOCAL_TIMEZONE))
        except (OverflowError, ValueError, OSError):
            return None
    normalized = text.replace("/", "-").replace("Z", "+00:00")
    try:
        value = datetime.fromisoformat(normalized)
        return _naive_datetime(value)
    except ValueError:
        pass
    match = re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})(?:[T\s](\d{1,2})(?::(\d{1,2})(?::(\d{1,2}))?)?)?", normalized)
    if match:
        year, month, day, hour, minute, second = match.groups(default="0")
        try:
            return datetime(
                int(year),
                int(month),
                int(day),
                int(hour or 0),
                int(minute or 0),
                int(second or 0),
            )
        except ValueError:
            pass
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return _naive_datetime(datetime.strptime(normalized[:19], fmt))
        except ValueError:
            continue
    logger.warning("remote assistance datetime parse failed: raw={}", text)
    return None


def _now_naive() -> datetime:
    return datetime.now(LOCAL_TIMEZONE).replace(tzinfo=None)


def _format_datetime(value: datetime | None) -> str | None:
    if not value:
        return None
    if value.tzinfo:
        value = value.astimezone(LOCAL_TIMEZONE)
    return value.strftime("%Y-%m-%dT%H:%M")


def _display_datetime(value: datetime | None) -> str:
    return value.strftime("%Y-%m-%d %H:%M") if value else "-"


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def _user_display_name(user: User | None) -> str:
    if not user:
        return ""
    return _clean_text(user.alias) or _clean_text(user.username) or _clean_text(user.email)


def _work_minutes_between(start: datetime | None, end: datetime | None) -> int:
    if not start or not end:
        return 0
    if end < start:
        raise ValueError("离场时间不能早于到场时间")
    return max(int((end - start).total_seconds() // 60), 0)


def _plan_snapshot(plan: RemoteHandsPlan) -> dict[str, Any]:
    return {
        "customer": plan.customer,
        "customer_id": plan.customer_id,
        "ticket": plan.ticket,
        "engineer_name": plan.engineer_name,
        "engineer_contact": plan.engineer_contact,
        "engineer_wechat": plan.engineer_wechat,
        "engineer_group": plan.engineer_group,
        "assignee_names": plan.assignee_names,
        "assignee_ids": int_list(plan.assignee_ids) or int_list(plan.assignee_id),
        "region": plan.region,
        "site": plan.site,
        "rack": plan.rack,
        "planned_at": _naive_datetime(plan.planned_at),
        "note": plan.note,
        "attachments": [item["name"] for item in (plan.attachments or [])],
    }


def _plan_value_for_compare(value: Any) -> str:
    if isinstance(value, datetime):
        return _display_datetime(_naive_datetime(value))
    if isinstance(value, list):
        return ",".join(str(item) for item in value)
    return _clean_text(value) or "-"


def _plan_change_rows(before: dict[str, Any], after: dict[str, Any]) -> list[dict[str, str]]:
    labels = {
        "attachments": "附件",
        "customer": "客户",
        "ticket": "工单",
        "engineer_name": "工程师",
        "engineer_contact": "工程师联系方式",
        "engineer_wechat": "工程师 TG/微信",
        "engineer_group": "工程师群组",
        "assignee_names": "通知接收人",
        "region": "地区",
        "site": "机房",
        "rack": "机柜/位置",
        "planned_at": "计划时间",
        "note": "说明",
    }
    rows = []
    for key, label in labels.items():
        old_value = _plan_value_for_compare(before.get(key))
        new_value = _plan_value_for_compare(after.get(key))
        if old_value != new_value:
            rows.append({"label": label, "old": old_value, "new": new_value})
    return rows


def _plan_change_elements(changes: list[dict[str, str]], operator_name: str = "") -> list[dict[str, Any]]:
    elements: list[dict[str, Any]] = []
    if operator_name:
        elements.append({"tag": "div", "text": {"tag": "lark_md", "content": f"**操作人：** {operator_name}"}})
    if not changes:
        elements.append({"tag": "div", "text": {"tag": "lark_md", "content": "**变更内容：** 无字段变化"}})
        return elements
    content = "\n".join(
        f"- **{item['label']}：** {item['old']} → {item['new']}"
        for item in changes
    )
    elements.append({"tag": "div", "text": {"tag": "lark_md", "content": f"**变更内容：**\n{content}"}})
    return elements


async def _save_plan_notify_result(plan: RemoteHandsPlan, ok: bool, message: str) -> None:
    now = _now_naive()
    plan.notify_status = "sent" if ok else "failed"
    plan.notify_message = message[:500]
    plan.notified_at = now if ok else plan.notified_at
    if ok and plan.planned_at and now < _naive_datetime(plan.planned_at) <= now + timedelta(days=1):
        plan.reminder_notified_at = plan.reminder_notified_at or now
    _normalize_plan_datetimes(plan)
    await plan.save(update_fields=["notify_status", "notify_message", "notified_at", "reminder_notified_at", "updated_at"])


def _is_settled_from_item(item: RemoteHands) -> bool:
    if bool(getattr(item, "is_settled", False)):
        return True
    return (
        (item.ops_settlement_status or "unbilled") == "settled"
        and (item.customer_settlement_status or "unbilled") == "settled"
    )


async def _remote_payload_data(payload: RemoteHandsPayload, existing: RemoteHands | None = None) -> dict[str, Any]:
    if existing and "customer_id" not in payload.model_fields_set and payload.customer == existing.customer:
        payload.customer_id = existing.customer_id
    await _validate_attachments(payload.attachments)
    arrived_at = _naive_datetime(_parse_datetime(payload.arrived_at))
    left_at = _naive_datetime(_parse_datetime(payload.left_at))
    if (payload.arrived_at and arrived_at is None) or (payload.left_at and left_at is None):
        raise ValueError("到场或离场时间无效，请按北京时间填写")
    is_settled = bool(payload.is_settled) if payload.is_settled is not None else (
        payload.ops_settlement_status == "settled" and payload.customer_settlement_status == "settled"
    )
    settlement_status = "settled" if is_settled else "unbilled"
    data = {
        "customer": await _customer_name(payload.customer_id, payload.customer),
        "customer_id": payload.customer_id,
        "ticket": _clean_text(payload.ticket) or None,
        "engineer_id": payload.engineer_id,
        "engineer_name": _clean_text(payload.engineer_name) or None,
        "engineer_contact": _clean_text(payload.engineer_contact) or None,
        "engineer_wechat": _clean_text(payload.engineer_wechat) or None,
        "engineer_group": _clean_text(payload.engineer_group) or None,
        "region": _clean_text(payload.region) or None,
        "site": _clean_text(payload.site) or None,
        "rack": _clean_text(payload.rack) or None,
        "timezone": region_timezone(payload.region) or _clean_text(payload.timezone) or "Asia/Shanghai",
        "arrived_at": arrived_at,
        "left_at": left_at,
        "work_minutes": _work_minutes_between(arrived_at, left_at),
        "status": payload.status,
        "is_settled": is_settled,
        "ops_settlement_status": settlement_status,
        "customer_settlement_status": settlement_status,
        "note": _clean_text(payload.note) or None,
    }
    if "attachments" in payload.model_fields_set:
        data["attachments"] = [item.model_dump() for item in payload.attachments]
    data["billing_data"] = await _billing_snapshot(data, payload.billing_context, existing, payload.refresh_billing_rules, payload.customer_pricing)
    return data


async def _customer_name(customer_id, name):
    if customer_id is None:
        return _clean_text(name)
    customer = await CrmCustomer.get_or_none(id=customer_id)
    if not customer:
        raise ValueError("客户不存在，请重新选择")
    return customer.name


def _default_customer_pricing(name):
    return {"kind": "internal"}


async def _billing_snapshot(data: dict, context: BillingContext | None = None, existing: RemoteHands | None = None, refresh=False, customer_pricing=None):
    old = (existing.billing_data or {}) if existing else {}
    rules = old.get("rules") if existing and existing.engineer_id == data.get("engineer_id") and not refresh else None
    if rules is None:
        engineer = await RemoteEngineer.get_or_none(id=data.get("engineer_id")) if data.get("engineer_id") else None
        rules = engineer.billing_rules if engineer else None
    same_customer = existing and existing.customer_id == data.get("customer_id") and existing.customer == data.get("customer")
    pricing = customer_pricing.model_dump(mode="json") if customer_pricing is not None else (old.get("customer_pricing") if same_customer else None)
    if pricing is None:
        pricing = _default_customer_pricing(data.get("customer"))
    ctx = context.model_dump(mode="json") if context is not None else old.get("context", {})
    result = await asyncio.to_thread(calculate_record_fee, rules, data.get("arrived_at"), data.get("left_at"),
                                    data.get("timezone") or "Asia/Shanghai", data.get("region") or "", ctx, pricing)
    return {"rules": rules, "context": ctx, "customer_pricing": pricing, "result": result}


@auth_router.post("/billing/preview", summary="根据北京时间和运维时区试算费用", dependencies=[DependAuth])
async def preview_billing(payload: BillingPreviewPayload):
    result = await asyncio.to_thread(calculate_record_fee, payload.rules.model_dump(mode="json") if payload.rules else None, payload.arrived_at,
                                    payload.left_at, payload.timezone, payload.region, payload.context.model_dump(mode="json"),
                                    payload.customer_pricing.model_dump(mode="json") if payload.customer_pricing else None)
    return Success(data=result)


def _engineer_payload_data(payload: EngineerPayload) -> dict[str, Any]:
    data = {
        "name": _clean_text(payload.name),
        "contact": _clean_text(payload.contact) or None,
        "wechat_id": _clean_text(payload.wechat_id) or None,
        "wechat_group": _clean_text(payload.wechat_group) or None,
        "region": _clean_text(payload.region) or None,
        "is_active": int(payload.is_active or 0),
        "note": _clean_text(payload.note) or None,
    }
    if "billing_rules" in payload.model_fields_set:
        data["billing_rules"] = payload.billing_rules.model_dump(mode="json") if payload.billing_rules else None
    return data


async def _validate_attachments(attachments: list[PlanAttachment]) -> None:
    for attachment in attachments:
        path = PLAN_ATTACHMENT_DIR / attachment.url.rsplit("/", 1)[-1]
        if not await asyncio.to_thread(path.is_file):
            raise ValueError("附件不存在，请重新上传")


async def _plan_payload_data(payload: RemoteHandsPlanPayload) -> dict[str, Any]:
    await _validate_attachments(payload.attachments)
    customer_name = await _customer_name(payload.customer_id, payload.customer)
    assignee_ids = int_list(payload.assignee_ids) or int_list(payload.assignee_id)
    users = await User.filter(id__in=assignee_ids, is_active=True) if assignee_ids else []
    user_map = {int(user.id): user for user in users}
    ordered_users = [user_map[user_id] for user_id in assignee_ids if user_id in user_map]
    assignee_names = [user.alias or user.username for user in ordered_users]
    return {
        "customer": customer_name,
        "customer_id": payload.customer_id,
        "customer_pricing": payload.customer_pricing.model_dump(mode="json") if payload.customer_pricing else _default_customer_pricing(customer_name),
        "ticket": _clean_text(payload.ticket) or None,
        "engineer_id": payload.engineer_id,
        "engineer_name": _clean_text(payload.engineer_name) or None,
        "engineer_contact": _clean_text(payload.engineer_contact) or None,
        "engineer_wechat": _clean_text(payload.engineer_wechat) or None,
        "engineer_group": _clean_text(payload.engineer_group) or None,
        "assignee_id": assignee_ids[0] if assignee_ids else None,
        "attachments": [item.model_dump() for item in payload.attachments],
        "assignee_ids": assignee_ids,
        "assignee_name": assignee_names[0] if assignee_names else None,
        "assignee_names": "、".join(assignee_names) or None,
        "region": _clean_text(payload.region) or None,
        "site": _clean_text(payload.site) or None,
        "rack": _clean_text(payload.rack) or None,
        "timezone": _clean_text(payload.timezone) or "Asia/Shanghai",
        "planned_at": _naive_datetime(_parse_datetime(payload.planned_at)),
        "status": payload.status,
        "note": _clean_text(payload.note) or None,
    }


def _normalize_plan_datetimes(plan: RemoteHandsPlan) -> None:
    plan.planned_at = _naive_datetime(plan.planned_at)
    plan.notified_at = _naive_datetime(plan.notified_at)
    plan.reminder_notified_at = _naive_datetime(plan.reminder_notified_at)


async def _remote_to_dict(item: RemoteHands, plans: list[RemoteHandsPlan] | None = None, engineer_rules=None) -> dict[str, Any]:
    billing = item.billing_data
    if not billing:
        if engineer_rules is None:
            engineer = await RemoteEngineer.get_or_none(id=item.engineer_id) if item.engineer_id else None
            rules = engineer.billing_rules if engineer else None
        else:
            rules = engineer_rules.get(item.engineer_id)
        result = await asyncio.to_thread(calculate_record_fee, rules, item.arrived_at, item.left_at,
                                        item.timezone or "Asia/Shanghai", item.region or "")
        billing = {"rules": rules, "context": {}, "result": result | {"basis": "current_rules"}}
    attachments = {value["url"]: value for value in (item.attachments or [])}
    if plans is None:
        plans = await RemoteHandsPlan.filter(remote_hands_id=item.id)
    for plan in plans:
        for value in plan.attachments or []:
            attachments.setdefault(value["url"], value)
    return {
        "id": item.id,
        "attachments": list(attachments.values()),
        "billing_context": billing.get("context", {}),
        "billing_rules_snapshot": billing.get("rules"),
        "customer_pricing_snapshot": billing.get("customer_pricing"),
        "billing_result": billing.get("result"),
        "customer": item.customer,
        "customer_id": item.customer_id,
        "ticket": item.ticket or "",
        "engineer_id": item.engineer_id,
        "engineer_name": item.engineer_name or "",
        "engineer_contact": item.engineer_contact or "",
        "engineer_wechat": item.engineer_wechat or "",
        "engineer_group": item.engineer_group or "",
        "region": item.region or "",
        "site": item.site or "",
        "rack": item.rack or "",
        "timezone": item.timezone or "Asia/Shanghai",
        "arrived_at": _format_datetime(item.arrived_at),
        "left_at": _format_datetime(item.left_at),
        "work_minutes": item.work_minutes or 0,
        "status": item.status or "scheduled",
        "is_settled": _is_settled_from_item(item),
        "ops_settlement_status": item.ops_settlement_status or "unbilled",
        "customer_settlement_status": item.customer_settlement_status or "unbilled",
        "note": item.note or "",
        "created_at": _format_datetime(item.created_at),
        "updated_at": _format_datetime(item.updated_at),
    }


async def _engineer_to_dict(item: RemoteEngineer) -> dict[str, Any]:
    return {
        "billing_rules": item.billing_rules,
        "id": item.id,
        "name": item.name,
        "contact": item.contact or "",
        "wechat_id": item.wechat_id or "",
        "wechat_group": item.wechat_group or "",
        "region": item.region or "",
        "is_active": item.is_active,
        "note": item.note or "",
        "created_at": _format_datetime(item.created_at),
        "updated_at": _format_datetime(item.updated_at),
    }


async def _plan_to_dict(item: RemoteHandsPlan) -> dict[str, Any]:
    return {
        "id": item.id,
        "customer": item.customer,
        "customer_id": item.customer_id,
        "customer_pricing": item.customer_pricing,
        "ticket": item.ticket or "",
        "engineer_id": item.engineer_id,
        "engineer_name": item.engineer_name or "",
        "engineer_contact": item.engineer_contact or "",
        "engineer_wechat": item.engineer_wechat or "",
        "engineer_group": item.engineer_group or "",
        "assignee_id": item.assignee_id,
        "assignee_ids": int_list(item.assignee_ids) or int_list(item.assignee_id),
        "assignee_name": item.assignee_name or "",
        "assignee_names": item.assignee_names or item.assignee_name or "",
        "created_by_id": item.created_by_id,
        "created_by_name": item.created_by_name or "",
        "region": item.region or "",
        "site": item.site or "",
        "rack": item.rack or "",
        "timezone": item.timezone or "Asia/Shanghai",
        "planned_at": _format_datetime(item.planned_at),
        "status": item.status or "pending",
        "notify_status": item.notify_status or "pending",
        "notify_message": item.notify_message or "",
        "notified_at": _format_datetime(item.notified_at),
        "reminder_notified_at": _format_datetime(item.reminder_notified_at),
        "remote_hands_id": item.remote_hands_id,
        "attachments": item.attachments or [],
        "note": item.note or "",
        "created_at": _format_datetime(item.created_at),
        "updated_at": _format_datetime(item.updated_at),
    }


async def _user_options() -> list[dict[str, Any]]:
    users = await User.filter(is_active=True).order_by("username")
    return [
        {
            "id": user.id,
            "label": user.alias or user.username,
            "username": user.username,
            "alias": user.alias or "",
            "email": user.email,
            "phone": user.phone or "",
        }
        for user in users
    ]


async def _datacenter_options() -> list[dict[str, Any]]:
    locations = await AssetLocation.filter(type=1, status=True).select_related("region").order_by("region__name", "name")
    options = []
    for item in locations:
        region = item.region
        region_name = region.name if region else ""
        country = region.country if region else ""
        city = region.city if region else ""
        options.append(
            {
                "id": item.id,
                "code": item.name,
                "name": item.name,
                "region": region_name or " / ".join([value for value in [country, city] if value]),
                "region_name": region_name,
                "country": country,
                "city": city,
                "location": item.name,
                "timezone": region_timezone(" / ".join(filter(None, [country, region_name, city]))),
            }
        )
    return options


@router.get("/overview", summary="运维记录页面数据")
async def overview():
    try:
        remote_hands = await RemoteHands.all().order_by("-arrived_at", "-created_at")
        plans = await RemoteHandsPlan.all().order_by("-planned_at", "-created_at")
        engineers = await RemoteEngineer.all().order_by("-is_active", "name")
        engineer_rules = {engineer.id: engineer.billing_rules for engineer in engineers}
        linked_plans: dict[int, list[RemoteHandsPlan]] = {}
        for plan in plans:
            if plan.remote_hands_id:
                linked_plans.setdefault(plan.remote_hands_id, []).append(plan)
        return Success(
            data={
                "remote_hands": [await _remote_to_dict(item, linked_plans.get(item.id, []), engineer_rules)
                                 for item in remote_hands],
                "plans": [await _plan_to_dict(item) for item in plans],
                "engineers": [await _engineer_to_dict(item) for item in engineers],
                "datacenters": await _datacenter_options(),
                "users": await _user_options(),
            }
        )
    except Exception as exc:
        return Fail(msg=f"读取运维记录数据失败: {exc}")


@router.post("/remote-hands", summary="新增运维记录")
async def create_remote_hands(payload: RemoteHandsPayload):
    try:
        data = await _remote_payload_data(payload)
        logger.info(
            "remote assistance create record parsed: customer={}, site={}, raw_arrived_at={}, parsed_arrived_at={}, raw_left_at={}, parsed_left_at={}",
            data["customer"],
            data["site"],
            payload.arrived_at,
            data["arrived_at"],
            payload.left_at,
            data["left_at"],
        )
        await RemoteHands.create(**data)
        return Success(msg="运维记录已创建")
    except Exception as exc:
        return Fail(msg=f"新增运维记录失败: {exc}")


@auth_router.post(
    "/plans/attachments/upload", summary="上传运维计划附件", dependencies=[DependAuth],
    openapi_extra=ATTACHMENT_UPLOAD_OPENAPI,
)
@auth_router.post(
    "/attachments/upload", summary="上传运维日志附件", dependencies=[DependAuth],
    openapi_extra=ATTACHMENT_UPLOAD_OPENAPI,
)
async def upload_plan_attachment(request: Request, file: UploadFile | None = File(None)):
    try:
        if request.headers.get("content-type", "").split(";", 1)[0].strip().lower() == "application/json":
            try:
                payload = AttachmentUploadPayload.model_validate(await request.json())
            except (ValidationError, ValueError, UnicodeDecodeError):
                return Fail(code=422, msg="附件参数无效或编码内容过大")
            encoded = payload.data.strip()
            if encoded.startswith("data:"):
                header, separator, encoded = encoded.partition(",")
                if not separator or not header.endswith(";base64"):
                    return Fail(msg="附件编码无效")
            try:
                content = await asyncio.to_thread(base64.b64decode, encoded, validate=True)
            except (binascii.Error, ValueError):
                return Fail(msg="附件编码无效")
            original_name = payload.filename
        elif file is not None:
            content = await file.read(MAX_ATTACHMENT_SIZE + 1)
            original_name = file.filename or "attachment"
        else:
            return Fail(code=422, msg="请选择上传附件")
        if not content:
            return Fail(msg="附件不能为空")
        if len(content) > MAX_ATTACHMENT_SIZE:
            return Fail(msg="单个附件不能超过20MB")
        name = original_name.replace("\\", "/").rsplit("/", 1)[-1][:255]
        filename = f"{uuid4().hex}.bin"
        await asyncio.to_thread(PLAN_ATTACHMENT_DIR.mkdir, parents=True, exist_ok=True)
        await asyncio.to_thread((PLAN_ATTACHMENT_DIR / filename).write_bytes, content)
        logger.info("remote plan attachment uploaded: file={}, size={}", filename, len(content))
        return Success(
            data={"name": name or "attachment", "url": f"/uploads/remote-plans/{filename}", "size": len(content)}
        )
    except OSError:
        logger.exception("remote plan attachment upload failed")
        return Fail(code=500, msg="附件上传失败，请重试")
    finally:
        if file is not None:
            await file.close()


@auth_router.delete("/attachments", summary="删除运维日志附件")
async def delete_attachment(payload: AttachmentDeletePayload, current_user: User = DependAuth):
    # Check every reference before deleting the physical file, including completed plans.
    path = PLAN_ATTACHMENT_DIR / payload.url.rsplit("/", 1)[-1]
    staged_path = path.with_suffix(f".deleting-{uuid4().hex}")
    staged = False
    try:
        async with in_transaction():
            references = []
            for model, route in ((RemoteHands, "remote-hands/{item_id}"), (RemoteHandsPlan, "plans/{plan_id}")):
                for item in await model.all().select_for_update():
                    if any(attachment.get("url") == payload.url for attachment in (item.attachments or [])):
                        references.append((item, route))
            if references and not current_user.is_superuser and not await has_admin_role(current_user):
                permissions = set()
                for role in await current_user.roles:
                    permissions.update((api.method, api.path) for api in await role.apis)
                for item, route in references:
                    paths = {
                        f"/api/v1/remote-assistance/{route}",
                        f"/api/v1/remote-assistance/{route.split('/')[0]}/{item.id}",
                    }
                    if not any(("PUT", path) in permissions for path in paths):
                        return Fail(code=403, msg="无关联运维记录或计划的编辑权限")
            try:
                await asyncio.to_thread(path.rename, staged_path)
                staged = True
            except FileNotFoundError:
                pass
            for item, _ in references:
                item.attachments = [value for value in item.attachments if value.get("url") != payload.url]
                await item.save(update_fields=["attachments", "updated_at"])
    except Exception:
        if staged:
            await asyncio.to_thread(staged_path.rename, path)
        logger.exception("remote attachment deletion failed")
        return Fail(code=500, msg="附件删除失败，请重试")
    try:
        await asyncio.to_thread(staged_path.unlink, missing_ok=True)
    except OSError:
        logger.exception("remote attachment staged file cleanup failed: file={}", staged_path.name)
        return Fail(code=500, msg="附件文件清理失败，请联系管理员")
    logger.info("remote attachment deleted: file={}, user={}", path.name, current_user.id)
    return Success(msg="附件已删除")


@router.post("/plans", summary="新增运维计划")
async def create_plan(payload: RemoteHandsPlanPayload, current_user: User = DependAuth):
    return await _create_plan(payload, current_user)


@router.post("/plans/create", summary="新增运维计划")
async def create_plan_compat(payload: RemoteHandsPlanPayload, current_user: User = DependAuth):
    return await _create_plan(payload, current_user)


async def _create_plan(payload: RemoteHandsPlanPayload, current_user: User | None = None):
    try:
        data = await _plan_payload_data(payload)
        if current_user is not None:
            data["created_by_id"] = current_user.id
            data["created_by_name"] = _user_display_name(current_user) or None
        logger.info(
            "remote assistance create plan parsed: customer={}, site={}, raw_planned_at={}, parsed_planned_at={}",
            data["customer"],
            data["site"],
            payload.planned_at,
            data["planned_at"],
        )
        if not data["customer"]:
            return Fail(msg="请输入客户名称")
        if not data["region"] or not data["site"]:
            return Fail(msg="请选择地区和机房")
        if not data["planned_at"]:
            return Fail(msg="请选择计划时间")
        plan = await RemoteHandsPlan.create(**data)
        if payload.notify:
            ok, message = await notify_remote_hands_plan(plan)
            await _save_plan_notify_result(plan, ok, message)
        return Success(msg="运维计划已创建", data=await _plan_to_dict(plan))
    except Exception as exc:
        return Fail(msg=f"新增运维计划失败: {exc}")


@router.put("/plans/{plan_id}", summary="变更运维计划")
async def update_plan(plan_id: int, payload: RemoteHandsPlanPayload, current_user: User = DependAuth):
    try:
        plan = await RemoteHandsPlan.get_or_none(id=plan_id)
        if not plan:
            return Fail(msg="运维计划不存在")
        if "customer_pricing" not in payload.model_fields_set and payload.customer == plan.customer:
            payload.customer_pricing = CustomerMaintenancePrice.model_validate(plan.customer_pricing) if plan.customer_pricing else None
        if "customer_id" not in payload.model_fields_set and payload.customer == plan.customer:
            payload.customer_id = plan.customer_id
        if plan.status != "pending":
            return Fail(msg="只有待执行的运维计划才能变更")
        before = _plan_snapshot(plan)
        data = await _plan_payload_data(payload)
        if "attachments" not in payload.model_fields_set:
            data.pop("attachments", None)
        logger.info(
            "remote assistance update plan parsed: plan_id={}, customer={}, site={}, raw_planned_at={}, parsed_planned_at={}",
            plan_id,
            data["customer"],
            data["site"],
            payload.planned_at,
            data["planned_at"],
        )
        if not data["customer"]:
            return Fail(msg="请输入客户名称")
        if not data["region"] or not data["site"]:
            return Fail(msg="请选择地区和机房")
        if not data["planned_at"]:
            return Fail(msg="请选择计划时间")
        for key, value in data.items():
            setattr(plan, key, value)
        plan.reminder_notified_at = None
        _normalize_plan_datetimes(plan)
        await plan.save()
        after = _plan_snapshot(plan)
        changes = _plan_change_rows(before, after)
        if changes:
            recipient_ids = int_list(before.get("assignee_ids")) + [
                item for item in int_list(after.get("assignee_ids")) if item not in int_list(before.get("assignee_ids"))
            ]
            ok, message = await notify_remote_hands_plan(
                plan,
                title="运维计划变更",
                template="orange",
                extra_elements=_plan_change_elements(changes, _user_display_name(current_user)),
                include_detail=False,
                recipient_ids=recipient_ids,
            )
            await _save_plan_notify_result(plan, ok, message)
        return Success(msg="运维计划已变更", data=await _plan_to_dict(plan))
    except Exception as exc:
        return Fail(msg=f"变更运维计划失败: {exc}")


@router.post("/plans/{plan_id}/notify", summary="发送运维计划飞书通知")
async def notify_plan(plan_id: int):
    try:
        plan = await RemoteHandsPlan.get_or_none(id=plan_id)
        if not plan:
            return Fail(msg="运维计划不存在")
        ok, message = await notify_remote_hands_plan(plan)
        await _save_plan_notify_result(plan, ok, message)
        return Success(msg=message, data=await _plan_to_dict(plan))
    except Exception as exc:
        return Fail(msg=f"发送运维计划通知失败: {exc}")


@router.post("/plans/{plan_id}/complete", summary="完成运维计划并生成运维记录")
async def complete_plan(plan_id: int, payload: RemoteHandsPlanCompletePayload):
    try:
        plan = await RemoteHandsPlan.get_or_none(id=plan_id)
        if not plan:
            return Fail(msg="运维计划不存在")
        if plan.status == "done" and plan.remote_hands_id:
            return Fail(msg="该运维计划已完成")
        arrived_at = _naive_datetime(_parse_datetime(payload.arrived_at) or plan.planned_at) or _now_naive()
        left_at = _naive_datetime(_parse_datetime(payload.left_at)) or _now_naive()
        note = _clean_text(payload.note) or plan.note
        billing_data = await _billing_snapshot({"customer": plan.customer, "customer_id": plan.customer_id,
                                               "engineer_id": plan.engineer_id, "arrived_at": arrived_at,
                                               "left_at": left_at, "timezone": plan.timezone, "region": plan.region},
                                               customer_pricing=CustomerMaintenancePrice.model_validate(plan.customer_pricing) if plan.customer_pricing else None)
        remote = await RemoteHands.create(
            billing_data=billing_data,
            customer=plan.customer,
            customer_id=plan.customer_id,
            ticket=plan.ticket,
            engineer_id=plan.engineer_id,
            engineer_name=plan.engineer_name,
            engineer_contact=plan.engineer_contact,
            engineer_wechat=plan.engineer_wechat,
            engineer_group=plan.engineer_group,
            region=plan.region,
            site=plan.site,
            rack=plan.rack,
            timezone=plan.timezone or "Asia/Shanghai",
            arrived_at=arrived_at,
            left_at=left_at,
            work_minutes=_work_minutes_between(arrived_at, left_at),
            status="done",
            is_settled=False,
            ops_settlement_status="unbilled",
            customer_settlement_status="unbilled",
            note=note,
            attachments=plan.attachments or [],
        )
        plan.status = "done"
        plan.remote_hands_id = remote.id
        await plan.save(update_fields=["status", "remote_hands_id", "updated_at"])
        return Success(msg="运维计划已完成，运维记录已生成", data=await _remote_to_dict(remote))
    except Exception as exc:
        return Fail(msg=f"完成运维计划失败: {exc}")


@router.post("/plans/{plan_id}/cancel", summary="取消运维计划")
async def cancel_plan(plan_id: int, current_user: User = DependAuth):
    try:
        plan = await RemoteHandsPlan.get_or_none(id=plan_id)
        if not plan:
            return Fail(msg="运维计划不存在")
        if plan.status == "done":
            return Fail(msg="已完成的运维计划不能取消")
        if plan.status == "cancelled":
            return Success(msg="运维计划已取消", data=await _plan_to_dict(plan))
        plan.status = "cancelled"
        await plan.save(update_fields=["status", "updated_at"])
        ok, message = await notify_remote_hands_plan(
            plan,
            title="运维计划取消",
            template="red",
            extra_elements=[
                {"tag": "div", "text": {"tag": "lark_md", "content": f"**操作人：** {_user_display_name(current_user) or '-'}"}},
                {"tag": "div", "text": {"tag": "lark_md", "content": f"**取消时间：** {_display_datetime(_now_naive())}"}},
            ],
        )
        await _save_plan_notify_result(plan, ok, message)
        return Success(msg="运维计划已取消", data=await _plan_to_dict(plan))
    except Exception as exc:
        return Fail(msg=f"取消运维计划失败: {exc}")


@router.delete("/plans/{plan_id}", summary="删除运维计划")
async def delete_plan(plan_id: int):
    try:
        plan = await RemoteHandsPlan.get_or_none(id=plan_id)
        if not plan:
            return Fail(msg="运维计划不存在")
        if plan.status not in ["done", "cancelled"]:
            return Fail(msg="只有已完成或已取消的运维计划才能删除")
        await plan.delete()
        return Success(msg="运维计划已删除")
    except Exception as exc:
        return Fail(msg=f"删除运维计划失败: {exc}")


@router.put("/remote-hands/{item_id}", summary="更新运维记录")
async def update_remote_hands(item_id: int, payload: RemoteHandsPayload):
    try:
        existing = await RemoteHands.get_or_none(id=item_id)
        if not existing:
            return Fail(msg="运维记录不存在")
        data = await _remote_payload_data(payload, existing)
        logger.info(
            "remote assistance update record parsed: item_id={}, customer={}, site={}, raw_arrived_at={}, parsed_arrived_at={}, raw_left_at={}, parsed_left_at={}",
            item_id,
            data["customer"],
            data["site"],
            payload.arrived_at,
            data["arrived_at"],
            payload.left_at,
            data["left_at"],
        )
        updated = await RemoteHands.filter(id=item_id).update(**data)
        if not updated:
            return Fail(msg="运维记录不存在")
        return Success(msg="运维记录已更新")
    except Exception as exc:
        return Fail(msg=f"更新运维记录失败: {exc}")


@router.delete("/remote-hands/{item_id}", summary="删除运维记录")
async def delete_remote_hands(item_id: int):
    try:
        deleted = await RemoteHands.filter(id=item_id).delete()
        if not deleted:
            return Fail(msg="运维记录不存在")
        return Success(msg="运维记录已删除")
    except Exception as exc:
        return Fail(msg=f"删除运维记录失败: {exc}")


@router.post("/engineers", summary="新增工程师")
async def create_engineer(payload: EngineerPayload):
    try:
        await RemoteEngineer.create(**_engineer_payload_data(payload))
        return Success(msg="工程师已创建")
    except Exception as exc:
        return Fail(msg=f"新增工程师失败: {exc}")


@router.put("/engineers/{engineer_id}", summary="更新工程师")
async def update_engineer(engineer_id: int, payload: EngineerPayload):
    try:
        data = _engineer_payload_data(payload)
        updated = await RemoteEngineer.filter(id=engineer_id).update(**data)
        if not updated:
            return Fail(msg="工程师不存在")
        return Success(msg="工程师已更新")
    except Exception as exc:
        return Fail(msg=f"更新工程师失败: {exc}")


@router.delete("/engineers/{engineer_id}", summary="删除工程师")
async def delete_engineer(engineer_id: int):
    try:
        deleted = await RemoteEngineer.filter(id=engineer_id).delete()
        if not deleted:
            return Fail(msg="工程师不存在")
        return Success(msg="工程师已删除")
    except Exception as exc:
        return Fail(msg=f"删除工程师失败: {exc}")
