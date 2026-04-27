import logging

from fastapi import APIRouter, Query
from tortoise.expressions import Q

from app.controllers.vendor import vendor_controller
from app.schemas.base import Success, SuccessExtra
from app.schemas.vendors import VendorCreate, VendorUpdate

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/list", summary="查看供应商列表")
async def list_vendor(
    page: int = Query(1, description="页码"),
    page_size: int = Query(10, description="每页数量"),
    name: str = Query("", description="供应商名称，用于搜索"),
    code: str = Query("", description="供应商编号"),
    status: bool | None = Query(None, description="启用状态"),
):
    q = Q()
    if name:
        q &= Q(name__contains=name)
    if code:
        q &= Q(code__contains=code)
    if status is not None:
        q &= Q(status=status)

    total, vendor_objs = await vendor_controller.list_vendors(page=page, page_size=page_size, search=q)
    data = [await obj.to_dict() for obj in vendor_objs]
    return SuccessExtra(data=data, total=total, page=page, page_size=page_size)


@router.get("/get", summary="查看供应商")
async def get_vendor(
    vendor_id: int = Query(..., description="供应商ID"),
):
    vendor_obj = await vendor_controller.get(id=vendor_id)
    return Success(data=await vendor_obj.to_dict())


@router.post("/create", summary="创建供应商")
async def create_vendor(
    vendor_in: VendorCreate,
):
    vendor_obj = await vendor_controller.create_vendor(vendor_in)
    return Success(msg="Created Successfully", data=await vendor_obj.to_dict())


@router.post("/update", summary="更新供应商")
async def update_vendor(
    vendor_in: VendorUpdate,
):
    vendor_obj = await vendor_controller.update_vendor(id=vendor_in.id, obj_in=vendor_in)
    return Success(msg="Updated Successfully", data=await vendor_obj.to_dict())


@router.delete("/delete", summary="删除供应商")
async def delete_vendor(
    vendor_id: int = Query(..., description="供应商ID"),
):
    await vendor_controller.remove(id=vendor_id)
    return Success(msg="Deleted Successfully")
