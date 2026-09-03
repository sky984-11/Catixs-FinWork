import asyncio
import json
import secrets
from datetime import date, datetime
from calendar import monthrange
from decimal import Decimal
from typing import Any, Literal
from uuid import uuid4

from fastapi import APIRouter, Query
from loguru import logger
from pydantic import BaseModel, Field
from tortoise.expressions import Q

from app.models.customer_center import CrmCustomer
from app.models.admin import User
from app.models.asset import AssetDevice, AssetRegion, CloudDhcpLease, PveNodeBinding, PveVmMetadata
from app.models.product_center import (
    ProductCategory,
    ProductItem,
    ProductPrice,
    ProductPriceHistory,
    ProductSpecAttribute,
    ProductSpecConfig,
    ProductTemplate,
)
from app.schemas.base import Fail, Success, SuccessExtra
from app.api.v1.pve.dhcp import allocate_dhcp_for_price, lease_dict_for_price, normalize_region_key, release_price_dhcp
from app.api.v1.pve.vm_create import (
    VMCreateRequest,
    VMNetworkConfig,
    create_vm as create_pve_vm,
    parse_storage_output,
    pdm_storage_options,
    resolve_create_host,
    run_remote_script,
)
from app.api.v1.pve.pve import (
    VMPowerRequest,
    all_vms,
    apply_vm_metadata,
    pdm_live_resources_list,
    submit_vm_power,
    sync_vm_spec_metadata_from_list,
)
from app.api.v1.resources.resources import aggregate_sales_device_status, device_to_sales_rows
from app.services.product_physical_server_sync import (
    CLOUD_VM_SOURCE,
    PHYSICAL_SERVER_SOURCE,
    cloud_remote_groups,
    product_matches_region,
    sync_physical_server_specs,
    sync_product_auto_specs,
)

router = APIRouter()

PRODUCT_STATUSES = [{"label": "在售", "value": "active"}, {"label": "下架", "value": "offline"}]
PRICE_TYPES = [{"label": "标准价格", "value": "standard"}, {"label": "客户价格", "value": "customer"}]
BILLING_MODES = [
    {"label": "固定费用", "value": "fixed"},
    {"label": "按小时计费", "value": "hourly"},
    {"label": "按数量计费", "value": "quantity"},
    {"label": "按用量计费", "value": "usage"},
    {"label": "按带宽计费", "value": "bandwidth"},
    {"label": "混合计费", "value": "hybrid"},
]
BILLING_UNITS = [
    {"label": "一次性", "value": "one_time"},
    {"label": "小时", "value": "hour"},
    {"label": "月", "value": "month"},
    {"label": "资源", "value": "resource"},
    {"label": "Mbps", "value": "mbps"},
    {"label": "Gbps", "value": "gbps"},
]
ATTRIBUTE_TYPES = [
    {"label": "文本", "value": "text"},
    {"label": "数字", "value": "number"},
    {"label": "单选", "value": "select"},
    {"label": "多选", "value": "multi_select"},
    {"label": "开关", "value": "switch"},
    {"label": "日期", "value": "date"},
    {"label": "资源引用", "value": "resource_ref"},
]
CURRENCIES = [{"label": item, "value": item} for item in ["USD", "EUR", "CNY", "JPY", "HKD"]]


class CategoryPayload(BaseModel):
    name: str = Field(..., max_length=120)
    code: str | None = Field(None, max_length=80)
    parent_id: int | None = None
    order: int = 0
    description: str | None = Field(None, max_length=500)
    status: bool = True


class ProductPayload(BaseModel):
    name: str = Field(..., max_length=160)
    code: str | None = Field(None, max_length=80)
    category_id: int | None = None
    status: str = "active"
    region: str | None = Field(None, max_length=100)
    billing_mode: str = "fixed"
    description: str | None = None


class AttributePayload(BaseModel):
    name: str = Field(..., max_length=120)
    code: str = Field(..., max_length=80)
    category_id: int | None = None
    category_ids: list[int] = Field(default_factory=list)
    attr_type: str = "text"
    unit: str | None = Field(None, max_length=40)
    required: bool = False
    options: str | None = None
    description: str | None = Field(None, max_length=500)
    status: bool = True


class SpecConfigItemPayload(BaseModel):
    attribute_id: int
    order: int = 0
    default_value: str | None = Field(None, max_length=255)
    value_range: str | None = Field(None, max_length=500)
    required: bool = False


class SpecConfigPayload(BaseModel):
    product_id: int
    attribute_id: int | None = None
    source_key: str | None = Field(None, max_length=160)
    config_ids: list[int] = Field(default_factory=list)
    order: int = 0
    default_value: str | None = Field(None, max_length=255)
    value_range: str | None = Field(None, max_length=500)
    required: bool = False
    configs: list[SpecConfigItemPayload] = Field(default_factory=list)


class PricePayload(BaseModel):
    product_id: int | None = None
    spec_config_key: str | None = Field(None, max_length=200)
    spec_config_name: str | None = Field(None, max_length=200)
    spec_values: dict[str, Any] | None = None
    os_type: str | None = Field(None, max_length=40)
    os_version: str | None = Field(None, max_length=40)
    dhcp_pool_id: int | None = None
    cloud_vm_remote: str | None = Field(None, max_length=100)
    cloud_vm_vmid: int | None = None
    cloud_vm_name: str | None = Field(None, max_length=160)
    physical_device_id: int | None = None
    physical_device_name: str | None = Field(None, max_length=160)
    physical_device_node: str | None = Field(None, max_length=100)
    vm_name: str | None = Field(None, max_length=160)
    vm_password: str | None = Field(None, min_length=8, max_length=128)
    inherited_from_price_id: int | None = None
    price_type: str = "standard"
    customer_id: int | None = None
    customer_name: str | None = Field(None, max_length=160)
    billing_mode: str = "fixed"
    billing_unit: str = "month"
    currency: str = Field("USD", max_length=12)
    amount: Decimal | float | int | str = 0
    min_amount: Decimal | float | int | str | None = None
    tier_rules: str | None = None
    bandwidth_rule: str | None = None
    effective_date: date | None = None
    expiry_date: date | None = None
    notify_enabled: bool = False
    notify_user_ids: list[int] = Field(default_factory=list)
    notify_schedule: Literal["once", "monthly"] = "once"
    notify_at: datetime | None = None
    status: str = "active"
    remark: str | None = None


class PriceNotificationPayload(BaseModel):
    notify_enabled: bool = False
    notify_user_ids: list[int] = Field(default_factory=list)
    notify_schedule: Literal["once", "monthly"] = "once"
    notify_at: datetime | None = None
    notify_day: int | None = Field(None, ge=1, le=31)
    notify_time: str | None = Field(None, pattern=r"^\d{2}:\d{2}(:\d{2})?$")


class TemplatePayload(BaseModel):
    name: str = Field(..., max_length=120)
    category_id: int | None = None
    template_type: str = "product"
    description: str | None = None
    config: str | None = None
    status: bool = True


def compact(values: dict[str, Any]) -> dict[str, Any]:
    return {key: (None if value == "" else value) for key, value in values.items()}


def label_of(options: list[dict[str, str]], value: str | None) -> str:
    return next((item["label"] for item in options if item["value"] == value), value or "-")


def effective_attr_type(code: str | None, attr_type: str | None) -> str:
    if code == "cpu":
        return "number"
    return attr_type or "text"


def normalize_category_ids(category_ids: list[int] | None, category_id: int | None = None) -> list[int]:
    values: list[int] = []
    for value in category_ids or []:
        try:
            item = int(value)
        except (TypeError, ValueError):
            continue
        if item > 0 and item not in values:
            values.append(item)
    if not values and category_id:
        values.append(int(category_id))
    return values


def attribute_category_ids(attribute: ProductSpecAttribute) -> list[int]:
    return normalize_category_ids(attribute.category_ids or [], attribute.category_id)


async def category_names(category_ids: list[int]) -> list[str]:
    if not category_ids:
        return []
    rows = await ProductCategory.filter(id__in=category_ids).values("id", "name")
    names_by_id = {int(item["id"]): item["name"] for item in rows}
    return [names_by_id[item] for item in category_ids if item in names_by_id]


async def category_sort_key(category_id: int | None) -> str:
    if not category_id:
        return "9999.9999.999999"
    nodes: list[ProductCategory] = []
    current_id = category_id
    while current_id:
        category = await ProductCategory.get_or_none(id=current_id)
        if not category:
            break
        nodes.insert(0, category)
        current_id = category.parent_id
    if not nodes:
        return "9999.9999.999999"
    parts = [f"{int(item.order or 0):04d}.{int(item.id):06d}" for item in nodes]
    return ".".join(parts)


async def product_sort_key(product: ProductItem) -> tuple[str, str, str]:
    return (
        await category_sort_key(product.category_id),
        str(product.name or "").casefold(),
        str(product.id or ""),
    )


async def product_category_names(product: ProductItem) -> list[str]:
    names: list[str] = []
    current_id = product.category_id
    while current_id:
        category = await ProductCategory.get_or_none(id=current_id)
        if not category:
            break
        names.insert(0, category.name or "")
        current_id = category.parent_id
    return names


async def product_is_category(product: ProductItem, names: set[str]) -> bool:
    return any(name in names for name in await product_category_names(product))


async def product_uses_resource_source(product: ProductItem, category_names: set[str], source_type: str) -> bool:
    return await product_is_category(product, category_names) or await ProductSpecConfig.filter(
        product_id=product.id, source_type=source_type
    ).exists()


async def product_snapshot(product_id: int) -> dict[str, str]:
    product = await ProductItem.get_or_none(id=product_id)
    if not product:
        return {
            "product_display_name": "",
            "product_category_name": "",
            "product_category_sort": "9999.9999.999999",
            "product_region_name": "",
        }
    category = await product.category if product.category_id else None
    return {
        "product_display_name": product.name or "",
        "product_category_name": category.name if category else "",
        "product_category_sort": await category_sort_key(product.category_id),
        "product_region_name": product.region or "",
    }


async def refresh_product_spec_config_snapshots(product_id: int) -> dict[str, str]:
    snapshot = await product_snapshot(product_id)
    await ProductSpecConfig.filter(product_id=product_id).update(**snapshot)
    return snapshot


def prepare_attribute_payload(payload: AttributePayload) -> dict[str, Any]:
    data = compact(payload.model_dump())
    ids = normalize_category_ids(data.pop("category_ids", None), data.get("category_id"))
    data["category_ids"] = ids
    data["category_id"] = ids[0] if ids else None
    return data


def validate_product_payload(data: dict[str, Any]) -> str | None:
    if not data.get("category_id"):
        return "请选择产品分类"
    if not str(data.get("region") or "").strip():
        return "请选择地区"
    return None


def delete_block_msg(target: str, refs: list[str]) -> str:
    return f"{target}存在关联数据，不能直接删除。请先删除：{'、'.join(refs)}。"


async def next_code(model, prefix: str, field: str = "code") -> str:
    latest = await model.filter(**{f"{field}__startswith": prefix}).order_by(f"-{field}").first()
    current = getattr(latest, field, None) if latest else None
    if not current:
        return f"{prefix}001"
    try:
        sequence = int(str(current).replace(prefix, "", 1)) + 1
    except ValueError:
        sequence = 1
    return f"{prefix}{sequence:03d}"


async def seed_categories():
    if await ProductCategory.exists():
        return
    tree = {
        "机房资源": ["整柜整租", "散柜机位", "Cross Connect"],
        "计算资源": ["物理服务器", "云主机"],
        "互联网资源": ["IPv4", "IPv6", "ASN"],
        "上云互联": ["IX", "Peering", "Cloud Connect"],
        "网络传输": ["IP Transit", "DIA", "China Route 回国带宽", "IEPL", "Wave"],
        "增值服务": ["Remote Hands"],
    }
    order = 1
    for parent_name, children in tree.items():
        parent = await ProductCategory.create(name=parent_name, code=f"CAT{order:03d}", level=1, order=order)
        for child_order, child_name in enumerate(children, start=1):
            await ProductCategory.create(
                name=child_name,
                code=f"CAT{order:03d}{child_order:02d}",
                parent_id=parent.id,
                level=2,
                order=child_order,
            )
        order += 1


PRODUCT_SPEC_ATTRIBUTE_SEEDS = [
    {
        "name": "地区",
        "code": "region",
        "attr_type": "select",
        "required": True,
        "options": "中国大陆\n香港\n新加坡\n日本\n美国\n欧洲\n其他",
        "description": "产品交付或计费所在地区。",
    },
    {
        "name": "A端接入类型",
        "code": "a_end_access_type",
        "attr_type": "select",
        "required": True,
        "options": "On-net\nOff-net",
        "description": "网络传输类产品的A端是否为本网覆盖。",
    },
    {
        "name": "A端位置",
        "code": "a_end_location",
        "attr_type": "text",
        "required": True,
        "description": "A端机房、楼宇或客户侧地址。",
    },
    {
        "name": "Z端位置",
        "code": "z_end_location",
        "attr_type": "text",
        "required": False,
        "description": "IEPL、Wave、Cloud Connect等点到点产品的Z端位置。",
    },
    {
        "name": "本地传输",
        "code": "local_loop_required",
        "attr_type": "switch",
        "required": False,
        "description": "Off-net场景是否需要附加本地传输。",
    },
    {
        "name": "是否为机房",
        "code": "is_datacenter",
        "attr_type": "switch",
        "required": False,
        "description": "DIA场景用于区分Datacenter和Retail Building。",
    },
    {
        "name": "接入场景",
        "code": "access_scenario",
        "attr_type": "select",
        "required": False,
        "options": "Datacenter\nRetail Building",
        "description": "DIA接入场景，Retail Building通常需要询价。",
    },
    {
        "name": "需询价",
        "code": "need_quote",
        "attr_type": "switch",
        "required": False,
        "description": "是否需要销售或采购手动询价后再确认价格。",
    },
    {
        "name": "自定义价格",
        "code": "custom_price_required",
        "attr_type": "switch",
        "required": False,
        "description": "不适用标准价格时启用客户或项目级自定义价格。",
    },
    {
        "name": "是否突发",
        "code": "burst_required",
        "attr_type": "switch",
        "required": False,
        "description": "IEPL、带宽等产品是否支持Burst。",
    },
    {
        "name": "带宽",
        "code": "bandwidth",
        "attr_type": "number",
        "unit": "Mbps",
        "required": False,
        "description": "固定带宽或产品带宽规格。",
    },
    {
        "name": "Commit",
        "code": "commit_bandwidth",
        "attr_type": "number",
        "unit": "Mbps",
        "required": False,
        "description": "95计费或突发带宽的承诺带宽。",
    },
    {
        "name": "Burst",
        "code": "burst_bandwidth",
        "attr_type": "number",
        "unit": "Mbps",
        "required": False,
        "description": "允许突发的最大带宽。",
    },
    {
        "name": "计费方式",
        "code": "billing_mode",
        "attr_type": "select",
        "required": False,
        "options": "固定费用\n按小时计费\n按数量计费\n按用量计费\n按带宽计费\n混合计费",
        "description": "产品默认计费方式。",
    },
    {
        "name": "计费周期",
        "code": "billing_cycle",
        "attr_type": "select",
        "required": False,
        "options": "一次性\n月付\n季付\n半年付\n年付",
        "description": "产品或套餐默认计费周期。",
    },
    {
        "name": "机柜规格",
        "code": "rack_size",
        "attr_type": "select",
        "required": False,
        "options": "整柜\n半柜\n1/4柜\n单U",
        "description": "机房资源类产品的机柜形态。",
    },
    {
        "name": "机位数量",
        "code": "rack_units",
        "attr_type": "number",
        "unit": "U",
        "required": False,
        "description": "散柜机位或服务器托管占用U数。",
    },
    {
        "name": "电力容量",
        "code": "power_capacity",
        "attr_type": "number",
        "unit": "kW",
        "required": False,
        "description": "机柜或机位可用电力容量。",
    },
    {
        "name": "电源类型",
        "code": "power_type",
        "attr_type": "select",
        "required": False,
        "options": "AC\nDC\n双路AC\n双路DC",
        "description": "机柜、机位或设备供电类型。",
    },
    {
        "name": "Cross Connect介质",
        "code": "cross_connect_media",
        "attr_type": "select",
        "required": False,
        "options": "Fiber\nCopper",
        "description": "Cross Connect使用的传输介质。",
    },
    {
        "name": "接口类型",
        "code": "interface_type",
        "attr_type": "select",
        "required": False,
        "options": "RJ45\nLC\nSC\nSFP\nSFP+\nQSFP+\nQSFP28",
        "description": "端口或交叉连接接口类型。",
    },
    {
        "name": "端口速率",
        "code": "port_speed",
        "attr_type": "select",
        "required": False,
        "options": "1G\n10G\n25G\n40G\n100G\n400G",
        "description": "端口或互联服务速率。",
    },
    {
        "name": "物理服务器型号",
        "code": "server_model",
        "attr_type": "text",
        "required": False,
        "description": "物理服务器品牌与型号。",
    },
    {
        "name": "CPU",
        "code": "cpu",
        "attr_type": "number",
        "unit": "核",
        "required": False,
        "description": "物理服务器CPU配置或云主机vCPU数量。",
    },
    {
        "name": "内存",
        "code": "memory",
        "attr_type": "number",
        "unit": "GB",
        "required": False,
        "description": "服务器或云主机内存容量。",
    },
    {
        "name": "存储",
        "code": "storage",
        "attr_type": "number",
        "unit": "GB",
        "required": False,
        "description": "服务器或云主机存储容量。",
    },
    {
        "name": "IP版本",
        "code": "ip_version",
        "attr_type": "select",
        "required": False,
        "options": "IPv4\nIPv6",
        "description": "互联网地址资源版本。",
    },
    {
        "name": "IP数量",
        "code": "ip_quantity",
        "attr_type": "number",
        "required": False,
        "description": "IPv4/IPv6地址数量。",
    },
    {
        "name": "IP前缀",
        "code": "ip_prefix",
        "attr_type": "text",
        "required": False,
        "description": "IPv4或IPv6前缀，例如/24、/48。",
    },
    {
        "name": "ASN",
        "code": "asn",
        "attr_type": "text",
        "required": False,
        "description": "自治系统号。",
    },
    {
        "name": "互联类型",
        "code": "interconnect_type",
        "attr_type": "select",
        "required": False,
        "options": "IX\nPeering\nCloud Connect",
        "description": "上云互联或互联网互联类型。",
    },
    {
        "name": "云服务商",
        "code": "cloud_provider",
        "attr_type": "select",
        "required": False,
        "options": "AWS\nAzure\nGoogle Cloud\nAlibaba Cloud\nTencent Cloud\nHuawei Cloud\nOther",
        "description": "Cloud Connect目标云服务商。",
    },
    {
        "name": "路由类型",
        "code": "route_type",
        "attr_type": "select",
        "required": False,
        "options": "BGP\nStatic\nDefault Route",
        "description": "网络产品路由交付方式。",
    },
    {
        "name": "线路保护",
        "code": "protection_type",
        "attr_type": "select",
        "required": False,
        "options": "无保护\n主备\n双路由\n环网保护",
        "description": "IEPL、Wave等专线产品保护方式。",
    },
    {
        "name": "Remote Hands工时",
        "code": "remote_hands_hours",
        "attr_type": "number",
        "unit": "小时",
        "required": False,
        "description": "Remote Hands服务预估或购买工时。",
    },
    {
        "name": "服务级别",
        "code": "service_level",
        "attr_type": "select",
        "required": False,
        "options": "标准\n加急\n7x24\n定制",
        "description": "增值服务或交付服务级别。",
    },
]

ATTRIBUTE_CATEGORY_CODE_MAP = {
    "cross_connect_media": "CAT00103",
    "server_model": "CAT00201",
    "asn": "CAT00303",
    "cloud_provider": "CAT00403",
    "remote_hands_hours": "CAT00601",
    "service_level": "CAT00601",
}

ATTRIBUTE_CATEGORY_CODES_MAP = {
    "region": [
        "CAT00101", "CAT00102", "CAT00103",
        "CAT00201", "CAT00202",
        "CAT00301", "CAT00302", "CAT00303",
        "CAT00401", "CAT00402", "CAT00403",
        "CAT00501", "CAT00502", "CAT00503", "CAT00504", "CAT00505",
        "CAT00601",
    ],
    "billing_mode": [
        "CAT00101", "CAT00102", "CAT00103",
        "CAT00201", "CAT00202",
        "CAT00301", "CAT00302", "CAT00303",
        "CAT00401", "CAT00402", "CAT00403",
        "CAT00501", "CAT00502", "CAT00503", "CAT00504", "CAT00505",
        "CAT00601",
    ],
    "billing_cycle": [
        "CAT00101", "CAT00102", "CAT00103",
        "CAT00201", "CAT00202",
        "CAT00301", "CAT00302", "CAT00303",
        "CAT00401", "CAT00402", "CAT00403",
        "CAT00501", "CAT00502", "CAT00503", "CAT00504", "CAT00505",
        "CAT00601",
    ],
    "rack_size": ["CAT00101"],
    "rack_units": ["CAT00102"],
    "power_capacity": ["CAT00101", "CAT00102"],
    "power_type": ["CAT00101", "CAT00102"],
    "cpu": ["CAT00201", "CAT00202"],
    "memory": ["CAT00201", "CAT00202"],
    "storage": ["CAT00201", "CAT00202"],
    "ip_version": ["CAT00301", "CAT00302"],
    "ip_quantity": ["CAT00301", "CAT00302"],
    "ip_prefix": ["CAT00301", "CAT00302"],
    "interconnect_type": ["CAT00401", "CAT00402", "CAT00403"],
    "bandwidth": ["CAT00401", "CAT00402", "CAT00403", "CAT00501", "CAT00502", "CAT00503", "CAT00504", "CAT00505"],
    "interface_type": ["CAT00103", "CAT00401", "CAT00402", "CAT00403", "CAT00501", "CAT00502", "CAT00503", "CAT00504", "CAT00505"],
    "port_speed": ["CAT00103", "CAT00401", "CAT00402", "CAT00403", "CAT00501", "CAT00502", "CAT00503", "CAT00504", "CAT00505"],
    "a_end_access_type": ["CAT00501", "CAT00502", "CAT00503"],
    "a_end_location": ["CAT00501", "CAT00502", "CAT00503", "CAT00504", "CAT00505"],
    "z_end_location": ["CAT00403", "CAT00504", "CAT00505"],
    "local_loop_required": ["CAT00501", "CAT00502", "CAT00503"],
    "is_datacenter": ["CAT00502"],
    "access_scenario": ["CAT00502"],
    "need_quote": ["CAT00502"],
    "custom_price_required": ["CAT00502"],
    "burst_required": ["CAT00504"],
    "commit_bandwidth": ["CAT00501", "CAT00502", "CAT00503", "CAT00504"],
    "burst_bandwidth": ["CAT00501", "CAT00502", "CAT00503", "CAT00504"],
    "route_type": ["CAT00501", "CAT00502", "CAT00503"],
    "protection_type": ["CAT00504", "CAT00505"],
}


async def seed_spec_attributes():
    if await ProductSpecAttribute.exists():
        return
    category_codes = set(ATTRIBUTE_CATEGORY_CODE_MAP.values())
    for codes in ATTRIBUTE_CATEGORY_CODES_MAP.values():
        category_codes.update(codes)
    category_ids = dict(await ProductCategory.filter(code__in=category_codes).values_list("code", "id"))
    for item in PRODUCT_SPEC_ATTRIBUTE_SEEDS:
        values = {**item, "status": True}
        category_codes = ATTRIBUTE_CATEGORY_CODES_MAP.get(item["code"])
        if not category_codes:
            category_code = ATTRIBUTE_CATEGORY_CODE_MAP.get(item["code"])
            category_codes = [category_code] if category_code else []
        ids = [category_ids[code] for code in category_codes if code in category_ids]
        if ids:
            values["category_id"] = ids[0]
            values["category_ids"] = ids
        await ProductSpecAttribute.update_or_create(defaults=values, code=item["code"])


async def category_dict(category: ProductCategory) -> dict[str, Any]:
    data = await category.to_dict()
    data["parent_name"] = ""
    if category.parent_id:
        parent = await category.parent
        data["parent_name"] = parent.name if parent else ""
    return data


async def product_dict(product: ProductItem) -> dict[str, Any]:
    data = await product.to_dict()
    category = await product.category if product.category_id else None
    data["category_name"] = category.name if category else ""
    data["status_label"] = label_of(PRODUCT_STATUSES, data.get("status"))
    data["billing_mode_label"] = label_of(BILLING_MODES, data.get("billing_mode"))
    return data


async def attribute_dict(attribute: ProductSpecAttribute) -> dict[str, Any]:
    data = await attribute.to_dict()
    data["attr_type"] = effective_attr_type(data.get("code"), data.get("attr_type"))
    ids = attribute_category_ids(attribute)
    names = await category_names(ids)
    data["category_ids"] = ids
    data["category_names"] = names
    data["category_id"] = ids[0] if ids else None
    data["category_name"] = "、".join(names) if names else "-"
    data["attr_type_label"] = label_of(ATTRIBUTE_TYPES, data.get("attr_type"))
    return data


async def spec_config_dict(config: ProductSpecConfig) -> dict[str, Any]:
    data = await config.to_dict()
    attribute = await config.attribute
    data["product_id"] = config.product_id
    data["attribute_id"] = config.attribute_id
    if not data.get("product_display_name") or not data.get("product_category_sort"):
        snapshot = await product_snapshot(config.product_id)
        for key, value in snapshot.items():
            data[key] = data.get(key) or value
    data["product_name"] = data.get("product_display_name") or ""
    data["product_category_name"] = data.get("product_category_name") or ""
    data["product_category_sort"] = data.get("product_category_sort") or "9999.9999.999999"
    data["product_region"] = data.get("product_region_name") or ""
    data["attribute_name"] = attribute.name
    data["attribute_code"] = attribute.code
    data["attr_type_label"] = label_of(ATTRIBUTE_TYPES, attribute.attr_type)
    data["unit"] = attribute.unit
    source_labels = {
        PHYSICAL_SERVER_SOURCE: "机柜资源",
        CLOUD_VM_SOURCE: "云资源",
    }
    data["source_label"] = source_labels.get(data.get("source_type"), "手动维护")
    return data


def spec_config_group_key(item: dict[str, Any]) -> str:
    source_type = item.get("source_type") or ("manual" if not item.get("auto_sync") else "auto")
    source_key = item.get("source_key") or item.get("source_id")
    if source_key:
        return f'{item.get("product_id")}:{source_type}:{source_key}'
    if item.get("auto_sync"):
        return f'{item.get("product_id")}:{source_type}:{item.get("id")}'
    return f'{item.get("product_id")}:manual:ungrouped'


def spec_config_attr_value(item: dict[str, Any]) -> str:
    value = item.get("default_value")
    if value is None or value == "":
        value = item.get("value_range")
    return str(value or "").strip()


def physical_server_node_position(source_key: str | None) -> str:
    marker = ":node:"
    if not source_key or marker not in source_key:
        return ""
    return source_key.split(marker, 1)[1].strip()


REGION_DISPLAY_ALIASES = {
    "tokyo": "东京",
    "japan / tokyo": "东京",
    "frankfurt": "法兰克福",
    "frankfurt am main": "法兰克福",
    "london": "伦敦",
    "hong kong": "香港",
    "shenzhen": "深圳",
    "taiwan": "台湾",
    "philippines": "菲律宾",
}


def region_display_name(value: str | None) -> str:
    text = str(value or "").strip()
    normalized = text.casefold().replace("\\", "/")
    normalized = " / ".join(item.strip() for item in normalized.split("/") if item.strip())
    return REGION_DISPLAY_ALIASES.get(normalized) or REGION_DISPLAY_ALIASES.get(normalized.replace(" ", "")) or text


def region_leaf_name(value: str | None) -> str:
    parts = [item.strip() for item in str(value or "").replace("\\", "/").split("/") if item.strip()]
    return region_display_name(parts[-1] if parts else str(value or "").strip())


async def cloud_spec_region_name(item: dict[str, Any]) -> str:
    source_id = item.get("source_id")
    region = await AssetRegion.get_or_none(id=source_id) if source_id else None
    if region:
        return region_display_name(region.city or region.name or region.code)
    return region_leaf_name(item.get("product_region") or item.get("source_key"))


async def spec_config_group_name(items: list[dict[str, Any]]) -> str:
    first = items[0]
    if first.get("source_type") == PHYSICAL_SERVER_SOURCE and first.get("source_id"):
        device = await AssetDevice.get_or_none(id=first.get("source_id"))
        device_name = str(device.name or "").strip() if device else ""
        if device_name:
            position = physical_server_node_position(first.get("source_key"))
            return f"{device_name} {position}".strip() if position else device_name
    if first.get("source_type") == CLOUD_VM_SOURCE:
        region_name = await cloud_spec_region_name(first)
        return f"{region_name} 云资源汇总".strip() if region_name else "云资源汇总"

    values = {item.get("attribute_code"): spec_config_attr_value(item) for item in items}
    parts = []
    for code in ("cpu_model", "cpu_num", "cpu_core", "mem_total", "disk_total"):
        if values.get(code):
            parts.append(values[code])
    if parts:
        return " / ".join(parts)
    source_key = str(first.get("source_key") or first.get("source_id") or "").strip()
    if source_key:
        return source_key
    return f'{first.get("product_name") or ""} 规格'


def spec_config_group_summary(items: list[dict[str, Any]]) -> str:
    chunks = []
    for item in sorted(items, key=lambda row: (row.get("order") or 0, row.get("id") or 0)):
        value = spec_config_attr_value(item)
        unit = item.get("unit") or ""
        if value and unit and not value.endswith(str(unit)):
            value = f"{value} {unit}"
        chunks.append(f'{item.get("attribute_name") or item.get("attribute_code")}：{value or "-"}')
    return " / ".join(chunks)


async def spec_config_group_dict(items: list[dict[str, Any]]) -> dict[str, Any]:
    first = items[0]
    sorted_items = sorted(items, key=lambda row: (row.get("order") or 0, row.get("id") or 0))
    attrs = [
        {
            "id": item.get("id"),
            "attribute_id": item.get("attribute_id"),
            "name": item.get("attribute_name"),
            "code": item.get("attribute_code"),
            "type": item.get("attr_type_label"),
            "default_value": item.get("default_value"),
            "value_range": item.get("value_range"),
            "value": spec_config_attr_value(item),
            "unit": item.get("unit") or "",
            "order": item.get("order") or 0,
            "required": bool(item.get("required")),
        }
        for item in sorted_items
    ]
    group_key = spec_config_group_key(first)
    return {
        "id": group_key,
        "is_group": True,
        "product_id": first.get("product_id"),
        "product_name": first.get("product_name"),
        "product_category_name": first.get("product_category_name"),
        "product_category_sort": first.get("product_category_sort"),
        "spec_name": await spec_config_group_name(sorted_items),
        "attribute_summary": spec_config_group_summary(sorted_items),
        "attributes": attrs,
        "source_type": first.get("source_type"),
        "source_id": first.get("source_id"),
        "source_key": first.get("source_key"),
        "source_label": first.get("source_label"),
        "auto_sync": any(item.get("auto_sync") for item in sorted_items),
        "config_ids": [item.get("id") for item in sorted_items],
    }


async def spec_config_groups(product_id: int | None = None) -> list[dict[str, Any]]:
    active_product_ids = await ProductItem.filter(status="active").values_list("id", flat=True)
    q = Q(product_id__in=active_product_ids)
    if product_id:
        q &= Q(product_id=product_id)
    rows = await ProductSpecConfig.filter(q).select_related("attribute").order_by(
        "product_category_sort",
        "product_display_name",
        "source_type",
        "source_key",
        "order",
        "id",
    )
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        item = await spec_config_dict(row)
        grouped.setdefault(spec_config_group_key(item), []).append(item)
    group_rows = [await spec_config_group_dict(items) for items in grouped.values()]
    group_rows.sort(
        key=lambda item: (
            str(item.get("product_category_sort") or "").casefold(),
            str(item.get("product_name") or "").casefold(),
            str(item.get("spec_name") or "").casefold(),
            str(item.get("id") or ""),
        )
    )
    return group_rows


async def get_spec_config_group(group_key: str | None) -> dict[str, Any] | None:
    if not group_key:
        return None
    for group in await spec_config_groups():
        if str(group.get("id")) == str(group_key):
            return group
    return None


def clean_spec_value(value: Any) -> str:
    text = str(value or "").strip()
    if text.endswith(".0"):
        text = text[:-2]
    return text


async def get_product_spec_attribute(product: ProductItem, code: str) -> ProductSpecAttribute | None:
    category_ids = []
    current_id = product.category_id
    while current_id:
        category_ids.insert(0, current_id)
        category = await ProductCategory.get_or_none(id=current_id)
        current_id = category.parent_id if category else None
    attrs = await ProductSpecAttribute.filter(code=code, status=True).all()
    for attr in attrs:
        ids = normalize_category_ids(attr.category_ids or [], attr.category_id)
        if not ids or any(item in ids for item in category_ids):
            return attr
    return attrs[0] if attrs else None


async def ensure_cloud_price_spec_group(product: ProductItem, values: dict[str, Any] | None) -> dict[str, Any] | None:
    spec_values = {
        "cpu_core": clean_spec_value((values or {}).get("cpu_core")),
        "mem_total": clean_spec_value((values or {}).get("mem_total")),
        "disk_total": clean_spec_value((values or {}).get("disk_total")),
    }
    if not all(spec_values.values()):
        return None
    source_key = f'price-cloud:{product.id}:{spec_values["cpu_core"]}c:{spec_values["mem_total"]}g:{spec_values["disk_total"]}g'
    attrs = []
    for index, code in enumerate(("cpu_core", "mem_total", "disk_total")):
        attr = await get_product_spec_attribute(product, code)
        if not attr:
            return None
        attrs.append((index, code, attr))
    snapshot = await product_snapshot(product.id)
    created_or_updated: list[ProductSpecConfig] = []
    for index, code, attr in attrs:
        config, _ = await ProductSpecConfig.update_or_create(
            product_id=product.id,
            attribute_id=attr.id,
            source_key=source_key,
            defaults={
                "order": index,
                "default_value": spec_values[code],
                "value_range": "",
                "required": True,
                "source_type": "price_cloud_custom",
                "source_id": None,
                "auto_sync": False,
                **snapshot,
            },
        )
        created_or_updated.append(config)
    return await spec_config_group_dict([await spec_config_dict(item) for item in created_or_updated])


async def price_dict(price: ProductPrice, *, resolve_spec_group: bool = True, include_dhcp_lease: bool = True) -> dict[str, Any]:
    data = await price.to_dict()
    product = await price.product
    data["product_name"] = product.name
    data["spec_config_key"] = data.get("spec_config_key") or ""
    data["spec_config_name"] = data.get("spec_config_name") or ""
    data["spec_config_display"] = data["spec_config_name"] or "-"
    if price.cloud_vm_remote and price.cloud_vm_vmid:
        vm = await PveVmMetadata.get_or_none(remote=price.cloud_vm_remote, vmid=price.cloud_vm_vmid)
        if vm:
            specs = []
            if vm.cpu_cores is not None:
                specs.append(f"CPU {vm.cpu_cores} 核")
            if vm.memory_gb is not None:
                specs.append(f"内存 {vm.memory_gb:g} GB")
            if vm.disk_gb is not None:
                specs.append(f"磁盘 {vm.disk_gb:g} GB")
            data["spec_config_display"] = " / ".join(specs) or data["spec_config_display"]
    elif price.physical_device_id:
        device = await AssetDevice.get_or_none(id=price.physical_device_id).select_related("region", "location", "cabinet")
        if device:
            node_name = str(price.physical_device_node or "")
            resource_row = next(
                (row for row in device_to_sales_rows(device) if str(row.get("node_name") or "") == node_name),
                None,
            )
            if resource_row:
                data["spec_config_display"] = resource_row.get("config") or data["spec_config_display"]
    cloud_spec_parts = data["spec_config_key"].split(":")
    if len(cloud_spec_parts) == 4 and cloud_spec_parts[0] == "cloud-price":
        data["spec_config_display"] = f"CPU {cloud_spec_parts[1]} 核 / 内存 {cloud_spec_parts[2]} GB / 磁盘 {cloud_spec_parts[3]} GB"
    elif resolve_spec_group and (group := await get_spec_config_group(data["spec_config_key"])):
        data["spec_config_display"] = group.get("attribute_summary") or data["spec_config_display"]
    data["price_type_label"] = label_of(PRICE_TYPES, data.get("price_type"))
    data["billing_mode_label"] = label_of(BILLING_MODES, data.get("billing_mode"))
    data["billing_unit_label"] = label_of(BILLING_UNITS, data.get("billing_unit"))
    data["amount"] = float(data.get("amount") or 0)
    data["min_amount"] = float(data.get("min_amount") or 0) if data.get("min_amount") is not None else None
    if include_dhcp_lease:
        data["dhcp_lease"] = await lease_dict_for_price(price.id)
    return data


async def template_dict(template: ProductTemplate) -> dict[str, Any]:
    data = await template.to_dict()
    category = await template.category if template.category_id else None
    data["category_name"] = category.name if category else ""
    return data


@router.get("/options", summary="产品中心选项")
async def options():
    await seed_categories()
    await seed_spec_attributes()
    categories = await ProductCategory.filter(status=True).order_by("level", "order", "name")
    products = await ProductItem.filter(status="active").all()
    product_sort_keys = {item.id: await product_sort_key(item) for item in products}
    product_category_map = {item.id: await product_category_names(item) for item in products}
    products.sort(key=lambda item: product_sort_keys.get(item.id, ("", "", "")))
    attributes = await ProductSpecAttribute.filter(status=True).order_by("category_id", "name").values("id", "name", "code", "attr_type", "unit", "options", "category_id", "category_ids")
    customers = await CrmCustomer.filter(status=True).exclude(lifecycle="terminated").order_by("name").values("id", "name", "legal_name")
    notify_users = await User.filter(is_active=True).order_by("username").values("id", "username", "alias")
    return Success(
        data={
            "categories": [{"label": item.name, "value": item.id, "parent_id": item.parent_id} for item in categories],
            "category_tree": await category_tree(),
            "products": [
                {
                    "label": item.name,
                    "value": item.id,
                    "code": item.code,
                    "billing_mode": item.billing_mode,
                    "region": item.region,
                    "category_id": item.category_id,
                    "category_path": product_category_map.get(item.id, []),
                    "category_name": (product_category_map.get(item.id, []) or [""])[-1],
                }
                for item in products
            ],
            "spec_configs": [
                {
                    "label": f'{item.get("product_name") or "-"} / {item.get("spec_name") or "-"}',
                    "value": item.get("id"),
                    "product_id": item.get("product_id"),
                    "product_name": item.get("product_name"),
                    "spec_name": item.get("spec_name"),
                    "source_type": item.get("source_type"),
                    "attributes": item.get("attributes") or [],
                    "product_category_name": item.get("product_category_name"),
                    "billing_mode": next(
                        (product.billing_mode for product in products if product.id == item.get("product_id")),
                        "fixed",
                    ),
                }
                for item in await spec_config_groups()
            ],
            "attributes": [
                {
                    "label": f'{item["name"]} ({item["code"]})',
                    "value": item["id"],
                    "code": item["code"],
                    "attr_type": effective_attr_type(item["code"], item["attr_type"]),
                    "unit": item["unit"],
                    "options": item["options"],
                    "category_id": item["category_id"],
                    "category_ids": normalize_category_ids(item.get("category_ids") or [], item.get("category_id")),
                }
                for item in attributes
            ],
            "customers": [{"label": item["legal_name"] or item["name"], "value": item["id"]} for item in customers],
            "notify_users": [{"label": item["alias"] or item["username"], "value": item["id"]} for item in notify_users],
            "product_statuses": PRODUCT_STATUSES,
            "price_types": PRICE_TYPES,
            "billing_modes": BILLING_MODES,
            "billing_units": BILLING_UNITS,
            "attribute_types": ATTRIBUTE_TYPES,
            "currencies": CURRENCIES,
        }
    )


async def category_tree():
    rows = await ProductCategory.filter(status=True).order_by("level", "order", "name")
    by_parent: dict[int, list[ProductCategory]] = {}
    for row in rows:
        by_parent.setdefault(int(row.parent_id or 0), []).append(row)

    def build(parent_id: int = 0):
        nodes = []
        for item in by_parent.get(parent_id, []):
            children = build(item.id)
            node = {"label": item.name, "key": item.id, "value": item.id}
            if children:
                node["children"] = children
            nodes.append(node)
        return nodes

    return build()


@router.get("/categories", summary="产品分类列表")
async def list_categories():
    await seed_categories()
    rows = await ProductCategory.all().order_by("level", "order", "name")
    return Success(data=[await category_dict(item) for item in rows])


@router.post("/categories", summary="新增产品分类")
async def create_category(payload: CategoryPayload):
    data = compact(payload.model_dump())
    if not data.get("code"):
        data["code"] = await next_code(ProductCategory, "CAT")
    parent_id = data.get("parent_id")
    data["level"] = 2 if parent_id else 1
    category = await ProductCategory.create(**data)
    return Success(msg="产品分类已创建", data=await category_dict(category))


@router.put("/categories/{category_id}", summary="编辑产品分类")
async def update_category(category_id: int, payload: CategoryPayload):
    data = compact(payload.model_dump(exclude_unset=True))
    if "parent_id" in data:
        data["level"] = 2 if data.get("parent_id") else 1
    await ProductCategory.filter(id=category_id).update(**data)
    return Success(msg="产品分类已更新", data=await category_dict(await ProductCategory.get(id=category_id)))


@router.delete("/categories/{category_id}", summary="删除产品分类")
async def delete_category(category_id: int):
    refs = []
    child_count = await ProductCategory.filter(parent_id=category_id).count()
    product_count = await ProductItem.filter(category_id=category_id).count()
    template_count = await ProductTemplate.filter(category_id=category_id).count()
    if child_count:
        refs.append(f"产品目录树下级分类 {child_count} 个")
    if product_count:
        refs.append(f"产品管理中的产品 {product_count} 个")
    if template_count:
        refs.append(f"产品模板 {template_count} 个")
    if refs:
        return Fail(msg=delete_block_msg("产品分类", refs))
    await delete_category_spec_attributes(category_id)
    await ProductCategory.filter(id=category_id).delete()
    return Success(msg="产品分类已删除")


async def delete_category_spec_attributes(category_id: int) -> None:
    attributes = await ProductSpecAttribute.all()
    for attribute in attributes:
        ids = attribute_category_ids(attribute)
        if int(category_id) not in ids:
            continue
        remaining_ids = [item for item in ids if item != int(category_id)]
        if remaining_ids:
            await ProductSpecAttribute.filter(id=attribute.id).update(
                category_ids=remaining_ids,
                category_id=remaining_ids[0],
            )
        else:
            await ProductSpecAttribute.filter(id=attribute.id).delete()


@router.get("/products", summary="产品列表")
async def list_products(
    page: int = Query(1),
    page_size: int = Query(20),
    keyword: str = Query(""),
    category_id: int | None = Query(None),
    status: str = Query(""),
    region: str = Query(""),
):
    q = Q()
    if keyword:
        q &= Q(name__contains=keyword) | Q(code__contains=keyword) | Q(region__contains=keyword)
    if category_id:
        q &= Q(category_id=category_id)
    if status:
        q &= Q(status=status)
    if region:
        q &= Q(region=region)
    all_rows = await ProductItem.filter(q).all()
    sort_keys = {item.id: await product_sort_key(item) for item in all_rows}
    all_rows.sort(key=lambda item: sort_keys.get(item.id, ("", "", "")))
    total = len(all_rows)
    rows = all_rows[(page - 1) * page_size : page * page_size]
    return SuccessExtra(data=[await product_dict(item) for item in rows], total=total, page=page, page_size=page_size)


@router.post("/products", summary="新增产品")
async def create_product(payload: ProductPayload):
    data = compact(payload.model_dump())
    if error := validate_product_payload(data):
        return Fail(msg=error)
    if not data.get("code"):
        data["code"] = await next_code(ProductItem, "PROD")
    product = await ProductItem.create(**data)
    await sync_product_auto_specs(product_id=product.id)
    return Success(msg="产品已创建", data=await product_dict(product))


@router.put("/products/{product_id}", summary="编辑产品")
async def update_product(product_id: int, payload: ProductPayload):
    data = compact(payload.model_dump(exclude_unset=True))
    if error := validate_product_payload(data):
        return Fail(msg=error)
    await ProductItem.filter(id=product_id).update(**data)
    product = await ProductItem.get(id=product_id)
    await refresh_product_spec_config_snapshots(product.id)
    await sync_product_auto_specs(product_id=product.id)
    return Success(msg="产品已更新", data=await product_dict(product))


@router.post("/products/{product_id}/sync-physical-servers", summary="同步物理服务器规格配置")
async def sync_product_physical_servers(product_id: int):
    product = await ProductItem.get_or_none(id=product_id)
    if not product:
        return Fail(msg="产品不存在")
    if product.status != "active":
        return Fail(msg="产品已下架，规格配置不会同步")
    summary = await sync_physical_server_specs(product_id=product_id)
    return Success(msg="物理服务器规格配置已同步", data=summary)


@router.delete("/products/{product_id}", summary="删除产品")
async def delete_product(product_id: int):
    refs = []
    config_count = await ProductSpecConfig.filter(product_id=product_id, auto_sync=False).count()
    price_count = await ProductPrice.filter(product_id=product_id).count()
    if config_count:
        refs.append(f"规格配置中的手动配置 {config_count} 条")
    if price_count:
        refs.append(f"价格管理中的价格记录 {price_count} 条")
    if refs:
        return Fail(msg=delete_block_msg("产品", refs))
    await ProductItem.filter(id=product_id).delete()
    return Success(msg="产品已删除")


@router.get("/attributes", summary="规格属性列表")
async def list_attributes(
    page: int = Query(1),
    page_size: int = Query(20),
    keyword: str = Query(""),
    attr_type: str = Query(""),
    category_id: int | None = Query(None),
):
    await seed_spec_attributes()
    q = Q()
    if keyword:
        q &= Q(name__contains=keyword) | Q(code__contains=keyword) | Q(unit__contains=keyword)
    if attr_type:
        q &= Q(attr_type=attr_type)
    if category_id:
        all_rows = await ProductSpecAttribute.filter(q).order_by("category_id", "name")
        matched = [item for item in all_rows if int(category_id) in attribute_category_ids(item)]
        total = len(matched)
        rows = matched[(page - 1) * page_size : page * page_size]
        return SuccessExtra(data=[await attribute_dict(item) for item in rows], total=total, page=page, page_size=page_size)
    total = await ProductSpecAttribute.filter(q).count()
    rows = await ProductSpecAttribute.filter(q).order_by("category_id", "name").offset((page - 1) * page_size).limit(page_size)
    return SuccessExtra(data=[await attribute_dict(item) for item in rows], total=total, page=page, page_size=page_size)


@router.post("/attributes", summary="新增规格属性")
async def create_attribute(payload: AttributePayload):
    data = prepare_attribute_payload(payload)
    if not data["category_ids"]:
        return Fail(msg="请选择适用分类")
    attribute = await ProductSpecAttribute.create(**data)
    return Success(msg="规格属性已创建", data=await attribute_dict(attribute))


@router.put("/attributes/{attribute_id}", summary="编辑规格属性")
async def update_attribute(attribute_id: int, payload: AttributePayload):
    data = prepare_attribute_payload(payload)
    if not data["category_ids"]:
        return Fail(msg="请选择适用分类")
    await ProductSpecAttribute.filter(id=attribute_id).update(**data)
    return Success(msg="规格属性已更新", data=await attribute_dict(await ProductSpecAttribute.get(id=attribute_id)))


@router.delete("/attributes/{attribute_id}", summary="删除规格属性")
async def delete_attribute(attribute_id: int):
    config_count = await ProductSpecConfig.filter(attribute_id=attribute_id).count()
    if config_count:
        return Fail(msg=delete_block_msg("规格属性", [f"规格配置中的引用 {config_count} 条"]))
    await ProductSpecAttribute.filter(id=attribute_id).delete()
    return Success(msg="规格属性已删除")


SPEC_CONFIG_SORT_FIELDS = {
    "product_category_sort": "product_category_sort",
    "product_name": "product_name",
    "spec_name": "spec_name",
    "attribute_summary": "attribute_summary",
    "source_label": "source_label",
}


@router.get("/spec-configs", summary="产品规格配置列表")
async def list_spec_configs(
    page: int = Query(1),
    page_size: int = Query(20),
    product_id: int | None = Query(None),
    sort_field: str = Query("product_category_sort"),
    sort_order: str = Query("ascend"),
):
    if product_id:
        product = await ProductItem.get_or_none(id=product_id)
        if not product or product.status != "active":
            return SuccessExtra(data=[], total=0, page=page, page_size=page_size)
    group_rows = await spec_config_groups(product_id=product_id)
    field = SPEC_CONFIG_SORT_FIELDS.get(sort_field) or "product_category_sort"
    reverse = sort_order == "descend"
    group_rows.sort(
        key=lambda item: (
            str(item.get(field) or "").casefold(),
            str(item.get("product_name") or "").casefold(),
            str(item.get("spec_name") or "").casefold(),
            str(item.get("id") or ""),
        ),
        reverse=reverse,
    )
    total = len(group_rows)
    start = (page - 1) * page_size
    return SuccessExtra(data=group_rows[start : start + page_size], total=total, page=page, page_size=page_size)


@router.post("/spec-configs", summary="新增产品规格配置")
async def create_spec_config(payload: SpecConfigPayload):
    if payload.configs:
        items = payload.configs
    elif payload.attribute_id:
        items = [
            SpecConfigItemPayload(
                attribute_id=payload.attribute_id,
                order=payload.order,
                default_value=payload.default_value,
                value_range=payload.value_range,
                required=payload.required,
            )
        ]
    else:
        items = []
    items = [item for item in items if item.attribute_id]
    if not items:
        return Fail(msg="请至少添加一个规格属性")
    source_key = f"manual-{uuid4().hex}"
    snapshot = await product_snapshot(payload.product_id)
    created: list[ProductSpecConfig] = []
    for index, item in enumerate(items):
        data = compact(item.model_dump())
        data["product_id"] = payload.product_id
        data["order"] = data.get("order") or index
        data["source_type"] = "manual"
        data["source_key"] = source_key
        data["auto_sync"] = False
        data.update(snapshot)
        created.append(await ProductSpecConfig.create(**data))
    return Success(msg="产品规格配置已创建", data=await spec_config_group_dict([await spec_config_dict(item) for item in created]))


def spec_config_item_payloads(payload: SpecConfigPayload) -> list[SpecConfigItemPayload]:
    if payload.configs:
        return [item for item in payload.configs if item.attribute_id]
    if payload.attribute_id:
        return [
            SpecConfigItemPayload(
                attribute_id=payload.attribute_id,
                order=payload.order,
                default_value=payload.default_value,
                value_range=payload.value_range,
                required=payload.required,
            )
        ]
    return []


async def get_manual_spec_group(payload: SpecConfigPayload):
    q = ProductSpecConfig.filter(product_id=payload.product_id, auto_sync=False)
    if payload.source_key:
        q = q.filter(source_key=payload.source_key)
    elif payload.config_ids:
        q = q.filter(id__in=payload.config_ids)
    else:
        return []
    rows = await q.order_by("order", "id")
    return rows


@router.post("/spec-config-groups/update", summary="编辑产品规格配置组")
async def update_spec_config_group(payload: SpecConfigPayload):
    existed = await get_manual_spec_group(payload)
    if not existed:
        return Fail(msg="规格配置不存在或为自动同步数据，不能编辑")
    items = spec_config_item_payloads(payload)
    if not items:
        return Fail(msg="请至少添加一个规格属性")
    source_key = payload.source_key or existed[0].source_key or f"manual-{uuid4().hex}"
    snapshot = await product_snapshot(payload.product_id)
    ids = [item.id for item in existed]
    await ProductSpecConfig.filter(id__in=ids).delete()
    created: list[ProductSpecConfig] = []
    for index, item in enumerate(items):
        data = compact(item.model_dump())
        data["product_id"] = payload.product_id
        data["order"] = data.get("order") or index
        data["source_type"] = "manual"
        data["source_key"] = source_key
        data["auto_sync"] = False
        data.update(snapshot)
        created.append(await ProductSpecConfig.create(**data))
    return Success(msg="产品规格配置已更新", data=await spec_config_group_dict([await spec_config_dict(item) for item in created]))


@router.post("/spec-config-groups/delete", summary="删除产品规格配置组")
async def delete_spec_config_group(payload: SpecConfigPayload):
    existed = await get_manual_spec_group(payload)
    if not existed:
        return Fail(msg="规格配置不存在或为自动同步数据，不能删除")
    await ProductSpecConfig.filter(id__in=[item.id for item in existed]).delete()
    return Success(msg="产品规格配置已删除")


@router.put("/spec-configs/{config_id}", summary="编辑产品规格配置")
async def update_spec_config(config_id: int, payload: SpecConfigPayload):
    config = await ProductSpecConfig.get_or_none(id=config_id)
    if not config:
        return Fail(msg="规格配置不存在")
    if config.auto_sync:
        return Fail(msg="自动同步的规格配置不能手动编辑")
    data = compact(
        {
            "product_id": payload.product_id,
            "attribute_id": payload.attribute_id,
            "order": payload.order,
            "default_value": payload.default_value,
            "value_range": payload.value_range,
            "required": payload.required,
        }
    )
    data.update(await product_snapshot(payload.product_id))
    await ProductSpecConfig.filter(id=config_id).update(**{key: value for key, value in data.items() if value is not None})
    return Success(msg="产品规格配置已更新", data=await spec_config_dict(await ProductSpecConfig.get(id=config_id)))


@router.delete("/spec-configs/{config_id}", summary="删除产品规格配置")
async def delete_spec_config(config_id: int):
    config = await ProductSpecConfig.get_or_none(id=config_id)
    if not config:
        return Fail(msg="规格配置不存在")
    if config.auto_sync:
        return Fail(msg="自动同步的规格配置不能手动删除")
    await ProductSpecConfig.filter(id=config_id).delete()
    return Success(msg="产品规格配置已删除")


@router.get("/prices", summary="产品价格列表")
async def list_prices(
    page: int = Query(1),
    page_size: int = Query(20),
    product_id: int | None = Query(None),
    category_id: int | None = Query(None),
    spec_config_key: str = Query(""),
    price_type: str = Query(""),
    keyword: str = Query(""),
    sort_field: str = Query("id"),
    sort_order: str = Query("descend"),
):
    q = Q()
    if product_id:
        q &= Q(product_id=product_id)
    if category_id:
        category_rows = await ProductCategory.all().values("id", "parent_id")
        children: dict[int, list[int]] = {}
        for item in category_rows:
            children.setdefault(int(item.get("parent_id") or 0), []).append(int(item["id"]))
        category_ids = {category_id}
        pending = [category_id]
        while pending:
            current_id = pending.pop()
            for child_id in children.get(current_id, []):
                if child_id not in category_ids:
                    category_ids.add(child_id)
                    pending.append(child_id)
        category_product_ids = await ProductItem.filter(category_id__in=list(category_ids)).values_list("id", flat=True)
        q &= Q(product_id__in=category_product_ids)
    if spec_config_key:
        q &= Q(spec_config_key=spec_config_key)
    if price_type:
        q &= Q(price_type=price_type)
    if keyword:
        product_ids = await ProductItem.filter(Q(name__contains=keyword) | Q(code__contains=keyword)).values_list("id", flat=True)
        q &= Q(customer_name__contains=keyword) | Q(spec_config_name__contains=keyword) | Q(product_id__in=product_ids)
    total = await ProductPrice.filter(q).count()
    sort_fields = {
        "product_name": "product__name",
        "spec_config_display": "spec_config_name",
        "spec_config_name": "spec_config_name",
        "price_type": "price_type",
        "price_type_label": "price_type",
        "customer_name": "customer_name",
        "billing_unit": "billing_unit",
        "billing_unit_label": "billing_unit",
        "amount": "amount",
        "effective_date": "effective_date",
        "expiry_date": "expiry_date",
        "id": "id",
    }
    order_field = sort_fields.get(sort_field, "id")
    if sort_order != "ascend":
        order_field = f"-{order_field}"
    order_fields = [order_field] if order_field.lstrip("-") == "id" else [order_field, "-id"]
    rows = await ProductPrice.filter(q).select_related("product").order_by(*order_fields).offset(
        (page - 1) * page_size
    ).limit(page_size)
    data = await asyncio.gather(
        *(price_dict(item, resolve_spec_group=False, include_dhcp_lease=False) for item in rows)
    )
    return SuccessExtra(data=data, total=total, page=page, page_size=page_size)


@router.get("/price-history", summary="客户历史价格列表")
async def list_price_history(
    page: int = Query(1),
    page_size: int = Query(20),
    product_id: int | None = Query(None),
    customer_id: int | None = Query(None),
):
    q = Q()
    if product_id:
        q &= Q(product_id=product_id)
    if customer_id:
        q &= Q(customer_id=customer_id)
    total = await ProductPriceHistory.filter(q).count()
    rows = await ProductPriceHistory.filter(q).order_by("-off_shelf_at", "-id").offset((page - 1) * page_size).limit(page_size)
    data = []
    for item in rows:
        row = await item.to_dict()
        row["amount"] = float(row.get("amount") or 0)
        row["spec_config_display"] = row.get("spec_config_name") or "-"
        row["price_type_label"] = label_of(PRICE_TYPES, row.get("price_type"))
        row["billing_unit_label"] = label_of(BILLING_UNITS, row.get("billing_unit"))
        data.append(row)
    return SuccessExtra(data=data, total=total, page=page, page_size=page_size)


@router.delete("/price-history/{history_id}", summary="删除客户历史价格")
async def delete_price_history(history_id: int):
    history = await ProductPriceHistory.get_or_none(id=history_id)
    if not history:
        return Fail(msg="客户历史价格记录不存在")
    await history.delete()
    return Success(msg="客户历史价格已删除")


@router.get("/prices/cloud-vms", summary="按产品地区获取可关联云主机")
async def price_cloud_vm_options(product_id: int):
    product = await ProductItem.get_or_none(id=product_id)
    if not product:
        return Fail(msg="关联产品不存在")
    remotes = []
    for binding in await PveNodeBinding.all().select_related("region"):
        region = await binding.region if binding.region_id else None
        if region and (
            await product_matches_region(product, region)
            or normalize_region_key(product.region)
            == normalize_region_key(" ".join(filter(None, [region.code, region.name, region.country, region.city])))
        ):
            remotes.append(binding.remote)
    try:
        vms = [vm for vm in all_vms(await pdm_live_resources_list()) if vm.get("remote") in remotes]
    except Exception as exc:
        logger.warning("failed to fetch live cloud resources for price selection: {}", exc)
        return Fail(msg="实时读取云资源失败，请稍后重试")
    await sync_vm_spec_metadata_from_list(vms)
    await apply_vm_metadata(vms)
    vms.sort(key=lambda item: (str(item.get("remote") or ""), int(item.get("vmid") or 0)))
    return Success(data=[{
        "label": f"{item.get('name') or 'VM'} · {item.get('remote')} / {item.get('vmid')}",
        "value": f"{item.get('remote')}:{item.get('vmid')}",
        "remote": item.get("remote"),
        "vmid": item.get("vmid"),
        "name": item.get("name") or "",
        "customer_id": item.get("customer_id"),
        "customer_name": item.get("customer_name") or "",
    } for item in vms])


async def device_customer(device: AssetDevice, attributes: dict[str, Any] | None = None) -> tuple[int | None, str]:
    attributes = dict(attributes if attributes is not None else device.attributes or {})
    raw_id = attributes.get("customer_id") or attributes.get("客户ID")
    customer = None
    try:
        customer = await CrmCustomer.filter(id=int(raw_id), status=True).exclude(lifecycle="terminated").first() if raw_id else None
    except (TypeError, ValueError):
        pass
    if not customer:
        raw_name = str(attributes.get("customer_name") or attributes.get("客户名称") or attributes.get("customer") or attributes.get("客户") or device.owner or "").strip()
        if raw_name:
            customer = await CrmCustomer.filter(Q(legal_name=raw_name) | Q(name=raw_name), status=True).exclude(lifecycle="terminated").first()
    return (customer.id, customer.legal_name or customer.name) if customer else (None, "")


@router.get("/prices/physical-devices", summary="按产品地区获取可关联物理服务器")
async def price_physical_device_options(product_id: int):
    product = await ProductItem.get_or_none(id=product_id)
    if not product:
        return Fail(msg="关联产品不存在")
    items = []
    for device in await AssetDevice.filter(type=0).select_related("region", "location", "cabinet").order_by("asset_no"):
        region = await device.region if device.region_id else None
        if not region or not (
            await product_matches_region(product, region)
            or normalize_region_key(product.region)
            == normalize_region_key(" ".join(filter(None, [region.code, region.name, region.country, region.city])))
        ):
            continue
        for row in device_to_sales_rows(device):
            if int(row.get("status") or 0) != 1:
                continue
            customer_id, customer_name = await device_customer(device, row.get("attributes"))
            node_name = str(row.get("node_name") or "")
            display_name = row.get("name") or device.name or device.asset_no
            items.append({
                "label": f"{display_name} · {row.get('asset_no') or device.asset_no}" if node_name else display_name,
                "value": f"{device.id}:{node_name}" if node_name else str(device.id),
                "id": device.id,
                "name": display_name,
                "node_name": node_name,
                "customer_id": customer_id,
                "customer_name": customer_name,
            })
    return Success(data=items)


async def price_payload_data(payload: PricePayload) -> tuple[dict[str, Any] | None, str | None]:
    data = compact(payload.model_dump())
    data["notify_user_ids"] = sorted({int(item) for item in (data.get("notify_user_ids") or []) if str(item).isdigit()})
    data["notify_next_at"] = data.get("notify_at") if data.get("notify_enabled") else None
    data.pop("spec_values", None)
    data.pop("os_type", None)
    data.pop("os_version", None)
    data.pop("dhcp_pool_id", None)
    data.pop("vm_name", None)
    data.pop("vm_password", None)
    if not data.get("product_id"):
        return None, "请选择产品"
    product = await ProductItem.get_or_none(id=data["product_id"])
    if not product:
        return None, "关联产品不存在"
    if await product_uses_resource_source(product, {"云主机"}, CLOUD_VM_SOURCE):
        remote, vmid = data.get("cloud_vm_remote"), data.get("cloud_vm_vmid")
        if not remote or not vmid:
            return None, "请选择当前产品地区的云主机"
        vm = await PveVmMetadata.get_or_none(remote=remote, vmid=vmid)
        if not vm:
            return None, "关联云主机不存在"
        data.update(
            cloud_vm_name=vm.vm_name or data.get("cloud_vm_name") or "",
            spec_config_key=f"cloud-vm:{vm.remote}:{vm.vmid}",
            spec_config_name=vm.vm_name or f"{vm.remote} / {vm.vmid}",
        )
        if vm.customer_id:
            data["customer_id"] = vm.customer_id
            data["customer_name"] = vm.customer_name or ""
    elif await product_uses_resource_source(product, {"物理服务器"}, PHYSICAL_SERVER_SOURCE):
        device = await AssetDevice.get_or_none(id=data.get("physical_device_id")).select_related("region", "location", "cabinet")
        if not device:
            return None, "请选择当前产品地区的物理服务器"
        region = await device.region if device.region_id else None
        if not region or not await product_matches_region(product, region):
            return None, "关联物理服务器不属于当前产品地区"
        node_name = str(data.get("physical_device_node") or "").strip()
        resource_row = next(
            (
                row
                for row in device_to_sales_rows(device)
                if int(row.get("status") or 0) == 1 and str(row.get("node_name") or "") == node_name
            ),
            None,
        )
        if not resource_row:
            return None, "关联物理服务器或四合一节点不是使用状态"
        customer_id, customer_name = await device_customer(device, resource_row.get("attributes"))
        data.update(
            physical_device_name=resource_row.get("name") or device.name or device.asset_no,
            physical_device_node=node_name or None,
            spec_config_key=f"physical-device:{device.id}" + (f":node:{node_name}" if node_name else ""),
            spec_config_name=resource_row.get("name") or device.name or device.asset_no,
        )
        if customer_id:
            data["customer_id"] = customer_id
            data["customer_name"] = customer_name
    elif not data.get("spec_config_key") or not await get_spec_config_group(data["spec_config_key"]):
        return None, "请选择有效的规格配置"
    data["price_type"] = "customer"
    data["billing_mode"] = product.billing_mode or "fixed"
    data.pop("min_amount", None)
    data.pop("tier_rules", None)
    data.pop("bandwidth_rule", None)
    if not data.get("customer_id"):
        return None, "请选择客户"
    if not data.get("customer_name"):
        customer = await CrmCustomer.filter(id=data["customer_id"], status=True).exclude(lifecycle="terminated").first()
        if not customer:
            return None, "请选择有效客户，已终止客户不能用于定价"
        data["customer_name"] = customer.legal_name or customer.name
    return data, None


def bytes_to_gb(value: Any) -> float:
    return max(0, float(value or 0)) / 1024 / 1024 / 1024


def pve_capacity_score(group: dict[str, Any], cpu_cores: int, memory_gb: int, disk_gb: int) -> tuple[float, float] | None:
    cpu_total = float(group.get("cpu_total") or 0)
    cpu_usage = float(group.get("cpu_usage") or 0)
    cpu_free = cpu_total * max(0, 1 - cpu_usage / 100)
    memory_free = bytes_to_gb(float(group.get("maxmem") or 0) - float(group.get("mem") or 0))
    disk_free = bytes_to_gb(float(group.get("maxdisk") or 0) - float(group.get("disk") or 0))
    if cpu_free < cpu_cores or memory_free < memory_gb or disk_free < disk_gb:
        return None
    ratios = (cpu_free / cpu_cores, memory_free / memory_gb, disk_free / disk_gb)
    return min(ratios), sum(ratios)


async def pve_remote_for_product_region(product: ProductItem, spec_values: dict[str, Any] | None) -> str | None:
    values = spec_values or {}
    cpu_cores = int(values.get("cpu_core") or 0)
    memory_gb = int(values.get("mem_total") or 0)
    disk_gb = int(values.get("disk_total") or 0)
    candidates: list[tuple[tuple[float, float], str]] = []
    for group in await cloud_remote_groups():
        region_id = group.get("region_id")
        region = await AssetRegion.get_or_none(id=region_id) if region_id else None
        region_key = normalize_region_key(" ".join(filter(None, [region.code, region.name, region.country, region.city]))) if region else ""
        if not region or not (await product_matches_region(product, region)) and normalize_region_key(product.region) != region_key:
            continue
        score = pve_capacity_score(group, cpu_cores, memory_gb, disk_gb)
        remote = str(group.get("remote") or group.get("value") or "")
        if score and remote:
            candidates.append((score, remote))
    if not candidates:
        return None
    candidates.sort(key=lambda item: (item[0][0], item[0][1], item[1]), reverse=True)
    return candidates[0][1]


async def pve_storage_for_remote(remote: str) -> str | None:
    storages = await pdm_storage_options(remote)
    if not storages:
        ssh_host = await resolve_create_host(remote)
        exit_status, stdout, _stderr = await run_remote_script(ssh_host, "pvesm status --content images")
        if exit_status == 0:
            storages = parse_storage_output(stdout)
    if not storages:
        return None
    preferred = next((item for item in storages if item.get("value") == "local-lvm"), None)
    return str((preferred or storages[0]).get("value") or "") or None


async def create_cloud_vm_for_price(
    price: ProductPrice, product: ProductItem, payload: PricePayload, lease: CloudDhcpLease
) -> tuple[str | None, dict[str, Any] | None]:
    remote = await pve_remote_for_product_region(product, payload.spec_values)
    if not remote:
        return f"产品地区 {product.region or '-'} 没有资源充足的已关联 PVE 节点", None
    storage = await pve_storage_for_remote(remote)
    if not storage:
        return f"PVE 节点 {remote} 未发现可用于创建虚拟机的存储", None

    vm_name = f"cloud-{price.id}"
    password = secrets.token_urlsafe(12)
    expiry_tag = f"有效期至：{payload.expiry_date}" if payload.expiry_date else ""
    description = " | ".join(item for item in (payload.remark or "", f"产品价格 #{price.id}", expiry_tag) if item)

    cidr_suffix = str(lease.cidr or "").split("/", 1)[1] if "/" in str(lease.cidr or "") else ""
    network = VMNetworkConfig(
        mode="static",
        ip=f"{lease.ip}/{cidr_suffix}" if cidr_suffix else lease.ip,
        gw=str(lease.gateway or "").split("/", 1)[0],
        dns=(await lease.pool).dns or "8.8.8.8",
        vlan=lease.vlan,
    )
    response = await create_pve_vm(
        VMCreateRequest(
            region=remote,
            storage=storage,
            vm_name=vm_name,
            description=description,
            os_type=str(payload.os_type or ""),
            os_version=str(payload.os_version or ""),
            cpu_cores=int((payload.spec_values or {}).get("cpu_core") or 0),
            memory_gb=int((payload.spec_values or {}).get("mem_total") or 0),
            disk_gb=int((payload.spec_values or {}).get("disk_total") or 0),
            password=password,
            customer_id=price.customer_id,
            customer_name=price.customer_name,
            network=network,
            expire_at=payload.expiry_date,
        )
    )
    result = json.loads(response.body)
    if result.get("code") != 200:
        return str(result.get("msg") or "创建虚拟机失败"), None
    created = result.get("data") or {}
    await CloudDhcpLease.filter(id=lease.id).update(remote=created.get("remote") or remote, vmid=created.get("vmid"))
    return None, {
        "vm_name": vm_name,
        "password": password,
        "ip": lease.ip,
        "remote": created.get("remote") or remote,
        "vmid": created.get("vmid"),
        "expiry_date": str(payload.expiry_date) if payload.expiry_date else None,
    }


@router.post("/prices", summary="新增产品价格")
async def create_price(payload: PricePayload):
    data, error = await price_payload_data(payload)
    if error:
        return Fail(msg=error)
    inherited_from_price_id = data.get("inherited_from_price_id")
    if inherited_from_price_id:
        source_price = await ProductPrice.get_or_none(id=inherited_from_price_id)
        if not source_price or source_price.price_type != "standard" or source_price.product_id != data.get("product_id"):
            return Fail(msg="继承来源价格无效")
    price = await ProductPrice.create(**data)
    product = await price.product
    try:
        result = await price_dict(price)
    except Exception:
        logger.exception("price created but response data assembly failed: price_id={}", price.id)
        result = {
            "id": price.id,
            "product_id": price.product_id,
            "product_name": product.name,
            "price_type": price.price_type,
            "amount": float(price.amount or 0),
        }
    return Success(msg="产品价格已创建", data=result)


@router.put("/prices/{price_id}", summary="编辑产品价格")
async def update_price(price_id: int, payload: PricePayload):
    data, error = await price_payload_data(payload)
    if error:
        return Fail(msg=error)
    await ProductPrice.filter(id=price_id).update(**data)
    price = await ProductPrice.get(id=price_id)
    return Success(msg="产品价格已更新", data=await price_dict(price))


@router.put("/prices/{price_id}/notification", summary="更新客户价格飞书通知")
async def update_price_notification(price_id: int, payload: PriceNotificationPayload):
    price = await ProductPrice.get_or_none(id=price_id)
    if not price:
        return Fail(msg="价格记录不存在")
    if price.price_type != "customer":
        return Fail(msg="仅客户价格支持飞书通知")
    user_ids = sorted({int(item) for item in payload.notify_user_ids})
    notify_at = payload.notify_at
    if payload.notify_enabled:
        if not user_ids:
            return Fail(msg="请选择飞书提醒接收人")
        if payload.notify_schedule == "monthly":
            if not payload.notify_day or not payload.notify_time:
                return Fail(msg="请填写每月执行日和执行时间")
            hour, minute, *second = [int(item) for item in payload.notify_time.split(":")]
            now = datetime.now()
            day = min(payload.notify_day, monthrange(now.year, now.month)[1])
            notify_at = now.replace(day=day, hour=hour, minute=minute, second=second[0] if second else 0, microsecond=0)
            if notify_at <= now:
                year = now.year + (now.month == 12)
                month = 1 if now.month == 12 else now.month + 1
                notify_at = notify_at.replace(year=year, month=month, day=min(payload.notify_day, monthrange(year, month)[1]))
        elif not notify_at:
            return Fail(msg="请选择一次性提醒时间")
    await price.update_from_dict(
        {
            "notify_enabled": payload.notify_enabled,
            "notify_user_ids": user_ids,
            "notify_schedule": payload.notify_schedule,
            "notify_at": notify_at,
            "notify_next_at": notify_at if payload.notify_enabled else None,
            "notify_last_at": None,
        }
    )
    await price.save()
    return Success(msg="飞书通知已更新", data=await price_dict(price))


@router.delete("/prices/{price_id}", summary="删除产品价格")
async def delete_price(price_id: int):
    price = await ProductPrice.get_or_none(id=price_id)
    if not price:
        return Fail(msg="价格记录不存在")
    product = await price.product
    is_cloud_product = await product_uses_resource_source(product, {"云主机"}, CLOUD_VM_SOURCE)
    if is_cloud_product and price.cloud_vm_remote and price.cloud_vm_vmid:
        response = await submit_vm_power(
            VMPowerRequest(remote=price.cloud_vm_remote, vmid=price.cloud_vm_vmid, type="pve-qemu", action="stop"),
            allow_price_managed_stop=True,
        )
        result = json.loads(response.body)
        if result.get("code") != 200:
            return Fail(msg=f"下架价格失败，关联虚拟机关机失败：{result.get('msg') or '未知错误'}")
    physical_released = False
    if price.physical_device_id:
        node_name = str(price.physical_device_node or "").strip()
        other_price_query = ProductPrice.filter(physical_device_id=price.physical_device_id).exclude(id=price.id)
        if node_name:
            other_price_query = other_price_query.filter(physical_device_node=node_name)
        if not await other_price_query.exists():
            device = await AssetDevice.get_or_none(id=price.physical_device_id)
            if device:
                if node_name:
                    attributes = dict(device.attributes or {})
                    nodes = attributes.get("nodes")
                    if isinstance(nodes, list):
                        for node in nodes:
                            if isinstance(node, dict) and str(node.get("name") or "").strip() == node_name:
                                node["status"] = 0
                                physical_released = True
                                break
                        if physical_released:
                            device.attributes = attributes
                            device.status = aggregate_sales_device_status(nodes)
                            await device.save(update_fields=["attributes", "status"])
                else:
                    device.status = 0
                    await device.save(update_fields=["status"])
                    physical_released = True
    history_data = await price.to_dict()
    history_data.pop("id", None)
    history_data.pop("created_at", None)
    history_data.pop("updated_at", None)
    history_data.pop("notify_enabled", None)
    history_data.pop("notify_user_ids", None)
    history_data.pop("notify_schedule", None)
    history_data.pop("notify_at", None)
    history_data.pop("notify_next_at", None)
    history_data.pop("notify_last_at", None)
    history_data.pop("inherited_from_price_id", None)
    history_data.pop("min_amount", None)
    history_data.pop("tier_rules", None)
    history_data.pop("bandwidth_rule", None)
    history_data.pop("status", None)
    history_data["source_price_id"] = price.id
    history_data["product_name"] = product.name
    history_data["off_shelf_at"] = datetime.now()
    await ProductPriceHistory.create(**history_data)
    await price.delete()
    if is_cloud_product and price.cloud_vm_remote:
        return Success(msg="产品价格已下架，关联虚拟机关机请求已提交")
    if physical_released:
        return Success(msg="产品价格已下架，关联物理服务器已标记为空闲")
    return Success(msg="产品价格已下架")


@router.get("/templates", summary="产品模板列表")
async def list_templates(page: int = Query(1), page_size: int = Query(20), keyword: str = Query(""), category_id: int | None = Query(None)):
    q = Q()
    if keyword:
        q &= Q(name__contains=keyword) | Q(description__contains=keyword)
    if category_id:
        q &= Q(category_id=category_id)
    total = await ProductTemplate.filter(q).count()
    rows = await ProductTemplate.filter(q).order_by("category_id", "name").offset((page - 1) * page_size).limit(page_size)
    return SuccessExtra(data=[await template_dict(item) for item in rows], total=total, page=page, page_size=page_size)


@router.post("/templates", summary="新增产品模板")
async def create_template(payload: TemplatePayload):
    template = await ProductTemplate.create(**compact(payload.model_dump()))
    return Success(msg="产品模板已创建", data=await template_dict(template))


@router.put("/templates/{template_id}", summary="编辑产品模板")
async def update_template(template_id: int, payload: TemplatePayload):
    await ProductTemplate.filter(id=template_id).update(**compact(payload.model_dump(exclude_unset=True)))
    return Success(msg="产品模板已更新", data=await template_dict(await ProductTemplate.get(id=template_id)))


@router.delete("/templates/{template_id}", summary="删除产品模板")
async def delete_template(template_id: int):
    await ProductTemplate.filter(id=template_id).delete()
    return Success(msg="产品模板已删除")
