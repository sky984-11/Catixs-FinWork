import unittest

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from tortoise import Tortoise

from app.api.v1 import v1_router
from app.core.init_app import remove_retired_feature_metadata
from app.models.admin import Api, Menu, Role
from app.models.project import CustomerRequirement
from app.models.product_center import ProductCategory, ProductItem, ProductPrice


class RetiredFeatureTests(unittest.IsolatedAsyncioTestCase):
    async def test_product_feature_cleanup_preserves_history_and_active_grants(self):
        role = await Role.create(name="product-admin")
        retired = [
            await Menu.create(name=mode, path=mode, component=f"/product-center/{mode}")
            for mode in ("configs", "pricing", "price-history")
        ]
        active = await Menu.create(name="Products", path="products", component="/product-center/products")
        retired_apis = [
            await Api.create(path=f"/api/v1/product-center/{path}", method="GET", summary="Test", tags="Test")
            for path in ("prices", "prices/{price_id}/notification", "price-history", "spec-configs",
                         "spec-config-groups/update", "products/{product_id}/sync-physical-servers")
        ]
        version_api = await Api.create(
            path="/api/v1/product-center/products/{product_id}/price-versions", method="GET",
            summary="Test", tags="Test",
        )
        await role.menus.add(*retired, active)
        await role.apis.add(*retired_apis, version_api)
        category = await ProductCategory.create(name="Historical category")
        product = await ProductItem.create(name="Historical product", code="HIST", category=category)
        price = await ProductPrice.create(product=product)
        await remove_retired_feature_metadata()
        await remove_retired_feature_metadata()
        self.assertEqual(await role.menus.all().values_list("id", flat=True), [active.id])
        self.assertEqual(await role.apis.all().values_list("id", flat=True), [version_api.id])
        self.assertTrue(await ProductPrice.filter(id=price.id).exists())

    async def asyncSetUp(self):
        await Tortoise.init(db_url="sqlite://:memory:", modules={"models": ["app.models"]})
        await Tortoise.generate_schemas()

    async def asyncTearDown(self):
        await Tortoise.close_connections()

    async def test_cleanup_is_idempotent_and_preserves_other_features_and_history(self):
        role = await Role.create(name="admin")
        parent = await Menu.create(name="IDC", path="/idc", component="Layout")
        child = await Menu.create(name="Orders", path="orders", component="/idc/orders", parent_id=parent.id)
        nested = await Menu.create(name="Nested", path="detail", component="legacy", parent_id=child.id)
        requirement = await Menu.create(name="Requirements", path="/requirements", component="/project-board/requirements")
        project = await Menu.create(name="Projects", path="/project-board", component="/project-board")
        retired_apis = [
            await Api.create(path=path, method="GET", summary="Test", tags="Test")
            for path in ("/api/v1/idc/orders", "/api/v1/requirement/list")
        ]
        active_api = await Api.create(path="/api/v1/project/list", method="GET", summary="Test", tags="Test")
        await role.menus.add(parent, child, nested, requirement, project)
        await role.apis.add(*retired_apis, active_api)
        history = await CustomerRequirement.create(title="Historical requirement")

        await remove_retired_feature_metadata()
        await remove_retired_feature_metadata()

        self.assertEqual(await Menu.all().values_list("id", flat=True), [project.id])
        self.assertEqual(await role.menus.all().values_list("id", flat=True), [project.id])
        self.assertEqual(await Api.all().values_list("id", flat=True), [active_api.id])
        self.assertEqual(await role.apis.all().values_list("id", flat=True), [active_api.id])
        self.assertTrue(await CustomerRequirement.filter(id=history.id).exists())

    async def test_retired_routes_are_unavailable(self):
        app = FastAPI()
        app.include_router(v1_router, prefix="/api/v1")
        paths = {route.path for route in app.routes}
        self.assertFalse(any(path.startswith(("/api/v1/idc/", "/api/v1/requirement/")) for path in paths))
        self.assertIn("/api/v1/project/list", paths)
        self.assertIn("/api/v1/product-center/products", paths)
        self.assertIn("/api/v1/product-center/attributes", paths)
        self.assertIn("/api/v1/product-center/products/{product_id}/price-versions", paths)
        self.assertFalse(any(path.startswith((
            "/api/v1/product-center/prices", "/api/v1/product-center/price-history",
            "/api/v1/product-center/spec-config",
        )) for path in paths))
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            for method, path in (
                ("GET", "/api/v1/idc/orders"),
                ("POST", "/api/v1/idc/billing/generate"),
                ("GET", "/api/v1/requirement/list"),
                ("POST", "/api/v1/requirement/create"),
                ("DELETE", "/api/v1/requirement/delete"),
                ("GET", "/api/v1/product-center/prices"),
                ("POST", "/api/v1/product-center/prices"),
                ("PUT", "/api/v1/product-center/prices/1/notification"),
                ("GET", "/api/v1/product-center/price-history"),
                ("DELETE", "/api/v1/product-center/price-history/1"),
                ("GET", "/api/v1/product-center/spec-configs"),
                ("POST", "/api/v1/product-center/spec-config-groups/update"),
                ("POST", "/api/v1/product-center/products/1/sync-physical-servers"),
            ):
                response = await client.request(method, path)
                self.assertEqual(response.status_code, 404, path)
