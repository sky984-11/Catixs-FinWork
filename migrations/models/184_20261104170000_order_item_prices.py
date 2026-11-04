from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
    ALTER TABLE "product_order_item"
        ADD COLUMN "price_version_id" BIGINT,
        ADD COLUMN "price_version_number" INT,
        ADD COLUMN "currency" VARCHAR(12),
        ADD COLUMN "period_months" INT,
        ADD COLUMN "billing_unit" VARCHAR(40),
        ADD COLUMN "base_mrc" DECIMAL(16,2),
        ADD COLUMN "base_nrc" DECIMAL(16,2),
        ADD COLUMN "mrc" DECIMAL(16,2),
        ADD COLUMN "nrc" DECIMAL(16,2);
    """


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
    ALTER TABLE "product_order_item"
        DROP COLUMN "price_version_id", DROP COLUMN "price_version_number", DROP COLUMN "currency",
        DROP COLUMN "period_months", DROP COLUMN "billing_unit", DROP COLUMN "base_mrc",
        DROP COLUMN "base_nrc", DROP COLUMN "mrc", DROP COLUMN "nrc";
    """
