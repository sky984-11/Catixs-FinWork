import json
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import httpx

from app.models.admin import Api
from app.models.asset import CloudResourceSnapshot, CloudDhcpPool, CloudDhcpLease
from app.models.remote_assistance import RemoteHands
from app.models.ticket import Ticket, TicketReply
from app.schemas import Fail, Success, SuccessExtra
from app.services import fw_ops_mcp as ops
from app.services.fw_ops_catalog import OPS_DATASETS
from tests import test_fw_database_mcp as base_tests


class OpsMcpTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = base_tests.DatabaseMcpTests.asyncSetUp
    asyncTearDown = base_tests.DatabaseMcpTests.asyncTearDown
    call = base_tests.DatabaseMcpTests.call

    async def grant(self, path):
        api, _ = await Api.get_or_create(path=path, method="GET", defaults={"summary": "test", "tags": "test"})
        await self.role.apis.add(api)

    async def test_all_catalog_projections_and_permissions(self):
        for name, (_, path, _) in OPS_DATASETS.items():
            with self.subTest(dataset=name):
                result, data = await self.call("finwork_query", {"dataset": name}, self.admin)
                self.assertFalse(result["isError"], data)
                self.assertIn("rows", data)
                if path:
                    result, _ = await self.call("finwork_query", {"dataset": name})
                    self.assertTrue(result["isError"])
        _, schema = await self.call("finwork_schema", {})
        self.assertEqual(set(schema["datasets"]), {"tickets", "ticket_replies"})
        self.assertEqual(set(schema["operations"]), {"traffic_regions", "traffic_widget", "traffic_graph"})

    async def test_ticket_reply_scope_uses_parent_ticket(self):
        mine = await Ticket.get(ticket_no="MCP-1")
        other = await Ticket.get(ticket_no="MCP-2")
        await TicketReply.create(ticket_id=mine.id, user_id=self.other.id, content="Reply to my ticket")
        await TicketReply.create(ticket_id=other.id, user_id=self.user.id, content="Not my ticket")
        result, data = await self.call("finwork_query", {"dataset": "ticket_replies"})
        self.assertFalse(result["isError"], data)
        self.assertEqual([row["content"] for row in data["rows"]], ["Reply to my ticket"])

    async def test_cloud_snapshot_projection_filter_and_age(self):
        with patch.object(ops, "cloud_read", AsyncMock()) as reader:
            result, _ = await self.call("finwork_ops_read", {"action": "cloud_vms"})
            self.assertTrue(result["isError"])
            reader.assert_not_awaited()
        await self.grant("/api/v1/pve/vms")
        result, _ = await self.call("finwork_ops_read", {"action": "cloud_vms"})
        self.assertTrue(result["isError"])
        await CloudResourceSnapshot.create(
            key="fleet",
            synced_at=datetime.now(timezone.utc) - timedelta(minutes=10),
            dirty=False,
            payload={
                "items": [
                    {
                        "remote": "node1",
                        "vmid": 101,
                        "name": "Test VM",
                        "status": "running",
                        "password": "never expose",
                        "config": {"token": "secret"},
                    },
                    {"remote": "node2", "vmid": 102, "status": "stopped"},
                ]
            },
        )
        result, data = await self.call("finwork_ops_read", {"action": "cloud_vms", "remote": "node1"})
        self.assertFalse(result["isError"], data)
        self.assertEqual(data["row_count"], 1)
        self.assertTrue(data["stale"])
        self.assertNotIn("password", data["rows"][0])
        self.assertNotIn("config", data["rows"][0])
        _, data = await self.call("finwork_ops_read", {"action": "cloud_vms", "mode": "count"})
        self.assertEqual(data["count"], 2)
        row = await CloudResourceSnapshot.get(key="fleet")
        self.assertFalse(row.dirty)  # The reader never schedules a refresh or changes the snapshot.

    async def test_syslog_permissions_paths_errors_and_redaction(self):
        await self.grant("/api/v1/syslog/logs")
        with patch("app.api.v1.syslog.syslog.query_syslog_logs", AsyncMock()) as reader:
            for arguments in (
                {"device": "host;whoami", "file": "test.log"},
                {"device": "192.0.2.1", "file": "../secret"},
            ):
                result, _ = await self.call("finwork_ops_read", {"action": "syslog_logs", **arguments})
                self.assertTrue(result["isError"])
            reader.assert_not_awaited()
        arguments = {"action": "syslog_logs", "device": "192.0.2.1", "file": "test.log", "limit": 1}
        with patch(
            "app.api.v1.syslog.syslog.query_syslog_logs",
            AsyncMock(
                return_value=SuccessExtra(
                    data=[{"message": "link down password=hidden"}, {"message": "link up"}], total=2
                )
            ),
        ) as reader:
            result, data = await self.call("finwork_ops_read", arguments)
        self.assertFalse(result["isError"], data)
        self.assertTrue(data["has_more"])
        self.assertEqual(data["total"], 2)
        self.assertNotIn("hidden", json.dumps(data))
        self.assertIn("末尾", data["scope"])
        self.assertEqual(reader.call_args.kwargs["tail"], 1000)
        with patch("app.api.v1.syslog.syslog.query_syslog_logs", AsyncMock(return_value=Fail(msg="private SSH error"))):
            result, data = await self.call("finwork_ops_read", arguments)
        self.assertTrue(result["isError"])
        self.assertNotIn("private", json.dumps(data))

    async def test_syslog_directory_and_file_adapters(self):
        await self.grant("/api/v1/syslog/devices")
        await self.grant("/api/v1/syslog/files")
        with patch(
            "app.api.v1.syslog.syslog.list_syslog_devices", AsyncMock(return_value=Success(data=[{"ip": "192.0.2.1"}]))
        ):
            result, data = await self.call("finwork_ops_read", {"action": "syslog_devices"})
            self.assertFalse(result["isError"], data)
            self.assertEqual(data["row_count"], 1)
        with patch(
            "app.api.v1.syslog.syslog.list_syslog_files", AsyncMock(return_value=Success(data=[{"name": "test.log"}]))
        ):
            result, data = await self.call("finwork_ops_read", {"action": "syslog_files", "device": "192.0.2.1"})
            self.assertFalse(result["isError"], data)
            self.assertEqual(data["rows"][0]["name"], "test.log")

    async def test_traffic_fixed_targets_and_bounded_graph(self):
        result, data = await self.call("finwork_ops_read", {"action": "traffic_regions"})
        self.assertFalse(result["isError"])
        self.assertTrue(data["rows"])
        self.assertNotIn("http", json.dumps(data))
        with patch.object(
            ops, "traffic_request", AsyncMock(return_value={"t": [], "rows": [], "points": []})
        ) as reader:
            for arguments in (
                {"region": "http://attacker"},
                {"region": "SZ", "url": "http://attacker"},
                {"region": "SZ", "start": "2026-10-01T00:00:00Z", "end": "2026-10-04T00:00:00Z"},
            ):
                result, _ = await self.call("finwork_ops_read", {"action": "traffic_graph", **arguments})
                self.assertTrue(result["isError"])
            reader.assert_not_awaited()
            result, data = await self.call(
                "finwork_ops_read",
                {
                    "action": "traffic_graph",
                    "region": "SZ",
                    "start": "2026-10-01T00:00:00Z",
                    "end": "2026-10-01T01:00:00Z",
                    "limit": 100,
                },
            )
            self.assertFalse(result["isError"], data)
            self.assertEqual(reader.call_args.args[1], "/api/v0/console/graph/line")
            self.assertEqual(reader.call_args.args[2]["limit"], 20)
            self.assertEqual(data["units"], "l3bps")
        with patch.object(ops, "traffic_request", AsyncMock(return_value={"rate": 3})) as reader:
            result, data = await self.call("finwork_ops_read", {"action": "traffic_widget", "region": "SZ"})
            self.assertFalse(result["isError"], data)
            self.assertEqual(reader.call_args.args[1], "/api/v0/console/widget/flow-rate")
            self.assertIsNone(data["units"])

    async def test_traffic_transport_errors_and_size_limit(self):
        original_client = httpx.AsyncClient
        requests = []

        async def handler(request):
            requests.append(request)
            self.assertNotIn("authorization", request.headers)
            if request.url.path == "/redirect":
                return httpx.Response(302, headers={"Location": "http://other.invalid/"})
            if request.url.path == "/oversized":
                return httpx.Response(200, content=b"x" * (1024 * 1024 + 1))
            if request.url.path == "/html":
                return httpx.Response(200, text="<html>error</html>")
            return httpx.Response(200, json={"rate": 10})

        def client(**kwargs):
            return original_client(transport=httpx.MockTransport(handler), **kwargs)

        with patch.object(ops.httpx, "AsyncClient", side_effect=client):
            self.assertEqual(await ops.traffic_request("http://source.invalid", "/read"), {"rate": 10})
            for path in ("/redirect", "/oversized", "/html"):
                with self.subTest(path=path), self.assertRaises(ValueError):
                    await ops.traffic_request("http://source.invalid", path)
        self.assertEqual(len(requests), 4)
        self.assertTrue(all(request.url.host == "source.invalid" for request in requests))

    async def test_dhcp_and_remote_log_business_data(self):
        pool = await CloudDhcpPool.create(
            name="Demo",
            region_code="TEST",
            vlan=100,
            gateway="192.0.2.1",
            cidr="192.0.2.0/24",
            start_ip="192.0.2.10",
            end_ip="192.0.2.20",
        )
        await CloudDhcpLease.create(
            pool_id=pool.id, ip="192.0.2.10", vlan=100, gateway="192.0.2.1", cidr="192.0.2.0/24"
        )
        await self.grant("/api/v1/pve/dhcp-pools")
        result, data = await self.call(
            "finwork_query", {"dataset": "dhcp_leases", "filters": [{"field": "pool_id", "value": pool.id}]}
        )
        self.assertFalse(result["isError"], data)
        self.assertEqual(data["rows"][0]["ip"], "192.0.2.10")
        await self.grant("/api/v1/remote-assistance/overview")
        await RemoteHands.create(
            customer="Demo", work_minutes=60, billing_data={"result": {"amount": 12}, "token": "hidden"}
        )
        result, data = await self.call("finwork_query", {"dataset": "remote_logs"})
        self.assertFalse(result["isError"], data)
        self.assertEqual(data["rows"][0]["billing_data"]["result"]["amount"], 12)
        self.assertNotIn("hidden", json.dumps(data))


if __name__ == "__main__":
    unittest.main()
