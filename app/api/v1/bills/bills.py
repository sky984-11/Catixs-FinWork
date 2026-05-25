import logging
import os
import uuid
from datetime import date, datetime

from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from tortoise.expressions import Q

from app.controllers.bill import bill_controller, bill_item_controller
from app.schemas.base import Success, SuccessExtra
from app.schemas.bills import BillCreate, BillUpdate

logger = logging.getLogger(__name__)

router = APIRouter()

UPLOAD_DIR = "uploads/bills"
os.makedirs(UPLOAD_DIR, exist_ok=True)

SORTABLE_FIELDS = {
    "customer_name",
    "bill_month",
    "is_settled",
    "invoice_no",
    "invoice_date",
    "due_date",
    "billing_start_date",
    "billing_end_date",
    "currency",
    "total_amount",
    "paid_amount",
    "unpaid_amount",
    "owner",
}


def build_invoice_no(customer_name: str | None, owner: str | None, bill_month) -> str:
    if not customer_name or not owner or not bill_month:
        return ""
    month_text = str(bill_month)
    if len(month_text) < 7:
        return ""
    return f"{customer_name}_INV{owner}_{month_text[2:4]}.{month_text[5:7]}"


def sync_settled_status(payload: dict):
    if "unpaid_amount" not in payload:
        return
    try:
        payload["is_settled"] = float(payload.get("unpaid_amount") or 0) <= 0
    except (TypeError, ValueError):
        payload["is_settled"] = False


def sync_bill_amounts(payload: dict, items: list):
    item_total = sum((item.nrc_amount or 0) + (item.mrc_amount or 0) for item in items)
    net_amount = float(payload.get("net_amount") or 0)
    vat_amount = float(payload.get("vat_amount") or 0)
    paid_amount = float(payload.get("paid_amount") or 0)
    if not payload.get("conversion_currency"):
        payload["conversion_currency"] = payload.get("currency") or "USD"
    if not payload.get("exchange_rate"):
        payload["exchange_rate"] = 1
    total_amount = net_amount + vat_amount
    if abs(total_amount - item_total) >= 0.01:
        raise HTTPException(status_code=400, detail="Total Amount must equal Invoice Summary NRC + MRC total")
    payload["net_amount"] = net_amount
    payload["total_amount"] = item_total
    payload["unpaid_amount"] = max(total_amount - paid_amount, 0)


def build_bill_order(sort_field: str = "", sort_order: str = "") -> list[str]:
    if sort_field in SORTABLE_FIELDS and sort_order in {"ascend", "descend"}:
        prefix = "-" if sort_order == "descend" else ""
        return [f"{prefix}{sort_field}", "customer_name", "-bill_month", "-id"]
    return ["customer_name", "-bill_month", "-id"]


async def build_bill_summary(q: Q) -> dict:
    rows = await bill_controller.model.filter(q).values(
        "total_amount",
        "paid_amount",
        "unpaid_amount",
        "currency",
        "conversion_currency",
        "exchange_rate",
    )
    by_currency = {}
    converted_by_currency = {}
    converted_currencies = set()
    converted = {"total": 0, "paid": 0, "unpaid": 0}
    for row in rows:
        currency = row.get("currency") or "-"
        bucket = by_currency.setdefault(currency, {"currency": currency, "total": 0, "paid": 0, "unpaid": 0, "count": 0})
        total_amount = float(row.get("total_amount") or 0)
        paid_amount = float(row.get("paid_amount") or 0)
        unpaid_amount = float(row.get("unpaid_amount") or 0)
        bucket["total"] += total_amount
        bucket["paid"] += paid_amount
        bucket["unpaid"] += unpaid_amount
        bucket["count"] += 1

        conversion_currency = row.get("conversion_currency") or currency
        exchange_rate = float(row.get("exchange_rate") or 1)
        converted_currencies.add(conversion_currency)
        converted_total = total_amount * exchange_rate
        converted_paid = paid_amount * exchange_rate
        converted_unpaid = unpaid_amount * exchange_rate
        converted["total"] += converted_total
        converted["paid"] += converted_paid
        converted["unpaid"] += converted_unpaid
        converted_bucket = converted_by_currency.setdefault(
            conversion_currency,
            {"currency": conversion_currency, "total": 0, "paid": 0, "unpaid": 0, "count": 0},
        )
        converted_bucket["total"] += converted_total
        converted_bucket["paid"] += converted_paid
        converted_bucket["unpaid"] += converted_unpaid
        converted_bucket["count"] += 1
    mixed_conversion_currency = len(converted_currencies) > 1
    return {
        "count": len(rows),
        "by_currency": sorted(by_currency.values(), key=lambda item: item["currency"]),
        "converted": converted,
        "converted_by_currency": sorted(converted_by_currency.values(), key=lambda item: item["currency"]),
        "conversion_currency": next(iter(converted_currencies)) if len(converted_currencies) == 1 else "MULTI",
        "mixed_conversion_currency": mixed_conversion_currency,
    }


async def bill_to_dict(obj, include_items: bool = False):
    data = await obj.to_dict()
    if include_items:
        items = await bill_item_controller.model.filter(bill_id=obj.id).order_by("id")
        data["items"] = [await item.to_dict() for item in items]
    return data


async def replace_bill_items(bill_id: int, items: list):
    await bill_item_controller.model.filter(bill_id=bill_id).delete()
    if not items:
        return
    await bill_item_controller.model.bulk_create(
        [
            bill_item_controller.model(
                bill_id=bill_id,
                service_id=str(index + 1),
                service=item.service or "",
                item=item.item or "",
                location=item.location or "",
                start_date=item.start_date,
                end_date=item.end_date,
                nrc_amount=item.nrc_amount or 0,
                mrc_amount=item.mrc_amount or 0,
                amount=(item.nrc_amount or 0) + (item.mrc_amount or 0),
            )
            for index, item in enumerate(items)
        ]
    )


@router.get("/list", summary="查看账单列表")
async def list_bill(
    page: int = Query(1, description="页码"),
    page_size: int = Query(10, description="每页数量"),
    company_id: int | None = Query(None, description="公司ID"),
    bill_type: int | None = Query(None, description="账单类型(1客户/2供应商)"),
    bill_month: date | None = Query(None, description="账单月份"),
    invoice_no: str = Query("", description="账单编号"),
    customer_name: str = Query("", description="客户/供应商名称"),
    is_settled: bool | None = Query(None, description="是否结清"),
    sort_field: str = Query("", description="排序字段"),
    sort_order: str = Query("", description="排序方向"),
):
    q = Q()
    if company_id is not None:
        q &= Q(company_id=company_id)
    if bill_type is not None:
        q &= Q(bill_type=bill_type)
    if bill_month is not None:
        q &= Q(bill_month=bill_month)
    if invoice_no:
        q &= Q(invoice_no__contains=invoice_no)
    if customer_name:
        q &= Q(customer_name__contains=customer_name)
    if is_settled is not None:
        q &= Q(is_settled=is_settled)

    total, objs = await bill_controller.list(
        page=page,
        page_size=page_size,
        search=q,
        order=build_bill_order(sort_field, sort_order),
    )
    data = [await bill_to_dict(obj) for obj in objs]
    summary = await build_bill_summary(q)
    return SuccessExtra(data=data, total=total, page=page, page_size=page_size, summary=summary)


@router.get("/get", summary="查看账单")
async def get_bill(
    bill_id: int = Query(..., description="账单ID"),
):
    obj = await bill_controller.get(id=bill_id)
    return Success(data=await bill_to_dict(obj, include_items=True))


@router.post("/create", summary="创建账单")
async def create_bill(
    obj_in: BillCreate,
):
    payload = obj_in.model_dump(exclude={"items"})
    if not payload.get("invoice_no"):
        payload["invoice_no"] = build_invoice_no(
            payload.get("customer_name"), payload.get("owner"), payload.get("bill_month")
        )
    sync_bill_amounts(payload, obj_in.items)
    sync_settled_status(payload)
    obj = await bill_controller.create(payload)
    await replace_bill_items(obj.id, obj_in.items)
    return Success(msg="Created Successfully", data=await bill_to_dict(obj, include_items=True))


@router.post("/update", summary="更新账单")
async def update_bill(
    obj_in: BillUpdate,
):
    payload = obj_in.model_dump(exclude_unset=True, exclude={"id", "items"})
    if not payload.get("invoice_no"):
        payload["invoice_no"] = build_invoice_no(
            payload.get("customer_name"), payload.get("owner"), payload.get("bill_month")
        )
    sync_bill_amounts(payload, obj_in.items)
    sync_settled_status(payload)
    obj = await bill_controller.update(id=obj_in.id, obj_in=payload)
    await replace_bill_items(obj.id, obj_in.items)
    return Success(msg="Updated Successfully", data=await bill_to_dict(obj, include_items=True))


@router.delete("/delete", summary="删除账单")
async def delete_bill(
    bill_id: int = Query(..., description="账单ID"),
):
    await bill_controller.remove(id=bill_id)
    return Success(msg="Deleted Successfully")


async def save_bill_file(file: UploadFile):
    file_ext = os.path.splitext(file.filename)[1]
    unique_filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:8]}{file_ext}"
    file_path = os.path.join(UPLOAD_DIR, unique_filename)
    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)
    return f"/uploads/bills/{unique_filename}"


@router.post("/upload_voucher", summary="上传付款凭证")
async def upload_payment_voucher(
    bill_id: int = Query(..., description="账单ID"),
    file: UploadFile = File(..., description="付款凭证"),
):
    if not str(file.content_type or "").startswith("image/"):
        return Success(msg="Only image files are allowed", code=400)

    payment_voucher_url = await save_bill_file(file)
    await bill_controller.update(id=bill_id, obj_in={"payment_voucher_url": payment_voucher_url})
    return Success(msg="Upload Successfully", data={"payment_voucher_url": payment_voucher_url})
