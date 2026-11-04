from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
    CREATE TABLE "product_order" (
        "id" BIGSERIAL NOT NULL PRIMARY KEY,
        "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
        "updated_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
        "order_no" VARCHAR(40) NOT NULL UNIQUE,
        "name" VARCHAR(160) NOT NULL,
        "remark" TEXT,
        "customer_id" BIGINT NOT NULL REFERENCES "crm_customer" ("id") ON DELETE RESTRICT
    );
    CREATE INDEX "idx_order_created" ON "product_order" ("created_at");
    CREATE INDEX "idx_order_updated" ON "product_order" ("updated_at");
    CREATE TABLE "product_order_item" (
        "id" BIGSERIAL NOT NULL PRIMARY KEY,
        "quantity" INT NOT NULL CHECK ("quantity" BETWEEN 1 AND 1000000),
        "position" INT NOT NULL DEFAULT 0,
        "order_id" BIGINT NOT NULL REFERENCES "product_order" ("id") ON DELETE CASCADE,
        "product_id" BIGINT NOT NULL REFERENCES "product_item" ("id") ON DELETE RESTRICT,
        CONSTRAINT "uid_order_product" UNIQUE ("order_id", "product_id")
    );
    CREATE INDEX "idx_order_customer" ON "product_order" ("customer_id");
    CREATE INDEX "idx_order_item_product" ON "product_order_item" ("product_id");
    """


async def downgrade(db: BaseDBAsyncClient) -> str:
    return 'DROP TABLE "product_order_item"; DROP TABLE "product_order";'
