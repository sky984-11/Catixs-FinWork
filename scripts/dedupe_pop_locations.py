import asyncio
import re
import sys
from pathlib import Path

from tortoise import Tortoise
from tortoise.transactions import in_transaction

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.models.asset import AssetCabinet, AssetDevice, AssetInventory, AssetLocation, AssetRegion
from app.settings.config import settings


COUNTRIES = {
    "Australia": "澳大利亚",
    "Canada": "加拿大",
    "China": "中国",
    "France": "法国",
    "Germany": "德国",
    "Hong Kong": "中国",
    "India": "印度",
    "Japan": "日本",
    "Singapore": "新加坡",
    "South Korea": "韩国",
    "Taiwan": "中国",
    "UAE": "阿联酋",
    "UK": "英国",
    "United Kingdom": "英国",
    "US": "美国",
    "USA": "美国",
    "United States": "美国",
}

CITIES = {
    "Amsterdam": "阿姆斯特丹",
    "Ashburn": "阿什本",
    "Chicago": "芝加哥",
    "Dallas": "达拉斯",
    "Frankfurt": "法兰克福",
    "Hong Kong": "香港",
    "London": "伦敦",
    "Los Angeles": "洛杉矶",
    "Manchester": "曼彻斯特",
    "New York": "纽约",
    "Osaka": "大阪",
    "San Jose": "圣何塞",
    "Seattle": "西雅图",
    "Seoul": "首尔",
    "Shanghai": "上海",
    "Shenzhen": "深圳",
    "Singapore": "新加坡",
    "Taipei": "台湾",
    "Tokyo": "东京",
    "Washington": "华盛顿",
    "Westmont": "韦斯特蒙特",
}


def text(value) -> str:
    return str(value or "").strip()


def canonical_country(value: str) -> str:
    raw = text(value)
    return COUNTRIES.get(raw, raw)


def canonical_city(value: str) -> str:
    raw = text(value)
    return CITIES.get(raw, raw)


def normalize_key(value: str) -> str:
    return re.sub(r"[^0-9a-zA-Z\u4e00-\u9fff]+", "", text(value).lower())


def region_key(region: AssetRegion) -> tuple[str, str]:
    return canonical_country(region.country), canonical_city(region.city)


def location_key(location: AssetLocation) -> str:
    name = text(location.name)
    remark = text(location.remark)
    code_match = re.search(r"POP代码:\s*([^|]+)", remark)
    if code_match:
        return f"code:{normalize_key(code_match.group(1))}"
    return f"name:{normalize_key(name)}"


async def merge_region_group(rows: list[AssetRegion], stats: dict) -> AssetRegion:
    rows = sorted(rows, key=lambda item: (0 if item.status else 1, item.id))
    keep = rows[0]
    country, city = region_key(keep)
    keep.country = country
    keep.city = city
    keep.name = " / ".join(part for part in [country, city] if part)
    await keep.save()

    for duplicate in rows[1:]:
        await AssetLocation.filter(region_id=duplicate.id).update(region_id=keep.id)
        await AssetDevice.filter(region_id=duplicate.id).update(region_id=keep.id)
        await AssetInventory.filter(region_id=duplicate.id).update(region_id=keep.id)
        await duplicate.delete()
        stats["regions_merged"] += 1
    return keep


async def merge_location_group(rows: list[AssetLocation], stats: dict) -> AssetLocation:
    rows = sorted(rows, key=lambda item: (0 if item.status else 1, item.id))
    keep = rows[0]
    for duplicate in rows[1:]:
        await AssetCabinet.filter(location_id=duplicate.id).update(location_id=keep.id)
        await AssetDevice.filter(location_id=duplicate.id).update(location_id=keep.id)
        await AssetInventory.filter(location_id=duplicate.id).update(location_id=keep.id)
        await duplicate.delete()
        stats["locations_merged"] += 1
    return keep


async def dedupe() -> dict:
    stats = {"region_groups": 0, "regions_merged": 0, "location_groups": 0, "locations_merged": 0}
    async with in_transaction():
        regions = await AssetRegion.all().order_by("country", "city", "id")
        groups: dict[tuple[str, str], list[AssetRegion]] = {}
        for region in regions:
            key = region_key(region)
            if all(key):
                groups.setdefault(key, []).append(region)
        for rows in groups.values():
            if len(rows) > 1:
                stats["region_groups"] += 1
                await merge_region_group(rows, stats)

        locations = await AssetLocation.filter(type=1).all().order_by("region_id", "name", "id")
        location_groups: dict[tuple[int, str], list[AssetLocation]] = {}
        for location in locations:
            key = (location.region_id, location_key(location))
            if key[1] not in {"name:", "code:"}:
                location_groups.setdefault(key, []).append(location)
        for rows in location_groups.values():
            if len(rows) > 1:
                stats["location_groups"] += 1
                await merge_location_group(rows, stats)
    return stats


async def main() -> None:
    await Tortoise.init(config=settings.TORTOISE_ORM)
    try:
        stats = await dedupe()
        print(stats)
    finally:
        await Tortoise.close_connections()


if __name__ == "__main__":
    asyncio.run(main())
