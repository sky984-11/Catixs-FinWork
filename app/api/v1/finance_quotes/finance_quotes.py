from fastapi import APIRouter, Query
from tortoise.expressions import Q

from app.controllers.finance_quote import finance_quote_controller
from app.schemas.base import Success, SuccessExtra
from app.schemas.finance_quotes import FinanceQuoteCreate, FinanceQuoteUpdate

router = APIRouter()

SORTABLE_FIELDS = {
    "quote_type",
    "service_resource",
    "region",
    "service_name",
    "provider",
    "bandwidth",
    "burst",
    "site_a",
    "contract_terms",
    "traffic",
    "nrc",
    "mrc",
    "cost_price",
    "target_price",
    "sale_price",
    "status",
    "sort",
    "created_at",
    "updated_at",
}


def build_order(sort_field: str = "", sort_order: str = "") -> list[str]:
    if sort_field in SORTABLE_FIELDS and sort_order in {"ascend", "descend"}:
        prefix = "-" if sort_order == "descend" else ""
        return [f"{prefix}{sort_field}", "sort", "region", "id"]
    return ["sort", "region", "quote_type", "id"]


async def quote_to_dict(obj):
    data = await obj.to_dict()
    if not data.get("remark") and data.get("note"):
        data["remark"] = data.get("note")
    return data


async def build_summary(q: Q) -> dict:
    rows = await finance_quote_controller.model.filter(q).values(
        "quote_type",
        "cost_price",
        "target_price",
        "sale_price",
        "status",
    )
    by_type = {}
    for row in rows:
        quote_type = row.get("quote_type") or "server"
        bucket = by_type.setdefault(
            quote_type,
            {"quote_type": quote_type, "count": 0, "active": 0, "avg_cost": 0, "avg_target": 0, "avg_sale": 0},
        )
        bucket["count"] += 1
        if int(row.get("status") or 0) == 1:
            bucket["active"] += 1
        bucket["avg_cost"] += float(row.get("cost_price") or 0)
        bucket["avg_target"] += float(row.get("target_price") or 0)
        bucket["avg_sale"] += float(row.get("sale_price") or 0)

    for bucket in by_type.values():
        count = bucket["count"] or 1
        bucket["avg_cost"] = round(bucket["avg_cost"] / count, 2)
        bucket["avg_target"] = round(bucket["avg_target"] / count, 2)
        bucket["avg_sale"] = round(bucket["avg_sale"] / count, 2)

    return {
        "count": len(rows),
        "active": sum(1 for row in rows if int(row.get("status") or 0) == 1),
        "by_type": sorted(by_type.values(), key=lambda item: item["quote_type"]),
    }


@router.get("/list", summary="查看报价列表")
async def list_quote(
    page: int = Query(1, description="页码"),
    page_size: int = Query(20, description="每页数量"),
    quote_type: str = Query("", description="报价类型"),
    region: str = Query("", description="地区"),
    status: int | None = Query(None, description="状态"),
    keyword: str = Query("", description="关键字"),
    sort_field: str = Query("", description="排序字段"),
    sort_order: str = Query("", description="排序方向"),
):
    q = Q()
    if quote_type:
        q &= Q(quote_type=quote_type)
    if region:
        q &= Q(region__contains=region)
    if status is not None:
        q &= Q(status=status)
    if keyword:
        q &= (
            Q(region__contains=keyword)
            | Q(service_resource__contains=keyword)
            | Q(service_name__contains=keyword)
            | Q(provider__contains=keyword)
            | Q(cpu_model__contains=keyword)
            | Q(cpu_cores__contains=keyword)
            | Q(memory__contains=keyword)
            | Q(disk__contains=keyword)
            | Q(bandwidth__contains=keyword)
            | Q(burst__contains=keyword)
            | Q(traffic__contains=keyword)
            | Q(site_a__contains=keyword)
            | Q(protection__contains=keyword)
            | Q(xc_cabling__contains=keyword)
            | Q(contract_terms__contains=keyword)
            | Q(usd_per_mbps_nrc__contains=keyword)
            | Q(ip_count__contains=keyword)
            | Q(note__contains=keyword)
            | Q(remark__contains=keyword)
        )

    total, objs = await finance_quote_controller.list(
        page=page,
        page_size=page_size,
        search=q,
        order=build_order(sort_field, sort_order),
    )
    return SuccessExtra(
        data=[await quote_to_dict(obj) for obj in objs],
        total=total,
        page=page,
        page_size=page_size,
        summary=await build_summary(q),
    )


@router.get("/get", summary="查看报价")
async def get_quote(quote_id: int = Query(..., description="报价ID")):
    obj = await finance_quote_controller.get(id=quote_id)
    return Success(data=await quote_to_dict(obj))


@router.post("/create", summary="创建报价")
async def create_quote(obj_in: FinanceQuoteCreate):
    if obj_in.remark and not obj_in.note:
        obj_in.note = obj_in.remark
    obj = await finance_quote_controller.create(obj_in)
    return Success(msg="Created Successfully", data=await quote_to_dict(obj))


@router.post("/update", summary="更新报价")
async def update_quote(obj_in: FinanceQuoteUpdate):
    obj_in.note = obj_in.remark
    obj = await finance_quote_controller.update(id=obj_in.id, obj_in=obj_in)
    return Success(msg="Updated Successfully", data=await quote_to_dict(obj))


@router.delete("/delete", summary="删除报价")
async def delete_quote(quote_id: int = Query(..., description="报价ID")):
    await finance_quote_controller.remove(id=quote_id)
    return Success(msg="Deleted Successfully")


@router.get("/site-options", summary="站点选项")
async def list_site_options(quote_type: str = Query("", description="报价类型")):
    q = Q()
    if quote_type:
        q &= Q(quote_type=quote_type)

    rows = await finance_quote_controller.model.filter(q).values("site_a", "region")
    sites = {
        str(row.get("site_a") or row.get("region") or "").strip()
        for row in rows
        if str(row.get("site_a") or row.get("region") or "").strip()
    }
    return Success(data=[{"label": site, "value": site} for site in sorted(sites)])
