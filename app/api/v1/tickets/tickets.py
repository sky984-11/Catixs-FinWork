import logging
import os
import uuid
from datetime import datetime

from fastapi import APIRouter, File, Query, UploadFile

from app.controllers.ticket import ticket_controller
from app.schemas.base import Success, SuccessExtra
from app.schemas.tickets import TicketCreate, TicketUpdate

logger = logging.getLogger(__name__)

router = APIRouter()

# 工单附件上传目录
UPLOAD_DIR = "uploads/tickets"
os.makedirs(UPLOAD_DIR, exist_ok=True)


@router.get("/list", summary="查看工单列表")
async def list_tickets(
    page: int = Query(1, description="页码"),
    page_size: int = Query(10, description="每页数量"),
    title: str = Query("", description="工单标题，用于搜索"),
    status: int | None = Query(None, description="工单状态：0-已完成, 1-进行中, 2-未开始, 3-已关闭"),
    type: int | None = Query(None, description="工单类型：0-故障工单, 1-服务请求, 2-变更工单, 3-维护工单"),
    user_id: int | None = Query(None, description="用户ID"),
    assignee_id: int | None = Query(None, description="处理人ID"),
):
    from tortoise.expressions import Q
    
    q = Q()
    if title:
        q &= Q(title__contains=title)
    if status is not None:
        q &= Q(status=status)
    if type is not None:
        q &= Q(type=type)
    if user_id is not None:
        q &= Q(user_id=user_id)
    if assignee_id is not None:
        q &= Q(assignee_id=assignee_id)

    total, ticket_objs = await ticket_controller.list_tickets(page=page, page_size=page_size, search=q, order=["-created_at"])
    data = [await obj.to_dict() for obj in ticket_objs]
    return SuccessExtra(data=data, total=total, page=page, page_size=page_size)


@router.get("/get", summary="查看工单详情")
async def get_ticket(
    ticket_id: int = Query(..., description="工单ID"),
):
    ticket_obj = await ticket_controller.get(id=ticket_id)
    return Success(data=await ticket_obj.to_dict())


@router.post("/create", summary="创建工单")
async def create_ticket(
    ticket_in: TicketCreate,
):
    ticket_obj = await ticket_controller.create_ticket(ticket_in)
    return Success(msg="工单创建成功", data=await ticket_obj.to_dict())


@router.post("/update", summary="更新工单")
async def update_ticket(
    ticket_in: TicketUpdate,
):
    ticket_obj = await ticket_controller.update_ticket(id=ticket_in.id, obj_in=ticket_in)
    return Success(msg="工单更新成功", data=await ticket_obj.to_dict())


@router.delete("/delete", summary="删除工单")
async def delete_ticket(
    ticket_id: int = Query(..., description="工单ID"),
):
    await ticket_controller.remove(id=ticket_id)
    return Success(msg="工单删除成功")


@router.get("/get_by_no", summary="根据工单编号查询工单")
async def get_ticket_by_no(
    ticket_no: str = Query(..., description="工单编号"),
):
    ticket_obj = await ticket_controller.get_ticket_by_no(ticket_no=ticket_no)
    if not ticket_obj:
        return Success(msg="工单不存在", code=404)
    return Success(data=await ticket_obj.to_dict())


@router.post("/upload", summary="上传工单附件图片")
async def upload_ticket_attachment(
    file: UploadFile = File(..., description="附件图片"),
):
    # 只允许图片
    if not file.content_type or not file.content_type.startswith('image/'):
        return Success(msg="只允许上传图片文件", code=400)

    # 生成唯一文件名
    file_ext = os.path.splitext(file.filename)[1]
    unique_filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:8]}{file_ext}"
    file_path = os.path.join(UPLOAD_DIR, unique_filename)

    # 保存文件
    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)

    # 返回可访问的URL路径
    file_url = f"/uploads/tickets/{unique_filename}"
    return Success(msg="上传成功", data={"url": file_url})
