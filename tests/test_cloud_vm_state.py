import json
import unittest
from unittest.mock import AsyncMock, patch

from tortoise import Tortoise

from app.api.v1.pve import pve
from app.models.asset import CloudResourceSnapshot
from app.services import cloud_vm_state as service
from app.services.cloud_resource_snapshot import stop_snapshot_tasks


class VmStateTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        await Tortoise.init(db_url="sqlite://:memory:", modules={"models": ["app.models"]}, use_tz=True)
        await Tortoise.generate_schemas()
        self.original = {
            "items": [
                {"remote": "a", "vmid": 1, "type": "pve-qemu", "status": "running", "ips": ["192.0.2.1"]},
                {"remote": "b", "vmid": 1, "status": "running"},
            ]
        }
        await CloudResourceSnapshot.create(key="fleet", payload=self.original, dirty=False)

    async def asyncTearDown(self):
        await stop_snapshot_tasks()
        await Tortoise.close_connections()

    async def test_targeted_status_preserves_other_guests_and_metadata(self):
        with patch.object(pve, "pdm_get", AsyncMock(return_value={"status": "stopped"})) as cloud:
            vm = await service.refresh_vm_state("a", 1)
            cloud.assert_awaited_once_with("/pve/remotes/a/qemu/1/status", timeout=5)
        self.assertEqual(vm["status"], "stopped")
        self.assertEqual(vm["uptime"], 0)
        self.assertEqual(vm["ips"], ["192.0.2.1"])
        row = await CloudResourceSnapshot.get(key="fleet")
        self.assertFalse(row.dirty)
        self.assertEqual(row.payload["items"][1], self.original["items"][1])

    async def test_concurrent_delete_is_not_resurrected(self):
        async def status(*args, **kwargs):
            await CloudResourceSnapshot.filter(key="fleet").update(payload={"items": []})
            return {"status": "stopped"}

        with patch.object(pve, "pdm_get", AsyncMock(side_effect=status)):
            with self.assertRaises(LookupError):
                await service.refresh_vm_state("a", 1)
        self.assertEqual((await CloudResourceSnapshot.get(key="fleet")).payload["items"], [])

    async def test_live_endpoint_does_not_trigger_fleet_refresh(self):
        with (
            patch.object(pve, "read_snapshot", AsyncMock()) as fleet,
            patch.object(pve, "pdm_get", AsyncMock(return_value={"status": "stopped"})),
        ):
            response = await pve.list_vms(node="a", vmid=1, refresh=False)
            self.assertEqual(json.loads(response.body)["data"]["items"][0]["status"], "stopped")
            fleet.assert_not_awaited()
            self.assertEqual((await pve.list_vms(node="a", vmid=99)).status_code, 404)
            self.assertEqual((await pve.list_vms(node="", vmid=1)).status_code, 422)
        with patch.object(pve, "pdm_get", AsyncMock(side_effect=RuntimeError("offline"))):
            self.assertEqual((await pve.list_vms(node="a", vmid=1)).status_code, 502)

    async def test_power_submission_schedules_only_targeted_followup(self):
        with (
            patch.object(pve, "pdm_post", AsyncMock(return_value="UPID:test")),
            patch.object(pve, "after_resource_change", AsyncMock()) as fleet,
            patch.object(service, "after_vm_power", AsyncMock()) as targeted,
        ):
            response = await pve.submit_vm_power(pve.VMPowerRequest(remote="a", vmid=1, action="stop"))
            self.assertEqual(response.status_code, 200)
            targeted.assert_awaited_once_with("a", 1, "UPID:test")
            fleet.assert_not_awaited()

    async def test_live_list_specs_win_over_local_metadata(self):
        async def get(path, **kwargs):
            if path.endswith("/lxc"):
                return []
            return [
                {
                    "vmid": 1,
                    "status": "running",
                    "cpus": 4,
                    "cpu": 0.25,
                    "maxmem": 800,
                    "mem": 200,
                    "maxdisk": 1000,
                    "disk": 300,
                    "uptime": 60,
                }
            ]

        async def metadata(items):
            for vm in items:
                vm.update(maxcpu=99, maxmem=9999, maxdisk=9999, customer_name="customer")

        with (
            patch.object(pve, "pdm_get", AsyncMock(side_effect=get)) as cloud,
            patch.object(pve, "apply_vm_metadata", AsyncMock(side_effect=metadata)),
            patch.object(pve, "read_snapshot", AsyncMock()) as fleet,
        ):
            response = await pve.list_vms(node="a", live=True)
            vm = json.loads(response.body)["data"]["items"][0]
            self.assertEqual((vm["maxcpu"], vm["maxmem"], vm["maxdisk"]), (4, 800, 1000))
            self.assertEqual(vm["cpu"], 25)
            self.assertEqual(vm["customer_name"], "customer")
            self.assertEqual(vm["ips"], ["192.0.2.1"])
            self.assertEqual(cloud.await_count, 2)
            fleet.assert_not_awaited()
        stored = await CloudResourceSnapshot.get(key="fleet")
        self.assertIn(self.original["items"][1], stored.payload["items"])
        self.assertFalse(stored.dirty)

    async def test_live_list_failure_preserves_inventory(self):
        async def get(path, **kwargs):
            if path.endswith("/lxc"):
                raise RuntimeError("unavailable")
            return []

        with patch.object(pve, "pdm_get", AsyncMock(side_effect=get)):
            response = await pve.list_vms(node="a", live=True)
        self.assertEqual(response.status_code, 502)
        self.assertEqual((await CloudResourceSnapshot.get(key="fleet")).payload, self.original)

    async def test_live_list_does_not_resurrect_concurrently_deleted_vm(self):
        async def get(path, **kwargs):
            if path.endswith("/lxc"):
                return []
            await CloudResourceSnapshot.filter(key="fleet").update(
                payload={
                    "items": [self.original["items"][1]],
                    "pending_deletions": [{"remote": "a", "vmid": 1}],
                }
            )
            return [{"vmid": 1, "status": "running"}]

        with (
            patch.object(pve, "pdm_get", AsyncMock(side_effect=get)),
            patch.object(pve, "apply_vm_metadata", AsyncMock()),
        ):
            self.assertEqual(await service.live_vm_list("a"), [])
        self.assertEqual((await CloudResourceSnapshot.get(key="fleet")).payload["items"], [self.original["items"][1]])
