import csv
import asyncio
import io
import json
import os
import urllib.error
import urllib.request
from copy import deepcopy
from datetime import date, datetime

from fastapi import APIRouter, File, Query, UploadFile
from fastapi.responses import StreamingResponse
from tortoise.expressions import Q
from tortoise.transactions import in_transaction

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
from app.models.admin import User
from app.schemas.assets import (
    AssetCabinetCreate,
    AssetCabinetUpdate,
    AssetDeviceBrandCreate,
    AssetDeviceCreate,
    AssetDeviceModelCreate,
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

INVENTORY_FEISHU_WEBHOOK = os.getenv(
    "INVENTORY_FEISHU_WEBHOOK",
    "https://open.feishu.cn/open-apis/bot/v2/hook/4c3e89a6-35dd-4de3-b763-e1049449e5d4",
)

SENSITIVE_DEVICE_ATTRIBUTE_KEYS = {"IPMI密码", "snmp团体名"}
MASKED_DEVICE_SECRET = "******"
DEVICE_SECRET_VIEW_ROLE_NAMES = {"admin", "noc"}
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
    if not can_view_secrets:
        data["attributes"] = mask_device_secret_attributes(data.get("attributes"))
    cabinet = await AssetCabinet.get_or_none(id=device.cabinet_id)
    location = await AssetLocation.get_or_none(id=device.location_id)
    region = await AssetRegion.get_or_none(id=device.region_id)
    data["cabinet_name"] = cabinet.name if cabinet else ""
    data["location_name"] = location.name if location else ""
    data["region_name"] = region.name if region else ""
    return data


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
    status: bool | None = Query(None),
):
    q = Q()
    if name:
        q &= Q(name__contains=name)
    if code:
        q &= Q(code__contains=code)
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
    return SuccessExtra(data=data, total=total, page=page, page_size=page_size)


@router.get("/cabinet/get", summary="机柜详情")
async def get_cabinet(cabinet_id: int = Query(...)):
    obj = await asset_cabinet_controller.get(id=cabinet_id)
    data = await obj.to_dict()
    data["device_count"] = await AssetDevice.filter(cabinet_id=cabinet_id).count()
    return Success(data=data)


@router.post("/cabinet/create", summary="创建机柜")
async def create_cabinet(cabinet_in: AssetCabinetCreate):
    obj = await asset_cabinet_controller.create(cabinet_in)
    return Success(msg="Created Successfully", data=await obj.to_dict())


@router.post("/cabinet/update", summary="更新机柜")
async def update_cabinet(cabinet_in: AssetCabinetUpdate):
    obj = await asset_cabinet_controller.update(id=cabinet_in.id, obj_in=cabinet_in)
    return Success(msg="Updated Successfully", data=await obj.to_dict())


@router.delete("/cabinet/delete", summary="删除机柜")
async def delete_cabinet(cabinet_id: int = Query(...)):
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


@router.post("/device/create", summary="创建设备")
async def create_device(device_in: AssetDeviceCreate):
    await prepare_device_attributes_for_save(device_in)
    obj = await asset_device_controller.create_device(device_in)
    return Success(data=await device_to_dict(obj, can_view_secrets=await can_view_device_secrets()), msg="Created Successfully")


@router.post("/device/update", summary="更新设备")
async def update_device(device_in: AssetDeviceUpdate):
    await prepare_device_attributes_for_save(device_in)
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
