import asyncio
import ipaddress
from collections import Counter
from typing import Any
from urllib.parse import urljoin

import httpx
from fastapi import APIRouter, Query

from app.api.v1.pve.pve import all_vms, enrich_vm_ips, pdm_remote_resources, pdm_resources_list
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


def object_customer(item: dict[str, Any]) -> str:
    custom_fields = item.get("custom_fields") or {}
    return nested_name(item.get("tenant")) or custom_field_value(custom_fields, ("customer", "client", "user", "tenant"))


def ip_supplier(item: dict[str, Any]) -> str:
    custom_fields = item.get("custom_fields") or {}
    return (
        nested_name(item.get("owner"))
        or custom_field_value(custom_fields, ("owner", "supplier", "vendor", "provider"))
        or "未指定"
    )


def scope_name(item: dict[str, Any]) -> str:
    custom_fields = item.get("custom_fields") or {}
    return (
        nested_name(item.get("scope"))
        or nested_name(item.get("site"))
        or nested_name(item.get("location"))
        or custom_field_value(custom_fields, ("scope", "region", "area", "location", "site"))
        or ""
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


def parse_network(value: str) -> ipaddress._BaseNetwork | None:
    try:
        return ipaddress.ip_network(value, strict=False)
    except ValueError:
        return None


def parse_address(value: str) -> ipaddress._BaseAddress | None:
    try:
        return ipaddress.ip_address(value.split("/", 1)[0])
    except ValueError:
        return None


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
        "customer": object_customer(item),
        "owner": nested_name(item.get("owner")),
        "supplier": ip_supplier(item),
        "assignee": ip_assignee(item),
        "dns_name": item.get("dns_name") or "",
        "description": item.get("description") or "",
        "tags": [nested_name(tag) for tag in item.get("tags") or []],
    }


def normalize_ip_range(item: dict[str, Any], ips: list[dict[str, Any]]) -> dict[str, Any]:
    start_address = str(item.get("start_address") or "")
    end_address = str(item.get("end_address") or "")
    start_ip = parse_address(start_address)
    end_ip = parse_address(end_address)
    contained_ips = []
    if start_ip and end_ip:
        for ip in ips:
            ip_value = parse_address(ip["ip"])
            if ip_value and ip_value.version == start_ip.version and start_ip <= ip_value <= end_ip:
                contained_ips.append(ip)
    status = status_value(item.get("status")) or "unknown"
    return {
        "id": item.get("id"),
        "range": f"{start_address}-{end_address}",
        "start_address": start_address,
        "end_address": end_address,
        "family": start_ip.version if start_ip else 0,
        "status": status,
        "status_label": prefix_status_label(status),
        "role": nested_name(item.get("role")),
        "tenant": nested_name(item.get("tenant")),
        "customer": object_customer(item),
        "owner": nested_name(item.get("owner")),
        "supplier": ip_supplier(item),
        "scope": scope_name(item),
        "region": scope_name(item),
        "description": item.get("description") or "",
        "ips": contained_ips,
    }


def range_cidr_label(start_ip: ipaddress._BaseAddress | None, end_ip: ipaddress._BaseAddress | None) -> str:
    if not start_ip or not end_ip:
        return ""
    networks = list(ipaddress.summarize_address_range(start_ip, end_ip))
    if len(networks) == 1:
        return str(networks[0])
    return f"{start_ip}-{end_ip}"


def parent_prefix_for_range(
    start_ip: ipaddress._BaseAddress | None,
    end_ip: ipaddress._BaseAddress | None,
    prefixes_raw: list[dict[str, Any]],
) -> str:
    if not start_ip or not end_ip:
        return ""
    candidates = []
    for item in prefixes_raw:
        network = prefix_network(item)
        if network and network.version == start_ip.version and start_ip in network and end_ip in network:
            candidates.append(network)
    if not candidates:
        return ""
    return str(sorted(candidates, key=lambda network: network.prefixlen, reverse=True)[0])


def parent_prefix_for_prefix(item: dict[str, Any], prefixes_raw: list[dict[str, Any]]) -> str:
    network = prefix_network(item)
    if not network:
        return ""
    candidates = []
    for candidate in prefixes_raw:
        if candidate.get("id") == item.get("id"):
            continue
        candidate_network = prefix_network(candidate)
        if (
            candidate_network
            and candidate_network.version == network.version
            and candidate_network.prefixlen < network.prefixlen
            and network.subnet_of(candidate_network)
        ):
            candidates.append(candidate_network)
    if not candidates:
        return ""
    return str(sorted(candidates, key=lambda candidate_network: candidate_network.prefixlen, reverse=True)[0])


def normalize_range_segment(
    item: dict[str, Any],
    prefixes_raw: list[dict[str, Any]],
) -> dict[str, Any]:
    start_ip = parse_address(item["start_address"])
    end_ip = parse_address(item["end_address"])
    prefix = range_cidr_label(start_ip, end_ip) or item["range"]
    total = int(end_ip) - int(start_ip) + 1 if start_ip and end_ip and start_ip.version == end_ip.version else len(item["ips"])
    used = len([ip for ip in item["ips"] if ip.get("is_used")])
    reserved = len([ip for ip in item["ips"] if str(ip.get("status") or "").lower() == "reserved"])
    registered = len(item["ips"])
    utilization = round(used / total * 100, 2) if total else 0
    customer_counts = Counter(ip["customer"] for ip in item["ips"])
    top_customers = [{"name": name, "count": count} for name, count in customer_counts.most_common(5)]
    customer = item["customer"]
    supplier = item["supplier"]
    if supplier == "未指定" and item["ips"]:
        supplier = most_common_value(item["ips"], "supplier", "未指定")
    return {
        "id": f"range-{item['id']}",
        "prefix": prefix,
        "family": item["family"],
        "status": item["status"],
        "status_label": item["status_label"],
        "role": item["role"],
        "site": "",
        "scope": item.get("scope") or "",
        "region": item.get("region") or item.get("scope") or "",
        "vrf": "",
        "tenant": item["tenant"],
        "customer": customer,
        "owner": item["owner"],
        "supplier": supplier,
        "vlan": "",
        "description": item["description"],
        "total": total,
        "usable": total,
        "used": used,
        "reserved": reserved,
        "registered": registered,
        "available": max(total - used, 0),
        "utilization": utilization,
        "top_customers": top_customers,
        "child_prefix_count": 0,
        "range_count": 1,
        "child_prefixes": [],
        "ip_ranges": [item],
        "parent_prefix": parent_prefix_for_range(start_ip, end_ip, prefixes_raw),
        "segment_type": "range",
        "ips": item["ips"],
    }


def prefix_network(item: dict[str, Any]) -> ipaddress._BaseNetwork | None:
    return parse_network(str(item.get("prefix") or ""))


def child_prefixes_for(parent: dict[str, Any], prefixes_raw: list[dict[str, Any]]) -> list[dict[str, Any]]:
    parent_network = prefix_network(parent)
    if not parent_network:
        return []
    parent_id = parent.get("id")
    children = []
    for item in prefixes_raw:
        if item.get("id") == parent_id:
            continue
        child_network = prefix_network(item)
        if child_network and child_network.version == parent_network.version and child_network.subnet_of(parent_network):
            children.append(item)
    return children


def ranges_for_prefix(parent_network: ipaddress._BaseNetwork | None, ranges: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not parent_network:
        return []
    matched = []
    for item in ranges:
        start_ip = parse_address(item["start_address"])
        end_ip = parse_address(item["end_address"])
        if (
            start_ip
            and end_ip
            and start_ip.version == parent_network.version
            and start_ip in parent_network
            and end_ip in parent_network
        ):
            matched.append(item)
    return matched


def prefix_is_container(item: dict[str, Any]) -> bool:
    item_id = str(item.get("id") or "")
    return not item_id.startswith("range-") and (
        int(item.get("child_prefix_count") or 0) > 0 or int(item.get("range_count") or 0) > 0
    )


def same_filter_value(value: str, expected: str) -> bool:
    return str(value or "").strip().lower() == str(expected or "").strip().lower()


def prefix_networks(prefixes: list[dict[str, Any]]) -> list[ipaddress._BaseNetwork]:
    networks = []
    for item in prefixes:
        network = parse_network(str(item.get("prefix") or ""))
        if network:
            networks.append(network)
    return networks


def ips_in_prefixes(ips: list[dict[str, Any]], prefixes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    networks = prefix_networks(prefixes)
    if not networks:
        return []
    matched = []
    for item in ips:
        ip_value = parse_address(str(item.get("ip") or item.get("address") or ""))
        if ip_value and any(ip_value.version == network.version and ip_value in network for network in networks):
            matched.append(item)
    return matched


def option_items(values: list[str]) -> list[dict[str, str]]:
    return [{"label": value, "value": value} for value in sorted({value for value in values if value})]


def strip_embedded_ips(prefixes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cleaned = []
    for item in prefixes:
        prefix = {**item, "ips": []}
        prefix["ip_ranges"] = [{**ip_range, "ips": []} for ip_range in item.get("ip_ranges") or []]
        cleaned.append(prefix)
    return cleaned


def segment_contains_ip(segment: str, ip_value: str) -> bool:
    address = parse_address(ip_value)
    if not address:
        return False
    if "-" in segment:
        start_value, end_value = segment.split("-", 1)
        start_ip = parse_address(start_value.strip())
        end_ip = parse_address(end_value.strip())
        return bool(start_ip and end_ip and address.version == start_ip.version == end_ip.version and start_ip <= address <= end_ip)
    network = parse_network(segment)
    return bool(network and address.version == network.version and address in network)


def ip_sort_key(item: dict[str, Any]) -> tuple[int, int, str]:
    address = parse_address(str(item.get("address") or item.get("ip") or item.get("start_address") or ""))
    if address:
        return address.version, int(address), str(item.get("address") or "")
    return 0, 0, str(item.get("address") or "")


def normalize_available_segment(start_ip: ipaddress._BaseAddress, end_ip: ipaddress._BaseAddress) -> dict[str, Any]:
    count = int(end_ip) - int(start_ip) + 1
    label = f"{count} 可用 IP" if count > 1 else f"{start_ip} 可用"
    return {
        "id": f"available-{start_ip}-{end_ip}",
        "entry_type": "available",
        "address": label,
        "ip": str(start_ip),
        "start_address": str(start_ip),
        "end_address": str(end_ip),
        "family": start_ip.version,
        "status": "available",
        "status_label": "Available",
        "is_used": False,
        "role": "",
        "tenant": "",
        "customer": "",
        "owner": "",
        "supplier": "",
        "assignee": "",
        "dns_name": "",
        "description": "",
        "available_count": count,
    }


def network_usable_bounds(network: ipaddress._BaseNetwork) -> tuple[int, int] | None:
    first = int(network.network_address)
    last = int(network.broadcast_address)
    if network.version == 4 and network.prefixlen < 31:
        first += 1
        last -= 1
    elif network.version == 6 and network.prefixlen < 127:
        first += 1
    if first > last:
        return None
    return first, last


def build_prefix_ip_rows(prefix: str, assigned_ips: list[dict[str, Any]]) -> list[dict[str, Any]]:
    network = parse_network(prefix)
    if not network:
        return sorted([normalize_ip(item) for item in assigned_ips], key=ip_sort_key)

    normalized_ips = sorted([normalize_ip(item) for item in assigned_ips], key=ip_sort_key)
    assigned_by_value = {
        int(address): item
        for item in normalized_ips
        if (address := parse_address(str(item.get("ip") or item.get("address") or ""))) and address.version == network.version
    }
    bounds = network_usable_bounds(network)
    if not bounds:
        return list(assigned_by_value.values())

    first, last = bounds
    cursor = first
    rows: list[dict[str, Any]] = []
    for value, item in sorted(assigned_by_value.items()):
        if value < first or value > last:
            continue
        if cursor < value:
            rows.append(normalize_available_segment(ipaddress.ip_address(cursor), ipaddress.ip_address(value - 1)))
        rows.append(item)
        cursor = value + 1

    if cursor <= last:
        rows.append(normalize_available_segment(ipaddress.ip_address(cursor), ipaddress.ip_address(last)))

    return rows


async def netbox_get_all_optional(path: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    try:
        return await netbox_get_all(path, params)
    except Exception:
        return []


async def fetch_filter_source_data() -> dict[str, list[dict[str, Any]]]:
    tenants = await netbox_get_all_optional("/api/tenancy/tenants/")
    regions = await netbox_get_all_optional("/api/dcim/regions/")
    sites = await netbox_get_all_optional("/api/dcim/sites/")
    locations = await netbox_get_all_optional("/api/dcim/locations/")
    return {
        "tenants": tenants,
        "regions": regions,
        "sites": sites,
        "locations": locations,
    }


def build_filter_options(
    prefixes_raw: list[dict[str, Any]],
    ranges_raw: list[dict[str, Any]],
    filter_sources: dict[str, list[dict[str, Any]]],
) -> dict[str, list[dict[str, str]]]:
    customer_values = [nested_name(item) for item in filter_sources.get("tenants", [])]
    customer_values.extend(object_customer(item) for item in prefixes_raw)
    customer_values.extend(object_customer(item) for item in ranges_raw)

    region_values = [nested_name(item) for item in filter_sources.get("regions", [])]
    region_values.extend(nested_name(item) for item in filter_sources.get("sites", []))
    region_values.extend(nested_name(item) for item in filter_sources.get("locations", []))
    region_values.extend(scope_name(item) for item in prefixes_raw)
    region_values.extend(scope_name(item) for item in ranges_raw)

    supplier_values = [ip_supplier(item) for item in prefixes_raw]
    supplier_values.extend(ip_supplier(item) for item in ranges_raw)
    supplier_values = [value for value in supplier_values if value != "未指定"]

    return {
        "regions": option_items(region_values),
        "customers": option_items(customer_values),
        "suppliers": option_items(supplier_values),
    }


def normalize_prefix(
    item: dict[str, Any],
    ips: list[dict[str, Any]],
    prefixes_raw: list[dict[str, Any]],
    ranges: list[dict[str, Any]],
) -> dict[str, Any]:
    prefix = str(item.get("prefix") or "")
    network = parse_network(prefix)
    child_prefixes_raw = child_prefixes_for(item, prefixes_raw)
    child_prefixes = []
    for child in child_prefixes_raw:
        child_network = prefix_network(child)
        child_prefixes.append(
            {
                "id": child.get("id"),
                "prefix": child.get("prefix"),
                "status": status_value(child.get("status")) or "unknown",
                "status_label": prefix_status_label(status_value(child.get("status")) or "unknown"),
                "role": nested_name(child.get("role")),
                "tenant": nested_name(child.get("tenant")),
                "customer": object_customer(child),
                "owner": nested_name(child.get("owner")),
                "supplier": ip_supplier(child),
                "scope": scope_name(child),
                "region": scope_name(child),
                "usable": int(child_network.num_addresses) if child_network else 0,
                "description": child.get("description") or "",
            }
        )
    child_ranges = ranges_for_prefix(network, ranges)

    contained_ips = []
    if network:
        for ip in ips:
            ip_value = parse_address(ip["ip"])
            if ip_value and ip_value.version == network.version and ip_value in network:
                contained_ips.append(ip)

    total = int(network.num_addresses) if network else 0
    usable = total
    used = len([ip for ip in contained_ips if ip.get("is_used")])
    reserved = len([ip for ip in contained_ips if str(ip.get("status") or "").lower() == "reserved"])
    registered = len(contained_ips)
    utilization = round(used / usable * 100, 2) if usable else 0
    customer_counts = Counter(ip["customer"] for ip in contained_ips)
    top_customers = [{"name": name, "count": count} for name, count in customer_counts.most_common(5)]
    customer = object_customer(item)
    supplier = ip_supplier(item)
    if supplier == "未指定":
        supplier_sources = child_prefixes + child_ranges + contained_ips
        supplier = most_common_value(supplier_sources, "supplier", "未指定")
    status = status_value(item.get("status")) or "unknown"
    parent_prefix = parent_prefix_for_prefix(item, prefixes_raw)
    return {
        "id": item.get("id"),
        "prefix": prefix,
        "family": network.version if network else 0,
        "status": status,
        "status_label": prefix_status_label(status),
        "role": nested_name(item.get("role")),
        "site": nested_name(item.get("site")),
        "scope": scope_name(item),
        "region": scope_name(item),
        "vrf": nested_name(item.get("vrf")),
        "tenant": nested_name(item.get("tenant")),
        "customer": customer,
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
        "child_prefix_count": len(child_prefixes),
        "range_count": len(child_ranges),
        "child_prefixes": child_prefixes,
        "ip_ranges": child_ranges,
        "parent_prefix": parent_prefix,
        "segment_type": "prefix",
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


async def netbox_get_page(path: str, params: dict[str, Any] | None = None) -> tuple[int, list[dict[str, Any]]]:
    url = urljoin(netbox_base_url(), path.lstrip("/"))
    query = params or {}
    async with httpx.AsyncClient(timeout=30, verify=False, trust_env=False) as client:
        response = await client.get(url, params=query, headers=netbox_headers())
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            if "Just a moment" in response.text or "challenges.cloudflare.com" in response.text:
                raise RuntimeError("NetBox API is blocked by Cloudflare challenge; allowlist this server or bypass /api/") from exc
            raise RuntimeError(f"NetBox API HTTP {response.status_code}: {response.text[:500]}") from exc
        data = response.json()
        if isinstance(data, list):
            return len(data), data
        return int(data.get("count") or 0), data.get("results") or []


async def netbox_request(
    method: str,
    path: str,
    params: dict[str, Any] | None = None,
    json_body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    url = urljoin(netbox_base_url(), path.lstrip("/"))
    headers = {**netbox_headers(), "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=30, verify=False, trust_env=False) as client:
        response = await client.request(method, url, params=params or {}, json=json_body, headers=headers)
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            if "Just a moment" in response.text or "challenges.cloudflare.com" in response.text:
                raise RuntimeError("NetBox API is blocked by Cloudflare challenge; allowlist this server or bypass /api/") from exc
            raise RuntimeError(f"NetBox API HTTP {response.status_code}: {response.text[:500]}") from exc
        if not response.content:
            return {}
        data = response.json()
        return data if isinstance(data, dict) else {"data": data}


async def netbox_filter_ips_by_segment(segment: str, page: int, page_size: int) -> tuple[int, list[dict[str, Any]]]:
    offset = 0
    limit = 200
    matched: list[dict[str, Any]] = []
    total_matches = 0
    page_start = (page - 1) * page_size
    page_end = page_start + page_size

    while True:
        total, batch = await netbox_get_page(
            "/api/ipam/ip-addresses/",
            {"limit": limit, "offset": offset, "ordering": "address"},
        )
        if not batch:
            break
        for item in batch:
            if segment_contains_ip(segment, str(item.get("address") or "")):
                if page_start <= total_matches < page_end:
                    matched.append(item)
                total_matches += 1
        offset += len(batch)
        if offset >= total:
            break
    return total_matches, matched


async def prefix_ip_count(prefix: str, status: str = "") -> int:
    params: dict[str, Any] = {"parent": prefix, "limit": 1, "offset": 0}
    if status:
        params["status"] = status
    total, _ = await netbox_get_page("/api/ipam/ip-addresses/", params)
    return total


async def build_prefix_ip_stats(prefixes_raw: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    async def build_item(item: dict[str, Any]) -> tuple[str, dict[str, int]]:
        prefix = str(item.get("prefix") or "")
        if not prefix:
            return prefix, {"registered": 0, "used": 0, "reserved": 0}
        registered, used, reserved = await asyncio.gather(
            prefix_ip_count(prefix),
            prefix_ip_count(prefix, "active"),
            prefix_ip_count(prefix, "reserved"),
        )
        return prefix, {"registered": registered, "used": used, "reserved": reserved}

    pairs = await asyncio.gather(*(build_item(item) for item in prefixes_raw))
    return {prefix: stats for prefix, stats in pairs if prefix}


def apply_prefix_ip_stats(prefixes: list[dict[str, Any]], stats: dict[str, dict[str, int]]) -> list[dict[str, Any]]:
    for item in prefixes:
        item_stats = stats.get(item.get("prefix") or "", {})
        used = int(item_stats.get("used") or 0)
        reserved = int(item_stats.get("reserved") or 0)
        registered = int(item_stats.get("registered") or 0)
        usable = int(item.get("usable") or 0)
        item["used"] = used
        item["reserved"] = reserved
        item["registered"] = registered
        item["available"] = max(usable - used, 0)
        item["utilization"] = round(used / usable * 100, 2) if usable else 0
    return prefixes


def pve_ip_address_with_prefix(ip_value: str) -> str:
    address = ipaddress.ip_address(str(ip_value).strip())
    prefix_length = 32 if address.version == 4 else 128
    return f"{address}/{prefix_length}"


def pve_sync_description(vm: dict[str, Any]) -> str:
    remote = str(vm.get("remote") or "")
    vmid = str(vm.get("vmid") or "")
    name = str(vm.get("name") or "").strip()
    node = str(vm.get("node") or "").strip()
    suffix = " ".join([value for value in (name, node) if value])
    return f"[CATIXS_VM_SYNC remote={remote} vmid={vmid}] {suffix}".strip()


def same_netbox_address(left: str, right: str) -> bool:
    try:
        return ipaddress.ip_interface(left) == ipaddress.ip_interface(right)
    except ValueError:
        return left == right


async def find_netbox_ip_address(address: str) -> dict[str, Any] | None:
    items = await netbox_get_all("/api/ipam/ip-addresses/", {"address": address})
    for item in items:
        if same_netbox_address(str(item.get("address") or ""), address):
            return item

    ip_value = address.split("/", 1)[0]
    items = await netbox_get_all("/api/ipam/ip-addresses/", {"q": ip_value})
    for item in items:
        if same_netbox_address(str(item.get("address") or ""), address):
            return item
    return None


async def sync_pve_ip_to_netbox(vm: dict[str, Any], ip_value: str) -> dict[str, Any]:
    address = pve_ip_address_with_prefix(ip_value)
    description = pve_sync_description(vm)
    existing = await find_netbox_ip_address(address)
    payload = {
        "address": address,
        "status": "active",
        "description": description,
    }
    if existing:
        current_description = str(existing.get("description") or "").strip()
        if current_description and "CATIXS_VM_SYNC" not in current_description and current_description != description:
            return {"action": "skipped", "address": address, "id": existing.get("id"), "vm": vm.get("name") or ""}
        update_payload = {
            key: value
            for key, value in payload.items()
            if key != "address" and str(existing.get(key) or "") != str(value or "")
        }
        if update_payload:
            await netbox_request("PATCH", f"/api/ipam/ip-addresses/{existing['id']}/", json_body=update_payload)
            return {"action": "updated", "address": address, "id": existing.get("id"), "vm": vm.get("name") or ""}
        return {"action": "unchanged", "address": address, "id": existing.get("id"), "vm": vm.get("name") or ""}

    created = await netbox_request("POST", "/api/ipam/ip-addresses/", json_body=payload)
    return {"action": "created", "address": address, "id": created.get("id"), "vm": vm.get("name") or ""}


async def pve_vms_for_sync(node: str = "") -> list[dict[str, Any]]:
    if node:
        try:
            resources = await pdm_remote_resources(node)
        except Exception:
            resources = []
        data = [{"remote": node, "resources": resources}]
    else:
        data = await pdm_resources_list()
    vms = all_vms(data)
    if node:
        vms = [vm for vm in vms if vm.get("remote") == node]
    await enrich_vm_ips(vms)
    return vms


def paginate_items(items: list[dict[str, Any]], page: int, page_size: int) -> list[dict[str, Any]]:
    start = (page - 1) * page_size
    return items[start : start + page_size]


@router.get("/ipam/overview", summary="NetBox IPAM overview")
async def ipam_overview(
    search: str = Query(""),
    family: int | None = Query(None),
    status: str = Query(""),
    region: str = Query(""),
    customer: str = Query(""),
    supplier: str = Query(""),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
):
    needs_global_filter = any(value.strip() for value in (region, customer, supplier))
    try:
        prefix_total, prefixes_raw, ranges_raw, ips_raw = await fetch_ipam_data(
            page,
            page_size,
            search,
            family,
            status,
            needs_global_filter,
        )
    except Exception as exc:
        return Fail(msg=f"读取 NetBox IPAM 数据失败: {type(exc).__name__}: {exc}")
    filter_sources, filter_prefixes_raw = await asyncio.gather(
        fetch_filter_source_data(),
        fetch_filter_prefixes(prefixes_raw, search, family, status, needs_global_filter),
    )

    ips = [normalize_ip(item) for item in ips_raw]
    ip_ranges = [normalize_ip_range(item, ips) for item in ranges_raw]
    prefixes = [normalize_prefix(item, ips, prefixes_raw, ip_ranges) for item in prefixes_raw]
    filter_options = build_filter_options(filter_prefixes_raw, ranges_raw, filter_sources)

    if family in {4, 6}:
        prefixes = [item for item in prefixes if item["family"] == family]
        ips = [item for item in ips if item["family"] == family]
    if status:
        prefixes = [item for item in prefixes if item["status"] == status]
        ips = [item for item in ips if item["status"] == status]
    if region:
        prefixes = [
            item
            for item in prefixes
            if same_filter_value(item.get("region") or item.get("scope") or item.get("site") or "", region)
        ]
        ips = ips_in_prefixes(ips, prefixes)
    if customer:
        prefixes = [item for item in prefixes if same_filter_value(item.get("customer") or "", customer)]
        ips = [item for item in ips if same_filter_value(item.get("customer") or "", customer)]
    if supplier:
        prefixes = [item for item in prefixes if same_filter_value(item.get("supplier") or item.get("owner") or "", supplier)]
        ips = [item for item in ips if same_filter_value(item.get("supplier") or item.get("owner") or "", supplier)]
    keyword = search.strip().lower()
    if keyword:
        prefixes = [
            item
            for item in prefixes
            if keyword
            in " ".join(
                str(item.get(key) or "")
                for key in (
                    "prefix",
                    "customer",
                    "supplier",
                    "tenant",
                    "owner",
                    "site",
                    "scope",
                    "region",
                    "role",
                    "description",
                    "vlan",
                    "vrf",
                )
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

    filtered_prefix_values = {item["prefix"] for item in prefixes}
    prefix_stats_raw = [item for item in prefixes_raw if str(item.get("prefix") or "") in filtered_prefix_values]
    prefix_stats = await build_prefix_ip_stats(prefix_stats_raw)
    prefixes = apply_prefix_ip_stats(prefixes, prefix_stats)

    customer_counts = Counter()
    supplier_counts = Counter()
    for item in ips:
        customer_counts[item["customer"]] += 1
        supplier_counts[item["supplier"]] += 1
    role_counts = Counter(item["role"] or "未分类" for item in prefixes)
    site_counts = Counter(item["site"] or "未指定" for item in prefixes)
    summary_prefixes = [item for item in prefixes if not prefix_is_container(item)]
    total_usable = sum(item["usable"] for item in summary_prefixes)
    total_used = sum(item["used"] for item in summary_prefixes)
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
    prefixes = sorted(prefixes, key=lambda item: (item["family"], item["prefix"]))
    prefix_total = len(prefixes) if needs_global_filter else prefix_total
    page_prefixes = paginate_items(prefixes, page, page_size) if needs_global_filter else prefixes
    return Success(
        data={
            "summary": summary,
            "prefixes": strip_embedded_ips(page_prefixes),
            "ips": [],
            "total": prefix_total,
            "page": page,
            "page_size": page_size,
            "customers": [{"name": name, "count": count} for name, count in customer_counts.most_common()],
            "suppliers": [{"name": name, "count": count} for name, count in supplier_counts.most_common()],
            "roles": [{"name": name, "count": count} for name, count in role_counts.most_common()],
            "sites": [{"name": name, "count": count} for name, count in site_counts.most_common()],
            "filter_options": filter_options,
        }
    )


@router.get("/ipam/prefix-ips", summary="NetBox IPAM prefix IP list")
async def ipam_prefix_ips(
    prefix: str = Query(...),
    prefix_id: str = Query(""),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
):
    try:
        numeric_prefix_id = int(prefix_id) if str(prefix_id or "").isdigit() else None
        if numeric_prefix_id:
            _, prefix_items = await netbox_get_page("/api/ipam/prefixes/", {"id": numeric_prefix_id, "limit": 1})
            if prefix_items and prefix_items[0].get("prefix"):
                prefix = str(prefix_items[0]["prefix"])
        params = {"parent": prefix, "ordering": "address"}
        try:
            ips_raw = await netbox_get_all("/api/ipam/ip-addresses/", params)
        except Exception:
            if not parse_network(prefix):
                raise
            total, ips_raw = await netbox_filter_ips_by_segment(prefix, 1, 100000)
        if not ips_raw and parse_network(prefix):
            total, ips_raw = await netbox_filter_ips_by_segment(prefix, 1, 100000)
        rows = build_prefix_ip_rows(prefix, ips_raw)
        total = len(rows)
        start = (page - 1) * page_size
    except Exception as exc:
        return Fail(msg=f"璇诲彇 NetBox IP 鏁版嵁澶辫触: {type(exc).__name__}: {exc}")

    return Success(
        data={
            "items": rows[start : start + page_size],
            "total": total,
            "page": page,
            "page_size": page_size,
        }
    )


@router.post("/ipam/sync-pve-ips", summary="Sync PVE guest-agent IPs to NetBox")
async def sync_pve_ips_to_netbox(
    node: str = Query(""),
):
    try:
        vms = await pve_vms_for_sync(node)
    except Exception as exc:
        return Fail(msg=f"读取 PVE IP 数据失败: {type(exc).__name__}: {exc}")

    targets: list[tuple[dict[str, Any], str]] = []
    seen: set[str] = set()
    for vm in vms:
        for ip_value in vm.get("ips") or vm.get("ip_addresses") or []:
            try:
                address = pve_ip_address_with_prefix(str(ip_value))
            except ValueError:
                continue
            key = address.lower()
            if key in seen:
                continue
            seen.add(key)
            targets.append((vm, str(ip_value)))

    semaphore = asyncio.Semaphore(6)

    async def sync_one(vm: dict[str, Any], ip_value: str) -> dict[str, Any]:
        async with semaphore:
            try:
                return await sync_pve_ip_to_netbox(vm, ip_value)
            except Exception as exc:
                try:
                    address = pve_ip_address_with_prefix(ip_value)
                except ValueError:
                    address = str(ip_value)
                return {
                    "action": "failed",
                    "address": address,
                    "vm": vm.get("name") or "",
                    "error": f"{type(exc).__name__}: {exc}",
                }

    results = await asyncio.gather(*(sync_one(vm, ip_value) for vm, ip_value in targets))
    counts = Counter(str(item.get("action") or "unknown") for item in results)
    failures = [item for item in results if item.get("action") == "failed"]

    return Success(
        msg="PVE IP 同步完成" if not failures else "PVE IP 同步完成，部分失败",
        data={
            "vm_count": len(vms),
            "ip_count": len(targets),
            "created": counts.get("created", 0),
            "updated": counts.get("updated", 0),
            "unchanged": counts.get("unchanged", 0),
            "skipped": counts.get("skipped", 0),
            "failed": counts.get("failed", 0),
            "failures": failures[:20],
            "items": results,
        },
    )


async def fetch_ipam_data(
    page: int,
    page_size: int,
    search: str = "",
    family: int | None = None,
    status: str = "",
    fetch_all_prefixes: bool = False,
) -> tuple[int, list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    params: dict[str, Any] = {
        "ordering": "prefix",
    }
    if search.strip():
        params["q"] = search.strip()
    if family in {4, 6}:
        params["family"] = family
    if status.strip():
        params["status"] = status.strip()

    if fetch_all_prefixes:
        prefixes = await netbox_get_all("/api/ipam/prefixes/", params)
        return len(prefixes), prefixes, [], []

    page_params = {
        **params,
        "limit": page_size,
        "offset": (page - 1) * page_size,
    }
    total, prefixes = await netbox_get_page("/api/ipam/prefixes/", page_params)
    return total, prefixes, [], []


async def fetch_filter_prefixes(
    current_prefixes: list[dict[str, Any]],
    search: str = "",
    family: int | None = None,
    status: str = "",
    already_global: bool = False,
) -> list[dict[str, Any]]:
    if already_global:
        return current_prefixes

    params: dict[str, Any] = {"ordering": "prefix"}
    if search.strip():
        params["q"] = search.strip()
    if family in {4, 6}:
        params["family"] = family
    if status.strip():
        params["status"] = status.strip()
    return await netbox_get_all_optional("/api/ipam/prefixes/", params)
