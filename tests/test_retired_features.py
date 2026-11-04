import unittest

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from tortoise import Tortoise

from app.api.v1 import v1_router
from app.core.init_app import remove_retired_feature_metadata
from app.models.admin import Api, Menu, Role
from app.models.project import CustomerRequirement


class RetiredFeatureTests(unittest.IsolatedAsyncioTestCase):
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
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            for method, path in (
                ("GET", "/api/v1/idc/orders"),
                ("POST", "/api/v1/idc/billing/generate"),
                ("GET", "/api/v1/requirement/list"),
                ("POST", "/api/v1/requirement/create"),
                ("DELETE", "/api/v1/requirement/delete"),
            ):
                response = await client.request(method, path)
                self.assertEqual(response.status_code, 404, path)
