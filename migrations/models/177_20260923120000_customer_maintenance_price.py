from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "crm_customer" ADD "maintenance_hourly_rate" DECIMAL(12,2);
        ALTER TABLE "crm_customer" ADD "maintenance_currency" VARCHAR(12) NOT NULL DEFAULT 'USD';
        ALTER TABLE "remote_hands" ADD "customer_id" BIGINT;
        ALTER TABLE "remote_hands_plan" ADD "customer_id" BIGINT;
        CREATE INDEX "idx_remote_hands_customer_id" ON "remote_hands" ("customer_id");
        CREATE INDEX "idx_remote_hands_plan_customer_id" ON "remote_hands_plan" ("customer_id");
    """


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        DROP INDEX "idx_remote_hands_plan_customer_id";
        DROP INDEX "idx_remote_hands_customer_id";
        ALTER TABLE "remote_hands_plan" DROP COLUMN "customer_id";
        ALTER TABLE "remote_hands" DROP COLUMN "customer_id";
        ALTER TABLE "crm_customer" DROP COLUMN "maintenance_currency";
        ALTER TABLE "crm_customer" DROP COLUMN "maintenance_hourly_rate";
    """
