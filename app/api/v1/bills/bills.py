import logging
import os
import uuid
from calendar import monthrange
from datetime import date, datetime, timedelta
from typing import Any

from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from tortoise.expressions import Q

from app.controllers.bill import bill_controller, bill_item_controller
from app.models.company import BillAuditLog, BillPayment, BillingProductTemplate, BillingSubscription, Company
from app.schemas.base import Success, SuccessExtra
from app.schemas.bills import (
    BillCreate,
    BillGeneratePayload,
    BillPaymentPayload,
    BillStatusPayload,
    BillUpdate,
    BillingSubscriptionPayload,
    BillingTemplatePayload,
)

logger = logging.getLogger(__name__)

router = APIRouter()

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))
UPLOAD_DIR = os.path.join(PROJECT_ROOT, "uploads", "bills")
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
    "status",
}

BILL_STATUS_LABELS = {
    "issued": "已开具",
    "pending_approval": "待审批",
    "pending_send": "待发送",
    "sent": "已发送",
    "paid": "已付款",
    "overdue": "未付款",
}

BILL_TRANSITIONS = {
    "submit": {"from": {"issued", "pending_approval"}, "to": "pending_approval"},
    "approve": {"from": {"pending_approval"}, "to": "pending_send"},
    "reject": {"from": {"pending_approval", "pending_send"}, "to": "pending_approval"},
    "send": {"from": {"pending_send"}, "to": "sent"},
    "mark_paid": {"from": {"issued", "pending_approval", "pending_send", "sent", "overdue"}, "to": "paid"},
    "mark_overdue": {"from": {"issued", "pending_approval", "pending_send", "sent"}, "to": "overdue"},
}


def build_invoice_no(customer_name: str | None, owner: str | None, bill_month) -> str:
    if not customer_name or not owner or not bill_month:
        return ""
    month_text = str(bill_month)
    if len(month_text) < 7:
        return ""
    return f"{customer_name}_INV{owner}_{month_text[2:4]}.{month_text[5:7]}"


def month_start(value: date | None = None) -> date:
    source = value or date.today()
    return date(source.year, source.month, 1)


def month_end(value: date) -> date:
    return date(value.year, value.month, monthrange(value.year, value.month)[1])


def date_overlap(start: date, end: date, left: date | None, right: date | None) -> tuple[date, date] | None:
    effective_start = max(start, left) if left else start
    effective_end = min(end, right) if right else end
    if effective_end < effective_start:
        return None
    return effective_start, effective_end


def sync_settled_status(payload: dict):
    if "unpaid_amount" not in payload:
        return
    try:
        payload["is_settled"] = float(payload.get("unpaid_amount") or 0) <= 0
    except (TypeError, ValueError):
        payload["is_settled"] = False


def sync_local_amount(payload: dict):
    fx_rate = payload.get("fx_rate")
    local_currency = payload.get("local_currency")
    if not fx_rate or not local_currency:
        return
    payload["local_amount"] = round(float(payload.get("total_amount") or 0) * float(fx_rate), 2)


def sync_bill_amounts(payload: dict, items: list):
    item_total = sum((item.nrc_amount or 0) + (item.mrc_amount or 0) for item in items)
    net_amount = float(payload.get("net_amount") or item_total or 0)
    vat_amount = float(payload.get("vat_amount") or 0)
    paid_amount = float(payload.get("paid_amount") or 0)
    if abs(net_amount - item_total) >= 0.01:
        raise HTTPException(status_code=400, detail="Net Amount must equal Invoice Summary NRC + MRC total")
    total_amount = item_total + vat_amount
    payload["net_amount"] = item_total
    payload["total_amount"] = total_amount
    payload["unpaid_amount"] = max(total_amount - paid_amount, 0)
    sync_local_amount(payload)


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
        "status",
    )
    by_currency = {}
    by_status = {}
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
        status = row.get("status") or "issued"
        by_status[status] = by_status.get(status, 0) + 1
    return {
        "count": len(rows),
        "by_currency": sorted(by_currency.values(), key=lambda item: item["currency"]),
        "by_status": [
            {"status": key, "label": BILL_STATUS_LABELS.get(key, key), "count": value}
            for key, value in sorted(by_status.items())
        ],
    }


async def bill_to_dict(obj, include_items: bool = False):
    data = await obj.to_dict()
    data["status_label"] = BILL_STATUS_LABELS.get(data.get("status") or "issued", data.get("status") or "issued")
    if include_items:
        items = await bill_item_controller.model.filter(bill_id=obj.id).order_by("id")
        data["items"] = [await item.to_dict() for item in items]
        data["payments"] = [await item.to_dict() for item in await BillPayment.filter(bill_id=obj.id).order_by("-payment_date", "-id")]
        data["audit_logs"] = [await item.to_dict() for item in await BillAuditLog.filter(bill_id=obj.id).order_by("-created_at", "-id")]
    return data


async def write_bill_audit(bill_id: int, action: str, before: dict | None = None, after: dict | None = None, comment: str = "", operator: str = ""):
    await BillAuditLog.create(
        bill_id=bill_id,
        action=action,
        operator=operator or None,
        comment=comment or None,
        before=before or {},
        after=after or {},
    )


async def replace_bill_items(bill_id: int, items: list):
    await bill_item_controller.model.filter(bill_id=bill_id).delete()
    if not items:
        return
    await bill_item_controller.model.bulk_create(
        [
            bill_item_controller.model(
                bill_id=bill_id,
                service_id=item.service_id or str(index + 1),
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


async def template_to_dict(obj: BillingProductTemplate) -> dict[str, Any]:
    return await obj.to_dict()


async def subscription_to_dict(obj: BillingSubscription) -> dict[str, Any]:
    data = await obj.to_dict()
    company = await Company.get_or_none(id=obj.company_id)
    template = await BillingProductTemplate.get_or_none(id=obj.template_id) if obj.template_id else None
    data["company_name"] = company.name if company else ""
    data["template_name"] = template.name if template else ""
    return data


def template_payload_data(payload: BillingTemplatePayload) -> dict[str, Any]:
    return {
        "name": payload.name.strip(),
        "product_code": payload.product_code.strip() or None,
        "service_type": payload.service_type.strip() or None,
        "billing_rule": payload.billing_rule.strip() or "monthly",
        "unit_price": float(payload.unit_price or 0),
        "currency": payload.currency.strip() or "USD",
        "unit": payload.unit.strip() or None,
        "default_contract_months": int(payload.default_contract_months or 12),
        "status": bool(payload.status),
        "remark": payload.remark.strip() or None,
    }


def clean(value: Any) -> str:
    return str(value or "").strip()


async def subscription_payload_data(payload: BillingSubscriptionPayload) -> dict[str, Any]:
    template = await BillingProductTemplate.get_or_none(id=payload.template_id) if payload.template_id else None
    return {
        "company_id": payload.company_id,
        "template_id": template.id if template else None,
        "product_code": clean((payload.product_code or template.product_code) if template else payload.product_code),
        "service_type": clean((payload.service_type or template.service_type) if template else payload.service_type) or None,
        "service_name": clean((payload.service_name or template.name) if template else payload.service_name) or None,
        "service_location": clean(payload.service_location) or None,
        "billing_start_date": payload.billing_start_date,
        "billing_end_date": payload.billing_end_date,
        "contract_months": int(payload.contract_months or (template.default_contract_months if template else 12)),
        "unit_price": float(payload.unit_price or (template.unit_price if template else 0)),
        "quantity": float(payload.quantity or 1),
        "currency": clean((payload.currency or template.currency) if template else payload.currency) or "USD",
        "unit": clean((payload.unit or template.unit) if template else payload.unit) or None,
        "vat_rate": float(payload.vat_rate or 0),
        "is_active": bool(payload.is_active),
        "last_billed_month": payload.last_billed_month,
        "remark": clean(payload.remark) or None,
    }


async def bill_exists_for_subscription(subscription_id: int, bill_month: date) -> bool:
    marker = f"subscription:{subscription_id}"
    return await bill_item_controller.model.filter(
        service_id=marker,
        bill__bill_month=bill_month,
    ).exists()


def generated_invoice_no(company: Company, owner: str, bill_month: date, sequence: int, location: str = "") -> str:
    customer_code = (company.code or company.name or company.legal_name or "CUSTOMER").replace(" ", "")
    suffix = "".join(ch for ch in (location or "") if ch.isalnum()).upper()[:4] or "AUTO"
    return f"{customer_code}_INV{owner or 'AUTO'}_{bill_month:%y.%m}_{sequence:03d}_{suffix}"


async def build_generated_bill_payload(
    company: Company,
    subscriptions: list[BillingSubscription],
    payload: BillGeneratePayload,
    bill_month: date,
    sequence: int,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    start = month_start(bill_month)
    end = month_end(start)
    days_in_month = (end - start).days + 1
    items = []
    vat_amount = 0.0
    for subscription in subscriptions:
        overlap = date_overlap(start, end, subscription.billing_start_date, subscription.billing_end_date)
        if not overlap:
            continue
        item_start, item_end = overlap
        bill_days = (item_end - item_start).days + 1
        mrc_amount = round(float(subscription.unit_price or 0) * float(subscription.quantity or 1) * bill_days / days_in_month, 2)
        vat_amount += round(mrc_amount * float(subscription.vat_rate or 0), 2)
        items.append(
            {
                "service_id": f"subscription:{subscription.id}",
                "service": subscription.service_type or subscription.product_code,
                "item": subscription.service_name or subscription.product_code,
                "location": subscription.service_location or "",
                "start_date": item_start,
                "end_date": item_end,
                "nrc_amount": 0,
                "mrc_amount": mrc_amount,
                "amount": mrc_amount,
            }
        )
    item_total = round(sum(item["mrc_amount"] for item in items), 2)
    invoice_date = date.today()
    due_days = max(int(payload.due_days or 30), 0)
    bill_data = {
        "company_id": company.id,
        "invoice_no": generated_invoice_no(company, payload.owner, bill_month, sequence, subscriptions[0].service_location if subscriptions else ""),
        "customer_name": company.name or company.legal_name or "",
        "bill_month": start,
        "invoice_date": invoice_date,
        "due_date": invoice_date + timedelta(days=due_days),
        "billing_start_date": start,
        "billing_end_date": end,
        "currency": subscriptions[0].currency if subscriptions else "USD",
        "net_amount": item_total,
        "vat_amount": round(vat_amount, 2),
        "total_amount": round(item_total + vat_amount, 2),
        "paid_amount": 0,
        "unpaid_amount": round(item_total + vat_amount, 2),
        "is_settled": False,
        "payment_voucher_url": "",
        "owner": payload.owner or "",
        "remark": "自动生成账单",
        "bill_type": 1,
        "status": "pending_approval",
        "term": payload.term or f"Net {due_days}",
        "local_currency": payload.local_currency or None,
        "fx_rate": payload.fx_rate,
    }
    sync_local_amount(bill_data)
    return bill_data, items


async def create_bill_items_from_dicts(bill_id: int, items: list[dict[str, Any]]):
    await bill_item_controller.model.bulk_create(
        [
            bill_item_controller.model(
                bill_id=bill_id,
                service_id=item.get("service_id") or str(index + 1),
                service=item.get("service") or "",
                item=item.get("item") or "",
                location=item.get("location") or "",
                start_date=item.get("start_date"),
                end_date=item.get("end_date"),
                nrc_amount=item.get("nrc_amount") or 0,
                mrc_amount=item.get("mrc_amount") or 0,
                amount=item.get("amount") or 0,
            )
            for index, item in enumerate(items)
        ]
    )


@router.get("/automation/options", summary="账单自动化选项")
async def automation_options():
    return Success(
        data={
            "statuses": [{"label": label, "value": value} for value, label in BILL_STATUS_LABELS.items()],
            "templates": [await template_to_dict(item) for item in await BillingProductTemplate.all().order_by("name")],
        }
    )


@router.get("/templates", summary="产品配置模板列表")
async def list_templates(status: bool | None = Query(None, description="状态")):
    q = Q()
    if status is not None:
        q &= Q(status=status)
    rows = await BillingProductTemplate.filter(q).order_by("-status", "name")
    return Success(data=[await template_to_dict(item) for item in rows])


@router.post("/templates", summary="保存产品配置模板")
async def save_template(payload: BillingTemplatePayload):
    data = template_payload_data(payload)
    if not data["name"]:
        raise HTTPException(status_code=400, detail="请填写模板名")
    if payload.id:
        obj = await BillingProductTemplate.get_or_none(id=payload.id)
        if not obj:
            raise HTTPException(status_code=404, detail="产品模板不存在")
        for key, value in data.items():
            setattr(obj, key, value)
        await obj.save()
    else:
        obj = await BillingProductTemplate.create(**data)
    return Success(msg="Saved Successfully", data=await template_to_dict(obj))


@router.delete("/templates/{template_id}", summary="删除产品配置模板")
async def delete_template(template_id: int):
    deleted = await BillingProductTemplate.filter(id=template_id).delete()
    if not deleted:
        raise HTTPException(status_code=404, detail="产品模板不存在")
    return Success(msg="Deleted Successfully")


@router.get("/subscriptions", summary="产品订阅列表")
async def list_subscriptions(
    company_id: int | None = Query(None, description="公司ID"),
    is_active: bool | None = Query(None, description="是否激活"),
):
    q = Q()
    if company_id is not None:
        q &= Q(company_id=company_id)
    if is_active is not None:
        q &= Q(is_active=is_active)
    rows = await BillingSubscription.filter(q).order_by("company_id", "product_code", "id")
    return Success(data=[await subscription_to_dict(item) for item in rows])


@router.post("/subscriptions", summary="保存产品订阅")
async def save_subscription(payload: BillingSubscriptionPayload):
    if not await Company.filter(id=payload.company_id).exists():
        raise HTTPException(status_code=400, detail="客户不存在")
    data = await subscription_payload_data(payload)
    if not data["product_code"]:
        raise HTTPException(status_code=400, detail="请填写产品Code")
    if payload.id:
        obj = await BillingSubscription.get_or_none(id=payload.id)
        if not obj:
            raise HTTPException(status_code=404, detail="产品订阅不存在")
        for key, value in data.items():
            setattr(obj, key, value)
        await obj.save()
    else:
        obj = await BillingSubscription.create(**data)
    return Success(msg="Saved Successfully", data=await subscription_to_dict(obj))


@router.delete("/subscriptions/{subscription_id}", summary="删除产品订阅")
async def delete_subscription(subscription_id: int):
    deleted = await BillingSubscription.filter(id=subscription_id).delete()
    if not deleted:
        raise HTTPException(status_code=404, detail="产品订阅不存在")
    return Success(msg="Deleted Successfully")


@router.post("/generate", summary="自动生成账单")
async def generate_bills(payload: BillGeneratePayload):
    bill_month = month_start(payload.bill_month)
    q = Q(is_active=True)
    if payload.company_id is not None:
        q &= Q(company_id=payload.company_id)
    if payload.subscription_ids:
        q &= Q(id__in=payload.subscription_ids)
    subscriptions = await BillingSubscription.filter(q).order_by("company_id", "currency", "id")

    grouped: dict[tuple[int, str], list[BillingSubscription]] = {}
    skipped = []
    for subscription in subscriptions:
        if await bill_exists_for_subscription(subscription.id, bill_month):
            skipped.append({"subscription_id": subscription.id, "reason": "已生成当月账单"})
            continue
        if not date_overlap(month_start(bill_month), month_end(bill_month), subscription.billing_start_date, subscription.billing_end_date):
            skipped.append({"subscription_id": subscription.id, "reason": "订阅不在本月计费区间"})
            continue
        grouped.setdefault((subscription.company_id, subscription.currency or "USD"), []).append(subscription)

    previews = []
    created = []
    sequence = 1
    for (company_id, _currency), group in grouped.items():
        company = await Company.get(id=company_id)
        bill_data, items = await build_generated_bill_payload(company, group, payload, bill_month, sequence)
        if not items:
            continue
        preview = {**bill_data, "items": items}
        if payload.dry_run:
            previews.append(preview)
        else:
            bill = await bill_controller.model.create(**bill_data)
            await create_bill_items_from_dicts(bill.id, items)
            for subscription in group:
                subscription.last_billed_month = bill_month
                await subscription.save(update_fields=["last_billed_month", "updated_at"])
            await write_bill_audit(bill.id, "auto_generate", after=preview, comment=f"{bill_month:%Y-%m} 自动生成")
            created.append(await bill_to_dict(bill, include_items=True))
        sequence += 1

    return Success(data={"created": created, "previews": previews, "skipped": skipped})


@router.post("/{bill_id}/status", summary="账单状态流转")
async def update_bill_status(bill_id: int, payload: BillStatusPayload):
    bill = await bill_controller.model.get_or_none(id=bill_id)
    if not bill:
        raise HTTPException(status_code=404, detail="账单不存在")
    action = payload.action.strip()
    transition = BILL_TRANSITIONS.get(action)
    if not transition:
        raise HTTPException(status_code=400, detail="不支持的状态动作")
    current_status = bill.status or "issued"
    if current_status not in transition["from"]:
        raise HTTPException(status_code=400, detail=f"当前状态不允许执行 {action}")
    before = await bill_to_dict(bill)
    bill.status = transition["to"]
    bill.approval_comment = payload.comment or bill.approval_comment
    if action == "approve":
        bill.approved_at = datetime.now()
    if action == "send":
        bill.sent_at = datetime.now()
    if action == "mark_paid":
        bill.is_settled = True
        bill.unpaid_amount = 0
    await bill.save()
    after = await bill_to_dict(bill)
    await write_bill_audit(bill.id, action, before=before, after=after, comment=payload.comment, operator=payload.operator)
    return Success(msg="Updated Successfully", data=after)


@router.post("/{bill_id}/payments", summary="登记付款")
async def create_payment(bill_id: int, payload: BillPaymentPayload):
    bill = await bill_controller.model.get_or_none(id=bill_id)
    if not bill:
        raise HTTPException(status_code=404, detail="账单不存在")
    before = await bill_to_dict(bill)
    payment = await BillPayment.create(
        bill_id=bill.id,
        payment_id=payload.payment_id.strip() or f"PAY{datetime.now():%Y%m%d%H%M%S}",
        payment_date=payload.payment_date or date.today(),
        amount=float(payload.amount or 0),
        currency=payload.currency.strip() or bill.currency or "USD",
        method=payload.method.strip() or None,
        fx_rate=payload.fx_rate,
        voucher_url=payload.voucher_url.strip() or None,
        remark=payload.remark.strip() or None,
    )
    bill.paid_amount = float(bill.paid_amount or 0) + float(payment.amount or 0)
    bill.unpaid_amount = max(float(bill.total_amount or 0) - bill.paid_amount, 0)
    bill.is_settled = bill.unpaid_amount <= 0
    if bill.is_settled:
        bill.status = "paid"
    await bill.save()
    after = await bill_to_dict(bill)
    await write_bill_audit(bill.id, "payment", before=before, after=after, comment=payload.remark)
    return Success(msg="Payment Saved", data={"bill": after, "payment": await payment.to_dict()})


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
    status: str = Query("", description="账单状态"),
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
    if status:
        q &= Q(status=status)

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
    payload["status"] = payload.get("status") or "issued"
    sync_bill_amounts(payload, obj_in.items)
    sync_settled_status(payload)
    obj = await bill_controller.create(payload)
    await replace_bill_items(obj.id, obj_in.items)
    await write_bill_audit(obj.id, "create", after=await bill_to_dict(obj, include_items=True))
    return Success(msg="Created Successfully", data=await bill_to_dict(obj, include_items=True))


@router.post("/update", summary="更新账单")
async def update_bill(
    obj_in: BillUpdate,
):
    existing = await bill_controller.get(id=obj_in.id)
    before = await bill_to_dict(existing, include_items=True)
    if (existing.status or "issued") != "pending_approval":
        locked_fields = {"invoice_no", "invoice_date", "company_id", "customer_name"}
        changed_locked = [
            field for field in locked_fields
            if getattr(existing, field, None) != getattr(obj_in, field, None)
        ]
        if changed_locked:
            raise HTTPException(status_code=400, detail="Invoice ID、Invoice Date 和客户主体信息生成后不可直接编辑")
    payload = obj_in.model_dump(exclude_unset=True, exclude={"id", "items"})
    if not payload.get("invoice_no"):
        payload["invoice_no"] = build_invoice_no(
            payload.get("customer_name"), payload.get("owner"), payload.get("bill_month")
        )
    sync_bill_amounts(payload, obj_in.items)
    sync_settled_status(payload)
    obj = await bill_controller.update(id=obj_in.id, obj_in=payload)
    await replace_bill_items(obj.id, obj_in.items)
    await write_bill_audit(obj.id, "update", before=before, after=await bill_to_dict(obj, include_items=True))
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
