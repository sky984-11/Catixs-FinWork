import re
from typing import Any, Literal

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field
from tortoise.expressions import Q
from tortoise.exceptions import IntegrityError
from tortoise.transactions import in_transaction

from .product_price_versions import router as price_versions_router

from app.models.customer_center import CrmCustomer
from app.models.admin import User
from app.models.product_center import (
    ProductCategory,
    ProductItem,
    ProductPrice,
    ProductPriceVersion,
    ProductSpecAttribute,
    ProductSpecConfig,
    ProductTemplate,
)
from app.schemas.base import Fail, Success, SuccessExtra

router = APIRouter()
router.include_router(price_versions_router)

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
    name: str = Field(..., min_length=1, max_length=160)
    code: str | None = Field(None, max_length=80)
    category_id: int | None = None
    status: Literal["active", "offline"] = "active"
    billing_unit: str = Field("month", min_length=1, max_length=40)
    min_contract_months: int = Field(1, ge=1, le=1200)
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


def prepare_attribute_payload(payload: AttributePayload) -> dict[str, Any]:
    data = compact(payload.model_dump())
    ids = normalize_category_ids(data.pop("category_ids", None), data.get("category_id"))
    data["category_ids"] = ids
    data["category_id"] = ids[0] if ids else None
    return data


def validate_product_payload(data: dict[str, Any]) -> str | None:
    if not data.get("category_id"):
        return "请选择产品分类"
    if not str(data.get("name") or "").strip():
        return "请填写产品名称"
    if not str(data.get("billing_unit", "month")).strip():
        return "请填写计费单位"
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


async def next_product_sku(category: ProductCategory, conn) -> str:
    # Reserve space for the separator and a growing numeric suffix within code's 80-character limit.
    category_code = (category.code or "").strip()
    prefix = category_code if category_code and len(category_code) <= 60 else f"CAT{category.id}"
    prefix += "-"
    codes = await ProductItem.filter(code__startswith=prefix).using_db(conn).values_list("code", flat=True)
    sequences = [int(code[len(prefix):]) for code in codes if re.fullmatch(r"[0-9]+", code[len(prefix):])]
    return f"{prefix}{max(sequences, default=0) + 1:03d}"


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
    customers = await CrmCustomer.filter(status=True).exclude(lifecycle="terminated").order_by("name").values(
        "id", "name", "legal_name", "signing_entity__name"
    )
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
            "customers": [
                {
                    "label": item["name"] or item["legal_name"],
                    "value": item["id"],
                    "signing_entity_name": item.get("signing_entity__name") or "",
                    "class": "customer-select-option",
                }
                for item in customers
            ],
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
        category_ids = {category_id}
        pending = {category_id}
        while pending:
            children = set(await ProductCategory.filter(parent_id__in=list(pending)).values_list("id", flat=True))
            pending = children - category_ids
            category_ids.update(pending)
        q &= Q(category_id__in=list(category_ids))
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
    automatic = not str(data.get("code") or "").strip()
    for attempt in range(3):
        try:
            async with in_transaction() as conn:
                category = await ProductCategory.filter(id=data["category_id"]).using_db(conn).select_for_update().first()
                if not category:
                    return Fail(msg="产品分类不存在")
                if automatic:
                    data["code"] = await next_product_sku(category, conn)
                if await ProductItem.filter(code=data["code"]).using_db(conn).exists():
                    return Fail(code=409, msg="SKU 已存在")
                product = await ProductItem.create(using_db=conn, **data)
            return Success(msg="产品已创建", data=await product_dict(product))
        except IntegrityError:
            # Also handle a manual SKU racing an automatic allocation from another category.
            if not await ProductItem.filter(code=data["code"]).exists():
                raise
            if not automatic or attempt == 2:
                return Fail(code=409, msg="SKU 已存在，请重试")


@router.put("/products/{product_id}", summary="编辑产品")
async def update_product(product_id: int, payload: ProductPayload):
    data = compact(payload.model_dump(exclude_unset=True))
    if error := validate_product_payload(data):
        return Fail(msg=error)
    if not await ProductItem.filter(id=product_id).exists():
        return Fail(code=404, msg="产品不存在")
    if not await ProductCategory.filter(id=data["category_id"]).exists():
        return Fail(msg="产品分类不存在")
    if data.get("code") and await ProductItem.filter(code=data["code"]).exclude(id=product_id).exists():
        return Fail(code=409, msg="SKU 已存在")
    await ProductItem.filter(id=product_id).update(**data)
    product = await ProductItem.get(id=product_id)
    return Success(msg="产品已更新", data=await product_dict(product))


@router.delete("/products/{product_id}", summary="删除产品")
async def delete_product(product_id: int):
    async with in_transaction() as conn:
        product = await ProductItem.filter(id=product_id).using_db(conn).select_for_update().first()
        if not product:
            return Fail(code=404, msg="产品不存在")
        refs = []
        version_count = await ProductPriceVersion.filter(product_id=product_id).count()
        if version_count:
            refs.append(f"价格方案历史版本 {version_count} 条")
        config_count = await ProductSpecConfig.filter(product_id=product_id, auto_sync=False).count()
        price_count = await ProductPrice.filter(product_id=product_id).count()
        if config_count:
            refs.append(f"历史规格中的手动配置 {config_count} 条")
        if price_count:
            refs.append(f"历史资源价格记录 {price_count} 条")
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
        # Legacy CAT and IDC catalogs can contain the same named category path.
        # Match the full path, so similarly named leaves in other branches remain separate.
        categories = {item.id: item for item in await ProductCategory.all()}

        def category_path(item_id):
            names = []
            visited = set()
            while item_id:
                if item_id in visited or item_id not in categories:
                    return None
                visited.add(item_id)
                item = categories[item_id]
                names.append(item.name)
                item_id = item.parent_id
            return tuple(reversed(names))

        selected_path = category_path(category_id)
        matching_ids = {category_id}
        if selected_path:
            matching_ids.update(item_id for item_id in categories if category_path(item_id) == selected_path)
        all_rows = await ProductSpecAttribute.filter(q).order_by("category_id", "name")
        matched = [item for item in all_rows if matching_ids.intersection(attribute_category_ids(item))]
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
        return Fail(msg=delete_block_msg("规格属性", [f"历史规格中的引用 {config_count} 条"]))
    await ProductSpecAttribute.filter(id=attribute_id).delete()
    return Success(msg="规格属性已删除")


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
