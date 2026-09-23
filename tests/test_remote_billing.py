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
from app.models.remote_assistance import RemoteEngineer, RemoteHands, RemoteHandsPlan
from app.models.customer_center import CrmCustomer, CrmSigningEntity
from app.schemas.remote_billing import EngineerBillingRules, MaintenanceBillingRules, GeneralBillingRules


RULES = {
    "currency": "CNY",
    "tiers": [
        {"up_to_minutes": 60, "hourly_rate": "120.00"},
        {"up_to_minutes": None, "hourly_rate": "90.00"},
    ],
}

PACKAGE_RULES = MaintenanceBillingRules(
    mode="package",
    currency="CNY",
    tiers=[{"up_to_minutes": 240, "total_fee": "1100.00"}, {"up_to_minutes": 480, "total_fee": "1650.00"}],
    overtime_hourly_rate="300.00",
).model_dump(mode="json")


class BillingValidationTests(unittest.TestCase):
    def test_package_validation(self):
        self.assertEqual(MaintenanceBillingRules(**PACKAGE_RULES).model_dump(mode="json"), PACKAGE_RULES)
        invalid = [
            {"tiers": []},
            {"tiers": [{"up_to_minutes": None, "total_fee": 1100}]},
            {"tiers": [{"up_to_minutes": 240, "total_fee": 1100}, {"up_to_minutes": 240, "total_fee": 1650}]},
            {"tiers": [{"up_to_minutes": 240, "total_fee": 1100}, {"up_to_minutes": 480, "total_fee": 1000}]},
            {"overtime_hourly_rate": "NaN"},
            {"overtime_hourly_rate": -1},
            {"overtime_hourly_rate": "0.001"},
            {"night_multiplier": 0},
            {"overtime_threshold_minutes": 0},
            {"overtime_threshold_minutes": 61},
            {"overtime_rounding": "invalid"},
            {"emergency_response_minutes": 0},
            {"emergency_region": "大阪"},
            {"emergency_region": " "},
            {"project_services": []},
            {"settlement_cycles": ["monthly"]},
            {"settlement_cycles": ["daily", "daily"]},
            {"japan_payment": ""},
        ]
        for patch in invalid:
            with self.subTest(patch=patch), self.assertRaises(ValidationError):
                MaintenanceBillingRules(**(PACKAGE_RULES | patch))

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
    async def test_customer_price_api_validation_and_permissions(self):
        entity = await CrmSigningEntity.create(name="Catixs")
        url = "http://test/api/v1/customer-center/customers"
        payload = {
            "name": "milk",
            "signing_entity_id": entity.id,
            "maintenance_hourly_rate": 80,
            "maintenance_currency": "USD",
        }
        response = await self.client.post(url, json=payload)
        self.assertEqual(response.status_code, 403)
        self.user.is_superuser = True
        response = await self.client.post(url, json=payload)
        self.assertEqual(response.json()["code"], 200, response.text)
        customer_id = response.json()["data"]["id"]
        for change in [
            {"maintenance_hourly_rate": -1},
            {"maintenance_currency": "BAD"},
            {"maintenance_hourly_rate": "NaN"},
            {"maintenance_hourly_rate": "0.001"},
        ]:
            response = await self.client.put(f"{url}/{customer_id}", json=payload | change)
            self.assertEqual(response.status_code, 422)
        response = await self.client.get("http://test/api/v1/customer-center/options")
        option = next(item for item in response.json()["data"]["customers"] if item["value"] == customer_id)
        self.assertEqual(float(option["maintenance_hourly_rate"]), 80)
        await self.client.put(f"{url}/{customer_id}", json={"name": "milk updated"})
        self.assertEqual(float((await CrmCustomer.get(id=customer_id)).maintenance_hourly_rate), 80)
        await self.client.put(f"{url}/{customer_id}", json={"name": "milk updated", "maintenance_hourly_rate": None})
        self.assertIsNone((await CrmCustomer.get(id=customer_id)).maintenance_hourly_rate)
        self.app.dependency_overrides.clear()
        self.assertEqual((await self.client.post(url, json=payload)).status_code, 422)

    async def test_customer_price_snapshot_and_record_expenses(self):
        preview = await self.client.post("/billing/preview", json={
            "customer_pricing": {"kind": "fixed", "fixed_fee": 500, "currency": "USD"}})
        self.assertEqual(preview.json()["data"]["total"], "500.00", preview.text)
        await self.grant()
        role = await Role.get(name="billing-test")
        for method, path in [
            ("POST", "/remote-hands"),
            ("PUT", "/remote-hands/{item_id}"),
            ("POST", "/plans"),
            ("POST", "/plans/{plan_id}/complete"),
        ]:
            permission = await Api.create(
                method=method, path=f"/api/v1/remote-assistance{path}", summary="test", tags="test"
            )
            await role.apis.add(permission)
        customer = await CrmCustomer.create(name="milk", maintenance_hourly_rate=80, maintenance_currency="USD")
        engineer = await RemoteEngineer.create(
            name="Anson",
            billing_rules=GeneralBillingRules(
                mode="general",
                currency="USD",
                hourly_rate=55,
                billing_increment_minutes=60,
                transport_mode="hourly",
                commute_mode="actual",
            ).model_dump(mode="json"),
        )
        payload = {
            "customer": "ignored",
            "customer_pricing": {"kind": "hourly", "hourly_rate": 80, "currency": "USD"},
            "customer_id": customer.id,
            "engineer_id": engineer.id,
            "arrived_at": "2026-09-23T10:00",
            "left_at": "2026-09-23T11:01",
            "billing_context": {
                "actual_commute_minutes": 31,
                "expenses": [{"name": "Taxi", "amount": 20, "currency": "USD"}],
            },
        }
        response = await self.client.post("/remote-hands", json=payload)
        self.assertEqual(response.json()["code"], 200, response.text)
        record = await RemoteHands.get(customer_id=customer.id)
        self.assertEqual(record.customer, "milk")
        self.assertEqual(record.billing_data["result"]["total"], "260.00")
        await CrmCustomer.filter(id=customer.id).update(maintenance_hourly_rate=100)
        response = await self.client.put(f"/remote-hands/{record.id}", json=payload | {"note": "Changed"})
        self.assertEqual(response.json()["code"], 200, response.text)
        await record.refresh_from_db()
        self.assertEqual(record.billing_data["result"]["total"], "260.00")
        await self.client.put(f"/remote-hands/{record.id}", json=payload | {"refresh_billing_rules": True})
        await record.refresh_from_db()
        self.assertEqual(record.billing_data["result"]["total"], "260.00")
        cleared = payload | {"billing_context": {"actual_commute_minutes": 0, "expenses": []}}
        await self.client.put(f"/remote-hands/{record.id}", json=cleared)
        await record.refresh_from_db()
        self.assertEqual(record.billing_data["result"]["total"], "160.00")
        invalid = await self.client.post(
            "/remote-hands",
            json=payload | {"billing_context": {"expenses": [{"name": "Taxi", "amount": -1, "currency": "USD"}]}},
        )
        self.assertEqual(invalid.status_code, 422)
        response = await self.client.post(
            "/plans",
            json={
                "customer": "ignored",
                "customer_pricing": {"kind": "fixed", "fixed_fee": 500, "currency": "USD"},
                "customer_id": customer.id,
                "engineer_id": engineer.id,
                "region": "LA",
                "site": "Test",
                "planned_at": payload["arrived_at"],
            },
        )
        self.assertEqual(response.json()["code"], 200, response.text)
        plan = await RemoteHandsPlan.get(customer_id=customer.id)
        response = await self.client.post(
            f"/plans/{plan.id}/complete", json={"arrived_at": payload["arrived_at"], "left_at": payload["left_at"]}
        )
        self.assertEqual(response.json()["data"]["customer_id"], customer.id)
        self.assertEqual(float(response.json()["data"]["customer_pricing_snapshot"]["fixed_fee"]), 500)
        self.assertEqual(response.json()["data"]["billing_result"]["total"], "500.00")
        # A new job never inherits the deprecated customer-level price.
        response = await self.client.post(
            "/remote-hands", json={key: value for key, value in payload.items() if key != "customer_pricing"}
        )
        self.assertEqual(response.json()["code"], 200, response.text)
        latest = await RemoteHands.filter(customer_id=customer.id).order_by("-id").first()
        self.assertEqual(latest.billing_data["customer_pricing"]["kind"], "internal")
        self.assertEqual(latest.billing_data["result"]["total"], "185.00")

    async def test_generic_rule_preview_auth_and_record_snapshots(self):
        await self.grant()
        role = await Role.get(name="billing-test")
        for method, route in [
            ("POST", "/remote-hands"),
            ("PUT", "/remote-hands/{item_id}"),
            ("POST", "/plans/{plan_id}/complete"),
        ]:
            api = await Api.create(method=method, path=f"/api/v1/remote-assistance{route}", summary="test", tags="test")
            await role.apis.add(api)
        rules = GeneralBillingRules(mode="general", currency="GBP", hourly_rate=30, transport_mode="hourly").model_dump(
            mode="json"
        )
        response = await self.client.post("/engineers", json={"name": "Generic", "billing_rules": rules})
        self.assertEqual(response.status_code, 200, response.text)
        engineer = await RemoteEngineer.get(name="Generic")
        payload = {
            "customer": "Catixs",
            "engineer_id": engineer.id,
            "arrived_at": "2026-09-22T10:00",
            "left_at": "2026-09-22T12:00",
            "timezone": "Europe/London",
        }
        preview = await self.client.post(
            "/billing/preview",
            json={"rules": rules, **{key: payload[key] for key in ["arrived_at", "left_at", "timezone"]}},
        )
        self.assertEqual(preview.json()["data"]["total"], "90.00", preview.text)
        response = await self.client.post("/remote-hands", json=payload)
        self.assertEqual(response.status_code, 200, response.text)
        record = await RemoteHands.get(customer="Catixs")
        self.assertEqual(record.billing_data["result"]["total"], "90.00")
        engineer.billing_rules = rules | {"hourly_rate": "100.00"}
        await engineer.save()
        response = await self.client.put(f"/remote-hands/{record.id}", json=payload | {"note": "Updated"})
        self.assertEqual(response.status_code, 200, response.text)
        await record.refresh_from_db()
        self.assertEqual(record.billing_data["result"]["total"], "90.00")
        response = await self.client.put(f"/remote-hands/{record.id}", json=payload | {"left_at": "2026-09-22T13:00"})
        self.assertEqual(response.status_code, 200)
        await record.refresh_from_db()
        self.assertEqual(record.billing_data["result"]["total"], "120.00")
        response = await self.client.put(f"/remote-hands/{record.id}", json=payload | {"refresh_billing_rules": True})
        self.assertEqual(response.status_code, 200)
        await record.refresh_from_db()
        self.assertEqual(record.billing_data["result"]["total"], "300.00")
        response = await self.client.post("/remote-hands", json=payload | {"timezone": "invalid"})
        self.assertEqual(response.status_code, 422)
        plan = await RemoteHandsPlan.create(customer="Catixs", engineer_id=engineer.id, timezone="Europe/London")
        response = await self.client.post(
            f"/plans/{plan.id}/complete", json={"arrived_at": payload["arrived_at"], "left_at": payload["left_at"]}
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["data"]["billing_result"]["total"], "300.00")
        self.app.dependency_overrides.clear()
        response = await self.client.post(
            "/billing/preview",
            json={"rules": rules, "arrived_at": payload["arrived_at"], "left_at": payload["left_at"]},
        )
        self.assertEqual(response.status_code, 422)
        response = await self.client.post(
            "/billing/preview",
            headers={"token": "invalid"},
            json={"rules": rules, "arrived_at": payload["arrived_at"], "left_at": payload["left_at"]},
        )
        self.assertEqual(response.status_code, 401)

    async def test_snapshot_migration_preserves_history(self):
        path = Path(__file__).resolve().parents[1] / "migrations/models/176_20260922120000_remote_billing_snapshot.py"
        spec = importlib.util.spec_from_file_location("snapshot_migration", path)
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)
        db = Tortoise.get_connection("default")
        record = await RemoteHands.create(customer="Historical")
        await db.execute_script(await migration.downgrade(db))
        await db.execute_script(await migration.upgrade(db))
        await record.refresh_from_db()
        self.assertEqual(record.customer, "Historical")
        self.assertIsNone(record.billing_data)

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

    async def test_package_create_update_read_and_legacy_compatibility(self):
        await self.grant()
        response = await self.client.post("/engineers", json={"name": "Package", "billing_rules": PACKAGE_RULES})
        self.assertEqual(response.json()["code"], 200, response.text)
        engineer = await RemoteEngineer.get(name="Package")
        self.assertEqual(engineer.billing_rules, PACKAGE_RULES)
        response = await self.client.get("/overview")
        self.assertEqual(response.json()["data"]["engineers"][0]["billing_rules"], PACKAGE_RULES)
        response = await self.client.put(f"/engineers/{engineer.id}", json={"name": "Package edited"})
        self.assertEqual(response.json()["code"], 200)
        await engineer.refresh_from_db()
        self.assertEqual(engineer.billing_rules, PACKAGE_RULES)
        updated = PACKAGE_RULES | {"overtime_rounding": "ceil_after_threshold", "emergency_fee": "600.00"}
        response = await self.client.put(
            f"/engineers/{engineer.id}", json={"name": "Package edited", "billing_rules": updated}
        )
        self.assertEqual(response.json()["code"], 200, response.text)
        await engineer.refresh_from_db()
        self.assertEqual(engineer.billing_rules, updated)
        response = await self.client.put(
            f"/engineers/{engineer.id}",
            json={"name": "Package edited", "billing_rules": updated | {"night_multiplier": -1}},
        )
        self.assertEqual(response.status_code, 422)
        await engineer.refresh_from_db()
        self.assertEqual(engineer.billing_rules, updated)
        response = await self.client.put(f"/engineers/{engineer.id}", json={"name": "Legacy", "billing_rules": RULES})
        self.assertEqual(response.json()["code"], 200)
        await engineer.refresh_from_db()
        self.assertEqual(engineer.billing_rules, RULES)

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
