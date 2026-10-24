import json
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import jwt
from fastapi import FastAPI, Request, Response
from httpx import ASGITransport, AsyncClient
from tortoise import Tortoise

from app.api.v1 import fw_assistant
from app.api.v1.fw_mcp import router
from app.core.middlewares import HttpAuditLogMiddleware
from app.models.admin import Api, Role, User
from app.models.asset import AssetCabinet, AssetDevice, AssetLocation, AssetRegion
from app.models.customer_center import CrmCustomer
from app.models.ticket import Ticket
from app.services import fw_database_mcp as mcp
from app.settings import settings


class DatabaseMcpTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        await Tortoise.init(db_url="sqlite://:memory:", modules={"models": ["app.models"]})
        await Tortoise.generate_schemas()
        self.user = await User.create(username="mcp-reader", email="reader@test.invalid")
        self.other = await User.create(username="mcp-other", email="other@test.invalid")
        self.admin = await User.create(username="mcp-admin", email="admin@test.invalid", is_superuser=True)
        self.role = await Role.create(name="mcp-reader")
        await self.user.roles.add(self.role)
        await Ticket.create(title="Mine", ticket_no="MCP-1", user_id=self.user.id)
        await Ticket.create(title="Other", ticket_no="MCP-2", user_id=self.other.id)
        self.app = FastAPI()
        self.app.include_router(router, prefix="/api/v1/fw-assistant")
        self.client = AsyncClient(transport=ASGITransport(app=self.app), base_url="http://test")
        token = jwt.encode(
            {"user_id": self.user.id, "exp": datetime.now(timezone.utc) + timedelta(hours=1)},
            settings.SECRET_KEY,
            algorithm=settings.JWT_ALGORITHM,
        )
        self.headers = {
            "token": token,
            "Accept": "application/json, text/event-stream",
            "MCP-Protocol-Version": mcp.PROTOCOL_VERSION,
        }
        self.enabled = patch.object(settings, "FW_ASSISTANT_DB_QUERY_ENABLED", True)
        self.enabled.start()

    async def asyncTearDown(self):
        self.enabled.stop()
        await self.client.aclose()
        await Tortoise.close_connections()

    async def call(self, name, arguments, user=None):
        result = await mcp.DatabaseMcpClient(user or self.user).call_tool(name, arguments)
        return result, json.loads(result["content"][0]["text"])

    async def post(self, message, **kwargs):
        return await self.client.post(
            "/api/v1/fw-assistant/mcp", json=message, headers=kwargs.pop("headers", self.headers), **kwargs
        )

    async def test_protocol_lifecycle_and_auth(self):
        response = await self.post(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "future-version",
                    "capabilities": {},
                    "clientInfo": {"name": "test", "version": "1"},
                },
            }
        )
        self.assertEqual(response.json()["result"]["protocolVersion"], mcp.PROTOCOL_VERSION)
        self.assertEqual(response.headers["cache-control"], "no-store")
        response = await self.post({"jsonrpc": "2.0", "method": "notifications/initialized"})
        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.content, b"")
        response = await self.post({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        self.assertEqual(len(response.json()["result"]["tools"]), 3)
        response = await self.post({"jsonrpc": "2.0", "id": 3, "method": "ping"}, headers={})
        self.assertEqual(response.status_code, 401)
        response = await self.client.get("/api/v1/fw-assistant/mcp", headers=self.headers)
        self.assertEqual(response.status_code, 405)

    async def test_protocol_invalid_requests_and_origin(self):
        message = {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}
        response = await self.post(message, headers={**self.headers, "Origin": "https://evil.invalid"})
        self.assertEqual(response.status_code, 403)
        response = await self.post(message, headers={**self.headers, "MCP-Protocol-Version": "invalid"})
        self.assertEqual(response.status_code, 400)
        response = await self.post(message, headers={**self.headers, "Accept": "application/json"})
        self.assertEqual(response.status_code, 406)
        response = await self.post([message])
        self.assertEqual(response.json()["error"]["code"], -32600)
        response = await self.post({**message, "method": "unknown"})
        self.assertEqual(response.json()["error"]["code"], -32601)
        response = await self.client.post(
            "/api/v1/fw-assistant/mcp", content="{", headers={**self.headers, "Content-Type": "application/json"}
        )
        self.assertEqual(response.json()["error"]["code"], -32700)
        response = await self.post({**message, "params": {"oversized": "x" * 65536}})
        self.assertEqual(response.status_code, 413)

    async def test_scope_cannot_be_overridden_by_filters(self):
        result, data = await self.call("finwork_query", {"dataset": "tickets"})
        self.assertFalse(result["isError"])
        self.assertEqual([row["title"] for row in data["rows"]], ["Mine"])
        _, data = await self.call(
            "finwork_query", {"dataset": "tickets", "filters": [{"field": "user_id", "value": self.other.id}]}
        )
        self.assertEqual(data["rows"], [])
        _, data = await self.call("finwork_query", {"dataset": "tickets", "mode": "count"})
        self.assertEqual(data["count"], 1)
        _, data = await self.call("finwork_query", {"dataset": "tickets", "mode": "count"}, self.admin)
        self.assertEqual(data["count"], 2)
        response = await self.post(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {"name": "finwork_query", "arguments": {"dataset": "tickets", "mode": "count"}},
            }
        )
        self.assertEqual(json.loads(response.json()["result"]["content"][0]["text"])["count"], 1)

    async def test_permissions_and_schema_projection(self):
        _, data = await self.call("finwork_schema", {})
        self.assertEqual(set(data["datasets"]), {"tickets", "ticket_replies"})
        result, _ = await self.call("finwork_query", {"dataset": "customers"})
        self.assertTrue(result["isError"])
        api = await Api.create(path="/api/v1/customer-center/customers", method="GET", summary="test", tags="test")
        await self.role.apis.add(api)
        await CrmCustomer.create(name="MCP test customer", finance_info="not exposed")
        result, data = await self.call("finwork_query", {"dataset": "customers"})
        self.assertFalse(result["isError"])
        self.assertEqual(data["rows"][0]["name"], "MCP test customer")
        self.assertEqual(data["rows"][0]["finance_info"], "not exposed")

    async def test_cabinet_permissions_and_fields(self):
        result, _ = await self.call("finwork_query", {"dataset": "cabinets"})
        self.assertTrue(result["isError"])
        _, schema = await self.call("finwork_schema", {})
        self.assertNotIn("cabinets", schema["datasets"])
        # A different asset permission must not grant access to cabinet information.
        other_api = await Api.create(path="/api/v1/asset/device/list", method="GET", summary="test", tags="test")
        await self.role.apis.add(other_api)
        result, _ = await self.call("finwork_query", {"dataset": "cabinets", "mode": "count"})
        self.assertTrue(result["isError"])
        api = await Api.create(path="/api/v1/asset/cabinet/list", method="GET", summary="test", tags="test")
        await self.role.apis.add(api)
        _, schema = await self.call("finwork_schema", {})
        self.assertEqual(schema["datasets"]["cabinets"]["location_name"], "所属机房/位置名称")
        self.assertIn("front_image_url", schema["datasets"]["cabinets"])
        for arguments in (
            {"columns": ["customer__finance_info"]},
            {"filters": [{"field": "location__address", "value": "test"}]},
            {"order_by": ["devices__mgmt_ip"]},
        ):
            result, _ = await self.call("finwork_query", {"dataset": "cabinets", **arguments})
            self.assertTrue(result["isError"])
        await self.role.apis.remove(api)
        result, _ = await self.call("finwork_query", {"dataset": "cabinets"})
        self.assertTrue(result["isError"])

    async def test_cabinet_queries_names_count_and_pagination(self):
        region = await AssetRegion.create(name="Test Region", code="MCP-REGION")
        location = await AssetLocation.create(name="Test DC", region_id=region.id)
        customer = await CrmCustomer.create(name="Test Customer")
        cabinet = await AssetCabinet.create(
            name="Rack A",
            code="R01",
            location_id=location.id,
            customer_id=customer.id,
            rental_start_u=5,
            rental_end_u=20,
            power_allocation_kw=3.5,
        )
        await AssetCabinet.create(name="Rack B", code="R02", location_id=location.id, status=False)
        result, data = await self.call("finwork_query", {"dataset": "cabinets", "order_by": ["code"]}, self.admin)
        self.assertFalse(result["isError"], data)
        self.assertEqual(data["row_count"], 2)
        self.assertEqual(data["rows"][0]["location_name"], "Test DC")
        self.assertEqual(data["rows"][0]["region_name"], "Test Region")
        self.assertEqual(data["rows"][0]["customer_name"], "Test Customer")
        self.assertEqual(data["rows"][0]["rental_start_u"], 5)
        self.assertEqual(data["rows"][0]["power_allocation_kw"], 3.5)
        self.assertIsNone(data["rows"][1]["customer_name"])
        filters = [
            {"field": "location_name", "value": "Test DC"},
            {"field": "region_name", "value": "Test Region"},
            {"field": "customer_name", "operator": "contains", "value": "Customer"},
            {"field": "status", "value": True},
        ]
        result, data = await self.call(
            "finwork_query", {"dataset": "cabinets", "filters": filters, "mode": "count"}, self.admin
        )
        self.assertFalse(result["isError"], data)
        self.assertEqual(data["count"], 1)
        result, data = await self.call(
            "finwork_query",
            {"dataset": "cabinets", "columns": ["id", "location_name", "customer_name"], "filters": filters},
            self.admin,
        )
        self.assertFalse(result["isError"], data)
        self.assertEqual(
            data["rows"], [{"id": cabinet.id, "location_name": "Test DC", "customer_name": "Test Customer"}]
        )
        _, data = await self.call(
            "finwork_query", {"dataset": "cabinets", "order_by": ["code"], "limit": 1}, self.admin
        )
        self.assertTrue(data["has_more"])
        self.assertEqual(data["next_offset"], 1)
        _, page = await self.call(
            "finwork_query",
            {"dataset": "cabinets", "order_by": ["code"], "limit": 1, "offset": data["next_offset"]},
            self.admin,
        )
        self.assertEqual(page["rows"][0]["name"], "Rack B")
        self.assertFalse(page["has_more"])

    async def test_all_device_fields_and_customer_details(self):
        region = await AssetRegion.create(name="Device Region", code="DEV-REGION")
        location = await AssetLocation.create(name="Device DC", region_id=region.id)
        cabinet = await AssetCabinet.create(name="Device Rack", location_id=location.id)
        customer = await CrmCustomer.create(name="Device Customer")
        for number in range(6):
            await AssetDevice.create(
                asset_no=f"DETAIL-{number}",
                name=f"Server {number}",
                cabinet_id=cabinet.id,
                region_id=region.id,
                location_id=location.id,
                customer_id=customer.id,
                status=1,
                type=0,
                u_position=number * 2 + 1,
                u_height=2,
                attributes={"cpu": "test CPU", "password": "never-expose-this"},
            )
        await AssetDevice.create(
            asset_no="UNASSIGNED",
            name="Unassigned",
            cabinet_id=cabinet.id,
            region_id=region.id,
            location_id=location.id,
            status=1,
        )
        api = await Api.create(path="/api/v1/asset/device/list", method="GET", summary="test", tags="test")
        await self.role.apis.add(api)
        _, schema = await self.call("finwork_schema", {})
        fields = schema["datasets"]["devices"]
        self.assertTrue(set(AssetDevice._meta.fields_db_projection).issubset(fields))
        self.assertIn("customer_name", fields)
        arguments = {
            "dataset": "devices",
            "filters": [
                {"field": "status", "value": 1},
                {"field": "customer_id", "operator": "isnull", "value": False},
            ],
        }
        _, count = await self.call("finwork_query", {**arguments, "mode": "count"})
        result, data = await self.call("finwork_query", {**arguments, "columns": list(fields)})
        self.assertFalse(result["isError"], data)
        self.assertEqual(count["count"], 6)
        self.assertEqual(data["row_count"], 6)
        self.assertEqual(data["rows"][0]["customer_name"], "Device Customer")
        self.assertEqual(data["rows"][0]["cabinet_name"], "Device Rack")
        self.assertEqual(data["rows"][0]["type"], 0)
        self.assertEqual(data["rows"][0]["u_height"], 2)
        self.assertEqual(data["rows"][0]["attributes"], {"cpu": "test CPU"})
        result, error = await self.call("finwork_query", {"dataset": "devices", "columns": ["unknown_column"]})
        self.assertTrue(result["isError"])
        self.assertIn("这不是权限错误", error["error"])

    async def test_reject_raw_sql_relations_and_injection(self):
        cases = [
            {"dataset": "user"},
            {"dataset": "tickets", "sql": "DELETE FROM ticket"},
            {"dataset": "tickets", "columns": ["user__password"]},
            {"dataset": "tickets", "order_by": ["id; DROP TABLE ticket"]},
            {"dataset": "tickets", "filters": [{"field": "user_id__in", "value": [1]}]},
            {"dataset": "tickets", "filters": [{"field": "id", "operator": "in", "value": 1}]},
            {"dataset": "tickets", "limit": 1000},
            {"dataset": "tickets", "current_user": {"is_superuser": True}},
        ]
        for arguments in cases:
            with self.subTest(arguments=arguments):
                result, _ = await self.call("finwork_query", arguments)
                self.assertTrue(result["isError"])
        result, data = await self.call(
            "finwork_query",
            {"dataset": "tickets", "filters": [{"field": "title", "value": "' OR 1=1; DELETE FROM ticket; --"}]},
        )
        self.assertFalse(result["isError"])
        self.assertEqual(data["rows"], [])
        self.assertEqual(await Ticket.all().count(), 2)

    async def test_limits_disabled_tools_and_error_redaction(self):
        with patch.object(settings, "FW_ASSISTANT_DB_QUERY_LIMIT", 1):
            _, data = await self.call("finwork_query", {"dataset": "tickets", "limit": 100}, self.admin)
        self.assertEqual(data["row_count"], 1)
        self.assertTrue(data["has_more"])
        self.assertEqual(data["next_offset"], 1)
        with patch.object(settings, "FW_ASSISTANT_DB_QUERY_ENABLED", False):
            self.assertEqual(await mcp.DatabaseMcpClient(self.user).list_tools(), [])
            result, _ = await self.call("finwork_query", {"dataset": "tickets"})
            self.assertTrue(result["isError"])
        with patch.object(mcp, "query_database", AsyncMock(side_effect=RuntimeError("secret connection string"))):
            result, data = await self.call("finwork_query", {"dataset": "tickets"})
        self.assertTrue(result["isError"])
        self.assertNotIn("secret", str(data))
        with patch.object(mcp, "query_database", AsyncMock(side_effect=TimeoutError)):
            result, data = await self.call("finwork_query", {"dataset": "tickets"})
        self.assertTrue(result["isError"])
        self.assertIn("超时", data["error"])

    async def test_project_scope_always_includes_owner_and_shared(self):
        scope = mcp.project_scope(self.user)

        def filters(q):
            return [q.filters] + [item for child in q.children for item in filters(child)]

        parts = filters(scope)
        self.assertIn({"owner__in": [self.user.username, self.user.email]}, parts)
        self.assertIn({"shared_users__contains": [self.user.username]}, parts)
        # Superuser access follows the existing project list's owner/shared scope too.
        self.assertTrue(mcp.project_scope(self.admin).children)

    async def test_chat_drives_mcp_and_returns_tool_results(self):
        def tool(name, arguments, call_id):
            return {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "tool_calls": [
                                {
                                    "id": call_id,
                                    "type": "function",
                                    "function": {"name": name, "arguments": json.dumps(arguments)},
                                }
                            ],
                        }
                    }
                ]
            }

        replies = [
            tool("finwork_schema", {}, "schema-1"),
            tool("finwork_query", {"dataset": "tickets", "mode": "count"}, "query-1"),
            {"choices": [{"message": {"content": "你有1个工单"}}]},
        ]
        recorded = []

        async def fake_ai(*args):
            recorded.append(json.loads(json.dumps(args[3])))
            return replies.pop(0)

        with patch.object(fw_assistant, "_call_ai", side_effect=fake_ai):
            result, db = await fw_assistant._chat_with_mcp(
                "https://example.invalid",
                "unused",
                "qwen-plus",
                fw_assistant.FwAssistantChatIn(message="我的工单数"),
                self.user,
                {"id": self.user.id},
            )
        self.assertEqual(fw_assistant._first_choice_content(result), "你有1个工单")
        tool_message = recorded[-1][-1]
        self.assertEqual(tool_message["tool_call_id"], "query-1")
        self.assertEqual(json.loads(tool_message["content"])["count"], 1)
        self.assertEqual(db["queries"][0]["result"]["count"], 1)

    async def test_chat_bad_tool_arguments_and_round_limit(self):
        response = {
            "choices": [
                {
                    "message": {
                        "tool_calls": [
                            {
                                "id": "call",
                                "type": "function",
                                "function": {"name": "finwork_query", "arguments": "invalid"},
                            }
                        ]
                    }
                }
            ]
        }
        with patch.object(fw_assistant, "_call_ai", AsyncMock(return_value=response)) as ai:
            with self.assertRaisesRegex(RuntimeError, "超出限制"):
                await fw_assistant._chat_with_mcp(
                    "unused", "unused", "qwen-plus", fw_assistant.FwAssistantChatIn(message="test"), self.user, {}
                )
        self.assertEqual(ai.call_count, 5)
        self.assertEqual(ai.call_args.args[-1], "none")
        self.assertIn("参数格式错误", ai.call_args.args[3][-1]["content"])

    async def test_audit_omits_private_bodies_and_chat_without_queries(self):
        middleware = HttpAuditLogMiddleware(self.app, methods=["POST"], exclude_paths=[])
        for path in ("/api/v1/fw-assistant/chat", "/api/v1/fw-assistant/mcp"):
            request = Request({"type": "http", "method": "POST", "path": path, "headers": []})
            self.assertEqual(await middleware.get_request_args(request), {})
            self.assertIsNone(await middleware.get_response_body(request, Response("private")))
        reply = {"choices": [{"message": {"content": "Hello"}}]}
        with (
            patch.object(settings, "FW_ASSISTANT_DB_QUERY_ENABLED", False),
            patch.object(fw_assistant, "_call_ai", AsyncMock(return_value=reply)) as ai,
            patch.object(mcp, "query_database", AsyncMock()) as query,
        ):
            result, db = await fw_assistant._chat_with_mcp(
                "unused", "unused", "qwen-plus", fw_assistant.FwAssistantChatIn(message="Hello"), self.user, {}
            )
        self.assertFalse(db["enabled"])
        self.assertEqual(ai.call_args.args[5], [])
        query.assert_not_awaited()
        self.assertEqual(fw_assistant._first_choice_content(result), "Hello")


if __name__ == "__main__":
    unittest.main()
