import csv
import io
import json

from fastapi import APIRouter, File, Query, UploadFile
from fastapi.responses import StreamingResponse
from tortoise.expressions import Q

from app.controllers.asset import (
    asset_cabinet_controller,
    asset_device_controller,
    asset_inventory_category_controller,
    asset_inventory_controller,
    asset_location_controller,
    asset_region_controller,
)
from app.models.asset import AssetCabinet, AssetDevice, AssetInventory, AssetInventoryCategory, AssetLocation, AssetRegion
from app.core.ctx import CTX_USER_ID
from app.models.admin import User
from app.schemas.assets import (
    AssetCabinetCreate,
    AssetCabinetUpdate,
    AssetDeviceCreate,
    AssetDeviceUpdate,
    AssetInventoryCategoryCreate,
    AssetInventoryCategoryUpdate,
    AssetInventoryCreate,
    AssetInventoryUpdate,
    AssetLocationCreate,
    AssetLocationUpdate,
    AssetRegionCreate,
    AssetRegionUpdate,
)
from app.schemas.base import Success, SuccessExtra

router = APIRouter()

SENSITIVE_DEVICE_ATTRIBUTE_KEYS = {"IPMI密码"}
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
    result = dict(attributes)
    for key in SENSITIVE_DEVICE_ATTRIBUTE_KEYS:
        if result.get(key):
            result[key] = MASKED_DEVICE_SECRET
    return result


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


def get_inventory_order(sort_by: str = "", sort_order: str = "") -> list[str]:
    sortable_fields = {"type", "subtype", "quantity"}
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
    if keyword:
        matched_items = [
            item
            for item in await AssetInventory.filter(q).order_by(*order)
            if inventory_matches_keyword(item, keyword)
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
            attributes = parse_inventory_attributes(row)
            inventory_data = {
                "location_id": location_id,
                "type": type_name,
                "subtype": str(row.get("子类", "") or "").strip(),
                "quantity": quantity,
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
                await asset_inventory_controller.update_inventory(
                    id=existed.id,
                    obj_in=AssetInventoryUpdate(id=existed.id, **inventory_data),
                )
            else:
                await asset_inventory_controller.create_inventory(AssetInventoryCreate(**inventory_data))
            success_count += 1
        except Exception as exc:
            error_rows.append(f"第{row_num}行: {exc}")

    msg = f"导入成功 {success_count} 条"
    if error_rows:
        msg += f"，错误: {'; '.join(error_rows[:5])}"
        if len(error_rows) > 5:
            msg += f" 等 {len(error_rows)} 条"
    return Success(msg=msg, data={"success_count": success_count, "errors": error_rows})


@router.post("/inventory/create", summary="创建库存")
async def create_inventory(inventory_in: AssetInventoryCreate):
    obj = await asset_inventory_controller.create_inventory(inventory_in)
    return Success(msg="Created Successfully", data=await inventory_to_dict(obj))


@router.post("/inventory/update", summary="更新库存")
async def update_inventory(inventory_in: AssetInventoryUpdate):
    obj = await asset_inventory_controller.update_inventory(id=inventory_in.id, obj_in=inventory_in)
    return Success(msg="Updated Successfully", data=await inventory_to_dict(obj))


@router.delete("/inventory/delete", summary="删除库存")
async def delete_inventory(inventory_id: int = Query(...)):
    await asset_inventory_controller.remove(id=inventory_id)
    return Success(msg="Deleted Successfully")
