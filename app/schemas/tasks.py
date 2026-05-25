from typing import Optional

from pydantic import BaseModel, Field, field_validator


class BaseScheduledTask(BaseModel):
    name: str = Field(..., description="任务名称", max_length=100)
    task_type: str = Field("script", description="任务类型")
    script_path: Optional[str] = Field(None, description="脚本路径", max_length=255)
    command: Optional[str] = Field(None, description="执行命令", max_length=500)
    schedule_type: str = Field("weekly", description="调度类型")
    day_of_week: Optional[int] = Field(None, ge=0, le=6, description="周几执行，0表示周一")
    hour: int = Field(2, ge=0, le=23, description="执行小时")
    minute: int = Field(0, ge=0, le=59, description="执行分钟")
    interval_minutes: Optional[int] = Field(None, ge=1, description="间隔分钟")
    is_enabled: bool = Field(True, description="是否启用")

    @field_validator("task_type")
    @classmethod
    def validate_task_type(cls, value: str) -> str:
        if value not in {"script", "command", "db_backup"}:
            raise ValueError("task_type must be script, command or db_backup")
        return value

    @field_validator("schedule_type")
    @classmethod
    def validate_schedule_type(cls, value: str) -> str:
        if value not in {"daily", "weekly", "interval"}:
            raise ValueError("schedule_type must be daily, weekly or interval")
        return value


class ScheduledTaskCreate(BaseScheduledTask):
    ...


class ScheduledTaskUpdate(BaseScheduledTask):
    id: int


class ScheduledTaskToggle(BaseModel):
    id: int
    is_enabled: bool
