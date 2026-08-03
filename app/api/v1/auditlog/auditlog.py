from datetime import datetime
from fastapi import APIRouter, Query
from tortoise.expressions import Q

from app.models.admin import AuditLog
from app.schemas import SuccessExtra
from app.schemas.apis import *

router = APIRouter()


@router.get("/list", summary="查看操作日志")
async def get_audit_log_list(
    page: int = Query(1, description="页码"),
    page_size: int = Query(10, description="每页数量"),
    username: str = Query("", description="操作人名称"),
    module: str = Query("", description="功能模块"),
    method: str = Query("", description="请求方法"),
    summary: str = Query("", description="接口描述"),
    path: str = Query("", description="请求路径"),
    status: int = Query(None, description="状态码"),
    start_time: datetime = Query("", description="开始时间"),
    end_time: datetime = Query("", description="结束时间"),
    sort_field: str = Query("", description="排序字段"),
    sort_order: str = Query("", description="排序方向"),
):
    q = Q()
    if username:
        q &= Q(username__icontains=username)
    if module:
        q &= Q(module__icontains=module)
    if method:
        q &= Q(method__icontains=method)
    if summary:
        q &= Q(summary__icontains=summary)
    if path:
        q &= Q(path__icontains=path)
    if status:
        q &= Q(status=status)
    if start_time and end_time:
        q &= Q(created_at__range=[start_time, end_time])
    elif start_time:
        q &= Q(created_at__gte=start_time)
    elif end_time:
        q &= Q(created_at__lte=end_time)

    sortable_fields = {
        "response_time",
        "created_at",
        "status",
        "username",
        "method",
        "path",
        "module",
        "summary",
    }
    order_field = sort_field if sort_field in sortable_fields else "created_at"
    order_prefix = "" if sort_order == "ascend" else "-"
    order_fields = [f"{order_prefix}{order_field}"]
    if order_field != "created_at":
        order_fields.append("-created_at")
    audit_log_objs = (
        await AuditLog.filter(q)
        .order_by(*order_fields)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    total = await AuditLog.filter(q).count()
    data = [await audit_log.to_dict() for audit_log in audit_log_objs]
    return SuccessExtra(data=data, total=total, page=page, page_size=page_size)
