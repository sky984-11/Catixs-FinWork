"""Read-only FinWork MCP tools, shared by HTTP and the in-process assistant client."""

import asyncio
import json
from dataclasses import dataclass
from typing import Any, Literal

from fastapi import HTTPException, Request
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator
from tortoise.expressions import F, Q

from app.core.dependency import PermissionControl
from app.log import logger
from app.models.asset import AssetCabinet
from app.models.customer_center import CrmCustomer, CrmCustomerBill, CrmCustomerContract
from app.models.project import CustomerProject, CustomerProjectTask
from app.models.ticket import Ticket
from app.services.fw_ops_catalog import OPS_DATASETS
from app.services.fw_ops_mcp import available_actions, definition, read_operations, sanitize
from app.settings import settings

PROTOCOL_VERSION = "2025-06-18"


@dataclass(frozen=True)
class Dataset:
    model: Any
    permission: str | None
    fields: tuple[str, ...]


# Registered business datasets retain module/row permissions; fields come from ORM metadata at query time.
DATASETS = {
    "cabinets": Dataset(
        AssetCabinet,
        "/api/v1/asset/cabinet/list",
        (
            "id",
            "name",
            "code",
            "location_id",
            "location_name",
            "region_name",
            "customer_id",
            "customer_name",
            "row",
            "column",
            "capacity_u",
            "rental_start_u",
            "rental_end_u",
            "width_mm",
            "depth_mm",
            "power_allocation_kw",
            "power_overage_rate",
            "pdu_spec",
            "power_socket_spec",
            "rack_tray",
            "pdu_socket_types",
            "remark",
            "status",
            "created_at",
            "updated_at",
        ),
    ),
    "projects": Dataset(
        CustomerProject,
        "/api/v1/project/list",
        (
            "id",
            "name",
            "code",
            "status",
            "priority",
            "health",
            "owner",
            "crm_customer_id",
            "vendor_id",
            "project_type",
            "contract_no",
            "start_date",
            "due_date",
            "progress",
            "budget_amount",
            "budget_currency",
        ),
    ),
    "project_tasks": Dataset(
        CustomerProjectTask,
        "/api/v1/project/list",
        ("id", "project_id", "title", "assignee", "due_date", "is_done", "remark"),
    ),
    "tickets": Dataset(
        Ticket,
        None,  # The existing ticket list uses login + row scope, not menu API permissions.
        (
            "id",
            "ticket_no",
            "title",
            "status",
            "type",
            "user_id",
            "assignee_id",
            "location",
            "start_time",
            "end_time",
            "created_at",
            "updated_at",
        ),
    ),
    "customers": Dataset(
        CrmCustomer,
        "/api/v1/customer-center/customers",
        (
            "id",
            "customer_code",
            "name",
            "legal_name",
            "alias",
            "signing_entity_id",
            "customer_level",
            "lifecycle",
            "sales_owner",
            "region",
            "status",
        ),
    ),
    "contracts": Dataset(
        CrmCustomerContract,
        "/api/v1/customer-center/contracts",
        (
            "id",
            "customer_id",
            "signing_entity_id",
            "contract_no",
            "name",
            "status",
            "effective_date",
            "expiry_date",
            "amount",
            "currency",
        ),
    ),
    "bills": Dataset(
        CrmCustomerBill,
        "/api/v1/customer-center/bills",
        (
            "id",
            "customer_id",
            "bill_no",
            "title",
            "status",
            "amount",
            "currency",
            "bill_date",
            "due_date",
            "is_settled",
            "business_closed",
        ),
    ),
}
DATASETS.update({name: Dataset(*definition) for name, definition in OPS_DATASETS.items()})
DATASETS["tickets"] = Dataset(Ticket, None, (*DATASETS["tickets"].fields, "desc", "completion_note"))

# Display aliases are fixed server-side; all concrete fields of a registered model are readable.
FIELD_ALIASES = {
    "cabinets": {
        "location_name": "location__name",
        "region_name": "location__region__name",
        "customer_name": "customer__name",
    },
    "devices": {
        "cabinet_name": "cabinet__name",
        "location_name": "location__name",
        "region_name": "region__name",
        "customer_name": "customer__name",
    },
    "locations": {"region_name": "region__name"},
    "inventory": {"location_name": "location__name", "region_name": "region__name"},
    "device_models": {"brand_name": "brand__name"},
    "dhcp_pools": {"location_name": "location__name"},
    "dhcp_leases": {"pool_name": "pool__name"},
    "cloud_bindings": {"region_name": "region__name", "location_name": "location__name", "device_name": "device__name"},
}
ALIAS_DESCRIPTIONS = {
    "location_name": "所属机房/位置名称",
    "region_name": "所属区域名称",
    "customer_name": "所属客户简称（未分配时为空）",
    "cabinet_name": "所属机柜名称",
    "brand_name": "品牌名称",
    "pool_name": "DHCP池名称",
    "device_name": "设备名称",
}


def available_fields(name: str, dataset: Dataset) -> list[str]:
    return list(dict.fromkeys([*dataset.model._meta.fields_db_projection, *FIELD_ALIASES.get(name, {})]))


class ToolInput(BaseModel):
    model_config = ConfigDict(extra="forbid")


class QueryFilter(ToolInput):
    field: str = Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")
    operator: Literal["eq", "in", "contains", "gte", "lte", "isnull"] = "eq"
    value: Any

    @field_validator("value")
    @classmethod
    def bounded_value(cls, value):
        values = value if isinstance(value, list) else [value]
        if len(values) > 100 or any(
            item is not None and (type(item) not in (str, int, float, bool) or len(str(item)) > 500) for item in values
        ):
            raise ValueError("筛选值仅支持短文本、数字、布尔值或最多100项的列表")
        return value


class QueryInput(ToolInput):
    dataset: str = Field(min_length=1, max_length=64)
    columns: list[str] | None = Field(default=None, min_length=1, max_length=128)
    filters: list[QueryFilter] = Field(default_factory=list, max_length=12)
    order_by: list[str] = Field(default_factory=lambda: ["-id"], max_length=5)
    limit: int = Field(default=50, ge=1, le=100, strict=True)
    offset: int = Field(default=0, ge=0, le=10000, strict=True)
    mode: Literal["rows", "count"] = "rows"


def tool_definitions() -> list[dict]:
    return [
        definition(),
        {
            "name": "finwork_schema",
            "description": "获取当前用户可查询的数据集、字段及字段含义。查询前先调用此工具，不猜测字段。",
            "inputSchema": ToolInput.model_json_schema(),
            "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False},
        },
        {
            "name": "finwork_query",
            "description": (
                "只读查询授权业务数据的全部本表字段。filters 按 AND 组合，支持 eq/in/contains/gte/lte/isnull；"
                "mode=count 返回满足条件的总数，rows 返回分页记录。不能执行 SQL、修改数据或跨关系取字段。"
                "权限和行范围由服务端强制限制；分页结果不能当作全部数据。"
            ),
            "inputSchema": QueryInput.model_json_schema(),
            "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False},
        },
    ]


async def authorize(dataset: Dataset, user) -> None:
    if not user or not user.is_active:
        raise ValueError("当前用户不可用")
    if dataset.permission:
        request = Request({"type": "http", "method": "GET", "path": dataset.permission, "headers": []})
        await PermissionControl.has_permission(request, user)


def project_scope(user) -> Q:
    from app.api.v1.projects.projects import get_project_owner_names

    names = get_project_owner_names(user)
    if not names:
        return Q(id=0)
    scope = Q(owner__in=names)
    for name in names:
        scope |= Q(shared_users__contains=[name])
    return scope


async def scoped_query(name: str, dataset: Dataset, user):
    query = dataset.model.all()
    if name in FIELD_ALIASES:
        query = query.annotate(**{alias: F(path) for alias, path in FIELD_ALIASES[name].items()})
    if name == "projects":
        query = query.filter(project_scope(user))
    elif name == "project_tasks":
        from tortoise.expressions import Subquery

        query = query.filter(project_id__in=Subquery(CustomerProject.filter(project_scope(user)).values("id")))
    elif name in {"tickets", "ticket_replies"}:
        from app.api.v1.tickets.tickets import can_view_all_tickets
        from tortoise.expressions import Subquery

        if not await can_view_all_tickets(user):
            if name == "tickets":
                query = query.filter(user_id=user.id)
            else:
                query = query.filter(ticket_id__in=Subquery(Ticket.filter(user_id=user.id).values("id")))
    return query


async def schema_for_user(user) -> dict:
    datasets = {}
    for name, dataset in DATASETS.items():
        try:
            await authorize(dataset, user)
        except HTTPException:
            continue
        datasets[name] = {
            field: getattr(dataset.model._meta.fields_map.get(field), "description", None) or field
            for field in available_fields(name, dataset)
        }
        datasets[name].update({alias: ALIAS_DESCRIPTIONS[alias] for alias in FIELD_ALIASES.get(name, {})})
        if name == "devices":
            datasets[name]["type"] = "设备类型：0服务器，1交换机，2路由器，3防火墙，4PDU，5配件，99其他"
    return {
        "datasets": datasets,
        "operations": await available_actions(user),
        "max_rows": max(1, min(settings.FW_ASSISTANT_DB_QUERY_LIMIT, 100)),
    }


async def query_database(arguments: dict, user) -> dict:
    args = QueryInput.model_validate(arguments)
    dataset = DATASETS.get(args.dataset)
    if dataset is None:
        raise ValueError("未开放的数据集，请先调用 finwork_schema")
    await authorize(dataset, user)
    fields = available_fields(args.dataset, dataset)
    columns = args.columns or fields
    names = columns + [item.field for item in args.filters] + [item.removeprefix("-") for item in args.order_by]
    unknown_fields = sorted(set(names) - set(fields))
    if unknown_fields:
        raise ValueError(
            f"字段不存在或不是本表字段：{', '.join(unknown_fields)}。请按 finwork_schema 返回的字段查询；这不是权限错误。"
        )
    query = await scoped_query(args.dataset, dataset, user)
    for item in args.filters:
        if item.operator == "in":
            if not isinstance(item.value, list):
                raise ValueError("in 筛选值必须为列表")
        elif isinstance(item.value, list):
            raise ValueError("该操作不接受列表")
        if item.operator == "isnull" and type(item.value) is not bool:
            raise ValueError("isnull 筛选值必须为布尔值")
        if item.operator == "contains" and not isinstance(item.value, str):
            raise ValueError("contains 筛选值必须为文本")
        suffix = "" if item.operator == "eq" else f"__{item.operator}"
        query = query.filter(**{item.field + suffix: item.value})
    if args.mode == "count":
        return {"dataset": args.dataset, "count": await query.count(), "rows": []}
    limit = min(args.limit, max(1, min(settings.FW_ASSISTANT_DB_QUERY_LIMIT, 100)))
    rows = jsonable_encoder(await query.order_by(*args.order_by).offset(args.offset).limit(limit + 1).values(*columns))
    has_more = len(rows) > limit
    rows = rows[:limit]
    # Bound the entire model context, not only the number of rows.
    result_rows, size, truncated = [], 0, False
    for row in rows:
        clipped = sanitize(row)
        truncated |= clipped != row
        row_size = len(json.dumps(clipped, ensure_ascii=False).encode("utf-8"))
        if size + row_size > 30000:
            if not result_rows:
                raise ValueError("单条结果过大，请使用columns减少返回字段")
            has_more = True
            break
        result_rows.append(clipped)
        size += row_size
    return {
        "dataset": args.dataset,
        "rows": result_rows,
        "row_count": len(result_rows),
        "offset": args.offset,
        "has_more": has_more,
        "truncated": truncated,
        "next_offset": args.offset + len(result_rows) if has_more else None,
    }


def tool_result(data: dict, error: bool = False) -> dict:
    return {"content": [{"type": "text", "text": json.dumps(data, ensure_ascii=False)}], "isError": error}


def rpc_error(request_id, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


async def dispatch(message: Any, user) -> dict | None:
    """Stateless JSON-RPC MCP endpoint; the caller supplies an authenticated user, never model arguments."""
    if not isinstance(message, dict) or message.get("jsonrpc") != "2.0" or not isinstance(message.get("method"), str):
        return rpc_error(None, -32600, "Invalid Request")
    request_id = message.get("id")
    if "id" in message and (type(request_id) not in (str, int)):
        return rpc_error(None, -32600, "Invalid request id")
    method = message["method"]
    if "id" not in message:
        return None  # Notifications must never receive a JSON-RPC response or execute a tool.
    params = message.get("params", {})
    if not isinstance(params, dict):
        return rpc_error(request_id, -32602, "Invalid params")
    if method == "initialize":
        if not isinstance(params.get("protocolVersion"), str) or not isinstance(params.get("capabilities"), dict):
            return rpc_error(request_id, -32602, "Missing protocolVersion or capabilities")
        if not isinstance(params.get("clientInfo"), dict):
            return rpc_error(request_id, -32602, "Missing clientInfo")
        result = {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": "finwork-database", "version": "1.0.0"},
        }
    elif method == "ping":
        result = {}
    elif method == "tools/list":
        if params.get("cursor"):
            return rpc_error(request_id, -32602, "Invalid cursor")
        result = {"tools": tool_definitions() if settings.FW_ASSISTANT_DB_QUERY_ENABLED else []}
    elif method == "tools/call":
        name, arguments = params.get("name"), params.get("arguments", {})
        if name not in {"finwork_schema", "finwork_query", "finwork_ops_read"} or not isinstance(arguments, dict):
            return rpc_error(request_id, -32602, "Unknown tool or invalid arguments")
        try:
            if not settings.FW_ASSISTANT_DB_QUERY_ENABLED:
                raise ValueError("数据库查询未启用")
            async with asyncio.timeout(10):
                if name == "finwork_schema":
                    ToolInput.model_validate(arguments)
                    data = await schema_for_user(user)
                elif name == "finwork_ops_read":
                    data = await read_operations(arguments, user)
                else:
                    data = await query_database(arguments, user)
            result = tool_result(data)
        except ValidationError:
            result = tool_result({"error": "工具参数校验失败，请按 inputSchema 提供参数"}, True)
        except HTTPException:
            result = tool_result({"error": "无权限查询该业务数据"}, True)
        except ValueError as exc:
            result = tool_result({"error": str(exc)}, True)
        except TimeoutError:
            result = tool_result({"error": "数据库查询超时，请缩小查询范围"}, True)
        except Exception as exc:
            logger.warning("FW MCP tool failed: tool={} type={}", name, type(exc).__name__)
            message = (
                "运维数据读取失败，请检查数据源连接后重试"
                if name == "finwork_ops_read"
                else "数据库查询失败，请检查字段和值类型后重试"
            )
            result = tool_result({"error": message}, True)
    else:
        return rpc_error(request_id, -32601, "Method not found")
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


class DatabaseMcpClient:
    """Request-scoped MCP client using an in-process JSON-RPC transport (no credentials sent to the LLM)."""

    def __init__(self, user):
        self.user = user
        self.request_id = 0

    async def request(self, method: str, params: dict | None = None) -> dict:
        self.request_id += 1
        response = await dispatch(
            {"jsonrpc": "2.0", "id": self.request_id, "method": method, "params": params or {}}, self.user
        )
        if "error" in response:
            raise ValueError(response["error"]["message"])
        return response["result"]

    async def initialize(self):
        await self.request(
            "initialize",
            {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "fw-assistant", "version": "1.0.0"},
            },
        )
        await dispatch({"jsonrpc": "2.0", "method": "notifications/initialized"}, self.user)

    async def list_tools(self) -> list[dict]:
        return (await self.request("tools/list"))["tools"]

    async def call_tool(self, name: str, arguments: dict) -> dict:
        return await self.request("tools/call", {"name": name, "arguments": arguments})
