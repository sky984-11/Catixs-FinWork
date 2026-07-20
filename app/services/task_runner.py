import asyncio
import os
import shlex
import subprocess
import sys
import traceback
from datetime import datetime

from tortoise.expressions import Q

from app.controllers.task import scheduled_task_controller
from app.log import logger
from app.models.admin import ScheduledTask, ScheduledTaskLog
from app.services.project_task_notifier import notify_due_project_tasks
from app.settings.config import settings

_scheduler_task: asyncio.Task | None = None
_running_task_ids: set[int] = set()
_project_task_notification_running = False


def _resolve_script_path(script_path: str | None) -> str:
    if not script_path:
        return os.path.join(settings.BASE_DIR, "scripts", "backup_database.py")
    if os.path.isabs(script_path):
        return script_path
    return os.path.abspath(os.path.join(settings.BASE_DIR, script_path))


def _build_subprocess_env() -> dict[str, str]:
    env = os.environ.copy()
    python_path = env.get("PYTHONPATH")
    env["PYTHONPATH"] = (
        settings.BASE_DIR if not python_path else os.pathsep.join([settings.BASE_DIR, python_path])
    )
    return env


async def execute_scheduled_task(task: ScheduledTask) -> None:
    task_id = int(task.id)
    if task_id in _running_task_ids:
        return

    _running_task_ids.add(task_id)
    started_at = datetime.now()
    command = []
    command_text = ""
    stdout_text = ""
    stderr_text = ""
    error_text = ""
    return_code = None
    try:
        if task.task_type in {"script", "db_backup"}:
            script_path = _resolve_script_path(task.script_path)
            command = [sys.executable, script_path]
        else:
            command = shlex.split(task.command or "", posix=os.name != "nt")

        if not command:
            raise ValueError("Task command is empty")
        command_text = shlex.join(command)

        process = await asyncio.to_thread(
            subprocess.run,
            command,
            cwd=settings.BASE_DIR,
            env=_build_subprocess_env(),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
            check=False,
        )
        return_code = process.returncode
        stdout_text = (process.stdout or "").strip()
        stderr_text = (process.stderr or "").strip()
        message = "\n".join(part for part in [stdout_text, stderr_text] if part)[:4000]
        task.last_status = "success" if return_code == 0 else "failed"
        task.last_message = message or f"Task exit code: {return_code}"
    except Exception as exc:
        task.last_status = "failed"
        error_text = traceback.format_exc()
        task.last_message = str(exc)[:4000]
        logger.exception(f"scheduled task failed: {task.name}")
    finally:
        finished_at = datetime.now()
        task.last_run_at = started_at
        task.next_run_at = scheduled_task_controller.calc_next_run_at(task, finished_at)
        await task.save()
        await ScheduledTaskLog.create(
            task_id=task_id,
            task_name=task.name,
            status=task.last_status or "failed",
            command=command_text or " ".join(command),
            return_code=return_code,
            stdout=stdout_text[:20000] if stdout_text else None,
            stderr=stderr_text[:20000] if stderr_text else None,
            error=error_text[:20000] if error_text else None,
            message=(task.last_message or "")[:4000],
            started_at=started_at,
            finished_at=finished_at,
            duration_ms=max(int((finished_at - started_at).total_seconds() * 1000), 0),
        )
        _running_task_ids.discard(task_id)


async def scheduler_loop() -> None:
    global _project_task_notification_running
    while True:
        try:
            now = datetime.now()
            if not _project_task_notification_running:
                _project_task_notification_running = True
                asyncio.create_task(run_project_task_notifications(now))

            due_tasks = await ScheduledTask.filter(
                Q(is_enabled=True) & (Q(next_run_at__lte=now) | Q(next_run_at=None))
            ).limit(10)
            for task in due_tasks:
                if task.next_run_at is None:
                    task.next_run_at = scheduled_task_controller.calc_next_run_at(task, now)
                    await task.save()
                    if task.next_run_at and task.next_run_at > now:
                        continue
                asyncio.create_task(execute_scheduled_task(task))
        except Exception:
            logger.exception("scheduled task loop error")
        await asyncio.sleep(60)


async def run_project_task_notifications(now: datetime) -> None:
    global _project_task_notification_running
    try:
        sent_count = await notify_due_project_tasks(now)
        if sent_count:
            logger.info("project task feishu notifications sent: %s", sent_count)
    except Exception:
        logger.exception("project task notification loop error")
    finally:
        _project_task_notification_running = False


def start_scheduler() -> None:
    global _scheduler_task
    if _scheduler_task is None or _scheduler_task.done():
        _scheduler_task = asyncio.create_task(scheduler_loop())


async def stop_scheduler() -> None:
    global _scheduler_task
    if _scheduler_task:
        _scheduler_task.cancel()
        try:
            await _scheduler_task
        except asyncio.CancelledError:
            pass
        _scheduler_task = None
