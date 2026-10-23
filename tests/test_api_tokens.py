import hashlib
import importlib.util
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

import jwt
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from tortoise import Tortoise

from app.api.v1.api_tokens import router
from app.core.dependency import DependAuth, DependPermission
from app.core.init_app import ensure_api_token_menu, ensure_task_menu
from app.core.middlewares import HttpAuditLogMiddleware
from app.models.admin import Api, ApiToken, AuditLog, Menu, Role, User
from app.services.api_tokens import generate_token
from app.settings import settings


class ApiTokenTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        await Tortoise.init(db_url="sqlite://:memory:", modules={"models": ["app.models"]})
        await Tortoise.generate_schemas()
        self.admin = await User.create(username="token-admin", email="admin@test.invalid", is_superuser=True)
        self.user = await User.create(username="token-user", email="user@test.invalid")
        self.role = await Role.create(name="token-reader")
        await self.user.roles.add(self.role)
        self.app = FastAPI()
        self.app.include_router(router, prefix="/api/v1/api-tokens", dependencies=[DependPermission])

        @self.app.get("/protected", dependencies=[DependPermission])
        async def protected():
            return {"ok": True}

        @self.app.get("/authenticated", dependencies=[DependAuth])
        async def authenticated():
            return {"ok": True}

        self.app.add_middleware(HttpAuditLogMiddleware, methods=["POST", "PUT", "DELETE"], exclude_paths=[])
        self.client = AsyncClient(transport=ASGITransport(app=self.app), base_url="http://test")
        self.headers = {"token": self.jwt_for(self.admin)}

    def jwt_for(self, user):
        return jwt.encode(
            {"user_id": user.id, "exp": datetime.now(timezone.utc) + timedelta(hours=1)},
            settings.SECRET_KEY,
            algorithm=settings.JWT_ALGORITHM,
        )

    async def asyncTearDown(self):
        await self.client.aclose()
        await Tortoise.close_connections()

    async def create(self, **kwargs):
        payload = {"name": "integration", "user_id": self.user.id, **kwargs}
        response = await self.client.post("/api/v1/api-tokens", json=payload, headers=self.headers)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.headers["cache-control"], "no-store")
        return response.json()["data"]

    async def assert_auth(self, token, status=200):
        response = await self.client.get("/authenticated", headers={"token": token})
        self.assertEqual(response.status_code, status)

    async def test_permanent_hash_only_and_single_disclosure(self):
        data = await self.create()
        self.assertIsNone(data["expires_at"])
        item = await ApiToken.get(id=data["id"])
        self.assertEqual(item.token_hash, hashlib.sha256(data["token"].encode()).hexdigest())
        self.assertNotIn(data["token"], str(await item.to_dict()))
        response = await self.client.get("/api/v1/api-tokens", headers=self.headers)
        self.assertNotIn(data["token"], response.text)
        self.assertNotIn("token_hash", response.text)
        await self.assert_auth(data["token"])
        await item.refresh_from_db()
        self.assertIsNotNone(item.last_used_at)
        logs = await AuditLog.all().values()
        self.assertNotIn(data["token"], str(logs))
        self.assertEqual(logs[0]["user_id"], self.admin.id)

    async def test_bearer_jwt_and_conflicting_headers(self):
        data = await self.create()
        response = await self.client.get("/authenticated", headers={"Authorization": f"Bearer {data['token']}"})
        self.assertEqual(response.status_code, 200)
        await self.assert_auth(self.jwt_for(self.user))
        response = await self.client.get(
            "/authenticated", headers={**self.headers, "Authorization": f"Bearer {data['token']}"}
        )
        self.assertEqual(response.status_code, 401)
        for headers in [{}, {"Authorization": "Basic abc"}, {"token": "fw_api_invalid"}, {"token": "invalid-jwt"}]:
            response = await self.client.get("/authenticated", headers=headers)
            self.assertEqual(response.status_code, 401)

    async def test_disabled_expired_deleted_and_rotated_tokens(self):
        data = await self.create()
        path = f"/api/v1/api-tokens/{data['id']}"
        response = await self.client.post(path + "/status", json={"is_enabled": False}, headers=self.headers)
        self.assertEqual(response.status_code, 200)
        await self.assert_auth(data["token"], 401)
        await self.client.post(path + "/status", json={"is_enabled": True}, headers=self.headers)
        await self.assert_auth(data["token"])
        response = await self.client.post(path + "/regenerate", headers=self.headers)
        self.assertEqual(response.status_code, 200)
        new_token = response.json()["data"]["token"]
        await self.assert_auth(data["token"], 401)
        await self.assert_auth(new_token)
        await ApiToken.filter(id=data["id"]).update(expires_at=datetime.now(timezone.utc) - timedelta(seconds=1))
        await self.assert_auth(new_token, 401)
        await ApiToken.filter(id=data["id"]).update(expires_at=None)
        await self.assert_auth(new_token)
        response = await self.client.delete(path, headers=self.headers)
        self.assertEqual(response.status_code, 200)
        await self.assert_auth(new_token, 401)
        self.assertFalse(await ApiToken.filter(id=data["id"]).exists())
        self.assertNotIn(new_token, str(await AuditLog.all().values()))

    async def test_live_user_state_and_permissions(self):
        data = await self.create()
        headers = {"token": data["token"]}
        self.assertEqual((await self.client.get("/protected", headers=headers)).status_code, 403)
        permission = await Api.create(path="/protected", method="GET", summary="test", tags="test")
        await self.role.apis.add(permission)
        self.assertEqual((await self.client.get("/protected", headers=headers)).status_code, 200)
        await self.role.apis.remove(permission)
        self.assertEqual((await self.client.get("/protected", headers=headers)).status_code, 403)
        self.user.is_active = False
        await self.user.save()
        await self.assert_auth(data["token"], 401)
        await self.assert_auth(self.jwt_for(self.user), 401)
        self.user.is_active = True
        await self.user.save()
        await self.assert_auth(data["token"])
        await self.user.delete()
        await self.assert_auth(data["token"], 401)
        self.assertFalse(await ApiToken.filter(id=data["id"]).exists())

    async def test_non_admin_management_is_forbidden_even_with_api_permission(self):
        data = await self.create()
        for method, path in [("GET", "/api/v1/api-tokens"), ("POST", "/api/v1/api-tokens")]:
            permission = await Api.create(path=path, method=method, summary="test", tags="test")
            await self.role.apis.add(permission)
        for headers in [{"token": self.jwt_for(self.user)}, {"token": data["token"]}]:
            response = await self.client.get("/api/v1/api-tokens", headers=headers)
            self.assertEqual(response.status_code, 403)
            response = await self.client.post(
                "/api/v1/api-tokens", headers=headers, json={"name": "escalate", "user_id": self.admin.id}
            )
            self.assertEqual(response.status_code, 403)
            for method, suffix, payload in [
                ("PUT", "", {"name": "changed"}),
                ("POST", "/status", {"is_enabled": False}),
                ("POST", "/regenerate", None),
                ("DELETE", "", None),
            ]:
                response = await self.client.request(
                    method, f"/api/v1/api-tokens/{data['id']}{suffix}", headers=headers, json=payload
                )
                self.assertEqual(response.status_code, 403)
        self.assertEqual((await self.client.get("/api/v1/api-tokens")).status_code, 401)
        self.assertEqual((await self.client.get("/api/v1/api-tokens", headers={"token": "dev"})).status_code, 401)

    async def test_input_validation_edit_and_filters(self):
        for payload in [
            {"name": " "},
            {"expires_at": "2020-01-01T00:00:00Z"},
            {"expires_at": "2099-01-01T00:00:00"},
            {"name": "x" * 101},
            {"user_id": 0},
        ]:
            response = await self.client.post(
                "/api/v1/api-tokens", headers=self.headers, json={"name": "test", "user_id": self.user.id, **payload}
            )
            self.assertEqual(response.status_code, 422)
        response = await self.client.post(
            "/api/v1/api-tokens", headers=self.headers, json={"name": "test", "user_id": 999999}
        )
        self.assertEqual(response.status_code, 400)
        data = await self.create(expires_at=(datetime.now(timezone.utc) + timedelta(days=2)).isoformat())
        path = f"/api/v1/api-tokens/{data['id']}"
        response = await self.client.put(path, headers=self.headers, json={"name": "renamed", "user_id": self.admin.id})
        self.assertEqual(response.status_code, 422)
        response = await self.client.put(path, headers=self.headers, json={"name": "renamed", "expires_at": None})
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json()["data"]["expires_at"])
        self.assertNotIn(data["token"], response.text)
        for params, total in [({"name": "renamed", "status": "enabled"}, 1), ({"status": "expired"}, 0)]:
            response = await self.client.get("/api/v1/api-tokens", headers=self.headers, params=params)
            self.assertEqual(response.json()["total"], total)
        self.assertEqual((await self.client.delete("/api/v1/api-tokens/999999", headers=self.headers)).status_code, 404)
        self.assertEqual(
            (await self.client.get("/api/v1/api-tokens", headers=self.headers, params={"page_size": 101})).status_code,
            422,
        )

    async def test_admin_role_bearer_audit_and_menu_idempotency(self):
        admin_role = await Role.create(name="管理员")
        await self.user.roles.add(admin_role)
        token, digest = generate_token()
        await ApiToken.create(name="admin-client", user=self.user, token_hash=digest)
        response = await self.client.post(
            "/api/v1/api-tokens",
            headers={"Authorization": f"Bearer {token}"},
            json={"name": "another", "user_id": self.user.id},
        )
        self.assertEqual(response.status_code, 200)
        log = await AuditLog.first()
        self.assertEqual(log.user_id, self.user.id)
        self.assertIsNone(log.response_body)
        await ensure_task_menu()
        first = await ensure_api_token_menu()
        second = await ensure_api_token_menu()
        self.assertEqual(first.id, second.id)
        self.assertEqual(await Menu.filter(component="/system/api-tokens").count(), 1)

    async def test_sqlite_migration_upgrade_downgrade(self):
        path = Path(__file__).parents[1] / "migrations/models/179_20261023120000_api_tokens.py"
        spec = importlib.util.spec_from_file_location("api_token_migration", path)
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)
        db = Tortoise.get_connection("default")
        await db.execute_script(await migration.downgrade(db))
        await db.execute_script(await migration.upgrade(db))
        await db.execute_script(await migration.upgrade(db))
        await self.create()
        self.assertEqual(await ApiToken.all().count(), 1)
        await db.execute_script(await migration.downgrade(db))
        self.assertEqual(await User.all().count(), 2)


if __name__ == "__main__":
    unittest.main()
