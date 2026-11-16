import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException
from pydantic import ValidationError
from tortoise import Tortoise

from app.models import CabinetMonitorConfig, CabinetMonitorTarget, MonitorEventConfig

from app.services import cabinet_monitor as service
from app.services.monitor_event_config import SelectedHost


class CabinetMonitorTests(unittest.IsolatedAsyncioTestCase):
    def device(self, **changes):
        values = dict(
            id=7,
            name="server",
            customer_ids=[1],
            customer_id=1,
            status=1,
            attributes={"ipmi_host": "192.0.2.40"},
            business_ip="192.0.2.10",
            mgmt_ip="192.0.2.20",
            u_position=12,
            cabinet=SimpleNamespace(name="rack", status=True, customer_id=None),
            location=SimpleNamespace(name="site"),
        )
        return SimpleNamespace(**(values | changes))

    def test_inventory_status_customer_and_ip_precedence(self):
        self.assertEqual(service.device_targets(self.device(), {"1": "Customer"}, {})[0]["ip"], "192.0.2.40")
        self.assertEqual(service.device_targets(self.device(attributes={}), {"1": "C"}, {})[0]["ip"], "")
        self.assertEqual(
            service.device_targets(self.device(attributes={"IPMI地址": "192.0.2.41"}), {"1": "C"}, {})[0]["ip"],
            "192.0.2.41",
        )
        self.assertEqual(
            service.device_targets(self.device(), {"1": "C"}, {"7:device": "192.0.2.30"})[0]["ip"], "192.0.2.30"
        )
        for state in (0, 4, 6):
            self.assertEqual(service.device_targets(self.device(status=state), {"1": "C"}, {}), [])
        self.assertEqual(service.device_targets(self.device(customer_ids=[], customer_id=None), {"1": "C"}, {}), [])

    def test_four_nodes_are_independent_and_do_not_use_chassis_address(self):
        device = self.device(
            attributes={
                "form_factor": "four_node",
                "ipmi_host": "192.0.2.99",
                "nodes": [
                    {"name": "N1", "customer_id": 1, "status": 1, "ip": "192.0.2.1"},
                    {"name": "N2", "customer_id": 2, "status": 1, "ipmiHost": "192.0.2.2"},
                    {"name": "N3", "status": 1},
                    {"name": "N4", "customer_id": 1, "status": 4},
                ],
            }
        )
        targets = service.device_targets(device, {"1": "A", "2": "B"}, {})
        self.assertEqual([t["key"] for t in targets], ["7:N1", "7:N2"])
        self.assertEqual([t["ip"] for t in targets], ["", "192.0.2.2"])

    def test_invalid_address_and_settings(self):
        for address in ("127.0.0.1", "0.0.0.0", "224.0.0.1", "::1", "169.254.1.2", "example.com", "1.2.3.4,5.6.7.8"):
            self.assertEqual(service.normalize_ip(address), "")
        with self.assertRaises(ValidationError):
            service.CabinetSettings(
                revision=0, enabled=True, template_id="1", group_id="1", overrides={"7:device": "bad"}
            )

    def test_item_must_target_correct_interface_and_be_enabled(self):
        def item(key, **kwargs):
            return {"itemid": "1", "status": "0", "state": "0", "interfaceid": "10", "key_": key, **kwargs}

        for key in ("icmpping", "icmpping[]", "icmpping[192.0.2.1]", "icmpping[{HOST.CONN},5]"):
            self.assertEqual(service.ping_items([item(key)], "192.0.2.1", {"10"}), ["1"])
        self.assertEqual(
            service.ping_items([item("icmpping[{HOST.CONN}]", interfaceid="0")], "192.0.2.1", {"10"}, True), ["1"]
        )
        for bad in [
            item("icmpping[192.0.2.2]"),
            item("icmpping", status="1"),
            item("icmpping", state="1"),
            item("icmpping", interfaceid="11"),
            item("icmpping[{$TARGET}]"),
            item("agent.ping"),
        ]:
            self.assertEqual(service.ping_items([bad], "192.0.2.1", {"10"}), [])

    async def test_create_then_reuse_deterministic_host(self):
        target = {"key": "7:device", "ip": "192.0.2.1", "customer": "C", "name": "server"}
        config = SimpleNamespace(group_id="2", template_id="3", proxy_id="4")
        hosts, writes = [], []

        async def call(method, params):
            if method == "hostinterface.get":
                return [{"hostid": "1", "interfaceid": "10"}] if hosts else []
            if method == "host.get":
                return hosts
            if method == "host.create":
                writes.append(params)
                hosts.append(
                    {
                        "hostid": "1",
                        "host": params["host"],
                        "status": "0",
                        "parentTemplates": [{"templateid": "3"}],
                        "interfaces": [{"interfaceid": "10", "ip": target["ip"], "useip": "1", "main": "1"}],
                    }
                )
                return {"hostids": ["1"]}
            if method == "item.get":
                return [
                    {"itemid": "5", "key_": "icmpping[{HOST.CONN},5]", "status": "0", "state": "0", "interfaceid": "0"}
                ]
            if method == "trigger.get":
                return [{"triggerid": "6"}]
            raise AssertionError(method)

        client = SimpleNamespace(call=call)
        self.assertEqual(await service.enrol(client, target, config), ("1", ["5"]))
        self.assertEqual(await service.enrol(client, target, config), ("1", ["5"]))
        self.assertEqual(len(writes), 1)
        self.assertEqual(writes[0]["proxyid"], "4")
        self.assertNotEqual(service.host_name(target), service.host_name(target | {"ip": "192.0.2.2"}))

    async def test_disabled_existing_host_never_reenabled(self):
        client = SimpleNamespace(call=AsyncMock(side_effect=[[], [{"hostid": "1", "status": "1"}]]))
        with self.assertRaises(HTTPException):
            await service.enrol(client, {"key": "7:device", "ip": "192.0.2.1"}, SimpleNamespace())
        self.assertFalse(any(c.args[0] in ("host.create", "host.update") for c in client.call.call_args_list))

    async def test_failed_feishu_delivery_not_marked_sent_and_success_deduplicated(self):
        row = SimpleNamespace(
            id=1,
            target_key="7:device",
            metadata={"ip": "192.0.2.1"},
            reason="missing",
            notified={},
            notification_error="",
        )
        config = SimpleNamespace(enabled=True, recipient_ids=[1])
        with (
            patch.object(service.CabinetMonitorConfig, "get_or_none", AsyncMock(return_value=None)),
            patch.object(service.MonitorNotificationConfig, "get_or_none", AsyncMock(return_value=config)),
            patch.object(service.User, "filter", AsyncMock(return_value=[SimpleNamespace(id=1)])),
            patch("app.utils.feishu_app.feishu_app_enabled", return_value=True),
            patch("app.services.monitor_notifications.send_to_user", AsyncMock(return_value=False)) as send,
        ):
            await service.notify_failure(row)
            self.assertEqual(row.notified, {})
            self.assertTrue(row.notification_error)
            send.return_value = True
            await service.notify_failure(row)
            await service.notify_failure(row)
            self.assertEqual(send.await_count, 2)
            self.assertIn("1", row.notified)


class CabinetMonitorDatabaseTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        await Tortoise.init(db_url="sqlite://:memory:", modules={"models": ["app.models"]})
        await Tortoise.generate_schemas()
        await CabinetMonitorConfig.create(id=1, enabled=True, template_id="1", group_id="2")

    async def asyncTearDown(self):
        await Tortoise.close_connections()

    async def test_automatic_category_is_persisted_once_and_preserves_user_edits(self):
        from app.services.monitor_event_config import load_settings

        first = await load_settings()
        category = next(c for c in first["categories"] if c["key"] == service.CATEGORY)
        self.assertEqual(category["fields"], service.FIELDS)
        second = await load_settings()
        self.assertEqual(first["revision"], second["revision"])
        row = await MonitorEventConfig.get(id=1)
        for category in row.categories:
            if category["key"] == service.CATEGORY:
                category.update(label="Customer machines", fields=[{"key": "customer", "label": "Customer"}])
        await row.save()
        with patch.object(service, "inventory", AsyncMock(return_value=[])):
            scope = await service.effective_settings()
        persisted = next(c for c in scope["categories"] if c["key"] == service.CATEGORY)
        self.assertEqual(persisted["label"], "Customer machines")
        self.assertEqual(persisted["fields"], [{"key": "customer", "label": "Customer"}])

    async def test_lease_prevents_concurrent_creation(self):
        await CabinetMonitorConfig.filter(id=1).update(lease_until=9999999999)
        with patch.object(service, "inventory", AsyncMock()) as inventory:
            with self.assertRaises(HTTPException) as exc:
                await service.synchronize(force=True)
        self.assertEqual(exc.exception.status_code, 409)
        inventory.assert_not_called()

    async def test_effective_scope_preserves_manual_selection_and_removes_retired_targets(self):
        await MonitorEventConfig.create(
            id=1, categories=[], hosts=[{"hostid": "1", "itemids": ["10"]}], updated_by_id=1
        )
        target = {
            "key": "7:device",
            "ip": "192.0.2.1",
            "name": "server",
            "customer": "C",
            "location": "L",
            "cabinet": "R",
            "position": "1U",
        }
        await CabinetMonitorTarget.create(
            target_key=target["key"], metadata=target, host_id="2", item_ids=["20"], status="managed"
        )
        with patch.object(service, "inventory", AsyncMock(return_value=[target])):
            scope = await service.effective_settings()
        self.assertEqual([h["hostid"] for h in scope["hosts"]], ["1", "2"])
        self.assertEqual(scope["hosts"][1]["attributes"]["customer"], "C")
        with patch.object(service, "inventory", AsyncMock(return_value=[])):
            retired = await service.effective_settings()
        self.assertEqual(retired["hosts"], [{"hostid": "1", "itemids": ["10"], "category": None}])
        self.assertNotEqual(scope["revision"], retired["revision"])

    async def test_address_changed_not_counted_as_managed(self):
        target = {"key": "7:device", "ip": "192.0.2.2"}
        await CabinetMonitorTarget.create(
            target_key="7:device", metadata={"ip": "192.0.2.1"}, host_id="1", item_ids=["1"], status="managed"
        )
        with patch.object(service, "inventory", AsyncMock(return_value=[target])):
            result = await service.view()
            scope = await service.effective_settings()
        self.assertEqual(result["rows"][0]["status"], "pending")
        self.assertEqual(scope["hosts"], [])

    async def test_custom_classification_and_items_survive_sync_and_removal_is_persistent(self):
        await MonitorEventConfig.create(
            id=1, updated_by_id=1, categories=[{"key": "network", "label": "Network", "fields": []}], hosts=[]
        )
        target = {
            "key": "7:device",
            "ip": "192.0.2.2",
            "name": "server",
            "customer": "C",
            "location": "L",
            "cabinet": "R",
            "position": "1U",
        }
        row = await CabinetMonitorTarget.create(
            target_key="7:device", metadata=target, host_id="2", item_ids=["20"], status="managed"
        )
        client = AsyncMock()
        client.__aenter__.return_value = client

        async def call(method, params):
            if method == "host.get":
                return [{"hostid": "2", "status": "0"}]
            if method == "item.get":
                return [{"hostid": "2", "itemid": "99", "status": "0"}]
            raise AssertionError(method)

        client.call.side_effect = call
        with (
            patch("app.services.monitor_events.ZabbixClient", return_value=client),
            patch.object(service, "inventory", AsyncMock(return_value=[target])),
        ):
            await CabinetMonitorConfig.filter(id=1).update(lease_until=9999999999)
            await service.update_host_policy(
                "2", 0, selection=SelectedHost(hostid="2", category="network", itemids=["99"])
            )
            self.assertEqual((await CabinetMonitorConfig.get(id=1)).lease_until, 9999999999)
            await CabinetMonitorConfig.filter(id=1).update(lease_until=0)
            row.item_ids = ["20", "21"]
            await row.save()
            scope = await service.effective_settings()
            self.assertEqual(scope["hosts"][0]["itemids"], ["99"])
            self.assertEqual(scope["hosts"][0]["category"], "network")
            await service.update_host_policy("2", 1, excluded=True)
            self.assertEqual((await service.effective_settings())["hosts"], [])
            with patch.object(service, "enrol", AsyncMock()) as enrol:
                await service.synchronize(force=True, notify=False)
                enrol.assert_not_called()
            self.assertEqual((await service.view())["rows"][0]["status"], "excluded")
            await service.update_host_policy("2", 2, excluded=False)
            with patch.object(service, "enrol", AsyncMock(return_value=("2", ["20", "21"]))):
                await service.synchronize(force=True, notify=False)
            self.assertEqual((await service.effective_settings())["hosts"][0]["itemids"], ["99"])

    async def test_policy_revision_rejects_conflicts_but_sync_lease_allows_editing(self):
        await CabinetMonitorTarget.create(target_key="7:device", host_id="2")
        with self.assertRaises(HTTPException) as stale:
            await service.update_host_policy("2", 99, excluded=True)
        self.assertEqual(stale.exception.status_code, 409)
        await CabinetMonitorConfig.filter(id=1).update(lease_until=9999999999)
        await service.update_host_policy("2", 0, excluded=True)
        config = await CabinetMonitorConfig.get(id=1)
        self.assertTrue(config.host_policies["7:device"]["excluded"])
        self.assertEqual(config.lease_until, 9999999999)

    async def test_mixed_batch_is_atomic_and_can_save_during_sync(self):
        from app.api.v1.monitor_events import BatchItems

        await MonitorEventConfig.create(
            id=1,
            updated_by_id=1,
            categories=[],
            hosts=[
                {"hostid": "1", "name": "Manual", "category": None, "itemids": ["10"], "attributes": {"keep": "value"}}
            ],
        )
        target = {
            "key": "7:device",
            "ip": "192.0.2.2",
            "name": "Auto",
            "customer": "C",
            "location": "L",
            "cabinet": "R",
            "position": "1U",
        }
        await CabinetMonitorTarget.create(
            target_key="7:device", metadata=target, host_id="2", item_ids=["20"], status="managed"
        )
        await CabinetMonitorConfig.filter(id=1).update(
            lease_until=9999999999, host_policies={"7:device": {"attributes": {"customer": "Custom"}}}
        )
        client = AsyncMock()
        client.__aenter__.return_value = client
        valid_items = [{"itemid": "11", "hostid": "1", "status": "0"}, {"itemid": "21", "hostid": "2", "status": "0"}]

        async def call(method, params):
            if method == "host.get":
                return [{"hostid": "1", "status": "0"}, {"hostid": "2", "status": "0"}]
            if method == "item.get":
                return valid_items
            raise AssertionError(method)

        client.call.side_effect = call
        with (
            patch("app.services.monitor_events.ZabbixClient", return_value=client),
            patch.object(service, "inventory", AsyncMock(return_value=[target])),
        ):
            from app.services.monitor_event_config import load_settings

            revision = (await load_settings())["revision"]
            bad = BatchItems(
                revision=revision,
                automatic_revision=0,
                hosts=[{"hostid": "1", "itemids": ["11"]}, {"hostid": "2", "itemids": ["11"]}],
            )
            with self.assertRaises(HTTPException):
                await service.update_monitor_items(bad, 1)
            self.assertEqual((await MonitorEventConfig.get(id=1)).hosts[0]["itemids"], ["10"])
            self.assertNotIn("itemids", (await CabinetMonitorConfig.get(id=1)).host_policies["7:device"])
            good = BatchItems(
                revision=revision,
                automatic_revision=0,
                hosts=[{"hostid": "1", "itemids": ["11"]}, {"hostid": "2", "itemids": ["21"]}],
            )
            result = await service.update_monitor_items(good, 1)
            self.assertEqual((await MonitorEventConfig.get(id=1)).hosts[0]["itemids"], ["11"])
            config = await CabinetMonitorConfig.get(id=1)
            self.assertEqual(config.host_policies["7:device"]["itemids"], ["21"])
            self.assertEqual(config.host_policies["7:device"]["attributes"], {"customer": "Custom"})
            self.assertEqual(config.lease_until, 9999999999)
            all_items = BatchItems(**result, hosts=[{"hostid": "1", "itemids": None}, {"hostid": "2", "itemids": None}])
            await service.update_monitor_items(all_items, 1)
            self.assertIsNone((await CabinetMonitorConfig.get(id=1)).host_policies["7:device"]["itemids"])


if __name__ == "__main__":
    unittest.main()
