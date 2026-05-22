import logging

from fastapi import APIRouter, Query
from tortoise.expressions import Q

from app.controllers.company import company_controller
from app.schemas.base import Success, SuccessExtra
from app.schemas.companies import CompanyCreate, CompanyUpdate

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/list", summary="查看公司列表")
async def list_company(
    page: int = Query(1, description="页码"),
    page_size: int = Query(10, description="每页数量"),
    name: str = Query("", description="公司简称/全称，用于搜索"),
    code: str = Query("", description="公司编号"),
    role: int | None = Query(None, description="角色：0=签约主体, 1=客户, 2=供应商"),
    status: bool | None = Query(None, description="启用状态"),
    business_only: bool = Query(False, description="仅查询客户和供应商"),
):
    q = Q()
    if name:
        q &= Q(name__contains=name) | Q(legal_name__contains=name)
    if code:
        q &= Q(code__contains=code)
    if role is not None:
        q &= Q(role=role)
    elif business_only:
        q &= Q(role__in=[1, 2])
    if status is not None:
        q &= Q(status=status)

    total, company_objs = await company_controller.list_companies(
        page=page, page_size=page_size, search=q
    )
    data = [await obj.to_dict() for obj in company_objs]
    return SuccessExtra(data=data, total=total, page=page, page_size=page_size)


@router.get("/get", summary="查看公司")
async def get_company(
    company_id: int = Query(..., description="公司ID"),
):
    company_obj = await company_controller.get(id=company_id)
    return Success(data=await company_obj.to_dict())


@router.post("/create", summary="创建公司")
async def create_company(
    company_in: CompanyCreate,
):
    company_obj = await company_controller.create(company_in.model_dump())
    return Success(msg="Created Successfully", data=await company_obj.to_dict())


@router.post("/update", summary="更新公司")
async def update_company(
    company_in: CompanyUpdate,
):
    company_obj = await company_controller.update(
        id=company_in.id, obj_in=company_in.model_dump(exclude_unset=True, exclude={"id"})
    )
    return Success(msg="Updated Successfully", data=await company_obj.to_dict())


@router.delete("/delete", summary="删除公司")
async def delete_company(
    company_id: int = Query(..., description="公司ID"),
):
    await company_controller.remove(id=company_id)
    return Success(msg="Deleted Successfully")
