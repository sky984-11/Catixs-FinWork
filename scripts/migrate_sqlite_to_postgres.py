import argparse
import asyncio
import json
import sqlite3
import sys
from collections import defaultdict, deque
from datetime import date, datetime
from pathlib import Path
from typing import Any

import asyncpg
from tortoise import Tortoise

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.settings import settings


def quote_ident(name: str) -> str:
    return f'"{name.replace(chr(34), chr(34) + chr(34))}"'


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Migrate the local SQLite database to PostgreSQL.")
    parser.add_argument("--sqlite-path", default=settings.SQLITE_DB_PATH, help="Source SQLite database path.")
    parser.add_argument("--postgres-dsn", default=settings.POSTGRES_DSN, help="Target PostgreSQL DSN.")
    parser.add_argument("--postgres-host", default=settings.POSTGRES_HOST, help="Target PostgreSQL host.")
    parser.add_argument("--postgres-port", type=int, default=settings.POSTGRES_PORT, help="Target PostgreSQL port.")
    parser.add_argument("--postgres-user", default=settings.POSTGRES_USER, help="Target PostgreSQL user.")
    parser.add_argument("--postgres-password", default=settings.POSTGRES_PASSWORD, help="Target PostgreSQL password.")
    parser.add_argument("--postgres-database", default=settings.POSTGRES_DATABASE, help="Target PostgreSQL database.")
    parser.add_argument("--postgres-ssl", action="store_true", default=settings.POSTGRES_SSL, help="Use SSL for PostgreSQL.")
    parser.add_argument(
        "--truncate",
        action="store_true",
        help="Truncate target tables before copying. Without this, migration refuses non-empty target tables.",
    )
    parser.add_argument("--skip-schema", action="store_true", help="Do not generate target PostgreSQL schema first.")
    return parser.parse_args()


def sqlite_tables(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute(
        "select name from sqlite_master where type = 'table' and name not like 'sqlite_%' order by name"
    ).fetchall()
    return [row[0] for row in rows]


def sqlite_columns(conn: sqlite3.Connection, table: str) -> list[str]:
    return [row[1] for row in conn.execute(f"pragma table_info({quote_ident(table)})").fetchall()]


def sqlite_foreign_key_order(conn: sqlite3.Connection, tables: list[str]) -> list[str]:
    table_set = set(tables)
    graph: dict[str, set[str]] = defaultdict(set)
    indegree = {table: 0 for table in tables}

    for table in tables:
        for row in conn.execute(f"pragma foreign_key_list({quote_ident(table)})").fetchall():
            dependency = row[2]
            if dependency not in table_set or dependency == table:
                continue
            if table not in graph[dependency]:
                graph[dependency].add(table)
                indegree[table] += 1

    queue = deque(table for table in tables if indegree[table] == 0)
    ordered: list[str] = []
    while queue:
        table = queue.popleft()
        ordered.append(table)
        for dependent in sorted(graph[table]):
            indegree[dependent] -= 1
            if indegree[dependent] == 0:
                queue.append(dependent)

    if len(ordered) != len(tables):
        unresolved = [table for table in tables if table not in ordered]
        ordered.extend(unresolved)
    return ordered


async def connect_postgres(args: argparse.Namespace) -> asyncpg.Connection:
    if args.postgres_dsn:
        return await asyncpg.connect(dsn=args.postgres_dsn, ssl=args.postgres_ssl)
    return await asyncpg.connect(
        host=args.postgres_host,
        port=args.postgres_port,
        user=args.postgres_user,
        password=args.postgres_password,
        database=args.postgres_database,
        ssl=args.postgres_ssl,
    )


async def generate_postgres_schema() -> None:
    await Tortoise.init(config=settings.build_tortoise_orm(default_connection="postgres"))
    try:
        await Tortoise.generate_schemas(safe=True)
    finally:
        await Tortoise.close_connections()


async def table_exists(pg: asyncpg.Connection, table: str) -> bool:
    return await pg.fetchval("select to_regclass($1)", f"public.{table}") is not None


async def target_column_types(pg: asyncpg.Connection, table: str) -> dict[str, str]:
    rows = await pg.fetch(
        """
        select column_name, data_type
        from information_schema.columns
        where table_schema = 'public' and table_name = $1
        """,
        table,
    )
    return {row["column_name"]: row["data_type"] for row in rows}


def parse_datetime(value: str, keep_timezone: bool) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is not None and not keep_timezone:
        return parsed.replace(tzinfo=None)
    return parsed


def convert_value(value: Any, data_type: str | None) -> Any:
    if value is None or data_type is None:
        return value
    if data_type == "boolean":
        return bool(value)
    if data_type == "date":
        if isinstance(value, date) and not isinstance(value, datetime):
            return value
        return date.fromisoformat(str(value)[:10])
    if data_type == "timestamp without time zone":
        if isinstance(value, datetime):
            return value.replace(tzinfo=None)
        return parse_datetime(str(value), keep_timezone=False)
    if data_type == "timestamp with time zone":
        if isinstance(value, datetime):
            return value
        return parse_datetime(str(value), keep_timezone=True)
    if data_type in {"json", "jsonb"} and not isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    return value


async def ensure_target_empty(pg: asyncpg.Connection, tables: list[str], truncate: bool) -> None:
    existing_tables = [table for table in tables if await table_exists(pg, table)]
    if truncate and existing_tables:
        joined = ", ".join(quote_ident(table) for table in existing_tables)
        await pg.execute(f"truncate table {joined} restart identity cascade")
        return

    non_empty = []
    for table in existing_tables:
        count = await pg.fetchval(f"select count(*) from {quote_ident(table)}")
        if count:
            non_empty.append(f"{table}({count})")

    if non_empty:
        raise RuntimeError(
            "Target PostgreSQL tables are not empty: "
            + ", ".join(non_empty)
            + ". Re-run with --truncate if you want to replace target data."
        )


async def reset_sequence(pg: asyncpg.Connection, table: str, columns: list[str]) -> None:
    if "id" not in columns:
        return
    sequence = await pg.fetchval("select pg_get_serial_sequence($1, $2)", f"public.{table}", "id")
    if not sequence:
        return
    max_id = await pg.fetchval(f"select max(id) from {quote_ident(table)}")
    if max_id is None:
        return
    await pg.execute("select setval($1, $2, true)", sequence, max_id)


async def copy_table(sqlite_conn: sqlite3.Connection, pg: asyncpg.Connection, table: str) -> int:
    if not await table_exists(pg, table):
        print(f"skip missing target table: {table}")
        return 0

    columns = sqlite_columns(sqlite_conn, table)
    if not columns:
        return 0

    column_types = await target_column_types(pg, table)
    source_rows = sqlite_conn.execute(
        f"select {', '.join(quote_ident(column) for column in columns)} from {quote_ident(table)}"
    ).fetchall()
    if not source_rows:
        await reset_sequence(pg, table, columns)
        return 0

    placeholders = ", ".join(f"${index}" for index in range(1, len(columns) + 1))
    statement = (
        f"insert into {quote_ident(table)} "
        f"({', '.join(quote_ident(column) for column in columns)}) values ({placeholders})"
    )
    values = [
        tuple(convert_value(row[column], column_types.get(column)) for column in columns)
        for row in source_rows
    ]
    await pg.executemany(statement, values)
    await reset_sequence(pg, table, columns)
    return len(values)


async def migrate(args: argparse.Namespace) -> None:
    sqlite_path = Path(args.sqlite_path)
    if not sqlite_path.exists():
        raise FileNotFoundError(f"SQLite database not found: {sqlite_path}")

    if not args.skip_schema:
        await generate_postgres_schema()

    sqlite_conn = sqlite3.connect(sqlite_path)
    sqlite_conn.row_factory = sqlite3.Row
    pg = await connect_postgres(args)
    try:
        tables = sqlite_tables(sqlite_conn)
        ordered_tables = sqlite_foreign_key_order(sqlite_conn, tables)
        await ensure_target_empty(pg, ordered_tables, truncate=args.truncate)

        async with pg.transaction():
            for table in ordered_tables:
                copied = await copy_table(sqlite_conn, pg, table)
                print(f"{table}: {copied} rows")
    finally:
        await pg.close()
        sqlite_conn.close()


if __name__ == "__main__":
    asyncio.run(migrate(parse_args()))
