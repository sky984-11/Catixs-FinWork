import json
import re
from datetime import date, datetime, timedelta
from urllib.parse import urlencode

from app.log import logger
from app.models.admin import User
from app.models.project import CustomerProject, CustomerProjectDailySummary, CustomerProjectTask
from app.settings.config import settings
from app.utils.feishu_app import (
    build_assignment_card,
    build_project_daily_summary_card,
    build_project_due_card,
    build_project_task_due_card,
    feishu_app_enabled,
    lookup_feishu_user_id_by_email,
    lookup_feishu_user_id_by_mobile,
    send_feishu_app_card,
)
from tortoise.expressions import Q

DAILY_SUMMARY_STATUSES = ("planning", "active", "acceptance")
DAILY_SUMMARY_LABELS = {
    "planning": "规划中",
    "active": "进行中",
    "acceptance": "验收中",
}


async def notify_due_project_tasks(now: datetime | None = None) -> int:
    if not feishu_app_enabled():
        return 0

    now = now or datetime.now()
    soon_deadline = now + timedelta(days=1)
    today = now.date()
    soon_date = soon_deadline.date()
    sent_count = 0

    due_soon_projects = await CustomerProject.filter(
        due_date__gt=today,
        due_date__lte=soon_date,
        due_soon_notified_at=None,
    ).exclude(status__in=["completed", "archived"]).select_related("customer")
    for project in due_soon_projects:
        if await notify_project_due(project, "due_soon", now):
            sent_count += 1

    due_projects = await CustomerProject.filter(
        due_date__lte=today,
        due_notified_at=None,
    ).exclude(status__in=["completed", "archived"]).select_related("customer")
    for project in due_projects:
        if await notify_project_due(project, "due", now):
            sent_count += 1

    due_soon_tasks = await CustomerProjectTask.filter(
        is_done=False,
        due_date__gt=now,
        due_date__lte=soon_deadline,
        due_soon_notified_at=None,
    ).select_related("project", "project__customer")
    for task in due_soon_tasks:
        if await notify_project_task(task, "due_soon", now):
            sent_count += 1

    due_tasks = await CustomerProjectTask.filter(
        is_done=False,
        due_date__lte=now,
        due_notified_at=None,
    ).select_related("project", "project__customer")
    for task in due_tasks:
        if await notify_project_task(task, "due", now):
            sent_count += 1

    return sent_count


async def notify_project_due(
    project: CustomerProject,
    stage: str,
    now: datetime,
) -> bool:
    if getattr(project, "status", "") in {"completed", "archived"}:
        return False
    if not getattr(project, "due_date", None):
        return False
    if not project.owner:
        return False
    if not await claim_project_due_notification(project, stage, now):
        return False

    customer = await project.customer if getattr(project, "customer_id", None) else None
    url = build_project_url(project.id)
    try:
        card = build_project_due_card(
            stage=stage,
            project_name=project.name,
            due_date=format_due_date(project.due_date),
            owner=project.owner,
            customer_name=getattr(customer, "name", "") or getattr(customer, "legal_name", ""),
            project_code=project.code,
            progress=project.progress,
            url=url,
        )
        return await send_card_to_person(project.owner, card)
    except Exception:
        logger.exception("project due feishu notification failed: project_id=%s stage=%s", project.id, stage)
        return False


async def notify_project_daily_summary(now: datetime | None = None) -> bool:
    if not feishu_app_enabled():
        return False

    now = now or datetime.now()
    if not should_run_daily_summary(now):
        return False

    summary_date = now.date()
    record, created = await CustomerProjectDailySummary.get_or_create(
        summary_date=summary_date,
        defaults={"status": "sending", "message": "sending"},
    )
    if not created:
        return False

    sections, owners = await build_daily_summary_sections()
    try:
        success = await send_daily_summary_to_people(summary_date.isoformat(), owners)
    except Exception:
        logger.exception("project daily summary feishu notification failed")
        success = False

    record.status = "success" if success else "failed"
    record.sent_at = now if success else None
    record.message = "sent" if success else "feishu app failed"
    await record.save()
    return success


def should_run_daily_summary(now: datetime) -> bool:
    run_time = now.replace(
        hour=int(settings.PROJECT_DAILY_SUMMARY_HOUR or 8),
        minute=int(settings.PROJECT_DAILY_SUMMARY_MINUTE or 30),
        second=0,
        microsecond=0,
    )
    return now >= run_time


async def build_daily_summary_sections(owner_filter: str | None = None) -> tuple[list[dict], list[str]]:
    filter_text = (
        str(settings.PROJECT_DAILY_SUMMARY_OWNER_FILTER or "").strip()
        if owner_filter is None
        else str(owner_filter or "").strip()
    )
    projects = await CustomerProject.filter(status__in=DAILY_SUMMARY_STATUSES).order_by(
        "status",
        "sort_order",
        "due_date",
        "-updated_at",
    )
    project_ids = [project.id for project in projects]
    tasks_by_project: dict[int, list[CustomerProjectTask]] = {project_id: [] for project_id in project_ids}
    if project_ids:
        tasks = await CustomerProjectTask.filter(project_id__in=project_ids, is_done=False).order_by(
            "due_date",
            "sort_order",
        )
        for task in tasks:
            tasks_by_project.setdefault(task.project_id, []).append(task)

    owners: list[str] = []
    sections: list[dict] = []
    for status in DAILY_SUMMARY_STATUSES:
        status_projects = [project for project in projects if project.status == status]
        section_projects = []
        open_task_count = 0
        project_index = 0
        for project in status_projects:
            open_tasks = tasks_by_project.get(project.id, [])
            if filter_text and not is_project_related_to_people(project, open_tasks, [filter_text]):
                continue
            project_index += 1
            open_task_count += len(open_tasks)
            project_owners = collect_people([project.owner] + [task.assignee for task in open_tasks])
            owners.extend(project_owners)
            section_projects.append(
                {
                    "index": project_index,
                    "name": project.name,
                    "url": build_project_url(project.id),
                    "owners": "、".join(project_owners) if project_owners else "",
                    "due_date": project.due_date.isoformat() if project.due_date else "",
                    "progress": project.progress,
                    "tasks": [
                        {
                            "index": task_index,
                            "id": task.id,
                            "title": task.title,
                            "due_date": format_due_date(task.due_date),
                            "url": build_project_url(project.id, task.id),
                        }
                        for task_index, task in enumerate(open_tasks, start=1)
                    ],
                }
            )
        sections.append(
            {
                "key": status,
                "label": DAILY_SUMMARY_LABELS[status],
                "count": len(section_projects),
                "open_task_count": open_task_count,
                "projects": section_projects,
            }
        )
    return sections, unique_people(owners)


async def notify_project_task(
    task: CustomerProjectTask,
    stage: str,
    now: datetime,
) -> bool:
    project = task.project
    if getattr(project, "status", "") in {"completed", "archived"}:
        return False
    if not task.assignee:
        return False

    if not await claim_project_task_notification(task, stage, now):
        return False

    customer = await project.customer if getattr(project, "customer_id", None) else None
    url = build_project_url(project.id, task.id)
    try:
        card = build_project_task_due_card(
            stage=stage,
            project_name=project.name,
            task_title=task.title,
            due_date=format_due_date(task.due_date),
            assignee=task.assignee,
            customer_name=getattr(customer, "name", "") or getattr(customer, "legal_name", ""),
            project_code=project.code,
            remark=task.remark,
            url=url,
        )
        return await send_card_to_person(task.assignee, card)
    except Exception:
        logger.exception("project task feishu notification failed: task_id=%s stage=%s", task.id, stage)
        return False


async def send_daily_summary_to_people(summary_date: str, owners: list[str]) -> bool:
    recipients = unique_people(owners)
    if not recipients:
        return False
    sent = 0
    for owner in recipients:
        sections, _ = await build_daily_summary_sections(owner_filter=owner)
        if not any(section.get("projects") for section in sections):
            continue
        card = build_project_daily_summary_card(summary_date=summary_date, sections=sections, recipient=owner)
        if await send_card_to_person(owner, card):
            sent += 1
    return sent > 0


async def notify_project_created(project: CustomerProject, creator: User | None = None) -> bool:
    owner = str(project.owner or "").strip()
    if not owner or is_same_person(owner, creator):
        return False
    customer = await project.customer if getattr(project, "customer_id", None) else None
    card = build_assignment_card(
        title="你有一个新的负责项目",
        fields=[
            ("项目", project.name),
            ("客户", getattr(customer, "name", "") or getattr(customer, "legal_name", "") or "-"),
            ("项目编号", project.code or "-"),
            ("状态", project.status or "-"),
            ("ETA", project.due_date.isoformat() if project.due_date else "未设置"),
            ("创建人", get_user_display_name(creator)),
        ],
        url=build_project_url(project.id),
    )
    return await send_card_to_person(owner, card)


async def notify_project_task_created(
    task: CustomerProjectTask,
    project: CustomerProject,
    creator: User | None = None,
) -> bool:
    assignee = str(task.assignee or "").strip()
    if not assignee or is_same_person(assignee, creator):
        return False
    card = build_assignment_card(
        title="你有一个新的项目子任务",
        fields=[
            ("项目", project.name),
            ("子任务", task.title),
            ("负责人", assignee),
            ("ETA", format_due_date(task.due_date)),
            ("创建人", get_user_display_name(creator)),
            ("备注", task.remark or "-"),
        ],
        url=build_project_url(project.id, task.id),
    )
    return await send_card_to_person(assignee, card)


async def notify_project_shared(
    project: CustomerProject,
    shared_users: list[str],
    sharer: User | None = None,
) -> int:
    recipients = [user for user in unique_people(shared_users) if not is_same_person(user, sharer)]
    if not recipients:
        return 0
    customer = await project.customer if getattr(project, "customer_id", None) else None
    sharer_name = get_user_display_name(sharer)
    card = build_assignment_card(
        title="你收到一个共享项目",
        fields=[
            ("分享人", sharer_name),
            ("项目", project.name),
            ("客户", getattr(customer, "name", "") or getattr(customer, "legal_name", "") or "-"),
            ("项目编号", project.code or "-"),
            ("负责人", project.owner or "-"),
            ("ETA", project.due_date.isoformat() if project.due_date else "未设置"),
        ],
        url=build_project_url(project.id),
    )
    sent = 0
    for user in recipients:
        if await send_card_to_person(user, card):
            sent += 1
    return sent


def format_due_date(value: date | datetime | None) -> str:
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M")
    return value.isoformat() if value else "未设置"


async def claim_project_task_notification(task: CustomerProjectTask, stage: str, now: datetime) -> bool:
    filters = {"id": task.id}
    values = {}
    if stage == "due_soon":
        filters["due_soon_notified_at"] = None
        values["due_soon_notified_at"] = now
    else:
        filters["due_notified_at"] = None
        values["due_notified_at"] = now

    updated = await CustomerProjectTask.filter(**filters).update(**values)
    return updated > 0


async def claim_project_due_notification(project: CustomerProject, stage: str, now: datetime) -> bool:
    filters = {"id": project.id}
    values = {}
    if stage == "due_soon":
        filters["due_soon_notified_at"] = None
        values["due_soon_notified_at"] = now
    else:
        filters["due_notified_at"] = None
        values["due_notified_at"] = now

    updated = await CustomerProject.filter(**filters).update(**values)
    return updated > 0


def build_project_url(project_id: int | None, task_id: int | None = None) -> str:
    base_url = settings.get_web_base_url()
    if not base_url or not project_id:
        return ""
    query = {"project_id": project_id}
    if task_id:
        query["task_id"] = task_id
    return f"{base_url}/project-board?{urlencode(query)}"


def parse_mention_map(raw: str | None) -> dict[str, str]:
    text = str(raw or "").strip()
    if not text:
        return {}
    try:
        value = json.loads(text)
        if isinstance(value, dict):
            return {str(key).strip(): str(item).strip() for key, item in value.items() if key and item}
    except json.JSONDecodeError:
        pass

    result: dict[str, str] = {}
    for item in re.split(r"[;\n,]", text):
        if not item.strip():
            continue
        if "=" in item:
            key, value = item.split("=", 1)
        elif ":" in item:
            key, value = item.split(":", 1)
        else:
            continue
        key = key.strip()
        value = value.strip()
        if key and value:
            result[key] = value
    return result


async def send_card_to_person(person: str, card: dict) -> bool:
    receive_id_type, receive_id = await resolve_feishu_receiver(person)
    if not receive_id:
        logger.warning("feishu receiver not resolved for project person: %s", person)
        return False
    try:
        return await send_feishu_app_card(
            receive_id=receive_id,
            receive_id_type=receive_id_type,
            card=card,
        )
    except Exception:
        logger.exception("feishu app message failed for project person: %s", person)
        return False


async def resolve_feishu_receiver(person: str) -> tuple[str, str]:
    name = str(person or "").strip()
    if not name:
        return "", ""

    user_map = parse_mention_map(settings.PROJECT_FEISHU_USER_MAP)
    mapped = str(user_map.get(name) or "").strip()
    if mapped:
        receive_id_type, receive_id = parse_feishu_receiver_value(mapped)
        if receive_id_type == "email":
            user_id = await lookup_feishu_user_id_by_email(receive_id)
            if user_id:
                return "user_id", user_id
            logger.warning(f"feishu receiver email not resolved by contact or directory: person={name} email={receive_id}")
            return "", ""
        if receive_id_type == "mobile":
            user_id = await lookup_feishu_user_id_by_mobile(receive_id)
            if user_id:
                return "user_id", user_id
            logger.warning(f"feishu receiver mobile not resolved by contact: person={name} mobile={receive_id}")
            return "", ""
        return receive_id_type, receive_id

    if "@" in name:
        user_id = await lookup_feishu_user_id_by_email(name)
        if user_id:
            return "user_id", user_id
        logger.warning(f"feishu receiver email not resolved by contact or directory: email={name}")
        return "", ""

    if is_mobile_like(name):
        user_id = await lookup_feishu_user_id_by_mobile(name)
        if user_id:
            return "user_id", user_id
        logger.warning(f"feishu receiver mobile not resolved by contact: mobile={name}")
        return "", ""

    user = await User.filter(Q(alias=name) | Q(username=name) | Q(email=name) | Q(phone=name)).first()
    if user:
        if user.email:
            user_id = await lookup_feishu_user_id_by_email(user.email)
            if user_id:
                return "user_id", user_id
        if user.phone:
            user_id = await lookup_feishu_user_id_by_mobile(user.phone)
            if user_id:
                return "user_id", user_id
        logger.warning(
            f"feishu receiver user not resolved by contact: "
            f"person={name} email={user.email or ''} phone={user.phone or ''}"
        )
    return "", ""


def parse_feishu_receiver_value(value: str) -> tuple[str, str]:
    text = str(value or "").strip()
    if not text:
        return "", ""
    if ":" in text:
        prefix, raw = text.split(":", 1)
        prefix = prefix.strip().lower()
        raw = raw.strip()
        if prefix in {"email", "mobile", "open_id", "user_id", "union_id", "chat_id"} and raw:
            return prefix, raw
    if "@" in text:
        return "email", text
    if text.startswith("ou_"):
        return "open_id", text
    if text.startswith("on_"):
        return "union_id", text
    return "user_id", text


def is_mobile_like(value: str) -> bool:
    digits = "".join(ch for ch in str(value or "") if ch.isdigit())
    return 8 <= len(digits) <= 15 and len(digits) >= len(str(value or "").strip()) - 2


def get_user_display_name(user: User | None) -> str:
    if not user:
        return "未知用户"
    return user.alias or user.username or user.email or "未知用户"


def is_same_person(person: str, user: User | None) -> bool:
    if not user:
        return False
    target = str(person or "").strip().lower()
    if not target:
        return False
    candidates = {
        str(user.alias or "").strip().lower(),
        str(user.username or "").strip().lower(),
        str(user.email or "").strip().lower(),
    }
    return target in candidates


def collect_people(values: list[str | None]) -> list[str]:
    people = []
    for value in values:
        text = str(value or "").strip()
        if not text:
            continue
        for item in re.split(r"[/,，、;；\s]+", text):
            item = item.strip()
            if item:
                people.append(item)
    return unique_people(people)


def is_project_related_to_people(
    project: CustomerProject,
    tasks: list[CustomerProjectTask],
    people: list[str],
) -> bool:
    needles = {str(person or "").strip().lower() for person in people if str(person or "").strip()}
    if not needles:
        return True
    values = [project.owner, getattr(project, "shared_users", None)]
    values.extend(task.assignee for task in tasks)
    haystack = {item.lower() for item in collect_people(flatten_people_values(values))}
    return bool(haystack & needles)


def flatten_people_values(values) -> list[str]:
    result = []
    for value in values:
        if isinstance(value, (list, tuple, set)):
            result.extend(str(item or "") for item in value)
        else:
            result.append(str(value or ""))
    return result


def unique_people(values: list[str]) -> list[str]:
    seen = set()
    result = []
    for value in values:
        item = str(value or "").strip()
        if not item or item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result
