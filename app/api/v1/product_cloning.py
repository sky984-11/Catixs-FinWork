from copy import deepcopy
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from loguru import logger
from pydantic import BaseModel, ConfigDict, Field
from tortoise.exceptions import IntegrityError
from tortoise.transactions import in_transaction

from app.models.product_center import ProductItem, ProductPriceVersion, ProductVariant
from app.schemas.base import Success

router = APIRouter()


class CloneProductPayload(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    name: str = Field(..., min_length=1, max_length=160)
    code: str = Field(..., min_length=1, max_length=80)
    copy_prices: bool = Field(True, strict=True)


@router.post("/products/{product_id}/clone", summary="克隆产品及规格组合")
async def clone_product(product_id: int, payload: CloneProductPayload):
    from .product_center import product_dict

    try:
        async with in_transaction() as conn:
            source = await ProductItem.filter(id=product_id).using_db(conn).select_for_update().first()
            if not source:
                raise HTTPException(404, "源产品不存在")
            if await ProductItem.filter(code=payload.code).using_db(conn).exists():
                raise HTTPException(409, "产品编号已存在，请更换编号")
            product_values = {
                field: deepcopy(getattr(source, field))
                for field in (
                    "category_id",
                    "status",
                    "region",
                    "billing_mode",
                    "description",
                    "billing_unit",
                    "min_contract_months",
                    "spec_values",
                )
            }
            product = await ProductItem.create(using_db=conn, name=payload.name, code=payload.code, **product_values)
            variants = await ProductVariant.filter(product_id=source.id).using_db(conn).order_by("id")
            variant_ids = {}
            for variant in variants:
                cloned = await ProductVariant.create(
                    using_db=conn,
                    product_id=product.id,
                    name=variant.name,
                    code=f"VAR-{uuid4().hex}",
                    status=variant.status,
                    spec_values=deepcopy(variant.spec_values),
                    spec_snapshot=deepcopy(variant.spec_snapshot),
                )
                variant_ids[variant.id] = cloned.id
            prices = []
            if payload.copy_prices:
                source_prices = (
                    await ProductPriceVersion.filter(product_id=source.id, customer_id=None)
                    .using_db(conn)
                    .order_by("version")
                )
                for price in source_prices:
                    if price.variant_id is not None and price.variant_id not in variant_ids:
                        raise HTTPException(409, "源价格的组合关联异常，请先修复源产品")
                    prices.append(
                        ProductPriceVersion(
                            product_id=product.id,
                            variant_id=variant_ids.get(price.variant_id),
                            **{
                                field: getattr(price, field)
                                for field in (
                                    "version",
                                    "currency",
                                    "mrc",
                                    "nrc",
                                    "period_months",
                                    "billing_unit",
                                    "effective_date",
                                    "expiry_date",
                                )
                            },
                        )
                    )
                if prices:
                    await ProductPriceVersion.bulk_create(prices, using_db=conn)
    except IntegrityError as exc:
        raise HTTPException(409, "产品编号或内部编码冲突，请更换编号后重试") from exc
    logger.info(
        "Product cloned: source_id={}, product_id={}, variants={}, prices={}",
        product_id,
        product.id,
        len(variant_ids),
        len(prices),
    )
    return Success(msg="产品已克隆", data=await product_dict(product))
