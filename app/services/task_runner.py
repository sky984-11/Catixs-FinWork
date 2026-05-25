import asyncio
import os
import shlex
import sys
from datetime import datetime

from tortoise.expressions import Q

from app.controllers.task import scheduled_task_controller
from app.log import logger
from app.models.admin import ScheduledTask
from app.settings.config import settings

_scheduler_task: asyncio.Task | None = None
_running_task_ids: set[int] = set()


def _resolve_script_path(script_path: str | None) -> str:
    if not script_path:
        return os.path.join(settings.BASE_DIR, "scripts", "backup_database.py")
    if os.path.isabs(script_path):
        return script_path
    return os.path.abspath(os.path.join(settings.BASE_DIR, script_path))


async def execute_scheduled_task(task: ScheduledTask) -> None:
    task_id = int(task.id)
    if task_id in _running_task_ids:
        return

    _running_task_ids.add(task_id)
    started_at = datetime.now()
    try:
        if task.task_type in {"script", "db_backup"}:
            script_path = _resolve_script_path(task.script_path)
            command = [sys.executable, script_path]
        else:
            command = shlex.split(task.command or "", posix=os.name != "nt")

        if not command:
            raise ValueError("任务命令为空")

        process = await asyncio.create_subprocess_exec(
            *command,
            cwd=settings.BASE_DIR,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()
        message_parts = [
            stdout.decode("utf-8", errors="ignore").strip(),
            stderr.decode("utf-8", errors="ignore").strip(),
        ]
        message = "\n".join(part for part in message_parts if part)[:4000]
        task.last_status = "success" if process.returncode == 0 else "failed"
        task.last_message = message or f"任务退出码：{process.returncode}"
    except Exception as exc:
        task.last_status = "failed"
        task.last_message = str(exc)[:4000]
        logger.exception(f"scheduled task failed: {task.name}")
    finally:
        task.last_run_at = started_at
        task.next_run_at = scheduled_task_controller.calc_next_run_at(task, datetime.now())
        await task.save()
        _running_task_ids.discard(task_id)


async def scheduler_loop() -> None:
    while True:
        try:
            now = datetime.now()
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
