import logging
import os
import uuid
from datetime import datetime

from fastapi import APIRouter, File, Query, UploadFile
from tortoise.expressions import Q

from app.controllers.bill import bill_controller
from app.schemas.base import Success, SuccessExtra
from app.schemas.bills import BillCreate, BillUpdate

logger = logging.getLogger(__name__)

router = APIRouter()

# 文件上传目录
UPLOAD_DIR = "uploads/bills"
os.makedirs(UPLOAD_DIR, exist_ok=True)


@router.get("/list", summary="查看账单列表")
async def list_bill(
    page: int = Query(1, description="页码"),
    page_size: int = Query(10, description="每页数量"),
    company_id: int = Query(..., description="公司ID"),
    bill_type: int | None = Query(None, description="账单类型(1客户/2供应商)"),
):
    q = Q(company_id=company_id)
    if bill_type is not None:
        q &= Q(bill_type=bill_type)
    total, objs = await bill_controller.list(page=page, page_size=page_size, search=q, order=["-id"])
    data = [await obj.to_dict() for obj in objs]
    return SuccessExtra(data=data, total=total, page=page, page_size=page_size)


@router.get("/get", summary="查看账单")
async def get_bill(
    bill_id: int = Query(..., description="账单ID"),
):
    obj = await bill_controller.get(id=bill_id)
    return Success(data=await obj.to_dict())


@router.post("/create", summary="创建账单")
async def create_bill(
    obj_in: BillCreate,
):
    obj = await bill_controller.create(obj_in)
    return Success(msg="Created Successfully", data=await obj.to_dict())


@router.post("/update", summary="更新账单")
async def update_bill(
    obj_in: BillUpdate,
):
    obj = await bill_controller.update(id=obj_in.id, obj_in=obj_in)
    return Success(msg="Updated Successfully", data=await obj.to_dict())


@router.delete("/delete", summary="删除账单")
async def delete_bill(
    bill_id: int = Query(..., description="账单ID"),
):
    await bill_controller.remove(id=bill_id)
    return Success(msg="Deleted Successfully")


@router.post("/upload", summary="上传账单PDF")
async def upload_bill_pdf(
    bill_id: int = Query(..., description="账单ID"),
    file: UploadFile = File(..., description="PDF文件"),
):
    # 检查文件类型
    if not file.filename.lower().endswith('.pdf'):
        return Success(msg="Only PDF files are allowed", code=400)
    
    # 生成唯一文件名
    file_ext = os.path.splitext(file.filename)[1]
    unique_filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:8]}{file_ext}"
    file_path = os.path.join(UPLOAD_DIR, unique_filename)
    
    # 保存文件
    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)
    
    # 返回的URL路径
    invoice_url = f"/uploads/bills/{unique_filename}"
    await bill_controller.update(id=bill_id, obj_in={"invoice_url": invoice_url})
    
    return Success(msg="Upload Successfully", data={"invoice_url": invoice_url})

