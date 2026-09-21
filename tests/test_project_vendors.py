import importlib
import json
import sqlite3
import unittest
from contextlib import closing
from unittest.mock import AsyncMock, patch

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from tortoise import Tortoise

from app.api.v1 import v1_router
from app.core.ctx import CTX_USER_ID
from app.core.dependency import AuthControl
from app.models.admin import User
from app.models.company import Company
from app.models.customer_center import CrmCustomer
from app.models.project import CustomerProject
from app.services.project_task_notifier import get_project_party
from app.utils.feishu_app import build_project_due_card


class ProjectVendorTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        await Tortoise.init(db_url="sqlite://:memory:", modules={"models": ["app.models"]})
        await Tortoise.generate_schemas()
        self.user = await User.create(username="project-test", email="project@example.test", is_superuser=True)
        self.vendor = await Company.create(name="Test Vendor", role=2)
        self.customer = await CrmCustomer.create(name="Test Customer")
        self.app = FastAPI()
        self.app.include_router(v1_router, prefix="/api/v1")

        async def authed():
            CTX_USER_ID.set(self.user.id)
            return self.user

        self.app.dependency_overrides[AuthControl.is_authed] = authed
        self.client = AsyncClient(transport=ASGITransport(app=self.app), base_url="http://test/api/v1")
        self.notification = patch("app.api.v1.projects.projects.notify_project_created", new_callable=AsyncMock)
        self.notification.start()

    async def asyncTearDown(self):
        self.notification.stop()
        await self.client.aclose()
        await Tortoise.close_connections()

    async def create(self, **kwargs):
        return await self.client.post("/project/create", json={"name": "Project", "owner": "project-test", **kwargs})

    async def update(self, project_id, **kwargs):
        return await self.client.post(
            "/project/update", json={"id": project_id, "name": "Project", "owner": "project-test", **kwargs}
        )

    async def test_completed_progress_on_create_update_status_and_legacy_read(self):
        response = await self.create(status="completed", progress=12)
        project_id = response.json()["data"]["id"]
        self.assertEqual(response.json()["data"]["progress"], 100)
        self.assertEqual((await CustomerProject.get(id=project_id)).progress, 100)
        response = await self.update(project_id, status="completed", progress=20)
        self.assertEqual(response.json()["data"]["progress"], 100)
        await self.update(project_id, status="active", progress=30)
        response = await self.client.post("/project/status", json={"id": project_id, "status": "completed", "sort_order": 1})
        self.assertEqual(response.json()["data"]["progress"], 100)
        await CustomerProject.filter(id=project_id).update(progress=10)
        response = await self.client.get("/project/get", params={"project_id": project_id})
        self.assertEqual(response.json()["data"]["progress"], 100)

    async def test_vendor_create_detail_update_and_filter(self):
        response = await self.create(project_type="vendor", vendor_id=self.vendor.id)
        self.assertEqual(response.json()["code"], 200, response.text)
        project_id = response.json()["data"]["id"]
        detail = (await self.client.get("/project/get", params={"project_id": project_id})).json()["data"]
        self.assertEqual(detail["vendor_name"], "Test Vendor")
        self.assertIsNone(detail["customer_id"])
        response = await self.update(project_id, progress=35)
        self.assertEqual(response.json()["data"]["vendor_id"], self.vendor.id)
        self.assertEqual(response.json()["data"]["project_type"], "vendor")
        # SQLite does not support the existing JSON contains access filter; capture the ORM query.
        with patch(
            "app.api.v1.projects.projects.customer_project_controller.list_projects", new_callable=AsyncMock
        ) as rows:
            rows.return_value = (0, [])
            response = await self.client.get(
                "/project/list", params={"project_type": "vendor", "vendor_id": self.vendor.id}
            )
            self.assertEqual(response.status_code, 200)
            query = CustomerProject.filter(rows.call_args.kwargs["search"]).sql()
            self.assertIn('"vendor_id"', query)
            self.assertIn('"project_type"', query)

    async def test_customer_compatibility_and_switching_clears_old_links(self):
        response = await self.create(customer_id=self.customer.id)
        self.assertEqual(response.json()["data"]["project_type"], "customer")
        project_id = response.json()["data"]["id"]
        legacy = await Company.create(name="Legacy Customer", role=1)
        await CustomerProject.filter(id=project_id).update(customer_id=legacy.id)
        response = await self.update(project_id, project_type="vendor", vendor_id=self.vendor.id)
        self.assertEqual(response.json()["code"], 200, response.text)
        project = await CustomerProject.get(id=project_id)
        self.assertIsNone(project.customer_id)
        self.assertIsNone(project.crm_customer_id)
        response = await self.update(project_id, project_type="customer", customer_id=self.customer.id)
        self.assertIsNone(response.json()["data"]["vendor_id"])
        self.assertEqual(response.json()["data"]["customer_name"], "Test Customer")
        legacy_project = await CustomerProject.create(name="Legacy", owner="project-test", customer_id=legacy.id)
        response = await self.update(legacy_project.id, customer_id=None)
        self.assertEqual(response.json()["data"]["customer_name"], "Legacy Customer")

    async def test_invalid_party_and_permission(self):
        internal = await Company.create(name="Internal", role=0)
        for payload in (
            {"project_type": "vendor"},
            {"project_type": "vendor", "vendor_id": 999999},
            {"project_type": "vendor", "vendor_id": internal.id},
            {"project_type": "vendor", "vendor_id": self.vendor.id, "customer_id": self.customer.id},
            {"vendor_id": self.vendor.id},
        ):
            self.assertEqual((await self.create(**payload)).status_code, 400)
        self.assertEqual((await self.create(project_type="invalid")).status_code, 422)
        self.assertEqual(await CustomerProject.all().count(), 0)
        project_id = (await self.create(project_type="vendor", vendor_id=self.vendor.id)).json()["data"]["id"]
        self.user = await User.create(username="other", email="other@example.test", is_superuser=True)
        self.assertEqual((await self.update(project_id, progress=50)).status_code, 403)
        self.assertEqual((await self.client.get("/project/get", params={"project_id": project_id})).status_code, 403)
        self.user.is_superuser = False
        self.assertEqual((await self.create(project_type="vendor", vendor_id=self.vendor.id)).status_code, 403)
        self.app.dependency_overrides.clear()
        self.assertIn((await self.create()).status_code, (401, 422))

    async def test_notification_party_and_deleted_vendor(self):
        project = await CustomerProject.create(name="Vendor project", project_type="vendor", vendor_id=self.vendor.id)
        label, name = await get_project_party(project)
        self.assertEqual((label, name), ("供应商", "Test Vendor"))
        card = build_project_due_card(
            stage="due", project_name=project.name, due_date="2026-09-18", customer_name=name, party_label=label
        )
        self.assertIn("供应商", json.dumps(card, ensure_ascii=False))
        await self.vendor.delete()
        await project.refresh_from_db()
        self.assertEqual(project.project_type, "vendor")
        self.assertIsNone(project.vendor_id)

    async def test_migration_preserves_existing_projects(self):
        migration = importlib.import_module("migrations.models.173_20260918020000_project_vendor")
        with closing(sqlite3.connect(":memory:")) as db:
            db.executescript(
                "CREATE TABLE company (id BIGINT PRIMARY KEY); CREATE TABLE customer_project (id BIGINT);"
                "INSERT INTO customer_project VALUES (1);"
            )
            db.executescript(await migration.upgrade(None))
            self.assertEqual(
                db.execute("SELECT project_type, vendor_id FROM customer_project").fetchone(), ("customer", None)
            )
            db.executescript(await migration.downgrade(None))
            self.assertEqual(db.execute("SELECT * FROM customer_project").fetchall(), [(1,)])


if __name__ == "__main__":
    unittest.main()
