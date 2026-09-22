import importlib.util
import unittest
from pathlib import Path

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError
from tortoise import Tortoise

from app.api.v1 import v1_router
from app.core.dependency import AuthControl
from app.models.admin import Api, Role, User
from app.models.remote_assistance import RemoteEngineer
from app.schemas.remote_billing import EngineerBillingRules


RULES = {
    "currency": "CNY",
    "tiers": [
        {"up_to_minutes": 60, "hourly_rate": "120.00"},
        {"up_to_minutes": None, "hourly_rate": "90.00"},
    ],
}


class BillingValidationTests(unittest.TestCase):
    def test_invalid_rules(self):
        invalid = [
            [],
            [{"up_to_minutes": 60, "hourly_rate": 1}],
            [{"up_to_minutes": None, "hourly_rate": -1}],
            [{"up_to_minutes": None, "hourly_rate": "NaN"}],
            [{"up_to_minutes": None, "hourly_rate": "0.001"}],
            [
                {"up_to_minutes": 60, "hourly_rate": 1},
                {"up_to_minutes": 60, "hourly_rate": 1},
                {"up_to_minutes": None, "hourly_rate": 1},
            ],
        ]
        for tiers in invalid:
            with self.subTest(tiers=tiers), self.assertRaises(ValidationError):
                EngineerBillingRules(currency="CNY", tiers=tiers)
        self.assertEqual(EngineerBillingRules(**RULES).model_dump(mode="json"), RULES)


class BillingApiTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        await Tortoise.init(db_url="sqlite://:memory:", modules={"models": ["app.models"]})
        await Tortoise.generate_schemas()
        self.user = await User.create(username="billing-test", email="billing@example.test")
        self.app = FastAPI()
        self.app.include_router(v1_router, prefix="/api/v1")
        self.app.dependency_overrides[AuthControl.is_authed] = lambda: self.user
        self.client = AsyncClient(
            transport=ASGITransport(app=self.app), base_url="http://test/api/v1/remote-assistance"
        )

    async def asyncTearDown(self):
        await self.client.aclose()
        await Tortoise.close_connections()

    async def grant(self):
        role = await Role.create(name="billing-test")
        for method, path in [("POST", "/engineers"), ("PUT", "/engineers/{engineer_id}"), ("GET", "/overview")]:
            api = await Api.create(method=method, path=f"/api/v1/remote-assistance{path}", summary="test", tags="test")
            await role.apis.add(api)
        await self.user.roles.add(role)

    async def test_save_read_preserve_and_clear(self):
        await self.grant()
        response = await self.client.post("/engineers", json={"name": "Test", "billing_rules": RULES})
        self.assertEqual(response.json()["code"], 200, response.text)
        engineer = await RemoteEngineer.get(name="Test")
        response = await self.client.get("/overview")
        self.assertEqual(response.json()["data"]["engineers"][0]["billing_rules"], RULES)
        response = await self.client.put(f"/engineers/{engineer.id}", json={"name": "Renamed"})
        self.assertEqual(response.json()["code"], 200)
        await engineer.refresh_from_db()
        self.assertEqual(engineer.billing_rules, RULES)
        response = await self.client.put(f"/engineers/{engineer.id}", json={"name": "Renamed", "billing_rules": None})
        self.assertEqual(response.json()["code"], 200)
        await engineer.refresh_from_db()
        self.assertIsNone(engineer.billing_rules)

    async def test_auth_and_validation(self):
        response = await self.client.post("/engineers", json={"name": "Test", "billing_rules": RULES})
        self.assertEqual(response.status_code, 403)
        await self.grant()
        response = await self.client.post("/engineers", json={"name": "Test", "billing_rules": {"tiers": []}})
        self.assertEqual(response.status_code, 422)
        self.assertEqual(await RemoteEngineer.all().count(), 0)
        self.app.dependency_overrides.clear()
        response = await self.client.post("/engineers", json={"name": "Test"})
        self.assertEqual(response.status_code, 422)
        response = await self.client.post("/engineers", headers={"token": "invalid"}, json={"name": "Test"})
        self.assertEqual(response.status_code, 401)

    async def test_migration_preserves_existing_engineers(self):
        path = Path(__file__).resolve().parents[1] / "migrations/models/175_20260922090000_engineer_billing_rules.py"
        spec = importlib.util.spec_from_file_location("billing_migration", path)
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)
        db = Tortoise.get_connection("default")
        engineer = await RemoteEngineer.create(name="Existing")
        await db.execute_script(await migration.downgrade(db))
        await db.execute_script(await migration.upgrade(db))
        await engineer.refresh_from_db()
        self.assertEqual(engineer.name, "Existing")
        self.assertIsNone(engineer.billing_rules)


if __name__ == "__main__":
    unittest.main()
