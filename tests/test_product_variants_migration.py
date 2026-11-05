"""Opt-in PostgreSQL migration test; all fixtures live in a rolled-back private schema."""

import importlib
import os
import unittest
from uuid import uuid4

from asyncpg.exceptions import RaiseError
from tortoise import Tortoise
from tortoise.transactions import in_transaction

from app.settings.config import settings


class RollbackFixtures(Exception):
    pass


@unittest.skipUnless(os.getenv("FINWORK_TEST_POSTGRES_MIGRATION") == "1", "Requires explicit PostgreSQL test opt-in")
class ProductVariantMigrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_upgrade_preserves_history_and_downgrade_guards_multi_variant_orders(self):
        migration = importlib.import_module("migrations.models.185_20261105120000_product_variants")
        await Tortoise.init(config=settings.TORTOISE_ORM)
        try:
            for constraint in ("uid_order_product", "uid_product_ord_order_i_legacy"):
                schema = "fw_variant_test_" + uuid4().hex
                try:
                    async with in_transaction() as conn:
                        await conn.execute_script(f'CREATE SCHEMA "{schema}"; SET LOCAL search_path TO "{schema}";')
                        await conn.execute_script(
                            f"""
                            CREATE TABLE product_item (id BIGINT PRIMARY KEY, name VARCHAR(160), status VARCHAR(30), spec_values JSONB);
                            CREATE TABLE product_spec_attribute (id BIGINT PRIMARY KEY, name TEXT, unit TEXT);
                            CREATE TABLE product_price_version (id BIGINT PRIMARY KEY, product_id BIGINT REFERENCES product_item(id), mrc DECIMAL(16,2));
                            CREATE TABLE product_order_item (id BIGINT PRIMARY KEY, order_id BIGINT, product_id BIGINT REFERENCES product_item(id), mrc DECIMAL(16,2),
                                CONSTRAINT {constraint} UNIQUE (order_id, product_id));
                            INSERT INTO product_item VALUES (1, 'Legacy server', 'active', '{{"10":128}}');
                            INSERT INTO product_spec_attribute VALUES (10, 'Memory', 'GB');
                            INSERT INTO product_price_version VALUES (2, 1, 100.25);
                            INSERT INTO product_order_item VALUES (3, 4, 1, 90.25);
                        """
                        )
                        await conn.execute_script(await migration.upgrade(conn))
                        _, rows = await conn.execute_query(
                            """
                            SELECT i.mrc::text AS price, i.product_name_snapshot AS name, i.variant_id,
                                i.spec_snapshot->0->>'value' AS memory, p.variant_id AS price_variant
                            FROM product_order_item i JOIN product_price_version p ON p.product_id=i.product_id
                        """
                        )
                        self.assertEqual(rows[0]["price"], "90.25")
                        self.assertEqual(rows[0]["name"], "Legacy server")
                        self.assertEqual(rows[0]["memory"], "128")
                        self.assertEqual(rows[0]["variant_id"], rows[0]["price_variant"])
                        await conn.execute_script(
                            """
                            INSERT INTO product_variant (product_id, name, code) VALUES (1, '256GB', 'SKU256');
                            INSERT INTO product_order_item (id, order_id, product_id, variant_id) VALUES
                                (5, 4, 1, (SELECT id FROM product_variant WHERE code='SKU256'));
                            SAVEPOINT before_downgrade;
                        """
                        )
                        with self.assertRaises(RaiseError):
                            await conn.execute_script(await migration.downgrade(conn))
                        await conn.execute_script(
                            "ROLLBACK TO SAVEPOINT before_downgrade; DELETE FROM product_order_item WHERE id=5;"
                        )
                        await conn.execute_script(await migration.downgrade(conn))
                        _, rows = await conn.execute_query("SELECT mrc::text AS price FROM product_order_item")
                        self.assertEqual(rows[0]["price"], "90.25")
                        raise RollbackFixtures()
                except RollbackFixtures:
                    pass
        finally:
            await Tortoise.close_connections()
