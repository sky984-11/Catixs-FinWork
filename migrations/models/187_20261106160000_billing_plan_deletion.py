from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
    ALTER TABLE "crm_billing_plan"
        ADD COLUMN "deleted_at" TIMESTAMPTZ,
        ADD COLUMN "deleted_by_id" BIGINT,
        ADD COLUMN "deletion_reason" VARCHAR(500) NOT NULL DEFAULT '';
    """


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
    ALTER TABLE "crm_billing_plan"
        DROP COLUMN "deletion_reason", DROP COLUMN "deleted_by_id", DROP COLUMN "deleted_at";
    """
