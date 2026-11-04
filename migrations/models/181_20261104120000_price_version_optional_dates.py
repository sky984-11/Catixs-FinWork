from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "product_price_version" ALTER COLUMN "effective_date" DROP NOT NULL;
        ALTER TABLE "product_price_version" ALTER COLUMN "expiry_date" DROP NOT NULL;"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "product_price_version" ALTER COLUMN "effective_date" SET NOT NULL;
        ALTER TABLE "product_price_version" ALTER COLUMN "expiry_date" SET NOT NULL;"""
