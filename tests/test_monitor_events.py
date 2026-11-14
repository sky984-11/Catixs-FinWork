import copy
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx
from fastapi import FastAPI, HTTPException
from httpx import ASGITransport, AsyncClient
from tortoise import Tortoise

from app.api.v1.monitor_events import router
from app.core.dependency import AuthControl, DependPermission
from app.models import Api, Menu, MonitorEventConfig, Role, User
from app.services.monitor_event_menu import ensure_monitor_event_menu
from app.services.monitor_event_config import load_settings
from app.services.monitor_events import ZabbixClient, advice, classify, dashboard, detail, get_hosts, tag_categories

HOST = {
    "hostid": "1",
    "host": "node-test",
    "name": "Test PVE",
    "status": "0",
    "maintenance_status": "0",
    "tags": [{"tag": "business_category", "value": "PVE 虚拟化"}, {"tag": "env", "value": "prod"}],
    "hostgroups": [{"name": "Proxmox"}],
    "inventory": {"location": "Test site"},
    "interfaces": [{"useip": "1", "ip": "192.0.2.10", "dns": "", "main": "1"}],
}
EVENT = {
    "eventid": "10",
    "objectid": "20",
    "name": "CPU utilization high",
    "severity": "4",
    "clock": "100",
    "r_eventid": "0",
    "acknowledged": "0",
    "suppressed": "1",
    "tags": [],
    "suppression_data": [],
    "acknowledges": [],
}
SCOPE = {
    "revision": 1,
    "categories": [{"key": "pve", "label": "PVE 虚拟化"}],
    "hosts": [{"hostid": "1", "name": "Test PVE", "category": "pve", "itemids": None}],
}


class FakeZabbix:
    version = "7.4.11"

    def __init__(self):
        self.event = copy.deepcopy(EVENT)
        self.manual = "1"
        self.calls = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    async def call(self, method, params):
        self.calls.append((method, params))
        if method == "hostgroup.get":
            return [{"groupid": "5", "name": "Test group"}]
        if method == "host.get":
            return [copy.deepcopy(HOST)]
        if method == "problem.get":
            return [copy.deepcopy(EVENT)]
        if method == "event.get":
            if params.get("eventids") == ["99"]:
                return [{"eventid": "99", "clock": "200"}]
            return [copy.deepcopy(self.event)]
        if method == "trigger.get":
            if "itemids" in params and "30" not in params["itemids"]:
                return []
            return [
                {
                    "triggerid": "20",
                    "manual_close": self.manual,
                    "hosts": [{"hostid": "1"}],
                    "expression": "last(/node-test/cpu)>90",
                    "items": [{"itemid": "30"}],
                }
            ]
        if method == "item.get":
            return [
                {
                    "itemid": "30",
                    "hostid": "1",
                    "name": "CPU",
                    "lastvalue": "95",
                    "lastclock": "100",
                    "units": "%",
                    "value_type": "0",
                    "status": "0",
                }
            ]
        if method == "history.get":
            return [{"clock": "150", "value": "95.5", "ns": "0"}, {"clock": "100", "value": "80", "ns": "0"}]
        if method == "event.acknowledge":
            return {"eventids": params["eventids"]}
        raise AssertionError(method)


class MonitorEventTests(unittest.IsolatedAsyncioTestCase):
    async def test_scope_change_during_action_requires_refresh(self):
        with patch(
            "app.api.v1.monitor_events.load_settings",
            AsyncMock(side_effect=[SCOPE, {**SCOPE, "revision": 2, "hosts": []}]),
        ):
            response = await self.client.post("/10/actions", json={"action": "close", "message": "Checked"})
        self.assertEqual(response.status_code, 409)
        self.assertNotIn("event.acknowledge", [method for method, _ in self.fake.calls])

    async def test_empty_configuration_makes_no_upstream_requests(self):
        await MonitorEventConfig.all().delete()
        response = await self.client.get("")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["data"]["configured"])
        self.assertFalse(self.fake.calls)
        self.assertEqual((await self.client.get("/10")).status_code, 404)
        self.assertFalse(self.fake.calls)

    async def test_search_requires_group_and_only_reads_group_candidates(self):
        self.assertEqual((await self.client.get("/host-options", params={"keyword": "x"})).status_code, 422)
        self.assertFalse(self.fake.calls)
        response = await self.client.get("/host-options", params={"group_id": "5", "keyword": "test"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.fake.calls[0][1]["search"], {"host": "test", "name": "test"})
        self.assertEqual(self.fake.calls[0][1]["groupids"], ["5"])
        self.assertEqual(self.fake.calls[1][1]["hostids"], ["1"])
        self.fake.calls.clear()
        self.assertEqual((await self.client.get("/host-options", params={"group_id": "5"})).status_code, 200)
        self.assertEqual(self.fake.calls[0][1]["groupids"], ["5"])
        self.assertNotIn("search", self.fake.calls[0][1])

    async def test_group_options_never_load_all_hosts(self):
        response = await self.client.get("/host-groups")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"][0]["groupid"], "5")
        self.assertEqual([method for method, _ in self.fake.calls], ["hostgroup.get"])

    async def test_configuration_persists_categories_and_prevents_lost_updates(self):
        data = {
            "revision": 1,
            "category_tag": "env",
            "hosts": [{"hostid": "1"}],
        }
        result = await self.client.put("/settings", json=data)
        self.assertEqual(result.status_code, 200, result.text)
        self.assertEqual(result.json()["data"]["revision"], 2)
        self.assertFalse(self.fake.calls)  # Local categories work without Zabbix.
        self.assertEqual((await self.client.put("/settings", json=data)).status_code, 409)
        snapshot = (await self.client.get("")).json()["data"]
        self.assertEqual(snapshot["rows"][0]["categories"], ["pve"])
        self.assertEqual(snapshot["categories"][0]["label"], "PVE 虚拟化")
        self.assertEqual(
            (await self.client.put("/settings", json={**data, "revision": 2, "category_tag": ""})).status_code, 422
        )
        cleared = await self.client.put("/settings", json={"revision": 2, "categories": [], "hosts": []})
        self.assertEqual(cleared.status_code, 200)
        self.fake.calls.clear()
        await self.client.get("")
        self.assertFalse(self.fake.calls)

    async def test_queries_and_actions_cannot_escape_selected_hosts(self):
        await self.client.get("")
        await self.client.get("?history=true")
        await self.client.get("/10")
        for method, params in self.fake.calls:
            if method in {"host.get", "problem.get", "item.get"} or (method == "event.get" and "value" in params):
                self.assertEqual(params["hostids"], ["1"], (method, params))
        row = await MonitorEventConfig.get(id=1)
        row.hosts = [{"hostid": "2", "category": "pve"}]
        await row.save()
        original = self.fake.call

        async def filtered(method, params):
            if method == "host.get":
                return []
            return await original(method, params)

        self.fake.call = filtered
        response = await self.client.post("/10/actions", json={"action": "close", "message": "X"})
        self.assertEqual(response.status_code, 404)
        self.assertNotIn("event.acknowledge", [m for m, _ in self.fake.calls])

    async def asyncSetUp(self):
        await Tortoise.init(db_url="sqlite://:memory:", modules={"models": ["app.models"]})
        await Tortoise.generate_schemas()
        self.user = await User.create(username="event-admin", email="event@test.invalid", is_superuser=True)
        await MonitorEventConfig.create(
            id=1, revision=1, categories=SCOPE["categories"], hosts=SCOPE["hosts"], updated_by_id=self.user.id
        )
        app = FastAPI()
        app.include_router(router, prefix="/api/v1/monitor-events", dependencies=[DependPermission])

        async def auth():
            return self.user

        app.dependency_overrides[AuthControl.is_authed] = auth
        self.app = app
        self.client = AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test/api/v1/monitor-events", follow_redirects=True
        )
        self.fake = FakeZabbix()
        self.patch = patch("app.api.v1.monitor_events.ZabbixClient", return_value=self.fake)
        self.patch.start()

    async def asyncTearDown(self):
        self.patch.stop()
        await self.client.aclose()
        await Tortoise.close_connections()

    async def test_snapshot_counts_categories_and_history_keep_current_totals(self):
        current = await dashboard(self.fake)
        self.assertEqual(
            current["summary"], {"hosts": 1, "abnormal_hosts": 1, "problems": 1, "critical": 1, "suppressed": 1}
        )
        self.fake.event["r_eventid"] = "99"
        history = await dashboard(self.fake, history=True)
        self.assertTrue(history["rows"][0]["recovered"])
        self.assertEqual(history["rows"][0]["recovery_clock"], 200)
        self.assertEqual(history["rows"][0]["duration_seconds"], 100)
        self.assertEqual(history["summary"], current["summary"])
        self.assertEqual(history["rows"][0]["categories"], ["pve"])

    async def test_detail_locates_host_metric_and_recovery_time(self):
        self.fake.event["r_eventid"] = "99"
        result = await detail(self.fake, "10")
        self.assertEqual(result["hosts"][0]["addresses"], ["192.0.2.10"])
        self.assertEqual(result["hosts"][0]["location"], "Test site")
        self.assertEqual(result["items"][0]["lastvalue"], "95")
        self.assertEqual(result["recovery_clock"], 200)

    async def test_missing_recovery_event_does_not_invent_duration(self):
        self.fake.event["r_eventid"] = "99"
        original_call = self.fake.call

        async def call(method, params):
            if method == "event.get" and params.get("eventids") == ["99"]:
                return []
            return await original_call(method, params)

        self.fake.call = call
        result = await dashboard(self.fake, history=True)
        self.assertTrue(result["rows"][0]["recovered"])
        self.assertEqual(result["rows"][0]["recovery_clock"], 0)
        self.assertIsNone(result["rows"][0]["duration_seconds"])

    async def test_existing_recovery_clock_needs_no_extra_lookup(self):
        self.fake.event.update(r_eventid="99", r_clock="175")
        result = await dashboard(self.fake, history=True)
        self.assertEqual(result["rows"][0]["duration_seconds"], 75)
        self.assertFalse(any(p.get("eventids") == ["99"] for _, p in self.fake.calls))

    async def test_all_actions_are_audited_and_duration_bounded(self):
        bits = {
            "acknowledge": 6,
            "unacknowledge": 20,
            "comment": 4,
            "suppress": 36,
            "unsuppress": 68,
            "close": 5,
            "severity": 12,
        }
        for action, expected in bits.items():
            with self.subTest(action=action), patch("app.api.v1.monitor_events.time.time", return_value=1000):
                response = await self.client.post(
                    "/10/actions", json={"action": action, "message": "Checked", "minutes": 30, "severity": 3}
                )
                self.assertEqual(response.status_code, 200, response.text)
                method, params = self.fake.calls[-1]
                self.assertEqual(method, "event.acknowledge")
                self.assertEqual(params["action"], expected)
                self.assertIn(f"FinWork user:{self.user.id}", params["message"])
                if action == "suppress":
                    self.assertEqual(params["suppress_until"], 2800)

    async def test_closed_and_disallowed_close_do_not_write(self):
        self.fake.manual = "0"
        response = await self.client.post("/10/actions", json={"action": "close", "message": "Checked"})
        self.assertEqual(response.status_code, 409)
        self.fake.event["r_eventid"] = "99"
        response = await self.client.post("/10/actions", json={"action": "suppress", "message": "Checked"})
        self.assertEqual(response.status_code, 409)
        self.assertNotIn("event.acknowledge", [method for method, _ in self.fake.calls])

    async def test_invalid_requests_and_unauthorized_never_call_upstream(self):
        for payload in [
            {"action": "suppress", "message": " "},
            {"action": "suppress", "message": "X", "minutes": 0},
            {"action": "severity", "message": "X"},
            {"action": "execute", "message": "X"},
        ]:
            response = await self.client.post("/10/actions", json=payload)
            self.assertEqual(response.status_code, 422)
        self.assertFalse(self.fake.calls)
        self.user.is_superuser = False
        response = await self.client.get("")
        self.assertEqual(response.status_code, 403)
        self.app.dependency_overrides.clear()
        response = await self.client.get("")
        self.assertEqual(response.status_code, 401)

    async def test_read_only_role_cannot_submit_actions(self):
        self.user.is_superuser = False
        role = await Role.create(name="event-reader")
        api = await Api.create(path="/api/v1/monitor-events", method="GET", summary="Read", tags="Events")
        await role.apis.add(api)
        await self.user.roles.add(role)
        self.assertEqual((await self.client.get("")).status_code, 200)
        self.assertEqual(
            (await self.client.post("/10/actions", json={"action": "comment", "message": "X"})).status_code, 403
        )

    async def test_metric_history_validates_scope_and_returns_ordered_points(self):
        response = await self.client.get("/10/metrics/30/history?time_from=50&time_till=200")
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual([p["clock"] for p in data["points"]], [100, 150])
        self.assertEqual(data["points"][1]["value"], 95.5)
        params = next(p for m, p in self.fake.calls if m == "history.get")
        self.assertEqual(params["history"], 0)
        self.assertEqual(params["hostids"], ["1"])
        self.assertEqual(params["itemids"], ["30"])
        self.fake.calls.clear()
        self.assertEqual((await self.client.get("/10/metrics/999/history?time_from=50&time_till=200")).status_code, 404)
        self.assertFalse(any(m == "history.get" for m, _ in self.fake.calls))

    async def test_metric_history_rejects_invalid_range_and_permissions(self):
        for query in ["time_from=200&time_till=100", "time_from=0&time_till=604801", "time_from=-1&time_till=100"]:
            self.assertEqual((await self.client.get("/10/metrics/30/history?" + query)).status_code, 422)
        self.assertFalse(any(m == "history.get" for m, _ in self.fake.calls))
        await MonitorEventConfig.filter(id=1).update(hosts=[])
        self.assertEqual((await self.client.get("/10/metrics/30/history?time_from=50&time_till=200")).status_code, 404)
        self.user.is_superuser = False
        self.assertEqual((await self.client.get("/10/metrics/30/history?time_from=50&time_till=200")).status_code, 403)
        self.app.dependency_overrides.clear()
        self.assertEqual((await self.client.get("/10/metrics/30/history?time_from=50&time_till=200")).status_code, 401)

    async def test_metric_history_numeric_type_and_truncation(self):
        original_call = self.fake.call
        value_type = "3"

        async def call(method, params):
            if method == "item.get":
                rows = await original_call(method, params)
                rows[0]["value_type"] = value_type
                return rows
            if method == "history.get":
                self.assertEqual(params["history"], 3)
                return [{"clock": str(i), "value": "1"} for i in range(10001, 0, -1)]
            return await original_call(method, params)

        self.fake.call = call
        response = await self.client.get("/10/metrics/30/history?time_from=0&time_till=20000")
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertTrue(data["truncated"])
        self.assertEqual(len(data["points"]), 10000)
        self.assertEqual(data["points"][0]["clock"], 2)
        value_type = "1"
        self.assertEqual((await self.client.get("/10/metrics/30/history?time_from=0&time_till=20000")).status_code, 422)

    async def test_local_categories_crud_without_zabbix_and_delete_guard(self):
        payload = {
            "revision": 1,
            "categories": [{"key": "pve", "label": "Compute"}, {"key": "new", "label": "New"}],
            "hosts": SCOPE["hosts"],
        }
        # API accepts identifiers only, not presentation names.
        payload["hosts"] = [{"hostid": "1", "category": "pve", "itemids": None}]
        self.assertEqual((await self.client.put("/settings", json=payload)).status_code, 200)
        self.assertFalse(self.fake.calls)
        result = await self.client.get("/settings")
        self.assertEqual(result.json()["data"]["categories"][0]["label"], "Compute")
        self.assertFalse(self.fake.calls)
        payload.update(revision=2, categories=[{"key": "new", "label": "New"}])
        self.assertEqual((await self.client.put("/settings", json=payload)).status_code, 422)
        payload["hosts"][0]["category"] = "new"
        self.assertEqual((await self.client.put("/settings", json=payload)).status_code, 200)
        self.assertFalse(self.fake.calls)

    async def test_item_scope_validates_owner_and_filters_all_event_paths(self):
        payload = {"revision": 1, "hosts": [{"hostid": "1", "category": "pve", "itemids": ["30"]}]}
        saved = await self.client.put("/settings", json=payload)
        self.assertEqual(saved.status_code, 200, saved.text)
        self.assertEqual(saved.json()["data"]["hosts"][0]["itemids"], ["30"])
        self.fake.calls.clear()
        response = await self.client.get("?history=true")
        self.assertEqual(response.status_code, 200)
        queries = [
            (method, p)
            for method, p in self.fake.calls
            if method == "problem.get" or method == "event.get" and "value" in p
        ]
        self.assertTrue(queries)
        self.assertTrue(all(p["objectids"] == ["20"] for _, p in queries))
        self.assertEqual((await self.client.get("/10")).status_code, 200)
        # Omitted fields in older clients must not broaden a restricted scope.
        legacy = await self.client.put("/settings", json={"revision": 2, "hosts": [{"hostid": "1"}]})
        self.assertEqual(legacy.status_code, 200)
        self.assertEqual(legacy.json()["data"]["hosts"][0]["itemids"], ["30"])
        payload.update(revision=3, hosts=[{"hostid": "1", "category": "pve", "itemids": ["999"]}])
        self.assertEqual((await self.client.put("/settings", json=payload)).status_code, 422)
        for invalid in [[], ["30", "30"], ["x"], ["0"]]:
            payload["hosts"][0]["itemids"] = invalid
            self.assertEqual((await self.client.put("/settings", json=payload)).status_code, 422)
        row = await MonitorEventConfig.get(id=1)
        row.hosts[0]["itemids"] = ["999"]
        await row.save()
        self.fake.calls.clear()
        empty = (await self.client.get("?history=true")).json()["data"]
        self.assertEqual(empty["rows"], [])
        self.assertEqual(empty["summary"]["problems"], 0)
        self.assertFalse(any(m in {"problem.get", "event.get"} for m, _ in self.fake.calls))
        self.assertEqual((await self.client.get("/10")).status_code, 404)
        self.assertEqual((await self.client.get("/10/metrics/30/history?time_from=50&time_till=200")).status_code, 404)
        self.assertEqual(
            (await self.client.post("/10/actions", json={"action": "acknowledge", "message": "test"})).status_code, 404
        )
        self.assertFalse(any(m == "event.acknowledge" for m, _ in self.fake.calls))

    async def test_host_items_only_queries_explicit_host(self):
        self.assertEqual((await self.client.get("/host-items")).status_code, 422)
        self.assertFalse(self.fake.calls)
        response = await self.client.get("/host-items?host_id=1&keyword=cpu")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["rows"][0]["itemid"], "30")
        self.assertTrue(
            all(params["hostids"] == ["1"] for method, params in self.fake.calls if method in {"host.get", "item.get"})
        )
        self.user.is_superuser = False
        self.assertEqual((await self.client.get("/host-items?host_id=1")).status_code, 403)

    async def test_old_tag_configuration_upgrades_once(self):
        row = await MonitorEventConfig.get(id=1)
        row.categories = []
        row.hosts = [{"hostid": "1", "name": "Test", "tags": HOST["tags"]}]
        await row.save()
        first = await load_settings()
        self.assertEqual(first["revision"], 2)
        self.assertEqual(first["categories"][0]["label"], "PVE 虚拟化")
        self.assertEqual(first["hosts"][0]["category"], first["categories"][0]["key"])
        self.assertIsNone(first["hosts"][0]["itemids"])
        row = await MonitorEventConfig.get(id=1)
        row.hosts[0]["tags"] = [{"tag": "business_category", "value": "Changed upstream"}]
        await row.save()
        second = await load_settings()
        self.assertEqual(second["revision"], 2)
        self.assertEqual(second["categories"], first["categories"])

    async def test_menu_only_granted_to_admin(self):
        admin = await Role.create(name="admin")
        reader = await Role.create(name="other")
        await ensure_monitor_event_menu()
        await ensure_monitor_event_menu()
        self.assertEqual(await admin.menus.filter(path="/ops/events").count(), 1)
        root = await admin.menus.filter(path="/events").get()
        self.assertEqual(root.parent_id, 0)
        self.assertEqual(str(root.menu_type), "catalog")
        self.assertEqual((await admin.menus.filter(path="/ops/events").first()).parent_id, root.id)
        self.assertEqual(await admin.menus.filter(parent_id=root.id).count(), 5)
        self.assertFalse(await reader.menus.filter(path="/ops/events").exists())

    async def test_menu_upgrade_preserves_existing_reader_access(self):
        await ensure_monitor_event_menu()
        menu = await Menu.get(path="/ops/events")
        reader = await Role.create(name="event-reader")
        await reader.menus.add(menu)
        await ensure_monitor_event_menu()
        self.assertTrue(await reader.menus.filter(path="/events").exists())
        self.assertTrue(await reader.menus.filter(path="/events/history").exists())
        self.assertFalse(await reader.menus.filter(path="/events/hosts").exists())
        self.assertEqual(await reader.apis.all().count(), 0)
        settings_api = await Api.create(
            path="/api/v1/monitor-events/settings", method="GET", summary="Read settings", tags="Events"
        )
        await reader.apis.add(settings_api)
        await ensure_monitor_event_menu()
        self.assertTrue(await reader.menus.filter(path="/events/hosts").exists())
        self.assertTrue(await reader.menus.filter(path="/events/categories").exists())
        self.assertFalse(await reader.apis.filter(method="PUT").exists())


class ZabbixTransportTests(unittest.IsolatedAsyncioTestCase):
    async def test_inherited_tags_are_merged_only_for_requested_hosts(self):
        fake = FakeZabbix()
        fake.call = AsyncMock(
            return_value=[
                {
                    **HOST,
                    "tags": [{"tag": "type", "value": "A"}],
                    "inheritedTags": [{"tag": "type", "value": "A"}, {"tag": "type", "value": "B"}],
                }
            ]
        )
        hosts = await get_hosts(fake, ["1"])
        self.assertEqual(fake.call.call_args.args[1]["hostids"], ["1"])
        self.assertEqual(len(hosts[0]["tags"]), 2)
        self.assertEqual(len(tag_categories(hosts, "type")[0]["1"]), 2)

    async def test_tag_categories_deduplicate_values_and_preserve_unclassified_hosts(self):
        hosts = [
            {
                "hostid": "1",
                "tags": [{"tag": "type", "value": "A"}, {"tag": "type", "value": "A"}, {"tag": "type", "value": "B"}],
            },
            {"hostid": "2", "tags": [{"tag": "type", "value": ""}]},
            {"hostid": "3", "tags": []},
        ]
        assigned, options = tag_categories(hosts, "type")
        self.assertEqual(len(assigned["1"]), 2)
        self.assertEqual(assigned["2"], ["untagged"])
        self.assertEqual(assigned["3"], ["untagged"])
        self.assertEqual(len(options), 3)
        hosts[0]["tags"] = [{"tag": "type", "value": "C"}]
        changed, labels = tag_categories(hosts, "type")
        self.assertNotEqual(changed["1"], assigned["1"])
        self.assertIn("C", [label["label"] for label in labels])

    async def test_empty_and_truncated_snapshots_are_explicit(self):
        fake = FakeZabbix()
        original = fake.call

        async def empty_problems(method, params):
            return [] if method == "problem.get" else await original(method, params)

        fake.call = empty_problems
        result = await dashboard(fake, config=SCOPE)
        self.assertEqual(result["summary"]["problems"], 0)
        self.assertEqual(result["rows"], [])

        async def two_problems(method, params):
            return [EVENT, {**EVENT, "eventid": "11"}] if method == "problem.get" else await original(method, params)

        fake.call = two_problems
        with patch("app.services.monitor_events.LIMIT", 1):
            result = await dashboard(fake, config=SCOPE)
        self.assertTrue(result["truncated"])
        self.assertEqual(len(result["rows"]), 1)

    async def test_missing_event_and_network_error(self):
        fake = FakeZabbix()
        fake.call = AsyncMock(return_value=[])
        with self.assertRaises(HTTPException) as caught:
            await detail(fake, "10", config=SCOPE)
        self.assertEqual(caught.exception.status_code, 404)
        client = ZabbixClient()
        client.modern = True
        client.client = AsyncMock()
        client.client.post.side_effect = httpx.ConnectError("secret-upstream-address")
        with self.assertRaises(HTTPException) as caught:
            await client.call("event.acknowledge", {})
        self.assertEqual(caught.exception.status_code, 502)
        self.assertNotIn("secret-upstream-address", caught.exception.detail)
        self.assertEqual(client.client.post.await_count, 1)

    async def test_auth_version_and_sanitized_errors(self):
        client = ZabbixClient()
        with patch(
            "app.services.monitor_events.settings",
            SimpleNamespace(ZABBIX_URL="https://example.invalid/api_jsonrpc.php", ZABBIX_TOKEN="test-secret"),
        ):
            for modern in [True, False]:
                client.modern = modern
                client.client = AsyncMock()
                client.client.post.return_value = httpx.Response(
                    200, json={"result": []}, request=httpx.Request("POST", "https://example.invalid")
                )
                await client.call("problem.get", {})
                kwargs = client.client.post.call_args.kwargs
                self.assertEqual("Authorization" in kwargs["headers"], modern)
                self.assertEqual("auth" in kwargs["json"], not modern)
            client.client.post.return_value = httpx.Response(
                200, json={"error": {"data": "test-secret"}}, request=httpx.Request("POST", "https://example.invalid")
            )
            with self.assertRaises(HTTPException) as caught:
                await client.call("problem.get", {})
            self.assertNotIn("test-secret", caught.exception.detail)

    async def test_classification_prefers_explicit_tags_and_advice_is_not_diagnosis(self):
        self.assertEqual(classify({**HOST, "tags": [{"tag": "finwork_category", "value": "circuit"}]}), "circuit")
        self.assertEqual(advice("SSD SMART failed")["type"], "存储")
        self.assertIn("不是已确认根因", advice("CPU high")["basis"])
