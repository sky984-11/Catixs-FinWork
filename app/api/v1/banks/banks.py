import logging

from fastapi import APIRouter, Query
from tortoise.expressions import Q

from app.controllers.bank import bank_controller
from app.schemas.banks import BankCreate, BankUpdate
from app.schemas.base import Success, SuccessExtra

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/list", summary="查看银行列表")
async def list_bank(
    page: int = Query(1, description="页码"),
    page_size: int = Query(50, description="每页数量"),
    name: str = Query("", description="银行名称，用于搜索"),
):
    q = Q()
    if name:
        q &= Q(name__contains=name)
    total, objs = await bank_controller.list(page=page, page_size=page_size, search=q, order=["-id"])
    data = [await obj.to_dict() for obj in objs]
    return SuccessExtra(data=data, total=total, page=page, page_size=page_size)


@router.post("/create", summary="创建银行")
async def create_bank(obj_in: BankCreate):
    obj = await bank_controller.create(obj_in)
    return Success(msg="Created Successfully", data=await obj.to_dict())


@router.post("/update", summary="更新银行")
async def update_bank(obj_in: BankUpdate):
    obj = await bank_controller.update(id=obj_in.id, obj_in=obj_in)
    return Success(msg="Updated Successfully", data=await obj.to_dict())


@router.delete("/delete", summary="删除银行")
async def delete_bank(bank_id: int = Query(..., description="银行ID")):
    await bank_controller.remove(id=bank_id)
    return Success(msg="Deleted Successfully")

