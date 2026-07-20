from datetime import date, datetime, timedelta

from app.log import logger
from app.models.project import CustomerProjectTask
from app.settings.config import settings
from app.utils.feishu_bot import send_project_task_due_notification


async def notify_due_project_tasks(now: datetime | None = None) -> int:
    webhook_url = str(settings.PROJECT_TASK_FEISHU_WEBHOOK_URL or "").strip()
    if not webhook_url:
        return 0

    now = now or datetime.now()
    today = now.date()
    tomorrow = today + timedelta(days=1)
    sent_count = 0

    due_soon_tasks = await CustomerProjectTask.filter(
        is_done=False,
        due_date=tomorrow,
        due_soon_notified_at=None,
    ).select_related("project", "project__customer")
    for task in due_soon_tasks:
        if await notify_project_task(task, "due_soon", now, webhook_url):
            sent_count += 1

    due_tasks = await CustomerProjectTask.filter(
        is_done=False,
        due_date__lte=today,
        due_notified_at=None,
    ).select_related("project", "project__customer")
    for task in due_tasks:
        if await notify_project_task(task, "due", now, webhook_url):
            sent_count += 1

    return sent_count


async def notify_project_task(
    task: CustomerProjectTask,
    stage: str,
    now: datetime,
    webhook_url: str,
) -> bool:
    project = task.project
    if getattr(project, "status", "") in {"completed", "archived"}:
        return False

    customer = await project.customer if getattr(project, "customer_id", None) else None
    try:
        sent = await send_project_task_due_notification(
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

    if not sent:
        return False

    if stage == "due_soon":
        task.due_soon_notified_at = now
    else:
        task.due_notified_at = now
    await task.save(update_fields=["due_soon_notified_at", "due_notified_at", "updated_at"])
    return True


def format_due_date(value: date | None) -> str:
    return value.isoformat() if value else "未设置"
