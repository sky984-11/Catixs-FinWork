from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
    CREATE TABLE "product_variant" (
        "id" BIGSERIAL PRIMARY KEY,
        "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
        "updated_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
        "product_id" BIGINT NOT NULL REFERENCES "product_item" ("id") ON DELETE RESTRICT,
        "name" VARCHAR(160) NOT NULL,
        "code" VARCHAR(80) NOT NULL UNIQUE,
        "status" VARCHAR(30) NOT NULL DEFAULT 'active',
        "spec_values" JSONB NOT NULL DEFAULT '{}',
        "spec_snapshot" JSONB NOT NULL DEFAULT '[]',
        CONSTRAINT "uid_variant_product_name" UNIQUE ("product_id", "name")
    );
    CREATE INDEX "idx_variant_created" ON "product_variant" ("created_at");
    CREATE INDEX "idx_variant_updated" ON "product_variant" ("updated_at");
    INSERT INTO "product_variant" ("product_id", "name", "code", "status", "spec_values", "spec_snapshot")
    SELECT p.id, '默认组合', 'LEGACY-' || p.id, p.status, COALESCE(p.spec_values, '{}'),
        COALESCE((SELECT jsonb_agg(jsonb_build_object('id', a.id, 'name', a.name,
            'unit', a.unit, 'value', s.value) ORDER BY a.id)
            FROM jsonb_each(COALESCE(p.spec_values, '{}')) s
            JOIN product_spec_attribute a ON a.id::text = s.key), '[]')
    FROM product_item p;
    ALTER TABLE "product_price_version" ADD COLUMN "variant_id" BIGINT
        REFERENCES "product_variant" ("id") ON DELETE RESTRICT;
    UPDATE "product_price_version" p SET variant_id = v.id FROM product_variant v WHERE v.product_id = p.product_id;
    ALTER TABLE "product_order_item"
        ADD COLUMN "variant_id" BIGINT REFERENCES "product_variant" ("id") ON DELETE RESTRICT,
        ADD COLUMN "product_name_snapshot" VARCHAR(160),
        ADD COLUMN "variant_name" VARCHAR(160),
        ADD COLUMN "variant_code" VARCHAR(80),
        ADD COLUMN "spec_snapshot" JSONB NOT NULL DEFAULT '[]';
    UPDATE product_order_item i SET variant_id = v.id, product_name_snapshot = p.name,
        variant_name = v.name, variant_code = v.code, spec_snapshot = v.spec_snapshot
        FROM product_variant v JOIN product_item p ON p.id = v.product_id WHERE i.product_id = v.product_id;
    DO $$ DECLARE c RECORD; BEGIN
        FOR c IN SELECT conname FROM pg_constraint WHERE conrelid = 'product_order_item'::regclass
            AND contype = 'u' AND pg_get_constraintdef(oid) = 'UNIQUE (order_id, product_id)'
        LOOP EXECUTE format('ALTER TABLE product_order_item DROP CONSTRAINT %I', c.conname); END LOOP;
    END $$;
    ALTER TABLE product_order_item ADD CONSTRAINT uid_order_product_variant UNIQUE (order_id, product_id, variant_id);
    CREATE INDEX idx_price_variant ON product_price_version (variant_id);
    CREATE INDEX idx_order_variant ON product_order_item (variant_id);
    """


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
    DO $$ BEGIN
        IF EXISTS (SELECT 1 FROM product_order_item GROUP BY order_id, product_id HAVING COUNT(*) > 1) THEN
            RAISE EXCEPTION 'Cannot downgrade orders containing multiple variants of the same product';
        END IF;
    END $$;
    ALTER TABLE product_order_item DROP CONSTRAINT uid_order_product_variant;
    ALTER TABLE product_order_item ADD CONSTRAINT uid_order_product UNIQUE (order_id, product_id);
    ALTER TABLE product_order_item DROP COLUMN variant_id, DROP COLUMN product_name_snapshot,
        DROP COLUMN variant_name, DROP COLUMN variant_code, DROP COLUMN spec_snapshot;
    ALTER TABLE product_price_version DROP COLUMN variant_id;
    DROP TABLE product_variant;
    """
