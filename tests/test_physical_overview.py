import json
import unittest

from tortoise import Tortoise
from tortoise.expressions import Q

from app.api.v1.assets.assets import physical_device_overview, validate_node_customer_mapping
from app.schemas.assets import AssetDeviceCreate, AssetDeviceUpdate
from app.models.asset import AssetCabinet, AssetDevice, AssetLocation, AssetRegion
from app.models.customer_center import CrmCustomer


class PhysicalOverviewTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        await Tortoise.init(db_url="sqlite://:memory:", modules={"models": ["app.models"]})
        await Tortoise.generate_schemas()
        region = await AssetRegion.create(name="Region", code="R1")
        location = await AssetLocation.create(name="DC", region=region)
        cabinet = await AssetCabinet.create(name="Rack", location=location)
        self.base = {"region": region, "location": location, "cabinet": cabinet}
        self.a = await CrmCustomer.create(name="A")
        self.b = await CrmCustomer.create(name="B")

    async def asyncTearDown(self):
        await Tortoise.close_connections()

    async def test_customers_configs_and_secret_exclusion(self):
        await AssetDevice.create(**self.base, name="Shared", asset_no="S1", customer=self.a,
                                 customer_ids=[self.a.id, self.b.id, self.b.id],
                                 attributes={"cpu_model": "Xeon", "memory": "128GB", "disk": "2xSSD",
                                             "ipmi_password": "do-not-expose"})
        await AssetDevice.create(**self.base, name="Unassigned", asset_no="S2")
        await AssetDevice.create(**self.base, name="Removed", asset_no="S3", customer=self.a, status=4)
        await AssetDevice.create(**self.base, name="Switch", asset_no="S4", customer=self.a, type=1)
        rows = await physical_device_overview(Q())
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["customer_ids"], [self.a.id, self.b.id])
        self.assertEqual(rows[0]["customer_names"], ["A", "B"])
        self.assertEqual(rows[0]["configurations"][0]["memory"], "128GB")
        self.assertEqual(rows[0]["region_name"], "Region")
        self.assertNotIn("do-not-expose", json.dumps(rows))
        self.assertNotIn("attributes", rows[0])
        self.assertEqual(await physical_device_overview(Q(name="missing")), [])

    async def test_four_node_configuration_is_preserved(self):
        await AssetDevice.create(**self.base, name="Four node", asset_no="F1", customer=self.a,
                                 attributes={"form_factor": "four_node", "nodes": [
                                     {"name": "N1", "cpu_count": 2, "cpu_model": "Xeon", "memory": "64GB"},
                                     {"name": "N2", "cpu_cores": 16, "disk": "1TB", "ipmi_password": "secret"},
                                 ]})
        rows = await physical_device_overview(Q())
        configs = rows[0]["configurations"]
        self.assertEqual([item["name"] for item in configs], ["N1", "N2"])
        self.assertEqual(configs[0]["cpu_count"], "2")
        self.assertEqual(configs[1]["disk"], "1TB")
        self.assertNotIn("secret", json.dumps(rows))

    async def test_node_customer_mapping_validation_and_legacy_update(self):
        attributes = {"form_factor": "four_node", "nodes": [
            {"name": "N1", "customer_id": self.a.id},
            {"name": "N2", "customer_id": self.b.id},
            {"name": "N3", "customer_id": None},
        ]}
        device = await AssetDevice.create(**self.base, name="Mapped", asset_no="M1", customer=self.a,
                                          customer_ids=[self.a.id, self.b.id], attributes=attributes)
        row = (await physical_device_overview(Q()))[0]
        self.assertEqual(row["form_factor"], "four_node")
        self.assertEqual([node["customer_id"] for node in row["configurations"]], [self.a.id, self.b.id, None])
        common = dict(cabinet_id=device.cabinet_id, asset_no="M1", name="Mapped", customer_ids=[self.a.id, self.b.id])
        legacy = AssetDeviceUpdate(id=device.id, **common, attributes={"form_factor": "four_node", "nodes": [{"name": "N1"}]})
        self.assertEqual(await validate_node_customer_mapping(legacy), "")
        self.assertEqual(legacy.attributes["nodes"][0]["customer_id"], self.a.id)
        cleared = AssetDeviceUpdate(id=device.id, **common, attributes={"form_factor": "four_node", "nodes": [{"name": "N1", "customer_id": None}]})
        self.assertEqual(await validate_node_customer_mapping(cleared), "")
        self.assertIsNone(cleared.attributes["nodes"][0]["customer_id"])
        invalid = AssetDeviceCreate(**common, attributes={"form_factor": "four_node", "nodes": [{"name": "N1", "customer_id": 99999}]})
        self.assertTrue(await validate_node_customer_mapping(invalid))


if __name__ == "__main__":
    unittest.main()
