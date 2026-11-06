from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
CREATE TABLE "crm_billing_document" (
    "id" BIGSERIAL NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "request_key" VARCHAR(80) NOT NULL UNIQUE,
    "request_hash" VARCHAR(64) NOT NULL,
    "created_by_id" BIGINT NOT NULL,
    "customer_snapshot" JSONB NOT NULL,
    "lines" JSONB NOT NULL,
    "settings" JSONB NOT NULL,
    "period_start" DATE NOT NULL,
    "period_end" DATE NOT NULL,
    "subtotal" DECIMAL(16,2) NOT NULL,
    "discount" DECIMAL(16,2) NOT NULL  DEFAULT 0,
    "adjustment" DECIMAL(16,2) NOT NULL  DEFAULT 0,
    "tax_rate" DECIMAL(7,4) NOT NULL  DEFAULT 0,
    "tax_amount" DECIMAL(16,2) NOT NULL  DEFAULT 0,
    "paid_amount" DECIMAL(16,2) NOT NULL  DEFAULT 0,
    "local_currency" VARCHAR(12) NOT NULL,
    "fx_rate" DECIMAL(18,8) NOT NULL  DEFAULT 1,
    "fx_source" VARCHAR(160) NOT NULL,
    "fx_date" DATE NOT NULL,
    "local_amount" DECIMAL(16,2) NOT NULL,
    "issued_at" TIMESTAMPTZ,
    "reminder_level" INT NOT NULL  DEFAULT 0,
    "bill_id" BIGINT NOT NULL UNIQUE REFERENCES "crm_customer_bill" ("id") ON DELETE RESTRICT
);
CREATE INDEX "idx_crm_billing_created_52a842" ON "crm_billing_document" ("created_at");
CREATE INDEX "idx_crm_billing_updated_220a0c" ON "crm_billing_document" ("updated_at");
CREATE TABLE "crm_billing_plan" (
    "id" BIGSERIAL NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "name" VARCHAR(160) NOT NULL,
    "created_by_id" BIGINT NOT NULL,
    "template" JSONB NOT NULL,
    "order_snapshot" JSONB NOT NULL,
    "next_period" DATE NOT NULL,
    "next_run" DATE NOT NULL,
    "enabled" BOOL NOT NULL  DEFAULT True,
    "last_attempt" DATE,
    "last_error" VARCHAR(500) NOT NULL  DEFAULT '',
    "customer_id" BIGINT NOT NULL REFERENCES "crm_customer" ("id") ON DELETE RESTRICT
);
CREATE INDEX "idx_crm_billing_created_d0b7c7" ON "crm_billing_plan" ("created_at");
CREATE INDEX "idx_crm_billing_updated_d0ee83" ON "crm_billing_plan" ("updated_at");
CREATE INDEX "idx_crm_billing_next_ru_468cbb" ON "crm_billing_plan" ("next_run");
CREATE TABLE "crm_billing_plan_order" (
    "id" BIGSERIAL NOT NULL PRIMARY KEY,
    "order_id" BIGINT NOT NULL REFERENCES "product_order" ("id") ON DELETE RESTRICT,
    "plan_id" BIGINT NOT NULL REFERENCES "crm_billing_plan" ("id") ON DELETE RESTRICT,
    CONSTRAINT "uid_crm_billing_plan_id_8c2a20" UNIQUE ("plan_id", "order_id")
);
CREATE TABLE "crm_billing_allocation" (
    "id" BIGSERIAL NOT NULL PRIMARY KEY,
    "currency" VARCHAR(12) NOT NULL,
    "period_start" DATE NOT NULL,
    "period_end" DATE NOT NULL,
    "includes_nrc" BOOL NOT NULL  DEFAULT False,
    "document_id" BIGINT NOT NULL REFERENCES "crm_billing_document" ("id") ON DELETE RESTRICT,
    "order_id" BIGINT NOT NULL REFERENCES "product_order" ("id") ON DELETE RESTRICT,
    CONSTRAINT "uid_crm_billing_documen_a3bfd4" UNIQUE ("document_id", "order_id", "currency")
);
CREATE TABLE "crm_billing_payment" (
    "id" BIGSERIAL NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "reference" VARCHAR(100) NOT NULL,
    "payment_date" DATE NOT NULL,
    "amount" DECIMAL(16,2) NOT NULL,
    "currency" VARCHAR(12) NOT NULL,
    "method" VARCHAR(80) NOT NULL,
    "remark" VARCHAR(500) NOT NULL  DEFAULT '',
    "reversed" BOOL NOT NULL  DEFAULT False,
    "operator_id" BIGINT NOT NULL,
    "document_id" BIGINT NOT NULL REFERENCES "crm_billing_document" ("id") ON DELETE RESTRICT,
    CONSTRAINT "uid_crm_billing_documen_19a88f" UNIQUE ("document_id", "reference")
);
CREATE INDEX "idx_crm_billing_created_d9129d" ON "crm_billing_payment" ("created_at");
CREATE INDEX "idx_crm_billing_updated_a5e80b" ON "crm_billing_payment" ("updated_at");
CREATE TABLE "crm_billing_audit" (
    "id" BIGSERIAL NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "action" VARCHAR(40) NOT NULL,
    "operator_id" BIGINT NOT NULL,
    "operator_name" VARCHAR(100) NOT NULL,
    "before" JSONB NOT NULL,
    "after" JSONB NOT NULL,
    "comment" VARCHAR(500) NOT NULL  DEFAULT '',
    "document_id" BIGINT NOT NULL REFERENCES "crm_billing_document" ("id") ON DELETE RESTRICT
);
CREATE INDEX "idx_crm_billing_created_e26b1f" ON "crm_billing_audit" ("created_at");
CREATE INDEX "idx_crm_billing_updated_a6553f" ON "crm_billing_audit" ("updated_at");
    """


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
DROP TABLE "crm_billing_audit";
DROP TABLE "crm_billing_payment";
DROP TABLE "crm_billing_allocation";
DROP TABLE "crm_billing_plan_order";
DROP TABLE "crm_billing_plan";
DROP TABLE "crm_billing_document";
    """
