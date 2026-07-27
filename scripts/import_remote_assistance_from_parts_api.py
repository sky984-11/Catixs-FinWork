import argparse
import asyncio
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx
from tortoise import Tortoise, connections

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.models.remote_assistance import RemoteEngineer, RemoteHands
from app.settings.config import settings


SCHEMA_SQL = """
    CREATE TABLE IF NOT EXISTS "remote_engineer" (
        "id" BIGSERIAL NOT NULL PRIMARY KEY,
        "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
        "updated_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
        "source_id" BIGINT UNIQUE,
        "name" VARCHAR(100) NOT NULL,
        "contact" VARCHAR(180),
        "wechat_id" VARCHAR(180),
        "wechat_group" VARCHAR(180),
        "region" VARCHAR(500),
        "is_active" INT NOT NULL DEFAULT 1,
        "note" TEXT
    );
    ALTER TABLE "remote_engineer" ADD COLUMN IF NOT EXISTS "source_id" BIGINT UNIQUE;
    CREATE INDEX IF NOT EXISTS "idx_remote_engineer_source_id" ON "remote_engineer" ("source_id");
    CREATE INDEX IF NOT EXISTS "idx_remote_engineer_name" ON "remote_engineer" ("name");
    CREATE INDEX IF NOT EXISTS "idx_remote_engineer_region" ON "remote_engineer" ("region");
    CREATE INDEX IF NOT EXISTS "idx_remote_engineer_active" ON "remote_engineer" ("is_active");

    CREATE TABLE IF NOT EXISTS "remote_hands" (
        "id" BIGSERIAL NOT NULL PRIMARY KEY,
        "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
        "updated_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
        "source_id" BIGINT UNIQUE,
        "customer" VARCHAR(200) NOT NULL,
        "ticket" VARCHAR(120),
        "engineer_id" BIGINT REFERENCES "remote_engineer" ("id") ON DELETE SET NULL,
        "engineer_name" VARCHAR(100),
        "engineer_contact" VARCHAR(180),
        "engineer_wechat" VARCHAR(180),
        "engineer_group" VARCHAR(180),
        "region" VARCHAR(180),
        "site" VARCHAR(180),
        "rack" VARCHAR(100),
        "timezone" VARCHAR(80) NOT NULL DEFAULT 'Asia/Shanghai',
        "arrived_at" TIMESTAMPTZ,
        "left_at" TIMESTAMPTZ,
        "work_minutes" INT NOT NULL DEFAULT 0,
        "status" VARCHAR(30) NOT NULL DEFAULT 'scheduled',
        "ops_settlement_status" VARCHAR(30) NOT NULL DEFAULT 'unbilled',
        "customer_settlement_status" VARCHAR(30) NOT NULL DEFAULT 'unbilled',
        "note" TEXT
    );
    ALTER TABLE "remote_hands" ADD COLUMN IF NOT EXISTS "source_id" BIGINT UNIQUE;
    CREATE INDEX IF NOT EXISTS "idx_remote_hands_source_id" ON "remote_hands" ("source_id");
    CREATE INDEX IF NOT EXISTS "idx_remote_hands_customer" ON "remote_hands" ("customer");
    CREATE INDEX IF NOT EXISTS "idx_remote_hands_ticket" ON "remote_hands" ("ticket");
    CREATE INDEX IF NOT EXISTS "idx_remote_hands_engineer_id" ON "remote_hands" ("engineer_id");
    CREATE INDEX IF NOT EXISTS "idx_remote_hands_engineer_name" ON "remote_hands" ("engineer_name");
    CREATE INDEX IF NOT EXISTS "idx_remote_hands_region" ON "remote_hands" ("region");
    CREATE INDEX IF NOT EXISTS "idx_remote_hands_site" ON "remote_hands" ("site");
    CREATE INDEX IF NOT EXISTS "idx_remote_hands_arrived_at" ON "remote_hands" ("arrived_at");
    CREATE INDEX IF NOT EXISTS "idx_remote_hands_left_at" ON "remote_hands" ("left_at");
    CREATE INDEX IF NOT EXISTS "idx_remote_hands_status" ON "remote_hands" ("status");
    CREATE INDEX IF NOT EXISTS "idx_remote_hands_ops_settlement" ON "remote_hands" ("ops_settlement_status");
    CREATE INDEX IF NOT EXISTS "idx_remote_hands_customer_settlement" ON "remote_hands" ("customer_settlement_status");
"""


def clean(value: Any) -> str:
    return str(value or "").strip()


def parse_datetime(value: Any) -> datetime | None:
    text = clean(value)
    if not text:
        return None
    for candidate in [text, text.replace("Z", "+00:00"), text.replace(" ", "T")]:
        try:
            return datetime.fromisoformat(candidate).replace(tzinfo=None)
        except ValueError:
            continue
    return None


def response_data(payload: Any) -> Any:
    if isinstance(payload, dict):
        value = payload.get("data", payload)
        if isinstance(value, dict):
            for key in ("items", "records", "list", "results", "rows", "data"):
                if isinstance(value.get(key), list):
                    return value[key]
        return value
    return payload


def as_list(payload: Any) -> list[dict[str, Any]]:
    value = response_data(payload)
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    if isinstance(value, dict):
        return [value]
    return []


def api_url(base_url: str, path: str) -> str:
    normalized = path.lstrip("/")
    base = base_url.rstrip("/")
    if normalized.startswith("api/"):
        return f"{base}/{normalized}"
    return f"{base}/api/{normalized}"


async def login(client: httpx.AsyncClient, args: argparse.Namespace) -> str:
    if args.token:
        return args.token.removeprefix("Bearer ").strip()
    response = await client.post(
        api_url(args.url, "login"),
        json={"username": args.username, "password": args.password},
    )
    response.raise_for_status()
    payload = response.json()
    data = payload.get("data") if isinstance(payload, dict) else None
    token = clean(
        (payload.get("token") if isinstance(payload, dict) else "")
        or (data.get("token") if isinstance(data, dict) else "")
    )
    if not token:
        raise RuntimeError("login succeeded, but token is missing from response")
    return token


async def get_json(client: httpx.AsyncClient, args: argparse.Namespace, token: str, path: str) -> Any:
    response = await client.get(
        api_url(args.url, path),
        headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
    )
    response.raise_for_status()
    return response.json()


def source_id(row: dict[str, Any]) -> int | None:
    value = row.get("id") or row.get("source_id")
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


async def upsert_engineer(row: dict[str, Any]) -> RemoteEngineer:
    sid = source_id(row)
    data = {
        "source_id": sid,
        "name": clean(row.get("name") or row.get("engineer_name")) or f"Engineer-{sid or 'unknown'}",
        "contact": clean(row.get("contact") or row.get("engineer_contact")) or None,
        "wechat_id": clean(row.get("wechat_id") or row.get("engineer_wechat")) or None,
        "wechat_group": clean(row.get("wechat_group") or row.get("engineer_group")) or None,
        "region": clean(row.get("region") or row.get("regions")) or None,
        "is_active": int(row.get("is_active") if row.get("is_active") is not None else 1),
        "note": clean(row.get("note") or row.get("remark")) or None,
    }

    item = await RemoteEngineer.filter(source_id=sid).first() if sid else None
    if not item:
        item = await RemoteEngineer.filter(name=data["name"], contact=data["contact"]).first()
    if item:
        await RemoteEngineer.filter(id=item.id).update(**data)
        return await RemoteEngineer.get(id=item.id)
    return await RemoteEngineer.create(**data)


async def upsert_remote_hands(row: dict[str, Any], engineer_id_map: dict[int, int]) -> RemoteHands:
    sid = source_id(row)
    old_engineer_id = source_id({"id": row.get("engineer_id")})
    engineer_id = engineer_id_map.get(old_engineer_id) if old_engineer_id else None
    data = {
        "source_id": sid,
        "customer": clean(row.get("customer")) or "-",
        "ticket": clean(row.get("ticket")) or None,
        "engineer_id": engineer_id,
        "engineer_name": clean(row.get("engineer_name")) or None,
        "engineer_contact": clean(row.get("engineer_contact")) or None,
        "engineer_wechat": clean(row.get("engineer_wechat")) or None,
        "engineer_group": clean(row.get("engineer_group")) or None,
        "region": clean(row.get("region")) or None,
        "site": clean(row.get("site")) or None,
        "rack": clean(row.get("rack")) or None,
        "timezone": clean(row.get("timezone")) or "Asia/Shanghai",
        "arrived_at": parse_datetime(row.get("arrived_at")),
        "left_at": parse_datetime(row.get("left_at")),
        "work_minutes": int(row.get("work_minutes") or 0),
        "status": clean(row.get("status")) or "scheduled",
        "ops_settlement_status": clean(
            row.get("ops_settlement_status")
            or row.get("operation_settlement_status")
            or row.get("ops_billing_status")
        )
        or "unbilled",
        "customer_settlement_status": clean(
            row.get("customer_settlement_status") or row.get("customer_billing_status")
        )
        or "unbilled",
        "note": clean(row.get("note") or row.get("remark")) or None,
    }

    item = await RemoteHands.filter(source_id=sid).first() if sid else None
    if not item:
        query = RemoteHands.filter(
            customer=data["customer"],
            ticket=data["ticket"],
            engineer_name=data["engineer_name"],
            arrived_at=data["arrived_at"],
        )
        item = await query.first()
    if item:
        await RemoteHands.filter(id=item.id).update(**data)
        return await RemoteHands.get(id=item.id)
    return await RemoteHands.create(**data)


async def import_data(args: argparse.Namespace) -> None:
    await Tortoise.init(config=settings.TORTOISE_ORM)
    connection_name = next(iter(settings.TORTOISE_ORM["connections"].keys()))
    await connections.get(connection_name).execute_script(SCHEMA_SQL)
    try:
        timeout = httpx.Timeout(args.timeout)
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            token = await login(client, args)
            engineers = as_list(await get_json(client, args, token, "engineers"))
            remote_hands = as_list(await get_json(client, args, token, "remote-hands"))

        engineer_id_map: dict[int, int] = {}
        for row in engineers:
            item = await upsert_engineer(row)
            sid = source_id(row)
            if sid:
                engineer_id_map[sid] = int(item.id)

        remote_count = 0
        for row in remote_hands:
            await upsert_remote_hands(row, engineer_id_map)
            remote_count += 1

        print(f"imported_engineers={len(engineers)}")
        print(f"imported_remote_hands={remote_count}")
        print(f"total_engineers={await RemoteEngineer.all().count()}")
        print(f"total_remote_hands={await RemoteHands.all().count()}")
    finally:
        await Tortoise.close_connections()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import remote assistance data from the legacy parts API.")
    parser.add_argument("--url", required=True, help="Legacy API base URL, for example https://example.com")
    parser.add_argument("--token", default="", help="Bearer token. If omitted, username/password login is used.")
    parser.add_argument("--username", default="", help="Legacy API username")
    parser.add_argument("--password", default="", help="Legacy API password")
    parser.add_argument("--timeout", type=float, default=30)
    return parser.parse_args()


if __name__ == "__main__":
    asyncio.run(import_data(parse_args()))
