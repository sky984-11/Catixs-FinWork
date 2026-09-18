import shutil
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import AsyncMock, patch

from aerich import Command
from aerich.migrate import Migrate
from aerich.models import Aerich
from tortoise import Tortoise
from tortoise.exceptions import OperationalError

from app.core import init_app
from app.models.project import CustomerProject


class ProjectStartupTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.config = {
            "connections": {"default": "sqlite://:memory:"},
            "apps": {"models": {"models": ["app.models", "aerich.models"], "default_connection": "default"}},
        }
        await Tortoise.init(config=self.config)
        await Tortoise.generate_schemas()
        await CustomerProject.create(name="Existing customer project", owner="owner")
        self.conn = Tortoise.get_connection("default")
        # Reproduce an existing project table from before the supplier feature.
        await self.conn.execute_script(
            "ALTER TABLE customer_project DROP COLUMN vendor_id;"
            "ALTER TABLE customer_project DROP COLUMN project_type;"
        )
        self.temp = tempfile.TemporaryDirectory()
        self.version = "173_20260918020000_project_vendor.py"
        shutil.copyfile(Path("migrations/models") / self.version, Path(self.temp.name) / self.version)
        self.command = Command(tortoise_config=self.config)
        self.stack = ExitStack()
        self.stack.enter_context(patch.object(Migrate, "migrate_location", self.temp.name, create=True))
        self.stack.enter_context(patch.object(init_app, "Command", return_value=self.command))
        self.stack.enter_context(patch.object(self.command, "init", new_callable=AsyncMock))
        self.stack.enter_context(patch.object(self.command, "init_db", side_effect=FileExistsError))
        self.stack.enter_context(patch.dict("os.environ", {"AUTO_DB_MIGRATE": "false"}))
        # Keep unrelated startup repairs out of this isolated migration test.
        for name in (
            "ensure_pre_schema_columns",
            "ensure_user_columns",
            "ensure_company_columns",
            "ensure_customer_center_columns",
            "ensure_product_center_columns",
            "ensure_asset_columns",
            "ensure_pve_node_binding_table",
            "ensure_cloud_dhcp_tables",
            "ensure_bill_columns",
            "ensure_project_columns",
            "ensure_requirement_columns",
            "ensure_ticket_columns",
            "ensure_finance_quote_columns",
            "ensure_remote_assistance_datetime_columns",
            "ensure_tg_assistant_tables",
            "ensure_billing_product_templates",
        ):
            self.stack.enter_context(patch.object(init_app, name, new_callable=AsyncMock))
        self.stack.enter_context(
            patch("app.controllers.vendor_attachments.ensure_vendor_columns", new_callable=AsyncMock)
        )

    async def asyncTearDown(self):
        self.stack.close()
        self.temp.cleanup()
        await Tortoise.close_connections()

    async def test_pending_migration_runs_before_schema_generation_and_only_once(self):
        generate = Tortoise.generate_schemas

        async def check_columns_then_generate(**kwargs):
            # PostgreSQL schema generation requires these columns for COMMENT ON COLUMN.
            await self.conn.execute_query("SELECT project_type, vendor_id FROM customer_project LIMIT 1")
            await generate(**kwargs)

        with patch.object(Tortoise, "generate_schemas", side_effect=check_columns_then_generate) as schemas:
            await init_app.init_db()
            await init_app.init_db()
        self.assertEqual(schemas.call_count, 2)
        self.assertEqual(await Aerich.filter(version=self.version).count(), 1)
        project = await CustomerProject.get(name="Existing customer project")
        self.assertEqual(project.project_type, "customer")
        self.assertIsNone(project.vendor_id)
        self.assertEqual(init_app.ensure_billing_product_templates.await_count, 2)

    async def test_migration_failure_is_not_hidden_by_schema_generation(self):
        with (
            patch.object(self.command, "upgrade", side_effect=OperationalError("migration failed")),
            patch.object(Tortoise, "generate_schemas", new_callable=AsyncMock) as schemas,
        ):
            with self.assertRaisesRegex(OperationalError, "migration failed"):
                await init_app.init_db()
            schemas.assert_not_awaited()
            init_app.ensure_billing_product_templates.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
