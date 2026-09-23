import importlib.util
import unittest
from pathlib import Path

from tortoise import Tortoise


class CustomerMaintenanceMigrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_plan_quote_upgrade_preserves_existing_plans(self):
        await Tortoise.init(db_url="sqlite://:memory:", modules={"models": []})
        try:
            db = Tortoise.get_connection("default")
            await db.execute_script('CREATE TABLE "remote_hands_plan" (id BIGINT PRIMARY KEY, customer VARCHAR(100));'
                                    'INSERT INTO "remote_hands_plan" VALUES (1, \'Existing\');')
            path = Path(__file__).resolve().parents[1] / "migrations/models/178_20260923150000_plan_maintenance_quote.py"
            spec = importlib.util.spec_from_file_location("plan_quote_migration", path)
            migration = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(migration)
            await db.execute_script(await migration.upgrade(db))
            row = (await db.execute_query_dict('SELECT * FROM "remote_hands_plan"'))[0]
            self.assertEqual(row["customer"], "Existing")
            self.assertIsNone(row["customer_pricing"])
            await db.execute_script(await migration.downgrade(db))
            self.assertEqual((await db.execute_query_dict('SELECT * FROM "remote_hands_plan"'))[0],
                             {"id": 1, "customer": "Existing"})
        finally:
            await Tortoise.close_connections()

    async def test_upgrade_and_downgrade_preserve_existing_names(self):
        await Tortoise.init(db_url="sqlite://:memory:", modules={"models": []})
        try:
            db = Tortoise.get_connection("default")
            for table in ["crm_customer", "remote_hands", "remote_hands_plan"]:
                await db.execute_script(
                    f'CREATE TABLE "{table}" (id BIGINT PRIMARY KEY, name VARCHAR(100));'
                    f"INSERT INTO \"{table}\" VALUES (1, 'Existing');"
                )
            path = (
                Path(__file__).resolve().parents[1]
                / "migrations/models/177_20260923120000_customer_maintenance_price.py"
            )
            spec = importlib.util.spec_from_file_location("customer_price_migration", path)
            migration = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(migration)
            await db.execute_script(await migration.upgrade(db))
            row = (await db.execute_query_dict('SELECT * FROM "crm_customer"'))[0]
            self.assertEqual(row["name"], "Existing")
            self.assertEqual(row["maintenance_currency"], "USD")
            self.assertIsNone(row["maintenance_hourly_rate"])
            await db.execute_script(await migration.downgrade(db))
            for table in ["crm_customer", "remote_hands", "remote_hands_plan"]:
                row = (await db.execute_query_dict(f'SELECT * FROM "{table}"'))[0]
                self.assertEqual(row, {"id": 1, "name": "Existing"})
        finally:
            await Tortoise.close_connections()
