import unittest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

from app.services import cloud_vm_display as service


class DisplayMetadataTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        service._cache.clear()

    def test_creation_uses_pve_ctime_not_local_discovery_time(self):
        result = service.display_metadata(
            {"ostype": "l26", "meta": "creation-qemu=9.0,ctime=1725000000", "created_at": "2000-01-01"}
        )
        self.assertEqual(result["os_type"], "l26")
        self.assertEqual(result["created_at"], datetime.fromtimestamp(1725000000, timezone.utc).isoformat())
        self.assertIsNone(service.display_metadata({"created_at": "2000-01-01"})["created_at"])
        self.assertIsNone(service.display_metadata({"ctime": "nan"})["created_at"])
        self.assertIsNone(service.display_metadata({"ctime": "9999999999999999999"})["created_at"])

    async def test_enrichment_caches_only_display_fields(self):
        from app.api.v1.pve import pve

        row = {"remote": "test", "vmid": 100, "type": "pve-qemu", "node": "host"}
        with patch.object(
            pve,
            "pdm_get",
            AsyncMock(return_value={"ostype": "win11", "meta": "ctime=1725000000", "cipassword": "do-not-return"}),
        ) as get:
            await service.enrich_display_metadata([row])
            await service.enrich_display_metadata([row])
        self.assertEqual(get.await_count, 1)
        self.assertEqual(row["os_type"], "win11")
        self.assertNotIn("cipassword", row)

    async def test_node_path_fallback_and_failed_guest_do_not_fail_list(self):
        from app.api.v1.pve import pve

        row = {"remote": "test", "vmid": 100, "type": "pve-lxc", "node": "host"}
        with patch.object(
            pve, "pdm_get", AsyncMock(side_effect=[RuntimeError("old PDM"), {"ostype": "debian"}])
        ) as get:
            await service.enrich_display_metadata([row])
        self.assertEqual(get.await_count, 2)
        self.assertEqual(row["os_type"], "debian")
        self.assertIsNone(row["created_at"])
        failed = {"remote": "failed", "vmid": 1, "type": "pve-qemu"}
        with patch.object(pve, "pdm_get", AsyncMock(side_effect=RuntimeError("offline"))):
            await service.enrich_display_metadata([failed])
        self.assertEqual(failed["os_type"], "")
        self.assertIsNone(failed["created_at"])
