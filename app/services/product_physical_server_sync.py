import hashlib
import json
import re
from typing import Any

from app.api.v1.pve.pve import (
    canonical_resource_type,
    pdm_nodes_list,
    pdm_remote_address_map,
    pdm_remote_config_detail_map,
    pdm_remote_summary_map,
    pve_node_binding_map,
    resource_groups,
)
from app.api.v1.resources.resources import device_to_sales_rows, is_free_device_status
from app.models.asset import AssetDevice, AssetRegion
from app.models.product_center import ProductCategory, ProductItem, ProductSpecAttribute, ProductSpecConfig

PHYSICAL_SERVER_SOURCE = "physical_server"
PHYSICAL_SERVER_CATEGORY_NAME = "物理服务器"
DEFAULT_PHYSICAL_SERVER_CODES = {"server_model", "cpu", "memory", "storage"}
CLOUD_VM_SOURCE = "cloud_vm"
CLOUD_VM_CATEGORY_NAME = "云主机"
DEFAULT_CLOUD_VM_CODES = {"cpu", "memory", "storage"}
ATTRIBUTE_ALIASES = {
    "server_model": ("物理服务器型号", "服务器型号", "server_model", "model", "型号"),
    "brand": ("品牌", "brand"),
    "model": ("型号", "model"),
    "cpu": ("CPU核心数", "CPU Cores", "cpu_cores", "cores", "cpu", "CPU"),
    "cpu_model": ("CPU型号", "CPU Model", "cpu_model", "processor", "Processor"),
    "cpu_count": ("CPU数量", "CPU颗数", "cpu_count"),
    "memory": ("内存总数", "内存容量", "内存大小", "内存", "memory", "Memory", "ram", "RAM"),
    "storage": ("磁盘总数", "硬盘总数", "磁盘", "硬盘", "storage", "Storage", "disk", "Disk"),
    "cabinet": ("机柜", "cabinet"),
    "location": ("位置", "机房", "location"),
    "u_position": ("U位", "u_position"),
    "status": ("状态", "status"),
}
CLOUD_ATTRIBUTE_ALIASES = {
    "cpu": {"cpu", "cpu_core", "cpu_cores", "vcpu", "vcpus", "available_vcpu", "available_cpu"},
    "memory": {"memory", "mem", "mem_total", "ram", "available_memory", "available_mem"},
    "storage": {"storage", "disk", "disk_total", "available_storage", "available_disk"},
}
BYTES_PER_GB = 1024 * 1024 * 1024


def text(value: Any, default: str = "") -> str:
    value = "" if value is None else str(value).strip()
    return value or default


def normalize_region_text(value: Any) -> str:
    return re.sub(r"\s+", " ", text(value).lower()).strip()


def compact_region_text(value: Any) -> str:
    return re.sub(r"[\s/\\|,，、-]+", "", text(value).lower()).strip()


def number_from_text(value: Any) -> str:
    raw = text(value)
    if not raw:
        return ""
    match = re.search(r"(\d+(?:\.\d+)?)", raw.replace(",", ""))
    if not match:
        return ""
    number = float(match.group(1))
    return str(int(number)) if number.is_integer() else f"{number:g}"


def capacity_to_gb(value: Any) -> str:
    raw = text(value)
    if not raw:
        return ""
    total = 0.0
    for amount, unit in re.findall(r"(\d+(?:\.\d+)?)\s*(tb|t|gb|g|gib|tib)", raw, re.IGNORECASE):
        size = float(amount)
        unit_text = unit.lower()
        total += size * 1024 if unit_text.startswith("t") else size
    if total:
        return str(int(total)) if total.is_integer() else f"{total:g}"
    return number_from_text(raw)


def sync_hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def format_number(value: float, digits: int = 2) -> str:
    rounded = round(max(0, float(value or 0)), digits)
    return str(int(rounded)) if rounded.is_integer() else f"{rounded:g}"


def bytes_to_gb(value: Any) -> float:
    try:
        number = float(value or 0)
    except (TypeError, ValueError):
        return 0
    return max(0, number) / BYTES_PER_GB


def number_value(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0


async def category_path_names(category_id: int | None) -> list[str]:
    names: list[str] = []
    current_id = category_id
    while current_id:
        category = await ProductCategory.get_or_none(id=current_id)
        if not category:
            break
        names.insert(0, category.name)
        current_id = category.parent_id
    return names


async def category_path_ids(category_id: int | None) -> list[int]:
    ids: list[int] = []
    current_id = category_id
    while current_id:
        category = await ProductCategory.get_or_none(id=current_id)
        if not category:
            break
        ids.insert(0, int(category.id))
        current_id = category.parent_id
    return ids


def normalize_category_ids(values: Any, fallback: int | None = None) -> list[int]:
    ids: list[int] = []
    raw_values = values if isinstance(values, list) else []
    for value in raw_values:
        try:
            item = int(value)
        except (TypeError, ValueError):
            continue
        if item > 0 and item not in ids:
            ids.append(item)
    if not ids and fallback:
        ids.append(int(fallback))
    return ids


async def is_physical_server_product(product: ProductItem) -> bool:
    return PHYSICAL_SERVER_CATEGORY_NAME in await category_path_names(product.category_id)


async def is_cloud_vm_product(product: ProductItem) -> bool:
    return CLOUD_VM_CATEGORY_NAME in await category_path_names(product.category_id)


async def product_matches_region(product: ProductItem, region: AssetRegion | None) -> bool:
    if not region:
        return False
    product_region = compact_region_text(product.region)
    if not product_region:
        return False
    candidates = {
        region.name,
        region.code,
        region.country,
        region.city,
        f"{region.country or ''} / {region.city or ''}",
        f"{region.country or ''}/{region.city or ''}",
    }
    return product_region in {compact_region_text(item) for item in candidates if text(item)}


def row_source(row: dict) -> tuple[int | None, str]:
    parent_id = row.get("parent_id") or row.get("id")
    try:
        source_id = int(parent_id)
    except (TypeError, ValueError):
        source_id = None
    if row.get("is_four_node"):
        return source_id, f"device:{source_id}:node:{text(row.get('node_name'))}"
    return source_id, f"device:{source_id}"


def row_attribute_value(row: dict, attribute: ProductSpecAttribute) -> str:
    attrs = row.get("attributes") if isinstance(row.get("attributes"), dict) else {}
    code = text(attribute.code)
    if code == "server_model":
        server_model = " ".join([item for item in [text(row.get("brand")), text(row.get("model"))] if item]).strip()
        return server_model or first_attr_value(attrs, ATTRIBUTE_ALIASES[code])
    if code == "brand":
        return text(row.get("brand")) or first_attr_value(attrs, ATTRIBUTE_ALIASES[code])
    if code == "model":
        return text(row.get("model")) or first_attr_value(attrs, ATTRIBUTE_ALIASES[code])
    if code == "cabinet":
        return text(row.get("cabinet")) or first_attr_value(attrs, ATTRIBUTE_ALIASES[code])
    if code == "location":
        return text(row.get("location")) or first_attr_value(attrs, ATTRIBUTE_ALIASES[code])
    if code == "u_position":
        return text(row.get("u_position")) or first_attr_value(attrs, ATTRIBUTE_ALIASES[code])
    if code == "status":
        return "空闲" if is_free_device_status(row.get("status")) else text(row.get("status"))
    aliases = ATTRIBUTE_ALIASES.get(code, ())
    raw = first_attr_value(attrs, (code, attribute.name, *aliases))
    if code in {"cpu", "cpu_count"} or attribute.attr_type == "number":
        return capacity_to_gb(raw) if code in {"memory", "storage"} else number_from_text(raw)
    if code in {"memory", "storage"}:
        return capacity_to_gb(raw)
    return raw


def first_attr_value(attrs: dict, keys: tuple[str, ...]) -> str:
    normalized = {normalize_region_text(key): value for key, value in attrs.items()}
    for key in keys:
        direct = text(attrs.get(key))
        if direct:
            return direct
        normalized_value = normalized.get(normalize_region_text(key))
        if text(normalized_value):
            return text(normalized_value)
    return ""


async def product_spec_attributes(product: ProductItem, default_codes: set[str] | None = None) -> list[ProductSpecAttribute]:
    default_codes = default_codes or DEFAULT_PHYSICAL_SERVER_CODES
    product_category_ids = await category_path_ids(product.category_id)
    rows = await ProductSpecAttribute.filter(status=True).order_by("category_id", "name")
    matched = []
    for attribute in rows:
        attr_category_ids = normalize_category_ids(attribute.category_ids, attribute.category_id)
        if attr_category_ids and set(attr_category_ids).isdisjoint(product_category_ids):
            continue
        if not attr_category_ids and attribute.code not in default_codes:
            continue
        matched.append(attribute)
    return matched


def cloud_attribute_kind(attribute: ProductSpecAttribute) -> str:
    code = normalize_region_text(attribute.code)
    name = normalize_region_text(attribute.name)
    for kind, aliases in CLOUD_ATTRIBUTE_ALIASES.items():
        if code in aliases or name in aliases:
            return kind
    return ""


def cloud_source_key(product: ProductItem, region_id: int | None) -> str:
    key = region_id or compact_region_text(product.region) or product.id
    return f"cloud-region:{key}"


def cloud_group_value_range(summary: dict[str, Any]) -> str:
    return (
        f"PVE: {summary['pve_count']} / "
        f"total vCPU: {format_number(summary['cpu_total'])} / "
        f"allocated vCPU: {format_number(summary['cpu_allocated'])} / "
        f"available vCPU: {format_number(summary['cpu_available'])} / "
        f"allocated mem: {format_number(summary['mem_allocated_gb'])}GB / "
        f"available mem: {format_number(summary['mem_available_gb'])}GB / "
        f"allocated disk: {format_number(summary['disk_allocated_gb'])}GB / "
        f"available disk: {format_number(summary['disk_available_gb'])}GB"
    )[:500]


def cloud_allocated_resources(groups: list[dict[str, Any]]) -> dict[str, float]:
    cpu = 0.0
    mem = 0.0
    disk = 0.0
    seen: set[tuple[str, str, int]] = set()
    for group in groups:
        remote = text(group.get("remote") or group.get("value"))
        for item in group.get("resources") or []:
            resource_type = canonical_resource_type(item.get("type"))
            if resource_type not in {"pve-qemu", "pve-lxc"}:
                continue
            if normalize_region_text(item.get("status")) in {"stopped", "stop", "已停止"}:
                continue
            try:
                vmid = int(item.get("vmid") or 0)
            except (TypeError, ValueError):
                vmid = 0
            key = (remote, resource_type, vmid)
            if vmid and key in seen:
                continue
            if vmid:
                seen.add(key)
            cpu += number_value(item.get("maxcpu"))
            mem += number_value(item.get("maxmem"))
            disk += number_value(item.get("maxdisk"))
    return {"cpu": cpu, "mem": mem, "disk": disk}


async def cloud_remote_groups() -> list[dict[str, Any]]:
    data = await pdm_nodes_list()
    remote_details = await pdm_remote_config_detail_map()
    remote_configs = {
        remote: str(detail.get("address") or "")
        for remote, detail in remote_details.items()
        if detail.get("address")
    }
    remote_addresses = await pdm_remote_address_map(data, remote_configs)
    remote_summaries = await pdm_remote_summary_map(data)
    groups = resource_groups(data, remote_addresses, remote_summaries, remote_details)
    resources_by_remote = {str(item.get("remote") or ""): item.get("resources") or [] for item in data}
    binding_map = await pve_node_binding_map([str(item.get("remote") or item.get("value") or "") for item in groups])
    for item in groups:
        remote = str(item.get("remote") or item.get("value") or "")
        item["resources"] = resources_by_remote.get(remote, [])
        item.update(binding_map.get(remote, {}))
    return groups


async def sync_product_cloud_vm_specs(product: ProductItem) -> dict[str, int]:
    if not await is_cloud_vm_product(product):
        return {"products": 0, "devices": 0, "configs": 0, "removed": 0}

    attributes = [
        attribute
        for attribute in await product_spec_attributes(product, DEFAULT_CLOUD_VM_CODES)
        if cloud_attribute_kind(attribute)
    ]
    if not attributes:
        return {"products": 1, "devices": 0, "configs": 0, "removed": 0}

    try:
        groups = await cloud_remote_groups()
    except Exception:
        return {"products": 1, "devices": 0, "configs": 0, "removed": 0}
    region_ids = {int(item["region_id"]) for item in groups if item.get("region_id")}
    regions = {item.id: item for item in await AssetRegion.filter(id__in=list(region_ids))} if region_ids else {}
    matched_groups: list[dict[str, Any]] = []
    for group in groups:
        try:
            region_id = int(group.get("region_id"))
        except (TypeError, ValueError):
            region_id = None
        if region_id and await product_matches_region(product, regions.get(region_id)):
            matched_groups.append(group)

    current_keys = set()
    config_count = 0
    if matched_groups:
        source_region_id = next((int(item.get("region_id")) for item in matched_groups if item.get("region_id")), None)
        source_key = cloud_source_key(product, source_region_id)
        current_keys.add(source_key)
        cpu_total = sum(float(item.get("cpu_total") or 0) for item in matched_groups)
        mem_total = sum(float(item.get("maxmem") or 0) for item in matched_groups)
        disk_total = sum(float(item.get("maxdisk") or 0) for item in matched_groups)
        allocated = cloud_allocated_resources(matched_groups)
        summary = {
            "pve_count": len(matched_groups),
            "cpu_total": cpu_total,
            "cpu_allocated": allocated["cpu"],
            "cpu_available": max(0, cpu_total - allocated["cpu"]),
            "mem_allocated_gb": bytes_to_gb(allocated["mem"]),
            "mem_available_gb": bytes_to_gb(mem_total - allocated["mem"]),
            "disk_allocated_gb": bytes_to_gb(allocated["disk"]),
            "disk_available_gb": bytes_to_gb(disk_total - allocated["disk"]),
        }
        values = {
            "cpu": format_number(summary["cpu_available"]),
            "memory": format_number(summary["mem_available_gb"]),
            "storage": f"{format_number(summary['disk_available_gb'])} G",
        }
        value_range = cloud_group_value_range(summary)
        for index, attribute in enumerate(attributes):
            kind = cloud_attribute_kind(attribute)
            value = values.get(kind, "")
            if not value:
                continue
            payload = {
                "order": index,
                "default_value": value[:255],
                "value_range": value_range,
                "required": bool(attribute.required),
                "source_id": source_region_id,
                "sync_hash": sync_hash({"code": attribute.code, "value": value, "source": source_key, "summary": summary}),
                "auto_sync": True,
            }
            await ProductSpecConfig.update_or_create(
                defaults=payload,
                product_id=product.id,
                attribute_id=attribute.id,
                source_type=CLOUD_VM_SOURCE,
                source_key=source_key,
            )
            config_count += 1

    stale_query = ProductSpecConfig.filter(product_id=product.id, source_type=CLOUD_VM_SOURCE, auto_sync=True)
    removed = await (stale_query.exclude(source_key__in=list(current_keys)).delete() if current_keys else stale_query.delete())
    return {"products": 1, "devices": len(matched_groups), "configs": config_count, "removed": int(removed or 0)}


async def sync_product_physical_server_specs(product: ProductItem) -> dict[str, int]:
    if not await is_physical_server_product(product):
        return {"products": 0, "devices": 0, "configs": 0, "removed": 0}

    attributes = await product_spec_attributes(product, DEFAULT_PHYSICAL_SERVER_CODES)
    if not attributes:
        return {"products": 1, "devices": 0, "configs": 0, "removed": 0}

    devices = await AssetDevice.filter(type=0).select_related("region", "location", "cabinet").order_by(
        "region__name", "location__name", "cabinet__name", "u_position", "name"
    )
    rows: list[dict] = []
    for device in devices:
        if not await product_matches_region(product, device.region):
            continue
        rows.extend([row for row in device_to_sales_rows(device) if is_free_device_status(row.get("status"))])

    current_keys = set()
    config_count = 0
    for row in rows:
        source_id, source_key = row_source(row)
        if not source_key:
            continue
        current_keys.add(source_key)
        for attribute in attributes:
            value = row_attribute_value(row, attribute)
            if not text(value):
                continue
            payload = {
                "order": 0,
                "default_value": text(value)[:255],
                "value_range": text(row.get("config"))[:500] or None,
                "required": bool(attribute.required),
                "source_id": source_id,
                "sync_hash": sync_hash({"code": attribute.code, "value": value, "source": source_key}),
                "auto_sync": True,
            }
            await ProductSpecConfig.update_or_create(
                defaults=payload,
                product_id=product.id,
                attribute_id=attribute.id,
                source_type=PHYSICAL_SERVER_SOURCE,
                source_key=source_key,
            )
            config_count += 1

    stale_query = ProductSpecConfig.filter(product_id=product.id, source_type=PHYSICAL_SERVER_SOURCE, auto_sync=True)
    removed = await (stale_query.exclude(source_key__in=list(current_keys)).delete() if current_keys else stale_query.delete())
    return {"products": 1, "devices": len(rows), "configs": config_count, "removed": int(removed or 0)}


async def sync_physical_server_specs(product_id: int | None = None, region_id: int | None = None) -> dict[str, int]:
    query = ProductItem.filter(status="active")
    if product_id:
        query = query.filter(id=product_id)
    products = await query.order_by("name")

    target_region = await AssetRegion.get_or_none(id=region_id) if region_id else None
    summary = {"products": 0, "devices": 0, "configs": 0, "removed": 0}
    for product in products:
        if target_region and not await product_matches_region(product, target_region):
            continue
        result = await sync_product_physical_server_specs(product)
        for key in summary:
            summary[key] += int(result.get(key) or 0)
    return summary


async def sync_cloud_vm_specs(product_id: int | None = None, region_id: int | None = None) -> dict[str, int]:
    query = ProductItem.filter(status="active")
    if product_id:
        query = query.filter(id=product_id)
    products = await query.order_by("name")

    target_region = await AssetRegion.get_or_none(id=region_id) if region_id else None
    summary = {"products": 0, "devices": 0, "configs": 0, "removed": 0}
    for product in products:
        if target_region and not await product_matches_region(product, target_region):
            continue
        result = await sync_product_cloud_vm_specs(product)
        for key in summary:
            summary[key] += int(result.get(key) or 0)
    return summary


async def sync_product_auto_specs(product_id: int | None = None, region_id: int | None = None) -> dict[str, Any]:
    physical = await sync_physical_server_specs(product_id=product_id, region_id=region_id)
    cloud = await sync_cloud_vm_specs(product_id=product_id, region_id=region_id)
    return {
        "products": int(physical.get("products") or 0) + int(cloud.get("products") or 0),
        "devices": int(physical.get("devices") or 0) + int(cloud.get("devices") or 0),
        "configs": int(physical.get("configs") or 0) + int(cloud.get("configs") or 0),
        "removed": int(physical.get("removed") or 0) + int(cloud.get("removed") or 0),
        "physical": physical,
        "cloud": cloud,
    }
