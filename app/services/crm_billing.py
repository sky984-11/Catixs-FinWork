"""Order-based billing. All monetary calculations use Decimal; generated lines are snapshots."""

import hashlib
import json
from calendar import monthrange
from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from uuid import uuid4

from pytz import timezone

from fastapi import HTTPException
from tortoise.transactions import in_transaction
from tortoise.expressions import Q

from app.core.dependency import has_admin_role
from app.models.admin import User
from app.models.crm_billing import (
    CrmBillingAllocation,
    CrmBillingAudit,
    CrmBillingDocument,
    CrmBillingPlan,
)
from app.models.customer_center import CrmCustomer, CrmCustomerBill
from app.models.product_order import ProductOrder, ProductOrderItem
from app.schemas.crm_billing import BillingGenerate

CENT = Decimal("0.01")
MAX_MONEY = Decimal("99999999999999.99")


def today():
    return datetime.now(timezone("Asia/Shanghai")).date()


def money(value):
    result = Decimal(value).quantize(CENT, rounding=ROUND_HALF_UP)
    if abs(result) > MAX_MONEY:
        raise HTTPException(422, "金额超过支持范围")
    return result


def serial(value):
    if isinstance(value, dict):
        return {key: serial(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [serial(item) for item in value]
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Decimal):
        integer, _, fraction = format(value, "f").partition(".")
        return f"{integer}.{fraction.ljust(2, '0')}"
    return value


def add_months(anchor, count):
    year, month = divmod(anchor.year * 12 + anchor.month - 1 + count, 12)
    if not 1 <= year <= 9999:
        raise HTTPException(422, "计费日期超出范围")
    return date(year, month + 1, min(anchor.day, monthrange(year, month + 1)[1]))


def period_end(payload):
    if payload.calendar_mode == "calendar":
        return add_months(payload.period_start, payload.months) - timedelta(days=1)
    offset = (payload.period_start.year - payload.service_start.year) * 12
    offset += payload.period_start.month - payload.service_start.month
    if offset < 0 or add_months(payload.service_start, offset) != payload.period_start:
        raise HTTPException(422, "周年日账期必须与服务开始日对齐")
    return add_months(payload.service_start, offset + payload.months) - timedelta(days=1)


def month_factor(start, end, mode, anchor):
    """Inclusive days, calendar months or service-anniversary months, including leap years."""
    cursor = start
    result = Decimal(0)
    while cursor <= end:
        if mode == "calendar":
            lower = cursor.replace(day=1)
            upper = add_months(lower, 1)
        else:
            offset = (cursor.year - anchor.year) * 12 + cursor.month - anchor.month
            if add_months(anchor, offset) > cursor:
                offset -= 1
            lower, upper = add_months(anchor, offset), add_months(anchor, offset + 1)
        stop = min(end + timedelta(days=1), upper)
        result += Decimal((stop - cursor).days) / Decimal((upper - lower).days)
        cursor = stop
    return result


async def privileged(user):
    # Finance staff still need explicit route permissions; this only defines data scope.
    return (
        user.is_superuser
        or await has_admin_role(user)
        or await user.roles.filter(name__in=["财务", "finance"]).exists()
    )


async def check_customer_scope(customer, user):
    if not await privileged(user) and customer.sales_owner != user.username:
        raise HTTPException(403, "无权访问其他销售负责的客户账单")


async def audit(document, user, action, before=None, after=None, comment=""):
    await CrmBillingAudit.create(
        document_id=document.id,
        action=action,
        operator_id=user.id,
        operator_name=user.username,
        before=serial(before or {}),
        after=serial(after or {}),
        comment=comment,
    )


def totals(subtotal, terms, currency):
    if terms.local_currency == currency and terms.fx_rate != 1:
        raise HTTPException(422, "同币种汇率必须为 1")
    net = money(subtotal - terms.discount + terms.adjustment)
    if net < 0:
        raise HTTPException(422, "折扣或变更差额不能使应收金额为负")
    tax = money(net * terms.tax_rate / 100)
    amount = money(net + tax)
    return {"net_amount": net, "tax_amount": tax, "amount": amount, "local_amount": money(amount * terms.fx_rate)}


async def source_orders(payload, user, conn, frozen_source=None):
    orders = await ProductOrder.filter(id__in=payload.order_ids).using_db(conn).order_by("id").select_for_update()
    if len(orders) != len(payload.order_ids) or any(order.customer_id != payload.customer_id for order in orders):
        raise HTTPException(422, "所选订单必须全部属于当前客户")
    customer = await CrmCustomer.filter(id=payload.customer_id).using_db(conn).select_for_update().first()
    if not customer or not customer.status or customer.lifecycle == "terminated":
        raise HTTPException(422, "请选择有效客户")
    await check_customer_scope(customer, user)
    result = []
    for order in orders:
        if frozen_source is not None:
            result.extend(row for row in frozen_source if row["order_id"] == order.id)
            continue
        items = await ProductOrderItem.filter(order_id=order.id).using_db(conn).prefetch_related("product")
        matched = False
        for item in items:
            if not item.currency or item.mrc is None or item.nrc is None:
                raise HTTPException(422, f"订单 {order.name} 存在未定价明细，请先补齐价格")
            if item.currency != payload.currency:
                continue
            matched = True
            result.append(
                serial(
                    {
                        "order_id": order.id,
                        "order_no": order.order_no,
                        "order_name": order.name,
                        "product_id": item.product_id,
                        "product_name": item.product_name_snapshot or item.product.name,
                        "variant_id": item.variant_id,
                        "variant_name": item.variant_name,
                        "spec_snapshot": item.spec_snapshot,
                        "quantity": item.quantity,
                        "mrc": item.mrc,
                        "nrc": item.nrc,
                        "currency": item.currency,
                        "price_version_id": item.price_version_id,
                        "price_version_number": item.price_version_number,
                        "period_months": item.period_months,
                    }
                )
            )
        if not matched:
            raise HTTPException(422, f"订单 {order.name} 没有 {payload.currency} 明细，请按币种分别出账")
    entity = await customer.signing_entity if customer.signing_entity_id else None
    snapshot = {
        "customer_id": customer.id,
        "name": customer.legal_name or customer.name,
        "short_name": customer.name,
        "customer_code": customer.customer_code,
        "address": customer.address,
        "invoice_info": customer.invoice_info,
        "signing_entity": (entity.legal_name or entity.name) if entity else "",
        "signing_entity_id": customer.signing_entity_id,
    }
    return result, snapshot


async def calculate(payload, source):
    end = period_end(payload)
    start = max(payload.period_start, payload.service_start)
    actual_end = min(end, payload.service_end or end)
    if start > actual_end:
        raise HTTPException(422, "账期与服务有效期没有交集")
    allocations = (
        await CrmBillingAllocation.filter(order_id__in=payload.order_ids, currency=payload.currency)
        .exclude(document__bill__status="void")
        .select_related("document__bill")
    )
    for entry in allocations:
        if entry.period_start <= actual_end and entry.period_end >= start:
            raise HTTPException(409, f"该订单账期与账单 {entry.document.bill.bill_no} 重叠，请勿重复出账")
    charged_nrc = {
        (row["order_id"], row["product_id"], row.get("variant_id"))
        for entry in allocations
        if entry.includes_nrc
        for row in entry.document.lines
        if row["order_id"] == entry.order_id and row.get("nrc_charged")
    }
    factor = month_factor(start, actual_end, payload.calendar_mode, payload.service_start)
    lines = []
    for entry in source:
        row = dict(entry)
        recurring = money(Decimal(row["mrc"]) * row["quantity"] * factor)
        charge_nrc = (
            payload.include_nrc and (row["order_id"], row["product_id"], row.get("variant_id")) not in charged_nrc
        )
        nrc = money(Decimal(row["nrc"]) * row["quantity"]) if charge_nrc else Decimal("0.00")
        row.update(
            serial(
                {
                    "period_start": start,
                    "period_end": actual_end,
                    "month_factor": factor,
                    "mrc_amount": recurring,
                    "nrc_amount": nrc,
                    "nrc_charged": charge_nrc,
                    "amount": money(recurring + nrc),
                }
            )
        )
        lines.append(row)
    subtotal = money(sum((Decimal(row["amount"]) for row in lines), Decimal(0)))
    return {
        "lines": lines,
        "subtotal": subtotal,
        "period_start": start,
        "period_end": actual_end,
        "cycle_end": end,
        **totals(subtotal, payload, payload.currency),
    }


async def generate(payload, user, preview=False, frozen_source=None):
    fingerprint = hashlib.sha256(payload.model_dump_json(exclude={"request_key", "preview_token"}).encode()).hexdigest()
    async with in_transaction() as conn:
        # All competing generation paths use the same order locks, including automatic plans.
        source, customer = await source_orders(payload, user, conn, frozen_source)
        existing = await CrmBillingDocument.filter(request_key=payload.request_key).first()
        if existing and not preview:
            if existing.request_hash != fingerprint:
                raise HTTPException(409, "出账请求编号已被其他内容使用，请重新预览")
            return existing
        result = await calculate(payload, source)
        token = hashlib.sha256(
            json.dumps(serial({"result": result, "customer": customer, "terms": fingerprint}), sort_keys=True).encode()
        ).hexdigest()
        if payload.preview_token and payload.preview_token != token:
            raise HTTPException(409, "订单价格或客户资料已变化，请重新预览后出账")
        if preview:
            return serial({**result, "customer": customer, "currency": payload.currency, "preview_token": token})
        bill = await CrmCustomerBill.create(
            customer_id=payload.customer_id,
            bill_no=f"INV-{today():%Y%m%d}-{uuid4().hex[:12].upper()}",
            title=payload.title,
            status="draft",
            amount=result["amount"],
            currency=payload.currency,
            bill_date=payload.bill_date,
            due_date=payload.due_date,
            remark=payload.remark,
        )
        document = await CrmBillingDocument.create(
            bill=bill,
            request_key=payload.request_key,
            request_hash=fingerprint,
            created_by_id=user.id,
            customer_snapshot=customer,
            lines=result["lines"],
            settings=payload.model_dump(mode="json"),
            period_start=result["period_start"],
            period_end=result["period_end"],
            subtotal=result["subtotal"],
            discount=payload.discount,
            adjustment=payload.adjustment,
            tax_rate=payload.tax_rate,
            tax_amount=result["tax_amount"],
            local_currency=payload.local_currency,
            fx_rate=payload.fx_rate,
            fx_source=payload.fx_source,
            fx_date=payload.fx_date,
            local_amount=result["local_amount"],
        )
        for order_id in sorted(payload.order_ids):
            await CrmBillingAllocation.create(
                document=document,
                order_id=order_id,
                currency=payload.currency,
                period_start=result["period_start"],
                period_end=result["period_end"],
                includes_nrc=any(row["nrc_charged"] for row in result["lines"] if row["order_id"] == order_id),
            )
        await audit(document, user, "generate", after={"bill_no": bill.bill_no, "amount": bill.amount})
        return document


async def document_dict(document, detail=False):
    bill = await document.bill
    data = await bill.to_dict()
    outstanding = max(Decimal(0), bill.amount - document.paid_amount)
    overdue = max(0, (today() - bill.due_date).days) if bill.status in ("issued", "partial") and outstanding > 0 else 0
    data.update(
        {
            "id": document.id,
            "bill_id": bill.id,
            "customer_name": document.customer_snapshot.get("name", ""),
            "signing_entity_name": document.customer_snapshot.get("signing_entity", ""),
            "period_start": document.period_start,
            "period_end": document.period_end,
            "paid_amount": document.paid_amount,
            "outstanding": outstanding if bill.status != "void" else Decimal(0),
            "overdue_days": overdue,
            "reminder_level": document.reminder_level,
        }
    )
    if detail:
        data.update(
            {
                "lines": document.lines,
                "customer_snapshot": document.customer_snapshot,
                "settings": document.settings,
                "subtotal": document.subtotal,
                "discount": document.discount,
                "adjustment": document.adjustment,
                "tax_rate": document.tax_rate,
                "tax_amount": document.tax_amount,
                "local_currency": document.local_currency,
                "local_amount": document.local_amount,
                "fx_rate": document.fx_rate,
                "fx_source": document.fx_source,
                "fx_date": document.fx_date,
                "issued_at": document.issued_at,
                "payments": [await row.to_dict() for row in await document.payments.all().order_by("-id")],
                "audits": [await row.to_dict() for row in await document.audits.all().order_by("-id")],
            }
        )
    return serial(data)


def plan_run_date(payload):
    return payload.period_start if payload.payment_timing == "prepaid" else period_end(payload) + timedelta(days=1)


async def run_plan(plan_id, force=False):
    """Plan lock + order locks + unique request key make restarts and multiple workers safe."""
    async with in_transaction() as conn:
        plan = await CrmBillingPlan.filter(id=plan_id).using_db(conn).select_for_update().first()
        if not plan or not plan.enabled or plan.next_run > today() or (plan.last_attempt == today() and not force):
            return None
        user = await User.filter(id=plan.created_by_id, is_active=True).first()
        if not user:
            raise HTTPException(409, "计划创建者已停用，请停用并重新建立计划")
        if not user.is_superuser and not await has_admin_role(user):
            if not await user.roles.filter(apis__path="/api/v1/crm-billing/plans", apis__method="POST").exists():
                raise HTTPException(403, "计划创建者已无自动出账权限")
        values = dict(plan.template)
        values["preview_token"] = None
        values.update(period_start=plan.next_period.isoformat(), request_key=f"PLAN-{plan.id}-{plan.next_period}")
        original = BillingGenerate.model_validate(plan.template)
        due_days = (original.due_date - original.bill_date).days
        values.update(
            bill_date=plan.next_run.isoformat(), due_date=(plan.next_run + timedelta(days=due_days)).isoformat()
        )
        payload = BillingGenerate.model_validate(values)
        document = await generate(payload, user, frozen_source=plan.order_snapshot)
        await audit(document, user, "scheduled", after={"plan_id": plan.id})
        plan.next_period = period_end(payload) + timedelta(days=1)
        next_payload = payload.model_copy(update={"period_start": plan.next_period})
        plan.next_run = plan_run_date(next_payload)
        if payload.service_end and plan.next_period > payload.service_end:
            plan.enabled = False
        plan.last_error = ""
        plan.last_attempt = None  # Multiple overdue cycles catch up, at most one cycle per plan per scan.
        await plan.save(using_db=conn)
        return document


async def run_due_plans():
    plans = (
        await CrmBillingPlan.filter(
            Q(last_attempt=None) | ~Q(last_attempt=today()), enabled=True, next_run__lte=today()
        )
        .order_by("next_run", "id")
        .limit(50)
    )
    for plan in plans:
        if plan.last_attempt == today():
            continue
        try:
            await run_plan(plan.id)
        except Exception as exc:
            # Keep a safe business error for retry; never serialize connection details or secrets.
            message = str(exc.detail) if isinstance(exc, HTTPException) else "自动出账失败，请检查计划和服务日志后重试"
            await CrmBillingPlan.filter(id=plan.id, next_period=plan.next_period, enabled=True).update(
                last_attempt=today(), last_error=message[:500]
            )
