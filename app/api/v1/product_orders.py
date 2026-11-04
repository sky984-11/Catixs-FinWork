from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query
from loguru import logger
from pydantic import BaseModel, ConfigDict, Field, field_validator
from tortoise.exceptions import IntegrityError
from tortoise.expressions import Q
from tortoise.transactions import in_transaction

from app.models.customer_center import CrmCustomer
from app.models.product_center import ProductItem
from app.models.product_order import ProductOrder, ProductOrderItem
from app.schemas.base import Success, SuccessExtra

router = APIRouter()


class OrderItemPayload(BaseModel):
    product_id: int = Field(..., gt=0)
    quantity: int = Field(..., ge=1, le=1000000, strict=True)


class OrderPayload(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(..., min_length=1, max_length=160)
    customer_id: int = Field(..., gt=0)
    remark: str | None = Field(None, max_length=5000)
    items: list[OrderItemPayload] = Field(..., min_length=1, max_length=200)

    @field_validator("items")
    @classmethod
    def unique_products(cls, items):
        if len({item.product_id for item in items}) != len(items):
            raise ValueError("同一产品请合并数量，不可重复添加")
        return items


async def order_dict(order):
    data = await order.to_dict()
    data["customer_name"] = order.customer.name
    data["signing_entity_name"] = order.customer.signing_entity.name if order.customer.signing_entity else ""
    data["items"] = [
        {
            "product_id": item.product_id,
            "product_name": item.product.name,
            "product_code": item.product.code,
            "product_status": item.product.status,
            "category_id": item.product.category_id,
            "category_name": item.product.category.name if item.product.category else "未分类",
            "quantity": item.quantity,
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
            if order_id is not None:
                order = await ProductOrder.filter(id=order_id).using_db(conn).select_for_update().first()
                if not order:
                    raise HTTPException(404, "订单不存在")
                old_product_ids = set(
                    await ProductOrderItem.filter(order_id=order_id).using_db(conn).values_list("product_id", flat=True)
                )
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
            if len(products) != len(payload.items):
                raise HTTPException(400, "部分产品不存在")
            if any(product.status != "active" and product.id not in old_product_ids for product in products):
                raise HTTPException(400, "不能新增已下架产品")
            values = payload.model_dump(exclude={"items"})
            if order:
                order.update_from_dict(values)
                await order.save(using_db=conn)
                await ProductOrderItem.filter(order_id=order.id).using_db(conn).delete()
            else:
                order = await ProductOrder.create(using_db=conn, order_no=f"ORD-{uuid4().hex.upper()}", **values)
            await ProductOrderItem.bulk_create(
                [
                    ProductOrderItem(order_id=order.id, position=i, **item.model_dump())
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
        await order.delete(using_db=conn)
    logger.info("Product order deleted: order_id={}", order_id)
    return Success(msg="订单已删除", data={"id": order_id})
