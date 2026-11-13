from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
CREATE TABLE "monitor_event_config" (
    "id" BIGSERIAL NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "revision" INT NOT NULL  DEFAULT 1,
    "categories" JSONB NOT NULL,
    "hosts" JSONB NOT NULL,
    "updated_by_id" BIGINT NOT NULL
);
CREATE INDEX "idx_monitor_eve_created_261798" ON "monitor_event_config" ("created_at");
CREATE INDEX "idx_monitor_eve_updated_38da38" ON "monitor_event_config" ("updated_at");
"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return 'DROP TABLE IF EXISTS "monitor_event_config";'
