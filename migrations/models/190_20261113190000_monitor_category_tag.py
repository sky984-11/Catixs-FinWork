from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """ALTER TABLE "monitor_event_config" ADD COLUMN IF NOT EXISTS "category_tag" VARCHAR(255) NOT NULL  DEFAULT 'business_category';"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return 'ALTER TABLE "monitor_event_config" DROP COLUMN IF EXISTS "category_tag";'
