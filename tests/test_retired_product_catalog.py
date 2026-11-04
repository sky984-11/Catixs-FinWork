import unittest
from datetime import date, datetime

from tortoise import Tortoise

from app.models.company import BillingProductTemplate
from app.models.product_center import (ProductCategory, ProductItem,
                                       ProductPrice, ProductPriceHistory,
                                       ProductPriceVersion,
                                       ProductSpecAttribute, ProductSpecConfig)
from app.services.retired_product_catalog import (
    RETIRED_CATALOG_PRODUCTS, remove_unused_retired_catalog_products)


class RetiredProductCatalogTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        await Tortoise.init(db_url="sqlite://:memory:", modules={"models": ["app.models"]})
        await Tortoise.generate_schemas()

    async def asyncTearDown(self):
        await Tortoise.close_connections()

    async def seed(self, code="IP.ASN", **changes):
        name = RETIRED_CATALOG_PRODUCTS[code]
        category = await ProductCategory.create(name=name, code=f"IDC.{code}.LEAF")
        return await ProductItem.create(**{"code": code, "name": name, "category": category, **changes})

    async def test_cleans_all_unused_seeds_but_preserves_categories_and_custom_products(self):
        for code in RETIRED_CATALOG_PRODUCTS:
            await self.seed(code)
        category = await ProductCategory.get(code="IDC.IP.ASN.LEAF")
        custom = await ProductItem.create(name="ASN", code="PROD001", category=category)
        self.assertEqual(await remove_unused_retired_catalog_products(), len(RETIRED_CATALOG_PRODUCTS))
        self.assertEqual(await ProductItem.all().values_list("id", flat=True), [custom.id])
        self.assertEqual(await ProductCategory.all().count(), len(RETIRED_CATALOG_PRODUCTS))
        self.assertEqual(await remove_unused_retired_catalog_products(), 0)

    async def test_modified_products_and_non_seed_categories_are_preserved(self):
        await self.seed("IP.ASN", name="Custom ASN")
        await self.seed("IP.V4", billing_unit="ip")
        await self.seed("IP.V6", min_contract_months=12)
        await self.seed("NET.TRANSIT", region="HK")
        await self.seed("NET.IEPL", description="Customer configured")
        await self.seed("NET.WAVE", status="offline")
        category = await ProductCategory.create(name="Cloud Connect", code="CUSTOM")
        await ProductItem.create(code="CLOUD.CONNECT", name="Cloud Connect", category=category)
        self.assertEqual(await remove_unused_retired_catalog_products(), 0)
        self.assertEqual(await ProductItem.all().count(), 7)

    async def test_specs_prices_history_versions_and_billing_references_are_preserved(self):
        product = await self.seed("IP.ASN")
        attribute = await ProductSpecAttribute.create(name="Test", code="test")
        await ProductSpecConfig.create(product=product, attribute=attribute)
        product = await self.seed("IP.V4")
        await ProductPrice.create(product=product)
        product = await self.seed("IP.V6")
        await ProductPriceHistory.create(product_id=product.id, off_shelf_at=datetime.now())
        product = await self.seed("NET.TRANSIT")
        await ProductPriceVersion.create(
            product=product,
            version=1,
            currency="CNY",
            mrc=100,
            billing_unit="month",
            effective_date=date(2026, 1, 1),
            expiry_date=date(2027, 1, 1),
        )
        product = await self.seed("NET.IEPL")
        await BillingProductTemplate.create(name="Template", product_code=product.code)
        self.assertEqual(await remove_unused_retired_catalog_products(), 0)
        self.assertEqual(await ProductItem.all().count(), 5)
