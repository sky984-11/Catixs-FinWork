import asyncio
import sys
from pathlib import Path

from tortoise import Tortoise

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.api.v1.product_center import ATTRIBUTE_CATEGORY_CODE_MAP, ATTRIBUTE_CATEGORY_CODES_MAP
from app.core.init_app import ensure_product_center_columns
from app.models.product_center import ProductCategory, ProductSpecAttribute
from app.settings.config import settings


async def main():
    await Tortoise.init(config=settings.TORTOISE_ORM)
    try:
        await ensure_product_center_columns()
        category_codes = set(ATTRIBUTE_CATEGORY_CODE_MAP.values())
        for codes in ATTRIBUTE_CATEGORY_CODES_MAP.values():
            category_codes.update(codes)
        category_ids = dict(await ProductCategory.filter(code__in=category_codes).values_list("code", "id"))
        updated = []
        skipped = []
        for attribute in await ProductSpecAttribute.all().order_by("code"):
            category_codes = ATTRIBUTE_CATEGORY_CODES_MAP.get(attribute.code)
            if not category_codes:
                category_code = ATTRIBUTE_CATEGORY_CODE_MAP.get(attribute.code)
                category_codes = [category_code] if category_code else []
            ids = [int(category_ids[code]) for code in category_codes if code in category_ids]
            if not ids:
                skipped.append(attribute.code)
                continue
            if attribute.category_id != ids[0] or attribute.category_ids != ids:
                attribute.category_id = ids[0]
                attribute.category_ids = ids
                await attribute.save(update_fields=["category_id", "category_ids", "updated_at"])
                updated.append(attribute.code)
        print(f"updated={len(updated)}")
        print("updated_codes=" + ",".join(updated))
        print(f"skipped={len(skipped)}")
        print("skipped_codes=" + ",".join(skipped))
    finally:
        await Tortoise.close_connections()


if __name__ == "__main__":
    asyncio.run(main())
