from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS "monitor_notification_config" (
    "id" BIGSERIAL NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "revision" INT NOT NULL  DEFAULT 0,
    "enabled" BOOL NOT NULL  DEFAULT False,
    "recipient_ids" JSONB NOT NULL,
    "category_keys" JSONB NOT NULL,
    "minimum_severity" INT NOT NULL  DEFAULT 2,
    "notify_recovery" BOOL NOT NULL  DEFAULT True,
    "skip_suppressed" BOOL NOT NULL  DEFAULT True,
    "ai_enabled" BOOL NOT NULL  DEFAULT True,
    "enabled_since" BIGINT NOT NULL  DEFAULT 0,
    "lease_until" BIGINT NOT NULL  DEFAULT 0,
    "lease_token" VARCHAR(36) NOT NULL  DEFAULT '',
    "last_poll_at" BIGINT NOT NULL  DEFAULT 0,
    "last_error" VARCHAR(300) NOT NULL  DEFAULT '',
    "updated_by_id" BIGINT NOT NULL  DEFAULT 0
);
CREATE INDEX IF NOT EXISTS "idx_monitor_not_created_9249c9" ON "monitor_notification_config" ("created_at");
CREATE INDEX IF NOT EXISTS "idx_monitor_not_updated_c6963c" ON "monitor_notification_config" ("updated_at");
        CREATE TABLE IF NOT EXISTS "monitor_notification_delivery" (
    "id" BIGSERIAL NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "event_id" VARCHAR(20) NOT NULL,
    "phase" VARCHAR(10) NOT NULL,
    "user_id" BIGINT NOT NULL,
    "status" VARCHAR(16) NOT NULL  DEFAULT 'pending',
    "attempts" INT NOT NULL  DEFAULT 0,
    "message" VARCHAR(300) NOT NULL  DEFAULT '',
    "event_name" VARCHAR(255) NOT NULL  DEFAULT '',
    "advice" TEXT NOT NULL,
    "advice_source" VARCHAR(16) NOT NULL  DEFAULT 'rule',
    "sent_at" BIGINT NOT NULL  DEFAULT 0,
    "recovery_done" BOOL NOT NULL  DEFAULT False,
    CONSTRAINT "uid_monitor_not_event_i_a4f3d1" UNIQUE ("event_id", "phase", "user_id")
);
CREATE INDEX IF NOT EXISTS "idx_monitor_not_created_ea2a82" ON "monitor_notification_delivery" ("created_at");
CREATE INDEX IF NOT EXISTS "idx_monitor_not_updated_f2ae38" ON "monitor_notification_delivery" ("updated_at");
CREATE INDEX IF NOT EXISTS "idx_monitor_not_event_i_fe55d6" ON "monitor_notification_delivery" ("event_id");
CREATE INDEX IF NOT EXISTS "idx_monitor_not_user_id_2a7401" ON "monitor_notification_delivery" ("user_id");
CREATE INDEX IF NOT EXISTS "idx_monitor_not_status_094c8b" ON "monitor_notification_delivery" ("status");"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        DROP TABLE IF EXISTS "monitor_notification_delivery";
        DROP TABLE IF EXISTS "monitor_notification_config";"""
