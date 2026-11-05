from typing import Any, Literal
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from loguru import logger
from pydantic import BaseModel, ConfigDict, Field
from tortoise.exceptions import IntegrityError
from tortoise.transactions import in_transaction

from app.models.product_center import ProductItem, ProductPriceVersion, ProductVariant
from app.models.product_order import ProductOrderItem
from app.schemas.base import Success

router = APIRouter()


class VariantPayload(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    name: str = Field(..., min_length=1, max_length=160)
    code: str | None = Field(None, min_length=1, max_length=80)
    status: Literal["active", "offline"] = "active"
    spec_values: dict[str, Any] = Field(default_factory=dict, max_length=200)


async def variant_dict(variant):
    return await variant.to_dict()


@router.get("/products/{product_id}/variants", summary="产品规格组合列表")
async def list_variants(product_id: int):
    if not await ProductItem.filter(id=product_id).exists():
        raise HTTPException(404, "产品不存在")
    rows = await ProductVariant.filter(product_id=product_id).order_by("id")
    return Success(data=[await variant_dict(row) for row in rows])


async def save_variant(product_id, payload, variant_id=None):
    # Reuse the existing typed parameter validation and category scope.
    from .product_center import product_spec_fields, validate_spec_values

    try:
        async with in_transaction() as conn:
            product = await ProductItem.filter(id=product_id).using_db(conn).select_for_update().first()
            if not product:
                raise HTTPException(404, "产品不存在")
            variant = None
            if variant_id is not None:
                variant = await ProductVariant.filter(id=variant_id, product_id=product_id).using_db(conn).first()
                if not variant:
                    raise HTTPException(404, "规格组合不存在")
            values = payload.model_dump()
            if values["code"] is None:
                values["code"] = variant.code if variant else f"VAR-{uuid4().hex}"
            # Status/name-only changes must remain possible after an attribute is retired.
            if variant and payload.spec_values == variant.spec_values:
                values["spec_snapshot"] = variant.spec_snapshot
            else:
                if variant and (
                    await ProductPriceVersion.filter(variant_id=variant.id).using_db(conn).exists()
                    or await ProductOrderItem.filter(variant_id=variant.id).using_db(conn).exists()
                ):
                    raise HTTPException(409, "组合已有价格或订单，参数不可覆盖；请新增组合")
                values["spec_values"] = await validate_spec_values(product.category_id, payload.spec_values)
                fields = await product_spec_fields(product.category_id)
                values["spec_snapshot"] = [
                    {
                        "id": field.id,
                        "name": field.name,
                        "unit": field.unit,
                        "value": values["spec_values"][str(field.id)],
                    }
                    for field in fields
                    if str(field.id) in values["spec_values"]
                ]
            if variant:
                variant.update_from_dict(values)
                await variant.save(using_db=conn)
            else:
                variant = await ProductVariant.create(using_db=conn, product_id=product_id, **values)
    except IntegrityError as exc:
        raise HTTPException(409, "该产品下组合名称重复或内部编码已存在") from exc
    logger.info("Product variant saved: product_id={}, variant_id={}", product_id, variant.id)
    return Success(data=await variant_dict(variant))


@router.post("/products/{product_id}/variants", summary="新增规格组合")
async def create_variant(product_id: int, payload: VariantPayload):
    return await save_variant(product_id, payload)


@router.put("/products/{product_id}/variants/{variant_id}", summary="编辑规格组合")
async def update_variant(product_id: int, variant_id: int, payload: VariantPayload):
    return await save_variant(product_id, payload, variant_id)


@router.delete("/products/{product_id}/variants/{variant_id}", summary="删除未被引用的规格组合")
async def delete_variant(product_id: int, variant_id: int):
    async with in_transaction() as conn:
        product = await ProductItem.filter(id=product_id).using_db(conn).select_for_update().first()
        if not product:
            raise HTTPException(404, "产品不存在")
        variant = await ProductVariant.filter(id=variant_id, product_id=product_id).using_db(conn).first()
        if not variant:
            raise HTTPException(404, "规格组合不存在")
        if (
            await ProductPriceVersion.filter(variant_id=variant_id).using_db(conn).exists()
            or await ProductOrderItem.filter(variant_id=variant_id).using_db(conn).exists()
        ):
            raise HTTPException(409, "组合已关联价格版本或订单，请下架以保留历史记录")
        await variant.delete(using_db=conn)
    logger.info("Product variant deleted: variant_id={}", variant_id)
    return Success(msg="规格组合已删除")
