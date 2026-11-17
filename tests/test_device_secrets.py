import json
import unittest
from unittest.mock import AsyncMock, patch

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from starlette.requests import Request
from tortoise import Tortoise

from app.api.v1.assets import assets
from app.core.dependency import AuthControl, DependPermission
from app.core.middlewares import HttpAuditLogMiddleware
from app.models import AssetCabinet, AssetDevice, AssetLocation, AssetRegion, User
from app.schemas.assets import AssetDeviceRedfishProbe, AssetDeviceUpdate
from app.schemas.base import Success
from app.services.device_secrets import MASK, mask_ipmi, preserve_ipmi
from app.utils.password import get_password_hash


class DeviceSecretTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        await Tortoise.init(db_url="sqlite://:memory:", modules={"models": ["app.models"]})
        await Tortoise.generate_schemas()
        region = await AssetRegion.create(name="R", code="R")
        location = await AssetLocation.create(name="L", region=region)
        cabinet = await AssetCabinet.create(name="C", location=location)
        self.device = await AssetDevice.create(
            name="Test",
            asset_no="TEST",
            cabinet=cabinet,
            region=region,
            location=location,
            attributes={
                "ipmi_host": "192.0.2.1",
                "ipmi_user": "ADMIN",
                "ipmi_password": "test-device-secret",
                "nodes": [{"name": "N1", "ipmiPassword": "test-node-secret"}],
            },
        )
        self.user = await User.create(
            username="secret-admin",
            email="test@example.invalid",
            is_superuser=True,
            password=get_password_hash("test-login-password"),
        )
        self.app = FastAPI()
        self.app.include_router(assets.router, prefix="/api/v1/asset", dependencies=[DependPermission])

        async def auth():
            return self.user

        self.app.dependency_overrides[AuthControl.is_authed] = auth
        self.client = AsyncClient(transport=ASGITransport(app=self.app), base_url="http://test/api/v1/asset")
        self.permission = patch.object(assets, "can_view_device_secrets", AsyncMock(return_value=True))
        self.permission.start()

    async def asyncTearDown(self):
        self.permission.stop()
        await self.client.aclose()
        await Tortoise.close_connections()

    async def test_admin_payload_never_contains_plaintext(self):
        result = await assets.device_to_dict(self.device, can_view_secrets=True)
        self.assertEqual(result["attributes"]["ipmi_password"], MASK)
        self.assertEqual(result["attributes"]["nodes"][0]["ipmiPassword"], MASK)
        self.assertNotIn("test-device-secret", json.dumps(result))
        self.assertEqual(self.device.attributes["ipmi_password"], "test-device-secret")

    async def test_resource_board_does_not_bypass_masking(self):
        from app.api.v1.resources.resources import device_to_sales_rows

        await self.device.fetch_related("cabinet", "location", "region")
        result = json.dumps(device_to_sales_rows(self.device))
        self.assertNotIn("test-device-secret", result)
        self.assertNotIn("test-node-secret", result)

    async def test_masks_preserved_on_save_and_cannot_be_stored_as_password(self):
        payload = AssetDeviceUpdate(
            id=self.device.id,
            cabinet_id=self.device.cabinet_id,
            asset_no="TEST",
            name="Test",
            attributes={"ipmi_password": MASK, "nodes": [{"name": "N1", "ipmi_password": MASK}]},
        )
        await assets.prepare_device_attributes_for_save(payload)
        self.assertEqual(payload.attributes["ipmi_password"], "test-device-secret")
        self.assertEqual(payload.attributes["nodes"][0]["ipmi_password"], "test-node-secret")
        self.assertEqual(preserve_ipmi({"ipmi_password": MASK}, {})["ipmi_password"], "")
        self.assertEqual(
            preserve_ipmi({"ipmiPassword": "attempt"}, self.device.attributes, False)["ipmi_password"],
            "test-device-secret",
        )

    async def test_unlock_requires_password_and_returns_only_requested_node(self):
        wrong = await self.client.post("/device/ipmi-unlock", json={"device_id": self.device.id, "password": "wrong"})
        self.assertEqual(wrong.status_code, 400)
        response = await self.client.post(
            "/device/ipmi-unlock",
            json={"device_id": self.device.id, "node_name": "N1", "password": "test-login-password"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"], {"ipmi_password": "test-node-secret", "expires_in": 60})
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertNotIn("test-device-secret", response.text)
        self.assertEqual((await assets.device_to_dict(self.device, True))["attributes"]["ipmi_password"], MASK)

    async def test_rate_limit_survives_requests_and_covers_all_devices(self):
        with patch("app.services.device_secrets.verify_password", return_value=False):
            for _ in range(5):
                response = await self.client.post(
                    "/device/ipmi-unlock", json={"device_id": self.device.id, "password": "wrong"}
                )
                self.assertEqual(response.status_code, 400)
            response = await self.client.post(
                "/device/ipmi-unlock", json={"device_id": self.device.id + 1, "password": "wrong"}
            )
            self.assertEqual(response.status_code, 429)

    async def test_api_permission_login_and_secret_permission(self):
        payload = {"device_id": self.device.id, "password": "test-login-password"}
        with patch.object(assets, "can_view_device_secrets", AsyncMock(return_value=False)):
            self.assertEqual((await self.client.post("/device/ipmi-unlock", json=payload)).status_code, 403)
        self.user.is_superuser = False
        self.assertEqual((await self.client.post("/device/ipmi-unlock", json=payload)).status_code, 403)
        self.app.dependency_overrides.clear()
        self.assertEqual((await self.client.post("/device/ipmi-unlock", json=payload)).status_code, 401)

    async def test_missing_login_password_is_not_bypassed(self):
        await User.filter(id=self.user.id).update(password=None)
        response = await self.client.post(
            "/device/ipmi-unlock", json={"device_id": self.device.id, "password": "anything"}
        )
        self.assertEqual(response.status_code, 400)

    async def test_redfish_reuses_saved_secret_only_for_same_address_and_user(self):
        payload = AssetDeviceRedfishProbe(
            device_id=self.device.id, ipmi_host="192.0.2.1", ipmi_user="ADMIN", ipmi_password=MASK
        )
        with patch.object(assets, "collect_redfish_inventory", AsyncMock(return_value={"CPU型号": "test"})) as collect:
            result = await assets.redfish_probe_device(payload)
            self.assertNotIn("test-device-secret", result.body.decode())
            self.assertEqual(collect.call_args.args[0].ipmi_password, "test-device-secret")
            payload.ipmi_host = "192.0.2.2"
            from fastapi import HTTPException

            with self.assertRaises(HTTPException):
                await assets.redfish_probe_device(payload)
            self.assertEqual(collect.await_count, 1)

    async def test_audit_does_not_record_credentials_and_masks_legacy_aliases(self):
        middleware = HttpAuditLogMiddleware(self.app, methods=["POST"], exclude_paths=[])
        request = Request(
            {
                "type": "http",
                "method": "POST",
                "path": "/api/v1/asset/device/ipmi-unlock",
                "headers": [],
                "query_string": b"",
            }
        )
        self.assertEqual(await middleware.get_request_args(request), {})
        self.assertIsNone(await middleware.get_response_body(request, Success(data={"ipmi_password": "secret"})))
        old = {"request_args": {"attributes": {"IPMI密码": "secret", "nodes": [{"ipmiPassword": "secret"}]}}}
        old["attributeList"] = [{"key": "IPMI密码", "value": "secret"}]
        self.assertNotIn("secret", json.dumps(mask_ipmi(old)))


if __name__ == "__main__":
    unittest.main()
