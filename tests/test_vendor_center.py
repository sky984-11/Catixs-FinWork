import base64
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from starlette.requests import Request
from tortoise import Tortoise

from app.api.v1 import v1_router
from app.controllers import vendor_attachments as files
from app.core.ctx import CTX_USER_ID
from app.core.dependency import AuthControl
from app.core.middlewares import HttpAuditLogMiddleware
from app.models.admin import Api, Menu, Role, User
from app.models.company import Company, VendorAttachment
from app.models.customer_center import CrmSigningEntity


class VendorCenterTests(unittest.IsolatedAsyncioTestCase):
    async def test_supplier_code_preview_and_legal_name(self):
        entity = await CrmSigningEntity.create(name="Catixs Ltd", code="CATIXS-LTD")
        response = await self.client.get("/vendor/next-code", params={"signing_entity_id": entity.id})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["data"]["code"], "VU0001")
        self.assertEqual(await Company.filter(role=2).count(), 0)
        vendor = (await self.create_vendor(signing_entity_id=entity.id, legal_name="Example Networks Limited")).json()[
            "data"
        ]
        self.assertEqual(vendor["legal_name"], "Example Networks Limited")
        self.assertEqual(vendor["code"], "VU0001")
        response = await self.client.get("/vendor/next-code", params={"signing_entity_id": entity.id})
        self.assertEqual(response.json()["data"]["code"], "VU0002")
        response = await self.client.post("/vendor/update", json={"id": vendor["id"], "name": "Renamed"})
        self.assertEqual(response.json()["data"]["legal_name"], "Example Networks Limited")
        self.assertEqual((await self.create_vendor(legal_name="x" * 201)).status_code, 422)
        entity.status = False
        await entity.save()
        self.assertEqual(
            (await self.client.get("/vendor/next-code", params={"signing_entity_id": entity.id})).status_code, 400
        )
        self.assertEqual(
            (await self.client.get("/vendor/next-code", params={"signing_entity_id": 999999})).status_code, 400
        )
        self.user.is_superuser = False
        self.assertEqual(
            (await self.client.get("/vendor/next-code", params={"signing_entity_id": entity.id})).status_code, 403
        )

    async def test_shared_signing_entity_uses_crm_ids_and_preserves_legacy_link(self):
        entity = await CrmSigningEntity.create(id=901, name="Catixs Ltd", code="CATIXS-LTD")
        response = await self.create_vendor(signing_entity_id=entity.id)
        self.assertEqual(response.status_code, 200, response.text)
        vendor = response.json()["data"]
        self.assertEqual(vendor["signing_entity_id"], 901)
        self.assertEqual(vendor["signing_entity_name"], "Catixs Ltd")
        self.assertEqual(vendor["contract_company_id"], self.entity.id)
        self.assertEqual(vendor["code"], "VU0001")
        self.assertEqual((await Company.get(id=vendor["id"])).signing_entity_id, 901)
        invalid = await self.create_vendor(signing_entity_id=self.entity.id)
        self.assertEqual(invalid.status_code, 400)
        options = await self.client.get("/customer-center/signing-entities")
        self.assertEqual([item["id"] for item in options.json()["data"]], [901])

    async def test_existing_vendor_resolves_unique_crm_identity_without_rewriting_ids(self):
        entity = await CrmSigningEntity.create(id=902, name="Catixs Ltd", code="CATIXS-LTD")
        vendor = (await self.create_vendor()).json()["data"]
        self.assertEqual(vendor["signing_entity_id"], entity.id)
        self.assertEqual(vendor["contract_company_id"], self.entity.id)
        self.assertIsNone((await Company.get(id=vendor["id"])).signing_entity_id)
        rows = (await self.client.get("/vendor/list")).json()["data"]
        self.assertEqual(rows[0]["signing_entity_name"], "Catixs Ltd")

    async def test_new_crm_entity_and_changing_entity_clear_stale_legacy_link(self):
        first = await CrmSigningEntity.create(name="Catixs Ltd", code="CATIXS-LTD")
        second = await CrmSigningEntity.create(name="New Entity", code="NEW")
        vendor = (await self.create_vendor(signing_entity_id=first.id)).json()["data"]
        response = await self.client.post(
            "/vendor/update", json={"id": vendor["id"], "name": vendor["name"], "signing_entity_id": second.id}
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["data"]["signing_entity_id"], second.id)
        self.assertIsNone(response.json()["data"]["contract_company_id"])
        response = await self.client.post(
            "/vendor/update", json={"id": vendor["id"], "name": vendor["name"], "signing_entity_id": None}
        )
        self.assertIsNone(response.json()["data"]["signing_entity_id"])

    async def test_disabled_and_missing_crm_entities_rejected(self):
        entity = await CrmSigningEntity.create(name="Disabled", code="DISABLED", status=False)
        self.assertEqual((await self.create_vendor(signing_entity_id=entity.id)).status_code, 400)
        self.assertEqual((await self.create_vendor(signing_entity_id=999999)).status_code, 400)

    async def test_ambiguous_legacy_identity_is_not_silently_reassigned(self):
        self.entity.registration_no = "SHARED-REG"
        await self.entity.save()
        await CrmSigningEntity.create(name="First", code="FIRST", registration_no="SHARED-REG")
        await CrmSigningEntity.create(name="Second", code="SECOND", registration_no="SHARED-REG")
        vendor = (await self.create_vendor()).json()["data"]
        self.assertIsNone(vendor["signing_entity_id"])
        self.assertTrue(vendor["legacy_signing_entity_unmatched"])
        self.assertEqual(vendor["contract_company_id"], self.entity.id)

    async def test_csv_resolves_customer_management_entity_and_exports_shared_name(self):
        entity = await CrmSigningEntity.create(id=903, name="77 Telecom Ltd", code="77-TELECOM-LTD")
        content = "名称,签约主体\nShared Entity Vendor,77 Telecom Ltd\n"
        response = await self.client.post("/vendor/import", files={"file": ("test.csv", content.encode(), "text/csv")})
        self.assertEqual(response.status_code, 200, response.text)
        vendor = await Company.get(name="Shared Entity Vendor")
        self.assertEqual(vendor.signing_entity_id, entity.id)
        self.assertEqual(vendor.code, "VH0001")
        self.assertIn("77 Telecom Ltd", (await self.client.get("/vendor/export")).text)

    async def test_vendor_menus_are_visible_unique_and_repeatable(self):
        from app.core.init_app import ensure_vendor_center_menu

        legacy = await Menu.create(name="客户/供应商", path="/vendor", component="/company", parent_id=99)
        await ensure_vendor_center_menu()
        catalog = await Menu.get(path="/vendor-center")
        extra = await Menu.create(
            name="供应商合同", path="contracts", component="/vendor-center/contracts", parent_id=catalog.id
        )
        await ensure_vendor_center_menu()
        await legacy.refresh_from_db()
        await extra.refresh_from_db()
        children = await Menu.filter(parent_id=catalog.id, is_hidden=False).order_by("order")
        self.assertEqual(catalog.parent_id, 0)
        self.assertFalse(catalog.is_hidden)
        self.assertEqual([item.name for item in children], ["供应商管理", "供应商联系人"])
        self.assertEqual([item.component for item in children], ["/vendor-center/vendors", "/vendor-center/contacts"])
        self.assertTrue(legacy.is_hidden)
        self.assertEqual(legacy.redirect, "/vendor-center/vendors")
        self.assertNotIn(legacy.name, [item.name for item in children])
        self.assertTrue(extra.is_hidden)
        self.assertEqual(await Menu.filter(path="/vendor-center").count(), 1)

    async def test_vendor_menu_role_permissions(self):
        from app.core.init_app import ensure_vendor_center_menu, ensure_vendor_center_permissions

        reader = await Role.create(name="vendor-reader")
        manager = await Role.create(name="noc")
        read_api = await Api.create(path="/api/v1/vendor/list", method="GET", summary="Test", tags="Test")
        region_api = await Api.create(path="/api/v1/asset/region/list", method="GET", summary="Test", tags="Test")
        write_api = await Api.create(path="/api/v1/vendor/update", method="POST", summary="Test", tags="Test")
        unrelated = await Api.create(path="/api/v1/unrelated/write", method="POST", summary="Test", tags="Test")
        await ensure_vendor_center_menu()
        await ensure_vendor_center_permissions()
        await ensure_vendor_center_permissions()
        self.assertEqual(await reader.menus.all().count(), 3)
        self.assertTrue(await reader.apis.filter(id=read_api.id).exists())
        self.assertTrue(await reader.apis.filter(id=region_api.id).exists())
        self.assertFalse(await reader.apis.filter(id=write_api.id).exists())
        self.assertTrue(await manager.apis.filter(id=write_api.id).exists())
        self.assertFalse(await manager.apis.filter(id=unrelated.id).exists())
        self.user.is_superuser = False
        await self.user.save(update_fields=["is_superuser"])
        await self.user.roles.add(reader)
        response = await self.client.get("/base/usermenu")
        self.assertEqual(response.status_code, 200)
        catalog = next(item for item in response.json()["data"] if item["path"] == "/vendor-center")
        self.assertFalse(catalog["is_hidden"])
        self.assertEqual({item["name"] for item in catalog["children"]}, {"供应商管理", "供应商联系人"})

    async def test_contact_page_updates_and_deletes_only_selected_role(self):
        vendor = (
            await self.create_vendor(
                sales_contact="Sales",
                billing_contact="Billing",
                noc_contact="NOC",
                noc_email="noc@example.test",
                payment_terms="30/30",
            )
        ).json()["data"]
        response = await self.client.post(
            "/vendor/update", json={"id": vendor["id"], "name": vendor["name"], "sales_contact": "New sales"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["billing_contact"], "Billing")
        self.assertEqual(response.json()["data"]["payment_terms"], "30/30")
        response = await self.client.post(
            "/vendor/update",
            json={"id": vendor["id"], "name": vendor["name"], "noc_contact": "", "noc_email": "", "noc_phone": ""},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["noc_email"], "")
        self.assertEqual(response.json()["data"]["sales_contact"], "New sales")

    async def asyncSetUp(self):
        await Tortoise.init(db_url="sqlite://:memory:", modules={"models": ["app.models"]})
        await Tortoise.generate_schemas()
        self.user = await User.create(username="vendor-test", email="vendor@example.test", is_superuser=True)
        self.entity = await Company.create(name="Catixs Ltd (UK)", role=0, code="U")
        self.app = FastAPI()
        self.app.include_router(v1_router, prefix="/api/v1")

        async def authed():
            CTX_USER_ID.set(self.user.id)
            return self.user

        self.app.dependency_overrides[AuthControl.is_authed] = authed
        self.client = AsyncClient(transport=ASGITransport(app=self.app), base_url="http://test/api/v1")
        self.temp = tempfile.TemporaryDirectory()
        self.directory = patch.object(files, "ATTACHMENT_DIR", Path(self.temp.name))
        self.directory.start()

    async def asyncTearDown(self):
        await self.client.aclose()
        self.directory.stop()
        self.temp.cleanup()
        await Tortoise.close_connections()

    async def upload(self, data=None, **kwargs):
        return await self.client.post(
            "/vendor/attachments/upload",
            json={
                "filename": "../test.pdf",
                "content_type": "application/pdf",
                "data": data if data is not None else base64.b64encode(b"synthetic attachment").decode(),
                **kwargs,
            },
        )

    async def create_vendor(self, **kwargs):
        return await self.client.post(
            "/vendor/create",
            json={
                "name": "Test vendor",
                "contract_company_id": self.entity.id,
                **kwargs,
            },
        )

    async def test_contacts_roundtrip_and_legacy_update(self):
        response = await self.create_vendor(
            payment_terms="1/30",
            tax_no="TAX-OLD",
            registration_no="REG-OLD",
            sales_contact="Sales\nsales@example.test",
            billing_contact="billing@example.test",
            noc_contact="24/7\n+1 555 0100",
            company_email="office@example.test",
            company_phone="+1 555 0101",
            noc_email="noc@example.test",
            noc_phone="+1 555 0102",
        )
        self.assertEqual(response.status_code, 200, response.text)
        vendor = response.json()["data"]
        self.assertEqual(vendor["code"], "VU0001")
        response = await self.client.post(
            "/vendor/update", json={"id": vendor["id"], "name": "Updated", "country": "中国 / 香港"}
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["data"]["payment_terms"], "1/30")
        self.assertEqual(response.json()["data"]["tax_no"], "TAX-OLD")
        self.assertEqual(response.json()["data"]["registration_no"], "REG-OLD")
        self.assertEqual(response.json()["data"]["country"], "中国 / 香港")
        self.assertEqual(response.json()["data"]["sales_contact"], "Sales\nsales@example.test")
        self.assertEqual(response.json()["data"]["company_email"], "office@example.test")
        self.assertEqual(response.json()["data"]["company_phone"], "+1 555 0101")
        self.assertEqual(response.json()["data"]["noc_email"], "noc@example.test")
        self.assertEqual(response.json()["data"]["noc_phone"], "+1 555 0102")

    async def test_startup_schema_upgrade_preserves_legacy_rows_and_is_repeatable(self):
        connection = Company._meta.db
        for name in ("payment_terms", "sales_contact", "billing_contact", "noc_contact", "signing_entity_id"):
            await connection.execute_script(f'ALTER TABLE "company" DROP COLUMN "{name}";')
        await files.ensure_vendor_columns()
        await files.ensure_vendor_columns()
        entity = await Company.get(id=self.entity.id)
        self.assertEqual(entity.name, self.entity.name)
        self.assertIsNone(entity.payment_terms)
        self.assertIsNone(entity.signing_entity_id)
        constraints = await connection.execute_query_dict('PRAGMA foreign_key_list("company")')
        self.assertTrue(
            any(item["from"] == "signing_entity_id" and item["table"] == "crm_signing_entity" for item in constraints)
        )

    async def test_identity_and_entity_validation(self):
        for kwargs in ({"name": "   "}, {"payment_terms": "x" * 201}, {"noc_contact": "x" * 10001}):
            self.assertEqual((await self.create_vendor(**kwargs)).status_code, 422)
        vendor = (await self.create_vendor(code="VU0009")).json()["data"]
        self.assertEqual((await self.create_vendor()).json()["data"]["code"], "VU0010")
        self.assertEqual((await self.create_vendor(code="VU0009")).status_code, 409)
        self.assertEqual((await self.create_vendor(contract_company_id=vendor["id"])).status_code, 400)
        response = await self.client.post("/vendor/update", json={"id": self.entity.id, "name": "Cannot change"})
        self.assertEqual(response.status_code, 404)
        response = await self.client.delete("/vendor/delete", params={"vendor_id": self.entity.id})
        self.assertEqual(response.status_code, 404)

    async def test_upload_bind_download_delete(self):
        for prefix in ("", "data:application/pdf;base64,"):
            response = await self.upload(prefix + base64.b64encode(b"synthetic").decode())
            self.assertEqual(response.status_code, 200, response.text)
            attachment = response.json()["data"]
            self.assertEqual(attachment["name"], "test.pdf")
            vendor = (await self.create_vendor(attachment_ids=[attachment["id"]])).json()["data"]
            row = await VendorAttachment.get(id=attachment["id"])
            self.assertEqual(row.vendor_id, vendor["id"])
            path = Path(self.temp.name) / row.stored_name
            self.assertEqual(path.read_bytes(), b"synthetic")
            response = await self.client.get("/vendor/attachments/download", params={"attachment_id": row.id})
            self.assertEqual(response.content, b"synthetic")
            response = await self.client.delete("/vendor/delete", params={"vendor_id": vendor["id"]})
            self.assertEqual(response.status_code, 409)
            response = await self.client.delete("/vendor/attachments/delete", params={"attachment_id": row.id})
            self.assertEqual(response.status_code, 200, response.text)
            self.assertFalse(path.exists())
            self.assertFalse(await VendorAttachment.filter(id=row.id).exists())
            self.assertEqual(list(Path(self.temp.name).iterdir()), [])

    async def test_unsaved_delete_and_failed_delete_retry(self):
        attachment = (await self.upload()).json()["data"]
        row = await VendorAttachment.get(id=attachment["id"])
        path = Path(self.temp.name) / row.stored_name
        with patch.object(Path, "unlink", side_effect=OSError("synthetic failure")):
            response = await self.client.delete("/vendor/attachments/delete", params={"attachment_id": row.id})
        self.assertEqual(response.status_code, 500, response.text)
        self.assertTrue(path.exists())
        self.assertTrue(await VendorAttachment.filter(id=row.id).exists())
        response = await self.client.delete("/vendor/attachments/delete", params={"attachment_id": row.id})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(path.exists())

    async def test_invalid_and_oversized_upload(self):
        for value in ("%%%", "data:text/plain,hello", "data:text/plain;base64,", "中文"):
            self.assertEqual((await self.upload(value)).status_code, 400)
        self.assertEqual((await self.upload("")).status_code, 422)
        self.assertEqual((await self.upload(filename=" ")).status_code, 400)
        with patch.object(files, "MAX_ATTACHMENT_SIZE", 3):
            self.assertEqual((await self.upload()).status_code, 413)
        with patch.object(files, "MAX_ENCODED_SIZE", 2):
            self.assertEqual((await self.upload()).status_code, 413)
        self.assertEqual(list(Path(self.temp.name).iterdir()), [])

    async def test_attachment_access_and_no_cross_vendor_binding(self):
        attachment = (await self.upload()).json()["data"]
        original_user = self.user
        self.user = await User.create(username="other-vendor-user", email="other@example.test", is_superuser=True)
        for method, route in (("get", "download"), ("delete", "delete")):
            response = await getattr(self.client, method)(
                f"/vendor/attachments/{route}", params={"attachment_id": attachment["id"]}
            )
            self.assertEqual(response.status_code, 403)
        self.assertEqual((await self.create_vendor(attachment_ids=[attachment["id"]])).status_code, 403)
        self.assertEqual(await Company.filter(role=2).count(), 0)
        self.user = original_user
        vendor = (await self.create_vendor(attachment_ids=[attachment["id"]])).json()["data"]
        self.assertEqual((await self.create_vendor(attachment_ids=[attachment["id"]])).status_code, 403)
        self.assertEqual((await VendorAttachment.get(id=attachment["id"])).vendor_id, vendor["id"])

    async def test_auth_and_permissions(self):
        self.user.is_superuser = False
        for path in ("/vendor/list", "/vendor/attachments/download?attachment_id=1"):
            self.assertEqual((await self.client.get(path)).status_code, 403)
        self.assertEqual((await self.upload()).status_code, 403)
        self.assertEqual((await self.client.delete("/vendor/attachments/delete?attachment_id=1")).status_code, 403)
        self.app.dependency_overrides.clear()
        self.assertIn((await self.upload()).status_code, (401, 422))
        self.assertEqual((await self.client.get("/vendor/list", headers={"token": "invalid"})).status_code, 401)

    async def test_csv_legacy_and_screenshot_headers(self):
        for content in (
            "名称,编号\nLegacy,VU0020\n",
            "Vendor Name,Vendor ID,Catixs Entity,Payment Terms,Sales Contact\nScreenshot,VU0021,Catixs Ltd (UK),30/30,sales@example.test\n",
        ):
            response = await self.client.post(
                "/vendor/import", files={"file": ("test.csv", content.encode(), "text/csv")}
            )
            self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(await Company.filter(role=2).count(), 2)
        self.assertEqual((await Company.get(code="VU0021")).payment_terms, "30/30")
        response = await self.client.get("/vendor/export")
        self.assertIn("付款条件", response.text)
        self.assertIn("sales@example.test", response.text)

    async def test_upload_body_not_audited_or_echoed(self):
        middleware = HttpAuditLogMiddleware(self.app, methods=["POST"], exclude_paths=[])
        request = Request(
            {
                "type": "http",
                "method": "POST",
                "path": "/api/v1/vendor/attachments/upload",
                "headers": [],
                "query_string": b"",
            }
        )
        self.assertEqual(await middleware.get_request_args(request), {})
        response = await self.client.post(
            "/vendor/attachments/upload", json={"filename": "a.pdf", "data": ["sensitive synthetic content"]}
        )
        self.assertEqual(response.status_code, 422)
        self.assertNotIn("sensitive synthetic content", response.text)


if __name__ == "__main__":
    unittest.main()
