import json
from datetime import datetime

from app.log import logger
from app.models.admin import User
from app.models.ticket import Ticket
from app.utils.feishu_app import (
    feishu_app_enabled,
    lookup_feishu_user_id_by_email,
    lookup_feishu_user_id_by_mobile,
    mask_receive_id,
    send_feishu_app_card,
)
from app.utils.feishu_bot import TICKET_STATUS_MAP, TICKET_TYPE_MAP

TICKET_MANAGER_ROLE_NAMES = {"admin", "noc", "管理员"}
TICKET_MANAGER_ACCOUNT_NAMES = {"noc"}


def text(value, default: str = "-") -> str:
    value = str(value or "").strip()
    return value or default


def user_display_name(user: User | None) -> str:
    if not user:
        return "未知用户"
    return user.alias or user.username or user.email or "未知用户"


def truncate(value: str | None, limit: int = 300) -> str:
    content = text(value, "")
    return content[:limit] + "..." if len(content) > limit else content


def markdown_link(label: str | None, url: str | None) -> str:
    safe_label = text(label).replace("[", "【").replace("]", "】")
    link = str(url or "").strip()
    return f"[{safe_label}]({link})" if link else safe_label


def build_ticket_card(
    *,
    title: str,
    template: str,
    ticket: Ticket,
    fields: list[tuple[str, str | None]],
    url: str = "",
    description: str | None = None,
) -> dict:
    elements = [
        {
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": "\n".join(f"**{label}：** {text(value)}" for label, value in fields),
            },
        }
    ]
    if description:
        elements.append(
            {
                "tag": "div",
                "text": {"tag": "lark_md", "content": f"**说明：**\n{truncate(description, 500)}"},
            }
        )
    if url:
        elements.append(
            {
                "tag": "action",
                "actions": [
                    {
                        "tag": "button",
                        "text": {"tag": "plain_text", "content": "查看工单"},
                        "type": "primary",
                        "url": url,
                    }
                ],
            }
        )
    return {
        "header": {
            "title": {"tag": "plain_text", "content": f"{title} - {ticket.ticket_no}"},
            "template": template,
        },
        "elements": elements,
    }


async def resolve_feishu_user_id(user: User | None) -> str:
    if not user:
        return ""
    if user.feishu_user_id:
        return str(user.feishu_user_id or "").strip()
    if user.email:
        user_id = await lookup_feishu_user_id_by_email(user.email)
        if user_id:
            return user_id
    if user.phone:
        user_id = await lookup_feishu_user_id_by_mobile(user.phone)
        if user_id:
            return user_id
    return ""


async def send_card_to_user(user: User, card: dict) -> bool:
    receive_id = await resolve_feishu_user_id(user)
    if not receive_id:
        logger.warning(
            "ticket feishu recipient not resolved: user_id=%s username=%s email=%s phone=%s",
            user.id,
            user.username,
            user.email or "",
            user.phone or "",
        )
        return False
    ok = await send_feishu_app_card(receive_id=receive_id, receive_id_type="user_id", card=card)
    logger.info(
        "ticket feishu app message result: ok=%s user_id=%s receive_id=%s bytes=%s",
        ok,
        user.id,
        mask_receive_id(receive_id),
        len(json.dumps(card, ensure_ascii=False).encode("utf-8")),
    )
    return ok


def unique_users(users: list[User | None], exclude_user: User | None = None) -> list[User]:
    seen = set()
    result = []
    exclude_id = getattr(exclude_user, "id", None)
    for user in users:
        if not user or user.id in seen or user.id == exclude_id:
            continue
        seen.add(user.id)
        result.append(user)
    return result


async def get_ticket_managers(exclude_user: User | None = None) -> list[User]:
    users = await User.all().prefetch_related("roles")
    managers = []
    for user in users:
        names = {
            str(user.username or "").strip().lower(),
            str(user.alias or "").strip().lower(),
            str(user.email or "").split("@", 1)[0].strip().lower(),
        }
        roles = await user.roles.all()
        role_names = {str(role.name or "").strip().lower() for role in roles}
        if user.is_superuser or names & TICKET_MANAGER_ACCOUNT_NAMES or role_names & TICKET_MANAGER_ROLE_NAMES:
            managers.append(user)
    return unique_users(managers, exclude_user=exclude_user)


async def send_card_to_users(users: list[User | None], card: dict, exclude_user: User | None = None) -> int:
    if not feishu_app_enabled():
        logger.warning("ticket feishu app notification skipped: feishu_app_disabled")
        return 0
    sent = 0
    for user in unique_users(users, exclude_user=exclude_user):
        if await send_card_to_user(user, card):
            sent += 1
    return sent


async def notify_ticket_created(ticket: Ticket, creator: User, ticket_url: str = "") -> int:
    assignee = await User.get_or_none(id=ticket.assignee_id) if ticket.assignee_id else None
    recipients = [assignee] if assignee else await get_ticket_managers(exclude_user=creator)
    card = build_ticket_card(
        title="新工单提醒",
        template="blue",
        ticket=ticket,
        fields=[
            ("工单", markdown_link(ticket.title, ticket_url)),
            ("类型", TICKET_TYPE_MAP.get(ticket.type, "未知类型")),
            ("状态", TICKET_STATUS_MAP.get(ticket.status, "未知状态")),
            ("创建人", user_display_name(creator)),
            ("处理人", user_display_name(assignee) if assignee else "未指定"),
            ("位置", ticket.location or "-"),
            ("创建时间", ticket.created_at.strftime("%Y-%m-%d %H:%M") if ticket.created_at else "-"),
        ],
        url=ticket_url,
        description=ticket.desc,
    )
    return await send_card_to_users(recipients, card, exclude_user=creator)


async def notify_ticket_reply(
    *,
    ticket: Ticket,
    replier: User,
    content: str,
    reply_to_user_id: int | None = None,
    reply_to_user_name: str | None = None,
    parent_content: str | None = None,
    ticket_url: str = "",
) -> int:
    creator = await User.get_or_none(id=ticket.user_id) if ticket.user_id else None
    assignee = await User.get_or_none(id=ticket.assignee_id) if ticket.assignee_id else None
    reply_to_user = await User.get_or_none(id=reply_to_user_id) if reply_to_user_id else None
    recipients = [reply_to_user] if reply_to_user else [creator, assignee]
    fields = [
        ("工单", markdown_link(ticket.title, ticket_url)),
        ("类型", TICKET_TYPE_MAP.get(ticket.type, "未知类型")),
        ("回复人", user_display_name(replier)),
        ("回复对象", reply_to_user_name or "工单相关人"),
        ("回复时间", datetime.now().strftime("%Y-%m-%d %H:%M")),
    ]
    if parent_content:
        fields.append(("原内容", truncate(parent_content, 160)))
    card = build_ticket_card(
        title="工单回复",
        template="blue",
        ticket=ticket,
        fields=fields,
        url=ticket_url,
        description=content,
    )
    return await send_card_to_users(recipients, card, exclude_user=replier)


async def notify_ticket_status_changed(
    *,
    ticket: Ticket,
    old_status: int,
    operator: User,
    ticket_url: str = "",
) -> int:
    creator = await User.get_or_none(id=ticket.user_id) if ticket.user_id else None
    assignee = await User.get_or_none(id=ticket.assignee_id) if ticket.assignee_id else None
    template = "green" if ticket.status == 0 else "grey" if ticket.status == 3 else "orange"
    card = build_ticket_card(
        title="工单状态变更",
        template=template,
        ticket=ticket,
        fields=[
            ("工单", markdown_link(ticket.title, ticket_url)),
            ("类型", TICKET_TYPE_MAP.get(ticket.type, "未知类型")),
            ("状态变更", f"{TICKET_STATUS_MAP.get(old_status, '未知状态')} -> {TICKET_STATUS_MAP.get(ticket.status, '未知状态')}"),
            ("操作人", user_display_name(operator)),
            ("处理人", user_display_name(assignee) if assignee else "未指定"),
            ("变更时间", datetime.now().strftime("%Y-%m-%d %H:%M")),
        ],
        url=ticket_url,
        description=ticket.completion_note,
    )
    return await send_card_to_users([creator, assignee], card, exclude_user=operator)
