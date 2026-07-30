import time
from collections import defaultdict
from typing import Any

import httpx
from fastapi import APIRouter, Query

from app.log import logger
from app.models.asset import AssetDevice
from app.schemas.base import Success
from app.settings.config import settings

router = APIRouter()

IPXO_TOKEN_URL = "https://hydra.ipxo.com/oauth2/token"
IPXO_API_BASE = "https://apigw.ipxo.com"
_ipxo_token = ""
_ipxo_token_expire_at = 0.0
_ip_geo_cache: dict[str, dict] = {}


def text(value: Any, default: str = "") -> str:
    value = "" if value is None else str(value).strip()
    return value or default


def number(value: Any, default: float = 0) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return default


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
    cpu = pick(attrs, "CPU型号", "cpu_model", "CPU鍨嬪彿")
    cpu_count = pick(attrs, "CPU数量", "CPU鏁伴噺", "cpu_count")
    memory = pick(attrs, "内存容量", "鍐呭瓨瀹归噺", "memory")
    disk = pick(attrs, "磁盘", "硬盘", "disk")
    parts = []
    if cpu_count or cpu:
        parts.append(" / ".join(item for item in [text(cpu_count), text(cpu)] if item))
    if memory:
        parts.append(text(memory))
    if disk:
        parts.append(text(disk))
    return " · ".join(parts)


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


@router.get("/zenlayer-pricing", summary="层峰价格参考")
async def zenlayer_pricing():
    rows = [
        {"area": "Asia", "from": "Hong Kong", "to": "Singapore", "bandwidth": "100M", "monthly_usd": 580, "unit": "USD/Mbps/月"},
        {"area": "Asia", "from": "Hong Kong", "to": "Tokyo", "bandwidth": "100M", "monthly_usd": 620, "unit": "USD/Mbps/月"},
        {"area": "Asia", "from": "Singapore", "to": "Jakarta", "bandwidth": "100M", "monthly_usd": 680, "unit": "USD/Mbps/月"},
        {"area": "Europe", "from": "London", "to": "Frankfurt", "bandwidth": "100M", "monthly_usd": 420, "unit": "USD/Mbps/月"},
        {"area": "US", "from": "Los Angeles", "to": "Ashburn", "bandwidth": "100M", "monthly_usd": 390, "unit": "USD/Mbps/月"},
    ]
    return Success(
        data={
            "source": "local_reference",
            "note": "参考 Zenlayer SDN 报价页布局；实际下单价格以后可接 Zenlayer API/报价表同步。",
            "rows": rows,
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
    page = 1
    rows = []
    last_meta = {}
    while len(rows) < limit:
        status, data = await ipxo_request(
            "GET",
            f"/billing/v1/{tenant}/market/ipv4/services",
            token,
            params={"page": page, "per_page": per_page},
        )
        if status >= 400:
            return status, data if isinstance(data, dict) else {"raw": data}
        batch = data.get("data") if isinstance(data, dict) else []
        last_meta = data.get("meta") if isinstance(data, dict) else {}
        if not isinstance(batch, list) or not batch:
            break
        rows.extend(batch)
        last_page = int(last_meta.get("last_page") or page)
        if page >= last_page:
            break
        page += 1
    return 200, {"data": rows[:limit], "meta": last_meta}


async def lookup_ip_region(ip_address: str) -> dict:
    ip_address = text(ip_address)
    if not ip_address:
        return {}
    if ip_address in _ip_geo_cache:
        return _ip_geo_cache[ip_address]
    try:
        async with httpx.AsyncClient(timeout=5.0, trust_env=False) as client:
            response = await client.get(
                f"http://ip-api.com/json/{ip_address}",
                params={"fields": "status,country,countryCode,regionName,city,message"},
            )
        data = response.json()
    except Exception as exc:
        logger.warning(f"ip geolocation lookup failed: ip={ip_address} error={exc}")
        return {}
    if response.status_code != 200 or data.get("status") != "success":
        logger.info("ip geolocation unavailable: ip=%s status=%s data=%s", ip_address, response.status_code, data)
        return {}
    country = text(data.get("country"))
    city = text(data.get("city") or data.get("regionName"))
    result = {
        "country": country,
        "country_code": text(data.get("countryCode")),
        "city": city,
        "region": " / ".join(item for item in [country, city] if item) or country,
    }
    _ip_geo_cache[ip_address] = result
    return result


def normalize_ipxo_resource(item: dict) -> dict:
    billing_service = item.get("billing_service") if isinstance(item.get("billing_service"), dict) else {}
    market_service = item.get("market_service") if isinstance(item.get("market_service"), dict) else {}
    address = pick(item, "billing_service.address", "address", "prefix", "notation", "product_fields.address", default="")
    cidr = pick(item, "billing_service.cidr", "prefix_length", "cidr", "product_fields.cidr", default="")
    if address and cidr and "/" not in str(address):
        notation = f"{address}/{cidr}"
    else:
        notation = text(address)
    price = pick(item, "billing_service.recurring_amount", "price", "monthly_price", "recurring_price", "total", "amount", "billing.price", default=0)
    currency = pick(item, "billing_service.currency", "currency", "price_currency", "billing.currency", default="USD")
    country = pick(item, "geo_country_code", "country", "geodata.0.countryCode", "whois.country", default="")
    status = pick(item, "billing_service.status", "status", "state", "subscription.status", default="")
    registry = pick(item, "market_service.registry", "registry", default="")
    return {
        "uuid": pick(item, "billing_service.uuid", "uuid", "id", "service_uuid", default=""),
        "market_service_uuid": pick(item, "market_service.uuid", default=""),
        "notation": notation,
        "address": text(address),
        "cidr": text(cidr),
        "country": text(country),
        "region": text(country, "未返回地区"),
        "registry": text(registry).upper(),
        "status": text(status, "unknown"),
        "monthly_price": number(price),
        "currency": text(currency, "USD"),
        "raw": item,
    }


async def enrich_ipxo_regions(items: list[dict]) -> None:
    by_address = {}
    for address in [item.get("address") for item in items if item.get("address")]:
        if address not in by_address:
            by_address[address] = await lookup_ip_region(address)
    for item in items:
        geo = by_address.get(item.get("address")) or {}
        if geo:
            item["country"] = geo.get("country") or item.get("country") or ""
            item["country_code"] = geo.get("country_code") or ""
            item["city"] = geo.get("city") or ""
            item["region"] = geo.get("region") or item.get("region") or "未识别地区"
        elif not item.get("region") or item.get("region") == "未返回地区":
            item["region"] = "未识别地区"


@router.get("/ipxo/resources", summary="IPXO IP资源")
async def ipxo_resources(limit: int = Query(100, ge=1, le=500)):
    if not text(settings.IPXO_COMPANY_UUID):
        return Success(code=400, msg="IPXO company uuid is not configured", data={"items": []})
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
            await enrich_ipxo_regions(items)
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
            return Success(data={"source": "billing_services", "summary": summary, "items": display_items, "errors": errors})

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
        await enrich_ipxo_regions(items)
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
        return Success(data={"source": source, "summary": summary, "items": items, "errors": errors})

    return Success(code=400, msg="IPXO resource APIs unavailable", data={"items": [], "errors": errors})
