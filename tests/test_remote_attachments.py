import base64
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from tortoise import Tortoise

from app.api.v1 import v1_router
from app.api.v1.remote_assistance import remote_assistance as module
from app.core.dependency import AuthControl
from app.core.middlewares import HttpAuditLogMiddleware
from starlette.requests import Request
from app.models.admin import Api, Role, User
from app.models.remote_assistance import RemoteHands, RemoteHandsPlan


class RemoteAttachmentTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        await Tortoise.init(db_url="sqlite://:memory:", modules={"models": ["app.models"]})
        await Tortoise.generate_schemas()
        self.user = await User.create(username="attachment-user", email="attachment@example.test")
        self.app = FastAPI()
        self.app.include_router(v1_router, prefix="/api/v1")
        self.app.dependency_overrides[AuthControl.is_authed] = lambda: self.user
        self.client = AsyncClient(transport=ASGITransport(app=self.app), base_url="http://test/api/v1")
        self.directory = tempfile.TemporaryDirectory()
        self.mock_dir = patch.object(module, "PLAN_ATTACHMENT_DIR", Path(self.directory.name))
        self.mock_dir.start()

    async def asyncTearDown(self):
        await self.client.aclose()
        self.mock_dir.stop()
        self.directory.cleanup()
        await Tortoise.close_connections()

    async def grant(self, method, path):
        role, _ = await Role.get_or_create(name="ops")
        api = await Api.create(method=method, path=f"/api/v1/remote-assistance/{path}", summary="test", tags="test")
        await role.apis.add(api)
        await self.user.roles.add(role)

    async def upload(self, route="attachments/upload"):
        response = await self.client.post(f"/remote-assistance/{route}", files={"file": ("test.txt", b"content")})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()["data"]

    async def test_login_only_upload_and_draft_delete(self):
        for route in ("attachments/upload", "plans/attachments/upload"):
            attachment = await self.upload(route)
            path = Path(self.directory.name) / attachment["url"].rsplit("/", 1)[-1]
            self.assertEqual(path.read_bytes(), b"content")
            response = await self.client.request(
                "DELETE", "/remote-assistance/attachments", json={"url": attachment["url"]}
            )
            self.assertEqual(response.status_code, 200)
            self.assertFalse(path.exists())

    async def test_json_upload_matches_project_board_and_can_be_deleted(self):
        content = b"\x00\xff\x80binary attachment"
        encoded = base64.b64encode(content).decode("ascii")
        for route in ("attachments/upload", "plans/attachments/upload"):
            for data in (encoded, f"data:application/octet-stream;base64,{encoded}"):
                response = await self.client.post(
                    f"/remote-assistance/{route}",
                    json={"filename": "sample.bin", "content_type": "application/octet-stream", "data": data},
                )
                self.assertEqual(response.status_code, 200, response.text)
                attachment = response.json()["data"]
                path = Path(self.directory.name) / attachment["url"].split("/")[-1]
                self.assertEqual(path.read_bytes(), content)
                self.assertEqual(attachment["size"], len(content))
                response = await self.client.request(
                    "DELETE", "/remote-assistance/attachments", json={"url": attachment["url"]}
                )
                self.assertEqual(response.status_code, 200)
                self.assertFalse(path.exists())

    async def test_json_invalid_empty_and_oversized_content(self):
        for data in ("%%%", "data:text/plain,hello", "", "data:text/plain;base64,", "非Base64"):
            response = await self.client.post(
                "/remote-assistance/attachments/upload", json={"filename": "test.txt", "data": data}
            )
            self.assertEqual(response.status_code, 400, response.text)
        response = await self.client.post("/remote-assistance/attachments/upload", json={"filename": "missing"})
        self.assertEqual(response.status_code, 422)
        with patch.object(module, "MAX_ATTACHMENT_SIZE", 3):
            response = await self.client.post(
                "/remote-assistance/attachments/upload", json={"filename": "large", "data": "aGVsbG8="}
            )
            self.assertEqual(response.status_code, 400)
        self.assertEqual(list(Path(self.directory.name).iterdir()), [])

    async def test_json_upload_requires_auth_and_excludes_content_from_audit(self):
        self.app.dependency_overrides.clear()
        response = await self.client.post(
            "/remote-assistance/attachments/upload", json={"filename": "test", "data": "aGVsbG8="}
        )
        self.assertEqual(response.status_code, 422)
        middleware = HttpAuditLogMiddleware(self.app, methods=["POST"], exclude_paths=[])
        for route in ("attachments/upload", "plans/attachments/upload"):
            request = Request({"type": "http", "path": f"/api/v1/remote-assistance/{route}", "headers": []})
            self.assertEqual(await middleware.get_request_args(request), {})

    async def test_authentication_and_validation(self):
        self.app.dependency_overrides.clear()
        response = await self.client.post("/remote-assistance/attachments/upload", files={"file": ("test", b"x")})
        self.assertNotEqual(response.status_code, 200)
        response = await self.client.request(
            "DELETE", "/remote-assistance/attachments", json={"url": "/uploads/remote-plans/" + "a" * 32 + ".bin"}
        )
        self.assertNotEqual(response.status_code, 200)
        self.app.dependency_overrides[AuthControl.is_authed] = lambda: self.user
        response = await self.client.request(
            "DELETE", "/remote-assistance/attachments", json={"url": "/uploads/remote-plans/../secret"}
        )
        self.assertEqual(response.status_code, 422)
        response = await self.client.post("/remote-assistance/attachments/upload", files={"file": ("empty", b"")})
        self.assertEqual(response.status_code, 400)

    async def test_record_save_preserve_and_physical_delete(self):
        await self.grant("POST", "remote-hands")
        await self.grant("PUT", "remote-hands/{item_id}")
        attachment = await self.upload()
        response = await self.client.post(
            "/remote-assistance/remote-hands", json={"customer": "test", "attachments": [attachment]}
        )
        self.assertEqual(response.status_code, 200, response.text)
        record = await RemoteHands.first()
        response = await self.client.put(f"/remote-assistance/remote-hands/{record.id}", json={"customer": "edited"})
        self.assertEqual(response.status_code, 200, response.text)
        await record.refresh_from_db()
        self.assertEqual(record.attachments, [attachment])
        extra = await self.upload()
        response = await self.client.put(
            f"/remote-assistance/remote-hands/{record.id}",
            json={"customer": "edited", "attachments": [attachment, extra]},
        )
        self.assertEqual(response.status_code, 200, response.text)
        response = await self.client.request(
            "DELETE", "/remote-assistance/attachments", json={"url": attachment["url"]}
        )
        self.assertEqual(response.status_code, 200, response.text)
        await record.refresh_from_db()
        self.assertEqual(record.attachments, [extra])
        self.assertFalse((Path(self.directory.name) / attachment["url"].split("/")[-1]).exists())

    async def test_shared_legacy_attachment_permissions_and_deletion(self):
        attachment = await self.upload()
        record = await RemoteHands.create(customer="test")
        plan = await RemoteHandsPlan.create(
            customer="test", status="done", remote_hands_id=record.id, attachments=[attachment]
        )
        self.assertEqual((await module._remote_to_dict(record))["attachments"], [attachment])
        response = await self.client.request(
            "DELETE", "/remote-assistance/attachments", json={"url": attachment["url"]}
        )
        self.assertEqual(response.status_code, 403)
        self.assertTrue((Path(self.directory.name) / attachment["url"].split("/")[-1]).exists())
        await self.grant("PUT", "plans/{plan_id}")
        response = await self.client.request(
            "DELETE", "/remote-assistance/attachments", json={"url": attachment["url"]}
        )
        self.assertEqual(response.status_code, 200, response.text)
        await plan.refresh_from_db()
        self.assertEqual(plan.attachments, [])
        self.assertEqual((await module._remote_to_dict(record))["attachments"], [])

    async def test_complete_plan_transfers_attachments(self):
        attachment = await self.upload()
        plan = await RemoteHandsPlan.create(customer="test", attachments=[attachment])
        result = await module.complete_plan(plan.id, module.RemoteHandsPlanCompletePayload())
        self.assertEqual(result.status_code, 200, result.body)
        record = await RemoteHands.get(id=json.loads(result.body)["data"]["id"])
        self.assertEqual(record.attachments, [attachment])

    async def test_delete_failure_restores_file_and_references(self):
        attachment = await self.upload()
        record = await RemoteHands.create(customer="test", attachments=[attachment])
        await self.grant("PUT", "remote-hands/{item_id}")
        with patch.object(RemoteHands, "save", new=AsyncMock(side_effect=RuntimeError("database failure"))):
            response = await self.client.request(
                "DELETE", "/remote-assistance/attachments", json={"url": attachment["url"]}
            )
        self.assertEqual(response.status_code, 500)
        await record.refresh_from_db()
        self.assertEqual(record.attachments, [attachment])
        self.assertEqual((Path(self.directory.name) / attachment["url"].split("/")[-1]).read_bytes(), b"content")

    async def test_template_permission_still_denies_other_methods(self):
        record = await RemoteHands.create(customer="test")
        response = await self.client.put(f"/remote-assistance/remote-hands/{record.id}", json={"customer": "denied"})
        self.assertEqual(response.status_code, 403)
        await self.grant("PUT", "remote-hands/{item_id}")
        response = await self.client.delete(f"/remote-assistance/remote-hands/{record.id}")
        self.assertEqual(response.status_code, 403)
        self.assertTrue(await RemoteHands.filter(id=record.id).exists())


if __name__ == "__main__":
    unittest.main()
