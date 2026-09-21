"""Transactional IDC workflow. All mutations lock the account before its children."""

from datetime import date
from decimal import Decimal
from uuid import uuid4

from fastapi import HTTPException
from fastapi.encoders import jsonable_encoder
from tortoise.transactions import in_transaction

from app.controllers.ticket import ticket_controller
from app.core.ctx import CTX_USER_ID
from app.core.dependency import has_admin_role
from app.models.admin import User
from app.models.asset import AssetCabinet, AssetDevice, CloudResourceSnapshot
from app.models.company import Company
from app.models.customer_center import CrmCustomer, CrmSigningEntity
from app.models.idc import (
    CustomerService,
    IdcAccount,
    IdcAudit,
    IdcDeliveryTask,
    IdcOrder,
    IdcOrderLine,
    IdcQuote,
    ServiceCharge,
    ServiceResourceBinding,
    ServiceVersion,
)
from app.models.product_center import ProductCategory, ProductItem, ProductPrice
from app.models.ticket import Ticket
from app.schemas.tickets import TicketCreate
from app.services.idc_catalog import CATALOG, validate_parameters

SERVICE_ACTIONS = {"change", "renew", "suspend", "resume", "terminate", "incident", "maintenance"}
SUPPORT_ACTIONS = {"incident", "maintenance"}
STAFF_APIS = {
    ("POST", "/api/v1/idc/accounts"),
    ("POST", "/api/v1/idc/lines/{line_id}/quotes"),
    ("POST", "/api/v1/idc/lines/{line_id}/delivery"),
    ("POST", "/api/v1/idc/billing/generate"),
}


async def actor():
    user = await User.get_or_none(id=CTX_USER_ID.get())
    if not user or not user.is_active:
        raise HTTPException(401, "登录失效")
    return user


async def is_staff(user):
    if user.is_superuser or await has_admin_role(user):
        return True
    for role in await user.roles:
        if any((api.method, api.path) in STAFF_APIS for api in await role.apis):
            return True
    return False


async def allowed_accounts(user):
    accounts = await IdcAccount.all().order_by("id")
    if await is_staff(user):
        return accounts
    return [item for item in accounts if user.id in (item.user_ids or [])]


async def account_access(account_id, user, *, lock=False, active=False):
    query = IdcAccount.filter(id=account_id)
    account = await (query.select_for_update() if lock else query).first()
    if not account:
        raise HTTPException(404, "客户账务映射不存在")
    if not await is_staff(user) and user.id not in (account.user_ids or []):
        raise HTTPException(403, "无权访问该客户")
    if active and not account.active:
        raise HTTPException(409, "客户账务映射已停用")
    return account


async def audit(user, action, kind, identifier, data):
    await IdcAudit.create(
        actor_id=user.id, action=action, object_type=kind, object_id=identifier, data=jsonable_encoder(data)
    )


async def catalog_products():
    """Idempotent additions only; never overwrite existing user product definitions."""
    for definition in CATALOG.values():
        group_code = "IDC." + definition["code"].split(".")[0]
        group, _ = await ProductCategory.get_or_create(
            code=group_code, defaults={"name": definition["category"], "level": 1}
        )
        parent = group
        if definition["code"].startswith("NET.DIA."):
            parent, _ = await ProductCategory.get_or_create(
                code="IDC.NET.DIA", defaults={"name": "DIA", "parent_id": group.id, "level": 2}
            )
        leaf, _ = await ProductCategory.get_or_create(
            code="IDC." + definition["code"] + ".LEAF",
            defaults={"name": definition["name"], "parent_id": parent.id, "level": parent.level + 1},
        )
        await ProductItem.get_or_create(
            code=definition["code"], defaults={"name": definition["name"], "category_id": leaf.id}
        )


async def account_dict(account):
    customer, entity, company = await account.customer, await account.signing_entity, await account.company
    return {
        **await account.to_dict(),
        "customer_name": customer.name,
        "customer_code": customer.customer_code,
        "signing_entity_name": entity.name,
        "company_name": company.name,
    }


async def save_account(payload, user):
    customer = await CrmCustomer.get_or_none(id=payload.customer_id, status=True)
    entity = await CrmSigningEntity.get_or_none(id=payload.signing_entity_id, status=True)
    company = await Company.get_or_none(id=payload.company_id, role=1)
    if not customer or not entity or not company:
        raise HTTPException(422, "请选择有效CRM客户、签约主体与账单客户公司")
    if customer.signing_entity_id != entity.id:
        raise HTTPException(422, "签约主体与CRM客户不匹配")
    ids = sorted(set(payload.user_ids))
    if await User.filter(id__in=ids).count() != len(ids):
        raise HTTPException(422, "授权用户不存在")
    async with in_transaction():
        existing = await IdcAccount.filter(id=payload.id).select_for_update().first() if payload.id else None
        if payload.id and not existing:
            raise HTTPException(404, "映射不存在")
        if existing and await IdcOrder.filter(account_id=existing.id).exists():
            if (existing.customer_id, existing.signing_entity_id, existing.company_id) != (
                payload.customer_id,
                payload.signing_entity_id,
                payload.company_id,
            ):
                raise HTTPException(409, "已有工单的客户/主体/账单映射不可修改")
        values = payload.model_dump(exclude={"id"})
        values["user_ids"] = ids
        if existing:
            await existing.update_from_dict(values).save()
        else:
            existing = await IdcAccount.create(**values)
        await audit(user, "account_saved", "account", existing.id, values)
        return await account_dict(existing)


async def current_version(service_id, on=None):
    on = on or date.today()
    version = await ServiceVersion.filter(service_id=service_id, starts_on__lte=on).order_by("-starts_on").first()
    if version and version.ends_before and version.ends_before <= on:
        return None
    return version


async def create_order(payload, user):
    async with in_transaction():
        await account_access(payload.account_id, user, lock=True, active=True)
        duplicate = await IdcOrder.get_or_none(request_key=payload.request_key)
        if duplicate:
            if duplicate.account_id != payload.account_id or (await duplicate.ticket).user_id != user.id:
                raise HTTPException(409, "请求标识已使用")
            return await order_dict(duplicate, user)
        lines = []
        for index, line in enumerate(payload.lines):
            product = await ProductItem.get_or_none(code=line.product_code, status="active")
            if not product or line.product_code not in CATALOG:
                raise HTTPException(422, "产品不存在或已停用")
            if line.parent_index is not None and line.parent_index >= index:
                raise HTTPException(422, "附加产品必须指向前面的主产品")
            service = None
            if line.source_service_id:
                service = await CustomerService.get_or_none(id=line.source_service_id, account_id=payload.account_id)
                if not service or service.product_code != line.product_code:
                    raise HTTPException(422, "原客户产品与客户或产品分类不匹配")
            if payload.action in SERVICE_ACTIONS and not service:
                raise HTTPException(422, "该业务动作必须关联已有客户产品")
            if payload.action in {"new", "one_time"} and service:
                raise HTTPException(422, "新开通不可覆盖已有客户产品")
            parameters = validate_parameters(
                line.product_code,
                line.parameters,
                complete=payload.action not in {"quote", *SUPPORT_ACTIONS, "terminate", "suspend", "resume", "renew"},
            )
            if not parameters and service:
                version = await current_version(service.id)
                parameters = version.parameters if version else {}
            lines.append((line, product, parameters))
        kind = 0 if payload.action == "incident" else 2 if payload.action == "maintenance" else 1
        ticket = await ticket_controller.create_ticket(
            TicketCreate(
                title=payload.title,
                type=kind,
                user_id=user.id,
                desc=payload.description,
            )
        )
        order = await IdcOrder.create(
            ticket=ticket,
            account_id=payload.account_id,
            action=payload.action,
            contact=payload.contact,
            requested_date=payload.requested_date,
            reference=payload.reference,
            request_key=payload.request_key,
        )
        created = []
        for line, product, parameters in lines:
            created.append(
                await IdcOrderLine.create(
                    order=order,
                    product=product,
                    product_code=product.code,
                    quantity=line.quantity,
                    parameters=parameters,
                    schema_snapshot=CATALOG[product.code],
                    service_id=line.source_service_id,
                    parent_id=created[line.parent_index].id if line.parent_index is not None else None,
                    stage="support" if payload.action in SUPPORT_ACTIONS else "draft",
                )
            )
        await audit(user, "order_created", "order", order.id, {"action": order.action, "ticket_id": ticket.id})
        return await order_dict(order, user)


async def line_access(line_id, user, *, lock=False):
    line = await IdcOrderLine.get_or_none(id=line_id)
    if not line:
        raise HTTPException(404, "工单产品明细不存在")
    order = await line.order
    account = await account_access(order.account_id, user, lock=lock)
    if lock:
        line = await IdcOrderLine.filter(id=line_id).select_for_update().get()
    return line, order, account


async def order_dict(order, user):
    await account_access(order.account_id, user)
    data = await order.to_dict()
    data["ticket"] = await (await order.ticket).to_dict()
    data["account"] = await account_dict(await order.account)
    data["lines"] = []
    for line in await IdcOrderLine.filter(order_id=order.id).order_by("id"):
        row = await line.to_dict()
        row["name"] = line.schema_snapshot.get("name", line.product_code)
        row["quotes"] = [await quote.to_dict() for quote in await IdcQuote.filter(line_id=line.id).order_by("version")]
        row["tasks"] = [await task.to_dict() for task in await IdcDeliveryTask.filter(line_id=line.id)]
        row["resources"] = [
            await binding.to_dict()
            for binding in await ServiceResourceBinding.filter(line_id=line.id).exclude(state="released")
        ]
        if line.service_id:
            present = {binding["id"] for binding in row["resources"]}
            for binding in await ServiceResourceBinding.filter(service_id=line.service_id).exclude(state="released"):
                if binding.id not in present and f"{binding.kind}:{binding.resource_key}" in line.delivery.get(
                    "resource_keys", []
                ):
                    row["resources"].append(await binding.to_dict())
        data["lines"].append(row)
    return jsonable_encoder(data, custom_encoder={Decimal: str})


async def update_line(line_id, payload, user):
    async with in_transaction():
        line, order, _ = await line_access(line_id, user, lock=True)
        if line.revision != payload.revision or line.stage not in {"draft", "quoted", "approved", "rejected"}:
            raise HTTPException(409, "明细已变化或已确认，请刷新；已确认需求须取消后重新提交")
        if line.product_code != payload.product_code or line.service_id != payload.source_service_id:
            raise HTTPException(409, "产品种类及原服务不可直接替换，请另建明细工单")
        line.parameters = validate_parameters(
            line.product_code,
            payload.parameters,
            complete=order.action not in {"quote", "terminate", "suspend", "resume", "renew"},
            snapshot=line.schema_snapshot,
        )
        line.quantity = payload.quantity
        line.revision += 1
        line.stage = "draft"
        await line.save()
        await audit(user, "line_updated", "line", line.id, {"revision": line.revision})
        return await order_dict(order, user)


async def price_candidates(line_id, user):
    line, _, account = await line_access(line_id, user)
    # Do not silently select prices lacking exact spec/region/currency confirmation.
    rows = await ProductPrice.filter(product_id=line.product_id, status="active").order_by("id")
    today = date.today()
    candidates = []
    for price in rows:
        if price.price_type not in {"standard", "customer"} or (
            price.price_type == "customer" and price.customer_id != account.customer_id
        ):
            continue
        if (price.effective_date and price.effective_date > today) or (price.expiry_date and price.expiry_date < today):
            continue
        candidates.append(await price.to_dict())
    return jsonable_encoder(
        sorted(candidates, key=lambda row: row["price_type"] != "customer"), custom_encoder={Decimal: str}
    )


async def quote_line(line_id, payload, user):
    async with in_transaction():
        line, order, _ = await line_access(line_id, user, lock=True)
        if order.action in SUPPORT_ACTIONS or line.stage not in {"draft", "quoted", "approved", "rejected"}:
            raise HTTPException(409, "该明细当前不能报价；故障维护收费须另建服务请求")
        if line.revision != payload.revision or payload.valid_until < date.today():
            raise HTTPException(409, "需求版本已变化或报价已过期")
        if order.action not in {"terminate", "suspend", "resume", "renew"}:
            validate_parameters(line.product_code, line.parameters, snapshot=line.schema_snapshot)
        needs_survey = line.product_code == "NET.DIA.RETAIL" or any(
            line.parameters.get(f"{side}_access") in {"off_net", "survey"} for side in ("a", "z")
        )
        if needs_survey and not payload.procurement_reference:
            raise HTTPException(422, "楼宇或Off-net产品必须提供勘查/采购询价依据")
        if order.action in {"one_time", "terminate"} and any(c.kind != "nrc" for c in payload.charges):
            raise HTTPException(422, "一次性服务或退订仅可报价一次性费用（免费项目填0）")
        if line.parameters.get("burst") == "yes" and not any(c.kind == "usage" for c in payload.charges):
            raise HTTPException(422, "开启突发须明确用量费用组件，可选择已包含并填0")
        line.quote_version += 1
        await IdcQuote.create(
            line=line,
            version=line.quote_version,
            line_revision=line.revision,
            currency=payload.currency,
            valid_until=payload.valid_until,
            author_id=user.id,
            charges=[item.model_dump(mode="json") for item in payload.charges],
            terms=payload.model_dump(mode="json", exclude={"charges", "revision", "currency", "valid_until"}),
        )
        line.stage = "quoted"
        await line.save()
        await audit(user, "quote_created", "line", line.id, {"version": line.quote_version})
        return await order_dict(order, user)


async def decide_quote(line_id, payload, user):
    async with in_transaction():
        line, order, _ = await line_access(line_id, user, lock=True)
        if payload.action == "cancel" and line.stage == "draft" and payload.version == line.quote_version:
            line.stage = "cancelled"
            await line.save()
            await audit(user, "line_cancelled", "line", line.id, {"evidence": payload.evidence})
            await sync_ticket_status(order)
            return await order_dict(order, user)
        quote = await IdcQuote.get_or_none(line_id=line.id, version=payload.version)
        if not quote or quote.version != line.quote_version or quote.line_revision != line.revision:
            raise HTTPException(409, "报价不存在或已被新版本替代")
        target = {
            "approve": "approved",
            "confirm": "confirmed",
            "reject": "rejected",
            "cancel": "cancelled",
            "revise": "superseded",
        }[payload.action]
        if quote.status == target and line.stage not in {"active", "accepted"}:
            return await order_dict(order, user)
        if payload.action in {"approve", "confirm"} and quote.valid_until < date.today():
            raise HTTPException(409, "报价已过期，请重新报价")
        if payload.action == "approve":
            if quote.status != "draft" or line.stage != "quoted":
                raise HTTPException(409, "仅待审批报价可批准")
            quote.approved_by = user.id
            line.stage = "approved"
        elif payload.action == "confirm":
            if quote.status != "approved" or line.stage != "approved":
                raise HTTPException(409, "先完成商务审批")
            quote.confirmed_by = user.id
            quote.confirmation = payload.evidence
            line.stage = "quote_done" if order.action == "quote" else "delivery"
            if order.action != "quote":
                await IdcDeliveryTask.get_or_create(line=line, department="delivery")
                if quote.terms.get("procurement_reference"):
                    await IdcDeliveryTask.get_or_create(line=line, department="procurement")
        elif payload.action == "revise":
            if line.stage not in {"delivery", "acceptance"}:
                raise HTTPException(409, "仅未验收的交付明细可撤回重新报价")
            line.revision += 1
            line.stage = "draft"
            line.delivery = {}
            await IdcDeliveryTask.filter(line_id=line.id).update(status="pending", evidence="")
            await ServiceResourceBinding.filter(line_id=line.id, state="reserved").update(
                state="released", exclusive_key=None
            )
        elif payload.action == "reject":
            if line.stage not in {"quoted", "approved"}:
                raise HTTPException(409, "已交付或已确认明细不能驳回报价")
            line.stage = "rejected"
        else:
            if line.stage in {"accepted", "active", "cancelled"}:
                raise HTTPException(409, "已生效服务应走退订工单")
            if await IdcDeliveryTask.filter(line_id=line.id, status__in=["working", "done"]).exists():
                raise HTTPException(409, "已实施工单需确认实际费用；请完成交付后通过退订/调整处理")
            line.stage = "cancelled"
            await ServiceResourceBinding.filter(line_id=line.id, state="reserved").update(
                state="released", exclusive_key=None
            )
        quote.status = target
        await quote.save()
        await line.save()
        await audit(
            user, f"quote_{payload.action}", "line", line.id, {"version": payload.version, "evidence": payload.evidence}
        )
        await sync_ticket_status(order)
        return await order_dict(order, user)


async def sync_ticket_status(order):
    stages = await IdcOrderLine.filter(order_id=order.id).values_list("stage", flat=True)
    finished = {"accepted", "quote_done", "cancelled", "support_done"}
    status = (
        3 if all(stage == "cancelled" for stage in stages) else 0 if all(stage in finished for stage in stages) else 1
    )
    await Ticket.filter(id=order.ticket_id).update(status=status)


async def update_task(task_id, payload, user):
    async with in_transaction():
        task = await IdcDeliveryTask.get_or_none(id=task_id)
        if not task:
            raise HTTPException(404, "交付任务不存在")
        line, order, _ = await line_access(task.line_id, user, lock=True)
        if line.stage not in {"delivery", "acceptance"}:
            raise HTTPException(409, "当前阶段不可修改交付任务")
        if payload.assignee_id and not await User.filter(id=payload.assignee_id, is_active=True).exists():
            raise HTTPException(422, "处理人无效")
        await task.update_from_dict(payload.model_dump()).save()
        await audit(user, "task_updated", "line", line.id, {"task_id": task.id, **payload.model_dump()})
        return await order_dict(order, user)


async def validate_resource(resource):
    key = resource.key.strip()
    if resource.kind == "device":
        parts = key.split(":", 1)
        if not parts[0].isdigit():
            raise HTTPException(422, "设备资源键应为设备ID或设备ID:节点名")
        device = await AssetDevice.get_or_none(id=int(parts[0]))
        if not device or device.status in {3, 4}:
            raise HTTPException(422, "设备不存在、故障或已下架")
        nodes = (device.attributes or {}).get("nodes", [])
        if len(parts) == 2 and parts[1] not in {str(node.get("name")) for node in nodes}:
            raise HTTPException(422, "设备子节点不存在")
        key = str(device.id) + (":" + parts[1] if len(parts) == 2 else "")
    elif resource.kind == "cabinet":
        if not key.isdigit() or not await AssetCabinet.filter(id=int(key), status=True).exists():
            raise HTTPException(422, "机柜不存在或已停用")
        key = str(int(key))
    elif resource.kind == "vm":
        remote, sep, vmid = key.rpartition(":")
        snapshot = await CloudResourceSnapshot.get_or_none(key="fleet")
        if (
            not sep
            or not snapshot
            or not any(
                str(item.get("remote")) == remote and str(item.get("vmid")) == vmid
                for item in (snapshot.payload or {}).get("items", [])
            )
        ):
            raise HTTPException(422, "VM资源键须为快照中存在的remote:vmid")
    elif resource.kind == "ip":
        from ipaddress import ip_network

        try:
            key = str(ip_network(key, strict=True))
        except ValueError:
            raise HTTPException(422, "IP资源键须为有效CIDR")
    if resource.shared and resource.kind in {"device", "vm", "ip"}:
        raise HTTPException(422, "设备、VM和IP不能标为共享资源；使用具体子节点/前缀")
    return key


async def save_delivery(line_id, payload, user):
    async with in_transaction():
        line, order, _ = await line_access(line_id, user, lock=True)
        # All IDC reservations share this catalog row lock, including overlapping IP ranges.
        await ProductItem.filter(code="ADDON.LOCAL_LOOP").select_for_update().get()
        if line.stage not in {"delivery", "acceptance"} or line.revision != payload.revision:
            raise HTTPException(409, "当前阶段或版本不允许交付回填")
        if order.action not in {"suspend", "resume", "terminate", "renew"}:
            actual = validate_parameters(line.product_code, payload.actual_parameters, snapshot=line.schema_snapshot)
            if actual != line.parameters:
                raise HTTPException(409, "实际规格与确认需求不同，请先撤回报价并通过需求变更重新确认")
            for label in line.schema_snapshot["delivery_fields"]:
                if not isinstance(payload.values.get(label), str) or not payload.values[label].strip():
                    raise HTTPException(422, f"缺少交付信息：{label}")
        if any(not isinstance(value, str) or len(value) > 3000 for value in payload.values.values()):
            raise HTTPException(422, "交付回填内容无效")
        if order.action in {"new", "one_time", "change"} and line.product_code in {"COMPUTE.BMS", "COMPUTE.VM"}:
            required_kind = "device" if line.product_code == "COMPUTE.BMS" else "vm"
            if not any(resource.kind == required_kind for resource in payload.resources):
                raise HTTPException(422, "计算资源须绑定实际设备或VM")
        await ServiceResourceBinding.filter(line_id=line.id, state="reserved").update(
            state="released", exclusive_key=None
        )
        keys = set()
        for resource in payload.resources:
            key = await validate_resource(resource)
            identity = f"{resource.kind}:{key}"
            if identity in keys:
                raise HTTPException(422, "资源重复")
            keys.add(identity)
            used = []
            for binding in await ServiceResourceBinding.filter(kind=resource.kind).exclude(state="released"):
                overlaps = binding.resource_key == key
                if resource.kind == "device":
                    left, right = binding.resource_key.split(":"), key.split(":")
                    overlaps = left[0] == right[0] and (len(left) == 1 or len(right) == 1 or left == right)
                elif resource.kind == "ip":
                    from ipaddress import ip_network

                    overlaps = ip_network(binding.resource_key).overlaps(ip_network(key))
                if overlaps:
                    used.append(binding)
            if any(binding.service_id != line.service_id or not line.service_id for binding in used):
                if not resource.shared or any(binding.exclusive_key for binding in used):
                    raise HTTPException(409, "资源已由其他客户产品占用")
            if used and all(binding.service_id == line.service_id for binding in used):
                if any(binding.resource_key != key for binding in used):
                    raise HTTPException(409, "新资源与原服务资源范围重叠，请沿用原资源或选择独立范围")
                continue
            await ServiceResourceBinding.create(
                line=line,
                kind=resource.kind,
                resource_key=key,
                exclusive_key=None if resource.shared else identity,
                details=resource.details,
            )
        if not keys and line.service_id and order.action != "terminate":
            previous = await ServiceVersion.filter(service_id=line.service_id).order_by("-starts_on").first()
            keys.update(previous.delivery.get("resource_keys", []) if previous else [])
        line.delivery = {
            "values": payload.values,
            "resource_keys": sorted(keys) if order.action != "terminate" else [],
            "evidence": payload.evidence,
            "by": user.id,
            "actual_parameters": payload.actual_parameters,
        }
        line.stage = "acceptance"
        await line.save()
        await audit(user, "delivery_saved", "line", line.id, {"resource_count": len(payload.resources)})
        return await order_dict(order, user)


async def accept_line(line_id, payload, user):
    async with in_transaction():
        line, order, account = await line_access(line_id, user, lock=True)
        existing = await ServiceVersion.get_or_none(source_line_id=line.id)
        if existing:
            repeated_quote = await IdcQuote.get_or_none(line_id=line.id, version=payload.quote_version)
            if (
                not payload.accept
                or not repeated_quote
                or existing.starts_on != payload.starts_on
                or existing.ends_before != payload.ends_before
                or existing.quote_id != repeated_quote.id
                or payload.revision != line.revision
            ):
                raise HTTPException(409, "该明细已按其他条件生效")
            return await order_dict(order, user)
        if (
            line.stage != "acceptance"
            or line.revision != payload.revision
            or payload.quote_version != line.quote_version
        ):
            raise HTTPException(409, "请先完成当前版本交付")
        if not payload.accept:
            line.stage = "delivery"
            line.acceptance = {"rejected_by": user.id, "evidence": payload.evidence}
            await line.save()
            await audit(user, "acceptance_rejected", "line", line.id, line.acceptance)
            return await order_dict(order, user)
        quote = await IdcQuote.get(line_id=line.id, version=line.quote_version)
        if quote.status != "confirmed" or order.action in {"quote", *SUPPORT_ACTIONS}:
            raise HTTPException(409, "未确认报价或非交付业务不能生效")
        if await IdcDeliveryTask.filter(line_id=line.id).exclude(status="done").exists():
            raise HTTPException(409, "交付任务尚未全部完成")
        dependencies = await IdcOrderLine.filter(parent_id=line.id)
        if any(child.stage != "accepted" for child in dependencies):
            raise HTTPException(409, "必需附加产品尚未验收（取消的附加项也需重新确认主产品方案）")
        for side in ("a", "z"):
            if line.parameters.get(f"{side}_local_loop") == "own" and not any(
                child.product_code == "ADDON.LOCAL_LOOP" and child.parameters.get("side") == side
                for child in dependencies
            ):
                raise HTTPException(409, f"缺少{side.upper()}端本地传输附加明细")
        if line.service_id:
            service = await CustomerService.filter(id=line.service_id).select_for_update().get()
            last = await ServiceVersion.filter(service=service).order_by("-starts_on").first()
            if not last or payload.starts_on <= last.starts_on:
                raise HTTPException(409, "变更生效日必须晚于最近版本；历史补差通过账单调整处理")
            if last.state == "terminated" or (
                last.ends_before and payload.starts_on > last.ends_before and order.action != "renew"
            ):
                raise HTTPException(409, "服务已终止或已过期")
            if order.action == "resume" and last.state != "suspended":
                raise HTTPException(409, "仅已暂停服务可以恢复")
            if order.action == "suspend" and last.state != "active":
                raise HTTPException(409, "仅在用服务可以暂停")
            from app.services.idc_billing import ensure_unbilled_change

            await ensure_unbilled_change(service.id, payload.starts_on)
            last.ends_before = payload.starts_on
            await last.save(update_fields=["ends_before", "updated_at"])
        else:
            service = await CustomerService.create(
                account=account,
                product_id=line.product_id,
                product_code=line.product_code,
                service_no="SVC-" + uuid4().hex[:16].upper(),
                name=line.schema_snapshot["name"],
                anchor=payload.starts_on,
            )
            line.service_id = service.id
        state = "terminated" if order.action == "terminate" else "suspended" if order.action == "suspend" else "active"
        version = await ServiceVersion.create(
            service=service,
            source_line=line,
            quote=quote,
            starts_on=payload.starts_on,
            ends_before=payload.ends_before,
            state=state,
            quantity=line.quantity,
            parameters=line.parameters,
            delivery=line.delivery,
        )
        for component in quote.charges:
            await ServiceCharge.create(
                version=version,
                code=component["code"],
                kind=component["kind"],
                name=component["name"],
                unit_price=Decimal(component["amount"]),
                tax_rate=Decimal(component["tax_rate"]),
                included=component["treatment"] != "separate",
                rule=component,
            )
        await ServiceResourceBinding.filter(line_id=line.id, state="reserved").update(
            service_id=service.id, state="active"
        )
        await reconcile_service_resources(service.id)
        if line.parent_id:
            parent = await IdcOrderLine.get(id=line.parent_id)
            if parent.service_id:
                service.parent_id = parent.service_id
                await service.save(update_fields=["parent_id", "updated_at"])
        for child in dependencies:
            if child.service_id:
                await CustomerService.filter(id=child.service_id).update(parent_id=service.id)
        line.stage = "accepted"
        line.acceptance = {**payload.model_dump(mode="json"), "by": user.id, "version_id": version.id}
        await line.save()
        await audit(user, "service_version_created", "service", service.id, line.acceptance)
        await sync_ticket_status(order)
        return await order_dict(order, user)


async def reconcile_service_resources(service_id):
    """Keep current and future resource assignments; release obsolete assignments only."""
    current = await current_version(service_id)
    versions = await ServiceVersion.filter(service_id=service_id, starts_on__gt=date.today())
    if current:
        versions.append(current)
    desired = {
        key
        for version in versions
        if version.state != "terminated"
        for key in version.delivery.get("resource_keys", [])
    }
    released = 0
    for binding in await ServiceResourceBinding.filter(service_id=service_id).exclude(state="released"):
        if f"{binding.kind}:{binding.resource_key}" not in desired:
            binding.state = "released"
            binding.exclusive_key = None
            await binding.save(update_fields=["state", "exclusive_key", "updated_at"])
            released += 1
    return released


async def service_dict(service):
    result = await service.to_dict()
    versions = await ServiceVersion.filter(service=service).order_by("starts_on")
    result["versions"] = []
    for version in versions:
        row = await version.to_dict()
        row["charges"] = [await charge.to_dict() for charge in await ServiceCharge.filter(version=version)]
        quote = await version.quote
        row["currency"] = quote.currency
        result["versions"].append(row)
    current = await current_version(service.id)
    result["state"] = current.state if current else "scheduled" if service.anchor > date.today() else "expired"
    result["resources"] = [
        await row.to_dict() for row in await ServiceResourceBinding.filter(service=service).exclude(state="released")
    ]
    return jsonable_encoder(result, custom_encoder={Decimal: str})
