import base64
import binascii
import logging
import json
import os
import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query, Request
from starlette.concurrency import run_in_threadpool
from tortoise.exceptions import DoesNotExist
from tortoise.expressions import Q

from app.controllers.ticket import ticket_controller
from app.core.ctx import CTX_USER_ID
from app.core.dependency import DependAuth
from app.models.admin import User
from app.models.ticket import Ticket
from app.schemas.base import Success, SuccessExtra
from app.schemas.tickets import TicketAttachmentUpload, TicketCreate, TicketEmailSend, TicketUpdate
from app.utils.feishu_bot import TICKET_STATUS_MAP, TICKET_TYPE_MAP, send_ticket_created_notification
from app.utils.feishu_email import send_email

logger = logging.getLogger(__name__)

router = APIRouter()

TICKET_MANAGER_ROLE_NAMES = {"admin", "noc", "管理员"}
TICKET_MANAGER_ACCOUNT_NAMES = {"noc"}

# 工单附件上传目录
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))
UPLOAD_DIR = os.path.join(PROJECT_ROOT, "uploads", "tickets")
MAX_UPLOAD_IMAGE_SIZE = 5 * 1024 * 1024
os.makedirs(UPLOAD_DIR, exist_ok=True)


async def can_view_all_tickets(user: User) -> bool:
    if user.is_superuser:
        return True
    user_names = {
        str(user.username or "").strip().lower(),
        str(user.alias or "").strip().lower(),
    }
    email_local = str(user.email or "").split("@", 1)[0].strip().lower()
    if email_local:
        user_names.add(email_local)
    if user_names & TICKET_MANAGER_ACCOUNT_NAMES:
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


def build_ticket_detail_url(request: Request, ticket_id: int) -> str:
    frontend_origin = get_frontend_origin(request)
    return f"{frontend_origin}/ticket/detail?ticket_id={ticket_id}"


def build_ticket_email_content(ticket_obj: Ticket, creator_name: str, ticket_url: str) -> str:
    type_name = TICKET_TYPE_MAP.get(ticket_obj.type, "未知类型")
    status_name = TICKET_STATUS_MAP.get(ticket_obj.status, "未知状态")
    created_at = ticket_obj.created_at.strftime("%Y-%m-%d %H:%M") if ticket_obj.created_at else "-"
    location = ticket_obj.location or "-"
    description = ticket_obj.desc or "暂无描述"

    return "\n".join(
        [
            "您好，您有一条工单通知，请及时查看。",
            "",
            f"工单编号：{ticket_obj.ticket_no}",
            f"工单标题：{ticket_obj.title}",
            f"工单类型：{type_name}",
            f"当前状态：{status_name}",
            f"创建人：{creator_name}",
            f"创建时间：{created_at}",
            f"发生地点：{location}",
            "",
            "工单描述：",
            description,
            "",
            f"详情链接：{ticket_url}",
        ]
    )


def get_frontend_origin(request: Request) -> str:
    # 只动态获取前端访问前缀，后面的工单详情路由固定为 /ticket/detail。
    origin = request.headers.get("origin", "").rstrip("/")
    if origin:
        return origin

    referer = request.headers.get("referer", "")
    if referer:
        from urllib.parse import urlsplit

        parts = urlsplit(referer)
        if parts.scheme and parts.netloc:
            return f"{parts.scheme}://{parts.netloc}".rstrip("/")

    forwarded_proto = request.headers.get("x-forwarded-proto")
    forwarded_host = request.headers.get("x-forwarded-host") or request.headers.get("host")

    if forwarded_proto and forwarded_host:
        return f"{forwarded_proto}://{forwarded_host}".rstrip("/")
    return str(request.base_url).rstrip("/")


def decode_base64_image(upload: TicketAttachmentUpload) -> tuple[bytes, str]:
    content_type = str(upload.content_type or "").strip().lower()
    base64_data = str(upload.data or "").strip()

    if base64_data.startswith("data:"):
        header, _, payload = base64_data.partition(",")
        if not payload:
            return b"", content_type
        if ";" in header:
            content_type = header[5:].split(";", 1)[0].strip().lower() or content_type
        base64_data = payload

    if not content_type.startswith("image/"):
        return b"", content_type

    try:
        content = base64.b64decode(base64_data, validate=True)
    except (binascii.Error, ValueError):
        return b"", content_type

    return content, content_type


def get_image_file_extension(filename: str, content_type: str) -> str:
    ext = os.path.splitext(os.path.basename(filename or ""))[1].lower()
    allowed_exts = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".svg"}
    if ext in allowed_exts:
        return ext
    content_type_exts = {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/gif": ".gif",
        "image/webp": ".webp",
        "image/bmp": ".bmp",
        "image/svg+xml": ".svg",
    }
    return content_type_exts.get(content_type, ".png")


@router.get("/list", summary="查看工单列表", dependencies=[DependAuth])
async def list_tickets(
    page: int = Query(1, description="页码"),
    page_size: int = Query(10, description="每页数量"),
    title: str = Query("", description="工单标题，用于搜索"),
    status: int | None = Query(None, description="工单状态：0-已完成, 1-进行中, 2-未开始, 3-已关闭"),
    type: int | None = Query(None, description="工单类型：0-故障工单, 1-服务请求, 2-维护工单"),
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


@router.get("/users", summary="查看工单用户选项", dependencies=[DependAuth])
async def list_ticket_users():
    current_user = await get_current_ticket_user()
    if not await can_view_all_tickets(current_user):
        raise HTTPException(status_code=403, detail="无权限查看工单用户选项")
    users = await User.all().order_by("username")
    data = [
        {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "alias": user.alias,
        }
        for user in users
    ]
    return Success(data=data)


@router.post("/send_email", summary="发送工单邮件通知", dependencies=[DependAuth])
async def send_ticket_email(
    email_in: TicketEmailSend,
    request: Request,
):
    current_user = await get_current_ticket_user()
    if not await can_view_all_tickets(current_user):
        raise HTTPException(status_code=403, detail="无权限发送工单通知")
    if not email_in.user_ids:
        return Success(code=400, msg="请至少选择一个收件用户")

    ticket_obj = await ticket_controller.get(id=email_in.ticket_id)
    creator = await User.get_or_none(id=ticket_obj.user_id) if ticket_obj.user_id else None
    creator_name = get_user_display_name(creator)
    users = await User.filter(id__in=email_in.user_ids).all()
    recipients = [user.email for user in users if user.email]
    if not recipients:
        return Success(code=400, msg="所选用户没有可用邮箱")

    subject = f"工单通知：{ticket_obj.ticket_no} {ticket_obj.title}"
    content = build_ticket_email_content(
        ticket_obj=ticket_obj,
        creator_name=creator_name,
        ticket_url=build_ticket_detail_url(request, ticket_obj.id),
    )
    failed_emails = []
    for email in recipients:
        try:
            await run_in_threadpool(send_email, email, subject, content)
        except Exception as e:
            logger.error(f"发送工单邮件失败，ticket_id={ticket_obj.id}, email={email}: {e}")
            failed_emails.append(email)

    sent_emails = [email for email in recipients if email not in failed_emails]
    if not sent_emails:
        return Success(code=500, msg="工单邮件发送失败", data={"failed_emails": failed_emails})
    if failed_emails:
        return Success(
            msg="工单邮件部分发送成功",
            data={"sent_emails": sent_emails, "failed_emails": failed_emails},
        )
    return Success(msg="工单邮件发送成功", data={"sent_emails": sent_emails})


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
    request: Request,
):
    current_user = await get_current_ticket_user()
    ticket_data = ticket_in.model_dump()
    ticket_data["user_id"] = current_user.id

    # 创建工单
    ticket_obj = await ticket_controller.create_ticket(TicketCreate(**ticket_data))
    
    # 获取创建人信息
    creator = current_user
    creator_name = creator.username if creator else "未知用户"
    
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
            ticket_url=build_ticket_detail_url(request, ticket_obj.id),
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
        if ticket_obj.type not in (2, 3):
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
    upload: TicketAttachmentUpload,
    ticket_id: int | None = Query(None, description="工单ID"),
):
    content, content_type = decode_base64_image(upload)
    if not content:
        return Success(msg="只允许上传图片文件", code=400)
    if len(content) > MAX_UPLOAD_IMAGE_SIZE:
        return Success(msg="图片大小不能超过 5MB", code=400)

    # 生成唯一文件名
    file_ext = get_image_file_extension(upload.filename, content_type)
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
    with open(file_path, "wb") as f:
        f.write(content)

    return Success(msg="上传成功", data={"url": file_url})
