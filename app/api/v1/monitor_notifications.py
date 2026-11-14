from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.core.dependency import AuthControl
from app.models import (MonitorNotificationConfig, MonitorNotificationDelivery,
                        User)
from app.schemas.base import Success
from app.services.monitor_event_config import load_settings
from app.services.monitor_events import ZabbixClient, advice, detail
from app.services.monitor_notifications import (NotificationSettings,
                                                build_card, generate_advice,
                                                notification_settings,
                                                save_notification_settings)

router = APIRouter()


@router.get("", summary="事件飞书通知配置与可选接收人")
async def get_notifications():
    return Success(data=await notification_settings())


@router.put("", summary="保存事件飞书通知配置")
async def put_notifications(payload: NotificationSettings, user=Depends(AuthControl.is_authed)):
    return Success(data=await save_notification_settings(payload, user.id))


class Preview(BaseModel):
    event_id: str | None = Field(default=None, pattern=r"^[1-9][0-9]{0,19}$")


@router.post("/preview", summary="预览飞书告警卡片与 AI 建议（不发送）")
async def preview_notification(payload: Preview):
    config = await MonitorNotificationConfig.get_or_none(id=1)
    scope = await load_settings()
    if payload.event_id:
        async with ZabbixClient() as client:
            row = await detail(client, payload.event_id, scope)
    else:
        row = {
            "id": "示例",
            "name": "ICMP 丢包率升高（示例）",
            "severity": 4,
            "clock": 1794614400,
            "recovery_clock": 0,
            "duration_seconds": 300,
            "recovered": False,
            "acknowledged": False,
            "hosts": [{"name": "示例线路主机", "addresses": ["192.0.2.1"]}],
            "categories": [],
            "items": [],
            "advice": advice("High ICMP ping loss"),
            "url": "",
        }
    text, source = await generate_advice(row, config.ai_enabled if config else True)
    return Success(
        data={
            "card": build_card(row, "recovery" if row["recovered"] else "problem", text, source, scope["categories"]),
            "advice": text,
            "advice_source": source,
            "sample": not payload.event_id,
        }
    )


@router.get("/deliveries", summary="事件通知发送记录")
async def deliveries(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status: Literal["pending", "sending", "sent", "failed", "skipped"] | None = None,
):
    query = MonitorNotificationDelivery.all()
    if status:
        query = query.filter(status=status)
    total = await query.count()
    rows = await query.order_by("-id").offset((page - 1) * page_size).limit(page_size)
    users = {u.id: u.alias or u.username for u in await User.filter(id__in=[row.user_id for row in rows])}
    return Success(
        data={
            "total": total,
            "rows": [
                {
                    "id": r.id,
                    "event_id": r.event_id,
                    "event_name": r.event_name,
                    "phase": r.phase,
                    "user_id": r.user_id,
                    "user_name": users.get(r.user_id, "已删除用户"),
                    "status": r.status,
                    "attempts": r.attempts,
                    "message": r.message,
                    "advice": r.advice,
                    "advice_source": r.advice_source,
                    "sent_at": r.sent_at,
                    "created_at": int(r.created_at.timestamp()),
                }
                for r in rows
            ],
        }
    )


@router.post("/deliveries/{delivery_id}/retry", summary="手动重试失败的事件通知")
async def retry_notification(delivery_id: int):
    row = await MonitorNotificationDelivery.get_or_none(id=delivery_id)
    if not row:
        raise HTTPException(404, "通知记录不存在")
    config = await MonitorNotificationConfig.get_or_none(id=1)
    if not config or not config.enabled or row.user_id not in config.recipient_ids:
        raise HTTPException(409, "请先启用通知并确认接收人仍在配置中")
    if row.status != "failed" or row.attempts >= 5:
        raise HTTPException(409, "仅可重试失败通知，最多尝试 5 次")
    if not await User.filter(id=row.user_id, is_active=True).exists():
        raise HTTPException(409, "接收人已停用或不存在")
    async with ZabbixClient() as client:
        await detail(client, row.event_id)
    changed = await MonitorNotificationDelivery.filter(id=row.id, status="failed").update(
        status="pending", message="已排队，等待下一轮发送"
    )
    if not changed:
        raise HTTPException(409, "记录状态已变化，请刷新")
    return Success(msg="已加入发送队列")
