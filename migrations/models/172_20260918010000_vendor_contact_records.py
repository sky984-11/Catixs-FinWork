from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS "vendor_contact" (
    "id" BIGSERIAL NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "contact_type" VARCHAR(20) NOT NULL  DEFAULT 'person',
    "name" VARCHAR(100) NOT NULL  DEFAULT '',
    "roles" JSONB NOT NULL,
    "email" VARCHAR(200) NOT NULL  DEFAULT '',
    "phone" VARCHAR(100) NOT NULL  DEFAULT '',
    "address" VARCHAR(500) NOT NULL  DEFAULT '',
    "remark" TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS "idx_vendor_cont_created_49aed0" ON "vendor_contact" ("created_at");
CREATE INDEX IF NOT EXISTS "idx_vendor_cont_updated_f99d77" ON "vendor_contact" ("updated_at");
        CREATE TABLE IF NOT EXISTS "vendor_contact_link" (
    "id" BIGSERIAL NOT NULL PRIMARY KEY,
    "contact_id" BIGINT NOT NULL REFERENCES "vendor_contact" ("id") ON DELETE CASCADE,
    "vendor_id" BIGINT NOT NULL REFERENCES "company" ("id") ON DELETE RESTRICT,
    CONSTRAINT "uid_vendor_cont_contact_5a66e2" UNIQUE ("contact_id", "vendor_id")
);"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        DROP TABLE IF EXISTS "vendor_contact_link";
        DROP TABLE IF EXISTS "vendor_contact";"""
