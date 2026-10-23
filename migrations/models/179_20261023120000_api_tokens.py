from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    if db.capabilities.dialect == "sqlite":
        return """
CREATE TABLE IF NOT EXISTS "api_token" (
    "id" INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    "created_at" TIMESTAMP NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "name" VARCHAR(100) NOT NULL  /* 令牌名称 */,
    "description" VARCHAR(500) NOT NULL  DEFAULT '' /* 用途说明 */,
    "token_hash" VARCHAR(64) NOT NULL UNIQUE /* SHA-256 摘要 */,
    "is_enabled" INT NOT NULL  DEFAULT 1,
    "expires_at" TIMESTAMP   /* 为空表示永久有效 */,
    "last_used_at" TIMESTAMP,
    "created_by_id" BIGINT REFERENCES "user" ("id") ON DELETE SET NULL,
    "user_id" BIGINT NOT NULL REFERENCES "user" ("id") ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS "idx_api_token_created_8ba0a0" ON "api_token" ("created_at");
CREATE INDEX IF NOT EXISTS "idx_api_token_updated_9b21e0" ON "api_token" ("updated_at");
"""
    return """
CREATE TABLE IF NOT EXISTS "api_token" (
    "id" BIGSERIAL NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "name" VARCHAR(100) NOT NULL,
    "description" VARCHAR(500) NOT NULL  DEFAULT '',
    "token_hash" VARCHAR(64) NOT NULL UNIQUE,
    "is_enabled" BOOL NOT NULL  DEFAULT True,
    "expires_at" TIMESTAMPTZ,
    "last_used_at" TIMESTAMPTZ,
    "created_by_id" BIGINT REFERENCES "user" ("id") ON DELETE SET NULL,
    "user_id" BIGINT NOT NULL REFERENCES "user" ("id") ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS "idx_api_token_created_8ba0a0" ON "api_token" ("created_at");
CREATE INDEX IF NOT EXISTS "idx_api_token_updated_9b21e0" ON "api_token" ("updated_at");
COMMENT ON COLUMN "api_token"."name" IS '令牌名称';
COMMENT ON COLUMN "api_token"."description" IS '用途说明';
COMMENT ON COLUMN "api_token"."token_hash" IS 'SHA-256 摘要';
COMMENT ON COLUMN "api_token"."expires_at" IS '为空表示永久有效';
"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return 'DROP TABLE IF EXISTS "api_token";'
