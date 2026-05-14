import logging
import json
import os
import uuid
from datetime import datetime

from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from tortoise.exceptions import DoesNotExist
from tortoise.expressions import Q

from app.controllers.ticket import ticket_controller
from app.core.ctx import CTX_USER_ID
from app.core.dependency import DependAuth
from app.models.admin import User
from app.models.ticket import Ticket
from app.schemas.base import Success, SuccessExtra
from app.schemas.tickets import TicketCreate, TicketUpdate
from app.utils.feishu_bot import send_ticket_created_notification

logger = logging.getLogger(__name__)

router = APIRouter()

TICKET_MANAGER_ROLE_NAMES = {"admin", "noc", "管理员"}

# 工单附件上传目录
UPLOAD_DIR = "uploads/tickets"
os.makedirs(UPLOAD_DIR, exist_ok=True)


async def can_view_all_tickets(user: User) -> bool:
    if user.is_superuser:
        return True
    roles = await user.roles.all()
    role_names = {str(role.name or "").strip().lower() for role in roles}
    return bool(role_names & TICKET_MANAGER_ROLE_NAMES)


async def get_current_ticket_user() -> User:
    current_user_id = CTX_USER_ID.get()
    return await User.get(id=current_user_id)


async def ensure_ticket_access(ticket_obj: Ticket, current_user: User) -> None:
    if await can_view_all_tickets(current_user):
        return
    if str(ticket_obj.user_id) != str(current_user.id):
        raise HTTPException(status_code=403, detail="无权限访问该工单")


def get_user_display_name(user: User | None) -> str:
    if not user:
        return "未知用户"
    return user.alias or user.username or "未知用户"


async def ticket_to_dict(ticket_obj: Ticket) -> dict:
    data = await ticket_obj.to_dict()
    creator = await User.get_or_none(id=ticket_obj.user_id) if ticket_obj.user_id else None
    assignee = await User.get_or_none(id=ticket_obj.assignee_id) if ticket_obj.assignee_id else None
    data["creator_name"] = get_user_display_name(creator)
    data["assignee_name"] = get_user_display_name(assignee) if assignee else ""
    data["attachment_urls"] = get_ticket_attachment_urls(ticket_obj)
    return data


def parse_attachment_urls(attachment_url: str | None) -> list[str]:
    if not attachment_url:
        return []
    try:
        parsed = json.loads(attachment_url)
    except (TypeError, json.JSONDecodeError):
        parsed = None
    if isinstance(parsed, list):
        return [str(url) for url in parsed if str(url).strip()]
    return [attachment_url]


def get_ticket_attachment_urls(ticket_obj: Ticket) -> list[str]:
    urls = parse_attachment_urls(ticket_obj.attachment_url)
    ticket_upload_dir = os.path.join(UPLOAD_DIR, str(ticket_obj.id))
    if os.path.isdir(ticket_upload_dir):
        for filename in sorted(os.listdir(ticket_upload_dir)):
            file_path = os.path.join(ticket_upload_dir, filename)
            if os.path.isfile(file_path):
                urls.append(f"/uploads/tickets/{ticket_obj.id}/{filename}")
    return list(dict.fromkeys(urls))


@router.get("/list", summary="查看工单列表", dependencies=[DependAuth])
async def list_tickets(
    page: int = Query(1, description="页码"),
    page_size: int = Query(10, description="每页数量"),
    title: str = Query("", description="工单标题，用于搜索"),
    status: int | None = Query(None, description="工单状态：0-已完成, 1-进行中, 2-未开始, 3-已关闭"),
    type: int | None = Query(None, description="工单类型：0-故障工单, 1-服务请求, 2-变更工单, 3-维护工单"),
    user_id: int | None = Query(None, description="用户ID"),
    assignee_id: int | None = Query(None, description="处理人ID"),
):
    q = Q()
    if title:
        q &= Q(title__contains=title)
    if status is not None:
        q &= Q(status=status)
    else:
        q &= ~Q(status=3)
    if type is not None:
        q &= Q(type=type)
    
    current_user = await get_current_ticket_user()
    if await can_view_all_tickets(current_user):
        filter_user_id = user_id
    else:
        filter_user_id = current_user.id
    
    if filter_user_id is not None:
        q &= Q(user_id=filter_user_id)
    if assignee_id is not None:
        q &= Q(assignee_id=assignee_id)

    total, ticket_objs = await ticket_controller.list_tickets(page=page, page_size=page_size, search=q, order=["-created_at"])
    data = [await ticket_to_dict(obj) for obj in ticket_objs]
    return SuccessExtra(data=data, total=total, page=page, page_size=page_size)


@router.get("/get", summary="查看工单详情", dependencies=[DependAuth])
async def get_ticket(
    ticket_id: int = Query(..., description="工单ID"),
):
    current_user = await get_current_ticket_user()
    ticket_obj = await ticket_controller.get(id=ticket_id)
    await ensure_ticket_access(ticket_obj, current_user)
    return Success(data=await ticket_to_dict(ticket_obj))


@router.post("/create", summary="创建工单", dependencies=[DependAuth])
async def create_ticket(
    ticket_in: TicketCreate,
):
    current_user = await get_current_ticket_user()
    has_ticket_manager_access = await can_view_all_tickets(current_user)
    ticket_data = ticket_in.model_dump()
    ticket_data["user_id"] = current_user.id

    # 创建工单
    ticket_obj = await ticket_controller.create_ticket(TicketCreate(**ticket_data))
    
    # 获取创建人信息
    creator = current_user
    creator_name = creator.username if creator else "未知用户"
    
    # 判断是否为非管理员用户创建的工单
    is_admin = has_ticket_manager_access
    
    # 只有非管理员用户创建工单时才发送飞书通知
    if not is_admin:
        try:
            await send_ticket_created_notification(
                ticket_no=ticket_obj.ticket_no,
                title=ticket_obj.title,
                ticket_type=ticket_obj.type,
                status=ticket_obj.status,
                creator_name=creator_name,
                description=ticket_obj.desc or "暂无描述",
                created_at=ticket_obj.created_at,
                location=ticket_obj.location,
            )
            logger.info(f"工单 {ticket_obj.ticket_no} 创建通知已发送至飞书")
        except Exception as e:
            # 通知发送失败不影响工单创建结果
            logger.error(f"发送飞书通知失败: {e}")
    
    return Success(msg="工单创建成功", data=await ticket_to_dict(ticket_obj))


@router.post("/update", summary="更新工单", dependencies=[DependAuth])
async def update_ticket(
    ticket_in: TicketUpdate,
):
    current_user = await get_current_ticket_user()
    ticket_obj = None
    if ticket_in.id is not None:
        try:
            ticket_obj = await ticket_controller.get(id=ticket_in.id)
        except DoesNotExist:
            ticket_obj = None
    if ticket_obj is None and ticket_in.ticket_no:
        ticket_obj = await ticket_controller.get_ticket_by_no(ticket_no=ticket_in.ticket_no)
    if ticket_obj is None:
        raise HTTPException(status_code=404, detail="工单不存在")
    await ensure_ticket_access(ticket_obj, current_user)
    if ticket_in.status == 0:
        ticket_in.assignee_id = current_user.id
        ticket_in.end_time = datetime.now()
    ticket_obj = await ticket_controller.update_ticket(id=ticket_obj.id, obj_in=ticket_in)
    return Success(msg="工单更新成功", data=await ticket_to_dict(ticket_obj))


@router.delete("/delete", summary="删除工单", dependencies=[DependAuth])
async def delete_ticket(
    ticket_id: int = Query(..., description="工单ID"),
):
    current_user = await get_current_ticket_user()
    ticket_obj = await ticket_controller.get(id=ticket_id)
    await ensure_ticket_access(ticket_obj, current_user)
    await ticket_controller.remove(id=ticket_id)
    return Success(msg="工单删除成功")


@router.get("/get_by_no", summary="根据工单编号查询工单", dependencies=[DependAuth])
async def get_ticket_by_no(
    ticket_no: str = Query(..., description="工单编号"),
):
    ticket_obj = await ticket_controller.get_ticket_by_no(ticket_no=ticket_no)
    if not ticket_obj:
        return Success(msg="工单不存在", code=404)
    current_user = await get_current_ticket_user()
    await ensure_ticket_access(ticket_obj, current_user)
    return Success(data=await ticket_to_dict(ticket_obj))


@router.post("/upload", summary="上传工单附件图片", dependencies=[DependAuth])
async def upload_ticket_attachment(
    file: UploadFile = File(..., description="附件图片"),
    ticket_id: int | None = Query(None, description="工单ID"),
):
    # 只允许图片
    if not file.content_type or not file.content_type.startswith('image/'):
        return Success(msg="只允许上传图片文件", code=400)

    # 生成唯一文件名
    file_ext = os.path.splitext(file.filename)[1]
    unique_filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:8]}{file_ext}"
    if ticket_id is not None:
        ticket_obj = await ticket_controller.get(id=ticket_id)
        current_user = await get_current_ticket_user()
        await ensure_ticket_access(ticket_obj, current_user)
        ticket_upload_dir = os.path.join(UPLOAD_DIR, str(ticket_id))
        file_url = f"/uploads/tickets/{ticket_id}/{unique_filename}"
    else:
        ticket_upload_dir = UPLOAD_DIR
        file_url = f"/uploads/tickets/{unique_filename}"
    os.makedirs(ticket_upload_dir, exist_ok=True)
    file_path = os.path.join(ticket_upload_dir, unique_filename)

    # 保存文件
    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)

    return Success(msg="上传成功", data={"url": file_url})
