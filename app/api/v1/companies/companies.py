import logging

from fastapi import APIRouter, Query
from tortoise.expressions import Q

from app.controllers.company import company_controller
from app.schemas.base import Success, SuccessExtra
from app.schemas.companies import CompanyCreate, CompanyUpdate

logger = logging.getLogger(__name__)

router = APIRouter()


def normalize_company_payload(payload: dict) -> dict:
    if not str(payload.get("code") or "").strip():
        payload["code"] = None
    try:
        payload["role"] = int(payload.get("role") or 0)
    except (TypeError, ValueError):
        payload["role"] = 0
    return payload


async def serialize_company(company_obj) -> dict:
    data = await company_obj.to_dict()
    contract_company_id = data.get("contract_company_id")
    data["contract_company_name"] = None
    if contract_company_id:
        contract_company = await company_controller.get(id=contract_company_id)
        data["contract_company_name"] = contract_company.name or contract_company.legal_name
    return data


@router.get("/list", summary="查看公司列表")
async def list_company(
    page: int = Query(1, description="页码"),
    page_size: int = Query(10, description="每页数量"),
    name: str = Query("", description="公司简称/全称"),
    code: str = Query("", description="公司编号"),
    role: int | None = Query(None, description="类型：0=签约主体, 1=客户, 2=供应商, 3=客户+供应商"),
    contract_company_id: int | None = Query(None, description="签约主体公司ID"),
    status: bool | None = Query(None, description="启用状态"),
    business_only: bool = Query(False, description="仅查询客户和供应商"),
):
    q = Q()
    if name:
        q &= Q(name__contains=name) | Q(legal_name__contains=name)
    if code:
        q &= Q(code__contains=code)
    if role == 1:
        q &= Q(role__in=[1, 3])
    elif role == 2:
        q &= Q(role__in=[2, 3])
    elif role is not None:
        q &= Q(role=role)
    elif business_only:
        q &= Q(role__in=[1, 2, 3])
    if contract_company_id:
        q &= Q(contract_company_id=contract_company_id)
    if status is not None:
        q &= Q(status=status)

    total, company_objs = await company_controller.list_companies(
        page=page, page_size=page_size, search=q
    )
    data = [await serialize_company(obj) for obj in company_objs]
    return SuccessExtra(data=data, total=total, page=page, page_size=page_size)


@router.get("/get", summary="查看公司")
async def get_company(
    company_id: int = Query(..., description="公司ID"),
):
    company_obj = await company_controller.get(id=company_id)
    return Success(data=await serialize_company(company_obj))


@router.post("/create", summary="创建公司")
async def create_company(
    company_in: CompanyCreate,
):
    company_obj = await company_controller.create(
        normalize_company_payload(company_in.model_dump())
    )
    return Success(msg="Created Successfully", data=await company_obj.to_dict())


@router.post("/update", summary="更新公司")
async def update_company(
    company_in: CompanyUpdate,
):
    payload = normalize_company_payload(
        company_in.model_dump(exclude_unset=True, exclude={"id"})
    )
    company_obj = await company_controller.update(
        id=company_in.id, obj_in=payload
    )
    return Success(msg="Updated Successfully", data=await company_obj.to_dict())


@router.delete("/delete", summary="删除公司")
async def delete_company(
    company_id: int = Query(..., description="公司ID"),
):
    await company_controller.remove(id=company_id)
    return Success(msg="Deleted Successfully")
