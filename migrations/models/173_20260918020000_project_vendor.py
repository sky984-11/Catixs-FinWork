from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "customer_project" ADD "project_type" VARCHAR(20) NOT NULL DEFAULT 'customer';
        ALTER TABLE "customer_project" ADD "vendor_id" BIGINT
            REFERENCES "company" ("id") ON DELETE SET NULL;
    """


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "customer_project" DROP COLUMN "vendor_id";
        ALTER TABLE "customer_project" DROP COLUMN "project_type";
    """
