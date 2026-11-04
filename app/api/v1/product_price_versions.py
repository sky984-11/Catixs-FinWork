from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from loguru import logger
from pydantic import BaseModel, Field, model_validator
from tortoise.transactions import in_transaction

from app.models.customer_center import CrmCustomer
from app.models.product_center import ProductItem, ProductPriceVersion
from app.schemas.base import Success, SuccessExtra

router = APIRouter()


class PriceVersionPayload(BaseModel):
    customer_id: int | None = Field(None, gt=0)
    currency: Literal["CNY", "USD", "EUR", "JPY", "HKD"] = "CNY"
    mrc: Decimal = Field(..., ge=0, max_digits=16, decimal_places=2, allow_inf_nan=False)
    nrc: Decimal = Field(Decimal("0"), ge=0, max_digits=16, decimal_places=2, allow_inf_nan=False)
    period_months: Literal[1, 3, 6, 12, 24, 36] = 1
    effective_date: date
    expiry_date: date

    @model_validator(mode="after")
    def validate_dates(self):
        if self.expiry_date <= self.effective_date:
            raise ValueError("失效日必须晚于生效日")
        return self


async def version_dict(version: ProductPriceVersion):
    data = await version.to_dict()
    data["mrc"] = str(version.mrc)
    data["nrc"] = str(version.nrc)
    today = datetime.now(timezone(timedelta(hours=8))).date()
    data["status"] = (
        "scheduled" if today < version.effective_date else "expired" if today >= version.expiry_date else "active"
    )
    return data


@router.get("/products/{product_id}/price-versions", summary="产品价格方案及版本历史")
async def list_price_versions(
    product_id: int,
    customer_id: int | None = Query(None, ge=0, description="不传为全部，0 为通用价格"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    if not await ProductItem.filter(id=product_id).exists():
        raise HTTPException(404, "产品不存在")
    query = ProductPriceVersion.filter(product_id=product_id)
    if customer_id is not None:
        query = query.filter(customer_id=customer_id or None)
    total = await query.count()
    rows = await query.order_by("-version").offset((page - 1) * page_size).limit(page_size)
    return SuccessExtra(data=[await version_dict(row) for row in rows], total=total, page=page, page_size=page_size)


@router.post("/products/{product_id}/price-versions", summary="新增不可覆盖的产品价格版本")
async def create_price_version(product_id: int, payload: PriceVersionPayload):
    # Serialize all versions of a product, including the first insert, to prevent overlapping submissions.
    async with in_transaction() as conn:
        product = await ProductItem.filter(id=product_id).using_db(conn).select_for_update().first()
        if not product:
            raise HTTPException(404, "产品不存在")
        customer_name = None
        if payload.customer_id:
            customer = await CrmCustomer.filter(id=payload.customer_id, status=True).using_db(conn).first()
            if not customer or customer.lifecycle == "terminated":
                raise HTTPException(422, "请选择有效客户，已终止客户不能用于定价")
            customer_name = customer.name or customer.legal_name
        overlap = (
            await ProductPriceVersion.filter(
                product_id=product_id,
                customer_id=payload.customer_id,
                currency=payload.currency,
                period_months=payload.period_months,
                effective_date__lt=payload.expiry_date,
                expiry_date__gt=payload.effective_date,
            )
            .using_db(conn)
            .exists()
        )
        if overlap:
            raise HTTPException(409, "同一客户、币种和计费周期的价格有效期不能重叠")
        latest = await ProductPriceVersion.filter(product_id=product_id).using_db(conn).order_by("-version").first()
        version = await ProductPriceVersion.create(
            using_db=conn,
            product_id=product_id,
            version=latest.version + 1 if latest else 1,
            customer_name=customer_name,
            billing_unit=product.billing_unit,
            **payload.model_dump(),
        )
    logger.info("Product price version created: product_id={}, version_id={}", product_id, version.id)
    return Success(msg="价格版本已创建，历史版本保留", data=await version_dict(version))


@router.delete("/products/{product_id}/price-versions/{version_id}", summary="删除产品价格方案版本")
async def delete_price_version(product_id: int, version_id: int):
    async with in_transaction() as conn:
        product = await ProductItem.filter(id=product_id).using_db(conn).select_for_update().first()
        if not product:
            raise HTTPException(404, "产品不存在")
        version = await ProductPriceVersion.filter(id=version_id, product_id=product_id).using_db(conn).first()
        if not version:
            raise HTTPException(404, "价格版本不存在或不属于该产品")
        await version.delete(using_db=conn)
    logger.info("Product price version deleted: product_id={}, version_id={}", product_id, version_id)
    return Success(msg="价格版本已删除", data={"id": version_id, "product_id": product_id})
