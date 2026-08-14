from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field

from app.log import logger
from app.models.asset import AssetLocation
from app.models.admin import User
from app.models.remote_assistance import RemoteEngineer, RemoteHands, RemoteHandsPlan
from app.schemas.base import Fail, Success
from app.services.remote_hands_plan_notifier import int_list, notify_remote_hands_plan

router = APIRouter()


class RemoteHandsPayload(BaseModel):
    model_config = ConfigDict(extra="allow")

    customer: str = ""
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
    ops_settlement_status: Literal["unbilled", "billed", "settled"] = "unbilled"
    customer_settlement_status: Literal["unbilled", "billed", "settled"] = "unbilled"
    note: str = ""


class EngineerPayload(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str = ""
    contact: str = ""
    wechat_id: str = ""
    wechat_group: str = ""
    region: str = ""
    is_active: int = 1
    note: str = ""


class RemoteHandsPlanPayload(BaseModel):
    model_config = ConfigDict(extra="allow")

    customer: str = ""
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


class RemoteHandsPlanCompletePayload(BaseModel):
    model_config = ConfigDict(extra="allow")

    arrived_at: str | None = ""
    left_at: str | None = ""
    note: str = ""


def _parse_datetime(value: str | None) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    if text.isdigit():
        try:
            timestamp = int(text)
            if len(text) == 10:
                timestamp *= 1000
            return datetime.fromtimestamp(timestamp / 1000).replace(tzinfo=None)
        except (OverflowError, ValueError, OSError):
            return None
    normalized = text.replace("/", "-").replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized).replace(tzinfo=None)
    except ValueError:
        pass
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(normalized[:19], fmt).replace(tzinfo=None)
        except ValueError:
            continue
    logger.warning("remote assistance datetime parse failed: raw={}", text)
    return None


def _naive_datetime(value: datetime | None) -> datetime | None:
    if not value:
        return None
    return value.replace(tzinfo=None)


def _now_naive() -> datetime:
    return datetime.now().replace(tzinfo=None)


def _format_datetime(value: datetime | None) -> str | None:
    if not value:
        return None
    return value.strftime("%Y-%m-%dT%H:%M")


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def _work_minutes_between(start: datetime | None, end: datetime | None) -> int:
    if not start or not end:
        return 0
    if end < start:
        raise ValueError("离场时间不能早于到场时间")
    return max(int((end - start).total_seconds() // 60), 0)


def _remote_payload_data(payload: RemoteHandsPayload) -> dict[str, Any]:
    arrived_at = _parse_datetime(payload.arrived_at)
    left_at = _parse_datetime(payload.left_at)
    return {
        "customer": _clean_text(payload.customer),
        "ticket": _clean_text(payload.ticket) or None,
        "engineer_id": payload.engineer_id,
        "engineer_name": _clean_text(payload.engineer_name) or None,
        "engineer_contact": _clean_text(payload.engineer_contact) or None,
        "engineer_wechat": _clean_text(payload.engineer_wechat) or None,
        "engineer_group": _clean_text(payload.engineer_group) or None,
        "region": _clean_text(payload.region) or None,
        "site": _clean_text(payload.site) or None,
        "rack": _clean_text(payload.rack) or None,
        "timezone": _clean_text(payload.timezone) or "Asia/Shanghai",
        "arrived_at": arrived_at,
        "left_at": left_at,
        "work_minutes": _work_minutes_between(arrived_at, left_at),
        "status": payload.status,
        "ops_settlement_status": payload.ops_settlement_status,
        "customer_settlement_status": payload.customer_settlement_status,
        "note": _clean_text(payload.note) or None,
    }


def _engineer_payload_data(payload: EngineerPayload) -> dict[str, Any]:
    return {
        "name": _clean_text(payload.name),
        "contact": _clean_text(payload.contact) or None,
        "wechat_id": _clean_text(payload.wechat_id) or None,
        "wechat_group": _clean_text(payload.wechat_group) or None,
        "region": _clean_text(payload.region) or None,
        "is_active": int(payload.is_active or 0),
        "note": _clean_text(payload.note) or None,
    }


async def _plan_payload_data(payload: RemoteHandsPlanPayload) -> dict[str, Any]:
    assignee_ids = int_list(payload.assignee_ids) or int_list(payload.assignee_id)
    users = await User.filter(id__in=assignee_ids, is_active=True) if assignee_ids else []
    user_map = {int(user.id): user for user in users}
    ordered_users = [user_map[user_id] for user_id in assignee_ids if user_id in user_map]
    assignee_names = [user.alias or user.username for user in ordered_users]
    return {
        "customer": _clean_text(payload.customer),
        "ticket": _clean_text(payload.ticket) or None,
        "engineer_id": payload.engineer_id,
        "engineer_name": _clean_text(payload.engineer_name) or None,
        "engineer_contact": _clean_text(payload.engineer_contact) or None,
        "engineer_wechat": _clean_text(payload.engineer_wechat) or None,
        "engineer_group": _clean_text(payload.engineer_group) or None,
        "assignee_id": assignee_ids[0] if assignee_ids else None,
        "assignee_ids": assignee_ids,
        "assignee_name": assignee_names[0] if assignee_names else None,
        "assignee_names": "、".join(assignee_names) or None,
        "region": _clean_text(payload.region) or None,
        "site": _clean_text(payload.site) or None,
        "rack": _clean_text(payload.rack) or None,
        "timezone": _clean_text(payload.timezone) or "Asia/Shanghai",
        "planned_at": _parse_datetime(payload.planned_at),
        "status": payload.status,
        "note": _clean_text(payload.note) or None,
    }


async def _remote_to_dict(item: RemoteHands) -> dict[str, Any]:
    return {
        "id": item.id,
        "customer": item.customer,
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
        "ops_settlement_status": item.ops_settlement_status or "unbilled",
        "customer_settlement_status": item.customer_settlement_status or "unbilled",
        "note": item.note or "",
        "created_at": _format_datetime(item.created_at),
        "updated_at": _format_datetime(item.updated_at),
    }


async def _engineer_to_dict(item: RemoteEngineer) -> dict[str, Any]:
    return {
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
                "timezone": "Asia/Shanghai",
            }
        )
    return options


@router.get("/overview", summary="运维记录页面数据")
async def overview():
    try:
        remote_hands = await RemoteHands.all().order_by("-arrived_at", "-created_at")
        plans = await RemoteHandsPlan.all().order_by("-planned_at", "-created_at")
        engineers = await RemoteEngineer.all().order_by("-is_active", "name")
        return Success(
            data={
                "remote_hands": [await _remote_to_dict(item) for item in remote_hands],
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
        data = _remote_payload_data(payload)
        await RemoteHands.create(**data)
        return Success(msg="运维记录已创建")
    except Exception as exc:
        return Fail(msg=f"新增运维记录失败: {exc}")


@router.post("/plans", summary="新增运维计划")
async def create_plan(payload: RemoteHandsPlanPayload):
    return await _create_plan(payload)


@router.post("/plans/create", summary="新增运维计划")
async def create_plan_compat(payload: RemoteHandsPlanPayload):
    return await _create_plan(payload)


async def _create_plan(payload: RemoteHandsPlanPayload):
    try:
        data = await _plan_payload_data(payload)
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
            plan.notify_status = "sent" if ok else "failed"
            plan.notify_message = message[:500]
            plan.notified_at = datetime.now() if ok else None
            await plan.save(update_fields=["notify_status", "notify_message", "notified_at", "updated_at"])
        return Success(msg="运维计划已创建", data=await _plan_to_dict(plan))
    except Exception as exc:
        return Fail(msg=f"新增运维计划失败: {exc}")


@router.put("/plans/{plan_id}", summary="变更运维计划")
async def update_plan(plan_id: int, payload: RemoteHandsPlanPayload):
    try:
        plan = await RemoteHandsPlan.get_or_none(id=plan_id)
        if not plan:
            return Fail(msg="运维计划不存在")
        if plan.status != "pending":
            return Fail(msg="只有待执行的运维计划才能变更")
        data = await _plan_payload_data(payload)
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
        if payload.notify:
            ok, message = await notify_remote_hands_plan(plan)
            plan.notify_status = "sent" if ok else "failed"
            plan.notify_message = message[:500]
            plan.notified_at = datetime.now() if ok else plan.notified_at
        await plan.save()
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
        plan.notify_status = "sent" if ok else "failed"
        plan.notify_message = message[:500]
        plan.notified_at = datetime.now() if ok else plan.notified_at
        await plan.save(update_fields=["notify_status", "notify_message", "notified_at", "updated_at"])
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
        remote = await RemoteHands.create(
            customer=plan.customer,
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
            ops_settlement_status="unbilled",
            customer_settlement_status="unbilled",
            note=note,
        )
        plan.status = "done"
        plan.remote_hands_id = remote.id
        await plan.save(update_fields=["status", "remote_hands_id", "updated_at"])
        return Success(msg="运维计划已完成，运维记录已生成", data=await _remote_to_dict(remote))
    except Exception as exc:
        return Fail(msg=f"完成运维计划失败: {exc}")


@router.post("/plans/{plan_id}/cancel", summary="取消运维计划")
async def cancel_plan(plan_id: int):
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
        data = _remote_payload_data(payload)
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
