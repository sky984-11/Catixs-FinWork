from calendar import monthrange
from datetime import datetime

from app.models.admin import User
from app.models.product_center import ProductPrice
from app.utils.feishu_app import feishu_app_enabled, lookup_feishu_user_id_by_email, send_feishu_app_card


def next_month(value: datetime) -> datetime:
    year = value.year + (value.month == 12)
    month = 1 if value.month == 12 else value.month + 1
    return value.replace(year=year, month=month, day=min(value.day, monthrange(year, month)[1]))


async def notify_due_price_reminders(now: datetime) -> int:
    if not feishu_app_enabled():
        return 0
    rows = await ProductPrice.filter(notify_enabled=True, notify_next_at__lte=now).limit(50)
    sent = 0
    for price in rows:
        current_next_at = price.notify_next_at
        next_notify_at = None
        next_enabled = False
        if price.notify_schedule == "monthly" and current_next_at:
            next_notify_at = current_next_at
            compare_now = now.replace(tzinfo=next_notify_at.tzinfo) if next_notify_at.tzinfo else now
            while next_notify_at <= compare_now:
                next_notify_at = next_month(next_notify_at)
            next_enabled = True

        # Claim the reminder before sending so another scheduler loop or a hot-reload worker cannot send it again.
        claimed = await ProductPrice.filter(
            id=price.id,
            notify_enabled=True,
            notify_next_at=current_next_at,
        ).update(
            notify_enabled=next_enabled,
            notify_next_at=next_notify_at,
            notify_last_at=now,
        )
        if not claimed:
            continue

        product = await price.product
        card = {
            "config": {"wide_screen_mode": True},
            "header": {"title": {"tag": "plain_text", "content": "客户价格提醒"}, "template": "blue"},
            "elements": [
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": "请关注以下客户价格信息。",
                    },
                },
                {
                    "tag": "div",
                    "fields": [
                        {"is_short": False, "text": {"tag": "lark_md", "content": f"**产品**\n{product.name}"}},
                        {"is_short": False, "text": {"tag": "lark_md", "content": f"**客户**\n{price.customer_name or '-'}"}},
                        {"is_short": True, "text": {"tag": "lark_md", "content": f"**价格**\n{price.currency} {price.amount}"}},
                        {"is_short": True, "text": {"tag": "lark_md", "content": f"**失效日期**\n{price.expiry_date or '-'}"}},
                    ],
                },
                {"tag": "hr"},
                {"tag": "note", "elements": [{"tag": "plain_text", "content": "来自 FinWork 客户价格管理"}]},
            ],
        }
        recipients = [int(item) for item in (price.notify_user_ids or []) if str(item).isdigit()]
        users = await User.filter(id__in=recipients, is_active=True)
        for user in users:
            receive_id = user.feishu_user_id or await lookup_feishu_user_id_by_email(user.email)
            if receive_id and await send_feishu_app_card(receive_id=receive_id, receive_id_type="user_id", card=card):
                sent += 1
    return sent
