import json
import re
from datetime import date, datetime, timedelta
from urllib.parse import urlencode

from app.log import logger
from app.models.project import CustomerProject, CustomerProjectDailySummary, CustomerProjectTask
from app.settings.config import settings
from app.utils.feishu_bot import (
    send_project_daily_summary_card,
    send_project_task_due_notification,
)

DAILY_SUMMARY_STATUSES = ("planning", "active", "acceptance")
DAILY_SUMMARY_LABELS = {
    "planning": "规划中",
    "active": "进行中",
    "acceptance": "验收中",
}


async def notify_due_project_tasks(now: datetime | None = None) -> int:
    webhook_url = str(settings.PROJECT_TASK_FEISHU_WEBHOOK_URL or "").strip()
    if not webhook_url:
        return 0

    now = now or datetime.now()
    soon_deadline = now + timedelta(days=1)
    sent_count = 0

    due_soon_tasks = await CustomerProjectTask.filter(
        is_done=False,
        due_date__gt=now,
        due_date__lte=soon_deadline,
        due_soon_notified_at=None,
    ).select_related("project", "project__customer")
    for task in due_soon_tasks:
        if await notify_project_task(task, "due_soon", now, webhook_url):
            sent_count += 1

    due_tasks = await CustomerProjectTask.filter(
        is_done=False,
        due_date__lte=now,
        due_notified_at=None,
    ).select_related("project", "project__customer")
    for task in due_tasks:
        if await notify_project_task(task, "due", now, webhook_url):
            sent_count += 1

    return sent_count


async def notify_project_daily_summary(now: datetime | None = None) -> bool:
    webhook_url = str(settings.PROJECT_TASK_FEISHU_WEBHOOK_URL or "").strip()
    if not webhook_url:
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
        success = await send_project_daily_summary_card(
            webhook_url=webhook_url,
            summary_date=summary_date.isoformat(),
            sections=sections,
            mention_text=build_mentions(owners),
        )
    except Exception:
        logger.exception("project daily summary feishu notification failed")
        success = False

    record.status = "success" if success else "failed"
    record.sent_at = now if success else None
    record.message = "sent" if success else "feishu webhook failed"
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


async def build_daily_summary_sections() -> tuple[list[dict], list[str]]:
    owner_filter = str(settings.PROJECT_DAILY_SUMMARY_OWNER_FILTER or "").strip()
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
            if owner_filter and not is_project_related_to_people(project, open_tasks, [owner_filter]):
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
                "count": len(status_projects),
                "open_task_count": open_task_count,
                "projects": section_projects,
            }
        )
    return sections, unique_people(owners)


async def notify_project_task(
    task: CustomerProjectTask,
    stage: str,
    now: datetime,
    webhook_url: str,
) -> bool:
    project = task.project
    if getattr(project, "status", "") in {"completed", "archived"}:
        return False

    if not await claim_project_task_notification(task, stage, now):
        return False

    customer = await project.customer if getattr(project, "customer_id", None) else None
    try:
        return await send_project_task_due_notification(
            webhook_url=webhook_url,
            stage=stage,
            project_name=project.name,
            task_title=task.title,
            due_date=format_due_date(task.due_date),
            assignee=task.assignee,
            customer_name=getattr(customer, "name", "") or getattr(customer, "legal_name", ""),
            project_code=project.code,
            remark=task.remark,
        )
    except Exception:
        logger.exception("project task feishu notification failed: task_id=%s stage=%s", task.id, stage)
        return False


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


def build_project_url(project_id: int | None, task_id: int | None = None) -> str:
    base_url = settings.get_web_base_url()
    if not base_url or not project_id:
        return ""
    query = {"project_id": project_id}
    if task_id:
        query["task_id"] = task_id
    return f"{base_url}/project-board?{urlencode(query)}"


def build_mentions(names: list[str]) -> str:
    mention_map = parse_mention_map(settings.PROJECT_FEISHU_MENTION_MAP)
    mention_parts = []
    for name in unique_people(names):
        feishu_user_id = mention_map.get(name)
        if feishu_user_id:
            mention_parts.append(f'<at user_id="{feishu_user_id}">{name}</at>')
        else:
            mention_parts.append(f"@{name}")
    return " ".join(mention_parts)


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
