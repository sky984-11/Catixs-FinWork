"""Merge the six legacy CAT roots into the matching IDC roots; dry-run by default."""

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tortoise import Tortoise
from tortoise.transactions import in_transaction

from app.models.product_center import ProductCategory, ProductItem, ProductSpecAttribute, ProductTemplate
from app.settings.config import settings

ROOT_CODES = {
    "CAT001": "IDC.DC",
    "CAT002": "IDC.COMPUTE",
    "CAT003": "IDC.IP",
    "CAT004": "IDC.CLOUD",
    "CAT005": "IDC.NET",
    "CAT006": "IDC.VAS",
}


async def merge_categories(apply=False):
    async with in_transaction() as conn:
        rows = await ProductCategory.all().using_db(conn).order_by("order", "name", "id").select_for_update()
        by_code = {row.code: row for row in rows}
        children = {}
        for row in rows:
            children.setdefault(row.parent_id, []).append(row)
        redirects = {}
        moves = {}

        def merge(source, target):
            redirects[source.id] = target.id
            for child in children.get(source.id, []):
                matches = [node for node in children.get(target.id, []) if node.name == child.name]
                if len(matches) > 1:
                    raise ValueError("Ambiguous target child categories; no changes applied")
                if matches:
                    merge(child, matches[0])
                else:
                    moves[child.id] = target.id
                    children.setdefault(target.id, []).append(child)

        for source_code, target_code in ROOT_CODES.items():
            source, target = by_code.get(source_code), by_code.get(target_code)
            if not source or not target:
                continue
            if source.parent_id is not None or target.parent_id is not None or source.name != target.name:
                raise ValueError("Legacy root does not match expected category; no changes applied")
            merge(source, target)

        result = {
            "merged_categories": len(redirects),
            "moved_categories": len(moves),
            "redirects": redirects,
            "moves": moves,
            "applied": apply,
        }
        result["products"] = await ProductItem.filter(category_id__in=list(redirects)).using_db(conn).count()
        result["templates"] = await ProductTemplate.filter(category_id__in=list(redirects)).using_db(conn).count()
        if not apply:
            return result

        before = [
            await model.all().using_db(conn).count() for model in (ProductItem, ProductTemplate, ProductSpecAttribute)
        ]
        for source, target in redirects.items():
            await ProductItem.filter(category_id=source).using_db(conn).update(category_id=target)
            await ProductTemplate.filter(category_id=source).using_db(conn).update(category_id=target)
        for attribute in await ProductSpecAttribute.all().using_db(conn).select_for_update():
            ids = list(dict.fromkeys(redirects.get(int(value), int(value)) for value in (attribute.category_ids or [])))
            primary = redirects.get(attribute.category_id, attribute.category_id)
            if ids != attribute.category_ids or primary != attribute.category_id:
                await ProductSpecAttribute.filter(id=attribute.id).using_db(conn).update(
                    category_id=primary, category_ids=ids
                )
        for child, parent in moves.items():
            await ProductCategory.filter(id=child).using_db(conn).update(parent_id=parent)
        # Children are merged/deleted before their source parents to prevent cascade loss.
        for source in reversed(redirects):
            if await ProductCategory.filter(parent_id=source).using_db(conn).exists():
                raise ValueError("Source category still has children; transaction rolled back")
            await ProductCategory.filter(id=source).using_db(conn).delete()
        after = [
            await model.all().using_db(conn).count() for model in (ProductItem, ProductTemplate, ProductSpecAttribute)
        ]
        if before != after:
            raise ValueError("Business record counts changed; transaction rolled back")
        return result


async def main(apply):
    try:
        await Tortoise.init(config=settings.TORTOISE_ORM)
        print(json.dumps(await merge_categories(apply), ensure_ascii=True))
    except Exception as exc:
        # Connection failures must not expose DSNs or credentials.
        print(f"Category merge failed: {type(exc).__name__}", file=sys.stderr)
        raise SystemExit(1) from None
    finally:
        await Tortoise.close_connections()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Apply the reviewed merge in one transaction")
    asyncio.run(main(parser.parse_args().apply))
