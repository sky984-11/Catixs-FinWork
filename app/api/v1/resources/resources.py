import asyncio
import hashlib
import hmac
import json
import os
import time
from collections import defaultdict
from datetime import datetime
from typing import Any

import httpx
from fastapi import APIRouter, Body, Query
from pydantic import BaseModel, Field

from app.log import logger
from app.models.asset import AssetDevice
from app.schemas.base import Success
from app.settings.config import settings

router = APIRouter()

IPXO_TOKEN_URL = "https://hydra.ipxo.com/oauth2/token"
IPXO_API_BASE = "https://apigw.ipxo.com"
IPINFO_API_BASE = "https://ipinfo.io"
IPINFO_BATCH_API_BASE = "https://api.ipinfo.io"
ZENLAYER_PRODUCT_SDN = "sdn"
IPXO_RESOURCES_CACHE_TTL = 300
EQUINIX_DEFAULT_API_BASE = "https://api.equinix.com"


class FreeDeviceSellRequest(BaseModel):
    device_id: int = Field(..., description="设备ID")
    description: str = Field(..., description="出售/交付描述")
    node_name: str | None = Field(None, description="四合一节点名称")

_ipxo_token = ""
_ipxo_token_expire_at = 0.0
_equinix_token = ""
_equinix_token_expire_at = 0.0
_ip_geo_cache: dict[str, dict] = {}
_ipxo_resources_cache: dict[str, tuple[float, dict]] = {}


def text(value: Any, default: str = "") -> str:
    value = "" if value is None else str(value).strip()
    return value or default


def number(value: Any, default: float = 0) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return default


def round_money(value: Any) -> float:
    return round(number(value), 2)


def normalized_country_code(value: Any) -> str:
    code = text(value).upper()
    return code if code.isalpha() and 2 <= len(code) <= 3 else ""


def pick(data: dict, *keys: str, default: Any = "") -> Any:
    for key in keys:
        value: Any = data
        for part in key.split("."):
            if not isinstance(value, dict):
                value = None
                break
            value = value.get(part)
        if value not in (None, ""):
            return value
    return default


def normalize_attribute_dict(attributes: Any) -> dict:
    if isinstance(attributes, dict):
        return {text(key): value for key, value in attributes.items() if text(key)}
    if isinstance(attributes, str):
        try:
            data = json.loads(attributes)
        except json.JSONDecodeError:
            return {}
        return {text(key): value for key, value in data.items() if text(key)} if isinstance(data, dict) else {}
    return {}


DEVICE_CONFIG_ATTRIBUTE_ALIASES = {
    "CPU型号": ("CPU Model", "cpu_model", "processor", "Processor"),
    "CPU数量": ("CPU颗数", "cpu_count"),
    "CPU核心数": ("CPU Cores", "cpu_cores", "cores"),
    "内存总数": ("内存容量", "内存大小", "内存", "memory", "Memory", "ram", "RAM"),
    "磁盘总数": (
        "磁盘",
        "硬盘",
        "硬盘容量",
        "磁盘容量",
        "磁盘大小",
        "硬盘大小",
        "storage",
        "Storage",
        "disk",
        "Disk",
        "disk_size",
        "disk_capacity",
    ),
}


DISK_CONFIG_KEYS = (
    "磁盘总数",
    "硬盘总数",
    "磁盘",
    "硬盘",
    "硬盘容量",
    "磁盘容量",
    "磁盘大小",
    "硬盘大小",
    "storage",
    "Storage",
    "disk",
    "Disk",
    "disks",
    "Disks",
    "disk_size",
    "disk_capacity",
    "disk_total",
    "diskTotal",
    "storage_total",
    "storageTotal",
    "storage_size",
    "storageSize",
    "drive",
    "drives",
    "hdd",
    "ssd",
    "nvme",
    "raid",
    "legacy_disk",
)


CPU_MODEL_CORE_COUNTS = {
    "intel xeon gold 5118": "12",
    "intel xeon gold 6138": "20",
    "intel(r) xeon(r) gold 6138": "20",
    "intel xeon gold 6148": "20",
    "intel(r) xeon(r) gold 6148": "20",
    "intel xeon platinum 8272cl": "26",
    "intel xeon e5-2698 v3": "16",
    "intel xeon e5-2680 v4": "14",
    "intel xeon e5-2640 v4": "10",
    "intel xeon e5-2640": "10",
    "amd epyc 7542": "32",
}


def infer_cpu_cores_from_model(value: Any) -> str:
    model = text(value)
    if not model:
        return ""
    import re

    explicit = re.search(r"\b(\d+)\s*[- ]?\s*core\b", model, re.IGNORECASE)
    if explicit:
        return explicit.group(1)
    normalized = " ".join(model.lower().replace("(r)", "").split())
    for key, cores in CPU_MODEL_CORE_COUNTS.items():
        normalized_key = " ".join(key.lower().replace("(r)", "").split())
        if normalized_key in normalized:
            return cores
    return ""


def normalize_device_config_attributes(attributes: Any) -> dict:
    result = normalize_attribute_dict(attributes)
    for standard_key, aliases in DEVICE_CONFIG_ATTRIBUTE_ALIASES.items():
        standard_value = text(result.get(standard_key))
        for alias in aliases:
            alias_value = text(result.get(alias))
            if not standard_value and alias_value:
                standard_value = alias_value
            result.pop(alias, None)
        if standard_value:
            result[standard_key] = standard_value
        else:
            result.pop(standard_key, None)
    return result


def format_device_config(attributes: dict) -> str:
    attrs = normalize_device_config_attributes(attributes)
    cpu = pick(attrs, "CPU型号", "CPU Model", "cpu_model", "processor", "Processor")
    cpu_count = pick(attrs, "CPU数量", "CPU颗数", "cpu_count")
    cpu_cores = pick(attrs, "CPU核心数", "CPU Cores", "cpu_cores", "cores") or infer_cpu_cores_from_model(cpu)
    memory = pick(attrs, "内存总数", "内存容量", "内存大小", "内存", "memory", "Memory")
    disk = pick(attrs, *DISK_CONFIG_KEYS)
    parts = []
    if cpu_count or cpu:
        parts.append(" / ".join(item for item in [text(cpu_count), text(cpu)] if item))
    if cpu_cores:
        parts.append(f"{text(cpu_cores)}核")
    if memory:
        parts.append(text(memory))
    if disk:
        parts.append(text(disk))
    return " | ".join(parts)


def format_four_node_config(node: dict) -> str:
    node_data = node if isinstance(node, dict) else {}
    cpu_model = text(node_data.get("cpu_model") or node_data.get("cpuModel") or node_data.get("cpu"))
    cpu_cores = node_data.get("cpu_cores") or node_data.get("cpuCores") or infer_cpu_cores_from_model(cpu_model)
    memory = pick(node_data, "memory", "Memory", "ram", "RAM", "内存总数", "内存容量", "内存大小", "内存")
    disk = pick(node_data, *DISK_CONFIG_KEYS)
    cpu_parts = [
        f"{node_data.get('cpu_count')}颗" if node_data.get("cpu_count") not in (None, "") else "",
        cpu_model,
        f"{cpu_cores}核" if cpu_cores not in (None, "") else "",
    ]
    parts = [" / ".join(item for item in cpu_parts if item)]
    for value in (memory, disk):
        if text(value):
            parts.append(text(value))
    return " | ".join(item for item in parts if item)


def node_config_attributes(node: dict) -> dict:
    node_data = node if isinstance(node, dict) else {}
    cpu_model = text(node_data.get("cpu_model") or node_data.get("cpuModel") or node_data.get("cpu"))
    cpu_count = node_data.get("cpu_count") or node_data.get("cpuCount")
    cpu_cores = node_data.get("cpu_cores") or node_data.get("cpuCores") or infer_cpu_cores_from_model(cpu_model)
    memory = pick(node_data, "memory", "Memory", "ram", "RAM", "内存总数", "内存容量", "内存大小", "内存")
    disk = pick(node_data, *DISK_CONFIG_KEYS)
    result = {}
    if cpu_model:
        result["CPU型号"] = cpu_model
    if cpu_count not in (None, ""):
        result["CPU数量"] = text(cpu_count)
    if cpu_cores not in (None, ""):
        result["CPU核心数"] = text(cpu_cores)
    if text(memory):
        result["内存总数"] = text(memory)
    if text(disk):
        result["磁盘总数"] = text(disk)
    return result


def is_four_node_device(attributes: dict) -> bool:
    attrs = attributes if isinstance(attributes, dict) else {}
    nodes = attrs.get("nodes")
    return (
        attrs.get("form_factor") == "four_node"
        or attrs.get("设备形态") == "四合一服务器"
        or attrs.get("设备形态") == "四节点服务器"
        or text(attrs.get("node_count") or attrs.get("节点数量")) == "4"
        or (isinstance(nodes, list) and len([node for node in nodes if isinstance(node, dict)]) >= 4)
    )


def normalize_four_node_list(attributes: dict) -> list[dict]:
    attrs = attributes if isinstance(attributes, dict) else {}
    nodes = attrs.get("nodes") if isinstance(attrs.get("nodes"), list) else []
    if is_four_node_device(attrs):
        normalized = [node for node in nodes if isinstance(node, dict)]
        result = []
        for index in range(1, 5):
            node = normalized[index - 1] if index <= len(normalized) else {}
            result.append({"name": f"Node {index}", **node})
        return result
    if nodes:
        return [node for node in nodes if isinstance(node, dict)]
    return []


def normalize_device_status(value, default: int = 0) -> int:
    try:
        status = int(value)
    except (TypeError, ValueError):
        return default
    return status if status in {0, 1, 2, 3, 4} else default


def is_free_device_status(value: Any) -> bool:
    try:
        return int(value) == 0
    except (TypeError, ValueError):
        return False


def device_to_card_row(device: AssetDevice) -> dict:
    attrs = normalize_device_config_attributes(device.attributes)
    if not text(attrs.get("CPU核心数")):
        inferred_cpu_cores = infer_cpu_cores_from_model(attrs.get("CPU型号"))
        if inferred_cpu_cores:
            attrs = {**attrs, "CPU核心数": inferred_cpu_cores}
    cabinet = device.cabinet
    location = device.location
    region = device.region
    return {
        "id": device.id,
        "asset_no": device.asset_no,
        "name": device.name,
        "brand": device.brand or "",
        "model": device.model or "",
        "serial_no": device.serial_no or "",
        "mgmt_ip": device.mgmt_ip or "",
        "business_ip": device.business_ip or "",
        "u_position": device.u_position,
        "u_height": device.u_height,
        "status": normalize_device_status(device.status, 0),
        "cabinet": cabinet.name if cabinet else "",
        "location": location.name if location else "",
        "region": region.name if region else "",
        "country": region.country if region else "",
        "city": region.city if region else "",
        "config": format_device_config(attrs),
        "attributes": attrs,
        "remark": device.remark or "",
    }


def device_to_sales_rows(device: AssetDevice) -> list[dict]:
    row = device_to_card_row(device)
    attrs = row["attributes"]
    nodes = normalize_four_node_list(attrs)
    if not nodes or not is_four_node_device(attrs):
        return [row]

    rows = []
    for index, node in enumerate(nodes[:4], start=1):
        node_status = normalize_device_status(node.get("status"), 0)
        node_name = text(node.get("name"), f"Node {index}")
        display_name = text(node.get("device_name"), f"{row['name']}-{node_name}")
        node_attrs = node_config_attributes(node)
        rows.append(
            {
                **row,
                "id": f"{row['id']}:{node_name}",
                "parent_id": row["id"],
                "asset_no": f"{row['asset_no']}-{node_name}" if row["asset_no"] else node_name,
                "name": display_name,
                "serial_no": text(node.get("serial_no"), row["serial_no"]),
                "mgmt_ip": text(node.get("mgmt_ip") or node.get("ipmi_host"), row["mgmt_ip"]),
                "business_ip": text(node.get("business_ip"), row["business_ip"]),
                "config": format_four_node_config(node) or row["config"],
                "attributes": {**row["attributes"], **node_attrs},
                "node_attributes": node,
                "remark": text(node.get("remark"), row["remark"]),
                "status": node_status,
                "node_name": node_name,
                "parent_name": row["name"],
                "is_four_node": True,
            }
        )
    return rows


def aggregate_sales_device_status(nodes: list[dict]) -> int:
    statuses = [normalize_device_status(node.get("status"), 0) for node in nodes if isinstance(node, dict)]
    if not statuses:
        return 0
    if all(status == 4 for status in statuses):
        return 4
    if any(status == 3 for status in statuses):
        return 3
    if any(status == 2 for status in statuses):
        return 2
    if any(status == 0 for status in statuses):
        return 0
    if any(status == 1 for status in statuses):
        return 1
    return statuses[0]


def append_device_remark(remark: str | None, description: str) -> str:
    sold_line = f"出售记录：{description}"
    current = text(remark).strip()
    return f"{current}\n{sold_line}" if current else sold_line


@router.get("/free-devices", summary="空闲设备销售看板")
async def free_devices(
    region_id: int | None = Query(None, description="地区ID"),
    keyword: str = Query("", description="设备名称、型号、资产编号"),
):
    query = AssetDevice.filter(type=0).select_related("region", "location", "cabinet")
    if region_id:
        query = query.filter(region_id=region_id)
    rows = await query.order_by("region__name", "location__name", "cabinet__name", "u_position", "name")

    keyword_text = keyword.strip().lower()
    groups: dict[str, dict] = {}
    for device in rows:
        group_key = str(getattr(device.region, "id", 0) or 0)
        if group_key not in groups:
            region = device.region
            groups[group_key] = {
                "region_id": getattr(region, "id", None),
                "region": getattr(region, "name", "") or "未设置地区",
                "country": getattr(region, "country", "") or "",
                "city": getattr(region, "city", "") or "",
                "count": 0,
                "models": defaultdict(int),
                "locations": defaultdict(int),
                "devices": [],
            }
        group = groups[group_key]
        for row in device_to_sales_rows(device):
            if not is_free_device_status(row.get("status")):
                continue
            if keyword_text:
                haystack = " ".join(
                    str(row.get(key) or "")
                    for key in [
                        "asset_no",
                        "name",
                        "brand",
                        "model",
                        "serial_no",
                        "mgmt_ip",
                        "business_ip",
                        "config",
                        "node_name",
                        "parent_name",
                    ]
                ).lower()
                if keyword_text not in haystack:
                    continue
            group["count"] += 1
            if row["model"]:
                group["models"][row["model"]] += 1
            if row["location"]:
                group["locations"][row["location"]] += 1
            group["devices"].append(row)

    result = []
    for group in groups.values():
        if not group["count"]:
            continue
        result.append(
            {
                **{key: group[key] for key in ["region_id", "region", "country", "city", "count", "devices"]},
                "models": [{"name": key, "count": value} for key, value in sorted(group["models"].items())],
                "locations": [{"name": key, "count": value} for key, value in sorted(group["locations"].items())],
            }
        )
    result.sort(key=lambda item: (-item["count"], item["region"]))
    summary = {
        "total": sum(item["count"] for item in result),
        "regions": len(result),
        "models": sorted({model["name"] for item in result for model in item["models"] if model["name"]}),
    }
    return Success(data={"summary": summary, "regions": result})


@router.post("/free-devices/sell", summary="出售空闲设备")
async def sell_free_device(payload: FreeDeviceSellRequest):
    description = text(payload.description).strip()
    if not description:
        return Success(code=400, msg="请填写机器描述")

    device = await AssetDevice.get_or_none(id=payload.device_id)
    if not device:
        return Success(code=404, msg="设备不存在")

    attrs = normalize_attribute_dict(device.attributes)
    sold_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    node_name = text(payload.node_name).strip()

    if node_name:
        nodes = normalize_four_node_list(attrs)
        matched = False
        for node in nodes:
            if text(node.get("name")) == node_name:
                if not is_free_device_status(node.get("status")):
                    return Success(code=400, msg="该节点不是空闲状态")
                node["status"] = 1
                node["sale_description"] = description
                node["sold_at"] = sold_at
                matched = True
                break
        if not matched:
            return Success(code=404, msg="四合一节点不存在")
        attrs["nodes"] = nodes
        attrs.setdefault("sale_records", []).append({
            "node_name": node_name,
            "description": description,
            "sold_at": sold_at,
        })
        device.status = aggregate_sales_device_status(nodes)
        device.attributes = attrs
        await device.save(update_fields=["status", "attributes", "updated_at"])
        return Success(msg="节点已出售", data=device_to_sales_rows(device))

    if not is_free_device_status(device.status):
        return Success(code=400, msg="设备不是空闲状态")

    attrs["sale_description"] = description
    attrs["sold_at"] = sold_at
    attrs.setdefault("sale_records", []).append({
        "description": description,
        "sold_at": sold_at,
    })
    device.status = 1
    device.attributes = attrs
    device.remark = append_device_remark(device.remark, description)
    await device.save(update_fields=["status", "attributes", "remark", "updated_at"])
    return Success(msg="设备已出售", data=device_to_card_row(device))


def sha256_hex(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def zenlayer_json_payload(payload: dict | None) -> str:
    return json.dumps(payload or {}, ensure_ascii=False, separators=(",", ":"))


async def zenlayer_request(product: str, action: str, payload: dict | None = None) -> tuple[int, dict]:
    access_key = text(settings.ZENLAYER_ACCESS_KEY_ID)
    access_secret = text(settings.ZENLAYER_ACCESS_KEY_PASSWORD)
    if not access_key or not access_secret:
        return 400, {"error": "Zenlayer credentials are not configured"}

    body = zenlayer_json_payload(payload)
    body_bytes = body.encode("utf-8")
    timestamp = str(int(time.time()))
    content_type = "application/json; charset=utf-8"
    host = "console.zenlayer.com"
    signed_headers = "content-type;host"
    canonical_headers = f"content-type:{content_type}\nhost:{host}\n"
    canonical_request = "\n".join(["POST", "/", "", canonical_headers, signed_headers, sha256_hex(body_bytes)])
    string_to_sign = "\n".join(
        ["ZC2-HMAC-SHA256", timestamp, sha256_hex(canonical_request.encode("utf-8"))]
    )
    signature = hmac.new(access_secret.encode("utf-8"), string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()
    headers = {
        "Authorization": f"ZC2-HMAC-SHA256 Credential={access_key}, SignedHeaders={signed_headers}, Signature={signature}",
        "Content-Type": content_type,
        "Host": host,
        "X-ZC-Action": action,
        "X-ZC-Timestamp": timestamp,
        "X-ZC-Signature-Method": "ZC2-HMAC-SHA256",
        "X-ZC-Version": text(settings.ZENLAYER_SDN_VERSION, "2026-04-01"),
    }
    url = f"{text(settings.ZENLAYER_API_BASE, 'https://console.zenlayer.com/api/v2').rstrip('/')}/{product}"
    async with httpx.AsyncClient(timeout=25.0, trust_env=False) as client:
        response = await client.post(url, content=body_bytes, headers=headers)
    try:
        data = response.json()
    except ValueError:
        data = {"raw": response.text[:2000]}
    return response.status_code, data if isinstance(data, dict) else {"raw": data}


def zenlayer_response_body(data: dict) -> dict:
    if isinstance(data.get("response"), dict):
        return data["response"]
    return data


def zenlayer_error(data: dict) -> str:
    body = zenlayer_response_body(data)
    error = body.get("error") if isinstance(body.get("error"), dict) else {}
    return text(
        pick(error, "message", "code")
        or body.get("message")
        or data.get("message")
        or data.get("error")
        or ""
    )


def normalize_datacenter(item: dict) -> dict:
    dc_id = text(pick(item, "dcId", "id"))
    name = text(pick(item, "dcName", "name"), dc_id)
    city = text(pick(item, "cityName", "city"))
    area = text(pick(item, "areaName", "area"))
    country = text(pick(item, "countryName", "country", "countryCode"))
    address = text(pick(item, "dcAddress", "address", "location", "siteAddress"))
    display_parts = [value for value in [name if name != dc_id else "", city, area] if value]
    return {
        "dcId": dc_id,
        "dcName": name,
        "label": " / ".join(display_parts) or dc_id,
        "cityName": city,
        "areaName": area,
        "countryName": country,
        "address": address,
        "status": text(pick(item, "status", "state")),
        "provider": text(pick(item, "provider", "vendor"), "Zenlayer"),
        "serviceTypes": item.get("serviceTypes") or [],
        "raw": item,
    }


def fallback_datacenters() -> list[dict]:
    rows = [
        {"dcId": "SIN1", "dcName": "Equinix SG1", "cityName": "Singapore", "areaName": "Asia"},
        {"dcId": "HKG1", "dcName": "Equinix HK1", "cityName": "Hong Kong", "areaName": "Asia"},
        {"dcId": "TYO1", "dcName": "Tokyo", "cityName": "Tokyo", "areaName": "Asia"},
        {"dcId": "LAX1", "dcName": "Los Angeles", "cityName": "Los Angeles", "areaName": "North America"},
        {"dcId": "LON1", "dcName": "London", "cityName": "London", "areaName": "Europe"},
    ]
    return [normalize_datacenter(item) for item in rows]


def extract_datacenters(data: dict) -> list[dict]:
    body = zenlayer_response_body(data)
    rows = (
        body.get("dataSet")
        or body.get("dcSet")
        or body.get("datacenters")
        or body.get("dataCenters")
        or body.get("items")
        or body.get("list")
        or []
    )
    if isinstance(rows, dict):
        rows = rows.get("items") or rows.get("dataSet") or []
    if not isinstance(rows, list):
        return []
    return [normalize_datacenter(item) for item in rows if isinstance(item, dict) and text(pick(item, "dcId", "id"))]


def normalize_zenlayer_price(price: Any) -> dict:
    if not isinstance(price, dict):
        return {"original": round_money(price), "discount": round_money(price), "charge_unit": "", "raw": price}
    original = pick(price, "originalPrice", "unitPrice", "price", "amount", default=0)
    discount = pick(price, "discountPrice", "discountUnitPrice", "unitPrice", "originalPrice", "price", "amount", default=0)
    return {
        "original": round_money(original),
        "discount": round_money(discount),
        "charge_unit": text(pick(price, "chargeUnit", "unit", "period")),
        "currency": text(pick(price, "currency", "currencyCode"), "USD"),
        "raw": price,
    }


def price_cost_item(name: str, price: Any, stock: Any = None) -> dict | None:
    normalized = normalize_zenlayer_price(price)
    cost = normalized["discount"] or normalized["original"]
    if not cost:
        return None
    return {
        "name": name,
        "supplier_price": normalized["original"] or cost,
        "quote_cost": cost,
        "suggest_20": round_money(cost * 1.2),
        "suggest_30": round_money(cost * 1.3),
        "suggest_40": round_money(cost * 1.4),
        "margin_30": round_money(cost / 0.7),
        "unit": normalized.get("charge_unit") or "MONTH",
        "currency": normalized.get("currency") or "USD",
        "stock": stock,
        "raw": normalized["raw"],
    }


def build_zenlayer_cost_items(service: str, body: dict) -> list[dict]:
    if service == "datacenter_port":
        candidates = [
            ("datacenter_port", "price"),
            ("cross_connect_monthly", "crossConnectPrice"),
            ("cross_connect_setup", "crossConnectOneTimeConstructionPrice"),
        ]
    else:
        candidates = [
            ("private_connect_bandwidth", "price"),
            ("endpoint_a_access", "endpointAPrice.price"),
            ("endpoint_a_cross_connect_monthly", "endpointAPrice.crossConnectPrice"),
            ("endpoint_a_cross_connect_setup", "endpointAPrice.crossConnectOneTimeConstructionPrice"),
            ("endpoint_z_access", "endpointZPrice.price"),
            ("endpoint_z_cross_connect_monthly", "endpointZPrice.crossConnectPrice"),
            ("endpoint_z_cross_connect_setup", "endpointZPrice.crossConnectOneTimeConstructionPrice"),
            ("cloud_router_bandwidth", "bandwidthPrice"),
            ("cloud_onramp_access", "cloudOnrampPrice"),
            ("ip_transit", "ipTransitPrice"),
        ]
    stock = pick(body, "stock", "endpointAPrice.stock", "endpointZPrice.stock", default=None)
    items = []
    for name, key in candidates:
        item = price_cost_item(name, pick(body, key, default=None), stock)
        if item:
            items.append(item)
    if not items and isinstance(body.get("price"), dict):
        item = price_cost_item("quote_cost", body["price"], body.get("stock"))
        if item:
            items.append(item)
    return items


def endpoint_payload(dc_id: str, port_type: str, assisted: bool) -> dict:
    return {
        "endpointType": "DATACENTER_PORT",
        "dcId": dc_id,
        "portType": port_type,
        "buildCrossConnectWithAssisted": assisted,
    }


def zenlayer_service_level(value: Any) -> str:
    level = text(value).upper()
    if level in {"SINGLE_PROTECTED", "SINGLE_UNPROTECTED"}:
        return level
    legacy_map = {
        "PLATINUM": "SINGLE_PROTECTED",
        "GOLD": "SINGLE_UNPROTECTED",
        "SILVER": "SINGLE_UNPROTECTED",
        "BRONZE": "SINGLE_UNPROTECTED",
    }
    return legacy_map.get(level, "SINGLE_UNPROTECTED")


@router.get("/zenlayer-pricing", summary="Zenlayer SDN报价选项")
async def zenlayer_pricing():
    errors = []
    datacenters = []
    if text(settings.ZENLAYER_ACCESS_KEY_ID) and text(settings.ZENLAYER_ACCESS_KEY_PASSWORD):
        try:
            status, data = await zenlayer_request(ZENLAYER_PRODUCT_SDN, "DescribeDatacenters", {"isPortAvailable": True})
        except Exception as exc:
            logger.exception("zenlayer datacenter request failed")
            errors.append({"action": "DescribeDatacenters", "error": str(exc)})
        else:
            if status >= 400 or zenlayer_error(data):
                errors.append({"action": "DescribeDatacenters", "status": status, "data": data})
            else:
                datacenters = extract_datacenters(data)

    source = "zenlayer_api" if datacenters else "fallback"
    datacenters = datacenters or fallback_datacenters()
    return Success(
        data={
            "source": source,
            "account": text(settings.ZENLAYER_ACCOUNT_EMAIL),
            "services": [
                {"label": "机房端口", "value": "datacenter_port"},
                {"label": "二层专线", "value": "private_connect"},
                {"label": "已有二层专线升级带宽", "value": "private_connect_bandwidth"},
            ],
            "datacenters": datacenters,
            "portTypes": ["1G", "10G", "40G"],
            "bandwidthOptions": [10, 50, 100, 200, 500, 1000, 2000, 5000, 10000],
            "internetTypes": [
                {"label": "固定带宽", "value": "ByBandwidth"},
                {"label": "95计费", "value": "ByInstanceBandwidth95"},
            ],
            "errors": errors,
        }
    )


@router.post("/zenlayer-pricing/quote", summary="Zenlayer SDN生成报价")
async def zenlayer_quote(payload: dict = Body(default_factory=dict)):
    service = text(payload.get("service"), "datacenter_port")
    dc_id = text(payload.get("dcId"))
    endpoint_a = text(payload.get("endpointA") or payload.get("sourceDcId"))
    endpoint_z = text(payload.get("endpointZ") or payload.get("destinationDcId"))
    port_type = text(payload.get("portType"), "10G")
    bandwidth = int(number(payload.get("bandwidthMbps"), 10))
    internet_type = text(payload.get("internetType"), "ByBandwidth")
    service_level = zenlayer_service_level(payload.get("serviceLevel"))
    assisted = bool(payload.get("buildCrossConnectWithAssisted"))

    action = ""
    request_payload: dict[str, Any] = {}
    if service == "datacenter_port":
        if not dc_id:
            return Success(code=400, msg="请选择机房")
        action = "QueryDataCenterPortPrice"
        request_payload = {"dcId": dc_id, "portType": port_type, "buildCrossConnectWithAssisted": assisted}
    elif service == "private_connect":
        if not endpoint_a or not endpoint_z:
            return Success(code=400, msg="请选择 A/Z 点机房")
        action = "QueryPrivateConnectPrice"
        request_payload = {
            "internetType": internet_type,
            "bandwidthMbps": bandwidth,
            "endpointA": endpoint_payload(endpoint_a, port_type, assisted),
            "endpointZ": endpoint_payload(endpoint_z, port_type, assisted),
        }
    elif service == "private_connect_bandwidth":
        if not endpoint_a or not endpoint_z:
            return Success(code=400, msg="请选择 A/Z 点机房")
        action = "QueryPrivateConnectBandwidthPrice"
        request_payload = {
            "sourceDcId": endpoint_a,
            "destinationDcId": endpoint_z,
            "internetType": internet_type,
            "bandwidthMbps": bandwidth,
            "serviceLevel": service_level,
        }
    elif service == "datacenter_lookup":
        return await zenlayer_pricing()
    else:
        return Success(code=400, msg="该服务的 Zenlayer 报价参数还需要进一步确认", data={"service": service})

    try:
        status, data = await zenlayer_request(ZENLAYER_PRODUCT_SDN, action, request_payload)
    except Exception as exc:
        logger.exception("zenlayer quote request failed: action=%s payload=%s", action, request_payload)
        return Success(code=400, msg=f"Zenlayer API请求失败: {exc}", data={"action": action, "payload": request_payload})

    body = zenlayer_response_body(data)
    error = zenlayer_error(data)
    if status >= 400 or error:
        logger.warning("zenlayer quote failed: status=%s action=%s error=%s data=%s", status, action, error, data)
        return Success(
            code=400,
            msg=error or "Zenlayer报价失败",
            data={"action": action, "payload": request_payload, "status": status, "raw": data},
        )

    cost_items = build_zenlayer_cost_items(service, body)
    return Success(
        data={
            "source": "zenlayer_api",
            "service": service,
            "action": action,
            "payload": request_payload,
            "stock": pick(body, "stock", "endpointAPrice.stock", "endpointZPrice.stock", default=None),
            "costItems": cost_items,
            "totalCost": round_money(sum(item["quote_cost"] for item in cost_items)),
            "currency": cost_items[0]["currency"] if cost_items else "USD",
            "raw": data,
        }
    )


EQUINIX_REFERENCE_DATA = {
    "productTypes": [
        {"code": "VIRTUAL_CONNECTION_PRODUCT", "name": "Virtual Connection"},
        {"code": "VIRTUAL_PORT_PRODUCT", "name": "Virtual Port"},
        {"code": "IP_BLOCK_PRODUCT", "name": "IP Block"},
    ],
    "connectionTypes": [
        {"code": "EVPL_VC", "name": "EVPL Virtual Connection"},
        {"code": "EPL_VC", "name": "EPL Virtual Connection"},
        {"code": "EC_VC", "name": "EC Virtual Connection"},
        {"code": "IP_VC", "name": "IP Virtual Connection"},
        {"code": "ACCESS_EPL_VC", "name": "Access EPL Virtual Connection"},
        {"code": "EIA_VC", "name": "Equinix Internet Access VC"},
        {"code": "EVPLAN_VC", "name": "EVPLAN Virtual Connection"},
        {"code": "EPLAN_VC", "name": "EPLAN Virtual Connection"},
        {"code": "EVPTREE_VC", "name": "EVPTREE Virtual Connection"},
        {"code": "EPTREE_VC", "name": "EPTREE Virtual Connection"},
        {"code": "IPWAN_VC", "name": "IPWAN Virtual Connection"},
        {"code": "IA_VC", "name": "Internet Access Virtual Connection"},
        {"code": "MC_VC", "name": "Metro Connect Virtual Connection"},
        {"code": "IX_PUBLIC_VC", "name": "IX Public Virtual Connection"},
        {"code": "IX_PRIVATE_VC", "name": "IX Private Virtual Connection"},
    ],
    "sideTypes": [
        {"code": "COLO", "name": "Colocation"},
        {"code": "VD", "name": "Virtual Device"},
        {"code": "VG", "name": "Virtual Gateway"},
        {"code": "SP", "name": "Service Provider"},
        {"code": "IGW", "name": "Internet Gateway"},
        {"code": "SUBNET", "name": "Subnet"},
        {"code": "CLOUD_ROUTER", "name": "Cloud Router"},
        {"code": "NETWORK", "name": "Network"},
        {"code": "METAL_NETWORK", "name": "Metal Network"},
        {"code": "VPIC_INTERFACE", "name": "VPIC Interface"},
        {"code": "APP_LINK", "name": "Application Link"},
    ],
    "connectionTypeRules": {
        "EVPL_VC": {"aSides": ["COLO", "VD", "CLOUD_ROUTER", "NETWORK"], "zSides": ["COLO", "VD", "SP", "CLOUD_ROUTER", "NETWORK"]},
        "EPL_VC": {"aSides": ["COLO"], "zSides": ["COLO"]},
        "EC_VC": {"aSides": ["COLO", "VD", "CLOUD_ROUTER"], "zSides": ["COLO", "VD", "SP", "CLOUD_ROUTER"]},
        "IP_VC": {"aSides": ["COLO", "VD", "CLOUD_ROUTER"], "zSides": ["SP", "IGW", "NETWORK"]},
        "ACCESS_EPL_VC": {"aSides": ["COLO"], "zSides": ["COLO"]},
        "EIA_VC": {"aSides": ["COLO", "VD", "CLOUD_ROUTER"], "zSides": ["IGW", "NETWORK"]},
        "EVPLAN_VC": {"aSides": ["COLO", "VD", "CLOUD_ROUTER", "NETWORK"], "zSides": ["COLO", "VD", "CLOUD_ROUTER", "NETWORK"]},
        "EPLAN_VC": {"aSides": ["COLO", "NETWORK"], "zSides": ["COLO", "NETWORK"]},
        "EVPTREE_VC": {"aSides": ["COLO", "VD", "NETWORK"], "zSides": ["COLO", "VD", "NETWORK"]},
        "EPTREE_VC": {"aSides": ["COLO", "NETWORK"], "zSides": ["COLO", "NETWORK"]},
        "IPWAN_VC": {"aSides": ["COLO", "VD", "CLOUD_ROUTER"], "zSides": ["SP", "NETWORK"]},
        "IA_VC": {"aSides": ["COLO", "VD", "CLOUD_ROUTER"], "zSides": ["IGW", "NETWORK"]},
        "MC_VC": {"aSides": ["COLO", "NETWORK"], "zSides": ["COLO", "NETWORK"]},
        "IX_PUBLIC_VC": {"aSides": ["COLO", "VD"], "zSides": ["SP"]},
        "IX_PRIVATE_VC": {"aSides": ["COLO", "VD"], "zSides": ["SP"]},
    },
    "bandwidths": [50, 100, 200, 500, 1000, 2000, 5000, 10000],
    "portOptions": {
        "types": [{"code": "XF_PORT", "name": "Fabric Port (XF_PORT)"}],
        "packages": [{"code": "STANDARD", "name": "Standard"}],
        "serviceTypes": [{"code": "EPL", "name": "EPL"}, {"code": "EVPL", "name": "EVPL"}],
        "connectivitySources": [{"code": "COLO", "name": "Colocation"}, {"code": "NETWORK_EDGE", "name": "Network Edge"}],
        "lagOptions": [{"code": False, "name": "No"}, {"code": True, "name": "Yes"}],
    },
    "ipBlockOptions": {
        "types": [{"code": "IPv4", "name": "IPv4"}],
        "prefixLengths": [{"code": 29, "name": "/29"}],
    },
    "fallbackMetros": [
        {"code": "SV", "name": "Silicon Valley"},
        {"code": "HK", "name": "Hong Kong"},
        {"code": "SG", "name": "Singapore"},
        {"code": "TY", "name": "Tokyo"},
        {"code": "LD", "name": "London"},
        {"code": "FR", "name": "Frankfurt"},
        {"code": "NY", "name": "New York"},
        {"code": "DC", "name": "Washington DC"},
    ],
}


def equinix_api_base() -> str:
    return text(settings.EQUINIX_API_URL, EQUINIX_DEFAULT_API_BASE).rstrip("/")


def read_dotenv_value(path: str, key: str) -> str:
    if not os.path.isfile(path):
        return ""
    try:
        with open(path, "r", encoding="utf-8") as file:
            for line in file:
                raw = line.strip()
                if not raw or raw.startswith("#") or "=" not in raw:
                    continue
                name, value = raw.split("=", 1)
                if name.strip() == key:
                    return value.strip().strip('"').strip("'")
    except OSError:
        return ""
    return ""


def priceweb_env_value(key: str) -> str:
    priceweb_env = os.path.abspath(os.path.join(settings.BASE_DIR, os.pardir, "PriceWeb", "backend", ".env"))
    return read_dotenv_value(priceweb_env, key)


def equinix_client_credentials() -> tuple[str, str]:
    client_id = (
        text(settings.EQUINIX_CLIENT_ID)
        or text(settings.CLIENT_ID)
        or text(os.getenv("CLIENT_ID"))
        or priceweb_env_value("CLIENT_ID")
    )
    client_secret = (
        text(settings.EQUINIX_CLIENT_SECRET)
        or text(settings.CLIENT_SECRET)
        or text(os.getenv("CLIENT_SECRET"))
        or priceweb_env_value("CLIENT_SECRET")
    )
    return client_id, client_secret


async def get_equinix_access_token() -> str:
    global _equinix_token, _equinix_token_expire_at
    now = time.time()
    if _equinix_token and now < _equinix_token_expire_at - 60:
        return _equinix_token

    client_id, client_secret = equinix_client_credentials()
    if not client_id or not client_secret:
        raise ValueError("Equinix API credentials are not configured")

    async with httpx.AsyncClient(timeout=20.0, trust_env=False) as client:
        response = await client.post(
            f"{equinix_api_base()}/oauth2/v1/token",
            data={"grant_type": "client_credentials", "client_id": client_id, "client_secret": client_secret},
        )
    payload = response.json()
    if response.status_code != 200 or not payload.get("access_token"):
        logger.warning("equinix token failed: status=%s data=%s", response.status_code, payload)
        raise ValueError("Failed to obtain Equinix access token")
    _equinix_token = payload["access_token"]
    _equinix_token_expire_at = now + int(payload.get("expires_in") or 3600)
    return _equinix_token


async def equinix_request(method: str, path: str, **kwargs) -> tuple[int, Any]:
    token = await get_equinix_access_token()
    headers = kwargs.pop("headers", {})
    headers.update({"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    async with httpx.AsyncClient(base_url=equinix_api_base(), timeout=30.0, trust_env=False) as client:
        response = await client.request(method, path, headers=headers, **kwargs)
    try:
        return response.status_code, response.json()
    except Exception:
        return response.status_code, response.text


def unique_code_options(values: list[Any], fallback: list[dict] | None = None) -> list[dict]:
    options: list[dict] = []
    seen = set()
    for value in values:
        if isinstance(value, dict):
            code = value.get("code")
            name = value.get("name") or code
        else:
            code = value
            name = value
        key = text(code)
        if not key or key in seen:
            continue
        seen.add(key)
        options.append({"code": code, "name": text(name, key)})
    return options or list(fallback or [])


def add_if_present(target: list, value: Any) -> None:
    if value not in (None, ""):
        target.append(value)


def merge_equinix_port_reference(reference: dict, data: Any) -> dict:
    if not isinstance(data, dict):
        return reference
    rows = [item for item in data.get("data", []) if isinstance(item, dict)]
    if not rows:
        return reference

    port_types: list[Any] = []
    packages: list[Any] = []
    service_types: list[Any] = []
    connectivity_sources: list[Any] = []
    lag_options: list[Any] = []
    bandwidths: list[int] = []

    for row in rows:
        add_if_present(port_types, pick(row, "type", "port.type", default=""))
        add_if_present(packages, pick(row, "package.code", "port.package.code", default=""))
        add_if_present(service_types, pick(row, "serviceType", "serviceCode", "port.serviceType", default=""))
        add_if_present(connectivity_sources, pick(row, "connectivitySource.type", "port.connectivitySource.type", default=""))
        if "lagEnabled" in row:
            lag_options.append(bool(row.get("lagEnabled")))
        add_if_present(bandwidths, int(number(pick(row, "bandwidth", "physicalPortsSpeed", default=0), 0)))

    port_options = reference.get("portOptions") or {}
    reference["portOptions"] = {
        **port_options,
        "types": unique_code_options(port_types, port_options.get("types")),
        "packages": unique_code_options(packages, port_options.get("packages")),
        "serviceTypes": unique_code_options(service_types, port_options.get("serviceTypes")),
        "connectivitySources": unique_code_options(connectivity_sources, port_options.get("connectivitySources")),
        "lagOptions": unique_code_options(
            [{"code": value, "name": "Yes" if value else "No"} for value in lag_options],
            port_options.get("lagOptions"),
        ),
    }
    dynamic_bandwidths = sorted({value for value in bandwidths if value > 0})
    if dynamic_bandwidths:
        reference["bandwidths"] = dynamic_bandwidths
    return reference


def merge_equinix_price_reference(reference: dict, data: Any) -> dict:
    rows = equinix_price_entries(data)
    if not rows:
        return reference

    product_types: list[Any] = []
    connection_types: list[Any] = []
    bandwidths: list[int] = []
    for row in rows:
        add_if_present(product_types, pick(row, "type", default=""))
        add_if_present(connection_types, pick(row, "connection.type", default=""))
        add_if_present(bandwidths, int(number(pick(row, "connection.bandwidth", "port.bandwidth", default=0), 0)))

    reference["productTypes"] = unique_code_options(product_types, reference.get("productTypes"))
    reference["connectionTypes"] = unique_code_options(connection_types, reference.get("connectionTypes"))
    dynamic_bandwidths = sorted({value for value in bandwidths if value > 0})
    if dynamic_bandwidths:
        reference["bandwidths"] = dynamic_bandwidths
    return reference


def equinix_filter_payload(payload: dict) -> dict:
    filters = payload.get("filters")
    if isinstance(filters, list) and filters:
        return {"filter": {"and": filters}}

    product_type = text(payload.get("type"), "VIRTUAL_CONNECTION_PRODUCT")
    filters = [{"property": "/type", "operator": "=", "values": [product_type]}]
    if product_type == "VIRTUAL_CONNECTION_PRODUCT":
        filters.extend([
            {"property": "/connection/type", "operator": "=", "values": [text(payload.get("connectionType"), "EVPL_VC")]},
            {"property": "/connection/bandwidth", "operator": "=", "values": [int(number(payload.get("bandwidth"), 1000))]},
            {"property": "/connection/aSide/accessPoint/type", "operator": "=", "values": [text(payload.get("aSideType"), "COLO")]},
            {"property": "/connection/aSide/accessPoint/location/metroCode", "operator": "=", "values": [text(payload.get("originMetro"), "SV")]},
            {"property": "/connection/zSide/accessPoint/type", "operator": "=", "values": [text(payload.get("zSideType"), "COLO")]},
            {"property": "/connection/zSide/accessPoint/location/metroCode", "operator": "=", "values": [text(payload.get("destinationMetro"), "HK")]},
        ])
    elif product_type == "VIRTUAL_PORT_PRODUCT":
        ibx = text(payload.get("ibx")) or f"{text(payload.get('originMetro'), 'SV')}{text(payload.get('ibxSuffix'), '1')}"
        filters.extend([
            {"property": "/port/location/ibx", "operator": "=", "values": [ibx]},
            {"property": "/port/type", "operator": "=", "values": [text(payload.get("portType"), "XF_PORT")]},
            {"property": "/port/bandwidth", "operator": "=", "values": [int(number(payload.get("bandwidth"), 1000))]},
            {"property": "/port/package/code", "operator": "=", "values": [text(payload.get("portPackage"), "STANDARD")]},
            {"property": "/port/serviceType", "operator": "=", "values": [text(payload.get("portServiceType"), "EPL")]},
            {"property": "/port/connectivitySource/type", "operator": "=", "values": [text(payload.get("portConnectivitySource"), "COLO")]},
            {"property": "/port/lag/enabled", "operator": "=", "values": [bool(payload.get("portLagEnabled"))]},
        ])
    elif product_type == "IP_BLOCK_PRODUCT":
        filters.extend([
            {"property": "/ipBlock/type", "operator": "=", "values": [text(payload.get("ipBlockType"), "IPv4")]},
            {"property": "/ipBlock/prefixLength", "operator": "=", "values": [int(number(payload.get("ipBlockPrefixLength"), 29))]},
            {"property": "/ipBlock/location/metroCode", "operator": "IN", "values": [text(payload.get("originMetro"), "SV")]},
        ])
    return {"filter": {"and": filters}}


def equinix_connection_rule_error(payload: dict) -> str | None:
    if text(payload.get("type"), "VIRTUAL_CONNECTION_PRODUCT") != "VIRTUAL_CONNECTION_PRODUCT":
        return None

    connection_type = text(payload.get("connectionType"), "EVPL_VC")
    rule = EQUINIX_REFERENCE_DATA.get("connectionTypeRules", {}).get(connection_type)
    if not rule:
        return None

    a_side_type = text(payload.get("aSideType"), "COLO")
    z_side_type = text(payload.get("zSideType"), "COLO")
    allowed_a_sides = rule.get("aSides") or []
    allowed_z_sides = rule.get("zSides") or []
    if allowed_a_sides and a_side_type not in allowed_a_sides:
        return f"{connection_type} 的 A端类型不支持 {a_side_type}，可选：{', '.join(allowed_a_sides)}"
    if allowed_z_sides and z_side_type not in allowed_z_sides:
        return f"{connection_type} 的 Z端类型不支持 {z_side_type}，可选：{', '.join(allowed_z_sides)}"
    return None


def equinix_error_message(data: Any, default: str = "Equinix报价失败") -> str:
    if isinstance(data, dict):
        for key in ("message", "detail", "error", "errorMessage", "title"):
            value = data.get(key)
            if value:
                return f"{default}: {value}"
        errors = data.get("errors")
        if isinstance(errors, list) and errors:
            first = errors[0]
            if isinstance(first, dict):
                for key in ("message", "detail", "error", "title"):
                    value = first.get(key)
                    if value:
                        return f"{default}: {value}"
            return f"{default}: {first}"
    return default


def equinix_price_entries(data: Any) -> list[dict]:
    if isinstance(data, dict):
        for key in ("data", "prices", "items"):
            value = data.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
        return [data]
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    return []


def equinix_cost_item(entry: dict, charge: dict, index: int) -> dict:
    price = number(pick(charge, "price", "amount", "value", default=0))
    currency = text(pick(charge, "currency", "currencyCode", default="")) or text(pick(entry, "currency", "currencyCode", default="USD"))
    name = text(pick(charge, "type", "name", "chargeType", default="")) or text(pick(entry, "type", "productType", default=f"price_{index}"))
    unit = text(pick(charge, "frequency", "unit", "billingFrequency", default="")) or name
    return {
        "name": name,
        "supplier_price": round_money(price),
        "quote_cost": round_money(price),
        "suggest_20": round_money(price * 1.2),
        "suggest_30": round_money(price * 1.3),
        "suggest_40": round_money(price * 1.4),
        "margin_30": round_money(price / 0.7) if price else 0,
        "unit": unit,
        "currency": currency or "USD",
        "raw": {"entry": entry, "charge": charge},
    }


def build_equinix_cost_items(data: Any) -> list[dict]:
    items = []
    for entry in equinix_price_entries(data):
        charges = entry.get("charges")
        if isinstance(charges, list) and charges:
            for charge in charges:
                if isinstance(charge, dict):
                    item = equinix_cost_item(entry, charge, len(items) + 1)
                    if item["supplier_price"] > 0 or item["name"]:
                        items.append(item)
        else:
            item = equinix_cost_item(entry, entry, len(items) + 1)
            if item["supplier_price"] > 0:
                items.append(item)
    return items


@router.get("/equinix-pricing/reference-data", summary="Equinix Fabric报价参考数据")
async def equinix_reference_data():
    reference = json.loads(json.dumps(EQUINIX_REFERENCE_DATA))
    reference["source"] = "fallback"
    reference["errors"] = []

    try:
        status, ports = await equinix_request(
            "POST",
            "/fabric/v4/ports/search",
            json={
                "filter": {"property": "/state", "operator": "=", "values": ["PROVISIONED"]},
                "pagination": {"limit": 100, "offset": 0},
            },
        )
    except Exception as exc:
        reference["errors"].append({"action": "ports/search", "error": str(exc)})
    else:
        if status < 400:
            reference = merge_equinix_port_reference(reference, ports)
            reference["source"] = "equinix_api"
            reference["rawPorts"] = ports
        else:
            reference["errors"].append({"action": "ports/search", "status": status, "data": ports})

    try:
        price_product_types = [item["code"] for item in EQUINIX_REFERENCE_DATA["productTypes"]]
        status, prices = await equinix_request(
            "POST",
            "/fabric/v4/prices/search",
            json={
                "filter": {"and": [{"property": "/type", "operator": "IN", "values": price_product_types}]},
                "pagination": {"limit": 100, "offset": 0},
            },
        )
    except Exception as exc:
        reference["errors"].append({"action": "prices/search", "error": str(exc)})
    else:
        if status < 400:
            reference = merge_equinix_price_reference(reference, prices)
            reference["source"] = "equinix_api"
            reference["rawPrices"] = prices
        else:
            reference["errors"].append({"action": "prices/search", "status": status, "data": prices})

    return Success(data=reference)


@router.get("/equinix-pricing/metros", summary="Equinix Fabric城市列表")
async def equinix_metros():
    try:
        status, data = await equinix_request("GET", "/fabric/v4/metros", params={"limit": 100})
    except Exception as exc:
        logger.warning("equinix metros failed: %s", exc)
        return Success(data={"source": "fallback", "metros": EQUINIX_REFERENCE_DATA["fallbackMetros"], "error": str(exc)})
    if status >= 400:
        return Success(data={"source": "fallback", "metros": EQUINIX_REFERENCE_DATA["fallbackMetros"], "raw": data})

    metros = []
    for metro in data.get("data", []) if isinstance(data, dict) else []:
        code = text(metro.get("code"))
        if code:
            metros.append({"code": code, "name": text(metro.get("name"), code)})
    metros = sorted(metros, key=lambda item: item["name"]) or EQUINIX_REFERENCE_DATA["fallbackMetros"]
    return Success(data={"source": "equinix_api", "metros": metros, "raw": data})


@router.post("/equinix-pricing/quote", summary="Equinix Fabric生成报价")
async def equinix_quote(payload: dict = Body(default_factory=dict)):
    rule_error = equinix_connection_rule_error(payload)
    if rule_error:
        return Success(code=400, msg=rule_error, data={"payload": payload})

    request_payload = equinix_filter_payload(payload)
    try:
        status, data = await equinix_request("POST", "/fabric/v4/prices/search", json=request_payload)
    except Exception as exc:
        logger.exception("equinix quote request failed: payload=%s", request_payload)
        return Success(code=400, msg=f"Equinix API请求失败: {exc}", data={"payload": request_payload})

    if status >= 400:
        logger.warning("equinix quote failed: status=%s data=%s", status, data)
        return Success(code=400, msg=equinix_error_message(data), data={"payload": request_payload, "status": status, "raw": data})

    cost_items = build_equinix_cost_items(data)
    total_cost = sum(item["quote_cost"] for item in cost_items)
    return Success(
        data={
            "source": "equinix_api",
            "payload": request_payload,
            "costItems": cost_items,
            "totalCost": round_money(total_cost),
            "currency": cost_items[0]["currency"] if cost_items else "USD",
            "raw": data,
        }
    )


async def get_ipxo_token() -> str:
    global _ipxo_token, _ipxo_token_expire_at
    now = time.time()
    if _ipxo_token and now < _ipxo_token_expire_at - 60:
        return _ipxo_token

    client_id = text(settings.IPXO_CLIENT_ID)
    secret = text(settings.IPXO_SECRET_KEY)
    if not client_id or not secret:
        return ""

    data = {
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": secret,
        "scope": text(settings.IPXO_SCOPE, "billing"),
    }
    async with httpx.AsyncClient(timeout=15.0, trust_env=False) as client:
        response = await client.post(IPXO_TOKEN_URL, data=data)
    payload = response.json()
    if response.status_code != 200 or not payload.get("access_token"):
        logger.warning("ipxo token failed: status=%s data=%s", response.status_code, payload)
        return ""
    _ipxo_token = payload["access_token"]
    _ipxo_token_expire_at = now + int(payload.get("expires_in") or 3600)
    return _ipxo_token


async def ipxo_request(method: str, path: str, token: str, **kwargs) -> tuple[int, Any]:
    async with httpx.AsyncClient(base_url=IPXO_API_BASE, timeout=20.0, trust_env=False) as client:
        response = await client.request(
            method,
            path,
            headers={"Authorization": f"Bearer {token}", "accept": "application/json"},
            **kwargs,
        )
    try:
        data = response.json()
    except ValueError:
        data = {"raw": response.text[:1000]}
    return response.status_code, data


async def fetch_ipxo_billing_services(token: str, tenant: str, limit: int) -> tuple[int, dict]:
    per_page = min(max(limit, 1), 100)
    pages = max(1, min((limit + per_page - 1) // per_page, 5))
    path = f"/billing/v1/{tenant}/market/ipv4/services"

    async def fetch_page(client: httpx.AsyncClient, page: int) -> tuple[int, dict]:
        response = await client.get(path, params={"page": page, "per_page": per_page})
        try:
            data = response.json()
        except ValueError:
            data = {"raw": response.text[:1000]}
        return response.status_code, data if isinstance(data, dict) else {"raw": data}

    async with httpx.AsyncClient(
        base_url=IPXO_API_BASE,
        timeout=20.0,
        trust_env=False,
        headers={"Authorization": f"Bearer {token}", "accept": "application/json"},
    ) as client:
        results = await asyncio.gather(*(fetch_page(client, page) for page in range(1, pages + 1)))

    rows = []
    last_meta = {}
    for page_index, (status, data) in enumerate(results, start=1):
        if status >= 400:
            return status, data
        last_meta = data.get("meta") if isinstance(data, dict) else {}
        last_page = int(last_meta.get("last_page") or pages)
        if page_index > last_page:
            continue
        batch = data.get("data") if isinstance(data, dict) else []
        if isinstance(batch, list):
            rows.extend(batch)
    return 200, {"data": rows[:limit], "meta": last_meta}


async def lookup_ip_region(ip_address: str) -> dict:
    ip_address = text(ip_address).split("/")[0]
    if not ip_address:
        return {}
    if ip_address in _ip_geo_cache:
        return _ip_geo_cache[ip_address]
    token = text(settings.IPINFO_TOKEN)
    if not token:
        logger.info("ipinfo token is not configured")
        return {}
    try:
        async with httpx.AsyncClient(base_url=IPINFO_API_BASE, timeout=8.0, trust_env=True) as client:
            response = await client.get(f"/{ip_address}/json", params={"token": token})
        data = response.json()
    except Exception as exc:
        logger.warning(f"ipinfo geolocation lookup failed: ip={ip_address} error={exc!r}")
        return {}
    if response.status_code != 200 or data.get("bogon") or data.get("error"):
        logger.info("ipinfo geolocation unavailable: ip=%s status=%s data=%s", ip_address, response.status_code, data)
        return {}
    country_code = text(data.get("country"))
    region_name = text(data.get("region"))
    city = text(data.get("city") or region_name)
    result = {
        "country": country_code,
        "country_code": country_code,
        "city": city,
        "region_name": region_name,
        "region": country_code,
        "source": "ipinfo",
    }
    _ip_geo_cache[ip_address] = result
    return result


def normalize_ipinfo_region(data: Any) -> dict:
    if not isinstance(data, dict) or data.get("bogon") or data.get("error"):
        return {}
    geo = data.get("geo") if isinstance(data.get("geo"), dict) else {}
    raw_country = text(data.get("country"))
    country_code = normalized_country_code(
        pick(geo, "country_code", default="") or data.get("country_code") or raw_country
    )
    country_name = text(pick(geo, "country", default="") or data.get("country_name") or (raw_country if len(raw_country) > 3 else ""))
    region_name = text(pick(geo, "region", default="") or data.get("region"))
    city = text(pick(geo, "city", default="") or data.get("city") or region_name)
    continent = text(data.get("continent") or pick(geo, "continent", default=""))
    if not country_code and not country_name:
        return {}
    country = country_name or country_code
    return {
        "country": country,
        "country_code": country_code,
        "country_name": country_name,
        "city": city,
        "region_name": region_name,
        "continent": continent,
        "region": country_code or country,
        "source": "ipinfo_batch",
    }


async def lookup_ip_regions_batch(addresses: list[str]) -> dict[str, dict]:
    token = text(settings.IPINFO_TOKEN)
    normalized_addresses = {address: text(address).split("/")[0] for address in addresses if text(address)}
    result = {address: _ip_geo_cache[ip] for address, ip in normalized_addresses.items() if ip in _ip_geo_cache}
    missing_ips = sorted({ip for ip in normalized_addresses.values() if ip and ip not in _ip_geo_cache})
    if not token or not missing_ips:
        return result

    chunks = [missing_ips[index : index + 20] for index in range(0, min(len(missing_ips), 1000), 20)]

    async def fetch_chunk(client: httpx.AsyncClient, chunk: list[str]) -> dict:
        try:
            response = await client.post("/batch/lite", params={"token": token}, json=chunk)
            if response.status_code != 200:
                logger.info("ipinfo lite batch unavailable: status=%s count=%s", response.status_code, len(chunk))
                return {}
            data = response.json()
            return data if isinstance(data, dict) else {}
        except Exception as exc:
            logger.warning(f"ipinfo lite batch lookup failed: count={len(chunk)} error={exc!r}")
            return {}

    async with httpx.AsyncClient(base_url=IPINFO_BATCH_API_BASE, timeout=3.0, trust_env=True) as client:
        batch_results = await asyncio.gather(*(fetch_chunk(client, chunk) for chunk in chunks))

    for data in batch_results:
        for ip, raw_geo in data.items():
            geo = normalize_ipinfo_region(raw_geo)
            if geo:
                _ip_geo_cache[ip] = geo

    for address, ip in normalized_addresses.items():
        if ip in _ip_geo_cache:
            result[address] = _ip_geo_cache[ip]
    return result


def normalize_ipxo_resource(item: dict) -> dict:
    address = pick(item, "billing_service.address", "address", "prefix", "notation", "product_fields.address", default="")
    cidr = pick(item, "billing_service.cidr", "prefix_length", "cidr", "product_fields.cidr", default="")
    notation = f"{address}/{cidr}" if address and cidr and "/" not in str(address) else text(address)
    price = pick(
        item,
        "billing_service.recurring_amount",
        "price",
        "monthly_price",
        "recurring_price",
        "total",
        "amount",
        "billing.price",
        default=0,
    )
    currency = pick(item, "billing_service.currency", "currency", "price_currency", "billing.currency", default="USD")
    country = pick(item, "country", "geo_country_code", "geodata.0.countryCode", "whois.country", default="")
    country_code = normalized_country_code(
        pick(item, "geo_country_code", "country_code", "geodata.0.countryCode", "whois.country", default="")
    )
    status = pick(item, "billing_service.status", "status", "state", "subscription.status", default="")
    registry = pick(item, "market_service.registry", "registry", default="")
    return {
        "uuid": pick(item, "billing_service.uuid", "uuid", "id", "service_uuid", default=""),
        "market_service_uuid": pick(item, "market_service.uuid", default=""),
        "notation": notation,
        "address": text(address),
        "cidr": text(cidr),
        "country": text(country),
        "country_code": text(country_code),
        "region": text(country_code or country, "未返回地区"),
        "registry": text(registry).upper(),
        "status": text(status, "unknown"),
        "monthly_price": number(price),
        "currency": text(currency, "USD"),
    }


async def enrich_ipxo_regions(items: list[dict]) -> None:
    addresses = sorted({item.get("address") for item in items if item.get("address")})
    by_address = await lookup_ip_regions_batch(addresses)
    for item in items:
        geo = by_address.get(item.get("address")) or {}
        if geo:
            item["country"] = geo.get("country") or item.get("country") or ""
            item["country_code"] = geo.get("country_code") or ""
            item["city"] = geo.get("city") or ""
            item["region"] = geo.get("country_code") or geo.get("country") or item.get("country_code") or item.get("country") or "未识别地区"
        elif not item.get("region") or item.get("region") == "未返回地区":
            item["region"] = "未识别地区"


def apply_ipxo_country_code_region(items: list[dict]) -> None:
    for item in items:
        country_name = text(item.get("country_name") or item.get("country"))
        country_code = (
            normalized_country_code(item.get("country_code"))
            or normalized_country_code(item.get("region"))
            or normalized_country_code(country_name)
        )
        if country_name:
            item["region"] = country_name
        elif country_code:
            item["region"] = country_code
        if country_code:
            item["country_code"] = country_code


@router.get("/ipxo/resources", summary="IPXO IP资源")
async def ipxo_resources(
    limit: int = Query(100, ge=1, le=500),
    refresh: bool = Query(False, description="skip cache and refresh from IPXO"),
    geo: bool = Query(True, description="enrich country code via IPinfo"),
):
    if not text(settings.IPXO_COMPANY_UUID):
        return Success(code=400, msg="IPXO company uuid is not configured", data={"items": []})
    cache_key = f"limit:{limit}:geo:{int(geo)}"
    now = time.time()
    if not refresh:
        cached = _ipxo_resources_cache.get(cache_key)
        if cached and now - cached[0] < IPXO_RESOURCES_CACHE_TTL:
            cached_data = {**cached[1], "cached": True, "cache_age": round(now - cached[0], 1)}
            return Success(data=cached_data)
    token = await get_ipxo_token()
    if not token:
        return Success(code=400, msg="IPXO token unavailable", data={"items": []})

    tenant = settings.IPXO_COMPANY_UUID
    errors = []
    try:
        status, data = await fetch_ipxo_billing_services(token, tenant, limit)
    except Exception as exc:
        logger.exception("ipxo resource request failed: source=billing_services")
        errors.append({"source": "billing_services", "error": str(exc)})
    else:
        if status >= 400:
            errors.append({"source": "billing_services", "status": status, "data": data})
        else:
            raw_items = data.get("data") if isinstance(data, dict) else []
            if not isinstance(raw_items, list):
                raw_items = []
            items = [normalize_ipxo_resource(item) for item in raw_items if isinstance(item, dict)]
            if geo:
                await enrich_ipxo_regions(items)
            apply_ipxo_country_code_region(items)
            active_items = [item for item in items if item["status"].lower() in {"active", "running"}]
            display_items = active_items
            summary = {
                "count": len(display_items),
                "total_count": len(items),
                "active_count": len(active_items),
                "terminated_count": len([item for item in items if item["status"].lower() == "terminated"]),
                "monthly_total": round(sum(item["monthly_price"] for item in display_items), 2),
                "active_monthly_total": round(sum(item["monthly_price"] for item in active_items), 2),
                "currencies": sorted({item["currency"] for item in display_items if item["currency"]}),
                "registries": sorted({item["registry"] for item in display_items if item["registry"]}),
            }
            result_data = {
                "source": "billing_services",
                "summary": summary,
                "items": display_items,
                "errors": errors,
                "cached": False,
            }
            _ipxo_resources_cache[cache_key] = (time.time(), result_data)
            return Success(data=result_data)

    attempts = [
        ("billing_services_alt", "GET", f"/billing/v1/{tenant}/services", {"params": {"limit": limit}}),
        (
            "nethub_prefixes",
            "POST",
            f"/nethub-data/{tenant}/prefixes/search",
            {"json": {"limit": limit, "fields": ["whois.country", "geodata.countryCode", "routes.origin"]}},
        ),
    ]
    for source, method, path, kwargs in attempts:
        try:
            status, data = await ipxo_request(method, path, token, **kwargs)
        except Exception as exc:
            logger.exception("ipxo resource request failed: source=%s", source)
            errors.append({"source": source, "error": str(exc)})
            continue
        if status >= 400:
            errors.append({"source": source, "status": status, "data": data})
            continue
        raw_items = data.get("data") if isinstance(data, dict) else data
        if isinstance(raw_items, dict):
            raw_items = raw_items.get("items") or raw_items.get("data") or raw_items.get("services") or []
        if not isinstance(raw_items, list):
            raw_items = []
        items = [normalize_ipxo_resource(item) for item in raw_items if isinstance(item, dict)]
        if geo:
            await enrich_ipxo_regions(items)
        apply_ipxo_country_code_region(items)
        active_items = [item for item in items if item["status"].lower() in {"active", "running"}]
        summary = {
            "count": len(items),
            "active_count": len(active_items),
            "terminated_count": len([item for item in items if item["status"].lower() == "terminated"]),
            "monthly_total": round(sum(item["monthly_price"] for item in items), 2),
            "active_monthly_total": round(sum(item["monthly_price"] for item in active_items), 2),
            "currencies": sorted({item["currency"] for item in items if item["currency"]}),
            "registries": sorted({item["registry"] for item in items if item["registry"]}),
        }
        result_data = {"source": source, "summary": summary, "items": items, "errors": errors, "cached": False}
        _ipxo_resources_cache[cache_key] = (time.time(), result_data)
        return Success(data=result_data)

    return Success(code=400, msg="IPXO resource APIs unavailable", data={"items": [], "errors": errors})
