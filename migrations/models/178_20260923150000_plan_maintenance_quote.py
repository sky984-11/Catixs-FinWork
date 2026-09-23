from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return 'ALTER TABLE "remote_hands_plan" ADD "customer_pricing" JSONB;'


async def downgrade(db: BaseDBAsyncClient) -> str:
    return 'ALTER TABLE "remote_hands_plan" DROP COLUMN "customer_pricing";'
