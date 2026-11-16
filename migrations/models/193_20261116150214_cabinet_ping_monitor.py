from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS "cabinet_monitor_config" (
    "id" BIGSERIAL NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "enabled" BOOL NOT NULL  DEFAULT False,
    "revision" INT NOT NULL  DEFAULT 0,
    "template_id" VARCHAR(20) NOT NULL  DEFAULT '',
    "group_id" VARCHAR(20) NOT NULL  DEFAULT '',
    "proxy_id" VARCHAR(20) NOT NULL  DEFAULT '',
    "overrides" JSONB NOT NULL,
    "lease_until" BIGINT NOT NULL  DEFAULT 0,
    "lease_token" VARCHAR(36) NOT NULL  DEFAULT '',
    "last_checked" BIGINT NOT NULL  DEFAULT 0,
    "last_error" VARCHAR(300) NOT NULL  DEFAULT ''
);
CREATE INDEX IF NOT EXISTS "idx_cabinet_mon_created_21cdc3" ON "cabinet_monitor_config" ("created_at");
CREATE INDEX IF NOT EXISTS "idx_cabinet_mon_updated_d95b04" ON "cabinet_monitor_config" ("updated_at");
        CREATE TABLE IF NOT EXISTS "cabinet_monitor_target" (
    "id" BIGSERIAL NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "target_key" VARCHAR(64) NOT NULL UNIQUE,
    "metadata" JSONB NOT NULL,
    "host_id" VARCHAR(20) NOT NULL  DEFAULT '',
    "item_ids" JSONB NOT NULL,
    "status" VARCHAR(20) NOT NULL  DEFAULT 'pending',
    "reason" VARCHAR(300) NOT NULL  DEFAULT '',
    "active" BOOL NOT NULL  DEFAULT True,
    "notified" JSONB NOT NULL,
    "notification_error" VARCHAR(300) NOT NULL  DEFAULT '',
    "checked_at" BIGINT NOT NULL  DEFAULT 0
);
CREATE INDEX IF NOT EXISTS "idx_cabinet_mon_created_05e6e6" ON "cabinet_monitor_target" ("created_at");
CREATE INDEX IF NOT EXISTS "idx_cabinet_mon_updated_8cf95a" ON "cabinet_monitor_target" ("updated_at");"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        DROP TABLE IF EXISTS "cabinet_monitor_target";
        DROP TABLE IF EXISTS "cabinet_monitor_config";"""
