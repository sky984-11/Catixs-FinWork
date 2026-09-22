from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return 'ALTER TABLE "remote_engineer" ADD "billing_rules" JSONB;'


async def downgrade(db: BaseDBAsyncClient) -> str:
    return 'ALTER TABLE "remote_engineer" DROP COLUMN "billing_rules";'
