import hashlib
import hmac
import json
import re
import time
from typing import Any
from urllib.parse import urlencode

from fastapi import Request

from app.log import logger
from app.models.admin import User
from app.models.tg_assistant import TGAssistantConfig, TGAssistantDeliveryLog
from app.services.project_task_notifier import send_card_to_person_detail
from app.settings.config import settings

DEFAULT_EVENTS = ["message_created", "message_updated"]
DEFAULT_MESSAGE_TYPES = ["incoming"]
MESSAGE_TYPE_MAP = {
    0: "incoming",
    1: "outgoing",
    2: "activity",
    3: "template",
    "0": "incoming",
    "1": "outgoing",
    "2": "activity",
    "3": "template",
}
EVENT_TITLE_MAP = {
    "message_created": "Chatwoot 新客户消息",
    "message_updated": "Chatwoot 消息更新",
}


def default_config_payload() -> dict[str, Any]:
    return {
        "is_enabled": False,
        "group_keywords": [],
        "include_user_keywords": [],
        "exclude_user_keywords": [],
        "source_user_keywords": [],
        "content_keywords": [],
        "mention_keywords": [],
        "ignored_keywords": [],
        "event_types": DEFAULT_EVENTS,
        "message_types": DEFAULT_MESSAGE_TYPES,
        "include_private": False,
        "show_message_detail": True,
    }


async def get_or_create_user_config(user_id: int) -> TGAssistantConfig:
    config = await TGAssistantConfig.filter(user_id=user_id).first()
    if config:
        return config
    return await TGAssistantConfig.create(user_id=user_id, **default_config_payload())


async def verify_chatwoot_signature(request: Request, raw_body: bytes) -> None:
    secret = str(settings.CHATWOOT_WEBHOOK_SECRET or "").strip()
    if not secret:
        return

    signature = request.headers.get("X-Chatwoot-Signature", "")
    timestamp = request.headers.get("X-Chatwoot-Timestamp", "")
    if not signature or not timestamp:
        if verify_chatwoot_body_signature(secret, raw_body, signature):
            return
        raise ValueError("missing or invalid Chatwoot signature headers")
    try:
        signed_at = int(timestamp)
    except ValueError as exc:
        raise ValueError("invalid Chatwoot signature timestamp") from exc

    tolerance = int(settings.CHATWOOT_SIGNATURE_TOLERANCE_SECONDS or 300)
    if abs(int(time.time()) - signed_at) > tolerance:
        raise ValueError("expired Chatwoot webhook signature")

    signed_payload = timestamp.encode("utf-8") + b"." + raw_body
    expected = "sha256=" + hmac.new(secret.encode("utf-8"), signed_payload, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature):
        if verify_chatwoot_body_signature(secret, raw_body, signature):
            return
        raise ValueError("invalid Chatwoot webhook signature")


def verify_chatwoot_body_signature(secret: str, raw_body: bytes, signature: str) -> bool:
    signature = str(signature or "").strip()
    if not signature:
        return False
    digest = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    return any(hmac.compare_digest(candidate, signature) for candidate in (digest, f"sha256={digest}"))


def normalize_message_type(value: Any) -> str:
    return MESSAGE_TYPE_MAP.get(value, str(value or "unknown"))


def pick(*values: Any) -> str:
    for value in values:
        if value is not None and value != "":
            return str(value)
    return ""


def as_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if not value:
        return []
    return [item.strip() for item in re.split(r"[\n,，;；]+", str(value)) if item.strip()]


def contains_any(text: str, keywords: list[str]) -> str:
    lower_text = text.lower()
    for keyword in keywords:
        if keyword.lower() in lower_text:
            return keyword
    return ""


def first_list(*values: Any) -> list[str]:
    for value in values:
        items = as_list(value)
        if items:
            return items
    return []


def extract_message_context(payload: dict[str, Any]) -> dict[str, str]:
    contact = payload.get("contact") or {}
    sender = payload.get("sender") or {}
    conversation = payload.get("conversation") or {}
    inbox = payload.get("inbox") or {}
    account = payload.get("account") or {}

    content = normalize_content(payload)
    content_name = extract_user_name_from_content(content)
    conversation_id = pick(conversation.get("display_id"), conversation.get("id"), payload.get("conversation_id"), "N/A")
    account_id = pick(account.get("id"), conversation.get("account_id"))
    return {
        "content": content,
        "contact_name": pick(content_name, contact.get("name"), sender.get("name"), "Unknown"),
        "sender_name": pick(sender.get("name"), content_name, contact.get("name"), "Unknown"),
        "inbox_name": pick(inbox.get("name"), "Unknown"),
        "account_name": pick(account.get("name"), "Unknown"),
        "content_type": pick(payload.get("content_type"), "text"),
        "created_at": pick(payload.get("created_at"), payload.get("updated_at"), "-"),
        "conversation_id": conversation_id,
        "conversation_url": build_conversation_url(account_id, conversation_id),
    }


def extract_user_name_from_content(content: Any) -> str:
    text = str(content or "").strip()
    for separator in ("：", ":"):
        if separator in text:
            name = text.split(separator, 1)[0].strip()
            if name:
                return name
    return ""


def normalize_content(payload: dict[str, Any]) -> str:
    content = str(payload.get("content") or "").strip()
    if content:
        return truncate(content, 3000)
    attachments = payload.get("attachments") or []
    if attachments:
        return f"[{len(attachments)} 个附件]"
    content_attributes = payload.get("content_attributes") or {}
    if content_attributes:
        return truncate(json.dumps(content_attributes, ensure_ascii=False), 3000)
    return "(无文本内容)"


def build_conversation_url(account_id: Any, conversation_id: Any) -> str:
    if not account_id or not conversation_id or conversation_id == "N/A":
        return ""
    base_url = str(settings.CHATWOOT_BASE_URL or "https://chatwoot.catixs.net").strip().rstrip("/")
    return f"{base_url}/app/accounts/{account_id}/conversations/{conversation_id}"


def truncate(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return value[: limit - 20].rstrip() + "\n...(内容已截断)"


def escape_md(value: Any) -> str:
    text = str(value or "")
    return text.replace("\\", "\\\\").replace("*", "\\*").replace("`", "\\`")


def match_config(config: TGAssistantConfig, payload: dict[str, Any], context: dict[str, str], event: str, message_type: str) -> tuple[bool, str]:
    if not config.is_enabled:
        return False, "disabled"
    event_types = as_list(config.event_types) or DEFAULT_EVENTS
    if event not in event_types:
        return False, f"event_filtered:{event}"
    message_types = as_list(config.message_types) or DEFAULT_MESSAGE_TYPES
    if message_type not in message_types:
        return False, f"message_type_filtered:{message_type}"
    if payload.get("private") and not config.include_private:
        return False, "private_message"

    haystack = "\n".join(
        [
            context.get("content", ""),
            context.get("sender_name", ""),
            context.get("contact_name", ""),
            context.get("inbox_name", ""),
            context.get("account_name", ""),
        ]
    )
    ignored = contains_any(haystack, as_list(config.ignored_keywords))
    if ignored:
        return False, f"ignored_keyword:{ignored}"

    matched = []
    group_keywords = as_list(getattr(config, "group_keywords", []))
    if group_keywords:
        group_text = "\n".join([context.get("inbox_name", ""), context.get("account_name", "")])
        keyword = contains_any(group_text, group_keywords)
        if not keyword:
            return False, "group_not_matched"
        matched.append(f"group={keyword}")

    source_text = "\n".join([context.get("sender_name", ""), context.get("contact_name", ""), context.get("content", "")])
    exclude_user_keywords = as_list(getattr(config, "exclude_user_keywords", []))
    ignored_user = contains_any(source_text, exclude_user_keywords)
    if ignored_user:
        return False, f"ignored_user:{ignored_user}"

    source_keywords = first_list(getattr(config, "include_user_keywords", []), config.source_user_keywords)
    if source_keywords:
        keyword = contains_any(source_text, source_keywords)
        if not keyword:
            return False, "source_user_not_matched"
        matched.append(f"user={keyword}")

    mention_keywords = as_list(config.mention_keywords)
    if mention_keywords:
        mention_text = context.get("content", "")
        keyword = contains_any(mention_text, mention_keywords) or contains_any(mention_text, [f"@{item}" for item in mention_keywords])
        if not keyword:
            return False, "mention_not_matched"
        matched.append(f"mention={keyword}")

    return True, ",".join(matched) or "default"


def user_receiver_name(user: User) -> str:
    return str(user.alias or user.username or user.email or user.phone or "").strip()


def build_tg_assistant_card(
    *,
    event: str,
    message_type: str,
    context: dict[str, str],
    show_message_detail: bool,
) -> dict[str, Any]:
    sender_name = context.get("sender_name") or context.get("contact_name") or "Chatwoot 用户"
    elements: list[dict[str, Any]] = []
    if show_message_detail:
        elements.append(
            {
                "tag": "div",
                "text": {"tag": "lark_md", "content": f"**消息内容**\n{escape_md(context.get('content'))}"},
            }
        )
        elements.append({"tag": "hr"})
    elements.append(
        {
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": (
                    f"**发送人：** {escape_md(sender_name)}\n"
                    f"**客户：** {escape_md(context.get('contact_name'))}\n"
                    f"**时间：** {escape_md(context.get('created_at'))}\n"
                    f"**收件箱：** {escape_md(context.get('inbox_name'))}\n"
                    f"**会话 ID：** {escape_md(context.get('conversation_id'))}\n"
                    f"**消息类型：** {escape_md(message_type)} / {escape_md(context.get('content_type'))}"
                ),
            },
        }
    )
    if context.get("conversation_url"):
        elements.extend(
            [
                {"tag": "hr"},
                {
                    "tag": "action",
                    "actions": [
                        {
                            "tag": "button",
                            "text": {"tag": "plain_text", "content": "打开会话"},
                            "type": "primary",
                            "url": context["conversation_url"],
                        }
                    ],
                },
            ]
        )
    return {
        "header": {
            "template": "blue" if event == "message_created" else "orange",
            "title": {"tag": "plain_text", "content": f"{sender_name} 发来消息"},
        },
        "elements": elements,
    }


async def process_chatwoot_payload(payload: dict[str, Any]) -> dict[str, Any]:
    event = str(payload.get("event") or "")
    message_type = normalize_message_type(payload.get("message_type"))
    context = extract_message_context(payload)
    configs = await TGAssistantConfig.filter(is_enabled=True).select_related("user")
    logger.info(
        "tg assistant webhook received: event=%s message_type=%s configs=%s conversation=%s sender=%s",
        event,
        message_type,
        len(configs),
        context.get("conversation_id"),
        context.get("sender_name"),
    )
    sent = 0
    failed = 0
    skipped = 0
    details = []

    for config in configs:
        user = config.user
        matched, reason = match_config(config, payload, context, event, message_type)
        if not matched:
            skipped += 1
            await create_delivery_log(config, context, event, message_type, "skipped", reason)
            continue

        receiver_name = user_receiver_name(user)
        if not receiver_name:
            failed += 1
            reason = "receiver_not_resolved"
            await create_delivery_log(config, context, event, message_type, "failed", reason)
            details.append(f"{user.username}:{reason}")
            continue

        card = build_tg_assistant_card(
            event=event,
            message_type=message_type,
            context=context,
            show_message_detail=bool(config.show_message_detail),
        )
        ok, detail = await send_card_to_person_detail(receiver_name, card)
        if ok:
            sent += 1
            await create_delivery_log(config, context, event, message_type, "sent", detail, reason)
        else:
            failed += 1
            await create_delivery_log(config, context, event, message_type, "failed", detail, reason)
            details.append(f"{user.username}:{detail}")

    logger.info(
        "tg assistant webhook processed: event=%s message_type=%s sent=%s failed=%s skipped=%s conversation=%s",
        event,
        message_type,
        sent,
        failed,
        skipped,
        context.get("conversation_id"),
    )
    return {
        "status": "processed",
        "event": event,
        "message_type": message_type,
        "sent": sent,
        "failed": failed,
        "skipped": skipped,
        "details": details,
    }


async def create_delivery_log(
    config: TGAssistantConfig,
    context: dict[str, str],
    event: str,
    message_type: str,
    status: str,
    reason: str,
    matched_rule: str = "",
) -> None:
    await TGAssistantDeliveryLog.create(
        user_id=config.user_id,
        event=event,
        message_type=message_type,
        conversation_id=context.get("conversation_id", "")[:100],
        sender_name=context.get("sender_name", "")[:200],
        contact_name=context.get("contact_name", "")[:200],
        status=status,
        reason=reason[:500],
        matched_rule=(matched_rule or reason)[:500],
        content_excerpt=truncate(context.get("content", ""), 1000),
    )


def webhook_url() -> str:
    base_url = settings.get_web_base_url()
    if not base_url:
        return "/api/v1/tg-assistant/chatwoot"
    return f"{base_url}/api/v1/tg-assistant/chatwoot?{urlencode({'source': 'chatwoot'})}"
