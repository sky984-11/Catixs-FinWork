from datetime import datetime, timedelta

from app.core.crud import CRUDBase
from app.models.admin import ScheduledTask
from app.schemas.tasks import ScheduledTaskCreate, ScheduledTaskUpdate


class ScheduledTaskController(CRUDBase[ScheduledTask, ScheduledTaskCreate, ScheduledTaskUpdate]):
    def __init__(self):
        super().__init__(model=ScheduledTask)

    def calc_next_run_at(self, task: ScheduledTask | dict, base_time: datetime | None = None) -> datetime | None:
        if isinstance(task, dict):
            schedule_type = task.get("schedule_type")
            day_of_week = task.get("day_of_week")
            hour = task.get("hour", 0)
            minute = task.get("minute", 0)
            interval_minutes = task.get("interval_minutes")
            is_enabled = task.get("is_enabled", True)
        else:
            schedule_type = task.schedule_type
            day_of_week = task.day_of_week
            hour = task.hour
            minute = task.minute
            interval_minutes = task.interval_minutes
            is_enabled = task.is_enabled

        if not is_enabled:
            return None

        now = base_time or datetime.now()
        if schedule_type == "interval":
            return now + timedelta(minutes=interval_minutes or 60)

        candidate = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if schedule_type == "daily":
            if candidate <= now:
                candidate += timedelta(days=1)
            return candidate

        weekday = 6 if day_of_week is None else day_of_week
        days_until = (weekday - now.weekday()) % 7
        candidate += timedelta(days=days_until)
        if candidate <= now:
            candidate += timedelta(days=7)
        return candidate

    async def create(self, obj_in: ScheduledTaskCreate) -> ScheduledTask:
        obj_dict = obj_in.model_dump()
        obj_dict["next_run_at"] = self.calc_next_run_at(obj_dict)
        obj = self.model(**obj_dict)
        await obj.save()
        return obj

    async def update(self, id: int, obj_in: ScheduledTaskUpdate) -> ScheduledTask:
        obj_dict = obj_in.model_dump(exclude_unset=True, exclude={"id"})
        obj_dict["next_run_at"] = self.calc_next_run_at(obj_dict)
        obj = await self.get(id=id)
        obj = obj.update_from_dict(obj_dict)
        await obj.save()
        return obj


scheduled_task_controller = ScheduledTaskController()
