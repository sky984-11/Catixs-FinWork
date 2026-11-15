import json
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from app.api.v1 import fw_assistant
from app.services import fw_grafana_mcp as mcp
from app.settings import settings


class GrafanaTests(unittest.IsolatedAsyncioTestCase):
    async def test_assistant_dispatches_grafana_and_records_source(self):
        def response(name, args):
            return {
                "choices": [
                    {
                        "message": {
                            "tool_calls": [
                                {
                                    "id": name,
                                    "type": "function",
                                    "function": {"name": name, "arguments": json.dumps(args)},
                                }
                            ]
                        }
                    }
                ]
            }

        db = SimpleNamespace(initialize=AsyncMock(), list_tools=AsyncMock(return_value=[]), call_tool=AsyncMock())
        with (
            patch.object(fw_assistant, "DatabaseMcpClient", return_value=db),
            patch.object(
                fw_assistant,
                "_call_ai",
                AsyncMock(
                    side_effect=[
                        response("grafana_tools", {}),
                        response("grafana_read", {"name": "list_datasources", "arguments": {}}),
                        {"choices": [{"message": {"content": "Grafana query completed"}}]},
                    ]
                ),
            ) as ai,
            patch.object(settings, "GRAFANA_API_TOKEN", "test-token"),
            patch.object(
                mcp,
                "exchange",
                side_effect=[
                    {"tools": [{"name": "list_datasources", "inputSchema": {"type": "object"}}]},
                    {"content": [{"text": "[]"}]},
                ],
            ),
        ):
            result, context = await fw_assistant._chat_with_mcp(
                "https://example.invalid",
                "key",
                "model",
                fw_assistant.FwAssistantChatIn(message="Grafana datasources"),
                self.user,
                {},
            )
        self.assertEqual(context["queries"][0]["tool"], "grafana_read")
        self.assertEqual(context["queries"][0]["result"]["source"], "Grafana MCP")
        self.assertEqual(ai.await_count, 3)
        db.call_tool.assert_not_awaited()

    def setUp(self):
        self.user = SimpleNamespace(is_active=True, is_superuser=True)
        self.client = mcp.GrafanaMcpClient(self.user)

    async def test_inactive_and_unauthorized_never_start_server(self):
        self.user.is_active = False
        with patch.object(mcp, "exchange") as exchange:
            self.assertEqual(await self.client.list_tools(), [])
            self.assertTrue((await self.client.call_tool("grafana_tools", {}))["isError"])
        exchange.assert_not_called()
        self.user.is_active = True
        with patch.object(mcp, "permitted", AsyncMock(return_value=False)), patch.object(mcp, "exchange") as exchange:
            self.assertTrue((await self.client.call_tool("grafana_tools", {}))["isError"])
        exchange.assert_not_called()

    async def test_write_tools_blocked_and_discovery_filtered(self):
        with (
            patch.object(settings, "GRAFANA_API_TOKEN", "test-token"),
            patch.object(
                mcp, "exchange", return_value={"tools": [{"name": "list_datasources"}, {"name": "update_dashboard"}]}
            ) as exchange,
        ):
            rejected = await self.client.call_tool("grafana_read", {"name": "update_dashboard", "arguments": {}})
            self.assertTrue(rejected["isError"])
            exchange.assert_not_called()
            result = await self.client.call_tool("grafana_tools", {})
            self.assertNotIn("update_dashboard", str(result))
            self.assertIn("list_datasources", str(result))

    async def test_result_limit_secret_redaction_and_upstream_failure(self):
        with (
            patch.object(settings, "GRAFANA_API_TOKEN", "test-token"),
            patch.object(mcp, "exchange", return_value={"content": [{"text": "test-token" + "x" * 21000}]}) as exchange,
        ):
            result = await self.client.call_tool("grafana_read", {"name": "list_datasources", "arguments": {}})
            data = json.loads(result["content"][0]["text"])
            self.assertTrue(data["truncated"])
            self.assertNotIn("test-token", str(result))
            exchange.side_effect = TimeoutError("private details")
            failed = await self.client.call_tool("grafana_tools", {})
            self.assertTrue(failed["isError"])
            self.assertNotIn("private details", str(failed))

    async def test_disabled(self):
        with patch.object(settings, "FW_ASSISTANT_GRAFANA_ENABLED", False), patch.object(mcp, "exchange") as exchange:
            self.assertEqual(await self.client.list_tools(), [])
            self.assertTrue((await self.client.call_tool("grafana_tools", {}))["isError"])
        exchange.assert_not_called()
