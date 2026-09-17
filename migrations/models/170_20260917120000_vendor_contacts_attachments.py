from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "company" ADD COLUMN IF NOT EXISTS "billing_contact" TEXT;
        ALTER TABLE "company" ADD COLUMN IF NOT EXISTS "noc_contact" TEXT;
        ALTER TABLE "company" ADD COLUMN IF NOT EXISTS "sales_contact" TEXT;
        ALTER TABLE "company" ADD COLUMN IF NOT EXISTS "payment_terms" VARCHAR(200);
        CREATE TABLE IF NOT EXISTS "vendor_attachment" (
    "id" BIGSERIAL NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "owner_id" BIGINT NOT NULL,
    "filename" VARCHAR(255) NOT NULL,
    "stored_name" VARCHAR(64) NOT NULL UNIQUE,
    "content_type" VARCHAR(200) NOT NULL  DEFAULT 'application/octet-stream',
    "size" INT NOT NULL,
    "vendor_id" BIGINT REFERENCES "company" ("id") ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS "idx_vendor_atta_created_7d51cf" ON "vendor_attachment" ("created_at");
CREATE INDEX IF NOT EXISTS "idx_vendor_atta_updated_b32019" ON "vendor_attachment" ("updated_at");
CREATE INDEX IF NOT EXISTS "idx_vendor_atta_owner_i_ceb264" ON "vendor_attachment" ("owner_id");
COMMENT ON COLUMN "company"."billing_contact" IS '供应商账单联系信息';
COMMENT ON COLUMN "company"."noc_contact" IS '供应商NOC联系信息';
COMMENT ON COLUMN "company"."sales_contact" IS '供应商销售联系信息';
COMMENT ON COLUMN "company"."payment_terms" IS '供应商付款条件';"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "company" DROP COLUMN "billing_contact";
        ALTER TABLE "company" DROP COLUMN "noc_contact";
        ALTER TABLE "company" DROP COLUMN "sales_contact";
        ALTER TABLE "company" DROP COLUMN "payment_terms";
        DROP TABLE IF EXISTS "vendor_attachment";"""
