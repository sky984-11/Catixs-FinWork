from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS "device_secret_unlock_attempt" (
    "id" BIGSERIAL NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "user_id" BIGINT NOT NULL UNIQUE,
    "window_start" BIGINT NOT NULL  DEFAULT 0,
    "attempts" INT NOT NULL  DEFAULT 0
);
CREATE INDEX IF NOT EXISTS "idx_device_secr_created_c81fdf" ON "device_secret_unlock_attempt" ("created_at");
CREATE INDEX IF NOT EXISTS "idx_device_secr_updated_093d69" ON "device_secret_unlock_attempt" ("updated_at");"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        DROP TABLE IF EXISTS "device_secret_unlock_attempt";"""
