import json
import time
from typing import Any

import httpx

from app.log import logger
from app.settings.config import settings

FEISHU_API_BASE = "https://open.feishu.cn/open-apis"

_tenant_access_token = ""
_tenant_access_token_expire_at = 0.0
_email_user_id_cache: dict[str, str] = {}
_mobile_user_id_cache: dict[str, str] = {}


def feishu_app_enabled() -> bool:
    return bool(str(settings.FEISHU_APP_ID or "").strip() and str(settings.FEISHU_APP_SECRET or "").strip())


async def get_tenant_access_token() -> str:
    global _tenant_access_token, _tenant_access_token_expire_at
    now = time.time()
    if _tenant_access_token and now < _tenant_access_token_expire_at - 60:
        return _tenant_access_token

    app_id = str(settings.FEISHU_APP_ID or "").strip()
    app_secret = str(settings.FEISHU_APP_SECRET or "").strip()
    if not app_id or not app_secret:
        return ""

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(
            f"{FEISHU_API_BASE}/auth/v3/tenant_access_token/internal",
            json={"app_id": app_id, "app_secret": app_secret},
        )
    try:
        data = response.json()
    except ValueError:
        logger.error("feishu tenant token response is not json: %s", response.text)
        return ""

    token = data.get("tenant_access_token") or ""
    if response.status_code != 200 or data.get("code") != 0 or not token:
        logger.error("feishu tenant token failed: status=%s data=%s", response.status_code, data)
        return ""

    _tenant_access_token = token
    _tenant_access_token_expire_at = now + int(data.get("expire") or 7200)
    return _tenant_access_token


async def send_feishu_app_card(
    *,
    receive_id: str,
    card: dict[str, Any],
    receive_id_type: str = "email",
) -> bool:
    receive_id = str(receive_id or "").strip()
    if not receive_id:
        return False
    token = await get_tenant_access_token()
    if not token:
        return False

    payload = {
        "receive_id": receive_id,
        "msg_type": "interactive",
        "content": json.dumps(card, ensure_ascii=False),
    }
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(
            f"{FEISHU_API_BASE}/im/v1/messages",
            params={"receive_id_type": receive_id_type},
            headers={"Authorization": f"Bearer {token}"},
            json=payload,
        )
    try:
        data = response.json()
    except ValueError:
        logger.error("feishu app message response is not json: %s", response.text)
        return False

    if response.status_code == 200 and data.get("code") == 0:
        logger.info("feishu app message sent: receive_id_type=%s receive_id=%s", receive_id_type, receive_id)
        return True

    logger.error(
        f"feishu app message failed: receive_id_type={receive_id_type} "
        f"receive_id={receive_id} status={response.status_code} data={data}"
    )
    return False


async def lookup_feishu_user_id_by_email(email: str) -> str:
    email = str(email or "").strip()
    if not email:
        return ""

    cache_key = email.lower()
    if cache_key in _email_user_id_cache:
        return _email_user_id_cache[cache_key]

    user_id = await lookup_feishu_user_id_by_email_from_contact(email)
    if not user_id:
        user_id = await lookup_feishu_user_id_by_email_from_directory(email)
    if user_id:
        _email_user_id_cache[cache_key] = user_id
    return user_id


async def lookup_feishu_user_id_by_mobile(mobile: str) -> str:
    mobile = normalize_mobile(mobile)
    if not mobile:
        return ""

    if mobile in _mobile_user_id_cache:
        return _mobile_user_id_cache[mobile]

    token = await get_tenant_access_token()
    if not token:
        return ""

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(
            f"{FEISHU_API_BASE}/contact/v3/users/batch_get_id",
            params={"user_id_type": "user_id"},
            headers={"Authorization": f"Bearer {token}"},
            json={"mobiles": [mobile], "include_resigned": True},
        )
    try:
        data = response.json()
    except ValueError:
        logger.error(f"feishu contact mobile lookup response is not json: {response.text}")
        return ""

    if response.status_code != 200 or data.get("code") != 0:
        logger.warning(f"feishu contact mobile lookup failed: status={response.status_code} data={data}")
        return ""

    for user in ((data.get("data") or {}).get("user_list") or []):
        user_mobile = normalize_mobile(user.get("mobile"))
        if user_mobile == mobile and user.get("user_id"):
            user_id = str(user.get("user_id") or "").strip()
            _mobile_user_id_cache[mobile] = user_id
            return user_id
    return ""


def normalize_mobile(value: str | None) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if text.startswith("+"):
        text = text[1:]
    return "".join(ch for ch in text if ch.isdigit())


async def lookup_feishu_user_id_by_email_from_contact(email: str) -> str:
    token = await get_tenant_access_token()
    if not token:
        return ""

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(
            f"{FEISHU_API_BASE}/contact/v3/users/batch_get_id",
            params={"user_id_type": "user_id"},
            headers={"Authorization": f"Bearer {token}"},
            json={"emails": [email], "include_resigned": True},
        )
    try:
        data = response.json()
    except ValueError:
        logger.error(f"feishu contact email lookup response is not json: {response.text}")
        return ""

    if response.status_code != 200 or data.get("code") != 0:
        logger.warning(f"feishu contact email lookup failed: status={response.status_code} data={data}")
        return ""

    target_email = email.lower()
    for user in ((data.get("data") or {}).get("user_list") or []):
        user_email = str(user.get("email") or "").strip().lower()
        if user_email == target_email and user.get("user_id"):
            return str(user.get("user_id") or "").strip()
    return ""


async def lookup_feishu_user_id_by_email_from_directory(email: str) -> str:
    token = await get_tenant_access_token()
    if not token:
        return ""

    required_fields = ["base_info.email", "base_info.employee_id"]
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(
            f"{FEISHU_API_BASE}/directory/v1/employees/filter",
            params={"employee_id_type": "user_id", "department_id_type": "open_department_id"},
            headers={"Authorization": f"Bearer {token}"},
            json={
                "filter": {
                    "conditions": [
                        {
                            "field": "base_info.email",
                            "operator": "eq",
                            "value": json.dumps(email, ensure_ascii=False),
                        }
                    ]
                },
                "required_fields": required_fields,
                "page_request": {"page_size": 10},
            },
        )
    try:
        data = response.json()
    except ValueError:
        logger.error(f"feishu directory email lookup response is not json: {response.text}")
        return ""

    if response.status_code != 200 or data.get("code") != 0:
        logger.warning(f"feishu directory email lookup failed: status={response.status_code} data={data}")
        return ""

    target_email = email.lower()
    for employee in ((data.get("data") or {}).get("employees") or []):
        base_info = employee.get("base_info") or {}
        user_email = str(base_info.get("email") or "").strip().lower()
        if user_email == target_email and base_info.get("employee_id"):
            return str(base_info.get("employee_id") or "").strip()
    return ""


def markdown_link(text: str | None, url: str | None) -> str:
    label = str(text or "-").replace("[", "【").replace("]", "】")
    link = str(url or "").strip()
    return f"[{label}]({link})" if link else label


def build_project_daily_summary_card(*, summary_date: str, sections: list[dict], recipient: str = "") -> dict:
    elements: list[dict[str, Any]] = []
    if recipient:
        elements.append(
            {
                "tag": "div",
                "text": {"tag": "lark_md", "content": f"**负责人：** {recipient}"},
            }
        )

    total_projects = sum(int(section.get("count") or 0) for section in sections)
    total_tasks = sum(int(section.get("open_task_count") or 0) for section in sections)
    elements.append(
        {
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": f"**项目数：** {total_projects}    **未完成子任务：** {total_tasks}",
            },
        }
    )

    for section in sections:
        elements.append({"tag": "hr"})
        elements.append(
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": (
                        f"**{section.get('label')}** "
                        f"({section.get('count', 0)} 个项目 / {section.get('open_task_count', 0)} 个未完成子任务)"
                    ),
                },
            }
        )
        projects = section.get("projects") or []
        if not projects:
            elements.append({"tag": "note", "elements": [{"tag": "plain_text", "content": "暂无项目"}]})
            continue

        content_lines = []
        for project in projects[:8]:
            project_name = markdown_link(project.get("name"), project.get("url"))
            project_index = project.get("index") or len(content_lines) + 1
            owners = project.get("owners") or "未设置负责人"
            due_date = project.get("due_date") or "无截止日期"
            progress = project.get("progress", 0)
            task_parts = []
            for task in (project.get("tasks") or [])[:3]:
                task_title = markdown_link(task.get("title"), task.get("url"))
                task_index = task.get("index") or len(task_parts) + 1
                task_due = task.get("due_date") or "未设置"
                task_parts.append(f"{project_index}.{task_index} {task_title}（ETA {task_due}）")
            task_text = "；".join(task_parts) if task_parts else "暂无未完成子任务"
            if len(project.get("tasks") or []) > 3:
                task_text += f"；另有 {len(project.get('tasks') or []) - 3} 项"
            content_lines.append(
                f"- {project_index}. {project_name} | {progress}% | {owners} | ETA {due_date}\n"
                f"  子任务：{task_text}"
            )
        if len(projects) > 8:
            content_lines.append(f"- 还有 {len(projects) - 8} 个项目未展示")
        elements.append({"tag": "div", "text": {"tag": "lark_md", "content": "\n".join(content_lines)}})

    return {
        "header": {
            "title": {"tag": "plain_text", "content": f"项目看板每日总结 - {summary_date}"},
            "template": "blue",
        },
        "elements": elements,
    }


def build_project_task_due_card(
    *,
    stage: str,
    project_name: str,
    task_title: str,
    due_date: str,
    assignee: str | None = None,
    customer_name: str | None = None,
    project_code: str | None = None,
    remark: str | None = None,
    url: str | None = None,
) -> dict:
    stage_label = "即将到期" if stage == "due_soon" else "已到期"
    template = "orange" if stage == "due_soon" else "red"
    fields = [
        ("项目", markdown_link(project_name, url)),
        ("子任务", markdown_link(task_title, url)),
        ("ETA", due_date),
        ("负责人", assignee or "未设置"),
    ]
    if customer_name:
        fields.append(("客户", customer_name))
    if project_code:
        fields.append(("项目编号", project_code))
    if remark:
        fields.append(("备注", remark))
    return build_field_card(
        title=f"项目子任务{stage_label}提醒",
        template=template,
        fields=fields,
    )


def build_assignment_card(
    *,
    title: str,
    fields: list[tuple[str, str]],
    url: str | None = None,
) -> dict:
    card_fields = fields[:]
    if url:
        card_fields.append(("查看详情", markdown_link("打开项目看板", url)))
    return build_field_card(title=title, template="blue", fields=card_fields)


def build_field_card(*, title: str, template: str, fields: list[tuple[str, str]]) -> dict:
    return {
        "header": {
            "title": {"tag": "plain_text", "content": title},
            "template": template,
        },
        "elements": [
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": "\n".join(f"**{label}：** {value}" for label, value in fields),
                },
            }
        ],
    }
