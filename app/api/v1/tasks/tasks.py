from fastapi import APIRouter, Query
from tortoise.expressions import Q

from app.controllers.task import scheduled_task_controller
from app.models.admin import ScheduledTaskLog
from app.schemas import Success, SuccessExtra
from app.schemas.tasks import ScheduledTaskCreate, ScheduledTaskToggle, ScheduledTaskUpdate
from app.services.task_runner import execute_scheduled_task

router = APIRouter()


@router.get("/list", summary="查看定时任务列表")
async def list_task(
    page: int = Query(1, description="页码"),
    page_size: int = Query(10, description="每页数量"),
    name: str = Query(None, description="任务名称"),
    task_type: str = Query(None, description="任务类型"),
    is_enabled: bool = Query(None, description="是否启用"),
):
    q = Q()
    if name:
        q &= Q(name__contains=name)
    if task_type:
        q &= Q(task_type=task_type)
    if is_enabled is not None:
        q &= Q(is_enabled=is_enabled)
    total, task_objs = await scheduled_task_controller.list(
        page=page, page_size=page_size, search=q, order=["-is_enabled", "next_run_at", "id"]
    )
    data = [await obj.to_dict() for obj in task_objs]
    return SuccessExtra(data=data, total=total, page=page, page_size=page_size)


@router.get("/get", summary="查看定时任务")
async def get_task(id: int = Query(..., description="任务ID")):
    task_obj = await scheduled_task_controller.get(id=id)
    return Success(data=await task_obj.to_dict())


@router.get("/logs", summary="查看定时任务执行日志")
async def list_task_logs(
    page: int = Query(1, description="页码"),
    page_size: int = Query(10, description="每页数量"),
    task_id: int = Query(None, description="任务ID"),
    status: str = Query(None, description="执行状态"),
):
    q = Q()
    if task_id:
        q &= Q(task_id=task_id)
    if status:
        q &= Q(status=status)
    total = await ScheduledTaskLog.filter(q).count()
    log_objs = (
        await ScheduledTaskLog.filter(q)
        .offset((page - 1) * page_size)
        .limit(page_size)
        .order_by("-started_at", "-id")
    )
    data = [await obj.to_dict() for obj in log_objs]
    return SuccessExtra(data=data, total=total, page=page, page_size=page_size)


@router.post("/create", summary="创建定时任务")
async def create_task(task_in: ScheduledTaskCreate):
    await scheduled_task_controller.create(obj_in=task_in)
    return Success(msg="Created Successfully")


@router.post("/update", summary="更新定时任务")
async def update_task(task_in: ScheduledTaskUpdate):
    await scheduled_task_controller.update(id=task_in.id, obj_in=task_in)
    return Success(msg="Update Successfully")


@router.post("/toggle", summary="启停定时任务")
async def toggle_task(task_in: ScheduledTaskToggle):
    task_obj = await scheduled_task_controller.get(id=task_in.id)
    task_obj.is_enabled = task_in.is_enabled
    task_obj.next_run_at = scheduled_task_controller.calc_next_run_at(task_obj)
    await task_obj.save()
    return Success(msg="Update Successfully")


@router.post("/run", summary="手动执行定时任务")
async def run_task(id: int = Query(..., description="任务ID")):
    task_obj = await scheduled_task_controller.get(id=id)
    await execute_scheduled_task(task_obj)
    return Success(msg="Executed Successfully")


@router.delete("/delete", summary="删除定时任务")
async def delete_task(id: int = Query(..., description="任务ID")):
    await scheduled_task_controller.remove(id=id)
    return Success(msg="Deleted Success")
