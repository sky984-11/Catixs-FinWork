import importlib
import unittest

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from tortoise import Tortoise

from app.api.v1 import v1_router
from app.core.dependency import AuthControl
from app.core.init_app import ensure_business_api_permissions, ensure_product_center_menu
from app.models.admin import Api, Menu, Role, User
from app.models.company import Company
from app.models.product_center import ProductItem, ProductPriceVersion
from app.models.resource_cost import ProductCostLink, ResourceCost, ResourceCostVersion


class ResourceCostTests(unittest.IsolatedAsyncioTestCase):
    async def test_xc_csv_currency_symbols_and_unquoted_costs(self):
        import csv
        import tempfile
        from pathlib import Path

        from app.schemas.resource_cost import CostPayload
        from scripts.import_resource_costs_csv import parse_rows, prepare_incomplete

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "xc.csv"
            with path.open("w", encoding="utf-8", newline="") as file:
                writer = csv.writer(file)
                writer.writerow(["Note: cost only"])
                writer.writerow(["DC Name", "Site Address", "Currency", "Tax Rate", "NRC", "MRC ", "Remarks", ""])
                writer.writerow(["Test DC", "Address", "USD", "0", "$198", "$265", "Note", "extra"])
                writer.writerow(["Unquoted DC", "Address", "", "", "", "", "", ""])
            rows = list(parse_rows(path, "xc"))
        self.assertEqual(len(rows), 2)
        model = CostPayload.model_validate(prepare_incomplete(rows[0][2], None))
        self.assertTrue(model.enabled)
        self.assertEqual(str(model.nrc), "198")
        self.assertEqual(str(model.mrc), "265")
        self.assertIn("extra", model.note)
        unquoted = CostPayload.model_validate(prepare_incomplete(rows[1][2], None))
        self.assertIsNone(unquoted.nrc)
        self.assertIsNone(unquoted.mrc)
        self.assertIsNone(unquoted.currency)

    async def test_retail_csv_fields_and_optional_site_b(self):
        import csv
        import tempfile
        from pathlib import Path

        from app.schemas.resource_cost import CostPayload
        from scripts.import_resource_costs_csv import HEADERS, parse_rows, prepare_incomplete

        headers = list(HEADERS) + ["Burst", "Site B", "USD/Mbps MRC"]
        source = {
            "Service": "DIA",
            "Site A": "Test building",
            "Currency": "USD",
            "Burst": "100M",
            "NRC": "0",
            "MRC": "570",
            "USD/Mbps MRC": "28.5",
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "retail.csv"
            with path.open("w", encoding="utf-8", newline="") as file:
                writer = csv.writer(file)
                writer.writerow(headers)
                writer.writerow([source.get(key, "") for key in headers])
            rows = list(parse_rows(path, "retail"))
        self.assertEqual(len(rows), 1)
        _, vendor, data = rows[0]
        model = CostPayload.model_validate(prepare_incomplete(data, vendor))
        self.assertTrue(model.enabled)
        self.assertEqual(model.burst, "100M")
        self.assertIsNone(model.site_b)
        self.assertEqual(str(model.price_per_mbps), "28.5")
        self.assertEqual(str(model.nrc), "0")

    async def test_ptp_csv_preamble_and_nonstandard_fields(self):
        import csv
        import tempfile
        from pathlib import Path

        from app.schemas.resource_cost import CostPayload
        from scripts.import_resource_costs_csv import HEADERS, parse_rows, prepare_incomplete

        headers = list(HEADERS) + ["Site B", "Price/Mbps MRC"]
        source = {
            "Service": "Wave",
            "Site A": "Test A",
            "Site B": "Test B",
            "Currency": "USD",
            "NRC": "100/port",
            "MRC": "1,500",
            "Protection": "Diverse",
            "Contract Terms": "NA",
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ptp.csv"
            with path.open("w", encoding="utf-8", newline="") as file:
                writer = csv.writer(file)
                writer.writerow(["Hints: example only"])
                writer.writerow([])
                writer.writerow(headers)
                writer.writerow([source.get(key, "") for key in headers])
            rows = list(parse_rows(path, "ptp"))
        self.assertEqual(len(rows), 1)
        number, vendor, data = rows[0]
        self.assertEqual(number, 4)
        model = CostPayload.model_validate(prepare_incomplete(data, vendor))
        self.assertFalse(model.enabled)
        self.assertEqual(str(model.mrc), "1500")
        self.assertEqual(model.site_b, "Test B")
        self.assertIn("100/port", model.note)
        self.assertIn("Diverse", model.note)
        self.assertIn("NA", model.note)

    async def test_incomplete_import_stays_disabled_and_retains_source_values(self):
        from app.schemas.resource_cost import CostPayload
        from scripts.import_resource_costs_csv import prepare_incomplete

        data = prepare_incomplete(
            {"category": "ipt_dia", "service": "DIA", "site_a": None, "currency": None, "mrc": "400-450"},
            "Example vendor",
        )
        self.assertFalse(data["enabled"])
        self.assertIsNone(data["mrc"])
        self.assertIn("400-450", data["note"])
        self.assertIn("Example vendor", data["note"])
        self.assertIsNone(CostPayload.model_validate(data).vendor_id)
        row = await self.post("", data)
        await self.post(f"/products/{self.product.id}/links", {"version_id": row["version_id"]}, 409)
        await self.post("", {**data, "enabled": True}, 422)
        complete = prepare_incomplete(
            {"category": "ipt_dia", "service": "DIA", "site_a": "Test DC", "currency": "USD", "mrc": "100"},
            "Example vendor",
        )
        self.assertTrue(CostPayload.model_validate(complete).enabled)

    async def asyncSetUp(self):
        await Tortoise.init(db_url="sqlite://:memory:", modules={"models": ["app.models"]})
        await Tortoise.generate_schemas()
        self.user = await User.create(username="cost-admin", email="cost@test.invalid", is_superuser=True)
        self.vendor = await Company.create(name="Test carrier", role=2)
        self.product = await ProductItem.create(name="XC", code="XC-TEST")
        self.app = FastAPI()
        self.app.include_router(v1_router, prefix="/api/v1")

        async def authed():
            return self.user

        self.app.dependency_overrides[AuthControl.is_authed] = authed
        self.client = AsyncClient(
            transport=ASGITransport(app=self.app), base_url="http://test/api/v1/resource-costs", follow_redirects=True
        )
        self.payload = {
            "category": "xc",
            "dc_name": "Test DC",
            "site_address": "Test address",
            "vendor_id": self.vendor.id,
            "currency": "USD",
            "nrc": "0",
            "mrc": None,
            "tax_rate": "0",
        }

    async def asyncTearDown(self):
        await self.client.aclose()
        await Tortoise.close_connections()

    async def post(self, path, payload, status=200):
        response = await self.client.post(path, json=payload)
        self.assertEqual(response.status_code, status, response.text)
        return response.json().get("data")

    async def test_five_categories_validation_and_filter(self):
        options = (await self.client.get("/options")).json()["data"]
        self.assertEqual(set(options["categories"]), {"xc", "ipt_dia", "ptp", "retail", "colo"})
        xc = await self.post("", self.payload)
        self.assertEqual(xc["nrc"], "0")
        self.assertIsNone(xc["mrc"])
        for category in ["ipt_dia", "ptp", "retail", "colo"]:
            payload = {
                "category": category,
                "service": "Test service",
                "site_a": "Site A",
                "currency": "GBP",
                "mrc": "701",
                "mrc_unit": "kVA",
            }
            if category in ["ptp", "retail"]:
                payload["site_b"] = "Site B"
            await self.post("", payload)
        result = (await self.client.get("", params={"category": "xc", "vendor_id": self.vendor.id})).json()
        self.assertEqual(result["total"], 1)
        for changes in [
            {"mrc": "-1"},
            {"tax_rate": "101"},
            {"nrc": "NaN"},
            {"nrc": "1", "currency": None},
            {"category": "misc"},
            {"site_b": "Unsupported"},
            {"expiry_date": "2026-01-01", "effective_date": "2026-01-02"},
        ]:
            await self.post("", {**self.payload, **changes}, 422)
        await self.post("", {**self.payload, "vendor_id": 99999}, 422)

    async def test_version_and_link_snapshot_preserves_sales_prices(self):
        first = await self.post("", {**self.payload, "mrc": "50"})
        await self.post(f"/products/{self.product.id}/links", {"version_id": first["version_id"]})
        response = await self.client.put(f"/{first['id']}", json={**self.payload, "mrc": "60", "expected_revision": 1})
        self.assertEqual(response.status_code, 200, response.text)
        second = response.json()["data"]
        stale = await self.client.put(f"/{first['id']}", json={**self.payload, "expected_revision": 1})
        self.assertEqual(stale.status_code, 409)
        linked = (await self.client.get(f"/products/{self.product.id}/links")).json()["data"][0]
        self.assertEqual(linked["mrc"], "50")
        self.assertEqual(linked["latest_revision"], 2)
        self.assertEqual(await ProductPriceVersion.all().count(), 0)
        await self.post(f"/products/{self.product.id}/links", {"version_id": first["version_id"]}, 409)
        await self.post(f"/products/{self.product.id}/links", {"version_id": second["version_id"]})
        self.assertEqual(await ProductCostLink.all().count(), 1)
        history = (await self.client.get(f"/{first['id']}/versions")).json()["data"]
        self.assertEqual([row["mrc"] for row in history], ["60", "50"])
        unrelated = await self.client.delete(f"/products/999/links/{linked['link_id']}")
        self.assertEqual(unrelated.status_code, 404)
        self.assertEqual(
            (await self.client.delete(f"/products/{self.product.id}/links/{linked['link_id']}")).status_code, 200
        )
        self.assertEqual(await ResourceCostVersion.all().count(), 2)

    async def test_disabled_and_expired_cost_cannot_be_linked(self):
        for extra in [{"enabled": False}, {"expiry_date": "2000-01-01"}, {"effective_date": "2999-01-01"}]:
            row = await self.post("", {**self.payload, **extra})
            await self.post(f"/products/{self.product.id}/links", {"version_id": row["version_id"]}, 409)

    async def test_import_preview_money_units_duplicates_and_atomic_commit(self):
        csv_text = "Service,Vendor,Site A,Currency,NRC,MRC\nColocation,Test carrier,LD8,USD,0,701/kVA\n"
        result = await self.post("/import/preview", {"category": "colo", "csv_text": csv_text})
        self.assertFalse(result["errors"])
        self.assertEqual(result["rows"][0]["mrc"], "701")
        self.assertEqual(result["rows"][0]["mrc_unit"], "kVA")
        self.assertEqual(await ResourceCost.all().count(), 0)
        await self.post("/import/commit", {"rows": result["rows"]})
        await self.post("/import/commit", {"rows": result["rows"]}, 409)
        self.assertEqual(await ResourceCost.all().count(), 1)
        duplicate = await self.post("/import/preview", {"category": "colo", "csv_text": csv_text})
        self.assertTrue(duplicate["errors"])
        # A later invalid row rolls back the preceding new row.
        await self.post(
            "/import/commit", {"rows": [{**self.payload, "code": "ROLLBACK"}, {**self.payload, "vendor_id": 999}]}, 422
        )
        self.assertFalse(await ResourceCost.filter(code="ROLLBACK").exists())
        bad = await self.post(
            "/import/preview", {"category": "xc", "csv_text": "DC Name,Vendor,Currency,NRC\nDC,Unknown,USD,0\n"}
        )
        self.assertEqual(bad["errors"][0]["row"], 2)
        await self.post("/import/preview", {"category": "xc", "csv_text": "Unknown column\nvalue\n"}, 422)
        blank = await self.post(
            "/import/preview", {"category": "xc", "csv_text": "DC Name,Currency,NRC,MRC\nDC,EUR,0,\n"}
        )
        self.assertIsNone(blank["rows"][0]["mrc"])
        euro = await self.post(
            "/import/preview", {"category": "xc", "csv_text": "DC Name,Currency,NRC,MRC\nDC,EUR,€50,€0\n"}
        )
        self.assertFalse(euro["errors"])
        self.assertEqual(euro["rows"][0]["mrc"], "0")

    async def test_permissions_menu_and_migration(self):
        self.user.is_superuser = False
        await self.user.save()
        self.assertEqual((await self.client.get("")).status_code, 403)
        await self.post("", self.payload, 403)
        self.app.dependency_overrides.clear()
        self.assertEqual((await self.client.get("")).status_code, 401)
        await ensure_product_center_menu()
        self.assertEqual(await Menu.filter(component="/product-center/resource-costs").count(), 1)
        api = await Api.create(path="/api/v1/resource-costs", method="GET", summary="Costs", tags="Costs")
        finance = await Role.create(name="finance")
        sales = await Role.create(name="sales")
        await ensure_business_api_permissions()
        self.assertTrue(await finance.apis.filter(id=api.id).exists())
        self.assertFalse(await sales.apis.filter(id=api.id).exists())
        self.assertFalse(await sales.menus.filter(component="/product-center/resource-costs").exists())
        migration = importlib.import_module("migrations.models.188_20261113120000_resource_costs")
        sql = await migration.upgrade(None)
        self.assertEqual(sql.count("CREATE TABLE"), 3)
        self.assertIn("ON DELETE RESTRICT", sql)
        self.assertNotIn("DROP TABLE", sql)
        self.assertIn('UNIQUE ("product_id", "resource_id")', sql)
