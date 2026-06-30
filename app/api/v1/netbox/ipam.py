import ipaddress
from collections import Counter
from typing import Any
from urllib.parse import urljoin

import httpx
from fastapi import APIRouter, Query

from app.schemas.base import Fail, Success
from app.settings.config import settings

router = APIRouter()


def netbox_base_url() -> str:
    if not settings.NETBOX_URL:
        raise RuntimeError("NetBox URL is not configured")
    return settings.NETBOX_URL.rstrip("/") + "/"


def netbox_headers() -> dict[str, str]:
    if not settings.NETBOX_TOKEN:
        raise RuntimeError("NetBox token is not configured")
    token = settings.NETBOX_TOKEN.strip()
    if token.lower().startswith(("bearer ", "token ")):
        authorization = token
    else:
        authorization = f"Token {token}"
    return {
        "Authorization": authorization,
        "Accept": "application/json",
        "User-Agent": "Catixs-FinWork NetBox IPAM/1.0",
    }


def nested_name(value: Any) -> str:
    if isinstance(value, dict):
        for key in ("name", "display", "label", "value", "slug"):
            if value.get(key):
                return str(value[key])
    if value is None:
        return ""
    return str(value)


def nested_id(value: Any) -> int | None:
    if isinstance(value, dict) and value.get("id") is not None:
        try:
            return int(value["id"])
        except (TypeError, ValueError):
            return None
    return None


def status_value(value: Any) -> str:
    if isinstance(value, dict):
        for key in ("value", "name", "slug", "label", "display"):
            if value.get(key):
                return str(value[key]).lower()
    if value is None:
        return ""
    return str(value).lower()


def custom_field_value(custom_fields: dict[str, Any], keys: tuple[str, ...]) -> str:
    lower_fields = {str(key).lower(): value for key, value in (custom_fields or {}).items()}
    for key in keys:
        value = lower_fields.get(key)
        if value in (None, ""):
            continue
        if isinstance(value, dict):
            return nested_name(value)
        if isinstance(value, list):
            names = [nested_name(item) for item in value if item]
            return ", ".join([name for name in names if name])
        return str(value)
    return ""


def ip_customer(item: dict[str, Any]) -> str:
    custom_fields = item.get("custom_fields") or {}
    return (
        nested_name(item.get("tenant"))
        or custom_field_value(custom_fields, ("customer", "client", "user", "tenant"))
        or "未归属"
    )


def ip_supplier(item: dict[str, Any]) -> str:
    custom_fields = item.get("custom_fields") or {}
    return (
        nested_name(item.get("owner"))
        or custom_field_value(custom_fields, ("owner", "supplier", "vendor", "provider"))
        or "未指定"
    )


def ip_assignee(item: dict[str, Any]) -> str:
    assigned = item.get("assigned_object")
    if isinstance(assigned, dict):
        parent = assigned.get("device") or assigned.get("virtual_machine")
        parent_name = nested_name(parent)
        name = nested_name(assigned)
        if parent_name and name and parent_name != name:
            return f"{parent_name} / {name}"
        return parent_name or name
    return item.get("dns_name") or item.get("description") or ""


def ip_status_label(status: str) -> str:
    return {
        "active": "已用",
        "reserved": "预留/空闲",
        "deprecated": "废弃",
        "dhcp": "DHCP",
        "slaac": "SLAAC",
    }.get(status.lower(), status or "未知")


def prefix_status_label(status: str) -> str:
    return {
        "active": "启用",
        "reserved": "预留",
        "deprecated": "废弃",
        "container": "容器",
    }.get(status.lower(), status or "未知")


def ip_counts_as_used(status: str) -> bool:
    return status.lower() == "active"


def most_common_value(items: list[dict[str, Any]], key: str, empty_value: str) -> str:
    values = [str(item.get(key) or "") for item in items]
    counts = Counter(value for value in values if value and value != empty_value)
    if not counts:
        return empty_value
    return counts.most_common(1)[0][0]


def normalize_ip(item: dict[str, Any]) -> dict[str, Any]:
    address = str(item.get("address") or "")
    try:
        interface = ipaddress.ip_interface(address)
        ip_value = str(interface.ip)
        family = interface.version
    except ValueError:
        ip_value = address.split("/", 1)[0]
        family = 0
    status = status_value(item.get("status")) or "unknown"
    return {
        "id": item.get("id"),
        "address": address,
        "ip": ip_value,
        "family": family,
        "status": status,
        "status_label": ip_status_label(status),
        "is_used": ip_counts_as_used(status),
        "role": nested_name(item.get("role")),
        "tenant": nested_name(item.get("tenant")),
        "customer": ip_customer(item),
        "owner": nested_name(item.get("owner")),
        "supplier": ip_supplier(item),
        "assignee": ip_assignee(item),
        "dns_name": item.get("dns_name") or "",
        "description": item.get("description") or "",
        "tags": [nested_name(tag) for tag in item.get("tags") or []],
    }


def normalize_prefix(item: dict[str, Any], ips: list[dict[str, Any]]) -> dict[str, Any]:
    prefix = str(item.get("prefix") or "")
    try:
        network = ipaddress.ip_network(prefix, strict=False)
    except ValueError:
        network = None

    contained_ips = []
    if network:
        for ip in ips:
            try:
                if ipaddress.ip_address(ip["ip"]) in network:
                    contained_ips.append(ip)
            except ValueError:
                continue

    total = int(network.num_addresses) if network else 0
    usable = total
    used = len([ip for ip in contained_ips if ip.get("is_used")])
    reserved = len([ip for ip in contained_ips if str(ip.get("status") or "").lower() == "reserved"])
    registered = len(contained_ips)
    utilization = round(used / usable * 100, 2) if usable else 0
    customer_counts = Counter(ip["customer"] for ip in contained_ips)
    top_customers = [{"name": name, "count": count} for name, count in customer_counts.most_common(5)]
    customer = nested_name(item.get("tenant")) or custom_field_value(
        item.get("custom_fields") or {},
        ("customer", "client", "user", "tenant"),
    )
    if not customer and contained_ips:
        customer = most_common_value(contained_ips, "customer", "未归属")
    supplier = ip_supplier(item)
    if supplier == "未指定" and contained_ips:
        supplier = most_common_value(contained_ips, "supplier", "未指定")
    status = status_value(item.get("status")) or "unknown"
    return {
        "id": item.get("id"),
        "prefix": prefix,
        "family": network.version if network else 0,
        "status": status,
        "status_label": prefix_status_label(status),
        "role": nested_name(item.get("role")),
        "site": nested_name(item.get("site")),
        "vrf": nested_name(item.get("vrf")),
        "tenant": nested_name(item.get("tenant")),
        "customer": customer or "共享/未归属",
        "owner": nested_name(item.get("owner")),
        "supplier": supplier,
        "vlan": nested_name(item.get("vlan")),
        "description": item.get("description") or "",
        "total": total,
        "usable": usable,
        "used": used,
        "reserved": reserved,
        "registered": registered,
        "available": max(usable - used, 0),
        "utilization": utilization,
        "top_customers": top_customers,
        "ips": contained_ips,
    }


async def netbox_get_all(path: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    url = urljoin(netbox_base_url(), path.lstrip("/"))
    query = {"limit": 200, **(params or {})}
    results: list[dict[str, Any]] = []
    async with httpx.AsyncClient(timeout=30, verify=False, trust_env=False) as client:
        while url:
            response = await client.get(url, params=query, headers=netbox_headers())
            query = None
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                if "Just a moment" in response.text or "challenges.cloudflare.com" in response.text:
                    raise RuntimeError("NetBox API is blocked by Cloudflare challenge; allowlist this server or bypass /api/") from exc
                raise RuntimeError(f"NetBox API HTTP {response.status_code}: {response.text[:500]}") from exc
            data = response.json()
            if isinstance(data, list):
                results.extend(data)
                break
            results.extend(data.get("results") or [])
            url = data.get("next") or ""
    return results


@router.get("/ipam/overview", summary="NetBox IPAM overview")
async def ipam_overview(
    search: str = Query(""),
    family: int | None = Query(None),
    status: str = Query(""),
):
    try:
        prefixes_raw, ips_raw = await fetch_ipam_data()
    except Exception as exc:
        return Fail(msg=f"读取 NetBox IPAM 数据失败: {type(exc).__name__}: {exc}")

    ips = [normalize_ip(item) for item in ips_raw]
    prefixes = [normalize_prefix(item, ips) for item in prefixes_raw]

    if family in {4, 6}:
        prefixes = [item for item in prefixes if item["family"] == family]
        ips = [item for item in ips if item["family"] == family]
    if status:
        prefixes = [item for item in prefixes if item["status"] == status]
        ips = [item for item in ips if item["status"] == status]
    keyword = search.strip().lower()
    if keyword:
        prefixes = [
            item
            for item in prefixes
            if keyword
            in " ".join(
                str(item.get(key) or "")
                for key in ("prefix", "customer", "supplier", "tenant", "owner", "site", "role", "description", "vlan", "vrf")
            ).lower()
        ]
        prefix_networks = []
        for item in prefixes:
            try:
                prefix_networks.append(ipaddress.ip_network(item["prefix"], strict=False))
            except ValueError:
                continue
        filtered_ips = []
        for item in ips:
            text_match = keyword in " ".join(
                str(item.get(key) or "") for key in ("address", "customer", "supplier", "assignee", "dns_name", "description")
            ).lower()
            network_match = False
            if not text_match:
                try:
                    ip_value = ipaddress.ip_address(item["ip"])
                    network_match = any(ip_value in network for network in prefix_networks)
                except ValueError:
                    network_match = False
            if text_match or network_match:
                filtered_ips.append(item)
        ips = filtered_ips

    customer_counts = Counter()
    supplier_counts = Counter()
    for item in ips:
        customer_counts[item["customer"]] += 1
        supplier_counts[item["supplier"]] += 1
    role_counts = Counter(item["role"] or "未分类" for item in prefixes)
    site_counts = Counter(item["site"] or "未指定" for item in prefixes)
    total_usable = sum(item["usable"] for item in prefixes)
    total_used = sum(item["used"] for item in prefixes)
    summary = {
        "prefix_count": len(prefixes),
        "ip_count": len(ips),
        "used": total_used,
        "usable": total_usable,
        "available": max(total_usable - total_used, 0),
        "utilization": round(total_used / total_usable * 100, 2) if total_usable else 0,
        "customer_count": len(customer_counts),
        "supplier_count": len(supplier_counts),
    }
    return Success(
        data={
            "summary": summary,
            "prefixes": sorted(prefixes, key=lambda item: (item["family"], item["prefix"])),
            "ips": sorted(ips, key=lambda item: item["ip"]),
            "customers": [{"name": name, "count": count} for name, count in customer_counts.most_common()],
            "suppliers": [{"name": name, "count": count} for name, count in supplier_counts.most_common()],
            "roles": [{"name": name, "count": count} for name, count in role_counts.most_common()],
            "sites": [{"name": name, "count": count} for name, count in site_counts.most_common()],
        }
    )


async def fetch_ipam_data() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    prefixes = await netbox_get_all("/api/ipam/prefixes/")
    ips = await netbox_get_all("/api/ipam/ip-addresses/")
    return prefixes, ips
