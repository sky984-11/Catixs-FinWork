import unittest

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from tortoise import Tortoise

from app.api.v1 import v1_router
from app.core.dependency import AuthControl
from app.models.admin import User
from app.models.customer_center import CrmCustomer
from app.models.product_center import ProductCategory, ProductItem, ProductSpecAttribute, ProductVariant
from app.models.product_order import ProductOrderItem


class ProductVariantTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        await Tortoise.init(db_url="sqlite://:memory:", modules={"models": ["app.models"]})
        await Tortoise.generate_schemas()
        self.category = await ProductCategory.create(name="Compute")
        self.field = await ProductSpecAttribute.create(
            name="Memory",
            code="memory",
            attr_type="number",
            required=True,
            category=self.category,
            category_ids=[self.category.id],
            unit="GB",
        )
        self.product = await ProductItem.create(name="Server", code="SERVER", category=self.category)
        self.customer = await CrmCustomer.create(name="Customer")
        self.user = await User.create(username="admin", email="variants@example.test", is_superuser=True)
        self.app = FastAPI()
        self.app.include_router(v1_router, prefix="/api/v1")

        async def authed():
            return self.user

        self.app.dependency_overrides[AuthControl.is_authed] = authed
        self.client = AsyncClient(transport=ASGITransport(app=self.app), base_url="http://test/api/v1/product-center/")
        self.path = f"products/{self.product.id}/variants"

    async def asyncTearDown(self):
        await self.client.aclose()
        await Tortoise.close_connections()

    def payload(self, name="128GB", code="SKU128", memory=128):
        return {"name": name, "code": code, "spec_values": {str(self.field.id): memory}}

    async def variant(self, **kwargs):
        response = await self.client.post(self.path, json=self.payload(**kwargs))
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()["data"]

    async def price(self, variant, mrc="100"):
        response = await self.client.post(
            f"products/{self.product.id}/price-versions",
            json={
                "variant_id": variant["id"],
                "currency": "USD",
                "mrc": mrc,
                "nrc": "10",
                "period_months": 1,
            },
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()["data"]

    async def test_common_product_does_not_require_parameter_values(self):
        response = await self.client.post(
            "products",
            json={"name": "Generic", "code": "GENERIC", "category_id": self.category.id, "parameterized": True},
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["data"]["spec_values"], {})

    async def test_product_without_variants_can_be_priced_and_ordered(self):
        listing = await self.client.get("products")
        self.assertEqual(listing.status_code, 200, listing.text)
        self.assertFalse(listing.json()["data"][0]["direct_pricing"])
        response = await self.client.post(
            f"products/{self.product.id}/price-versions",
            json={"currency": "USD", "mrc": "100", "nrc": "20", "period_months": 1},
        )
        self.assertEqual(response.status_code, 200, response.text)
        price = response.json()["data"]
        self.assertIsNone(price["variant_id"])
        listing = await self.client.get("products")
        self.assertTrue(listing.json()["data"][0]["direct_pricing"])
        selected = await self.client.get(f"products/{self.product.id}/order-price")
        self.assertEqual(selected.status_code, 200, selected.text)
        self.assertEqual(selected.json()["data"]["price_version_id"], price["id"])
        response = await self.client.post(
            "orders",
            json={
                "name": "No specifications",
                "customer_id": self.customer.id,
                "items": [{"product_id": self.product.id, "variant_id": None, "quantity": 2}],
            },
        )
        self.assertEqual(response.status_code, 200, response.text)
        item = response.json()["data"]["items"][0]
        self.assertIsNone(item["variant_id"])
        self.assertEqual(item["price_version_id"], price["id"])
        self.assertEqual(float(item["mrc"]), 100)
        self.assertEqual(float(item["nrc"]), 20)
        self.assertFalse(await ProductVariant.filter(product_id=self.product.id).exists())
        await self.variant()
        listing = await self.client.get("products")
        self.assertFalse(listing.json()["data"][0]["direct_pricing"])

    async def test_variant_without_sku_generates_internal_code_and_preserves_legacy_code(self):
        payload = self.payload()
        payload.pop("code")
        response = await self.client.post(self.path, json=payload)
        self.assertEqual(response.status_code, 200, response.text)
        created = response.json()["data"]
        self.assertTrue(created["code"].startswith("VAR-"))
        response = await self.client.put(f"{self.path}/{created['id']}", json={**payload, "name": "Renamed"})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["data"]["code"], created["code"])
        legacy = await self.variant(name="Legacy", code="OLD-SKU")
        response = await self.client.put(
            f"{self.path}/{legacy['id']}", json={**payload, "name": "Legacy renamed", "code": None}
        )
        self.assertEqual(response.json()["data"]["code"], "OLD-SKU")
        response = await self.client.post(self.path, json={**payload, "name": "Second"})
        self.assertNotEqual(response.json()["data"]["code"], created["code"])

    async def test_variant_crud_typed_fields_and_duplicate_codes(self):
        response = await self.client.post(self.path, json={"name": "Bad", "code": "BAD"})
        self.assertEqual(response.status_code, 422)
        response = await self.client.post(self.path, json=self.payload(memory="not a number"))
        self.assertEqual(response.status_code, 422)
        variant = await self.variant()
        self.assertEqual(variant["spec_snapshot"][0]["value"], 128)
        self.assertEqual((await self.client.post(self.path, json=self.payload())).status_code, 409)
        self.assertEqual(len((await self.client.get(self.path)).json()["data"]), 1)
        response = await self.client.put(f"{self.path}/{variant['id']}", json=self.payload(memory=256))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["spec_values"][str(self.field.id)], 256)
        self.assertEqual((await self.client.delete(f"{self.path}/{variant['id']}")).status_code, 200)
        self.assertEqual(await ProductVariant.all().count(), 0)
        self.assertEqual((await self.client.delete(f"{self.path}/{variant['id']}")).status_code, 404)

    async def test_prices_and_orders_are_isolated_by_variant(self):
        first = await self.variant()
        second = await self.variant(name="256GB", code="SKU256", memory=256)
        first_price = await self.price(first, "100")
        second_price = await self.price(second, "200")
        history = await self.client.get(
            f"products/{self.product.id}/price-versions", params={"variant_id": first["id"]}
        )
        self.assertEqual([row["id"] for row in history.json()["data"]], [first_price["id"]])
        self.assertEqual((await self.client.get(f"products/{self.product.id}/order-price")).status_code, 422)
        selected = await self.client.get(f"products/{self.product.id}/order-price", params={"variant_id": first["id"]})
        self.assertEqual(selected.json()["data"]["mrc"], "100.00")
        payload = {
            "name": "Order",
            "customer_id": self.customer.id,
            "items": [
                {"product_id": self.product.id, "variant_id": first["id"], "quantity": 1, "mrc": "90"},
                {"product_id": self.product.id, "variant_id": second["id"], "quantity": 2},
            ],
        }
        response = await self.client.post("orders", json=payload)
        self.assertEqual(response.status_code, 200, response.text)
        order = response.json()["data"]
        self.assertEqual([row["mrc"] for row in order["items"]], ["90.00", "200.00"])
        self.assertEqual([row["spec_snapshot"][0]["value"] for row in order["items"]], [128, 256])
        payload["items"][0]["price_version_id"] = second_price["id"]
        response = await self.client.put(f"orders/{order['id']}", json=payload)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(await ProductOrderItem.all().count(), 2)
        payload["items"][0].pop("price_version_id")
        self.product.name = "Renamed"
        await self.product.save()
        response = await self.client.put(
            f"{self.path}/{first['id']}", json={**self.payload(name="Renamed variant"), "status": "offline"}
        )
        self.assertEqual(response.status_code, 200, response.text)
        response = await self.client.put(f"orders/{order['id']}", json=payload)
        self.assertEqual(response.status_code, 200, response.text)
        saved = response.json()["data"]["items"][0]
        self.assertEqual(saved["product_name"], "Server")
        self.assertEqual(saved["variant_name"], "128GB")
        self.assertEqual((await self.client.post("orders", json=payload)).status_code, 400)
        self.assertEqual((await self.client.delete(f"{self.path}/{first['id']}")).status_code, 409)
        self.assertEqual((await self.client.delete(f"products/{self.product.id}")).status_code, 400)
        response = await self.client.put(f"{self.path}/{first['id']}", json=self.payload(memory=512))
        self.assertEqual(response.status_code, 409)

    async def test_cross_product_duplicate_selection_and_legacy_compatibility(self):
        variant = await self.variant()
        await self.price(variant)
        other = await ProductItem.create(name="Other", code="OTHER")
        payload = {
            "name": "Order",
            "customer_id": self.customer.id,
            "items": [{"product_id": other.id, "variant_id": variant["id"], "quantity": 1}],
        }
        self.assertEqual((await self.client.post("orders", json=payload)).status_code, 404)
        payload["items"][0]["product_id"] = self.product.id
        payload["items"].append({"product_id": self.product.id, "quantity": 1})
        self.assertEqual((await self.client.post("orders", json=payload)).status_code, 422)
        payload["items"] = [{"product_id": self.product.id, "quantity": 1}]
        response = await self.client.post("orders", json=payload)
        self.assertEqual(response.status_code, 200, response.text)
        order_id = response.json()["data"]["id"]
        self.assertEqual(response.json()["data"]["items"][0]["variant_id"], variant["id"])
        await self.variant(name="256GB", code="SKU256", memory=256)
        self.assertEqual((await self.client.post("orders", json=payload)).status_code, 422)
        self.assertEqual((await self.client.put(f"orders/{order_id}", json=payload)).status_code, 200)

    async def test_permission_and_auth_for_variant_routes(self):
        variant = await self.variant()
        for authed, code in [(False, 401), (True, 403)]:
            self.app.dependency_overrides.clear()
            if authed:
                self.user.is_superuser = False

                async def ordinary():
                    return self.user

                self.app.dependency_overrides[AuthControl.is_authed] = ordinary
            for method, path, kwargs in [
                ("get", self.path, {}),
                ("post", self.path, {"json": self.payload()}),
                ("put", f"{self.path}/{variant['id']}", {"json": self.payload()}),
                ("delete", f"{self.path}/{variant['id']}", {}),
            ]:
                self.assertEqual((await getattr(self.client, method)(path, **kwargs)).status_code, code)
