import unittest
from unittest.mock import AsyncMock, patch

from app.api.v1.pve import pve


class NetworkConfigTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.current = {
            "net0": "virtio=AA:BB:CC:DD:EE:00,rate=10.000,queues=4,bridge=vmbr10,firewall=0,link_down=1",
            "net1": "virtio=AA:BB:CC:DD:EE:01,trunks=20;30,bridge=vmbr20,tag=20,mtu=1500,rate=5,firewall=1",
        }
        self.networks = pve.vm_network_devices(self.current)

    async def submit(self, networks):
        payload = pve.VMConfigUpdateRequest(remote="test", vmid=100, networks=networks)
        with (
            patch.object(pve, "vm_config_from_pve", AsyncMock(return_value=("test-host", self.current))),
            patch.object(pve, "upsert_vm_metadata", AsyncMock()),
            patch.object(pve, "ssh_execute_pve", return_value=(0, "", "")) as execute,
        ):
            response = await pve.update_vm_config(payload)
        self.assertEqual(response.status_code, 200, response.body)
        return execute

    async def test_legacy_full_payload_only_writes_changed_device(self):
        self.networks[1]["bridge"] = "vmbr30"
        execute = await self.submit(self.networks)
        command = execute.call_args.args[1]
        self.assertNotIn("--net0", command)
        self.assertIn("--net1", command)
        self.assertIn("trunks=20;30", command)
        self.assertIn("AA:BB:CC:DD:EE:01", command)

    async def test_unchanged_devices_do_not_execute_commands(self):
        execute = await self.submit(self.networks)
        execute.assert_not_called()

    async def test_partial_update_preserves_other_options(self):
        execute = await self.submit([{"key": "net0", "bridge": "vmbr30"}])
        command = execute.call_args.args[1]
        self.assertIn("--net0", command)
        self.assertNotIn("--net1", command)
        for option in ("queues=4", "firewall=0", "rate=10.000", "link_down=1", "AA:BB:CC:DD:EE:00"):
            self.assertIn(option, command)

    def test_clear_optional_fields_preserves_mac_and_hidden_options(self):
        value = pve.merge_qemu_net_value(
            pve.VMNetworkDeviceRequest(key="net1", vlan=None, mtu=None, rate=None, firewall=False),
            self.networks[1],
        )
        self.assertEqual(value, "virtio=AA:BB:CC:DD:EE:01,trunks=20;30,bridge=vmbr20")

    def test_model_change_keeps_mac(self):
        value = pve.merge_qemu_net_value(pve.VMNetworkDeviceRequest(key="net0", model="e1000"), self.networks[0])
        self.assertEqual(value, self.current["net0"].replace("virtio=", "e1000="))

    async def test_delete_only_targets_selected_device(self):
        execute = await self.submit([{"key": "net1", "delete": True}])
        command = execute.call_args.args[1]
        self.assertIn("--delete net1", command)
        self.assertNotIn("--net0", command)
        self.assertNotIn("--net1", command)

    async def test_new_device_allocates_free_slot(self):
        execute = await self.submit([{"bridge": "vmbr30"}])
        command = execute.call_args.args[1]
        self.assertIn("--net2", command)
        self.assertNotIn("--net0", command)
        self.assertNotIn("--net1", command)


if __name__ == "__main__":
    unittest.main()
