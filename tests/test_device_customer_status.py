import json
import unittest
from unittest.mock import AsyncMock, patch

from tortoise import Tortoise

from app.api.v1.assets import assets
from app.models.asset import AssetCabinet, AssetDevice, AssetLocation, AssetRegion
from app.models.customer_center import CrmCustomer
from app.schemas.assets import AssetDeviceCreate, AssetDeviceUpdate


class DeviceCustomerStatusTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        await Tortoise.init(db_url="sqlite://:memory:", modules={"models": ["app.models"]})
        await Tortoise.generate_schemas()
        region = await AssetRegion.create(name="Test", code="TEST")
        location = await AssetLocation.create(name="Test", region=region)
        self.cabinet = await AssetCabinet.create(name="Test", location=location)
        self.customer = await CrmCustomer.create(name="Test")
        self.patches = [
            patch.object(assets, "can_view_device_secrets", AsyncMock(return_value=True)),
            patch.object(assets, "sync_physical_server_specs", AsyncMock()),
        ]
        for mocked in self.patches:
            mocked.start()

    async def asyncTearDown(self):
        for mocked in self.patches:
            mocked.stop()
        await Tortoise.close_connections()

    async def create(self, **kwargs):
        payload = AssetDeviceCreate(cabinet_id=self.cabinet.id, name="Server", asset_no="S1", u_position=1, **kwargs)
        result = json.loads((await assets.create_device(payload)).body)
        self.assertEqual(result["code"], 200, result)
        return result["data"]

    async def update(self, device, **kwargs):
        payload = AssetDeviceUpdate(id=device["id"], cabinet_id=self.cabinet.id, name="Server", asset_no="S1", u_position=1, **kwargs)
        result = json.loads((await assets.update_device(payload)).body)
        self.assertEqual(result["code"], 200, result)
        return result["data"]

    async def test_reserved_then_assign_then_remove_customers(self):
        device = await self.create(status=6, customer_ids=[])
        self.assertEqual(device["status"], 6)
        device = await self.update(device, status=6, customer_ids=[self.customer.id])
        self.assertEqual(device["status"], 1)
        device = await self.update(device, status=2, customer_ids=[self.customer.id])
        self.assertEqual(device["status"], 2)
        device = await self.update(device, status=1, customer_ids=[])
        self.assertEqual(device["status"], 0)
        self.assertEqual(device["customer_ids"], [])
        self.assertIsNone((await AssetDevice.get(id=device["id"])).customer_id)

    async def test_four_node_removal_clears_mapping_and_status(self):
        attributes = {"form_factor": "four_node", "nodes": [{"name": "N1", "customer_id": self.customer.id, "status": 1}]}
        device = await self.create(customer_ids=[self.customer.id], attributes=attributes)
        device = await self.update(device, customer_ids=[], attributes=attributes)
        self.assertEqual(device["status"], 0)
        self.assertIsNone(device["attributes"]["nodes"][0]["customer_id"])
        self.assertEqual(device["attributes"]["nodes"][0]["status"], 0)

    async def test_reserved_nodes_are_not_free(self):
        device = await self.create(customer_ids=[], attributes={"form_factor": "four_node", "nodes": [{"name": "N1", "status": 6}]})
        self.assertEqual(device["status"], 6)

    async def test_legacy_customer_can_be_removed(self):
        device = await self.create(customer_ids=[])
        await AssetDevice.filter(id=device["id"]).update(customer_id=self.customer.id, status=1)
        device = await self.update(device, customer_ids=[], status=1)
        self.assertEqual(device["status"], 0)
        self.assertEqual(device["customer_ids"], [])

    async def test_assign_customer_to_reserved_four_node_device(self):
        attributes = {"form_factor": "four_node", "nodes": [{"name": "N1", "status": 6}]}
        device = await self.create(customer_ids=[], attributes=attributes)
        device = await self.update(device, customer_ids=[self.customer.id], attributes=attributes)
        self.assertEqual(device["status"], 1)
        self.assertEqual((await AssetDevice.get(id=device["id"])).status, 1)
