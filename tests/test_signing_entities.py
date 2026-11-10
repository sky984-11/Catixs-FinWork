import unittest

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from tortoise import Tortoise

from app.api.v1 import v1_router
from app.core.dependency import AuthControl
from app.core.init_app import ensure_customer_center_menu, ensure_required_signing_entities
from app.models.admin import Menu, User
from app.models.customer_center import CrmSigningEntity


class SigningEntityTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        await Tortoise.init(db_url="sqlite://:memory:", modules={"models": ["app.models"]})
        await Tortoise.generate_schemas()
        self.user = await User.create(username="entity-admin", email="entity@test.invalid", is_superuser=True)
        self.app = FastAPI()
        self.app.include_router(v1_router, prefix="/api/v1")

        async def authed():
            return self.user

        self.app.dependency_overrides[AuthControl.is_authed] = authed
        self.client = AsyncClient(transport=ASGITransport(app=self.app), base_url="http://test/api/v1/customer-center/")

    async def asyncTearDown(self):
        await self.client.aclose()
        await Tortoise.close_connections()

    async def test_manage_validate_and_permissions(self):
        response = await self.client.post("signing-entities", json={"name": "Test", "code": "T", "logo_url": "/logos/test.png"})
        self.assertEqual(response.status_code, 200, response.text)
        entity_id = response.json()["data"]["id"]
        response = await self.client.put(f"signing-entities/{entity_id}", json={"name": "Renamed", "status": False})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual((await self.client.get("signing-entities")).json()["data"], [])
        self.assertEqual(len((await self.client.get("signing-entities?include_inactive=true")).json()["data"]), 1)
        self.assertEqual((await self.client.post("signing-entities", json={"name": "Renamed"})).status_code, 409)
        self.assertEqual((await self.client.post("signing-entities", json={"name": "   "})).status_code, 422)
        self.assertEqual((await self.client.post("signing-entities", json={"name": "Other", "logo_url": "javascript:alert(1)"})).status_code, 422)
        self.assertEqual((await self.client.put("signing-entities/999", json={"name": "Missing"})).status_code, 404)
        self.user.is_superuser = False
        await self.user.save()
        self.assertEqual((await self.client.post("signing-entities", json={"name": "Denied"})).status_code, 403)
        self.app.dependency_overrides.clear()
        self.assertEqual((await self.client.get("signing-entities")).status_code, 401)

    async def test_restart_preserves_managed_data_and_menu(self):
        await ensure_required_signing_entities()
        self.assertEqual(await CrmSigningEntity.all().count(), 3)
        entity = await CrmSigningEntity.first()
        entity.name = "Renamed issuer"
        entity.code = "RENAMED"
        entity.address = "Managed address"
        entity.logo_url = "/logos/custom.png"
        entity.status = False
        await entity.save()
        await ensure_required_signing_entities()
        await entity.refresh_from_db()
        self.assertEqual(await CrmSigningEntity.all().count(), 3)
        self.assertEqual(entity.address, "Managed address")
        self.assertEqual(entity.logo_url, "/logos/custom.png")
        self.assertFalse(entity.status)
        await ensure_customer_center_menu()
        await ensure_customer_center_menu()
        self.assertEqual(await Menu.filter(component="/customer-center/signing-entities").count(), 1)
