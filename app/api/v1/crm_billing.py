from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from tortoise.exceptions import IntegrityError
from tortoise.expressions import Q
from tortoise.transactions import in_transaction

from app.core.dependency import AuthControl
from app.models.crm_billing import (
    CrmBillingDocument,
    CrmBillingPayment,
    CrmBillingPlan,
    CrmBillingPlanOrder,
)
from app.models.customer_center import CrmCustomer
from app.schemas.base import Success, SuccessExtra
from app.schemas.crm_billing import BillingAction, BillingGenerate, BillingPaymentIn, BillingReversal, BillingTerms
from app.services.crm_billing import (
    audit,
    check_customer_scope,
    document_dict,
    generate,
    plan_run_date,
    privileged,
    run_plan,
    serial,
    source_orders,
    today,
    totals,
)

router = APIRouter()
CurrentUser = Depends(AuthControl.is_authed)


async def scoped_query(user):
    query = CrmBillingDocument.all()
    if not await privileged(user):
        query = query.filter(bill__customer__sales_owner=user.username)
    return query


async def require_document(document_id, user, lock=False):
    # Lock only the document row: PostgreSQL cannot lock the nullable side of an outer join.
    query = CrmBillingDocument.filter(id=document_id)
    if lock:
        query = query.select_for_update()
    document = await query.first()
    if not document:
        raise HTTPException(404, "账单不存在或不在可访问范围内")
    bill = await document.bill
    customer = await bill.customer
    if not await privileged(user) and customer.sales_owner != user.username:
        raise HTTPException(404, "账单不存在或不在可访问范围内")
    return document


@router.get("/bills", summary="订单账单列表、分币种应收汇总")
async def list_bills(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    keyword: str = Query("", max_length=160),
    customer_id: int | None = Query(None, gt=0),
    status: str = Query(""),
    overdue: bool = False,
    user=CurrentUser,
):
    query = await scoped_query(user)
    if keyword:
        query = query.filter(Q(bill__bill_no__icontains=keyword) | Q(bill__title__icontains=keyword))
    if customer_id:
        query = query.filter(bill__customer_id=customer_id)
    if status:
        query = query.filter(bill__status=status)
    if overdue:
        query = query.filter(bill__status__in=["issued", "partial"], bill__due_date__lt=today())
    count = await query.count()
    rows = await query.order_by("-id").offset((page - 1) * page_size).limit(page_size)
    grouped = {}
    for row in await query.values("bill__currency", "bill__status", "bill__amount", "paid_amount", "bill__due_date"):
        if row["bill__status"] in ("draft", "void"):
            continue
        group = grouped.setdefault(
            row["bill__currency"], {"receivable": Decimal(0), "paid": Decimal(0), "overdue": Decimal(0)}
        )
        group["receivable"] += row["bill__amount"] - row["paid_amount"]
        group["paid"] += row["paid_amount"]
        if row["bill__due_date"] < today():
            group["overdue"] += row["bill__amount"] - row["paid_amount"]
    return SuccessExtra(
        data=[await document_dict(row) for row in rows],
        total=count,
        page=page,
        page_size=page_size,
        summary=serial([{"currency": currency, **amounts} for currency, amounts in grouped.items()]),
    )


@router.post("/preview", summary="预览订单账单，不写入账务数据")
async def preview_bill(payload: BillingGenerate, user=CurrentUser):
    return Success(data=await generate(payload, user, preview=True))


@router.post("/generate", summary="生成幂等账单草稿")
async def generate_bill(payload: BillingGenerate, user=CurrentUser):
    try:
        document = await generate(payload, user)
    except IntegrityError as exc:
        raise HTTPException(409, "出账请求已存在或关联数据发生变化，请刷新") from exc
    return Success(data=await document_dict(document, True), msg="账单草稿已生成")


@router.get("/bills/{document_id}", summary="账单详情、收款与审计记录")
async def get_bill(document_id: int, user=CurrentUser):
    return Success(data=await document_dict(await require_document(document_id, user), True))


@router.put("/bills/{document_id}", summary="调整草稿账期、折扣、税额和汇率")
async def edit_bill(document_id: int, payload: BillingTerms, user=CurrentUser):
    async with in_transaction():
        document = await require_document(document_id, user, True)
        bill = await document.bill
        if bill.status != "draft":
            raise HTTPException(409, "账单已锁定，只能修改草稿")
        before = await document_dict(document)
        before["terms"] = document.settings
        amounts = totals(document.subtotal, payload, bill.currency)
        bill.update_from_dict(
            {
                "title": payload.title,
                "bill_date": payload.bill_date,
                "due_date": payload.due_date,
                "amount": amounts["amount"],
                "remark": payload.remark,
            }
        )
        document.update_from_dict(
            payload.model_dump(
                include={"discount", "adjustment", "tax_rate", "local_currency", "fx_rate", "fx_source", "fx_date"}
            )
        )
        document.tax_amount = amounts["tax_amount"]
        document.local_amount = amounts["local_amount"]
        document.settings = {**document.settings, **payload.model_dump(mode="json")}
        await bill.save()
        await document.save()
        await audit(
            document,
            user,
            "edit",
            before,
            {**await document_dict(document), "terms": payload.model_dump()},
            payload.adjustment_reason,
        )
    return Success(data=await document_dict(document, True))


@router.post("/bills/{document_id}/actions", summary="审核锁定、作废或记录催收")
async def bill_action(document_id: int, payload: BillingAction, user=CurrentUser):
    async with in_transaction():
        document = await require_document(document_id, user, True)
        bill = await document.bill
        before = await document_dict(document)
        if payload.action == "issue":
            if bill.status != "draft":
                raise HTTPException(409, "仅草稿可审核锁定")
            bill.status = "paid" if bill.amount == 0 else "issued"
            bill.is_settled = bill.amount == 0
            document.issued_at = datetime.now(timezone.utc)
        elif payload.action == "void":
            if bill.status == "void" or document.paid_amount > 0:
                raise HTTPException(409, "已作废或尚有收款的账单不能作废；请先冲销收款")
            bill.status = "void"
            bill.is_settled = False
        else:
            if bill.status not in ("issued", "partial") or bill.due_date >= today():
                raise HTTPException(409, "仅逾期未结清账单可登记催收")
            document.reminder_level += 1
        await bill.save()
        await document.save()
        await audit(document, user, payload.action, before, await document_dict(document), payload.comment)
    return Success(data=await document_dict(document, True))


@router.post("/bills/{document_id}/payments", summary="登记收款，支持部分付款与幂等核销")
async def payment(document_id: int, payload: BillingPaymentIn, user=CurrentUser):
    async with in_transaction():
        document = await require_document(document_id, user, True)
        bill = await document.bill
        previous = await CrmBillingPayment.filter(document=document, reference=payload.reference).first()
        if previous:
            same = all(getattr(previous, key) == value for key, value in payload.model_dump().items())
            if not same or previous.reversed:
                raise HTTPException(409, "收款流水号已使用，不可重复登记")
            return Success(data=await document_dict(document, True), msg="该笔收款已登记")
        if bill.status not in ("issued", "partial"):
            raise HTTPException(409, "仅已锁定且未结清账单可收款")
        if payload.currency != bill.currency:
            raise HTTPException(422, "收款币种必须与账单一致，跨币种收款请先完成换汇")
        if payload.payment_date > today():
            raise HTTPException(422, "收款日期不能晚于今天")
        if payload.amount > bill.amount - document.paid_amount:
            raise HTTPException(422, "收款金额不能超过未收金额")
        before = await document_dict(document)
        record = await CrmBillingPayment.create(document=document, operator_id=user.id, **payload.model_dump())
        document.paid_amount += payload.amount
        bill.is_settled = document.paid_amount == bill.amount
        bill.status = "paid" if bill.is_settled else "partial"
        await document.save()
        await bill.save()
        await audit(
            document,
            user,
            "payment",
            before,
            {**await document_dict(document), "payment_id": record.id},
            payload.remark,
        )
    return Success(data=await document_dict(document, True))


@router.post("/bills/{document_id}/payments/{payment_id}/reverse", summary="冲销收款并保留原流水")
async def reverse_payment(document_id: int, payment_id: int, payload: BillingReversal, user=CurrentUser):
    async with in_transaction():
        document = await require_document(document_id, user, True)
        record = await CrmBillingPayment.filter(id=payment_id, document=document).first()
        if not record:
            raise HTTPException(404, "收款记录不存在")
        if record.reversed:
            raise HTTPException(409, "收款已冲销")
        bill = await document.bill
        before = await document_dict(document)
        record.reversed = True
        document.paid_amount -= record.amount
        bill.status = "partial" if document.paid_amount else "issued"
        bill.is_settled = False
        await record.save()
        await document.save()
        await bill.save()
        await audit(
            document,
            user,
            "reverse",
            before,
            {**await document_dict(document), "payment_id": record.id},
            payload.reason,
        )
    return Success(data=await document_dict(document, True))


@router.get("/plans", summary="自动出账计划及失败状态")
async def list_plans(user=CurrentUser):
    query = CrmBillingPlan.all()
    if not await privileged(user):
        query = query.filter(customer__sales_owner=user.username)
    return Success(data=[await row.to_dict() for row in await query.order_by("-id").limit(500)])


@router.post("/plans", summary="建立周期出账计划，冻结订单价格")
async def create_plan(payload: BillingGenerate, user=CurrentUser):
    async with in_transaction() as conn:
        source, _ = await source_orders(payload, user, conn)
        # Validate first period, tax/fx and overlap before enabling automatic billing.
        await generate(payload, user, preview=True)
        existing = await CrmBillingPlanOrder.filter(order_id__in=payload.order_ids, plan__enabled=True).select_related(
            "plan"
        )
        for entry in existing:
            if entry.plan.template.get("currency") == payload.currency:
                raise HTTPException(409, "该订单币种已有启用的自动出账计划，请先停用原计划")
        plan = await CrmBillingPlan.create(
            name=payload.title,
            customer_id=payload.customer_id,
            created_by_id=user.id,
            template=payload.model_dump(mode="json"),
            order_snapshot=source,
            next_period=payload.period_start,
            next_run=plan_run_date(payload),
        )
        for order_id in payload.order_ids:
            await CrmBillingPlanOrder.create(plan=plan, order_id=order_id)
    return Success(data=await plan.to_dict(), msg="自动出账计划已启用")


async def require_plan(plan_id, user):
    plan = await CrmBillingPlan.filter(id=plan_id).first()
    if not plan:
        raise HTTPException(404, "计划不存在")
    await check_customer_scope(await CrmCustomer.get(id=plan.customer_id), user)
    return plan


@router.post("/plans/{plan_id}/stop", summary="停用自动出账计划，保留历史")
async def stop_plan(plan_id: int, user=CurrentUser):
    async with in_transaction():
        plan = await require_plan(plan_id, user)
        await CrmBillingPlan.filter(id=plan.id).select_for_update().first()
        await CrmBillingPlan.filter(id=plan.id).update(enabled=False)
    return Success(msg="计划已停用")


@router.post("/plans/{plan_id}/run", summary="重试已到期的自动出账计划")
async def retry_plan(plan_id: int, user=CurrentUser):
    await require_plan(plan_id, user)
    document = await run_plan(plan_id, force=True)
    return Success(
        data=await document_dict(document) if document else None, msg="检查完成；仅到达出账日的启用计划会生成草稿"
    )
