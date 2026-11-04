import unittest
from unittest.mock import AsyncMock, patch

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from tortoise import Tortoise

from app.api.v1 import v1_router
from app.core.dependency import AuthControl
from app.models.admin import User
from app.models.customer_center import CrmCustomer
from app.models.product_center import (ProductCategory, ProductItem,
                                       ProductPriceVersion)


class ProductPriceVersionTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        await Tortoise.init(db_url="sqlite://:memory:", modules={"models": ["app.models"]})
        await Tortoise.generate_schemas()
        self.user = await User.create(username="admin", email="admin@example.test", is_superuser=True)
        self.category = await ProductCategory.create(name="Network")
        self.product = await ProductItem.create(name="Transit", code="NET-1", category=self.category, region="HK")
        self.customer = await CrmCustomer.create(name="Customer A")
        self.other = await CrmCustomer.create(name="Customer B")
        self.app = FastAPI()
        self.app.include_router(v1_router, prefix="/api/v1")

        async def authed():
            return self.user

        self.app.dependency_overrides[AuthControl.is_authed] = authed
        self.client = AsyncClient(transport=ASGITransport(app=self.app), base_url="http://test/api/v1/product-center")
        self.path = f"/products/{self.product.id}/price-versions"
        self.payload = {
            "customer_id": self.customer.id,
            "currency": "CNY",
            "mrc": "123.45",
            "nrc": "50.00",
            "period_months": 1,
            "effective_date": "2026-01-01",
            "expiry_date": "2026-07-01",
        }

    async def asyncTearDown(self):
        await self.client.aclose()
        await Tortoise.close_connections()

    async def post(self, **changes):
        return await self.client.post(self.path, json={**self.payload, **changes})

    async def test_versions_preserve_history_and_half_open_intervals(self):
        first = await self.post()
        self.assertEqual(first.status_code, 200, first.text)
        next_version = await self.post(mrc="150", effective_date="2026-07-01", expiry_date="2027-01-01")
        self.assertEqual(next_version.status_code, 200, next_version.text)
        self.assertEqual(next_version.json()["data"]["version"], 2)
        history = (await self.client.get(self.path)).json()["data"]
        self.assertEqual([row["version"] for row in history], [2, 1])
        self.assertEqual(history[1]["mrc"], "123.45")
        self.assertEqual(history[1]["customer_name"], "Customer A")
        self.assertEqual((await self.client.put(self.path, json=self.payload)).status_code, 405)
        self.assertEqual((await self.client.delete(self.path)).status_code, 405)

    async def test_overlap_is_scoped_to_customer_currency_and_period(self):
        self.assertEqual((await self.post()).status_code, 200)
        self.assertEqual((await self.post(effective_date="2026-06-30")).status_code, 409)
        for changes in (
            {"customer_id": self.other.id},
            {"customer_id": None},
            {"currency": "USD"},
            {"period_months": 3},
        ):
            result = await self.post(**changes)
            self.assertEqual(result.status_code, 200, result.text)
        filtered = (await self.client.get(self.path, params={"customer_id": self.other.id})).json()
        self.assertEqual(filtered["total"], 1)
        self.assertEqual(filtered["data"][0]["customer_id"], self.other.id)
        common = (await self.client.get(self.path, params={"customer_id": 0})).json()
        self.assertEqual(common["total"], 1)
        self.assertIsNone(common["data"][0]["customer_id"])
        self.assertEqual((await self.client.get(self.path, params={"page_size": 2})).json()["total"], 5)

    async def test_invalid_values_do_not_create_versions(self):
        for changes in (
            {"mrc": "-1"},
            {"mrc": "NaN"},
            {"nrc": "-1"},
            {"mrc": "1.001"},
            {"mrc": "100000000000000"},
            {"period_months": 0},
            {"currency": "BAD"},
            {"expiry_date": "2026-01-01"},
            {"expiry_date": "2025-12-01"},
            {"customer_id": 999999},
        ):
            with self.subTest(changes=changes):
                self.assertEqual((await self.post(**changes)).status_code, 422)
        self.customer.lifecycle = "terminated"
        await self.customer.save()
        self.assertEqual((await self.post()).status_code, 422)
        self.assertEqual(await ProductPriceVersion.all().count(), 0)

    async def test_auth_and_permission(self):
        self.app.dependency_overrides.clear()
        self.assertEqual((await self.post()).status_code, 401)
        self.assertEqual((await self.client.get(self.path)).status_code, 401)

        async def ordinary_user():
            self.user.is_superuser = False
            return self.user

        self.app.dependency_overrides[AuthControl.is_authed] = ordinary_user
        self.assertEqual((await self.post()).status_code, 403)
        self.assertEqual((await self.client.get(self.path)).status_code, 403)
        self.assertEqual(await ProductPriceVersion.all().count(), 0)

    async def test_product_deletion_protects_history(self):
        await self.post()
        response = await self.client.delete(f"/products/{self.product.id}")
        self.assertEqual(response.status_code, 400)
        self.assertTrue(await ProductItem.filter(id=self.product.id).exists())
        self.assertEqual(await ProductPriceVersion.all().count(), 1)
        unused = await ProductItem.create(name="Unused")
        self.assertEqual((await self.client.delete(f"/products/{unused.id}")).status_code, 200)
        self.assertFalse(await ProductItem.filter(id=unused.id).exists())
        response = await self.client.delete(f"http://test/api/v1/customer-center/customers/{self.customer.id}")
        self.assertEqual(response.status_code, 409)
        self.assertTrue(await CrmCustomer.filter(id=self.customer.id).exists())

    async def test_pre_migration_backfill_uses_only_existing_columns(self):
        from app.core import init_app
        from app.models.product_center import ProductSpecAttribute, ProductSpecConfig

        attribute = await ProductSpecAttribute.create(name="Bandwidth", code="bandwidth")
        config = await ProductSpecConfig.create(product=self.product, attribute=attribute)
        conn = Tortoise.get_connection("default")
        await conn.execute_script(
            'ALTER TABLE product_item DROP COLUMN billing_unit;'
            'ALTER TABLE product_item DROP COLUMN min_contract_months;'
        )
        with (
            patch.object(init_app.settings, "DB_TYPE", "sqlite"),
            patch.object(Tortoise, "get_connection", return_value=conn),
        ):
            await init_app.ensure_product_center_columns()
        await config.refresh_from_db()
        self.assertEqual(config.product_display_name, "Transit")

    async def test_product_fields_and_category_descendants(self):
        child = await ProductCategory.create(name="Child", parent=self.category)
        response = await self.client.put(
            f"/products/{self.product.id}",
            json={
                "name": "Updated",
                "category_id": child.id,
                "billing_unit": "mbps",
                "min_contract_months": 12,
            },
        )
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()["data"]
        self.assertEqual(data["billing_unit"], "mbps")
        self.assertEqual(data["min_contract_months"], 12)
        self.assertEqual(data["region"], "HK")
        self.assertEqual(data["code"], "NET-1")
        invalid = await self.client.post(
            "/products", json={"name": "Invalid", "category_id": child.id, "min_contract_months": 0}
        )
        self.assertEqual(invalid.status_code, 422)
        result = (await self.client.get("/products", params={"category_id": self.category.id})).json()
        self.assertEqual(result["total"], 1)
        await self.post()
        self.assertEqual((await ProductPriceVersion.first()).billing_unit, "mbps")
