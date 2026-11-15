"""Bounded read-only bridge to the official Grafana MCP stdio server."""

import asyncio
import json
import os
import queue
import shutil
import signal
import subprocess
import threading
import time

from fastapi import HTTPException, Request

from app.core.dependency import PermissionControl
from app.services.fw_database_mcp import tool_result
from app.settings import settings

ALLOWED = {
    "list_datasources",
    "get_datasource_by_uid",
    "search_dashboards",
    "get_dashboard_summary",
    "get_dashboard_property",
    "get_dashboard_panel_queries",
    "query_prometheus",
    "list_prometheus_metric_names",
    "list_prometheus_label_names",
    "list_prometheus_label_values",
    "query_loki_logs",
    "list_loki_label_names",
    "list_loki_label_values",
}
PERMISSION = "/api/v1/pve/grafana/proxy/{path}"


async def permitted(user):
    if not user or not user.is_active:
        return False
    try:
        await PermissionControl.has_permission(
            Request({"type": "http", "method": "GET", "path": PERMISSION, "headers": []}), user
        )
        return True
    except HTTPException:
        return False


def exchange(method, params):
    """Thread-owned subprocess: bounded IO, no shell, no credentials in arguments/logs."""
    command = shutil.which(settings.GRAFANA_MCP_COMMAND)
    if not command:
        raise RuntimeError("Grafana MCP 启动程序未安装")
    env = dict(os.environ)
    env.update(
        GRAFANA_URL=settings.GRAFANA_URL, GRAFANA_SERVICE_ACCOUNT_TOKEN=settings.GRAFANA_API_TOKEN, DO_NOT_TRACK="1"
    )
    process = subprocess.Popen(
        [command, "mcp-grafana==2.2.0", "--disable-write", "--usage-stats=disabled"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        env=env,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        start_new_session=os.name != "nt",
    )
    responses = queue.Queue(maxsize=16)
    stopped = threading.Event()

    def read():
        try:
            while not stopped.is_set():
                line = process.stdout.readline(4 * 1024 * 1024 + 1)
                if not line or len(line) > 4 * 1024 * 1024:
                    return
                responses.put_nowait(json.loads(line))
        except (ValueError, OSError, queue.Full):
            return

    reader = threading.Thread(target=read, daemon=True)
    reader.start()
    deadline = time.monotonic() + 20

    def rpc(ident, name, arguments):
        message = {"jsonrpc": "2.0", "method": name, "params": arguments}
        if ident is not None:
            message["id"] = ident
        process.stdin.write((json.dumps(message) + "\n").encode())
        process.stdin.flush()
        if ident is None:
            return None
        while True:
            reply = responses.get(timeout=max(0.01, deadline - time.monotonic()))
            if reply.get("id") == ident:
                if "error" in reply or "result" not in reply:
                    raise RuntimeError("Grafana MCP 请求失败")
                return reply["result"]
            if time.monotonic() >= deadline:
                raise TimeoutError()

    try:
        init = rpc(
            1,
            "initialize",
            {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "finwork", "version": "1"}},
        )
        if init.get("protocolVersion") != "2025-06-18":
            raise RuntimeError("Grafana MCP 协议版本不兼容")
        rpc(None, "notifications/initialized", {})
        return rpc(2, method, params)
    finally:
        stopped.set()
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW,
                timeout=5,
            )
        else:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        process.wait(timeout=5)
        reader.join(timeout=1)
        process.stdin.close()
        process.stdout.close()


class GrafanaMcpClient:
    def __init__(self, user):
        self.user = user

    async def list_tools(self):
        if not settings.FW_ASSISTANT_GRAFANA_ENABLED or not await permitted(self.user):
            return []
        return [
            {
                "name": "grafana_tools",
                "description": "发现 Grafana 只读工具及其参数定义。查询仪表盘或监控指标前先调用。",
                "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
            },
            {
                "name": "grafana_read",
                "description": "调用 grafana_tools 返回的只读工具，必须按返回的 inputSchema 传 arguments。只支持明确列出的工具，不支持任意 HTTP、SQL 或修改操作。",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "enum": sorted(ALLOWED)},
                        "arguments": {"type": "object"},
                    },
                    "required": ["name", "arguments"],
                    "additionalProperties": False,
                },
            },
        ]

    async def call_tool(self, name, arguments):
        if not settings.FW_ASSISTANT_GRAFANA_ENABLED or not await permitted(self.user):
            return tool_result({"error": "Grafana 查询未启用或当前用户无 Grafana 读取权限"}, True)
        if not settings.GRAFANA_API_TOKEN:
            return tool_result({"error": "Grafana 凭据未配置"}, True)
        if name == "grafana_tools" and not arguments:
            method, params = "tools/list", {}
        elif (
            name == "grafana_read"
            and set(arguments) == {"name", "arguments"}
            and arguments.get("name") in ALLOWED
            and isinstance(arguments.get("arguments"), dict)
        ):
            method, params = "tools/call", arguments
        else:
            return tool_result({"error": "未知工具或参数错误"}, True)
        try:
            result = await asyncio.to_thread(exchange, method, params)
            if method == "tools/list":

                def compact(value):
                    if isinstance(value, dict):
                        return {k: str(v)[:160] if k == "description" else compact(v) for k, v in value.items()}
                    if isinstance(value, list):
                        return [compact(v) for v in value]
                    return value

                result = {
                    "tools": [
                        {
                            "name": t["name"],
                            "description": t.get("description", "")[:250],
                            "inputSchema": compact(t.get("inputSchema", {})),
                        }
                        for t in result.get("tools", [])
                        if t["name"] in ALLOWED
                    ]
                }
            if result.get("isError"):
                return tool_result({"error": "Grafana 查询失败，请检查数据源、参数及服务账号权限"}, True)
            encoded = json.dumps(result, ensure_ascii=False).replace(settings.GRAFANA_API_TOKEN, "[redacted]")
            truncated = len(encoded) > 20000
            return tool_result({"source": "Grafana MCP", "truncated": truncated, "result": encoded[:20000]}, False)
        except Exception:
            return tool_result({"error": "Grafana MCP 连接或查询失败，请检查启动程序、网络和凭据"}, True)
