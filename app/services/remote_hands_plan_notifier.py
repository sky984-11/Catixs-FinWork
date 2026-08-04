from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from app.log import logger
from app.models.admin import User
from app.models.remote_assistance import RemoteHandsPlan
from app.settings.config import settings
from app.utils.feishu_app import (
    feishu_app_enabled,
    lookup_feishu_user_id_by_email,
    lookup_feishu_user_id_by_mobile,
    send_feishu_app_card,
)


def text(value: Any) -> str:
    return str(value or "").strip()


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


def format_datetime(value: datetime | None) -> str:
    return value.strftime("%Y-%m-%d %H:%M") if value else ""


def build_plan_card(plan: RemoteHandsPlan) -> dict[str, Any]:
    detail_url = f"{settings.get_web_base_url()}/remote-assistance"
    site = " / ".join(item for item in [text(plan.region), text(plan.site), text(plan.rack)] if item)
    engineer = " / ".join(item for item in [text(plan.engineer_name), text(plan.engineer_wechat or plan.engineer_contact)] if item)
    return {
        "config": {"wide_screen_mode": True},
        "header": {
            "template": "blue",
            "title": {"tag": "plain_text", "content": "运维计划"},
        },
        "elements": [
            {"tag": "div", "text": {"tag": "lark_md", "content": f"**客户：** {plan.customer}"}},
            {"tag": "div", "text": {"tag": "lark_md", "content": f"**工单：** {plan.ticket or '-'}"}},
            {"tag": "div", "text": {"tag": "lark_md", "content": f"**位置：** {site or '-'}"}},
            {"tag": "div", "text": {"tag": "lark_md", "content": f"**工程师：** {engineer or '-'}"}},
            {"tag": "div", "text": {"tag": "lark_md", "content": f"**计划时间：** {format_datetime(plan.planned_at) or '-'}"}},
            {"tag": "div", "text": {"tag": "lark_md", "content": f"**说明：** {plan.note or '-'}"}},
            {
                "tag": "action",
                "actions": [
                    {
                        "tag": "button",
                        "text": {"tag": "plain_text", "content": "查看运维计划"},
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


async def notify_remote_hands_plan(plan: RemoteHandsPlan) -> tuple[bool, str]:
    assignee_ids = int_list(plan.assignee_ids) or int_list(plan.assignee_id)
    if not assignee_ids:
        return False, "未选择通知负责人"
    users = await User.filter(id__in=assignee_ids, is_active=True)
    user_map = {int(user.id): user for user in users}
    ordered_users = [user_map[user_id] for user_id in assignee_ids if user_id in user_map]
    if not ordered_users:
        return False, "通知负责人不存在或未启用"

    card = build_plan_card(plan)
    results = [await send_card_to_user(user, card) for user in ordered_users]
    success_count = sum(1 for ok, _ in results if ok)
    message = "；".join(message for _, message in results)
    return success_count > 0, f"{success_count}/{len(results)} 飞书通知成功：{message}"


async def notify_due_remote_hands_plans(now: datetime | None = None) -> int:
    if not feishu_app_enabled():
        return 0

    now = now or datetime.now()
    deadline = now + timedelta(days=1)
    plans = await RemoteHandsPlan.filter(
        planned_at__gt=now,
        planned_at__lte=deadline,
        reminder_notified_at=None,
    ).exclude(status__in=["done", "cancelled"]).order_by("planned_at").limit(50)

    sent_count = 0
    for plan in plans:
        try:
            ok, message = await notify_remote_hands_plan(plan)
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
            logger.exception("remote hands plan reminder failed: plan_id=%s", plan.id)
    return sent_count
