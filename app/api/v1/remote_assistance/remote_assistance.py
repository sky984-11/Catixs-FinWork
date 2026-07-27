from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict

from app.models.asset import AssetLocation
from app.models.remote_assistance import RemoteEngineer, RemoteHands
from app.schemas.base import Fail, Success

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


def _parse_datetime(value: str | None) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None


def _format_datetime(value: datetime | None) -> str | None:
    if not value:
        return None
    return value.strftime("%Y-%m-%dT%H:%M")


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def _remote_payload_data(payload: RemoteHandsPayload) -> dict[str, Any]:
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
        "arrived_at": _parse_datetime(payload.arrived_at),
        "left_at": _parse_datetime(payload.left_at),
        "work_minutes": int(payload.work_minutes or 0),
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


async def _datacenter_options() -> list[dict[str, Any]]:
    locations = await AssetLocation.filter(type=2, status=True).select_related("region").order_by("region__name", "name")
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
        engineers = await RemoteEngineer.all().order_by("-is_active", "name")
        return Success(
            data={
                "remote_hands": [await _remote_to_dict(item) for item in remote_hands],
                "engineers": [await _engineer_to_dict(item) for item in engineers],
                "datacenters": await _datacenter_options(),
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
