import asyncio
import hashlib
import hmac
import json
import time
from collections import defaultdict
from typing import Any

import httpx
from fastapi import APIRouter, Body, Query

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

_ipxo_token = ""
_ipxo_token_expire_at = 0.0
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


def format_device_config(attributes: dict) -> str:
    attrs = attributes if isinstance(attributes, dict) else {}
    cpu = pick(attrs, "CPU型号", "cpu_model", "CPU Model")
    cpu_count = pick(attrs, "CPU数量", "CPU核心数", "cpu_count")
    memory = pick(attrs, "内存容量", "内存", "memory")
    disk = pick(attrs, "磁盘", "硬盘", "disk")
    parts = []
    if cpu_count or cpu:
        parts.append(" / ".join(item for item in [text(cpu_count), text(cpu)] if item))
    if memory:
        parts.append(text(memory))
    if disk:
        parts.append(text(disk))
    return " | ".join(parts)


def device_to_card_row(device: AssetDevice) -> dict:
    attrs = device.attributes if isinstance(device.attributes, dict) else {}
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
        "cabinet": cabinet.name if cabinet else "",
        "location": location.name if location else "",
        "region": region.name if region else "",
        "country": region.country if region else "",
        "city": region.city if region else "",
        "config": format_device_config(attrs),
        "attributes": attrs,
        "remark": device.remark or "",
    }


@router.get("/free-devices", summary="空闲设备销售看板")
async def free_devices(
    region_id: int | None = Query(None, description="地区ID"),
    keyword: str = Query("", description="设备名称、型号、资产编号"),
):
    query = AssetDevice.filter(status=0).select_related("region", "location", "cabinet")
    if region_id:
        query = query.filter(region_id=region_id)
    rows = await query.order_by("region__name", "location__name", "cabinet__name", "u_position", "name")

    keyword_text = keyword.strip().lower()
    groups: dict[str, dict] = {}
    for device in rows:
        row = device_to_card_row(device)
        if keyword_text:
            haystack = " ".join(
                str(row.get(key) or "")
                for key in ["asset_no", "name", "brand", "model", "serial_no", "mgmt_ip", "business_ip", "config"]
            ).lower()
            if keyword_text not in haystack:
                continue
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
        group["count"] += 1
        if row["model"]:
            group["models"][row["model"]] += 1
        if row["location"]:
            group["locations"][row["location"]] += 1
        group["devices"].append(row)

    result = []
    for group in groups.values():
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
    display_parts = [value for value in [name if name != dc_id else "", city, area] if value]
    return {
        "dcId": dc_id,
        "dcName": name,
        "label": " / ".join(display_parts) or dc_id,
        "cityName": city,
        "areaName": area,
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
                {"label": "云专线接入", "value": "cloud_onramp", "disabled": True},
                {"label": "三层云路由带宽", "value": "cloud_router_bandwidth", "disabled": True},
                {"label": "IP Transit", "value": "ip_transit", "disabled": True},
                {"label": "查询可用机房", "value": "datacenter_lookup"},
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
    service_level = text(payload.get("serviceLevel"), "Gold")
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
