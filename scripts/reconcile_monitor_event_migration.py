"""Validate an existing migration-189 table, then optionally reconcile its Aerich record."""

# ruff: noqa: E402 -- standalone script imports the repository after setting its path.
import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aerich import Command
from aerich.models import Aerich
from aerich.utils import get_app_connection_name, get_models_describe
from tortoise import Tortoise
from tortoise.transactions import in_transaction

from app.settings.config import settings

VERSION = "189_20261113180000_monitor_event_config.py"
EXPECTED = {
    "id": "bigint",
    "created_at": "timestamp with time zone",
    "updated_at": "timestamp with time zone",
    "revision": "integer",
    "categories": "jsonb",
    "hosts": "jsonb",
    "updated_by_id": "bigint",
}
INDEXES = {"idx_monitor_eve_created_261798": "created_at", "idx_monitor_eve_updated_38da38": "updated_at"}


def validate_schema(columns, indexes, primary_key):
    if {c["column_name"]: c["data_type"] for c in columns} != EXPECTED:
        raise ValueError("Column names/types differ from migration 189; refusing to mark it applied")
    if any(c["is_nullable"] != "NO" for c in columns):
        raise ValueError("Column nullability differs from migration 189")
    defaults = {c["column_name"]: c["column_default"] for c in columns}
    if not str(defaults["id"]).startswith("nextval(") or defaults["revision"] != "1":
        raise ValueError("ID sequence or revision default differs from migration 189")
    if any(defaults[key] not in ("CURRENT_TIMESTAMP", "now()") for key in ("created_at", "updated_at")):
        raise ValueError("Timestamp defaults differ from migration 189")
    if any(defaults[key] is not None for key in ("categories", "hosts", "updated_by_id")):
        raise ValueError("Unexpected column defaults")
    if primary_key != "PRIMARY KEY (id)":
        raise ValueError("Primary key differs from migration 189")
    for name, column in INDEXES.items():
        if not any(i["indexname"] == name and i["indexdef"].endswith(f" USING btree ({column})") for i in indexes):
            raise ValueError(f"Missing or incompatible migration index: {name}")


async def reconcile(apply=False):
    command = Command(tortoise_config=settings.TORTOISE_ORM)
    await command.init()
    try:
        pending = await command.heads()
        if VERSION not in pending:
            return {"status": "already_recorded", "version": VERSION}
        if any(int(version.split("_", 1)[0]) < 189 for version in pending):
            raise ValueError("Earlier migrations are pending; resolve them before reconciling 189")
        name = get_app_connection_name(settings.TORTOISE_ORM, "models")
        async with in_transaction(name) as conn:
            if conn.capabilities.dialect != "postgres":
                raise ValueError("This repair only supports PostgreSQL")
            await conn.execute_script(
                'LOCK TABLE "aerich" IN EXCLUSIVE MODE; LOCK TABLE "monitor_event_config" IN SHARE MODE;'
            )
            columns = await conn.execute_query_dict(
                "SELECT column_name,data_type,is_nullable,column_default FROM information_schema.columns WHERE table_schema=current_schema() AND table_name='monitor_event_config'"
            )
            indexes = await conn.execute_query_dict(
                "SELECT indexname,indexdef FROM pg_indexes WHERE schemaname=current_schema() AND tablename='monitor_event_config'"
            )
            keys = await conn.execute_query_dict(
                "SELECT pg_get_constraintdef(oid) AS definition FROM pg_constraint WHERE conrelid='monitor_event_config'::regclass AND contype='p'"
            )
            validate_schema(columns, indexes, keys[0]["definition"] if len(keys) == 1 else "")
            if apply and not await Aerich.filter(version=VERSION, app="models").using_db(conn).exists():
                await Aerich.create(version=VERSION, app="models", content=get_models_describe("models"), using_db=conn)
            return {"status": "reconciled" if apply else "validated_no_changes", "version": VERSION}
    finally:
        await Tortoise.close_connections()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Record migration only after validating existing schema")
    print(json.dumps(asyncio.run(reconcile(parser.parse_args().apply))))
