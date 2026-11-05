from fastapi import HTTPException

from app.models.product_center import ProductVariant


async def resolve_variant(product_id, variant_id=None, conn=None):
    query = ProductVariant.filter(product_id=product_id)
    if conn:
        query = query.using_db(conn)
    if variant_id is not None:
        variant = await query.filter(id=variant_id).first()
        if not variant:
            raise HTTPException(404, "规格组合不存在或不属于该产品")
        return variant
    variants = await query.order_by("id").limit(2)
    if len(variants) > 1:
        raise HTTPException(422, "该产品有多个规格组合，请选择具体组合")
    return variants[0] if variants else None
