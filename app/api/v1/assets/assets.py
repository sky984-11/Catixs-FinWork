import csv
import asyncio
import ipaddress
import io
import json
import os
import socket
import ssl
import urllib.error
import urllib.request
import uuid
from copy import deepcopy
from datetime import date, datetime
from urllib.parse import urlencode

import httpx
import websockets
from fastapi import APIRouter, File, HTTPException, Query, UploadFile, WebSocket
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from starlette.websockets import WebSocketDisconnect
from tortoise.expressions import Q
from tortoise.functions import Count
from tortoise.transactions import in_transaction

from app.core.dependency import AuthControl
from app.controllers.asset import (
    asset_cabinet_controller,
    asset_device_brand_controller,
    asset_device_controller,
    asset_device_model_controller,
    asset_inventory_category_controller,
    asset_inventory_controller,
    asset_location_controller,
    asset_region_controller,
)
from app.models.asset import (
    AssetCabinet,
    AssetDevice,
    AssetDeviceBrand,
    AssetDeviceModel,
    AssetInventory,
    AssetInventoryCategory,
    AssetInventorySaleItem,
    AssetInventorySaleOrder,
    AssetInventoryStockFlow,
    AssetLocation,
    AssetRegion,
)
from app.core.ctx import CTX_USER_ID
from app.log import logger
from app.models.admin import User
from app.schemas.assets import (
    AssetCabinetCreate,
    AssetCabinetUpdate,
    AssetDeviceBrandCreate,
    AssetDeviceCreate,
    AssetDeviceModelCreate,
    AssetDeviceRedfishProbe,
    AssetDeviceUpdate,
    AssetInventoryCategoryCreate,
    AssetInventoryCategoryUpdate,
    AssetInventoryCreate,
    AssetInventorySaleCancel,
    AssetInventorySaleCreate,
    AssetInventoryUpdate,
    AssetLocationCreate,
    AssetLocationUpdate,
    AssetRegionCreate,
    AssetRegionUpdate,
)
from app.schemas.base import Success, SuccessExtra

router = APIRouter()
ws_router = APIRouter()

INVENTORY_FEISHU_WEBHOOK = os.getenv(
    "INVENTORY_FEISHU_WEBHOOK",
    "https://open.feishu.cn/open-apis/bot/v2/hook/4c3e89a6-35dd-4de3-b763-e1049449e5d4",
)

SENSITIVE_DEVICE_ATTRIBUTE_KEYS = {"IPMI密码", "ipmi_password", "vnc_password", "VNC密码", "snmp团体名"}
MASKED_DEVICE_SECRET = "******"
DEVICE_SECRET_VIEW_ROLE_NAMES = {"admin", "noc"}
DEVICE_VNC_SESSIONS: dict[str, dict] = {}
DEVICE_VNC_SESSION_TTL = 120
DEVICE_VNC_DEFAULT_PORT = 5901
DEVICE_VNC_DEFAULT_PASSWORD = "vnc@3202"


class AssetDeviceVncRequest(BaseModel):
    device_id: int
    node_name: str | None = None


class AssetDevicePowerRequest(BaseModel):
    device_id: int
    action: str
    node_name: str | None = None


class AssetDeviceIpmiLogRequest(BaseModel):
    device_id: int
    node_name: str | None = None
    limit: int = 50


def normalize_redfish_host(value: str) -> str:
    host = str(value or "").strip().replace("https://", "").replace("http://", "").split("/", 1)[0]
    if ":" in host and not host.count(":") > 1:
        host = host.split(":", 1)[0]
    try:
        ipaddress.ip_address(host)
    except ValueError as exc:
        raise ValueError("IPMI地址必须是有效的IP地址") from exc
    return host


def redfish_path(value: str | None) -> str:
    path = str(value or "").strip()
    if not path:
        return ""
    if path.startswith("http://") or path.startswith("https://"):
        marker = "/redfish/"
        index = path.find(marker)
        return path[index:] if index >= 0 else ""
    return path


async def redfish_get(client: httpx.AsyncClient, path: str) -> dict:
    if not path:
        return {}
    response = await client.get(path)
    response.raise_for_status()
    data = response.json()
    return data if isinstance(data, dict) else {}


async def redfish_post(client: httpx.AsyncClient, path: str, data: dict) -> dict:
    if not path:
        return {}
    response = await client.post(path, json=data)
    response.raise_for_status()
    if not response.content:
        return {}
    data = response.json()
    return data if isinstance(data, dict) else {}


def redfish_link(data: dict, key: str) -> str:
    value = data.get(key)
    if isinstance(value, dict):
        return redfish_path(value.get("@odata.id") or value.get("href"))
    return ""


def redfish_members(data: dict) -> list[str]:
    members = data.get("Members") if isinstance(data, dict) else []
    if not isinstance(members, list):
        return []
    return [redfish_path(item.get("@odata.id")) for item in members if isinstance(item, dict) and item.get("@odata.id")]


def format_memory_mib(value) -> str:
    try:
        mib = float(value or 0)
    except (TypeError, ValueError):
        return ""
    if mib <= 0:
        return ""
    gib = mib / 1024
    return f"{gib:g} GiB" if gib < 1024 else f"{gib / 1024:g} TiB"


def redfish_cpu_summary(processors: list[dict]) -> tuple[str, str, str]:
    models = []
    cores = 0
    enabled = 0
    for item in processors:
        model = str(item.get("Model") or item.get("ProcessorId", {}).get("EffectiveFamily") or "").strip()
        if model and model not in models:
            models.append(model)
        try:
            cores += int(item.get("TotalCores") or 0)
        except (TypeError, ValueError):
            pass
        status = item.get("Status") if isinstance(item.get("Status"), dict) else {}
        state = str(status.get("State") or status.get("Health") or "").lower()
        if state not in {"absent", "disabled"}:
            enabled += 1
    return str(enabled or len(processors) or ""), " / ".join(models), str(cores or "")


def redfish_memory_summary(memory_modules: list[dict], system: dict) -> tuple[str, str]:
    total_gib = system.get("MemorySummary", {}).get("TotalSystemMemoryGiB")
    try:
        total_gib_number = float(total_gib or 0)
    except (TypeError, ValueError):
        total_gib_number = 0
    if total_gib_number:
        return f"{total_gib_number:g} GiB", str(len(memory_modules) or "")
    capacity_mib = 0
    count = 0
    for item in memory_modules:
        try:
            capacity = float(item.get("CapacityMiB") or 0)
        except (TypeError, ValueError):
            capacity = 0
        if capacity > 0:
            capacity_mib += capacity
            count += 1
    return format_memory_mib(capacity_mib), str(count or len(memory_modules) or "")


def redfish_attribute_rows(system: dict, processors: list[dict], memory_modules: list[dict], nics: list[dict]) -> dict:
    cpu_count, cpu_model, cpu_cores = redfish_cpu_summary(processors)
    memory_total, memory_count = redfish_memory_summary(memory_modules, system)
    macs = [str(item.get("MACAddress") or "").strip() for item in nics if item.get("MACAddress")]
    rows = {
        "CPU型号": cpu_model,
        "CPU数量": cpu_count,
        "网卡MAC": " / ".join(macs[:8]),
        "BIOS版本": system.get("BiosVersion") or "",
        "CPU核心数": cpu_cores,
        "内存容量": memory_total,
        "电源状态": system.get("PowerState") or "",
        "内存条数量": memory_count,
        "Redfish更新时间": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    return {key: str(value) for key, value in rows.items() if value not in (None, "")}


async def collect_redfish_inventory(payload: AssetDeviceRedfishProbe) -> dict:
    host = normalize_redfish_host(payload.ipmi_host)
    auth = (payload.ipmi_user, payload.ipmi_password) if payload.ipmi_user else None
    base_url = f"https://{host}"
    timeout = httpx.Timeout(8.0, connect=4.0)
    async with httpx.AsyncClient(base_url=base_url, timeout=timeout, verify=False, trust_env=False, auth=auth) as client:
        service = await redfish_get(client, "/redfish/v1/")
        systems_path = redfish_link(service, "Systems") or "/redfish/v1/Systems"
        systems = await redfish_get(client, systems_path)
        system_paths = redfish_members(systems)
        if not system_paths:
            raise ValueError("未发现Redfish Systems资源")
        system = await redfish_get(client, system_paths[0])

        processor_paths = redfish_members(await redfish_get(client, redfish_link(system, "Processors")))
        memory_paths = redfish_members(await redfish_get(client, redfish_link(system, "Memory")))
        nic_paths = redfish_members(await redfish_get(client, redfish_link(system, "EthernetInterfaces")))
        processors, memory_modules, nics = await asyncio.gather(
            asyncio.gather(*(redfish_get(client, path) for path in processor_paths)) if processor_paths else asyncio.sleep(0, result=[]),
            asyncio.gather(*(redfish_get(client, path) for path in memory_paths)) if memory_paths else asyncio.sleep(0, result=[]),
            asyncio.gather(*(redfish_get(client, path) for path in nic_paths)) if nic_paths else asyncio.sleep(0, result=[]),
        )

    attributes = redfish_attribute_rows(system, list(processors), list(memory_modules), list(nics))
    return {
        "host": host,
        "attributes": attributes,
    }


def device_ipmi_config(device: AssetDevice, node_name: str | None = None) -> dict:
    attributes = dict(device.attributes or {})
    if node_name:
        nodes = attributes.get("nodes")
        if not isinstance(nodes, list):
            raise ValueError("设备未配置四节点信息")
        normalized_node_name = str(node_name or "").strip()
        node = next(
            (
                item
                for item in nodes
                if isinstance(item, dict) and str(item.get("name") or "").strip() == normalized_node_name
            ),
            None,
        )
        if not node:
            raise ValueError("未找到对应的四节点")
        host = first_device_attribute(node, ("ipmi_host", "ipmiHost", "IPMI地址"))
        user = first_device_attribute(node, ("ipmi_user", "ipmiUser", "IPMI用户"))
        password = first_device_attribute(node, ("ipmi_password", "ipmiPassword", "IPMI密码"))
        display_name = str(node.get("device_name") or node.get("deviceName") or normalized_node_name).strip()
    else:
        host = first_device_attribute(attributes, ("ipmi_host", "IPMI地址"))
        user = first_device_attribute(attributes, ("ipmi_user", "IPMI用户"))
        password = first_device_attribute(attributes, ("ipmi_password", "IPMI密码"))
        display_name = device.name
    if not host:
        raise ValueError("设备未配置 IPMI 地址")
    return {"host": host, "user": user, "password": password, "display_name": display_name}


def redfish_reset_types(action: str) -> list[str]:
    normalized = str(action or "").strip().lower()
    if normalized in {"on", "power_on", "start"}:
        return ["On"]
    if normalized in {"off", "power_off", "shutdown"}:
        return ["GracefulShutdown", "ForceOff"]
    if normalized in {"restart", "reboot", "reset"}:
        return ["GracefulRestart", "ForceRestart"]
    raise ValueError("不支持的电源操作")


async def redfish_system_path(client: httpx.AsyncClient) -> tuple[str, dict]:
    service = await redfish_get(client, "/redfish/v1/")
    systems_path = redfish_link(service, "Systems") or "/redfish/v1/Systems"
    systems = await redfish_get(client, systems_path)
    system_paths = redfish_members(systems)
    if not system_paths:
        raise ValueError("未发现 Redfish Systems 资源")
    system = await redfish_get(client, system_paths[0])
    return system_paths[0], system


async def redfish_collection_member_paths(client: httpx.AsyncClient, path: str) -> list[str]:
    if not path:
        return []
    try:
        data = await redfish_get(client, path)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code in {404, 405}:
            return []
        raise
    return redfish_members(data)


async def redfish_log_service_paths(client: httpx.AsyncClient) -> list[str]:
    service = await redfish_get(client, "/redfish/v1/")
    candidate_roots = []
    managers_path = redfish_link(service, "Managers") or "/redfish/v1/Managers"
    systems_path = redfish_link(service, "Systems") or "/redfish/v1/Systems"
    for collection_path in (managers_path, systems_path):
        member_paths = await redfish_collection_member_paths(client, collection_path)
        for member_path in member_paths:
            if member_path:
                candidate_roots.append(member_path)

    log_paths = []
    for root in candidate_roots:
        try:
            resource = await redfish_get(client, root)
            log_services_path = redfish_link(resource, "LogServices") or f"{root}/LogServices"
            for log_path in await redfish_collection_member_paths(client, log_services_path):
                if log_path and log_path not in log_paths:
                    log_paths.append(log_path)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code in {401, 403}:
                raise
            logger.warning("skip Redfish log service discovery root={} error={}", root, repr(exc))

    fallback_paths = [
        "/redfish/v1/Managers/1/LogServices/SEL",
        "/redfish/v1/Managers/1/LogServices/EventLog",
        "/redfish/v1/Managers/1/LogServices/Log",
        "/redfish/v1/Systems/1/LogServices/EventLog",
        "/redfish/v1/Systems/1/LogServices/SEL",
    ]
    for path in fallback_paths:
        if path not in log_paths:
            log_paths.append(path)
    return log_paths


def normalize_redfish_log_entry(entry: dict, service_name: str) -> dict:
    severity = str(entry.get("Severity") or entry.get("Health") or "").strip()
    created = str(entry.get("Created") or entry.get("Timestamp") or "").strip()
    message = str(entry.get("Message") or entry.get("Description") or entry.get("Name") or "").strip()
    return {
        "id": str(entry.get("Id") or entry.get("EntryCode") or "").strip(),
        "created": created,
        "severity": severity,
        "message": message,
        "message_id": str(entry.get("MessageId") or "").strip(),
        "entry_type": str(entry.get("EntryType") or "").strip(),
        "sensor": str(entry.get("SensorNumber") or entry.get("SensorType") or "").strip(),
        "service": service_name,
    }


async def redfish_log_entries(client: httpx.AsyncClient, log_service_path: str, limit: int) -> list[dict]:
    try:
        service = await redfish_get(client, log_service_path)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code in {404, 405}:
            return []
        raise
    service_name = str(service.get("Name") or service.get("Id") or log_service_path).strip()
    entries_path = redfish_link(service, "Entries") or f"{log_service_path}/Entries"
    entries = []
    next_path = entries_path
    while next_path and len(entries) < limit:
        try:
            data = await redfish_get(client, next_path)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code in {404, 405}:
                return entries
            raise
        members = data.get("Members") if isinstance(data, dict) else []
        if not isinstance(members, list):
            members = []
        for item in members:
            if isinstance(item, dict):
                if item.get("@odata.id") and len(item) <= 1:
                    try:
                        item = await redfish_get(client, redfish_path(item.get("@odata.id")))
                    except httpx.HTTPStatusError:
                        continue
                entries.append(normalize_redfish_log_entry(item, service_name))
                if len(entries) >= limit:
                    break
        next_path = redfish_path(data.get("@odata.nextLink") or data.get("Members@odata.nextLink"))
    return entries


async def collect_redfish_ipmi_logs(config: dict, limit: int = 50) -> dict:
    host = normalize_redfish_host(config["host"])
    auth = (config["user"], config["password"]) if config.get("user") else None
    base_url = f"https://{host}"
    bounded_limit = max(1, min(int(limit or 50), 200))
    timeout = httpx.Timeout(12.0, connect=5.0)
    async with httpx.AsyncClient(base_url=base_url, timeout=timeout, verify=False, trust_env=False, auth=auth) as client:
        log_paths = await redfish_log_service_paths(client)
        entries_by_service = await asyncio.gather(
            *(redfish_log_entries(client, path, bounded_limit) for path in log_paths),
            return_exceptions=True,
        )
    entries = []
    for item in entries_by_service:
        if isinstance(item, Exception):
            continue
        entries.extend(item)
    entries.sort(key=lambda row: row.get("created") or "", reverse=True)
    return {
        "host": host,
        "logs": entries[:bounded_limit],
        "services": log_paths,
    }


async def control_redfish_power(config: dict, action: str) -> dict:
    host = normalize_redfish_host(config["host"])
    auth = (config["user"], config["password"]) if config.get("user") else None
    base_url = f"https://{host}"
    timeout = httpx.Timeout(12.0, connect=5.0)
    reset_types = redfish_reset_types(action)
    async with httpx.AsyncClient(base_url=base_url, timeout=timeout, verify=False, trust_env=False, auth=auth) as client:
        system_path, system = await redfish_system_path(client)
        actions = system.get("Actions") if isinstance(system.get("Actions"), dict) else {}
        reset_action = actions.get("#ComputerSystem.Reset") if isinstance(actions.get("#ComputerSystem.Reset"), dict) else {}
        reset_target = redfish_path(reset_action.get("target")) or f"{system_path}/Actions/ComputerSystem.Reset"
        last_error: Exception | None = None
        for reset_type in reset_types:
            try:
                await redfish_post(client, reset_target, {"ResetType": reset_type})
                return {
                    "host": host,
                    "reset_type": reset_type,
                    "power_state": system.get("PowerState") or "",
                    "target": reset_target,
                }
            except httpx.HTTPStatusError as exc:
                last_error = exc
                if exc.response.status_code not in {400, 405, 409, 501}:
                    raise
        if last_error:
            raise last_error
    raise ValueError("电源操作提交失败")
DEVICE_SECRET_VIEW_ACCOUNT_NAMES = {"admin", "noc"}
INVENTORY_IMPORT_BASE_COLUMNS = {
    "区域",
    "位置",
    "分类",
    "子类",
    "数量",
    "扩展属性(JSON)",
    "备注",
    "状态",
}

DEFAULT_INVENTORY_CATEGORY_TREE = [
    {"name": "光模块", "children": ["100G", "40G", "25G", "10G", "1G"]},
    {"name": "光纤", "children": ["单模", "多模", "MPO"]},
    {"name": "网线", "children": []},
    {"name": "电源线", "children": ["接口类型"]},
    {"name": "调试线", "children": []},
    {"name": "DAC", "children": []},
    {"name": "AOC", "children": []},
    {"name": "服务器配件", "children": ["CPU", "内存", "硬盘", "网卡", "导轨", "背板"]},
    {"name": "工具", "children": ["螺丝刀", "扎带", "标签机", "手套"]},
]

DEFAULT_DEVICE_BRAND_TREE = [
    {"name": "戴尔", "models": ["R640", "R740", "R750", "R760"]},
    {"name": "华为", "models": ["RH2288H V5", "2288H V5", "2288H V6"]},
    {"name": "浪潮", "models": ["NF5280M5", "NF5280M6"]},
    {"name": "新华三", "models": ["R4900 G3", "R4900 G5"]},
    {"name": "联想", "models": ["SR650", "SR650 V2"]},
    {"name": "Cisco", "models": ["UCS C220", "UCS C240"]},
]


async def can_view_device_secrets() -> bool:
    user_id = CTX_USER_ID.get()
    user = await User.get_or_none(id=user_id)
    if not user:
        return False
    if user.is_superuser:
        return True

    user_names = {
        str(user.username or "").strip().lower(),
        str(user.alias or "").strip().lower(),
    }
    email_local = str(user.email or "").split("@", 1)[0].strip().lower()
    if email_local:
        user_names.add(email_local)
    if user_names & DEVICE_SECRET_VIEW_ACCOUNT_NAMES:
        return True

    roles = await user.roles.all()
    role_names = {str(role.name or "").strip().lower() for role in roles}
    return bool(role_names & DEVICE_SECRET_VIEW_ROLE_NAMES)


def mask_device_secret_attributes(attributes: dict | None) -> dict:
    if not isinstance(attributes, dict):
        return {}
    result = deepcopy(attributes)
    for key in SENSITIVE_DEVICE_ATTRIBUTE_KEYS:
        if result.get(key):
            result[key] = MASKED_DEVICE_SECRET
    if isinstance(result.get("nodes"), list):
        for node in result["nodes"]:
            if isinstance(node, dict) and node.get("ipmi_password"):
                node["ipmi_password"] = MASKED_DEVICE_SECRET
    return result


def preserve_masked_four_node_secrets(attributes: dict, existed_attributes: dict) -> None:
    nodes = attributes.get("nodes")
    existed_nodes = existed_attributes.get("nodes")
    if not isinstance(nodes, list):
        return
    if not isinstance(existed_nodes, list):
        existed_nodes = []
    existed_by_name = {
        str(node.get("name") or ""): node
        for node in existed_nodes
        if isinstance(node, dict) and str(node.get("name") or "")
    }
    for node in nodes:
        if not isinstance(node, dict):
            continue
        existed_node = existed_by_name.get(str(node.get("name") or ""))
        if existed_node:
            node["ipmi_password"] = existed_node.get("ipmi_password", "")
        else:
            node.pop("ipmi_password", None)


def normalize_device_status_value(value, default: int = 0) -> int:
    try:
        status = int(value)
    except (TypeError, ValueError):
        return default
    return status if status in {0, 1, 3, 4} else default


def is_four_node_attributes(attributes: dict) -> bool:
    return attributes.get("form_factor") == "four_node" or attributes.get("设备形态") == "四节点服务器"


def aggregate_four_node_status(nodes: list) -> int:
    statuses = [
        normalize_device_status_value(node.get("status"), 0)
        for node in nodes
        if isinstance(node, dict)
    ]
    if not statuses:
        return 0
    if all(status == 4 for status in statuses):
        return 4
    if any(status == 3 for status in statuses):
        return 3
    if any(status == 1 for status in statuses):
        return 1
    if any(status == 0 for status in statuses):
        return 0
    return statuses[0]


def normalize_four_node_status_for_save(device_in: AssetDeviceCreate | AssetDeviceUpdate) -> None:
    attributes = dict(device_in.attributes or {})
    if not is_four_node_attributes(attributes):
        return
    nodes = attributes.get("nodes")
    if not isinstance(nodes, list):
        nodes = []
    normalized_nodes = []
    for node in nodes:
        if not isinstance(node, dict):
            continue
        item = dict(node)
        item["status"] = normalize_device_status_value(item.get("status"), 0)
        normalized_nodes.append(item)
    attributes["nodes"] = normalized_nodes
    device_in.attributes = attributes
    device_in.status = aggregate_four_node_status(normalized_nodes)


async def prepare_device_attributes_for_save(device_in: AssetDeviceCreate | AssetDeviceUpdate) -> None:
    attributes = dict(device_in.attributes or {})
    if await can_view_device_secrets():
        device_in.attributes = attributes
        return

    if isinstance(device_in, AssetDeviceUpdate):
        existed_device = await asset_device_controller.get(id=device_in.id)
        existed_attributes = dict(existed_device.attributes or {})
    else:
        existed_attributes = {}

    for key in SENSITIVE_DEVICE_ATTRIBUTE_KEYS:
        if key in existed_attributes:
            attributes[key] = existed_attributes[key]
        else:
            attributes.pop(key, None)
    preserve_masked_four_node_secrets(attributes, existed_attributes)
    device_in.attributes = attributes


async def device_to_dict(device: AssetDevice, can_view_secrets: bool = False) -> dict:
    data = await device.to_dict()
    raw_attributes = data.get("attributes") if isinstance(data.get("attributes"), dict) else {}
    if is_four_node_attributes(raw_attributes):
        nodes = raw_attributes.get("nodes") if isinstance(raw_attributes.get("nodes"), list) else []
        data["status"] = aggregate_four_node_status(nodes)
    if not can_view_secrets:
        data["attributes"] = mask_device_secret_attributes(data.get("attributes"))
    cabinet = await AssetCabinet.get_or_none(id=device.cabinet_id)
    location = await AssetLocation.get_or_none(id=device.location_id)
    region = await AssetRegion.get_or_none(id=device.region_id)
    data["cabinet_name"] = cabinet.name if cabinet else ""
    data["location_name"] = location.name if location else ""
    data["region_name"] = region.name if region else ""
    return data


def first_device_attribute(attributes: dict, keys: tuple[str, ...]) -> str:
    for key in keys:
        value = attributes.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def is_huawei_vnc_device(device: AssetDevice) -> bool:
    attributes = dict(device.attributes or {})
    text = " ".join(
        [
            str(device.name or ""),
            str(getattr(device, "brand", "") or ""),
            str(getattr(device, "model", "") or ""),
            json.dumps(attributes, ensure_ascii=False),
        ]
    ).lower()
    return any(keyword in text for keyword in ("huawei", "ibmc", "\u534e\u4e3a"))


def device_vnc_config(device: AssetDevice) -> dict:
    attributes = dict(device.attributes or {})
    host = first_device_attribute(
        attributes,
        ("vnc_host", "vnc_address", "VNC地址", "VNC主机", "ipmi_host", "IPMI地址"),
    )
    port_text = first_device_attribute(attributes, ("vnc_port", "VNC端口"))
    password = first_device_attribute(attributes, ("vnc_password", "VNC密码")) or DEVICE_VNC_DEFAULT_PASSWORD
    if not host:
        raise ValueError("设备未配置 VNC 地址或 IPMI 地址")
    try:
        port = int(port_text or DEVICE_VNC_DEFAULT_PORT)
    except ValueError as exc:
        raise ValueError("VNC 端口格式错误") from exc
    if port < 1 or port > 65535:
        raise ValueError("VNC 端口必须在 1-65535 之间")
    return {"host": host, "port": port, "password": password, "tls_preferred": is_huawei_vnc_device(device)}


def four_node_vnc_config(device: AssetDevice, node_name: str) -> dict:
    attributes = dict(device.attributes or {})
    nodes = attributes.get("nodes")
    if not isinstance(nodes, list):
        raise ValueError("设备未配置四节点信息")

    normalized_node_name = str(node_name or "").strip()
    node = next(
        (
            item
            for item in nodes
            if isinstance(item, dict) and str(item.get("name") or "").strip() == normalized_node_name
        ),
        None,
    )
    if not node:
        raise ValueError("未找到对应的四节点")

    host = first_device_attribute(
        node,
        ("vnc_host", "vnc_address", "VNC地址", "VNC主机", "ipmi_host", "ipmiHost", "IPMI地址"),
    )
    port_text = first_device_attribute(node, ("vnc_port", "vncPort", "VNC端口")) or first_device_attribute(
        attributes, ("vnc_port", "VNC端口")
    )
    password = (
        first_device_attribute(node, ("vnc_password", "vncPassword", "VNC密码"))
        or first_device_attribute(attributes, ("vnc_password", "VNC密码"))
        or DEVICE_VNC_DEFAULT_PASSWORD
    )
    if not host:
        raise ValueError("该节点未配置 IPMI 地址")
    try:
        port = int(port_text or DEVICE_VNC_DEFAULT_PORT)
    except ValueError as exc:
        raise ValueError("VNC 端口格式错误") from exc
    if port < 1 or port > 65535:
        raise ValueError("VNC 端口必须在 1-65535 之间")

    display_name = str(node.get("device_name") or node.get("deviceName") or normalized_node_name).strip()
    return {
        "host": host,
        "port": port,
        "password": password,
        "node_name": normalized_node_name,
        "display_name": display_name,
        "tls_preferred": is_huawei_vnc_device(device),
    }


def cleanup_device_vnc_sessions() -> None:
    now = datetime.now().timestamp()
    expired = [
        session_id
        for session_id, session in DEVICE_VNC_SESSIONS.items()
        if now - float(session.get("created_at") or 0) > DEVICE_VNC_SESSION_TTL
    ]
    for session_id in expired:
        DEVICE_VNC_SESSIONS.pop(session_id, None)


def create_device_vnc_session(device: AssetDevice, config: dict) -> str:
    cleanup_device_vnc_sessions()
    session_id = uuid.uuid4().hex
    DEVICE_VNC_SESSIONS[session_id] = {
        "created_at": datetime.now().timestamp(),
        "device_id": device.id,
        "device_name": device.name,
        "host": config["host"],
        "port": config["port"],
        "password": config["password"],
        "tls_preferred": bool(config.get("tls_preferred")),
    }
    return session_id


async def inventory_to_dict(item: AssetInventory) -> dict:
    data = await item.to_dict()
    location = await AssetLocation.get_or_none(id=item.location_id)
    region = await AssetRegion.get_or_none(id=item.region_id)
    data["location_name"] = location.name if location else ""
    data["region_name"] = region.name if region else ""
    return data


def is_low_inventory(item: AssetInventory) -> bool:
    if not item.status:
        return False
    if item.quantity <= 0:
        return True
    return bool(item.threshold > 0 and item.quantity < item.threshold)


def build_inventory_alert_card(items: list[dict]) -> dict:
    lines = []
    for item in items[:10]:
        name = f"{item.get('type') or '-'} / {item.get('subtype') or '-'}"
        location = item.get("location_name") or "-"
        region = item.get("region_name") or "-"
        quantity = int(item.get("quantity", 0) or 0)
        threshold = int(item.get("threshold", 0) or 0)
        reason = "库存已为 0" if quantity <= 0 else f"低于阈值 {threshold}"
        lines.append(
            f"**{name}**\n"
            f"区域/位置：{region} / {location}\n"
            f"当前库存：{quantity}，阈值：{threshold}，原因：{reason}"
        )
    if len(items) > 10:
        lines.append(f"还有 {len(items) - 10} 条低库存记录未展示")

    return {
        "msg_type": "interactive",
        "card": {
            "config": {"wide_screen_mode": True},
            "header": {
                "template": "orange",
                "title": {"tag": "plain_text", "content": "库存阈值告警"},
            },
            "elements": [
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"检测到 **{len(items)}** 条库存异常：\n\n" + "\n\n".join(lines),
                    },
                }
            ],
        },
    }


def post_feishu_card(payload: dict) -> None:
    if not INVENTORY_FEISHU_WEBHOOK:
        return
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        INVENTORY_FEISHU_WEBHOOK,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            body = response.read().decode("utf-8", errors="replace")
    except urllib.error.URLError as exc:
        print(f"inventory feishu alert failed: {exc}")
        return

    try:
        result = json.loads(body)
    except json.JSONDecodeError:
        return
    if result.get("StatusCode", result.get("code", 0)) not in (0, "0"):
        print(f"inventory feishu alert returned error: {body}")


async def send_inventory_threshold_alert(items: list[AssetInventory]) -> None:
    low_items = [item for item in items if is_low_inventory(item)]
    if not low_items:
        return
    data = [await inventory_to_dict(item) for item in low_items]
    await asyncio.to_thread(post_feishu_card, build_inventory_alert_card(data))


async def generate_sale_no() -> str:
    prefix = f"SALE-{datetime.now().strftime('%Y%m%d')}"
    count = await AssetInventorySaleOrder.filter(sale_no__startswith=prefix).count()
    return f"{prefix}-{count + 1:04d}"


async def stock_flow_to_dict(flow: AssetInventoryStockFlow) -> dict:
    data = await flow.to_dict()
    inventory = await AssetInventory.get_or_none(id=flow.inventory_id)
    if inventory:
        data["inventory_type"] = inventory.type
        data["inventory_subtype"] = inventory.subtype or ""
        data["inventory_location_id"] = inventory.location_id
    return data


async def sale_order_to_dict(order: AssetInventorySaleOrder, include_items: bool = True) -> dict:
    data = await order.to_dict()
    if not include_items:
        return data

    items = await AssetInventorySaleItem.filter(sale_order_id=order.id).order_by("id")
    data["items"] = []
    for item in items:
        item_data = await item.to_dict()
        inventory = await AssetInventory.get_or_none(id=item.inventory_id)
        if inventory:
            item_data["inventory_quantity"] = inventory.quantity
            item_data["inventory_threshold"] = inventory.threshold
            location = await AssetLocation.get_or_none(id=inventory.location_id)
            item_data["location_name"] = location.name if location else ""
        data["items"].append(item_data)
    return data


async def create_stock_flow(
    *,
    inventory: AssetInventory,
    flow_type: str,
    quantity_before: int,
    quantity_change: int,
    quantity_after: int,
    biz_type: str,
    biz_id: int | None,
    remark: str = "",
) -> AssetInventoryStockFlow:
    return await AssetInventoryStockFlow.create(
        inventory_id=inventory.id,
        flow_type=flow_type,
        quantity_before=quantity_before,
        quantity_change=quantity_change,
        quantity_after=quantity_after,
        biz_type=biz_type,
        biz_id=biz_id,
        remark=remark,
        created_by=CTX_USER_ID.get(),
    )


async def ensure_default_inventory_categories() -> None:
    if await AssetInventoryCategory.exists():
        return

    for sort, item in enumerate(DEFAULT_INVENTORY_CATEGORY_TREE, start=1):
        parent = await AssetInventoryCategory.create(name=item["name"], parent_id=None, sort=sort, status=True)
        for child_sort, child_name in enumerate(item["children"], start=1):
            await AssetInventoryCategory.create(
                name=child_name,
                parent_id=parent.id,
                sort=child_sort,
                status=True,
            )


def category_to_dict(item: AssetInventoryCategory) -> dict:
    return {
        "id": item.id,
        "label": item.name,
        "value": item.name,
        "name": item.name,
        "parent_id": item.parent_id,
        "sort": item.sort,
        "status": item.status,
        "children": [],
    }


async def inventory_category_tree() -> list[dict]:
    await ensure_default_inventory_categories()
    categories = await asset_inventory_category_controller.list_categories()
    parents = [category_to_dict(item) for item in categories if item.parent_id is None]
    parent_map = {item["id"]: item for item in parents}
    for item in categories:
        if item.parent_id is None:
            continue
        parent = parent_map.get(item.parent_id)
        if parent:
            parent["children"].append(category_to_dict(item))
    return parents


async def ensure_device_brand_models() -> None:
    if not await AssetDeviceBrand.exists():
        for sort, item in enumerate(DEFAULT_DEVICE_BRAND_TREE, start=1):
            brand = await asset_device_brand_controller.create(
                AssetDeviceBrandCreate(name=item["name"], sort=sort, status=True)
            )
            for model_sort, model_name in enumerate(item["models"], start=1):
                await asset_device_model_controller.create(
                    AssetDeviceModelCreate(
                        brand_id=brand.id,
                        name=model_name,
                        sort=model_sort,
                        status=True,
                    )
                )

    devices = await AssetDevice.all()
    for device in devices:
        brand_name = str(device.brand or "").strip()
        model_name = str(device.model or "").strip()
        if not brand_name:
            continue
        brand = await AssetDeviceBrand.get_or_none(name=brand_name)
        if not brand:
            brand = await asset_device_brand_controller.create(
                AssetDeviceBrandCreate(
                    name=brand_name,
                    sort=await AssetDeviceBrand.all().count() + 1,
                    status=True,
                )
            )
        if model_name and not await AssetDeviceModel.get_or_none(brand_id=brand.id, name=model_name):
            await asset_device_model_controller.create(
                AssetDeviceModelCreate(
                    brand_id=brand.id,
                    name=model_name,
                    sort=await AssetDeviceModel.filter(brand_id=brand.id).count() + 1,
                    status=True,
                )
            )


async def device_brand_tree() -> list[dict]:
    await ensure_device_brand_models()
    brands = await asset_device_brand_controller.list_brands()
    models = await asset_device_model_controller.list_models()
    model_map: dict[int, list[dict]] = {}
    for item in models:
        model_map.setdefault(item.brand_id, []).append(
            {
                "id": item.id,
                "label": item.name,
                "value": item.name,
                "name": item.name,
                "brand_id": item.brand_id,
            }
        )
    return [
        {
            "id": brand.id,
            "label": brand.name,
            "value": brand.name,
            "name": brand.name,
            "models": model_map.get(brand.id, []),
        }
        for brand in brands
    ]


def get_inventory_order(sort_by: str = "", sort_order: str = "") -> list[str]:
    sortable_fields = {"type", "subtype", "quantity", "cost_price", "sale_price"}
    if sort_by not in sortable_fields:
        return ["type", "subtype", "id"]
    prefix = "-" if sort_order == "descend" else ""
    return [f"{prefix}{sort_by}", "id"]


def inventory_matches_keyword(item: AssetInventory, keyword: str) -> bool:
    text = keyword.strip().lower()
    if not text:
        return True
    attributes_text = json.dumps(item.attributes or {}, ensure_ascii=False).lower()
    values = [
        item.type,
        item.subtype,
        str(item.quantity),
        str(getattr(item, "threshold", 0)),
        str(getattr(item, "cost_price", 0)),
        str(getattr(item, "cost_price_currency", "")),
        str(getattr(item, "sale_price", 0)),
        str(getattr(item, "sale_price_currency", "")),
        item.remark,
        attributes_text,
    ]
    return any(text in str(value or "").lower() for value in values)


def parse_bool_status(value: str | None, default: bool = True) -> bool:
    text = str(value or "").strip().lower()
    if not text:
        return default
    if text in {"禁用", "停用", "否", "false", "0", "disabled", "inactive", "no"}:
        return False
    return True


def parse_inventory_attributes(row: dict) -> dict:
    attributes = {}
    json_text = str(row.get("扩展属性(JSON)", "") or "").strip()
    if json_text:
        try:
            parsed = json.loads(json_text)
            if isinstance(parsed, dict):
                attributes.update({str(key): str(value) for key, value in parsed.items()})
        except json.JSONDecodeError:
            pass

    for key, value in row.items():
        if not key.startswith("属性:"):
            continue
        attr_key = key.split(":", 1)[1].strip()
        attr_value = str(value or "").strip()
        if attr_key and attr_value:
            attributes[attr_key] = attr_value
    return attributes


async def resolve_inventory_location_id(row: dict) -> int | None:
    location_name = str(row.get("位置", "") or "").strip()
    if not location_name:
        return None

    query = AssetLocation.filter(name=location_name, type=0)
    region_name = str(row.get("区域", "") or "").strip()
    if region_name:
        region = await AssetRegion.get_or_none(name=region_name)
        if region:
            query = query.filter(region_id=region.id)
    location = await query.first()
    return location.id if location else None


@router.get("/tree", summary="资产位置树")
async def asset_tree():
    regions = await AssetRegion.filter(status=True).order_by("code", "id")
    locations = await AssetLocation.filter(status=True).order_by("region_id", "type", "id")
    cabinets = await AssetCabinet.filter(status=True).order_by("location_id", "code", "id")

    location_map: dict[int, list[AssetLocation]] = {}
    for location in locations:
        location_map.setdefault(location.region_id, []).append(location)

    cabinet_map: dict[int, list[AssetCabinet]] = {}
    for cabinet in cabinets:
        cabinet_map.setdefault(cabinet.location_id, []).append(cabinet)

    data = []
    for region in regions:
        region_node = {
            "id": f"region-{region.id}",
            "raw_id": region.id,
            "label": region.name,
            "type": "region",
            "children": [],
        }
        for location in location_map.get(region.id, []):
            location_node = {
                "id": f"location-{location.id}",
                "raw_id": location.id,
                "label": location.name,
                "type": "location",
                "location_type": location.type,
                "children": [],
            }
            for cabinet in cabinet_map.get(location.id, []):
                location_node["children"].append(
                    {
                        "id": f"cabinet-{cabinet.id}",
                        "raw_id": cabinet.id,
                        "label": cabinet.name,
                        "type": "cabinet",
                        "children": [],
                    }
                )
            region_node["children"].append(location_node)
        data.append(region_node)
    return Success(data=data)


@router.get("/region/list", summary="区域列表")
async def list_region(
    page: int = Query(1),
    page_size: int = Query(100),
    name: str = Query(""),
    code: str = Query(""),
    country: str = Query(""),
    city: str = Query(""),
    status: bool | None = Query(None),
):
    q = Q()
    if name:
        q &= Q(name__contains=name)
    if code:
        q &= Q(code__contains=code)
    if country:
        q &= Q(country__contains=country)
    if city:
        q &= Q(city__contains=city)
    if status is not None:
        q &= Q(status=status)
    total, objs = await asset_region_controller.list_regions(page=page, page_size=page_size, search=q)
    data = [await obj.to_dict() for obj in objs]
    return SuccessExtra(data=data, total=total, page=page, page_size=page_size)


@router.get("/region/get", summary="区域详情")
async def get_region(region_id: int = Query(...)):
    obj = await asset_region_controller.get(id=region_id)
    return Success(data=await obj.to_dict())


@router.post("/region/create", summary="创建区域")
async def create_region(region_in: AssetRegionCreate):
    obj = await asset_region_controller.create(region_in)
    return Success(msg="Created Successfully", data=await obj.to_dict())


@router.post("/region/update", summary="更新区域")
async def update_region(region_in: AssetRegionUpdate):
    obj = await asset_region_controller.update(id=region_in.id, obj_in=region_in)
    return Success(msg="Updated Successfully", data=await obj.to_dict())


@router.delete("/region/delete", summary="删除区域")
async def delete_region(region_id: int = Query(...)):
    await asset_region_controller.remove(id=region_id)
    return Success(msg="Deleted Successfully")


@router.get("/location/list", summary="位置列表")
async def list_location(
    page: int = Query(1),
    page_size: int = Query(100),
    region_id: int | None = Query(None),
    type: int | None = Query(None),
    name: str = Query(""),
    status: bool | None = Query(None),
):
    q = Q()
    if region_id is not None:
        q &= Q(region_id=region_id)
    if type is not None:
        q &= Q(type=type)
    if name:
        q &= Q(name__contains=name)
    if status is not None:
        q &= Q(status=status)
    total, objs = await asset_location_controller.list_locations(page=page, page_size=page_size, search=q)
    data = [await obj.to_dict() for obj in objs]
    return SuccessExtra(data=data, total=total, page=page, page_size=page_size)


@router.post("/location/create", summary="创建位置")
async def create_location(location_in: AssetLocationCreate):
    obj = await asset_location_controller.create(location_in)
    return Success(msg="Created Successfully", data=await obj.to_dict())


@router.post("/location/update", summary="更新位置")
async def update_location(location_in: AssetLocationUpdate):
    obj = await asset_location_controller.update(id=location_in.id, obj_in=location_in)
    return Success(msg="Updated Successfully", data=await obj.to_dict())


@router.delete("/location/delete", summary="删除位置")
async def delete_location(location_id: int = Query(...)):
    await asset_location_controller.remove(id=location_id)
    return Success(msg="Deleted Successfully")


@router.get("/cabinet/list", summary="机柜列表")
async def list_cabinet(
    page: int = Query(1),
    page_size: int = Query(100),
    location_id: int | None = Query(None),
    name: str = Query(""),
    code: str = Query(""),
    status: bool | None = Query(None),
):
    q = Q()
    if location_id is not None:
        q &= Q(location_id=location_id)
    if name:
        q &= Q(name__contains=name)
    if code:
        q &= Q(code__contains=code)
    if status is not None:
        q &= Q(status=status)
    total, objs = await asset_cabinet_controller.list_cabinets(page=page, page_size=page_size, search=q)
    data = [await obj.to_dict() for obj in objs]
    cabinet_ids = [item["id"] for item in data]
    if cabinet_ids:
        rows = await AssetDevice.filter(cabinet_id__in=cabinet_ids).group_by("cabinet_id").annotate(
            device_count=Count("id")
        ).values("cabinet_id", "device_count")
        count_map = {int(row["cabinet_id"]): int(row["device_count"] or 0) for row in rows}
        for item in data:
            item["device_count"] = count_map.get(int(item["id"]), 0)
    else:
        for item in data:
            item["device_count"] = 0
    return SuccessExtra(data=data, total=total, page=page, page_size=page_size)


@router.get("/cabinet/get", summary="机柜详情")
async def get_cabinet(cabinet_id: int = Query(...)):
    obj = await asset_cabinet_controller.get(id=cabinet_id)
    data = await obj.to_dict()
    data["device_count"] = await AssetDevice.filter(cabinet_id=cabinet_id).count()
    return Success(data=data)


def normalize_cabinet_payload(cabinet_in: AssetCabinetCreate | AssetCabinetUpdate) -> dict:
    data = cabinet_in.model_dump(exclude={"id"})
    start_u = int(data.get("rental_start_u") or 1)
    end_u = int(data.get("rental_end_u") or start_u)
    if start_u < 1 or end_u < start_u:
        raise ValueError("请填写有效的租用U位范围，例如 20-25U")
    data["name"] = str(data.get("name") or "").strip()
    data["code"] = str(data.get("code") or data["name"]).strip()
    data["row"] = ""
    data["column"] = ""
    data["capacity_u"] = end_u - start_u + 1
    data["rental_start_u"] = start_u
    data["rental_end_u"] = end_u
    data["width_mm"] = max(int(data.get("width_mm") or 0), 0)
    data["depth_mm"] = max(int(data.get("depth_mm") or 0), 0)
    data["power_allocation_kw"] = max(float(data.get("power_allocation_kw") or 0), 0)
    for field in ("power_overage_rate", "pdu_spec", "power_socket_spec", "rack_tray", "pdu_socket_types", "remark"):
        data[field] = str(data.get(field) or "").strip()
    return data


async def validate_device_u_range(device_in: AssetDeviceCreate | AssetDeviceUpdate) -> str:
    cabinet = await AssetCabinet.get(id=device_in.cabinet_id)
    rental_start = max(int(cabinet.rental_start_u or 1), 1)
    rental_end = max(int(cabinet.rental_end_u or rental_start), rental_start)
    start = int(device_in.u_position or 0)
    height = max(int(device_in.u_height or 1), 1)
    end = start + height - 1
    if not start or start < rental_start or end > rental_end:
        return f"设备U位必须在当前机柜可用范围内: {rental_start}-{rental_end}U"
    return ""


@router.post("/cabinet/create", summary="创建机柜")
async def create_cabinet(cabinet_in: AssetCabinetCreate):
    try:
        data = normalize_cabinet_payload(cabinet_in)
    except ValueError as exc:
        return Success(msg=str(exc), code=400)
    obj = await asset_cabinet_controller.create(data)
    return Success(msg="Created Successfully", data=await obj.to_dict())


@router.post("/cabinet/update", summary="更新机柜")
async def update_cabinet(cabinet_in: AssetCabinetUpdate):
    try:
        data = normalize_cabinet_payload(cabinet_in)
    except ValueError as exc:
        return Success(msg=str(exc), code=400)
    used = await AssetDevice.filter(cabinet_id=cabinet_in.id)
    for device in used:
        start = int(device.u_position or 0)
        end = start + max(int(device.u_height or 1), 1) - 1
        if start and (start < data["rental_start_u"] or end > data["rental_end_u"]):
            return Success(msg="已有设备超出租用U位范围，请先调整设备U位", code=400)
    obj = await asset_cabinet_controller.update(id=cabinet_in.id, obj_in=data)
    return Success(msg="Updated Successfully", data=await obj.to_dict())


@router.delete("/cabinet/delete", summary="删除机柜")
async def delete_cabinet(cabinet_id: int = Query(...)):
    if await AssetDevice.filter(cabinet_id=cabinet_id).exists():
        return Success(msg="机柜下存在设备，不能删除", code=400)
    await asset_cabinet_controller.remove(id=cabinet_id)
    return Success(msg="Deleted Successfully")


@router.get("/device-brand/list", summary="设备品牌型号列表")
async def list_device_brands():
    return Success(data=await device_brand_tree())


@router.post("/device-brand/create", summary="创建设备品牌")
async def create_device_brand(brand_in: AssetDeviceBrandCreate):
    name = brand_in.name.strip()
    if not name:
        return Success(msg="品牌名称不能为空", code=400)
    if await AssetDeviceBrand.get_or_none(name=name):
        return Success(msg="品牌已存在", code=400)
    data = brand_in.model_dump()
    data["name"] = name
    if not data.get("sort"):
        data["sort"] = await AssetDeviceBrand.all().count() + 1
    await asset_device_brand_controller.create(data)
    return Success(msg="Created Successfully", data=await device_brand_tree())


@router.delete("/device-brand/delete", summary="删除设备品牌")
async def delete_device_brand(brand_id: int = Query(...)):
    await AssetDeviceModel.filter(brand_id=brand_id).delete()
    await asset_device_brand_controller.remove(id=brand_id)
    return Success(msg="Deleted Successfully", data=await device_brand_tree())


@router.post("/device-model/create", summary="创建设备型号")
async def create_device_model(model_in: AssetDeviceModelCreate):
    name = model_in.name.strip()
    if not name:
        return Success(msg="型号名称不能为空", code=400)
    if not await AssetDeviceBrand.get_or_none(id=model_in.brand_id):
        return Success(msg="品牌不存在", code=400)
    if await AssetDeviceModel.get_or_none(brand_id=model_in.brand_id, name=name):
        return Success(msg="型号已存在", code=400)
    data = model_in.model_dump()
    data["name"] = name
    if not data.get("sort"):
        data["sort"] = await AssetDeviceModel.filter(brand_id=model_in.brand_id).count() + 1
    await asset_device_model_controller.create(data)
    return Success(msg="Created Successfully", data=await device_brand_tree())


@router.delete("/device-model/delete", summary="删除设备型号")
async def delete_device_model(model_id: int = Query(...)):
    await asset_device_model_controller.remove(id=model_id)
    return Success(msg="Deleted Successfully", data=await device_brand_tree())


@router.get("/device/list", summary="设备列表")
async def list_device(
    page: int = Query(1),
    page_size: int = Query(10),
    region_id: int | None = Query(None),
    location_id: int | None = Query(None),
    cabinet_id: int | None = Query(None),
    keyword: str = Query(""),
    type: int | None = Query(None),
    status: int | None = Query(None),
):
    q = Q()
    if region_id is not None:
        q &= Q(region_id=region_id)
    if location_id is not None:
        q &= Q(location_id=location_id)
    if cabinet_id is not None:
        q &= Q(cabinet_id=cabinet_id)
    if type is not None:
        q &= Q(type=type)
    if status is not None:
        q &= Q(status=status)
    if keyword:
        q &= (
            Q(asset_no__contains=keyword)
            | Q(name__contains=keyword)
            | Q(serial_no__contains=keyword)
            | Q(mgmt_ip__contains=keyword)
            | Q(business_ip__contains=keyword)
        )
    total, objs = await asset_device_controller.list_devices(page=page, page_size=page_size, search=q)
    can_view_secrets = await can_view_device_secrets()
    data = [await device_to_dict(obj, can_view_secrets=can_view_secrets) for obj in objs]
    return SuccessExtra(data=data, total=total, page=page, page_size=page_size)


@router.get("/device/get", summary="设备详情")
async def get_device(device_id: int = Query(...)):
    obj = await asset_device_controller.get(id=device_id)
    return Success(data=await device_to_dict(obj, can_view_secrets=await can_view_device_secrets()))


@router.post("/device/vnc", summary="创建设备 VNC 控制台会话")
async def device_vnc_console(payload: AssetDeviceVncRequest):
    try:
        device = await asset_device_controller.get(id=payload.device_id)
        config = four_node_vnc_config(device, payload.node_name) if payload.node_name else device_vnc_config(device)
        session_id = create_device_vnc_session(device, config)
        query = urlencode({"session": session_id, "device_id": str(device.id)})
        device_name = config.get("display_name") or device.name
        return Success(
            data={
                "wsUrl": f"/api/v1/asset/device/vnc/ws?{query}",
                "password": config["password"],
                "host": config["host"],
                "port": config["port"],
                "device_id": device.id,
                "device_name": device_name,
                "node_name": config.get("node_name", ""),
            }
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@ws_router.websocket("/device/vnc/ws")
async def device_vnc_websocket_proxy(
    websocket: WebSocket,
    session: str,
    device_id: int,
    token: str = "",
):
    await websocket.accept(subprotocol="binary")
    try:
        await AuthControl.is_authed(token=token)
    except HTTPException as exc:
        await websocket.close(code=1008, reason=str(exc.detail)[:120])
        return

    cleanup_device_vnc_sessions()
    vnc_session = DEVICE_VNC_SESSIONS.get(session)
    if not vnc_session or int(vnc_session.get("device_id") or 0) != int(device_id):
        await websocket.close(code=1008, reason="VNC session expired")
        return

    proxy_stats = {"client_bytes": 0, "vnc_bytes": 0}

    async def close_vnc_writer(writer_obj):
        if not writer_obj:
            return
        try:
            writer_obj.close()
            await writer_obj.wait_closed()
        except (ConnectionResetError, OSError):
            pass

    async def open_vnc_connection(use_tls: bool = False):
        tls_context = None
        if use_tls:
            tls_context = ssl.create_default_context()
            tls_context.check_hostname = False
            tls_context.verify_mode = ssl.CERT_NONE
        mode = "tls" if use_tls else "plain"
        reader_obj, writer_obj = await asyncio.wait_for(
            asyncio.open_connection(
                str(vnc_session["host"]),
                int(vnc_session["port"]),
                ssl=tls_context,
                server_hostname=None if use_tls else None,
            ),
            timeout=8,
        )
        transport_obj = writer_obj.get_extra_info("socket")
        if transport_obj:
            transport_obj.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        logger.info(
            "device VNC TCP connected: device_id={} device_name={} target={}:{} mode={}",
            vnc_session.get("device_id"),
            vnc_session.get("device_name"),
            vnc_session.get("host"),
            vnc_session.get("port"),
            mode,
        )
        try:
            banner = await asyncio.wait_for(reader_obj.readexactly(12), timeout=5)
            if not banner.startswith(b"RFB "):
                raise ValueError(f"invalid RFB banner: {banner!r}")
            return reader_obj, writer_obj, banner, mode
        except Exception:
            await close_vnc_writer(writer_obj)
            raise

    reader = None
    writer = None
    vnc_mode = "plain"
    preferred_tls = bool(vnc_session.get("tls_preferred"))
    first_tls = preferred_tls
    second_tls = not preferred_tls
    try:
        reader, writer, rfb_banner, vnc_mode = await open_vnc_connection(use_tls=first_tls)
    except asyncio.TimeoutError:
        logger.info(
            "device VNC {} handshake timeout, retrying {}: device_id={} device_name={} target={}:{}",
            "TLS" if first_tls else "plain",
            "plain" if first_tls else "TLS",
            vnc_session.get("device_id"),
            vnc_session.get("device_name"),
            vnc_session.get("host"),
            vnc_session.get("port"),
        )
        try:
            reader, writer, rfb_banner, vnc_mode = await open_vnc_connection(use_tls=second_tls)
        except Exception as exc:
            logger.warning(
                "device VNC {} fallback failed: device_id={} device_name={} target={}:{} error={}",
                "plain" if first_tls else "TLS",
                vnc_session.get("device_id"),
                vnc_session.get("device_name"),
                vnc_session.get("host"),
                vnc_session.get("port"),
                repr(exc),
            )
            await websocket.close(code=1011, reason=f"VNC handshake failed: {exc}"[:120])
            return
    except asyncio.IncompleteReadError as exc:
        logger.warning(
            "device VNC handshake incomplete: device_id={} device_name={} target={}:{} bytes={} error={}",
            vnc_session.get("device_id"),
            vnc_session.get("device_name"),
            vnc_session.get("host"),
            vnc_session.get("port"),
            len(exc.partial or b""),
            repr(exc),
        )
        await websocket.close(code=1011, reason="VNC service closed before RFB handshake")
        return
    except Exception as exc:
        logger.warning(
            "device VNC connect/handshake failed: device_id={} device_name={} target={}:{} error={}",
            vnc_session.get("device_id"),
            vnc_session.get("device_name"),
            vnc_session.get("host"),
            vnc_session.get("port"),
            repr(exc),
        )
        await websocket.close(code=1011, reason=f"VNC connect failed: {exc}"[:120])
        return

    logger.info(
        "device VNC RFB handshake ready: device_id={} device_name={} target={}:{} mode={} banner={!r}",
        vnc_session.get("device_id"),
        vnc_session.get("device_name"),
        vnc_session.get("host"),
        vnc_session.get("port"),
        vnc_mode,
        rfb_banner,
    )
    proxy_stats["vnc_bytes"] += len(rfb_banner)
    await websocket.send_bytes(rfb_banner)
    server_initial_bytes = bytearray(rfb_banner)
    server_init_logged = False

    def log_server_init_if_ready() -> bool:
        if len(server_initial_bytes) < 14:
            return False
        security_type_count = server_initial_bytes[12]
        security_types = list(server_initial_bytes[13 : 13 + security_type_count])
        if len(server_initial_bytes) < 13 + security_type_count:
            return False

        security_offset = 13 + security_type_count
        server_init_offsets = []
        if 2 in security_types:
            server_init_offsets.append(security_offset + 16 + 4)
        if 1 in security_types:
            server_init_offsets.append(security_offset + 4)

        for server_init_offset in server_init_offsets:
            if len(server_initial_bytes) < server_init_offset + 24:
                continue
            width = int.from_bytes(server_initial_bytes[server_init_offset : server_init_offset + 2], "big")
            height = int.from_bytes(server_initial_bytes[server_init_offset + 2 : server_init_offset + 4], "big")
            name_length = int.from_bytes(
                server_initial_bytes[server_init_offset + 20 : server_init_offset + 24],
                "big",
            )
            if len(server_initial_bytes) < server_init_offset + 24 + name_length:
                continue
            desktop_name = bytes(
                server_initial_bytes[server_init_offset + 24 : server_init_offset + 24 + name_length]
            ).decode("utf-8", errors="replace")
            logger.info(
                "device VNC server init: device_id={} target={}:{} mode={} security_types={} size={}x{} name={!r}",
                vnc_session.get("device_id"),
                vnc_session.get("host"),
                vnc_session.get("port"),
                vnc_mode,
                security_types,
                width,
                height,
                desktop_name,
            )
            return True
        return False

    async def client_to_vnc():
        while True:
            message = await websocket.receive()
            if message.get("type") == "websocket.disconnect":
                await close_vnc_writer(writer)
                return
            if message.get("bytes") is not None:
                proxy_stats["client_bytes"] += len(message["bytes"])
                writer.write(message["bytes"])
            elif message.get("text") is not None:
                data = message["text"].encode()
                proxy_stats["client_bytes"] += len(data)
                writer.write(data)
            await writer.drain()

    async def vnc_to_client():
        nonlocal server_init_logged
        while True:
            data = await reader.read(65535)
            if not data:
                await websocket.close()
                return
            proxy_stats["vnc_bytes"] += len(data)
            if not server_init_logged and len(server_initial_bytes) < 512:
                server_initial_bytes.extend(data[: 512 - len(server_initial_bytes)])
                server_init_logged = log_server_init_if_ready()
            await websocket.send_bytes(data)

    async def log_proxy_stats():
        while True:
            await asyncio.sleep(5)
            logger.info(
                "device VNC proxy stats: device_id={} target={}:{} client_bytes={} vnc_bytes={}",
                vnc_session.get("device_id"),
                vnc_session.get("host"),
                vnc_session.get("port"),
                proxy_stats["client_bytes"],
                proxy_stats["vnc_bytes"],
            )

    tasks = [
        asyncio.create_task(client_to_vnc()),
        asyncio.create_task(vnc_to_client()),
        asyncio.create_task(log_proxy_stats()),
    ]
    try:
        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for task in done:
            task.result()
        for task in pending:
            task.cancel()
    except (WebSocketDisconnect, websockets.ConnectionClosed):
        pass
    except Exception as exc:
        try:
            await websocket.close(code=1011, reason=str(exc)[:120])
        except Exception:
            pass
    finally:
        logger.info(
            "device VNC proxy closed: device_id={} target={}:{} client_bytes={} vnc_bytes={}",
            vnc_session.get("device_id"),
            vnc_session.get("host"),
            vnc_session.get("port"),
            proxy_stats["client_bytes"],
            proxy_stats["vnc_bytes"],
        )
        for task in tasks:
            task.cancel()
        await close_vnc_writer(writer)


@router.post("/device/redfish-probe", summary="根据IPMI地址采集Redfish设备信息")
async def redfish_probe_device(probe_in: AssetDeviceRedfishProbe):
    try:
        data = await collect_redfish_inventory(probe_in)
    except httpx.HTTPStatusError as exc:
        status_code = exc.response.status_code
        if status_code in {401, 403}:
            raise HTTPException(status_code=400, detail="Redfish认证失败，请检查IPMI账号密码") from exc
        raise HTTPException(status_code=400, detail=f"Redfish请求失败: HTTP {status_code}") from exc
    except httpx.RequestError as exc:
        raise HTTPException(status_code=400, detail=f"无法连接Redfish服务: {exc}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return Success(data=data)


@router.post("/device/power", summary="服务器电源控制")
async def device_power_control(payload: AssetDevicePowerRequest):
    try:
        device = await asset_device_controller.get(id=payload.device_id)
        config = device_ipmi_config(device, payload.node_name)
        data = await control_redfish_power(config, payload.action)
        data["device_id"] = device.id
        data["device_name"] = config.get("display_name") or device.name
        data["action"] = payload.action
    except httpx.HTTPStatusError as exc:
        status_code = exc.response.status_code
        if status_code in {401, 403}:
            raise HTTPException(status_code=400, detail="Redfish认证失败，请检查IPMI账号密码") from exc
        raise HTTPException(status_code=400, detail=f"Redfish电源操作失败: HTTP {status_code}") from exc
    except httpx.RequestError as exc:
        raise HTTPException(status_code=400, detail=f"无法连接Redfish服务: {exc}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return Success(data=data)


@router.post("/device/ipmi-logs", summary="查看服务器IPMI日志")
async def device_ipmi_logs(payload: AssetDeviceIpmiLogRequest):
    try:
        device = await asset_device_controller.get(id=payload.device_id)
        config = device_ipmi_config(device, payload.node_name)
        data = await collect_redfish_ipmi_logs(config, payload.limit)
        data["device_id"] = device.id
        data["device_name"] = config.get("display_name") or device.name
    except httpx.HTTPStatusError as exc:
        status_code = exc.response.status_code
        if status_code in {401, 403}:
            raise HTTPException(status_code=400, detail="Redfish认证失败，请检查IPMI账号密码") from exc
        raise HTTPException(status_code=400, detail=f"Redfish日志读取失败: HTTP {status_code}") from exc
    except httpx.RequestError as exc:
        raise HTTPException(status_code=400, detail=f"无法连接Redfish服务: {exc}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return Success(data=data)


@router.post("/device/create", summary="创建设备")
async def create_device(device_in: AssetDeviceCreate):
    error = await validate_device_u_range(device_in)
    if error:
        return Success(msg=error, code=400)
    await prepare_device_attributes_for_save(device_in)
    normalize_four_node_status_for_save(device_in)
    obj = await asset_device_controller.create_device(device_in)
    return Success(data=await device_to_dict(obj, can_view_secrets=await can_view_device_secrets()), msg="Created Successfully")


@router.post("/device/update", summary="更新设备")
async def update_device(device_in: AssetDeviceUpdate):
    error = await validate_device_u_range(device_in)
    if error:
        return Success(msg=error, code=400)
    await prepare_device_attributes_for_save(device_in)
    normalize_four_node_status_for_save(device_in)
    obj = await asset_device_controller.update_device(id=device_in.id, obj_in=device_in)
    return Success(data=await device_to_dict(obj, can_view_secrets=await can_view_device_secrets()), msg="Updated Successfully")


@router.delete("/device/delete", summary="删除设备")
async def delete_device(device_id: int = Query(...)):
    await asset_device_controller.remove(id=device_id)
    return Success(msg="Deleted Successfully")


@router.get("/inventory-category/list", summary="库存分类列表")
async def list_inventory_categories():
    return Success(data=await inventory_category_tree())


@router.post("/inventory-category/create", summary="创建库存分类")
async def create_inventory_category(category_in: AssetInventoryCategoryCreate):
    name = category_in.name.strip()
    if not name:
        return Success(msg="分类名称不能为空", code=400)
    parent_id = category_in.parent_id
    if parent_id is not None:
        parent = await AssetInventoryCategory.get_or_none(id=parent_id, parent_id=None)
        if not parent:
            return Success(msg="父级分类不存在", code=400)

    existed = await AssetInventoryCategory.get_or_none(name=name, parent_id=parent_id)
    if existed:
        return Success(msg="分类已存在", code=400)

    data = category_in.model_dump()
    data["name"] = name
    if not data.get("sort"):
        data["sort"] = await AssetInventoryCategory.filter(parent_id=parent_id).count() + 1
    await asset_inventory_category_controller.create(data)
    return Success(msg="Created Successfully", data=await inventory_category_tree())


@router.post("/inventory-category/update", summary="更新库存分类")
async def update_inventory_category(category_in: AssetInventoryCategoryUpdate):
    name = category_in.name.strip()
    if not name:
        return Success(msg="分类名称不能为空", code=400)
    existed = await AssetInventoryCategory.get_or_none(name=name, parent_id=category_in.parent_id)
    if existed and existed.id != category_in.id:
        return Success(msg="分类已存在", code=400)
    data = category_in.model_dump(exclude={"id"})
    data["name"] = name
    await asset_inventory_category_controller.update(id=category_in.id, obj_in=data)
    return Success(msg="Updated Successfully", data=await inventory_category_tree())


@router.delete("/inventory-category/delete", summary="删除库存分类")
async def delete_inventory_category(category_id: int = Query(...)):
    category = await asset_inventory_category_controller.get(id=category_id)
    if category.parent_id is None:
        await AssetInventoryCategory.filter(parent_id=category.id).delete()
    await category.delete()
    return Success(msg="Deleted Successfully", data=await inventory_category_tree())


@router.get("/inventory/list", summary="库存列表")
async def list_inventory(
    page: int = Query(1),
    page_size: int = Query(10),
    region_id: int | None = Query(None),
    location_id: int | None = Query(None),
    keyword: str = Query(""),
    type: str = Query(""),
    subtype: str = Query(""),
    status: bool | None = Query(None),
    only_low_stock: bool = Query(False),
    only_available: bool = Query(False),
    sort_by: str = Query(""),
    sort_order: str = Query(""),
):
    q = Q()
    if region_id is not None:
        q &= Q(region_id=region_id)
    if location_id is not None:
        q &= Q(location_id=location_id)
    if type:
        q &= Q(type__contains=type)
    if subtype:
        q &= Q(subtype__contains=subtype)
    if status is not None:
        q &= Q(status=status)
    order = get_inventory_order(sort_by, sort_order)
    if keyword or only_low_stock:
        matched_items = [
            item
            for item in await AssetInventory.filter(q).order_by(*order)
            if inventory_matches_keyword(item, keyword) and (not only_low_stock or is_low_inventory(item))
        ]
        total = len(matched_items)
        start = (page - 1) * page_size
        objs = matched_items[start : start + page_size]
    else:
        total, objs = await asset_inventory_controller.list_inventory(
            page=page,
            page_size=page_size,
            search=q,
            order=order,
        )
    data = [await inventory_to_dict(obj) for obj in objs]
    return SuccessExtra(data=data, total=total, page=page, page_size=page_size)


@router.get("/inventory/get", summary="库存详情")
async def get_inventory(inventory_id: int = Query(...)):
    obj = await asset_inventory_controller.get(id=inventory_id)
    return Success(data=await inventory_to_dict(obj))


@router.get("/inventory/export", summary="导出库存")
async def export_inventory():
    items = await AssetInventory.all().order_by("type", "subtype", "id")
    locations = await AssetLocation.all()
    regions = await AssetRegion.all()
    location_map = {location.id: location for location in locations}
    region_map = {region.id: region for region in regions}

    attribute_keys = []
    for item in items:
        for key in dict(item.attributes or {}).keys():
            if key not in attribute_keys:
                attribute_keys.append(key)

    headers = [
        "区域",
        "位置",
        "分类",
        "子类",
        "数量",
        "告警阈值",
        "成本价",
        "成本价币种",
        "默认售价",
        "默认售价币种",
        *[f"属性:{key}" for key in attribute_keys],
        "扩展属性(JSON)",
        "备注",
        "状态",
    ]

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(headers)
    for item in items:
        location = location_map.get(item.location_id)
        region = region_map.get(item.region_id)
        attributes = dict(item.attributes or {})
        writer.writerow(
            [
                region.name if region else "",
                location.name if location else "",
                item.type or "",
                item.subtype or "",
                item.quantity,
                item.threshold,
                item.cost_price,
                item.cost_price_currency or "USD",
                item.sale_price,
                item.sale_price_currency or "USD",
                *[attributes.get(key, "") for key in attribute_keys],
                json.dumps(attributes, ensure_ascii=False),
                item.remark or "",
                "启用" if item.status else "禁用",
            ]
        )

    output.seek(0)
    filename = "asset_inventory.csv"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.post("/inventory/import", summary="导入库存")
async def import_inventory(file: UploadFile = File(..., description="CSV文件")):
    if not file.filename.lower().endswith(".csv"):
        return Success(msg="请上传 CSV 文件", code=400)

    content = await file.read()
    try:
        decoded = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        try:
            decoded = content.decode("gbk")
        except UnicodeDecodeError:
            return Success(msg="文件编码不支持，请使用 UTF-8 或 GBK 编码", code=400)

    reader = csv.DictReader(io.StringIO(decoded))
    success_count = 0
    error_rows = []
    saved_items = []

    for row_num, row in enumerate(reader, start=2):
        try:
            location_id = await resolve_inventory_location_id(row)
            if not location_id:
                raise ValueError("库存位置不存在，请填写区域+位置")

            type_name = str(row.get("分类", "") or "").strip()
            if not type_name:
                raise ValueError("分类不能为空")

            quantity_text = str(row.get("数量", "") or "0").strip()
            quantity = int(quantity_text) if quantity_text else 0
            threshold_text = str(row.get("告警阈值", "") or "0").strip()
            threshold = int(threshold_text) if threshold_text else 0
            cost_price_text = str(row.get("成本价", "") or "0").strip()
            sale_price_text = str(row.get("默认售价", "") or "0").strip()
            cost_price = float(cost_price_text) if cost_price_text else 0
            sale_price = float(sale_price_text) if sale_price_text else 0
            cost_price_currency = str(row.get("成本价币种", "") or "USD").strip().upper()
            sale_price_currency = str(row.get("默认售价币种", "") or "USD").strip().upper()
            attributes = parse_inventory_attributes(row)
            inventory_data = {
                "location_id": location_id,
                "type": type_name,
                "subtype": str(row.get("子类", "") or "").strip(),
                "quantity": quantity,
                "threshold": threshold,
                "cost_price": cost_price,
                "cost_price_currency": cost_price_currency or "USD",
                "sale_price": sale_price,
                "sale_price_currency": sale_price_currency or "USD",
                "attributes": attributes,
                "remark": str(row.get("备注", "") or "").strip(),
                "status": parse_bool_status(row.get("状态"), default=True),
            }

            existed = await AssetInventory.get_or_none(
                location_id=location_id,
                type=inventory_data["type"],
                subtype=inventory_data["subtype"],
            )
            if existed:
                saved_item = await asset_inventory_controller.update_inventory(
                    id=existed.id,
                    obj_in=AssetInventoryUpdate(id=existed.id, **inventory_data),
                )
            else:
                saved_item = await asset_inventory_controller.create_inventory(AssetInventoryCreate(**inventory_data))
            saved_items.append(saved_item)
            success_count += 1
        except Exception as exc:
            error_rows.append(f"第{row_num}行: {exc}")

    await send_inventory_threshold_alert(saved_items)

    msg = f"导入成功 {success_count} 条"
    if error_rows:
        msg += f"，错误: {'; '.join(error_rows[:5])}"
        if len(error_rows) > 5:
            msg += f" 等 {len(error_rows)} 条"
    return Success(msg=msg, data={"success_count": success_count, "errors": error_rows})


@router.post("/inventory/create", summary="创建库存")
async def create_inventory(inventory_in: AssetInventoryCreate):
    obj = await asset_inventory_controller.create_inventory(inventory_in)
    await send_inventory_threshold_alert([obj])
    return Success(msg="Created Successfully", data=await inventory_to_dict(obj))


@router.post("/inventory/update", summary="更新库存")
async def update_inventory(inventory_in: AssetInventoryUpdate):
    obj = await asset_inventory_controller.update_inventory(id=inventory_in.id, obj_in=inventory_in)
    await send_inventory_threshold_alert([obj])
    return Success(msg="Updated Successfully", data=await inventory_to_dict(obj))


@router.delete("/inventory/delete", summary="删除库存")
async def delete_inventory(inventory_id: int = Query(...)):
    await asset_inventory_controller.remove(id=inventory_id)
    return Success(msg="Deleted Successfully")


@router.get("/inventory-sale/list", summary="库存销售单列表")
async def list_inventory_sales(
    page: int = Query(1),
    page_size: int = Query(10),
    keyword: str = Query(""),
    status: int | None = Query(None),
):
    q = Q()
    if keyword:
        q &= Q(sale_no__contains=keyword) | Q(customer_name__contains=keyword) | Q(customer_contact__contains=keyword)
    if status is not None:
        q &= Q(status=status)
    query = AssetInventorySaleOrder.filter(q).order_by("-created_at", "-id")
    total = await query.count()
    objs = await query.offset((page - 1) * page_size).limit(page_size)
    data = [await sale_order_to_dict(obj, include_items=True) for obj in objs]
    return SuccessExtra(data=data, total=total, page=page, page_size=page_size)


@router.post("/inventory-sale/create", summary="创建库存销售单")
async def create_inventory_sale(sale_in: AssetInventorySaleCreate):
    if not sale_in.items:
        return Success(msg="请至少选择一个销售明细", code=400)

    try:
        async with in_transaction():
            sale_no = await generate_sale_no()
            total_amount = sum(item.quantity * item.unit_price for item in sale_in.items)
            order = await AssetInventorySaleOrder.create(
                sale_no=sale_no,
                customer_name=sale_in.customer_name.strip(),
                customer_contact=sale_in.customer_contact.strip(),
                sale_date=sale_in.sale_date or date.today(),
                status=1,
                total_amount=total_amount,
                remark=sale_in.remark.strip(),
                created_by=CTX_USER_ID.get(),
            )

            changed_inventory: list[AssetInventory] = []
            for item_in in sale_in.items:
                inventory = await AssetInventory.get(id=item_in.inventory_id)
                if not inventory.status:
                    raise ValueError(f"{inventory.type}/{inventory.subtype or '-'} 已禁用，不能售卖")
                if inventory.quantity < item_in.quantity:
                    raise ValueError(
                        f"{inventory.type}/{inventory.subtype or '-'} 库存不足，当前 {inventory.quantity}，需要 {item_in.quantity}"
                    )

                quantity_before = inventory.quantity
                inventory.quantity -= item_in.quantity
                await inventory.save(update_fields=["quantity", "updated_at"])
                amount = item_in.quantity * item_in.unit_price
                await AssetInventorySaleItem.create(
                    sale_order_id=order.id,
                    inventory_id=inventory.id,
                    type=inventory.type,
                    subtype=inventory.subtype or "",
                    quantity=item_in.quantity,
                    cost_price=inventory.cost_price,
                    cost_price_currency=inventory.cost_price_currency or "USD",
                    unit_price=item_in.unit_price,
                    unit_price_currency=inventory.sale_price_currency or "USD",
                    amount=amount,
                    remark=item_in.remark.strip(),
                )
                await create_stock_flow(
                    inventory=inventory,
                    flow_type="sale",
                    quantity_before=quantity_before,
                    quantity_change=-item_in.quantity,
                    quantity_after=inventory.quantity,
                    biz_type="sale_order",
                    biz_id=order.id,
                    remark=f"销售单 {sale_no}",
                )
                changed_inventory.append(inventory)
    except ValueError as exc:
        return Success(msg=str(exc), code=400)

    await send_inventory_threshold_alert(changed_inventory)
    return Success(msg="销售单创建成功", data=await sale_order_to_dict(order))


@router.post("/inventory-sale/cancel", summary="取消库存销售单")
async def cancel_inventory_sale(cancel_in: AssetInventorySaleCancel):
    async with in_transaction():
        order = await AssetInventorySaleOrder.get(id=cancel_in.id)
        if order.status == 2:
            return Success(msg="销售单已取消", data=await sale_order_to_dict(order))

        items = await AssetInventorySaleItem.filter(sale_order_id=order.id)
        for item in items:
            inventory = await AssetInventory.get(id=item.inventory_id)
            quantity_before = inventory.quantity
            inventory.quantity += item.quantity
            await inventory.save(update_fields=["quantity", "updated_at"])
            await create_stock_flow(
                inventory=inventory,
                flow_type="sale_cancel",
                quantity_before=quantity_before,
                quantity_change=item.quantity,
                quantity_after=inventory.quantity,
                biz_type="sale_order",
                biz_id=order.id,
                remark=cancel_in.reason.strip() or f"取消销售单 {order.sale_no}",
            )

        order.status = 2
        order.canceled_at = datetime.now()
        order.canceled_by = CTX_USER_ID.get()
        order.cancel_reason = cancel_in.reason.strip()
        await order.save(update_fields=["status", "canceled_at", "canceled_by", "cancel_reason", "updated_at"])

    return Success(msg="销售单已取消", data=await sale_order_to_dict(order))


@router.get("/inventory-flow/list", summary="库存流水列表")
async def list_inventory_flows(
    page: int = Query(1),
    page_size: int = Query(20),
    inventory_id: int | None = Query(None),
    flow_type: str = Query(""),
):
    q = Q()
    if inventory_id is not None:
        q &= Q(inventory_id=inventory_id)
    if flow_type:
        q &= Q(flow_type=flow_type)
    query = AssetInventoryStockFlow.filter(q).order_by("-created_at", "-id")
    total = await query.count()
    objs = await query.offset((page - 1) * page_size).limit(page_size)
    data = [await stock_flow_to_dict(obj) for obj in objs]
    return SuccessExtra(data=data, total=total, page=page, page_size=page_size)
