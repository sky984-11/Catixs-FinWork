from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return 'ALTER TABLE "remote_hands" ADD "billing_data" JSONB;'


async def downgrade(db: BaseDBAsyncClient) -> str:
    return 'ALTER TABLE "remote_hands" DROP COLUMN "billing_data";'
