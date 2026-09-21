"""Decimal billing with immutable allocations and serialized, repeatable billing runs."""

import calendar
from datetime import date, datetime, timedelta
from decimal import ROUND_CEILING, ROUND_HALF_UP, Decimal

from fastapi import HTTPException
from fastapi.encoders import jsonable_encoder
from tortoise.transactions import in_transaction

from app.models.company import Bill, BillAuditLog, BillItem
from app.models.idc import (
    CustomerService,
    IdcBillAllocation,
    IdcBillingEvent,
    IdcBillingRun,
    IdcUsage,
    ServiceCharge,
    ServiceVersion,
)
from app.services.idc_workflow import account_access, audit


def money(value, currency="USD"):
    quantum = Decimal("1") if currency == "JPY" else Decimal("0.01")
    return Decimal(value).quantize(quantum, rounding=ROUND_HALF_UP)


def add_months(value, months):
    index = value.year * 12 + value.month - 1 + months
    year, month = divmod(index, 12)
    return date(year, month + 1, min(value.day, calendar.monthrange(year, month + 1)[1]))


def cycles(anchor, start, end, interval):
    anchor = anchor.replace(day=1)
    difference = (start.year - anchor.year) * 12 + start.month - anchor.month
    current = add_months(anchor, max(0, difference // interval) * interval)
    while current < end:
        following = add_months(current, interval)
        yield current, following
        current = following


async def ensure_unbilled_change(service_id, starts_on):
    for allocation in await IdcBillAllocation.all().select_related("item__bill"):
        snapshot = allocation.snapshot
        if snapshot.get("service_id") != service_id or snapshot.get("kind") == "nrc":
            continue
        if snapshot.get("ends_before", "") > starts_on.isoformat() and allocation.item.bill.status != "void":
            raise HTTPException(409, "变更区间已有账单，请先作废未审核草稿；已审核费用用调整项处理")


async def record_usage(payload, user):
    charge = await ServiceCharge.get_or_none(id=payload.charge_id)
    if not charge or charge.kind != "usage" or charge.included:
        raise HTTPException(422, "费用项不是独立用量费用")
    version = await charge.version
    service = await version.service
    async with in_transaction():
        await account_access(service.account_id, user, lock=True)
        if payload.ends_before <= payload.starts_on or payload.starts_on < version.starts_on:
            raise HTTPException(422, "用量区间无效")
        if version.ends_before and payload.ends_before > version.ends_before:
            raise HTTPException(422, "用量区间跨越服务版本")
        for allocation in await IdcBillAllocation.exclude(item__bill__status="void"):
            if allocation.snapshot.get("charge_id") == charge.id:
                if (
                    allocation.snapshot.get("starts_on") < payload.ends_before.isoformat()
                    and allocation.snapshot.get("ends_before") > payload.starts_on.isoformat()
                ):
                    raise HTTPException(409, "该区间已有账单，不能覆盖原计量")
        overlapping = await IdcUsage.filter(
            charge=charge, starts_on__lt=payload.ends_before, ends_before__gt=payload.starts_on
        )
        if any(row.starts_on != payload.starts_on or row.ends_before != payload.ends_before for row in overlapping):
            raise HTTPException(409, "用量区间重叠")
        values = payload.model_dump(exclude={"charge_id"})
        values["recorded_by"] = user.id
        if overlapping:
            row = overlapping[0]
            await row.update_from_dict(values).save()
        else:
            row = await IdcUsage.create(charge=charge, **values)
        await audit(
            user, "usage_recorded", "service", service.id, {"usage_id": row.id, **payload.model_dump(mode="json")}
        )
        return jsonable_encoder(await row.to_dict(), custom_encoder={Decimal: str})


def usage_quantity(charge, quantity):
    rule = charge.rule
    value = max(Decimal("0"), quantity - Decimal(rule.get("allowance", "0")))
    if rule.get("usage_mode") == "hours" and value:
        step = Decimal(rule.get("step", "1"))
        value = (value / step).quantize(Decimal("1"), rounding=ROUND_CEILING) * step
    return max(value, Decimal(rule.get("minimum", "0")))


async def calculate(account, month):
    start, end = month.replace(day=1), add_months(month.replace(day=1), 1)
    items, errors = [], []
    services = await CustomerService.filter(account=account)
    for service in services:
        for version in await ServiceVersion.filter(service=service).order_by("starts_on"):
            quote = await version.quote
            for charge in await ServiceCharge.filter(version=version):
                if charge.included:
                    continue
                if version.state == "terminated" and charge.kind != "nrc":
                    continue
                base = {
                    "service_id": service.id,
                    "service_no": service.service_no,
                    "service_name": service.name,
                    "product_code": service.product_code,
                    "charge_id": charge.id,
                    "charge_name": charge.name,
                    "quote_id": quote.id,
                    "quote_version": quote.version,
                    "source_line_id": version.source_line_id,
                    "kind": charge.kind,
                    "currency": quote.currency,
                    "tax_rate": str(charge.tax_rate),
                    "unit_price": str(charge.unit_price),
                    "quantity": str(version.quantity),
                    "rule": charge.rule,
                    "payment_days": quote.terms.get("payment_days", 15),
                }
                if charge.kind == "nrc":
                    if start <= version.starts_on < end:
                        net = money(charge.unit_price * version.quantity, quote.currency)
                        items.append(
                            {
                                **base,
                                "key": f"nrc:{charge.id}",
                                "starts_on": version.starts_on.isoformat(),
                                "ends_before": (version.starts_on + timedelta(days=1)).isoformat(),
                                "amount": net,
                                "tax": money(net * charge.tax_rate, quote.currency),
                            }
                        )
                    continue
                interval = charge.rule.get("interval", 1)
                # Only cycles whose invoice trigger falls in this requested month are considered.
                lookback = add_months(start, -interval)
                for cycle_start, cycle_end in cycles(
                    service.anchor, max(service.anchor.replace(day=1), lookback), end, interval
                ):
                    due = (
                        cycle_start
                        if charge.rule.get("timing") == "advance" and charge.kind == "recurring"
                        else cycle_end - timedelta(days=1)
                    )
                    # A partial first cycle cannot be invoiced before its service has a start date.
                    due = max(due, version.starts_on)
                    if not start <= due < end:
                        continue
                    slice_start = max(cycle_start, version.starts_on)
                    slice_end = min(cycle_end, version.ends_before or cycle_end)
                    if slice_end <= slice_start:
                        continue
                    metadata = {
                        "starts_on": slice_start.isoformat(),
                        "ends_before": slice_end.isoformat(),
                        "cycle_start": cycle_start.isoformat(),
                        "cycle_end": cycle_end.isoformat(),
                    }
                    net = charge.unit_price * version.quantity
                    if charge.kind == "usage":
                        records = await IdcUsage.filter(
                            charge=charge, starts_on__gte=slice_start, ends_before__lte=slice_end
                        ).order_by("starts_on")
                        cursor = slice_start
                        for row in records:
                            if row.starts_on != cursor:
                                break
                            cursor = row.ends_before
                        if not records or cursor != slice_end:
                            errors.append(
                                {
                                    "service_id": service.id,
                                    "charge_id": charge.id,
                                    **metadata,
                                    "reason": "缺少完整且连续的已核实用量；不能按0计费",
                                }
                            )
                            continue
                        if charge.rule.get("usage_mode") == "95th" and len(records) != 1:
                            errors.append(
                                {
                                    "service_id": service.id,
                                    "charge_id": charge.id,
                                    **metadata,
                                    "reason": "95计量必须提交整个结算区间的单一核实结果，不能累加分段百分位",
                                }
                            )
                            continue
                        quantity = usage_quantity(charge, sum((row.quantity for row in records), Decimal("0")))
                        net = charge.unit_price * quantity
                        cap = charge.rule.get("cap")
                        if cap is not None:
                            net = min(net, Decimal(cap))
                        metadata.update({"meter_quantity": str(quantity), "usage_ids": [row.id for row in records]})
                    else:
                        proration = charge.rule.get("proration", "actual_days")
                        if proration == "actual_days":
                            net *= Decimal((slice_end - slice_start).days) / Decimal((cycle_end - cycle_start).days)
                        elif proration == "30_days":
                            net *= min(Decimal("1"), Decimal((slice_end - slice_start).days) / Decimal(30 * interval))
                    net = money(net, quote.currency)
                    items.append(
                        {
                            **base,
                            **metadata,
                            "key": f"charge:{charge.id}:{slice_start}:{slice_end}",
                            "amount": net,
                            "tax": money(net * charge.tax_rate, quote.currency),
                        }
                    )
    for event in await IdcBillingEvent.filter(account=account, due_on__gte=start, due_on__lt=end):
        items.append(
            {
                "key": f"event:{event.id}",
                "event_id": event.id,
                "service_id": event.service_id,
                "service_no": "",
                "service_name": event.description,
                "charge_name": event.description,
                "kind": event.kind,
                "currency": event.currency,
                "amount": event.amount,
                "tax": event.tax,
                "starts_on": event.due_on.isoformat(),
                "ends_before": (event.due_on + timedelta(days=1)).isoformat(),
                "source": event.source,
                "payment_days": 15,
            }
        )
    return items, errors


async def generate(payload, user):
    month = payload.month.replace(day=1)
    async with in_transaction():
        account = await account_access(payload.account_id, user, lock=True)
        items, errors = await calculate(account, month)
        if errors:
            return {"blocked": errors, "previews": [], "created": [], "skipped": []}
        grouped, skipped = {}, []
        for item in items:
            existing = await IdcBillAllocation.get_or_none(allocation_key=item["key"])
            if existing:
                run = await existing.run
                bill = await run.bill
                if run.month != month or bill.status not in {"pending_approval", "rejected"}:
                    skipped.append({"key": item["key"], "bill_id": bill.id, "reason": "已生成"})
                    continue
            grouped.setdefault(item["currency"], []).append(item)
        previews, created = [], []
        customer, entity = await account.customer, await account.signing_entity
        for currency, rows in grouped.items():
            net = sum((row["amount"] for row in rows), Decimal("0"))
            tax = sum((row["tax"] for row in rows), Decimal("0"))
            preview = {
                "account_id": account.id,
                "customer_name": customer.legal_name or customer.name,
                "signing_entity_name": entity.legal_name or entity.name,
                "currency": currency,
                "month": str(month),
                "net_amount": str(net),
                "vat_amount": str(tax),
                "total_amount": str(net + tax),
                "items": rows,
            }
            run = await IdcBillingRun.get_or_none(account=account, month=month, currency=currency)
            if run and run.bill_id and (await run.bill).status not in {"pending_approval", "rejected", "void"}:
                raise HTTPException(409, "当期账单已锁定；新增或迟到费用请登记下期调整项")
            previews.append(preview)
            if payload.dry_run:
                continue
            if not run:
                run = await IdcBillingRun.create(account=account, month=month, currency=currency)
            bill = await run.bill if run.bill_id else None
            if bill and bill.status != "void":
                item_ids = await BillItem.filter(bill=bill).values_list("id", flat=True)
                await IdcBillAllocation.filter(run=run, item_id__in=item_ids).delete()
                await BillItem.filter(bill=bill).delete()
                run.revision += 1
            else:
                if bill:
                    run.revision += 1
                bill = await Bill.create(
                    company_id=account.company_id,
                    bill_type=1,
                    source="idc",
                    source_record_id=str(run.id),
                    invoice_no=f"IDC-{month:%Y%m}-{run.id}-{run.revision}",
                    customer_name=customer.legal_name or customer.name,
                    bill_month=month,
                    currency=currency,
                )
                run.bill_id = bill.id
            bill.status = "pending_approval"
            bill.net_amount, bill.vat_amount, bill.total_amount = float(net), float(tax), float(net + tax)
            bill.paid_amount, bill.unpaid_amount, bill.is_settled = 0, float(net + tax), False
            bill.invoice_date = date.today()
            bill.due_date = date.today() + timedelta(days=min(row["payment_days"] for row in rows))
            bill.billing_start_date, bill.billing_end_date = month, add_months(month, 1) - timedelta(days=1)
            bill.remark = f"签约主体：{entity.legal_name or entity.name}；IDC账单版本{run.revision}"
            await bill.save()
            await run.save()
            for row in rows:
                item = await BillItem.create(
                    bill=bill,
                    service_id=row.get("service_no") or row["key"],
                    service=str(row.get("product_code", row["kind"]))[:100],
                    item=row["charge_name"][:100],
                    start_date=date.fromisoformat(row["starts_on"]),
                    end_date=date.fromisoformat(row["ends_before"]) - timedelta(days=1),
                    nrc_amount=float(row["amount"]) if row["kind"] == "nrc" else 0,
                    mrc_amount=float(row["amount"]) if row["kind"] == "recurring" else 0,
                    amount=float(row["amount"]),
                )
                snapshot = jsonable_encoder(row, custom_encoder={Decimal: str})
                await IdcBillAllocation.create(
                    run=run,
                    item=item,
                    allocation_key=row["key"],
                    amount=row["amount"],
                    tax=row["tax"],
                    snapshot=snapshot,
                )
            await BillAuditLog.create(
                bill=bill,
                action="idc_generate",
                operator=str(user.id),
                after=jsonable_encoder(preview, custom_encoder={Decimal: str}),
            )
            await audit(user, "bill_generated", "bill", bill.id, {"run": run.id, "revision": run.revision})
            created.append({"bill_id": bill.id, "invoice_no": bill.invoice_no, "total": str(net + tax)})
        return jsonable_encoder(
            {"blocked": [], "previews": previews, "created": created, "skipped": skipped}, custom_encoder={Decimal: str}
        )


async def bill_decision(bill_id, payload, user):
    async with in_transaction():
        run = await IdcBillingRun.get_or_none(bill_id=bill_id)
        if not run:
            raise HTTPException(404, "IDC账单不存在")
        await account_access(run.account_id, user, lock=True)
        bill = await Bill.filter(id=bill_id).select_for_update().get()
        if payload.action == "approve":
            if bill.status != "pending_approval":
                raise HTTPException(409, "仅待审核账单可批准")
            bill.status = "issued"
            bill.approved_at = datetime.now()
        elif payload.action == "reject":
            if bill.status != "pending_approval":
                raise HTTPException(409, "仅待审核账单可退回")
            bill.status = "rejected"
        else:
            if bill.status not in {"pending_approval", "rejected"} or bill.paid_amount:
                raise HTTPException(409, "仅未审核未收款草稿可作废；已开账单请创建调整或贷项")
            bill.status = "void"
            # Preserve the old allocation audit trail while freeing the idempotency keys for regeneration.
            for row in await IdcBillAllocation.filter(run=run, item__bill_id=bill.id):
                row.allocation_key = f"void:{bill.id}:{row.id}:{row.allocation_key}"[:220]
                await row.save(update_fields=["allocation_key", "updated_at"])
        bill.approval_comment = payload.comment
        await bill.save()
        await audit(user, f"bill_{payload.action}", "bill", bill.id, {"comment": payload.comment})
        return jsonable_encoder(await bill.to_dict(), custom_encoder={Decimal: str})


async def create_event(payload, user):
    async with in_transaction():
        await account_access(payload.account_id, user, lock=True)
        if (
            payload.service_id
            and not await CustomerService.filter(id=payload.service_id, account_id=payload.account_id).exists()
        ):
            raise HTTPException(422, "客户产品归属不匹配")
        source = None
        if payload.source_bill_id:
            run = await IdcBillingRun.get_or_none(bill_id=payload.source_bill_id, account_id=payload.account_id)
            source = await Bill.get_or_none(id=payload.source_bill_id)
            if (
                not run
                or not source
                or source.currency != payload.currency
                or source.status not in {"issued", "sent", "paid", "overdue"}
            ):
                raise HTTPException(422, "原账单客户、币种或状态无效")
        if payload.kind in {"credit", "adjustment"} and not source:
            raise HTTPException(422, "调整或贷项须关联已审核原账单")
        if payload.kind == "credit" and (payload.amount > 0 or payload.tax > 0):
            raise HTTPException(422, "贷项金额及税额须不大于0")
        if payload.kind == "prepayment" and payload.amount <= 0:
            raise HTTPException(422, "预付款金额必须大于0")
        key = "manual:" + payload.request_key
        existing = await IdcBillingEvent.get_or_none(event_key=key)
        if existing:
            if existing.account_id != payload.account_id:
                raise HTTPException(409, "请求标识已使用")
            return jsonable_encoder(await existing.to_dict(), custom_encoder={Decimal: str})
        if payload.kind == "credit":
            prior = [
                event
                for event in await IdcBillingEvent.filter(account_id=payload.account_id, kind="credit")
                if event.source.get("bill_id") == source.id
            ]
            net_credited = -sum((event.amount for event in prior), payload.amount)
            tax_credited = -sum((event.tax for event in prior), payload.tax)
            if net_credited > Decimal(str(source.net_amount)) or tax_credited > Decimal(str(source.vat_amount)):
                raise HTTPException(409, "累计贷项超过原账单未税金额或税额，请核对已登记抵扣")
        event = await IdcBillingEvent.create(
            event_key=key,
            **payload.model_dump(exclude={"request_key", "source_bill_id"}),
            source={"bill_id": payload.source_bill_id, "approved_by": user.id},
        )
        await audit(
            user,
            "billing_event_created",
            "account",
            payload.account_id,
            {"event_id": event.id, **payload.model_dump(mode="json")},
        )
        return jsonable_encoder(await event.to_dict(), custom_encoder={Decimal: str})
