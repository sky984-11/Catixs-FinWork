from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
CREATE TABLE "resource_cost" (
    "id" BIGSERIAL NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "code" VARCHAR(80) NOT NULL UNIQUE,
    "category" VARCHAR(30) NOT NULL,
    "title" VARCHAR(255) NOT NULL,
    "revision" INT NOT NULL  DEFAULT 1,
    "enabled" BOOL NOT NULL  DEFAULT True,
    "vendor_id" BIGINT REFERENCES "company" ("id") ON DELETE RESTRICT
);
CREATE INDEX "idx_resource_co_created_333865" ON "resource_cost" ("created_at");
CREATE INDEX "idx_resource_co_updated_fa61a5" ON "resource_cost" ("updated_at");
CREATE INDEX "idx_resource_co_categor_f3285b" ON "resource_cost" ("category");
CREATE TABLE "resource_cost_version" (
    "id" BIGSERIAL NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "revision" INT NOT NULL,
    "data" JSONB NOT NULL,
    "created_by_id" BIGINT NOT NULL,
    "resource_id" BIGINT NOT NULL REFERENCES "resource_cost" ("id") ON DELETE RESTRICT,
    CONSTRAINT "uid_resource_co_resourc_cba4e9" UNIQUE ("resource_id", "revision")
);
CREATE INDEX "idx_resource_co_created_dddfb6" ON "resource_cost_version" ("created_at");
CREATE INDEX "idx_resource_co_updated_4ee38f" ON "resource_cost_version" ("updated_at");
CREATE TABLE "product_cost_link" (
    "id" BIGSERIAL NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "product_id" BIGINT NOT NULL REFERENCES "product_item" ("id") ON DELETE CASCADE,
    "resource_id" BIGINT NOT NULL REFERENCES "resource_cost" ("id") ON DELETE RESTRICT,
    "version_id" BIGINT NOT NULL REFERENCES "resource_cost_version" ("id") ON DELETE RESTRICT,
    CONSTRAINT "uid_product_cos_product_49fe13" UNIQUE ("product_id", "resource_id")
);
CREATE INDEX "idx_product_cos_created_42ac3a" ON "product_cost_link" ("created_at");
CREATE INDEX "idx_product_cos_updated_1ea291" ON "product_cost_link" ("updated_at");
"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
DROP TABLE IF EXISTS "product_cost_link";
DROP TABLE IF EXISTS "resource_cost_version";
DROP TABLE IF EXISTS "resource_cost";
"""
