from datetime import date
from decimal import Decimal

from fastapi import APIRouter, HTTPException, Query
from fastapi.encoders import jsonable_encoder
from tortoise.exceptions import IntegrityError
from tortoise.transactions import in_transaction

from app.core.dependency import has_admin_role
from app.models.admin import User
from app.models.company import Company
from app.models.customer_center import CrmCustomer, CrmSigningEntity
from app.models.idc import (
    CustomerService,
    IdcAudit,
    IdcBillAllocation,
    IdcBillingRun,
    IdcOrder,
    IdcOrderLine,
)
from app.schemas.base import Success
from app.schemas.idc import (
    AcceptanceInput,
    AccountInput,
    BillDecision,
    BillingInput,
    DecisionInput,
    DeliveryInput,
    EventInput,
    LineUpdate,
    OrderInput,
    QuoteInput,
    TaskInput,
    UsageInput,
)
from app.services import idc_billing as billing
from app.services import idc_workflow as workflow
from app.services.idc_catalog import ACTIONS, CATALOG

router = APIRouter()


def ok(data):
    return Success(data=jsonable_encoder(data, custom_encoder={Decimal: str}))


async def staff():
    user = await workflow.actor()
    if not await workflow.is_staff(user):
        raise HTTPException(403, "该操作需要内部业务权限")
    return user


async def mutate(call):
    try:
        return ok(await call)
    except IntegrityError as exc:
        raise HTTPException(409, "数据已变化、资源已占用或重复提交，请刷新核对") from exc


@router.get("/catalog", summary="IDC产品目录、动态表单和当前权限")
async def catalog():
    user = await workflow.actor()
    all_permissions = user.is_superuser or await has_admin_role(user)
    apis = set()
    if not all_permissions:
        for role in await user.roles:
            apis.update((api.method, api.path) for api in await role.apis)

    def allowed(method, path):
        return all_permissions or (method, "/api/v1/idc" + path) in apis

    return ok(
        {
            "products": list(CATALOG.values()),
            "actions": ACTIONS,
            "staff": await workflow.is_staff(user),
            "capabilities": {
                "accounts": allowed("POST", "/accounts"),
                "create": allowed("POST", "/orders"),
                "edit": allowed("POST", "/lines/{line_id}"),
                "quote": allowed("POST", "/lines/{line_id}/quotes"),
                "decision": allowed("POST", "/lines/{line_id}/decision"),
                "delivery": allowed("POST", "/lines/{line_id}/delivery"),
                "accept": allowed("POST", "/lines/{line_id}/accept"),
                "billing": allowed("POST", "/billing/generate"),
                "audit_bill": allowed("POST", "/billing/{bill_id}/decision"),
                "usage": allowed("POST", "/usage"),
                "events": allowed("POST", "/billing/events"),
            },
        }
    )


@router.get("/accounts", summary="IDC客户与账务映射选项")
async def accounts():
    user = await workflow.actor()
    return ok([await workflow.account_dict(item) for item in await workflow.allowed_accounts(user)])


@router.get("/account-options", summary="IDC账务映射管理候选项")
async def account_options():
    await staff()
    return ok(
        {
            "customers": await CrmCustomer.filter(status=True).values("id", "name", "legal_name", "signing_entity_id"),
            "entities": await CrmSigningEntity.filter(status=True).values("id", "name"),
            "companies": await Company.filter(role=1).values("id", "name"),
            "users": await User.filter(is_active=True).values("id", "username", "alias"),
        }
    )


@router.post("/accounts", summary="保存IDC客户账务及用户授权映射")
async def save_account(payload: AccountInput):
    return await mutate(workflow.save_account(payload, await staff()))


@router.post("/orders", summary="创建结构化IDC工单")
async def create_order(payload: OrderInput):
    return await mutate(workflow.create_order(payload, await workflow.actor()))


@router.get("/orders", summary="IDC工单列表")
async def orders(account_id: int | None = None, page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100)):
    user = await workflow.actor()
    ids = [item.id for item in await workflow.allowed_accounts(user)]
    query = IdcOrder.filter(account_id__in=ids)
    if account_id:
        query = query.filter(account_id=account_id)
    count = await query.count()
    rows = await query.order_by("-id").offset((page - 1) * page_size).limit(page_size)
    data = []
    for row in rows:
        ticket = await row.ticket
        account = await row.account
        data.append(
            {
                **await row.to_dict(),
                "ticket_no": ticket.ticket_no,
                "title": ticket.title,
                "ticket_status": ticket.status,
                "customer_name": (await account.customer).name,
                "stages": await IdcOrderLine.filter(order=row).values_list("stage", flat=True),
            }
        )
    return ok({"items": data, "total": count})


@router.get("/orders/{order_id}", summary="IDC工单产品明细、报价及交付详情")
async def order_detail(order_id: int):
    order = await IdcOrder.get_or_none(id=order_id)
    if not order:
        raise HTTPException(404, "工单不存在")
    return ok(await workflow.order_dict(order, await workflow.actor()))


@router.post("/lines/{line_id}", summary="修改未确认IDC工单明细")
async def update_line(line_id: int, payload: LineUpdate):
    return await mutate(workflow.update_line(line_id, payload, await workflow.actor()))


@router.get("/lines/{line_id}/prices", summary="匹配有效客户价格与标准价格候选")
async def prices(line_id: int):
    return ok(await workflow.price_candidates(line_id, await staff()))


@router.post("/lines/{line_id}/quotes", summary="提交版本化IDC产品报价")
async def quote(line_id: int, payload: QuoteInput):
    return await mutate(workflow.quote_line(line_id, payload, await staff()))


@router.post("/lines/{line_id}/decision", summary="IDC报价审批、客户确认、驳回与取消")
async def decision(line_id: int, payload: DecisionInput):
    user = await staff() if payload.action in {"approve", "reject", "revise"} else await workflow.actor()
    return await mutate(workflow.decide_quote(line_id, payload, user))


@router.post("/tasks/{task_id}", summary="回填IDC交付任务")
async def task(task_id: int, payload: TaskInput):
    return await mutate(workflow.update_task(task_id, payload, await staff()))


@router.post("/lines/{line_id}/delivery", summary="IDC交付参数与资源绑定")
async def delivery(line_id: int, payload: DeliveryInput):
    return await mutate(workflow.save_delivery(line_id, payload, await staff()))


@router.post("/lines/{line_id}/accept", summary="验收IDC产品并生成客户产品与费用版本")
async def acceptance(line_id: int, payload: AcceptanceInput):
    return await mutate(workflow.accept_line(line_id, payload, await workflow.actor()))


@router.post("/lines/{line_id}/support-complete", summary="结束IDC故障或维护明细，不计费")
async def support_complete(line_id: int, payload: TaskInput):
    user = await staff()
    if payload.status != "done":
        raise HTTPException(422, "结束故障或维护时任务状态必须为done")
    async with in_transaction():
        line, order, _ = await workflow.line_access(line_id, user, lock=True)
        if order.action not in workflow.SUPPORT_ACTIONS or line.stage not in {"support", "support_done"}:
            raise HTTPException(409, "不是故障或维护明细")
        line.stage = "support_done"
        line.delivery = {"evidence": payload.evidence, "by": user.id}
        await line.save()
        await workflow.audit(user, "support_completed", "line", line.id, line.delivery)
        await workflow.sync_ticket_status(order)
        return ok(await workflow.order_dict(order, user))


@router.get("/services", summary="客户产品及生效版本")
async def services(account_id: int | None = None, page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100)):
    user = await workflow.actor()
    ids = [item.id for item in await workflow.allowed_accounts(user)]
    query = CustomerService.filter(account_id__in=ids)
    if account_id:
        query = query.filter(account_id=account_id)
    total = await query.count()
    return ok(
        {
            "items": [
                await workflow.service_dict(row)
                for row in await query.order_by("-id").offset((page - 1) * page_size).limit(page_size)
            ],
            "total": total,
        }
    )


@router.post("/resources/reconcile", summary="释放已到期或已终止服务的IDC资源锁")
async def reconcile():
    user = await staff()
    count = 0
    for account in await workflow.allowed_accounts(user):
        async with in_transaction():
            await workflow.account_access(account.id, user, lock=True)
            for service in await CustomerService.filter(account=account, anchor__lte=date.today()):
                count += await workflow.reconcile_service_resources(service.id)
            await workflow.audit(user, "resources_reconciled", "account", account.id, {"released": count})
    return ok({"released": count})


@router.post("/usage", summary="登记核实后的IDC用量结算数据")
async def usage(payload: UsageInput):
    return await mutate(billing.record_usage(payload, await staff()))


@router.post("/billing/generate", summary="预览或生成IDC客户账单，包含NRC与用量")
async def generate(payload: BillingInput):
    return await mutate(billing.generate(payload, await staff()))


@router.post("/billing/events", summary="登记经过授权的账单调整、预付款或贷项")
async def event(payload: EventInput):
    return await mutate(billing.create_event(payload, await staff()))


@router.get("/billing", summary="IDC账单及费用来源")
async def bills(account_id: int | None = None, page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100)):
    user = await workflow.actor()
    ids = [item.id for item in await workflow.allowed_accounts(user)]
    query = IdcBillingRun.filter(account_id__in=ids).exclude(bill_id=None)
    if account_id:
        query = query.filter(account_id=account_id)
    total = await query.count()
    data = []
    for run in await query.order_by("-month", "-id").offset((page - 1) * page_size).limit(page_size):
        bill = await run.bill
        allocations = await IdcBillAllocation.filter(run=run).select_related("item")
        data.append(
            {
                **await bill.to_dict(),
                "account_id": run.account_id,
                "revision": run.revision,
                "items": [
                    {**row.snapshot, "bill_item_id": row.item_id} for row in allocations if row.item.bill_id == bill.id
                ],
            }
        )
    return ok({"items": data, "total": total})


@router.post("/billing/{bill_id}/decision", summary="审核、退回或作废IDC账单草稿")
async def bill_decision(bill_id: int, payload: BillDecision):
    return await mutate(billing.bill_decision(bill_id, payload, await staff()))


@router.get("/audit", summary="IDC工单与客户产品审计记录")
async def audit_list(object_type: str, object_id: int, page: int = Query(1, ge=1)):
    user = await workflow.actor()
    if object_type == "line":
        await workflow.line_access(object_id, user)
    elif object_type == "service":
        service = await CustomerService.get_or_none(id=object_id)
        if not service:
            raise HTTPException(404, "服务不存在")
        await workflow.account_access(service.account_id, user)
    else:
        raise HTTPException(422, "仅支持line或service审计")
    rows = (
        await IdcAudit.filter(object_type=object_type, object_id=object_id)
        .order_by("-id")
        .offset((page - 1) * 50)
        .limit(50)
    )
    return ok([await row.to_dict() for row in rows])
