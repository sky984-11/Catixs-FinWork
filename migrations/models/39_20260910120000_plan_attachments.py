from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "remote_hands_plan"
        ADD COLUMN IF NOT EXISTS "attachments" JSONB NOT NULL DEFAULT '[]'::jsonb;
    """


async def downgrade(db: BaseDBAsyncClient) -> str:
    return 'ALTER TABLE "remote_hands_plan" DROP COLUMN IF EXISTS "attachments";'
