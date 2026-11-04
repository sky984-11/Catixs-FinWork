import importlib
import unittest

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from tortoise import Tortoise

from app.api.v1 import v1_router
from app.core.dependency import AuthControl
from app.models.admin import User
from app.models.customer_center import CrmCustomer
from app.models.product_center import ProductCategory, ProductItem
from app.models.product_order import ProductOrder, ProductOrderItem
from app.services.retired_product_catalog import remove_unused_retired_catalog_products


class ProductOrderTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        await Tortoise.init(db_url="sqlite://:memory:", modules={"models": ["app.models"]})
        await Tortoise.generate_schemas()
        self.user = await User.create(username="admin", email="admin@example.test", is_superuser=True)
        self.customer = await CrmCustomer.create(name="订单客户")
        self.product = await ProductItem.create(name="线路", code="ORDER-1")
        self.other = await ProductItem.create(name="机柜", code="ORDER-2")
        self.app = FastAPI()
        self.app.include_router(v1_router, prefix="/api/v1")

        async def authed():
            return self.user

        self.app.dependency_overrides[AuthControl.is_authed] = authed
        self.client = AsyncClient(transport=ASGITransport(app=self.app), base_url="http://test/api/v1/")
        self.path = "product-center/orders"
        self.payload = {
            "name": "客户产品组合",
            "customer_id": self.customer.id,
            "items": [{"product_id": self.product.id, "quantity": 2}, {"product_id": self.other.id, "quantity": 1}],
        }

    async def asyncTearDown(self):
        await self.client.aclose()
        await Tortoise.close_connections()

    async def create(self):
        response = await self.client.post(self.path, json=self.payload)
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()["data"]

    async def test_crud_filters_and_delete_protection(self):
        order = await self.create()
        self.assertEqual(order["customer_name"], self.customer.name)
        self.assertEqual([item["quantity"] for item in order["items"]], [2, 1])
        self.assertTrue(order["order_no"].startswith("ORD-"))
        response = await self.client.get(self.path, params={"customer_id": self.customer.id, "keyword": "订单客户"})
        self.assertEqual(response.json()["total"], 1)
        self.assertEqual((await self.client.get(self.path, params={"keyword": "missing"})).json()["total"], 0)
        self.assertEqual((await self.client.delete(f"product-center/products/{self.product.id}")).status_code, 400)
        self.assertEqual((await self.client.delete(f"customer-center/customers/{self.customer.id}")).status_code, 409)
        detail = await self.client.get(f"{self.path}/{order['id']}")
        self.assertEqual(detail.json()["data"]["id"], order["id"])
        edited = {**self.payload, "items": [{"product_id": self.other.id, "quantity": 3}]}
        response = await self.client.put(f"{self.path}/{order['id']}", json=edited)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["data"]["order_no"], order["order_no"])
        self.assertEqual(await ProductOrderItem.all().count(), 1)
        self.assertEqual((await self.client.delete(f"{self.path}/{order['id']}")).status_code, 200)
        self.assertEqual(await ProductOrderItem.all().count(), 0)
        self.assertEqual(await ProductItem.all().count(), 2)
        self.assertEqual(await CrmCustomer.all().count(), 1)
        self.assertEqual((await self.client.get(f"{self.path}/{order['id']}")).status_code, 404)
        self.assertEqual((await self.client.delete(f"{self.path}/{order['id']}")).status_code, 404)

    async def test_invalid_inputs_and_atomic_update(self):
        order = await self.create()
        for changes, code in [
            ({"name": "   "}, 422),
            ({"items": []}, 422),
            ({"items": [{"product_id": self.product.id, "quantity": 0}]}, 422),
            ({"items": [{"product_id": self.product.id, "quantity": 1.2}]}, 422),
            ({"items": [self.payload["items"][0]] * 2}, 422),
            ({"customer_id": 99999}, 400),
            ({"items": [{"product_id": 99999, "quantity": 1}]}, 400),
        ]:
            with self.subTest(changes=changes):
                response = await self.client.put(f"{self.path}/{order['id']}", json={**self.payload, **changes})
                self.assertEqual(response.status_code, code, response.text)
                self.assertEqual(await ProductOrderItem.all().count(), 2)
        self.assertEqual(await ProductOrder.all().count(), 1)

    async def test_inactive_references_preserved_but_not_added(self):
        order = await self.create()
        self.product.status = "offline"
        await self.product.save()
        self.customer.lifecycle = "terminated"
        await self.customer.save()
        self.assertEqual((await self.client.put(f"{self.path}/{order['id']}", json=self.payload)).status_code, 200)
        self.assertEqual((await self.client.post(self.path, json=self.payload)).status_code, 400)
        self.customer.lifecycle = "active"
        await self.customer.save()
        self.assertEqual((await self.client.post(self.path, json=self.payload)).status_code, 400)

    async def test_auth_and_permissions(self):
        order = await self.create()
        for authenticated, code in [(False, 401), (True, 403)]:
            self.app.dependency_overrides.clear()
            if authenticated:
                self.user.is_superuser = False

                async def ordinary():
                    return self.user

                self.app.dependency_overrides[AuthControl.is_authed] = ordinary
            for method, url, kwargs in [
                ("get", self.path, {}),
                ("get", f"{self.path}/{order['id']}", {}),
                ("post", self.path, {"json": self.payload}),
                ("put", f"{self.path}/{order['id']}", {"json": self.payload}),
                ("delete", f"{self.path}/{order['id']}", {}),
            ]:
                response = await getattr(self.client, method)(url, **kwargs)
                self.assertEqual(response.status_code, code, response.text)
        self.assertEqual(await ProductOrder.all().count(), 1)

    async def test_migration_constraints(self):
        migration = importlib.import_module("migrations.models.183_20261104150000_product_orders")
        sql = await migration.upgrade(None)
        self.assertIn('REFERENCES "crm_customer" ("id") ON DELETE RESTRICT', sql)
        self.assertIn('REFERENCES "product_item" ("id") ON DELETE RESTRICT', sql)
        self.assertIn('REFERENCES "product_order" ("id") ON DELETE CASCADE', sql)
        self.assertIn('UNIQUE ("order_id", "product_id")', sql)
        self.assertEqual(
            await migration.downgrade(None), 'DROP TABLE "product_order_item"; DROP TABLE "product_order";'
        )

    async def test_startup_cleanup_preserves_order_products(self):
        category = await ProductCategory.create(name="ASN", code="IDC.IP.ASN.LEAF")
        self.product.name = "ASN"
        self.product.code = "IP.ASN"
        self.product.category = category
        await self.product.save()
        await self.create()
        self.assertEqual(await remove_unused_retired_catalog_products(), 0)
        self.assertTrue(await ProductItem.filter(id=self.product.id).exists())
        self.product.status = "offline"
        await self.product.save()
        response = await self.client.get(self.path)
        item = response.json()["data"][0]["items"][0]
        self.assertEqual(item["category_id"], category.id)
        self.assertEqual(item["category_name"], "ASN")
