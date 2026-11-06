from decimal import Decimal
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query
from loguru import logger
from pydantic import BaseModel, ConfigDict, Field, field_validator
from tortoise.exceptions import IntegrityError
from tortoise.expressions import Q
from tortoise.transactions import in_transaction

from app.models.customer_center import CrmCustomer
from app.models.product_center import ProductItem, ProductPriceVersion
from app.models.product_order import ProductOrder, ProductOrderItem
from app.schemas.base import Success, SuccessExtra
from app.services.product_variants import resolve_variant

router = APIRouter()


class OrderItemPayload(BaseModel):
    product_id: int = Field(..., gt=0)
    variant_id: int | None = Field(None, gt=0)
    quantity: int = Field(..., ge=1, le=1000000, strict=True)
    price_version_id: int | None = Field(None, gt=0)
    mrc: Decimal | None = Field(None, ge=0, max_digits=16, decimal_places=2, allow_inf_nan=False)
    nrc: Decimal | None = Field(None, ge=0, max_digits=16, decimal_places=2, allow_inf_nan=False)


PRICE_FIELDS = (
    "price_version_id",
    "price_version_number",
    "currency",
    "period_months",
    "billing_unit",
    "base_mrc",
    "base_nrc",
    "mrc",
    "nrc",
)


def price_snapshot(version):
    return {
        "price_version_id": version.id,
        "price_version_number": version.version,
        "currency": version.currency,
        "period_months": version.period_months,
        "billing_unit": version.billing_unit,
        "base_mrc": version.mrc,
        "base_nrc": version.nrc,
        "mrc": version.mrc,
        "nrc": version.nrc,
    }


def serialize_price(values):
    return {key: format(value, ".2f") if isinstance(value, Decimal) else value for key, value in values.items()}


@router.get("/products/{product_id}/order-price", summary="订单使用的最新公共价格")
async def get_order_price(product_id: int, variant_id: int | None = Query(None, gt=0)):
    if not await ProductItem.filter(id=product_id).exists():
        raise HTTPException(404, "产品不存在")
    variant = await resolve_variant(product_id, variant_id)
    version = (
        await ProductPriceVersion.filter(
            product_id=product_id, variant_id=variant.id if variant else None, customer_id=None
        )
        .order_by("-version")
        .first()
    )
    return Success(data=serialize_price(price_snapshot(version)) if version else None)


async def resolve_price(item, old, conn):
    # Preserve saved prices for old clients and for deleted/replaced catalog versions.
    if (
        old
        and old.price_version_id
        and ("price_version_id" not in item.model_fields_set or item.price_version_id == old.price_version_id)
    ):
        values = {field: getattr(old, field) for field in PRICE_FIELDS}
    else:
        query = ProductPriceVersion.filter(
            product_id=item.product_id, variant_id=item.variant_id, customer_id=None
        ).using_db(conn)
        if item.price_version_id:
            version = await query.filter(id=item.price_version_id).first()
            if not version:
                raise HTTPException(409, "公共价格版本已删除或不属于该产品，请重新继承公共价格")
        else:
            version = await query.order_by("-version").first()
        values = price_snapshot(version) if version else dict.fromkeys(PRICE_FIELDS)
    for field in ("mrc", "nrc"):
        if field in item.model_fields_set:
            override = getattr(item, field)
            if override is not None and values["price_version_id"] is None:
                raise HTTPException(400, "产品尚无公共价格，请先在产品管理中配置价格")
            values[field] = override if override is not None else values[f"base_{field}"]
    return values


class OrderPayload(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(..., min_length=1, max_length=160)
    customer_id: int = Field(..., gt=0)
    remark: str | None = Field(None, max_length=5000)
    items: list[OrderItemPayload] = Field(..., min_length=1, max_length=200)

    @field_validator("items")
    @classmethod
    def unique_products(cls, items):
        if len({(item.product_id, item.variant_id) for item in items}) != len(items):
            raise ValueError("同一产品的同一组合请合并数量，不可重复添加")
        return items


async def order_dict(order):
    data = await order.to_dict()
    data["customer_name"] = order.customer.name
    data["signing_entity_name"] = order.customer.signing_entity.name if order.customer.signing_entity else ""
    data["items"] = [
        {
            "product_id": item.product_id,
            "product_name": item.product_name_snapshot or item.product.name,
            "variant_id": item.variant_id,
            "variant_name": item.variant_name,
            "variant_code": item.variant_code,
            "spec_snapshot": item.spec_snapshot,
            "product_code": item.product.code,
            "product_status": item.product.status,
            "category_id": item.product.category_id,
            "category_name": item.product.category.name if item.product.category else "未分类",
            "quantity": item.quantity,
            **serialize_price({field: getattr(item, field) for field in PRICE_FIELDS}),
        }
        for item in sorted(order.items, key=lambda item: item.position)
    ]
    return data


def order_query():
    return ProductOrder.all().prefetch_related("customer__signing_entity", "items__product__category")


@router.get("/orders", summary="订单列表")
async def list_orders(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    keyword: str = Query("", max_length=160),
    customer_id: int | None = Query(None, gt=0),
):
    query = order_query()
    if keyword.strip():
        query = query.filter(
            Q(order_no__icontains=keyword.strip())
            | Q(name__icontains=keyword.strip())
            | Q(customer__name__icontains=keyword.strip())
        )
    if customer_id:
        query = query.filter(customer_id=customer_id)
    total = await query.count()
    rows = await query.order_by("-id").offset((page - 1) * page_size).limit(page_size)
    return SuccessExtra(data=[await order_dict(row) for row in rows], total=total, page=page, page_size=page_size)


@router.get("/orders/{order_id}", summary="订单详情")
async def get_order(order_id: int):
    order = await order_query().filter(id=order_id).first()
    if not order:
        raise HTTPException(404, "订单不存在")
    return Success(data=await order_dict(order))


async def save_order(payload, order_id=None):
    try:
        async with in_transaction() as conn:
            order = None
            old_product_ids = set()
            old_items = {}
            if order_id is not None:
                order = await ProductOrder.filter(id=order_id).using_db(conn).select_for_update().first()
                if not order:
                    raise HTTPException(404, "订单不存在")
                if payload.customer_id != order.customer_id and (
                    await order.billing_allocations.all().using_db(conn).exists()
                    or await order.billing_plans.all().using_db(conn).exists()
                ):
                    raise HTTPException(409, "订单已关联账单或计费计划，不能更换客户")
                old_items = {
                    (item.product_id, item.variant_id): item
                    for item in await ProductOrderItem.filter(order_id=order_id).using_db(conn)
                }
                old_product_ids = {key[0] for key in old_items}
            customer = await CrmCustomer.filter(id=payload.customer_id).using_db(conn).select_for_update().first()
            if not customer:
                raise HTTPException(400, "客户不存在")
            if (not order or order.customer_id != customer.id) and (
                not customer.status or customer.lifecycle == "terminated"
            ):
                raise HTTPException(400, "请选择有效客户")
            products = (
                await ProductItem.filter(id__in=[item.product_id for item in payload.items])
                .using_db(conn)
                .order_by("id")
                .select_for_update()
            )
            if len(products) != len({item.product_id for item in payload.items}):
                raise HTTPException(400, "部分产品不存在")
            if any(product.status != "active" and product.id not in old_product_ids for product in products):
                raise HTTPException(400, "不能新增已下架产品")
            products_by_id = {product.id: product for product in products}
            snapshots = []
            seen = set()
            for item in payload.items:
                hint = item.variant_id
                if "variant_id" not in item.model_fields_set:
                    candidates = [old for key, old in old_items.items() if key[0] == item.product_id]
                    if len(candidates) == 1:
                        hint = candidates[0].variant_id
                variant = await resolve_variant(item.product_id, hint, conn)
                item.variant_id = variant.id if variant else None
                key = (item.product_id, item.variant_id)
                if key in seen:
                    raise HTTPException(422, "同一规格组合不可重复添加，请合并数量")
                seen.add(key)
                old = old_items.get(key)
                if variant and variant.status != "active" and not old:
                    raise HTTPException(400, "不能新增已下架的规格组合")
                snapshots.append(
                    {
                        "variant_id": item.variant_id,
                        "product_name_snapshot": (
                            old.product_name_snapshot
                            if old and old.product_name_snapshot
                            else products_by_id[item.product_id].name
                        ),
                        "variant_name": old.variant_name if old else variant.name if variant else None,
                        "variant_code": old.variant_code if old else variant.code if variant else None,
                        "spec_snapshot": old.spec_snapshot if old else variant.spec_snapshot if variant else [],
                        **await resolve_price(item, old, conn),
                    }
                )
            values = payload.model_dump(exclude={"items"})
            if order:
                order.update_from_dict(values)
                await order.save(using_db=conn)
                await ProductOrderItem.filter(order_id=order.id).using_db(conn).delete()
            else:
                order = await ProductOrder.create(using_db=conn, order_no=f"ORD-{uuid4().hex.upper()}", **values)
            await ProductOrderItem.bulk_create(
                [
                    ProductOrderItem(
                        order_id=order.id,
                        position=i,
                        product_id=item.product_id,
                        quantity=item.quantity,
                        **snapshots[i],
                    )
                    for i, item in enumerate(payload.items)
                ],
                using_db=conn,
            )
    except IntegrityError as exc:
        raise HTTPException(409, "关联数据已变化，请刷新后重试") from exc
    logger.info("Product order saved: order_id={}", order.id)
    return await get_order(order.id)


@router.post("/orders", summary="新增订单")
async def create_order(payload: OrderPayload):
    return await save_order(payload)


@router.put("/orders/{order_id}", summary="编辑订单")
async def update_order(order_id: int, payload: OrderPayload):
    return await save_order(payload, order_id)


@router.delete("/orders/{order_id}", summary="删除订单及产品明细")
async def delete_order(order_id: int):
    async with in_transaction() as conn:
        order = await ProductOrder.filter(id=order_id).using_db(conn).select_for_update().first()
        if not order:
            raise HTTPException(404, "订单不存在")
        if (
            await order.billing_allocations.all().using_db(conn).exists()
            or await order.billing_plans.all().using_db(conn).exists()
        ):
            raise HTTPException(409, "订单已关联账单或计费计划，不能删除")
        await order.delete(using_db=conn)
    logger.info("Product order deleted: order_id={}", order_id)
    return Success(msg="订单已删除", data={"id": order_id})
