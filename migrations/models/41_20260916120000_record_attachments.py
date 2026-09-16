from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "remote_hands"
        ADD COLUMN IF NOT EXISTS "attachments" JSONB NOT NULL DEFAULT '[]'::jsonb;
    """


async def downgrade(db: BaseDBAsyncClient) -> str:
    return 'ALTER TABLE "remote_hands" DROP COLUMN IF EXISTS "attachments";'
