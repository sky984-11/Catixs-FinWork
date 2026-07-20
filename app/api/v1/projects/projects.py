import logging
import base64
import binascii
import os
import uuid
from datetime import datetime

from fastapi import APIRouter, Query
from tortoise.expressions import Q

from app.controllers.project import customer_project_controller
from app.core.ctx import CTX_USER_ID
from app.models.admin import User
from app.models.project import (
    CustomerProject,
    CustomerProjectAttachment,
    CustomerProjectDiscussion,
    CustomerProjectTask,
)
from app.schemas.base import Success, SuccessExtra
from app.schemas.projects import (
    CustomerProjectCreate,
    CustomerProjectStatusUpdate,
    CustomerProjectUpdate,
    ProjectAttachmentUpload,
    ProjectDiscussionCreate,
    ProjectTaskCreate,
    ProjectTaskUpdate,
)

logger = logging.getLogger(__name__)

router = APIRouter()

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))
UPLOAD_DIR = os.path.join(PROJECT_ROOT, "uploads", "projects")
MAX_UPLOAD_FILE_SIZE = 20 * 1024 * 1024
os.makedirs(UPLOAD_DIR, exist_ok=True)


async def serialize_project(project: CustomerProject) -> dict:
    data = await project.to_dict()
    data.pop("next_action", None)
    if data.get("status") == "blocked":
        data["status"] = "active"
    customer = await project.customer if data.get("customer_id") else None
    data["customer_name"] = customer.name if customer else ""
    data["customer_legal_name"] = customer.legal_name if customer else ""
    return data


async def serialize_project_detail(project: CustomerProject) -> dict:
    data = await serialize_project(project)
    tasks = await CustomerProjectTask.filter(project_id=project.id).order_by("is_done", "sort_order", "due_date")
    attachments = await CustomerProjectAttachment.filter(project_id=project.id, task_id=None).order_by("-created_at")
    data["tasks"] = [await serialize_task(item) for item in tasks]
    data["attachments"] = [await serialize_attachment(item) for item in attachments]
    return data


async def serialize_task(item: CustomerProjectTask) -> dict:
    data = await item.to_dict()
    discussions = await CustomerProjectDiscussion.filter(
        project_id=item.project_id,
        task_id=item.id,
    ).order_by("created_at")
    attachments = await CustomerProjectAttachment.filter(
        project_id=item.project_id,
        task_id=item.id,
    ).order_by("-created_at")
    data["discussions"] = [await serialize_discussion(discussion) for discussion in discussions]
    data["attachments"] = [await serialize_attachment(attachment) for attachment in attachments]
    return data


async def serialize_discussion(item: CustomerProjectDiscussion) -> dict:
    data = await item.to_dict()
    user = await User.get_or_none(id=item.author_id) if item.author_id else None
    data["author_name"] = get_user_display_name(user)
    task = await item.task if data.get("task_id") else None
    attachment = await item.attachment if data.get("attachment_id") else None
    data["referenced_task"] = await task.to_dict() if task else None
    data["referenced_attachment"] = await serialize_attachment(attachment) if attachment else None
    return data


async def serialize_attachment(item: CustomerProjectAttachment) -> dict:
    data = await item.to_dict()
    user = await User.get_or_none(id=item.uploader_id) if item.uploader_id else None
    data["uploader_name"] = get_user_display_name(user)
    return data


def get_current_user_id() -> int | None:
    try:
        return CTX_USER_ID.get()
    except LookupError:
        return None


def get_user_display_name(user: User | None) -> str:
    if not user:
        return "未知用户"
    return user.alias or user.username or "未知用户"


def normalize_project_payload(payload: dict) -> dict:
    if not str(payload.get("code") or "").strip():
        payload["code"] = None
    if payload.get("status") == "blocked":
        payload["status"] = "active"
    for key in ["owner", "contract_no", "description"]:
        if payload.get(key) is None:
            payload[key] = ""
    payload["progress"] = max(0, min(100, int(payload.get("progress") or 0)))
    return payload


@router.get("/list", summary="查看客户项目列表")
async def list_project(
    page: int = Query(1, description="页码"),
    page_size: int = Query(100, description="每页数量"),
    keyword: str = Query("", description="项目名、编号、合同号或负责人"),
    customer_id: int | None = Query(None, description="客户ID"),
    status: str = Query("", description="项目状态"),
    priority: str = Query("", description="优先级"),
    health: str = Query("", description="健康度"),
    owner: str = Query("", description="负责人"),
):
    q = Q()
    if keyword:
        q &= (
            Q(name__contains=keyword)
            | Q(code__contains=keyword)
            | Q(contract_no__contains=keyword)
            | Q(owner__contains=keyword)
        )
    if customer_id:
        q &= Q(customer_id=customer_id)
    if status:
        q &= Q(status=status)
    if priority:
        q &= Q(priority=priority)
    if health:
        q &= Q(health=health)
    if owner:
        q &= Q(owner__contains=owner)

    total, project_objs = await customer_project_controller.list_projects(
        page=page,
        page_size=page_size,
        search=q,
        order=["sort_order", "due_date", "-updated_at"],
    )
    data = [await serialize_project(obj) for obj in project_objs]
    summary = build_project_summary(data)
    return SuccessExtra(data=data, total=total, page=page, page_size=page_size, summary=summary)


@router.get("/get", summary="查看客户项目")
async def get_project(project_id: int = Query(..., description="项目ID")):
    project_obj = await customer_project_controller.get(id=project_id)
    return Success(data=await serialize_project_detail(project_obj))


@router.post("/create", summary="创建客户项目")
async def create_project(project_in: CustomerProjectCreate):
    project_obj = await customer_project_controller.create(
        normalize_project_payload(project_in.model_dump())
    )
    return Success(msg="Created Successfully", data=await serialize_project(project_obj))


@router.post("/update", summary="更新客户项目")
async def update_project(project_in: CustomerProjectUpdate):
    payload = normalize_project_payload(project_in.model_dump(exclude_unset=True, exclude={"id"}))
    project_obj = await customer_project_controller.update(id=project_in.id, obj_in=payload)
    return Success(msg="Updated Successfully", data=await serialize_project(project_obj))


@router.post("/status", summary="更新客户项目看板状态")
async def update_project_status(project_in: CustomerProjectStatusUpdate):
    project_obj = await customer_project_controller.update(
        id=project_in.id,
        obj_in={"status": project_in.status, "sort_order": project_in.sort_order},
    )
    return Success(msg="Updated Successfully", data=await serialize_project(project_obj))


@router.delete("/delete", summary="删除客户项目")
async def delete_project(project_id: int = Query(..., description="项目ID")):
    await customer_project_controller.remove(id=project_id)
    return Success(msg="Deleted Successfully")


@router.post("/discussion/create", summary="新增项目讨论")
async def create_project_discussion(discussion_in: ProjectDiscussionCreate):
    project_obj = await customer_project_controller.get(id=discussion_in.project_id)
    task = None
    attachment = None
    if discussion_in.task_id:
        task = await CustomerProjectTask.get(id=discussion_in.task_id, project_id=project_obj.id)
    if discussion_in.attachment_id:
        attachment = await CustomerProjectAttachment.get(
            id=discussion_in.attachment_id,
            project_id=project_obj.id,
        )
    discussion = await CustomerProjectDiscussion.create(
        project=project_obj,
        author_id=get_current_user_id(),
        content=discussion_in.content.strip(),
        task=task,
        attachment=attachment,
    )
    return Success(msg="Created Successfully", data=await serialize_discussion(discussion))


@router.delete("/discussion/delete", summary="删除项目讨论")
async def delete_project_discussion(discussion_id: int = Query(..., description="讨论ID")):
    discussion = await CustomerProjectDiscussion.get(id=discussion_id)
    await discussion.delete()
    return Success(msg="Deleted Successfully")


@router.post("/task/create", summary="创建项目任务")
async def create_project_task(task_in: ProjectTaskCreate):
    project_obj = await customer_project_controller.get(id=task_in.project_id)
    payload = task_in.model_dump(exclude={"project_id"})
    task = await CustomerProjectTask.create(project=project_obj, **payload)
    return Success(msg="Created Successfully", data=await serialize_task(task))


@router.post("/task/update", summary="更新项目任务")
async def update_project_task(task_in: ProjectTaskUpdate):
    task = await CustomerProjectTask.get(id=task_in.id)
    payload = task_in.model_dump(exclude={"id", "project_id"}, exclude_unset=True)
    if "due_date" in payload and payload["due_date"] != task.due_date:
        payload["due_soon_notified_at"] = None
        payload["due_notified_at"] = None
    task.update_from_dict(payload)
    await task.save()
    return Success(msg="Updated Successfully", data=await serialize_task(task))


@router.delete("/task/delete", summary="删除项目任务")
async def delete_project_task(task_id: int = Query(..., description="任务ID")):
    task = await CustomerProjectTask.get(id=task_id)
    await task.delete()
    return Success(msg="Deleted Successfully")


@router.post("/attachment/upload", summary="上传项目截图资料")
async def upload_project_attachment(upload: ProjectAttachmentUpload):
    project_obj = await customer_project_controller.get(id=upload.project_id)
    task = None
    if upload.task_id:
        task = await CustomerProjectTask.get(id=upload.task_id, project_id=project_obj.id)
    content, content_type = decode_base64_file(upload)
    if not content:
        return Success(msg="文件内容无效", code=400)
    if len(content) > MAX_UPLOAD_FILE_SIZE:
        return Success(msg="文件大小不能超过 20MB", code=400)

    file_ext = get_file_extension(upload.filename, content_type)
    unique_filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:8]}{file_ext}"
    upload_group = "tasks" if task else "files"
    project_upload_dir = os.path.join(UPLOAD_DIR, str(project_obj.id), upload_group)
    os.makedirs(project_upload_dir, exist_ok=True)
    file_path = os.path.join(project_upload_dir, unique_filename)
    file_url = f"/uploads/projects/{project_obj.id}/{upload_group}/{unique_filename}"

    with open(file_path, "wb") as f:
        f.write(content)

    attachment = await CustomerProjectAttachment.create(
        project=project_obj,
        task=task,
        uploader_id=get_current_user_id(),
        name=upload.filename,
        file_url=file_url,
        content_type=content_type,
        remark=upload.remark or "",
    )
    return Success(msg="Uploaded Successfully", data=await serialize_attachment(attachment))


@router.delete("/attachment/delete", summary="删除项目截图资料")
async def delete_project_attachment(attachment_id: int = Query(..., description="附件ID")):
    attachment = await CustomerProjectAttachment.get(id=attachment_id)
    await attachment.delete()
    return Success(msg="Deleted Successfully")


def build_project_summary(projects: list[dict]) -> dict:
    status_counts = {}
    priority_counts = {}
    health_counts = {}
    overdue = 0
    today = None

    for project in projects:
        status_counts[project["status"]] = status_counts.get(project["status"], 0) + 1
        priority_counts[project["priority"]] = priority_counts.get(project["priority"], 0) + 1
        health_counts[project["health"]] = health_counts.get(project["health"], 0) + 1
        due_date = project.get("due_date")
        if not due_date or project.get("status") in {"completed", "archived"}:
            continue
        if today is None:
            from datetime import date

            today = date.today().strftime("%Y-%m-%d")
        if due_date < today:
            overdue += 1

    return {
        "count": len(projects),
        "status_counts": status_counts,
        "priority_counts": priority_counts,
        "health_counts": health_counts,
        "overdue": overdue,
    }


def decode_base64_file(upload: ProjectAttachmentUpload) -> tuple[bytes, str]:
    content_type = str(upload.content_type or "").strip().lower()
    base64_data = str(upload.data or "").strip()

    if base64_data.startswith("data:"):
        header, _, payload = base64_data.partition(",")
        if not payload:
            return b"", content_type
        if ";" in header:
            content_type = header[5:].split(";", 1)[0].strip().lower() or content_type
        base64_data = payload

    try:
        content = base64.b64decode(base64_data, validate=True)
    except (binascii.Error, ValueError):
        return b"", content_type

    return content, content_type


def get_file_extension(filename: str, content_type: str) -> str:
    ext = os.path.splitext(os.path.basename(filename or ""))[1].lower()
    if ext:
        return ext
    content_type_exts = {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/gif": ".gif",
        "image/webp": ".webp",
        "image/bmp": ".bmp",
        "image/svg+xml": ".svg",
        "application/pdf": ".pdf",
        "text/plain": ".txt",
        "text/csv": ".csv",
        "application/json": ".json",
        "application/zip": ".zip",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
    }
    return content_type_exts.get(content_type, ".bin")
