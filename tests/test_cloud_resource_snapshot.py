import asyncio
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

from tortoise import Tortoise

from app.models.asset import CloudResourceSnapshot
from app.services import cloud_resource_snapshot as service


class SnapshotTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        await Tortoise.init(db_url="sqlite://:memory:", modules={"models": ["app.models"]}, use_tz=True)
        await Tortoise.generate_schemas()

    async def asyncTearDown(self):
        await service.stop_snapshot_tasks()
        await Tortoise.close_connections()

    async def test_cold_reads_share_background_refresh_and_warm_reads_do_not_fetch(self):
        started, release = asyncio.Event(), asyncio.Event()

        async def collect(previous):
            started.set()
            await release.wait()
            return {"nodes": [], "items": [{"vmid": 100}]}, ""

        with patch.object(service, "collect_snapshot", AsyncMock(side_effect=collect)) as fetch:
            payload, sync = await service.read_snapshot()
            self.assertEqual(payload, {})
            self.assertTrue(sync["refreshing"])
            await started.wait()
            await service.read_snapshot()
            await service.read_snapshot(force=True)
            self.assertEqual(fetch.await_count, 1)
            release.set()
            await asyncio.gather(*list(service._tasks))
            payload, sync = await service.read_snapshot()
            self.assertEqual(payload["items"][0]["vmid"], 100)
            self.assertFalse(sync["stale"])
            self.assertEqual(fetch.await_count, 1)

    async def test_failure_retains_snapshot_and_success_time(self):
        timestamp = datetime.now(timezone.utc) - timedelta(hours=1)
        await CloudResourceSnapshot.create(key="fleet", payload={"items": [1]}, synced_at=timestamp)
        with (
            patch.object(service, "collect_snapshot", AsyncMock(side_effect=RuntimeError("offline"))),
            patch.object(service.logger, "exception"),
        ):
            payload, _ = await service.read_snapshot()
            self.assertEqual(payload["items"], [1])
            await asyncio.gather(*list(service._tasks))
        row = await CloudResourceSnapshot.get(key="fleet")
        self.assertEqual(row.payload["items"], [1])
        self.assertEqual(row.synced_at, timestamp)
        self.assertTrue(row.error)
        self.assertIsNone(row.lease_until)

    async def test_failed_remote_preserved_successful_empty_remote_removed(self):
        from app.api.v1.pve import pve

        async def get(path, **kwargs):
            if "/bad/" in path:
                raise RuntimeError("offline")
            return []

        previous = {"items": [{"remote": "bad", "vmid": 1}, {"remote": "good", "vmid": 2}]}
        with (
            patch.object(pve, "pdm_remote_list", AsyncMock(return_value=["bad", "good"])),
            patch.object(pve, "pve_node_binding_map", AsyncMock(return_value={})),
            patch.object(pve, "pdm_remote_config_detail_map", AsyncMock(return_value={})),
            patch.object(pve, "pdm_live_resources_list", AsyncMock(side_effect=RuntimeError("unavailable"))),
            patch.object(pve, "pdm_get", AsyncMock(side_effect=get)),
            patch.object(pve, "sync_vm_spec_metadata_from_list", AsyncMock()),
            patch.object(pve, "apply_vm_metadata", AsyncMock()),
        ):
            payload, error = await service.collect_snapshot(previous)
        self.assertEqual(payload["items"], [{"remote": "bad", "vmid": 1}])
        self.assertIn("bad", error)

    async def test_completed_operation_requests_refresh(self):
        from app.api.v1.pve import pve

        with (
            patch.object(pve, "pdm_task_request", AsyncMock(return_value={"status": "stopped", "exitstatus": "OK"})),
            patch.object(service, "read_snapshot", AsyncMock()) as read,
        ):
            await service.after_resource_change("remote", "UPID:test")
            await asyncio.gather(*list(service._tasks))
            read.assert_awaited_once_with(force=True)

    async def test_list_apis_use_database_without_cloud_calls(self):
        from app.api.v1.pve import pve
        import json

        await CloudResourceSnapshot.create(
            key="fleet", dirty=False, synced_at=datetime.now(timezone.utc),
            payload={"nodes": [{"remote": "a"}], "items": [
                {"remote": "a", "vmid": 1, "status": "running"},
                {"remote": "b", "vmid": 2, "status": "stopped"},
            ]},
        )
        with patch.object(pve, "pdm_get", AsyncMock()) as cloud, patch.object(pve, "apply_vm_metadata", AsyncMock()):
            nodes = await pve.list_nodes(refresh=False)
            vms = await pve.list_vms(node="a", refresh=False)
            self.assertEqual(json.loads(nodes.body)["data"], [{"remote": "a"}])
            data = json.loads(vms.body)["data"]
            self.assertEqual(data["summary"], {"total": 1, "running": 1, "stopped": 0})
            self.assertFalse(data["sync"]["refreshing"])
            cloud.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
