from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.log import logger
from app.models.admin import User
from app.models.asset import AssetDevice
from app.models.device_maintenance import DeviceMaintenanceTask
from app.schemas.base import Fail, Success
from app.services.device_maintenance_notifier import (
    device_parent_id,
    device_to_maintenance_rows,
    get_task_devices,
    int_list,
    notify_task,
    text,
    unique_device_keys,
)

router = APIRouter()


class MaintenanceTaskPayload(BaseModel):
    device_id: int | str | None = None
    device_ids: list[int | str] = Field(default_factory=list)
    title: str
    description: str = ""
    assignee_id: int | None = None
    assignee_ids: list[int] = Field(default_factory=list)
    due_at: str | None = None
    priority: Literal["low", "medium", "high", "urgent"] = "medium"
    status: Literal["pending", "processing", "done", "cancelled"] = "pending"
    remark: str = ""
    notify: bool = False


class MaintenanceTaskStatusPayload(BaseModel):
    status: Literal["pending", "processing", "done", "cancelled"]
    remark: str = ""


def parse_datetime(value: str | None) -> datetime | None:
    value = text(value)
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None


def format_datetime(value: datetime | None) -> str:
    return value.strftime("%Y-%m-%d %H:%M") if value else ""


async def task_to_dict(task: DeviceMaintenanceTask) -> dict[str, Any]:
    devices = await get_task_devices(task)
    assignee_ids = int_list(task.assignee_ids) or int_list(task.assignee_id)
    assignee_names = text(task.assignee_names) or text(task.assignee_name)
    return {
        "id": task.id,
        "device_id": task.device_id,
        "device_ids": unique_device_keys(task.device_ids) or unique_device_keys(task.device_id),
        "device": devices[0] if devices else {},
        "devices": devices,
        "title": task.title,
        "description": task.description or "",
        "assignee_id": task.assignee_id,
        "assignee_ids": assignee_ids,
        "assignee_name": task.assignee_name or "",
        "assignee_names": assignee_names,
        "due_at": format_datetime(task.due_at),
        "status": task.status,
        "priority": task.priority,
        "notify_status": task.notify_status,
        "notify_message": task.notify_message or "",
        "notified_at": format_datetime(task.notified_at),
        "reminder_notified_at": format_datetime(task.reminder_notified_at),
        "remark": task.remark or "",
        "created_at": format_datetime(task.created_at),
        "updated_at": format_datetime(task.updated_at),
    }


async def user_options() -> list[dict[str, Any]]:
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


async def resolve_device_rows(device_keys: list[str]) -> list[dict[str, Any]]:
    if not device_keys:
        return []
    parent_ids = [item for item in [device_parent_id(key) for key in device_keys] if item]
    devices = await AssetDevice.filter(id__in=parent_ids).select_related("region", "location", "cabinet")
    row_map = {}
    for device in devices:
        for row in device_to_maintenance_rows(device, include_plain=True):
            row_map[str(row["id"])] = row
    return [row_map[key] for key in device_keys if key in row_map]


async def resolve_users(user_ids: list[int]) -> list[User]:
    if not user_ids:
        return []
    users = await User.filter(id__in=user_ids, is_active=True)
    user_map = {int(user.id): user for user in users}
    return [user_map[user_id] for user_id in user_ids if user_id in user_map]


@router.get("/overview", summary="维护计划")
async def overview():
    try:
        raw_devices = await AssetDevice.all().select_related("region", "location", "cabinet").order_by(
            "region__name", "location__name", "cabinet__name", "u_position", "name"
        )
        devices = []
        for device in raw_devices:
            try:
                devices.extend(device_to_maintenance_rows(device))
            except Exception:
                logger.exception("build maintenance device row failed: device_id=%s", getattr(device, "id", None))
        tasks = await DeviceMaintenanceTask.all().order_by("-created_at")
        return Success(
            data={
                "devices": devices,
                "tasks": [await task_to_dict(task) for task in tasks],
                "users": await user_options(),
            }
        )
    except Exception as exc:
        logger.exception("device maintenance overview failed")
        return Fail(msg=f"读取维护计划数据失败: {exc}")


@router.post("/task", summary="新增维护计划")
async def create_task(payload: MaintenanceTaskPayload):
    title = text(payload.title)
    if not title:
        return Fail(msg="请填写维护计划标题")

    device_keys = unique_device_keys(payload.device_ids) or unique_device_keys(payload.device_id)
    if not device_keys:
        return Fail(msg="请选择维护设备")
    devices = await resolve_device_rows(device_keys)
    if len(devices) != len(device_keys):
        return Fail(msg="部分维护设备不存在")

    assignee_ids = int_list(payload.assignee_ids) or int_list(payload.assignee_id)
    users = await resolve_users(assignee_ids)
    if assignee_ids and len(users) != len(assignee_ids):
        return Fail(msg="部分负责人不存在或未启用")

    assignee_names = [user.alias or user.username for user in users]
    parent_id = device_parent_id(device_keys[0])
    if not parent_id:
        return Fail(msg="维护设备格式不正确")
    task = await DeviceMaintenanceTask.create(
        device_id=parent_id,
        device_ids=device_keys,
        title=title,
        description=text(payload.description) or None,
        assignee_id=assignee_ids[0] if assignee_ids else None,
        assignee_ids=assignee_ids,
        assignee_name=assignee_names[0] if assignee_names else None,
        assignee_names="、".join(assignee_names) or None,
        due_at=parse_datetime(payload.due_at),
        priority=payload.priority,
        status=payload.status,
        remark=text(payload.remark) or None,
    )
    if payload.notify:
        ok, message = await notify_task(task)
        task.notify_status = "sent" if ok else "failed"
        task.notify_message = message[:500]
        task.notified_at = datetime.now() if ok else None
        await task.save(update_fields=["notify_status", "notify_message", "notified_at", "updated_at"])
    return Success(msg="维护计划已创建", data=await task_to_dict(task))


@router.post("/task/{task_id}/notify", summary="发送维护计划飞书通知")
async def notify_task_api(task_id: int):
    task = await DeviceMaintenanceTask.get_or_none(id=task_id)
    if not task:
        return Fail(msg="维护计划不存在")
    ok, message = await notify_task(task)
    task.notify_status = "sent" if ok else "failed"
    task.notify_message = message[:500]
    task.notified_at = datetime.now() if ok else task.notified_at
    await task.save(update_fields=["notify_status", "notify_message", "notified_at", "updated_at"])
    return Success(msg=message, data=await task_to_dict(task))


@router.post("/task/{task_id}/status", summary="更新维护计划状态")
async def update_task_status(task_id: int, payload: MaintenanceTaskStatusPayload):
    task = await DeviceMaintenanceTask.get_or_none(id=task_id)
    if not task:
        return Fail(msg="维护计划不存在")
    task.status = payload.status
    if text(payload.remark):
        task.remark = text(payload.remark)
    await task.save(update_fields=["status", "remark", "updated_at"])
    return Success(msg="维护计划状态已更新")
