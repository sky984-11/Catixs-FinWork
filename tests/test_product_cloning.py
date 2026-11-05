import unittest
from unittest.mock import AsyncMock, patch

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from tortoise import Tortoise
from tortoise.exceptions import IntegrityError

from app.api.v1 import v1_router
from app.core.dependency import AuthControl
from app.models.admin import User
from app.models.customer_center import CrmCustomer
from app.models.product_center import ProductCategory, ProductItem, ProductPriceVersion, ProductVariant
from app.models.product_order import ProductOrder, ProductOrderItem


class ProductCloningTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        await Tortoise.init(db_url="sqlite://:memory:", modules={"models": ["app.models"]})
        await Tortoise.generate_schemas()
        category = await ProductCategory.create(name="Compute")
        self.product = await ProductItem.create(
            name="Server",
            code="SERVER",
            category=category,
            region="HK",
            billing_unit="resource",
            min_contract_months=12,
            description="Source description",
            spec_values={"7": 128},
        )
        self.variant = await ProductVariant.create(
            product=self.product,
            name="128GB",
            code="SOURCE-128",
            spec_values={"7": 128},
            spec_snapshot=[{"id": 7, "name": "Memory", "value": 128, "unit": "GB"}],
        )
        await ProductVariant.create(
            product=self.product, name="256GB", code="SOURCE-256", status="offline", spec_values={"7": 256}
        )
        self.price = await ProductPriceVersion.create(
            product=self.product,
            variant=self.variant,
            version=2,
            currency="USD",
            mrc="99.99",
            nrc="10.00",
            period_months=3,
            billing_unit="resource",
        )
        customer = await CrmCustomer.create(name="Customer")
        await ProductPriceVersion.create(
            product=self.product,
            variant=self.variant,
            customer=customer,
            customer_name="Customer",
            version=3,
            currency="USD",
            mrc="80",
            nrc="0",
            billing_unit="resource",
        )
        order = await ProductOrder.create(order_no="ORDER1", name="Existing order", customer=customer)
        await ProductOrderItem.create(order=order, product=self.product, variant=self.variant, quantity=1)
        self.user = await User.create(username="admin", email="clone@example.test", is_superuser=True)
        self.app = FastAPI()
        self.app.include_router(v1_router, prefix="/api/v1")

        async def authed():
            return self.user

        self.app.dependency_overrides[AuthControl.is_authed] = authed
        self.client = AsyncClient(transport=ASGITransport(app=self.app), base_url="http://test/api/v1/product-center/")
        self.path = f"products/{self.product.id}/clone"
        self.payload = {"name": "Cloned server", "code": "SERVER-COPY"}

    async def asyncTearDown(self):
        await self.client.aclose()
        await Tortoise.close_connections()

    async def test_clones_full_catalog_without_business_links(self):
        response = await self.client.post(self.path, json=self.payload)
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()["data"]
        self.assertNotEqual(data["id"], self.product.id)
        for field in (
            "category_id",
            "region",
            "description",
            "billing_unit",
            "min_contract_months",
            "spec_values",
            "status",
        ):
            self.assertEqual(data[field], getattr(self.product, field))
        variants = await ProductVariant.filter(product_id=data["id"]).order_by("id")
        self.assertEqual([row.name for row in variants], ["128GB", "256GB"])
        self.assertEqual(variants[1].status, "offline")
        self.assertNotEqual(variants[0].code, self.variant.code)
        self.assertEqual(variants[0].spec_snapshot, self.variant.spec_snapshot)
        prices = await ProductPriceVersion.filter(product_id=data["id"])
        self.assertEqual(len(prices), 1)
        self.assertEqual(prices[0].variant_id, variants[0].id)
        self.assertEqual(prices[0].version, 2)
        self.assertEqual(prices[0].mrc, self.price.mrc)
        self.assertIsNone(prices[0].customer_id)
        self.assertEqual(await ProductOrder.all().count(), 1)
        self.assertEqual(await ProductOrderItem.filter(product_id=data["id"]).count(), 0)
        variants[0].spec_values = {"7": 512}
        await variants[0].save()
        await self.variant.refresh_from_db()
        self.assertEqual(self.variant.spec_values, {"7": 128})
        self.assertEqual(await ProductPriceVersion.filter(product_id=self.product.id).count(), 2)

    async def test_can_omit_prices_and_clone_legacy_product(self):
        response = await self.client.post(self.path, json={**self.payload, "copy_prices": False})
        self.assertEqual(response.status_code, 200, response.text)
        new_id = response.json()["data"]["id"]
        self.assertEqual(await ProductVariant.filter(product_id=new_id).count(), 2)
        self.assertEqual(await ProductPriceVersion.filter(product_id=new_id).count(), 0)
        legacy = await ProductItem.create(name="Legacy", code="LEGACY")
        await ProductPriceVersion.create(product=legacy, version=1, currency="CNY", mrc="10", billing_unit="month")
        response = await self.client.post(
            f"products/{legacy.id}/clone", json={"name": "Legacy copy", "code": "LEGACY-COPY"}
        )
        self.assertEqual(response.status_code, 200, response.text)
        copied = await ProductPriceVersion.get(product_id=response.json()["data"]["id"])
        self.assertIsNone(copied.variant_id)

    async def test_validation_and_transaction_rollback(self):
        for payload, code in [
            ({**self.payload, "code": self.product.code}, 409),
            ({**self.payload, "name": "   "}, 422),
            ({**self.payload, "code": "x" * 81}, 422),
            ({**self.payload, "copy_prices": "yes"}, 422),
        ]:
            self.assertEqual((await self.client.post(self.path, json=payload)).status_code, code)
        self.assertEqual((await self.client.post("products/999999/clone", json=self.payload)).status_code, 404)
        with patch(
            "app.api.v1.product_cloning.ProductPriceVersion.bulk_create",
            new=AsyncMock(side_effect=IntegrityError("fixture")),
        ):
            response = await self.client.post(self.path, json=self.payload)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(await ProductItem.all().count(), 1)
        self.assertEqual(await ProductVariant.all().count(), 2)

    async def test_auth_and_permissions(self):
        self.app.dependency_overrides.clear()
        self.assertEqual((await self.client.post(self.path, json=self.payload)).status_code, 401)

        async def ordinary():
            self.user.is_superuser = False
            return self.user

        self.app.dependency_overrides[AuthControl.is_authed] = ordinary
        self.assertEqual((await self.client.post(self.path, json=self.payload)).status_code, 403)
        self.assertEqual(await ProductItem.all().count(), 1)
