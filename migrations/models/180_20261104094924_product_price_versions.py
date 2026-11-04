from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "product_item" ADD "billing_unit" VARCHAR(40) NOT NULL  DEFAULT 'month';
        ALTER TABLE "product_item" ADD "min_contract_months" INT NOT NULL  DEFAULT 1;
        CREATE TABLE IF NOT EXISTS "product_price_version" (
    "id" BIGSERIAL NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "customer_name" VARCHAR(160),
    "version" INT NOT NULL,
    "currency" VARCHAR(12) NOT NULL,
    "mrc" DECIMAL(16,2) NOT NULL,
    "nrc" DECIMAL(16,2) NOT NULL  DEFAULT 0,
    "period_months" INT NOT NULL  DEFAULT 1,
    "billing_unit" VARCHAR(40) NOT NULL,
    "effective_date" DATE NOT NULL,
    "expiry_date" DATE NOT NULL,
    "customer_id" BIGINT REFERENCES "crm_customer" ("id") ON DELETE RESTRICT,
    "product_id" BIGINT NOT NULL REFERENCES "product_item" ("id") ON DELETE RESTRICT,
    CONSTRAINT "uid_product_pri_product_423224" UNIQUE ("product_id", "version")
);
CREATE INDEX IF NOT EXISTS "idx_product_pri_created_91abc9" ON "product_price_version" ("created_at");
CREATE INDEX IF NOT EXISTS "idx_product_pri_updated_475140" ON "product_price_version" ("updated_at");
COMMENT ON COLUMN "product_item"."billing_unit" IS '计费单位';
COMMENT ON COLUMN "product_item"."min_contract_months" IS '最短合同期（月）';
COMMENT ON COLUMN "product_price_version"."customer_name" IS '客户名称快照';
COMMENT ON COLUMN "product_price_version"."version" IS '产品内版本号';
COMMENT ON COLUMN "product_price_version"."currency" IS '币种';
COMMENT ON COLUMN "product_price_version"."mrc" IS '每单位月费';
COMMENT ON COLUMN "product_price_version"."nrc" IS '一次性开通费';
COMMENT ON COLUMN "product_price_version"."period_months" IS '计费周期（月）';
COMMENT ON COLUMN "product_price_version"."billing_unit" IS '计费单位快照';
COMMENT ON COLUMN "product_price_version"."effective_date" IS '生效日（含）';
COMMENT ON COLUMN "product_price_version"."expiry_date" IS '失效日（不含）';"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "product_item" DROP COLUMN "billing_unit";
        ALTER TABLE "product_item" DROP COLUMN "min_contract_months";
        DROP TABLE IF EXISTS "product_price_version";"""
