import csv
import hashlib
import io
import json
import re
from datetime import datetime
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import ValidationError
from pytz import timezone
from tortoise.exceptions import IntegrityError
from tortoise.expressions import Q
from tortoise.transactions import in_transaction

from app.core.dependency import AuthControl
from app.log import logger
from app.models.company import Company
from app.models.product_center import ProductItem
from app.models.resource_cost import ProductCostLink, ResourceCost, ResourceCostVersion
from app.schemas.base import Success, SuccessExtra
from app.schemas.resource_cost import (
    CATEGORIES,
    FIELDS,
    Category,
    CostImport,
    CostLinkPayload,
    CostPayload,
    ImportPreview,
)

router = APIRouter()
CurrentUser = Depends(AuthControl.is_authed)


async def resource_data(resource, version=None):
    version = version or await ResourceCostVersion.get(resource_id=resource.id, revision=resource.revision)
    title = version.data.get("dc_name") or " · ".join(
        filter(None, [version.data.get("service"), version.data.get("site_a"), version.data.get("site_b")])
    )
    return {
        **version.data,
        "id": resource.id,
        "code": resource.code,
        "title": title,
        "category": resource.category,
        "enabled": version.data.get("enabled", resource.enabled),
        "resource_enabled": resource.enabled,
        "revision": version.revision,
        "latest_revision": resource.revision,
        "version_id": version.id,
        "updated_at": (await version.to_dict())["created_at"],
    }


async def save_cost(payload, user, resource=None):
    vendor = None
    if payload.vendor_id:
        vendor = await Company.filter(id=payload.vendor_id, role__in=[2, 3]).first()
        if not vendor or (not vendor.status and (not resource or resource.vendor_id != vendor.id)):
            raise HTTPException(422, "供应商不存在或已停用，请先在供应商管理维护")
    data = payload.model_dump(mode="json", exclude={"expected_revision"})
    data["vendor_name"] = (vendor.name or vendor.legal_name) if vendor else ""
    title = (
        payload.dc_name
        if payload.category == "xc"
        else " · ".join(filter(None, [payload.service, payload.site_a, payload.site_b]))
    )
    if resource:
        if payload.expected_revision != resource.revision:
            raise HTTPException(409, "成本记录已更新，请重新加载后编辑")
        if payload.category != resource.category:
            raise HTTPException(422, "已有成本记录不能更换分类，请新建记录")
        resource.revision += 1
        resource.code = payload.code or resource.code
        resource.title = title[:255]
        resource.vendor_id = payload.vendor_id
        resource.enabled = payload.enabled
        await resource.save()
    else:
        resource = await ResourceCost.create(
            code=payload.code or f"RC-{uuid4().hex[:16].upper()}",
            category=payload.category,
            title=title[:255],
            vendor_id=payload.vendor_id,
            enabled=payload.enabled,
        )
    data["code"] = resource.code
    version = await ResourceCostVersion.create(
        resource=resource, revision=resource.revision, data=data, created_by_id=user.id
    )
    return await resource_data(resource, version)


@router.get("/options", summary="资源成本库分类字段及供应商选项")
async def options():
    vendors = await Company.filter(role__in=[2, 3]).order_by("name").values("id", "name", "legal_name", "status")
    return Success(data={"categories": CATEGORIES, "fields": FIELDS, "vendors": vendors})


@router.get("", summary="资源成本列表")
async def list_costs(
    category: Category | None = None,
    keyword: str = Query("", max_length=200),
    vendor_id: int | None = None,
    enabled: bool | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    query = ResourceCost.all()
    if category:
        query = query.filter(category=category)
    if vendor_id:
        query = query.filter(vendor_id=vendor_id)
    if enabled is not None:
        query = query.filter(enabled=enabled)
    if keyword:
        query = query.filter(
            Q(title__icontains=keyword) | Q(code__icontains=keyword) | Q(vendor__name__icontains=keyword)
        )
    total = await query.count()
    rows = await query.order_by("-id").offset((page - 1) * page_size).limit(page_size)
    return SuccessExtra(data=[await resource_data(row) for row in rows], total=total, page=page, page_size=page_size)


@router.post("", summary="新增资源成本")
async def create_cost(payload: CostPayload, user=CurrentUser):
    try:
        async with in_transaction():
            data = await save_cost(payload, user)
    except IntegrityError as exc:
        raise HTTPException(409, "成本编号已存在") from exc
    logger.info(f"resource_cost create id={data['id']} user_id={user.id}")
    return Success(data=data)


@router.put("/{resource_id}", summary="更新资源成本并保存新版本")
async def update_cost(resource_id: int, payload: CostPayload, user=CurrentUser):
    try:
        async with in_transaction():
            resource = await ResourceCost.filter(id=resource_id).select_for_update().first()
            if not resource:
                raise HTTPException(404, "成本记录不存在")
            data = await save_cost(payload, user, resource)
    except IntegrityError as exc:
        raise HTTPException(409, "成本编号或版本冲突") from exc
    logger.info(f"resource_cost update id={resource_id} revision={data['revision']} user_id={user.id}")
    return Success(data=data)


@router.get("/{resource_id}/versions", summary="资源成本历史版本")
async def versions(resource_id: int):
    resource = await ResourceCost.get_or_none(id=resource_id)
    if not resource:
        raise HTTPException(404, "成本记录不存在")
    rows = await ResourceCostVersion.filter(resource_id=resource_id).order_by("-revision")
    return Success(data=[await resource_data(resource, row) for row in rows])


def normalized_header(value):
    return re.sub(r"[\s_()/（）、%]+", "", value.strip().lower())


@router.post("/import/preview", summary="校验 CSV 成本数据，不写入数据库")
async def import_preview(payload: ImportPreview):
    if len(payload.csv_text.encode("utf-8")) > 2 * 1024 * 1024:
        raise HTTPException(422, "CSV 文件不能超过 2 MiB")
    keys = ["code"] + CATEGORIES[payload.category]["fields"] + ["effective_date", "expiry_date"]
    aliases = {normalized_header(key): key for key in keys}
    aliases.update({normalized_header(FIELDS[key]["label"]): key for key in keys if key in FIELDS})
    aliases.update(
        {
            "nrc": "nrc",
            "mrc": "mrc",
            "contractterms": "contract_months",
            "taxrate": "tax_rate",
            "remarks": "note",
            "usdmbpsmrc": "price_per_mbps",
            "编号": "code",
        }
    )
    vendors = await Company.filter(role__in=[2, 3], status=True)
    try:
        reader = csv.DictReader(io.StringIO(payload.csv_text.lstrip("\ufeff")), strict=True)
        headers = reader.fieldnames or []
        mapped = [aliases.get(normalized_header(header)) for header in headers]
        if not headers or any(key not in keys for key in mapped) or len(set(mapped)) != len(mapped):
            raise HTTPException(422, "表头不匹配或重复，请使用当前分类 CSV 模板（移除说明行）")
        rows, errors = [], []
        for line_number, raw in enumerate(reader, 2):
            if line_number > 501:
                raise HTTPException(422, "每次最多导入 500 行")
            if not any(value for value in raw.values()):
                continue
            try:
                if None in raw:
                    raise ValueError("列数超过表头；含逗号的地址请用双引号包裹")
                data = {key: (raw[header] or "").strip() or None for header, key in zip(headers, mapped)}
                data["category"] = payload.category
                vendor_value = data.get("vendor_id")
                if vendor_value:
                    matches = [
                        v
                        for v in vendors
                        if str(v.id) == vendor_value or vendor_value in (v.name, v.legal_name, v.code)
                    ]
                    if len(matches) != 1:
                        raise ValueError("Vendor 未唯一匹配启用供应商，请先维护供应商或填写供应商 ID")
                    data["vendor_id"] = matches[0].id
                if data.get("contract_months"):
                    data["contract_months"] = re.sub(r"\s*(months?|月)$", "", data["contract_months"], flags=re.I)
                if data.get("mrc") and data["mrc"] not in ("N/A", "NA") and "/" in data["mrc"]:
                    amount, unit = data["mrc"].split("/", 1)
                    if data.get("mrc_unit") and data["mrc_unit"] != unit:
                        raise ValueError("MRC 计价单位不一致")
                    data.update(mrc=amount.strip(), mrc_unit=unit.strip())
                for key in ("nrc", "mrc", "tax_rate", "price_per_mbps", "burst_price"):
                    value = data.get(key)
                    if value in ("NA", "N/A", "—", "-"):
                        data[key] = None
                    elif value:
                        for symbol, currency in [("€", "EUR"), ("£", "GBP")]:
                            if value.startswith(symbol):
                                if data.get("currency") != currency:
                                    raise ValueError("价格符号与币种不一致")
                                value = value[len(symbol) :]
                        data[key] = value
                model = CostPayload.model_validate(data)
                clean = model.model_dump(mode="json")
                if not clean["code"]:
                    clean["code"] = (
                        "IMP-" + hashlib.sha256(json.dumps(clean, sort_keys=True).encode()).hexdigest()[:20].upper()
                    )
                rows.append(clean)
            except (ValueError, ValidationError) as exc:
                if isinstance(exc, ValidationError):
                    message = "; ".join(f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in exc.errors())
                else:
                    message = str(exc)
                errors.append({"row": line_number, "message": message})
    except csv.Error as exc:
        raise HTTPException(422, "CSV 格式无效或单个字段过长") from exc
    codes = [row["code"] for row in rows]
    if len(codes) != len(set(codes)):
        errors.append({"row": 0, "message": "导入文件包含重复记录或重复编号"})
    if await ResourceCost.filter(code__in=codes).exists():
        errors.append({"row": 0, "message": "成本编号已存在，请编辑已有记录，勿重复导入"})
    return Success(data={"rows": rows, "errors": errors})


@router.post("/import/commit", summary="批量导入资源成本，全部成功或全部回滚")
async def import_commit(payload: CostImport, user=CurrentUser):
    try:
        async with in_transaction():
            for item in payload.rows:
                await save_cost(item, user)
    except IntegrityError as exc:
        raise HTTPException(409, "成本编号重复，本次导入未写入任何记录") from exc
    logger.info(f"resource_cost import count={len(payload.rows)} user_id={user.id}")
    return Success(data={"count": len(payload.rows)})


@router.get("/products/{product_id}/links", summary="产品已关联的成本版本")
async def product_links(product_id: int):
    if not await ProductItem.filter(id=product_id).exists():
        raise HTTPException(404, "产品不存在")
    links = await ProductCostLink.filter(product_id=product_id).select_related("resource", "version")
    return Success(data=[{**await resource_data(row.resource, row.version), "link_id": row.id} for row in links])


@router.post("/products/{product_id}/links", summary="关联或明确更新产品成本来源，不修改销售价格")
async def link_product(product_id: int, payload: CostLinkPayload, user=CurrentUser):
    async with in_transaction():
        product = await ProductItem.filter(id=product_id).select_for_update().first()
        if not product:
            raise HTTPException(404, "产品不存在")
        version = await ResourceCostVersion.get_or_none(id=payload.version_id)
        if not version:
            raise HTTPException(404, "成本版本不存在")
        resource = await ResourceCost.filter(id=version.resource_id).select_for_update().first()
        if not resource.enabled or resource.revision != version.revision:
            raise HTTPException(409, "成本记录已停用或已有新版本，请刷新后选择")
        today = datetime.now(timezone("Asia/Shanghai")).date().isoformat()
        if (version.data.get("effective_date") and version.data["effective_date"] > today) or (
            version.data.get("expiry_date") and version.data["expiry_date"] <= today
        ):
            raise HTTPException(409, "该成本版本未生效或已失效")
        link, _ = await ProductCostLink.update_or_create(
            product_id=product_id, resource_id=resource.id, defaults={"version_id": version.id}
        )
    logger.info(f"resource_cost link product_id={product_id} version_id={version.id} user_id={user.id}")
    return Success(data={"id": link.id})


@router.delete("/products/{product_id}/links/{link_id}", summary="解除产品成本关联，保留成本历史")
async def unlink_product(product_id: int, link_id: int, user=CurrentUser):
    deleted = await ProductCostLink.filter(id=link_id, product_id=product_id).delete()
    if not deleted:
        raise HTTPException(404, "产品成本关联不存在")
    logger.info(f"resource_cost unlink product_id={product_id} link_id={link_id} user_id={user.id}")
    return Success()
