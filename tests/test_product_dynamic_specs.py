import unittest

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from tortoise import Tortoise

from app.api.v1 import v1_router
from app.core.dependency import AuthControl
from app.models.admin import User
from app.models.product_center import ProductCategory, ProductItem, ProductSpecAttribute


class ProductDynamicSpecsTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        await Tortoise.init(db_url="sqlite://:memory:", modules={"models": ["app.models"]})
        await Tortoise.generate_schemas()
        self.category = await ProductCategory.create(name="Physical", code="BMS")
        self.alias = await ProductCategory.create(name="Physical", code="OLD.BMS")
        self.other = await ProductCategory.create(name="Network", code="NET")
        self.fields = {}
        for kind in ("text", "number", "select", "multi_select", "switch", "date", "resource_ref"):
            field = await ProductSpecAttribute.create(
                name=kind, code=kind, attr_type=kind, category=self.alias,
                required=True, options='["A", "B"]' if kind in ("select", "multi_select") else None,
            )
            self.fields[kind] = field
        self.disabled = await ProductSpecAttribute.create(name="Disabled", code="disabled", status=False, category=self.alias)
        self.values = {str(self.fields[kind].id): value for kind, value in {
            "text": "Server", "number": 0, "select": "A", "multi_select": ["A", "B"],
            "switch": False, "date": "2026-11-04", "resource_ref": "resource-1",
        }.items()}
        self.user = await User.create(username="admin", email="admin@example.test", is_superuser=True)
        self.app = FastAPI()
        self.app.include_router(v1_router, prefix="/api/v1")

        async def authed():
            return self.user

        self.app.dependency_overrides[AuthControl.is_authed] = authed
        self.client = AsyncClient(transport=ASGITransport(app=self.app), base_url="http://test/api/v1/product-center")

    async def asyncTearDown(self):
        await self.client.aclose()
        await Tortoise.close_connections()

    async def create(self, values=None):
        return await self.client.post("/products", json={
            "name": "Server", "category_id": self.category.id,
            "spec_values": self.values if values is None else values,
        })

    async def test_enabled_fields_follow_alias_category_and_round_trip_all_types(self):
        response = await self.client.get("/product-spec-fields", params={"category_id": self.category.id})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["data"]), 7)
        field = next(item for item in response.json()["data"] if item["attr_type"] == "select")
        self.assertEqual(field["select_options"], [{"label": "A", "value": "A"}, {"label": "B", "value": "B"}])
        response = await self.create()
        self.assertEqual(response.status_code, 200, response.text)
        product = response.json()["data"]
        self.assertEqual(product["spec_values"], self.values)
        rows = (await self.client.get("/products")).json()["data"]
        self.assertEqual(rows[0]["spec_values"], self.values)
        changed = {**self.values, str(self.fields["number"].id): 32}
        response = await self.client.put(f"/products/{product['id']}", json={
            "name": "Updated", "category_id": self.category.id, "spec_values": changed,
        })
        self.assertEqual(response.json()["data"]["spec_values"], changed)

    async def test_required_types_and_inapplicable_fields_are_rejected(self):
        for kind, value in (("text", ""), ("number", True), ("select", "Z"),
                            ("multi_select", ["Z"]), ("switch", "false"), ("date", "2026-02-30")):
            response = await self.create({**self.values, str(self.fields[kind].id): value})
            self.assertEqual(response.status_code, 422, response.text)
        response = await self.create({**self.values, str(self.disabled.id): "ignored"})
        self.assertEqual(response.status_code, 422)
        self.assertEqual(await ProductItem.all().count(), 0)

    async def test_legacy_edits_preserve_values_and_category_change_requires_new_fields(self):
        product = (await self.create()).json()["data"]
        response = await self.client.put(f"/products/{product['id']}", json={"name": "Rename", "category_id": self.category.id})
        self.assertEqual(response.json()["data"]["spec_values"], self.values)
        network = await ProductSpecAttribute.create(name="Bandwidth", code="bandwidth", category=self.other, required=True)
        response = await self.client.put(f"/products/{product['id']}", json={"name": "Network", "category_id": self.other.id})
        self.assertEqual(response.status_code, 422)
        saved = await ProductItem.get(id=product["id"])
        self.assertEqual(saved.category_id, self.category.id)
        response = await self.client.put(f"/products/{product['id']}", json={
            "name": "Network", "category_id": self.other.id, "spec_values": {str(network.id): "1Gbps"},
        })
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["data"]["spec_values"], {str(network.id): "1Gbps"})

    async def test_field_endpoint_auth_and_missing_category(self):
        self.assertEqual((await self.client.get("/product-spec-fields", params={"category_id": 999999})).status_code, 404)
        self.app.dependency_overrides.clear()
        self.assertEqual((await self.client.get("/product-spec-fields", params={"category_id": self.category.id})).status_code, 401)

        async def ordinary_user():
            self.user.is_superuser = False
            return self.user

        self.app.dependency_overrides[AuthControl.is_authed] = ordinary_user
        self.assertEqual((await self.client.get("/product-spec-fields", params={"category_id": self.category.id})).status_code, 403)
