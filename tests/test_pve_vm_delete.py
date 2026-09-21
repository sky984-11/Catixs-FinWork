import json
import unittest
from unittest.mock import AsyncMock, patch

from app.api.v1.pve import pve


class VmDeleteTests(unittest.IsolatedAsyncioTestCase):
    async def run_delete(self, statuses=None, command_result=(0, "UPID:test", "")):
        request = pve.VMDeleteRequest(remote="a", vmid=1, status="stopped")
        with (
            patch.object(pve, "pdm_remote_config_host", AsyncMock(return_value="test-host")),
            patch.object(pve, "ssh_execute_pve", return_value=command_result),
            patch.object(pve, "pdm_task_request", AsyncMock(side_effect=statuses)) as status,
            patch.object(pve, "remove_snapshot_vm", AsyncMock()) as remove,
            patch.object(pve, "release_vm_dhcp_lease", AsyncMock()) as release,
            patch.object(pve.PveVmMetadata, "filter") as metadata,
            patch.object(pve, "after_resource_change", AsyncMock()) as refresh,
            patch.object(pve.asyncio, "sleep", AsyncMock()) as sleep,
        ):
            metadata.return_value.delete = AsyncMock()

            async def during_wait(_):
                remove.assert_not_awaited()
                release.assert_not_awaited()
                metadata.assert_not_called()

            sleep.side_effect = during_wait
            response = await pve.delete_vm(request)
            refresh.assert_not_awaited()
            if response.status_code != 200:
                remove.assert_not_awaited()
                release.assert_not_awaited()
                metadata.assert_not_called()
            else:
                remove.assert_awaited_once_with("a", 1)
                release.assert_awaited_once()
                metadata.return_value.delete.assert_awaited_once()
        return response, status

    async def test_async_failure_returns_pve_error_without_cleanup(self):
        response, _ = await self.run_delete([
            {"status": "running"},
            {"status": "stopped", "exitstatus": "disk removal failed"},
            [{"t": "TASK ERROR: disk removal failed"}],
        ])
        self.assertEqual(response.status_code, 400)
        self.assertIn("disk removal failed", json.loads(response.body)["msg"])

    async def test_cleanup_only_after_success(self):
        response, status = await self.run_delete([
            {"status": "running"}, {"status": "stopped", "exitstatus": "OK"},
        ])
        self.assertEqual(status.await_count, 2)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(json.loads(response.body)["data"]["deleted"])

    async def test_command_failure(self):
        response, status = await self.run_delete(command_result=(1, "", "VM is locked"))
        self.assertEqual(response.status_code, 400)
        self.assertIn("VM is locked", json.loads(response.body)["msg"])
        status.assert_not_awaited()

    async def test_missing_task_id_is_not_success(self):
        response, status = await self.run_delete(command_result=(0, "", ""))
        self.assertEqual(response.status_code, 400)
        status.assert_not_awaited()

    async def test_status_query_failure_is_not_success(self):
        response, _ = await self.run_delete(RuntimeError("status unavailable"))
        self.assertEqual(response.status_code, 400)
        self.assertIn("status unavailable", json.loads(response.body)["msg"])

    async def test_timeout_is_not_success(self):
        response, _ = await self.run_delete(TimeoutError())
        self.assertEqual(response.status_code, 400)
        self.assertIn("超时", json.loads(response.body)["msg"])


if __name__ == "__main__":
    unittest.main()
