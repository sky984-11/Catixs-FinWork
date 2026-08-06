from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from app.log import logger
from app.models.admin import User
from app.models.asset import AssetDevice
from app.models.device_maintenance import DeviceMaintenanceTask
from app.settings.config import settings
from app.utils.feishu_app import (
    feishu_app_enabled,
    lookup_feishu_user_id_by_email,
    lookup_feishu_user_id_by_mobile,
    send_feishu_app_card,
)


def text(value: Any) -> str:
    return str(value or "").strip()


def format_datetime(value: datetime | None) -> str:
    return value.strftime("%Y-%m-%d %H:%M") if value else ""


def normalize_device_status(value: Any, default: int = 0) -> int:
    try:
        status = int(value)
    except (TypeError, ValueError):
        return default
    return status if status in {0, 1, 2, 3, 4} else default


def is_four_node_device(attributes: dict) -> bool:
    attrs = attributes if isinstance(attributes, dict) else {}
    nodes = attrs.get("nodes")
    return (
        attrs.get("form_factor") == "four_node"
        or attrs.get("设备形态") == "四合一服务器"
        or attrs.get("设备形态") == "四节点服务器"
        or text(attrs.get("node_count") or attrs.get("节点数量")) == "4"
        or (isinstance(nodes, list) and len([node for node in nodes if isinstance(node, dict)]) >= 4)
    )


def normalize_four_node_list(attributes: dict) -> list[dict]:
    attrs = attributes if isinstance(attributes, dict) else {}
    nodes = attrs.get("nodes") if isinstance(attrs.get("nodes"), list) else []
    if is_four_node_device(attrs):
        normalized = [node for node in nodes if isinstance(node, dict)]
        result = []
        for index in range(1, 5):
            node = normalized[index - 1] if index <= len(normalized) else {}
            result.append({"name": f"Node {index}", **node})
        return result
    return [node for node in nodes if isinstance(node, dict)]


def device_key(value: Any) -> str:
    return text(value)


def device_parent_id(value: Any) -> int | None:
    key = device_key(value)
    if not key:
        return None
    try:
        return int(key.split(":", 1)[0])
    except (TypeError, ValueError):
        return None


def unique_device_keys(value: Any) -> list[str]:
    if not value:
        return []
    if not isinstance(value, list):
        value = [value]
    result = []
    for item in value:
        key = device_key(item)
        if key and key not in result:
            result.append(key)
    return result


def device_label(device: dict[str, Any]) -> str:
    return " / ".join(
        item
        for item in [
            text(device.get("name")),
            text(device.get("brand")),
            text(device.get("model")),
        ]
        if item
    ) or f"Device #{device.get('id')}"


def device_location(device: dict[str, Any]) -> str:
    return " / ".join(
        item
        for item in [
            text(device.get("region")),
            text(device.get("cabinet")),
            f"U{device.get('u_position')}" if device.get("u_position") else "",
        ]
        if item
    )


def int_list(value: Any) -> list[int]:
    if not value:
        return []
    if not isinstance(value, list):
        value = [value]
    result = []
    for item in value:
        try:
            item_id = int(item)
        except (TypeError, ValueError):
            continue
        if item_id > 0 and item_id not in result:
            result.append(item_id)
    return result


async def get_task_devices(task: DeviceMaintenanceTask) -> list[dict[str, Any]]:
    keys = unique_device_keys(task.device_ids) or unique_device_keys(getattr(task, "device_id", None))
    if not keys:
        return []
    parent_ids = [item for item in [device_parent_id(key) for key in keys] if item]
    devices = await AssetDevice.filter(id__in=parent_ids).select_related("region", "location", "cabinet")
    row_map = {}
    for device in devices:
        rows = device_to_maintenance_rows(device, include_plain=True)
        for row in rows:
            row_map[device_key(row["id"])] = row
    return [row_map[key] for key in keys if key in row_map]


def device_to_plain_row(device: AssetDevice) -> dict[str, Any]:
    cabinet = device.cabinet
    location = device.location
    region = device.region
    return {
        "id": str(device.id),
        "device_db_id": device.id,
        "region_id": region.id if region else None,
        "location_id": location.id if location else None,
        "cabinet_id": cabinet.id if cabinet else None,
        "asset_no": device.asset_no,
        "name": device.name,
        "brand": device.brand or "",
        "model": device.model or "",
        "serial_no": device.serial_no or "",
        "mgmt_ip": device.mgmt_ip or "",
        "business_ip": device.business_ip or "",
        "status": normalize_device_status(device.status, 0),
        "region": region.name if region else "",
        "country": region.country if region else "",
        "city": region.city if region else "",
        "location": location.name if location else "",
        "cabinet": cabinet.name if cabinet else "",
        "u_position": device.u_position,
        "u_height": device.u_height,
        "remark": device.remark or "",
        "is_four_node": False,
        "node_name": "",
        "parent_id": None,
        "parent_name": "",
    }


def device_to_maintenance_rows(device: AssetDevice, include_plain: bool = False) -> list[dict[str, Any]]:
    row = device_to_plain_row(device)
    attrs = device.attributes if isinstance(device.attributes, dict) else {}
    nodes = normalize_four_node_list(attrs)
    if is_four_node_device(attrs) and nodes:
        rows = []
        for index, node in enumerate(nodes[:4], start=1):
            node_status = normalize_device_status(node.get("status"), 0)
            if node_status != 2:
                continue
            node_name = text(node.get("name"), f"Node {index}")
            rows.append(
                {
                    **row,
                    "id": f"{device.id}:{node_name}",
                    "parent_id": device.id,
                    "parent_name": device.name,
                    "name": text(node.get("device_name"), f"{device.name}-{node_name}"),
                    "serial_no": text(node.get("serial_no"), row["serial_no"]),
                    "mgmt_ip": text(node.get("mgmt_ip") or node.get("ipmi_host"), row["mgmt_ip"]),
                    "business_ip": text(node.get("business_ip"), row["business_ip"]),
                    "status": node_status,
                    "remark": text(node.get("remark"), row["remark"]),
                    "node_name": node_name,
                    "is_four_node": True,
                }
            )
        return rows
    if include_plain or row["status"] == 2:
        return [row]
    return []


def maintenance_card(task: DeviceMaintenanceTask, devices: list[dict[str, Any]]) -> dict[str, Any]:
    device_lines = "\n".join(
        f"- {device_label(device)} ({device_location(device) or '-'})" for device in devices[:12]
    )
    if len(devices) > 12:
        device_lines += f"\n- 另有 {len(devices) - 12} 台设备"

    detail_url = f"{settings.get_web_base_url()}/ops/device-maintenance"
    return {
        "config": {"wide_screen_mode": True},
        "header": {
            "template": "orange",
            "title": {"tag": "plain_text", "content": "维护计划"},
        },
        "elements": [
            {"tag": "div", "text": {"tag": "lark_md", "content": f"**计划：** {task.title}"}},
            {"tag": "div", "text": {"tag": "lark_md", "content": f"**设备数量：** {len(devices)}"}},
            {"tag": "div", "text": {"tag": "lark_md", "content": f"**维护设备：**\n{device_lines or '-'}"}},
            {"tag": "div", "text": {"tag": "lark_md", "content": f"**计划时间：** {format_datetime(task.due_at) or '-'}"}},
            {"tag": "div", "text": {"tag": "lark_md", "content": f"**说明：** {task.description or '-'}"}},
            {
                "tag": "action",
                "actions": [
                    {
                        "tag": "button",
                        "text": {"tag": "plain_text", "content": "查看维护计划"},
                        "url": detail_url,
                        "type": "primary",
                    }
                ],
            },
        ],
    }


async def send_card_to_user(user: User, card: dict[str, Any]) -> tuple[bool, str]:
    receive_id = ""
    if user.phone:
        receive_id = await lookup_feishu_user_id_by_mobile(user.phone)
    if not receive_id and user.email:
        receive_id = await lookup_feishu_user_id_by_email(user.email)
    if not receive_id:
        return False, f"{user.alias or user.username} 未匹配到飞书用户"

    ok = await send_feishu_app_card(receive_id=receive_id, receive_id_type="user_id", card=card)
    return ok, f"{user.alias or user.username} {'已发送' if ok else '发送失败'}"


async def notify_task(task: DeviceMaintenanceTask) -> tuple[bool, str]:
    assignee_ids = int_list(task.assignee_ids) or int_list(task.assignee_id)
    if not assignee_ids:
        return False, "未选择负责人"

    users = await User.filter(id__in=assignee_ids, is_active=True)
    user_map = {int(user.id): user for user in users}
    ordered_users = [user_map[user_id] for user_id in assignee_ids if user_id in user_map]
    if not ordered_users:
        return False, "负责人不存在或未启用"

    devices = await get_task_devices(task)
    if not devices:
        return False, "设备不存在"

    card = maintenance_card(task, devices)
    results = [await send_card_to_user(user, card) for user in ordered_users]
    success_count = sum(1 for ok, _ in results if ok)
    message = "；".join(message for _, message in results)
    return success_count > 0, f"{success_count}/{len(results)} 飞书通知成功：{message}"


async def notify_due_device_maintenance_tasks(now: datetime | None = None) -> int:
    if not feishu_app_enabled():
        return 0

    now = now or datetime.now()
    deadline = now + timedelta(days=1)
    plans = await DeviceMaintenanceTask.filter(
        due_at__gt=now,
        due_at__lte=deadline,
        reminder_notified_at=None,
    ).exclude(status__in=["done", "cancelled"]).order_by("due_at").limit(50)

    sent_count = 0
    for plan in plans:
        try:
            ok, message = await notify_task(plan)
            plan.notify_status = "sent" if ok else "failed"
            plan.notify_message = message[:500]
            if ok:
                plan.notified_at = now
                sent_count += 1
            plan.reminder_notified_at = now
            await plan.save(
                update_fields=[
                    "notify_status",
                    "notify_message",
                    "notified_at",
                    "reminder_notified_at",
                    "updated_at",
                ]
            )
        except Exception:
            logger.exception("device maintenance reminder failed: task_id=%s", plan.id)
    return sent_count
