from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS "cloud_resource_snapshot" (
            "id" BIGSERIAL PRIMARY KEY,
            "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            "updated_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            "key" VARCHAR(40) NOT NULL UNIQUE,
            "payload" JSONB NOT NULL DEFAULT '{}',
            "synced_at" TIMESTAMPTZ,
            "attempted_at" TIMESTAMPTZ,
            "lease_until" TIMESTAMPTZ,
            "dirty" BOOL NOT NULL DEFAULT TRUE,
            "error" TEXT NOT NULL DEFAULT ''
        );
    """


async def downgrade(db: BaseDBAsyncClient) -> str:
    return 'DROP TABLE IF EXISTS "cloud_resource_snapshot";'
