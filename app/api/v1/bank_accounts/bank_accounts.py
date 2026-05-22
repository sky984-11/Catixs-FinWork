import logging

from fastapi import APIRouter, Query
from tortoise.expressions import Q

from app.controllers.bank_account import bank_account_controller
from app.schemas.bank_accounts import BankAccountCreate, BankAccountUpdate
from app.schemas.base import Success, SuccessExtra

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/list", summary="查看银行账户列表")
async def list_bank_account(
    page: int = Query(1, description="页码"),
    page_size: int = Query(10, description="每页数量"),
    company_id: int = Query(..., description="公司ID"),
):
    q = Q(company_id=company_id)
    query = bank_account_controller.model.filter(q).prefetch_related("bank").order_by("-id")
    total = await query.count()
    objs = await query.offset((page - 1) * page_size).limit(page_size)
    data = []
    for obj in objs:
        d = await obj.to_dict()
        d["bank_id"] = obj.bank_id
        d["bank_name"] = getattr(getattr(obj, "bank", None), "name", None)
        d["bank_swift_code"] = getattr(getattr(obj, "bank", None), "swift_code", None)
        d["bank_address"] = getattr(getattr(obj, "bank", None), "bank_address", None)
        if not d.get("swift_code"):
            d["swift_code"] = d["bank_swift_code"]
        data.append(d)
    return SuccessExtra(data=data, total=total, page=page, page_size=page_size)


@router.post("/create", summary="创建银行账户")
async def create_bank_account(
    obj_in: BankAccountCreate,
):
    obj = await bank_account_controller.create(obj_in)
    return Success(msg="Created Successfully", data=await obj.to_dict())


@router.post("/update", summary="更新银行账户")
async def update_bank_account(
    obj_in: BankAccountUpdate,
):
    obj = await bank_account_controller.update(id=obj_in.id, obj_in=obj_in)
    return Success(msg="Updated Successfully", data=await obj.to_dict())


@router.delete("/delete", summary="删除银行账户")
async def delete_bank_account(
    bank_account_id: int = Query(..., description="银行账户ID"),
):
    await bank_account_controller.remove(id=bank_account_id)
    return Success(msg="Deleted Successfully")
