from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "company" ADD COLUMN IF NOT EXISTS "signing_entity_id" BIGINT REFERENCES "crm_signing_entity" ("id") ON DELETE SET NULL;"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "company" DROP CONSTRAINT IF EXISTS "fk_company_crm_sign_aeba0b5d";
        ALTER TABLE "company" DROP COLUMN "signing_entity_id";"""
