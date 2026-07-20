import argparse
import asyncio
import json
import re
import sys
from pathlib import Path

from tortoise import Tortoise
from tortoise.transactions import in_transaction

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.models.asset import AssetLocation, AssetRegion  # noqa: E402
from app.settings.config import settings  # noqa: E402


DEFAULT_POPS_PATH = Path(r"C:\Users\LiuPeng\Downloads\catixs-api-production-pops.json")


def text(value) -> str:
    return str(value or "").strip()


def truncate(value: str, length: int) -> str:
    return text(value)[:length]


def normalize_code(value: str) -> str:
    code = re.sub(r"[^A-Z0-9-]+", "", text(value).upper())
    return truncate(code, 50)


def compact_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", text(value).lower())


def region_code(country_code: str, city_name: str, fallback_id: int | str) -> str:
    city_part = re.sub(r"[^A-Z0-9]+", "-", text(city_name).upper()).strip("-")
    base = "-".join(part for part in [normalize_code(country_code), city_part] if part) or f"POP-{fallback_id}"
    return truncate(base, 50)


def region_name(country_name: str, city_name: str) -> str:
    return truncate(" / ".join(part for part in [text(country_name), text(city_name)] if part), 100)


def location_name(pop: dict) -> str:
    code = normalize_code(pop.get("code"))
    name = text(pop.get("name"))
    if code and code.lower() not in name.lower():
        return truncate(f"{name} {code}".strip(), 100)
    return truncate(name or code, 100)


def location_remark(pop: dict, continent_name: str) -> str:
    parts = []
    provider = text(pop.get("provider"))
    pop_code = normalize_code(pop.get("code"))
    notes = text(pop.get("notes"))
    source_id = pop.get("id")
    if pop_code:
        parts.append(f"POP代码: {pop_code}")
    if provider:
        parts.append(f"供应商: {provider}")
    if continent_name:
        parts.append(f"大区: {continent_name}")
    if notes:
        parts.append(notes)
    if source_id is not None:
        parts.append(f"source=catixs-api.pop:{source_id}")
    return truncate(" | ".join(parts), 500)


def load_pops(path: Path) -> list[dict]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload.get("data"), list):
        return payload["data"]
    tables = payload.get("tables") or {}
    pops = tables.get("pops") or tables.get("datacenters") or []
    cities = {item.get("id"): item for item in tables.get("cities", [])}
    countries = {item.get("id"): item for item in tables.get("countries", [])}
    continents = {item.get("id"): item for item in tables.get("continents", [])}
    hydrated = []
    for pop in pops:
        city = cities.get(pop.get("city_id") or pop.get("cityId")) or {}
        country = countries.get(city.get("country_id") or city.get("countryId")) or {}
        continent = continents.get(country.get("continent_id") or country.get("continentId")) or {}
        hydrated.append({**pop, "city": city, "country": country, "continent": continent})
    return hydrated


def pop_status(pop: dict) -> bool:
    return text(pop.get("status")).lower() not in {"inactive", "disabled", "deleted", "archived"}


async def upsert_region(pop: dict, stats: dict) -> AssetRegion:
    city = pop.get("city") or {}
    country = pop.get("country") or {}
    city_name = text(city.get("name"))
    country_name = text(country.get("name"))
    country_code = text(country.get("code") or country.get("iso2"))
    code = region_code(country_code, city_name, city.get("id") or pop.get("cityId") or pop.get("city_id") or pop.get("id"))
    defaults = {
        "name": region_name(country_name, city_name) or code,
        "country": truncate(country_name, 100),
        "city": truncate(city_name, 100),
        "remark": truncate(f"source=catixs-api.country:{country.get('id') or ''};city:{city.get('id') or ''}", 500),
        "status": True,
    }
    region = await AssetRegion.get_or_none(code=code)
    if region:
        changed = False
        for field, value in defaults.items():
            if getattr(region, field) != value:
                setattr(region, field, value)
                changed = True
        if changed:
            await region.save()
            stats["regions_updated"] += 1
        return region
    stats["regions_created"] += 1
    return await AssetRegion.create(code=code, **defaults)


async def find_location(region: AssetRegion, pop: dict) -> AssetLocation | None:
    pop_code = normalize_code(pop.get("code"))
    source_token = f"source=catixs-api.pop:{pop.get('id')}"
    if pop.get("id") is not None:
        found = await AssetLocation.filter(type=1, remark__contains=source_token).first()
        if found:
            return found
    if pop_code:
        found = await AssetLocation.filter(region_id=region.id, type=1, remark__contains=f"POP代码: {pop_code}").first()
        if found:
            return found
    name = location_name(pop)
    return await AssetLocation.filter(region_id=region.id, type=1, name=name).first()


async def upsert_location(region: AssetRegion, pop: dict, stats: dict) -> AssetLocation:
    continent = pop.get("continent") or {}
    address = truncate(text(pop.get("address")), 255)
    defaults = {
        "region_id": region.id,
        "name": location_name(pop),
        "type": 1,
        "address": address,
        "remark": location_remark(pop, text(continent.get("name") or continent.get("code"))),
        "status": pop_status(pop),
    }
    location = await find_location(region, pop)
    if location:
        changed = False
        for field, value in defaults.items():
            if getattr(location, field) != value:
                setattr(location, field, value)
                changed = True
        if changed:
            await location.save()
            stats["locations_updated"] += 1
        return location
    stats["locations_created"] += 1
    return await AssetLocation.create(**defaults)


async def import_pops(path: Path) -> dict:
    pops = load_pops(path)
    stats = {
        "source_count": len(pops),
        "regions_created": 0,
        "regions_updated": 0,
        "locations_created": 0,
        "locations_updated": 0,
        "skipped": 0,
    }
    seen = set()
    async with in_transaction():
        for pop in pops:
            city = pop.get("city") or {}
            country = pop.get("country") or {}
            if not text(pop.get("name")) and not text(pop.get("code")):
                stats["skipped"] += 1
                continue
            key = (
                pop.get("id"),
                compact_key(country.get("name")),
                compact_key(city.get("name")),
                normalize_code(pop.get("code")),
                compact_key(pop.get("name")),
            )
            if key in seen:
                stats["skipped"] += 1
                continue
            seen.add(key)
            region = await upsert_region(pop, stats)
            await upsert_location(region, pop, stats)
    return stats


async def main() -> None:
    parser = argparse.ArgumentParser(description="Import production POP data into AssetRegion/AssetLocation.")
    parser.add_argument("json_path", nargs="?", default=str(DEFAULT_POPS_PATH), help="Path to production POP JSON export")
    args = parser.parse_args()
    path = Path(args.json_path)
    if not path.exists():
        raise SystemExit(f"File not found: {path}")
    await Tortoise.init(config=settings.TORTOISE_ORM)
    try:
        stats = await import_pops(path)
        print(json.dumps(stats, ensure_ascii=False, indent=2))
    finally:
        await Tortoise.close_connections()


if __name__ == "__main__":
    asyncio.run(main())
