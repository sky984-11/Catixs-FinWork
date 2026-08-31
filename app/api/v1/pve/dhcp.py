import ipaddress
from datetime import date, datetime
from typing import Any

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field
from tortoise.expressions import Q

from app.models.asset import AssetLocation, AssetRegion, CloudDhcpLease, CloudDhcpPool
from app.models.product_center import ProductItem, ProductPrice
from app.schemas.base import Fail, Success, SuccessExtra

router = APIRouter(prefix="/dhcp-pools")

ACTIVE_LEASE_STATUS = "reserved"

class DhcpPoolPayload(BaseModel):
    name: str = Field(..., max_length=120)
    region_code: str = Field(..., max_length=40)
    region_id: int | None = None
    location_id: int | None = None
    vlan: int
    gateway: str = Field(..., max_length=64)
    cidr: str = Field(..., max_length=64)
    start_ip: str = Field(..., max_length=64)
    end_ip: str = Field(..., max_length=64)
    dns: str | None = Field(None, max_length=120)
    status: bool = True
    remark: str | None = Field(None, max_length=500)


def normalize_region_key(value: str | None) -> str:
    text = str(value or "").casefold()
    if any(key in text for key in ("香港", "hong kong", " hk", "/ hk", "hk ")):
        return "HK"
    if any(key in text for key in ("台湾", "taiwan", "taipei", "tw ")):
        return "TW"
    if any(key in text for key in ("日本", "东京", "tokyo", "japan", "jpn")):
        return "JPN"
    if any(key in text for key in ("新加坡", "singapore", "sg ")):
        return "SG"
    if any(key in text for key in ("英国", "伦敦", "london", "united kingdom", " uk")):
        return "UK"
    if any(key in text for key in ("德国", "法兰克福", "frankfurt", "germany", " de")):
        return "DE"
    if any(key in text for key in ("la3", "los angeles", "洛杉矶")):
        return "LA3"
    return str(value or "").strip().upper()


def region_matches(region: AssetRegion, region_code: str) -> bool:
    haystack = " ".join([region.code or "", region.name or "", region.country or "", region.city or ""])
    return normalize_region_key(haystack) == region_code


async def default_region(region_code: str) -> AssetRegion | None:
    regions = await AssetRegion.filter(status=True).all()
    for region in regions:
        if region_matches(region, region_code):
            return region
    return None


def ip_range(start_ip: str, end_ip: str) -> list[str]:
    start = ipaddress.ip_address(start_ip)
    end = ipaddress.ip_address(end_ip)
    if int(end) < int(start):
        raise ValueError("IP结束地址不能小于开始地址")
    return [str(ipaddress.ip_address(item)) for item in range(int(start), int(end) + 1)]


def validate_pool_ips(data: dict[str, Any]) -> str | None:
    try:
        ipaddress.ip_interface(data["gateway"])
        ipaddress.ip_network(data["cidr"], strict=False)
        ip_range(data["start_ip"], data["end_ip"])
    except ValueError as exc:
        return str(exc)
    return None


def expiry_remark(expiry_date: Any | None) -> str:
    value = normalize_expiry_date(expiry_date)
    return f"有效期至: {value}" if value else ""


def normalize_expiry_date(value: Any | None) -> date | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, (int, float)):
        timestamp = float(value) / 1000 if float(value) > 10_000_000_000 else float(value)
        return datetime.fromtimestamp(timestamp).date()
    text = str(value).strip()
    if not text:
        return None
    try:
        if text.isdigit():
            return normalize_expiry_date(int(text))
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except ValueError:
        return None


async def pool_counts(pool: CloudDhcpPool) -> dict[str, Any]:
    addresses = ip_range(pool.start_ip, pool.end_ip)
    used_ips = set(
        await CloudDhcpLease.filter(pool_id=pool.id, status=ACTIVE_LEASE_STATUS).values_list("ip", flat=True)
    )
    available = [item for item in addresses if item not in used_ips]
    return {
        "total_count": len(addresses),
        "used_count": len(used_ips),
        "available_count": len(available),
        "next_ip": available[0] if available else "",
    }


async def pool_dict(pool: CloudDhcpPool) -> dict[str, Any]:
    data = await pool.to_dict()
    data.update(await pool_counts(pool))
    location = await pool.location if pool.location_id else None
    data["location_name"] = location.name if location else ""
    place = pool.region_name or pool.region_code
    if location:
        place = f"{place} / {location.name}"
    data["label"] = f'{place} / VLAN {pool.vlan} ({data["available_count"]} available)'
    data["value"] = pool.id
    return data


async def active_pools_for_region(
    region: str | None = None,
    pool_id: int | None = None,
    region_id: int | None = None,
) -> list[CloudDhcpPool]:
    q = Q(status=True)
    if pool_id:
        q &= Q(id=pool_id)
    elif region_id:
        q &= Q(region_id=region_id)
    else:
        region_code = normalize_region_key(region)
        if region_code:
            q &= Q(region_code=region_code)
    return await CloudDhcpPool.filter(q).order_by("region_code", "vlan", "id")


async def allocate_dhcp_for_price(
    price: ProductPrice,
    product: ProductItem,
    spec_values: dict[str, Any] | None = None,
    os_type: str | None = None,
    os_version: str | None = None,
    expiry_date: Any | None = None,
    pool_id: int | None = None,
) -> CloudDhcpLease | None:
    existing = await CloudDhcpLease.filter(price_id=price.id, status=ACTIVE_LEASE_STATUS).first()
    values = spec_values or {}
    if existing:
        if pool_id and existing.pool_id != pool_id:
            await CloudDhcpLease.filter(id=existing.id).update(status="released")
        else:
            await CloudDhcpLease.filter(id=existing.id).update(
                os_type=os_type,
                os_version=os_version,
                cpu_cores=int(values.get("cpu_core") or existing.cpu_cores or 2),
                memory_gb=int(values.get("mem_total") or existing.memory_gb or 2),
                disk_gb=int(values.get("disk_total") or existing.disk_gb or 20),
                expiry_date=normalize_expiry_date(expiry_date),
                remark=expiry_remark(expiry_date),
            )
            return await CloudDhcpLease.get(id=existing.id)
    pools = await active_pools_for_region(product.region, pool_id=pool_id)
    for pool in pools:
        counts = await pool_counts(pool)
        if not counts["next_ip"]:
            continue
        lease, _ = await CloudDhcpLease.update_or_create(
            pool_id=pool.id,
            ip=counts["next_ip"],
            defaults={
                "product_id": product.id,
                "price_id": price.id,
                "vlan": pool.vlan,
                "gateway": pool.gateway,
                "cidr": pool.cidr,
                "os_type": os_type,
                "os_version": os_version,
                "cpu_cores": int(values.get("cpu_core") or 2),
                "memory_gb": int(values.get("mem_total") or 2),
                "disk_gb": int(values.get("disk_total") or 20),
                "expiry_date": normalize_expiry_date(expiry_date),
                "status": ACTIVE_LEASE_STATUS,
                "remark": expiry_remark(expiry_date),
            },
        )
        return lease
    return None


async def release_price_dhcp(price_id: int) -> None:
    await CloudDhcpLease.filter(price_id=price_id, status=ACTIVE_LEASE_STATUS).update(status="released")


async def release_dhcp_lease(lease_id: int | None) -> None:
    if lease_id:
        await CloudDhcpLease.filter(id=lease_id, status=ACTIVE_LEASE_STATUS).update(status="released")


async def build_pool_data(payload: DhcpPoolPayload) -> dict[str, Any]:
    data = payload.model_dump()
    region_id = data.pop("region_id", None)
    location_id = data.pop("location_id", None)
    region = await AssetRegion.get_or_none(id=region_id) if region_id else None
    location = await AssetLocation.get_or_none(id=location_id).select_related("region") if location_id else None
    if location:
        region = await location.region if location.region_id else region
    if not region:
        region = await default_region(data.get("region_code"))
    data["region_code"] = normalize_region_key(region.code or region.name or data.get("region_code")) if region else normalize_region_key(data.get("region_code"))
    data["region_id"] = region.id if region else None
    data["location_id"] = location.id if location else None
    data["region_name"] = f"{region.country or ''} / {region.city or region.name or ''}".strip(" /") if region else data["region_code"]
    return data


async def reserve_dhcp_lease(
    pool_id: int,
    *,
    os_type: str | None = None,
    os_version: str | None = None,
    cpu_cores: int = 2,
    memory_gb: int = 2,
    disk_gb: int = 20,
    expiry_date: Any | None = None,
    remark: str | None = None,
) -> CloudDhcpLease | None:
    pools = await active_pools_for_region(pool_id=pool_id)
    if not pools:
        return None
    pool = pools[0]
    counts = await pool_counts(pool)
    if not counts["next_ip"]:
        return None
    lease, _ = await CloudDhcpLease.update_or_create(
        pool_id=pool.id,
        ip=counts["next_ip"],
        defaults={
            "vlan": pool.vlan,
            "gateway": pool.gateway,
            "cidr": pool.cidr,
            "os_type": os_type,
            "os_version": os_version,
            "cpu_cores": int(cpu_cores or 2),
            "memory_gb": int(memory_gb or 2),
            "disk_gb": int(disk_gb or 20),
            "expiry_date": normalize_expiry_date(expiry_date),
            "status": ACTIVE_LEASE_STATUS,
            "remark": remark or expiry_remark(expiry_date),
        },
    )
    return lease


async def lease_dict_for_price(price_id: int) -> dict[str, Any] | None:
    lease = await CloudDhcpLease.filter(price_id=price_id, status=ACTIVE_LEASE_STATUS).first()
    if not lease:
        return None
    data = await lease.to_dict()
    pool = await lease.pool
    data["pool_name"] = pool.name if pool else ""
    data["region_name"] = pool.region_name if pool else ""
    data["location_name"] = (await pool.location).name if pool and pool.location_id else ""
    return data


@router.get("", summary="Cloud DHCP pool list")
async def list_dhcp_pools(
    page: int = Query(1),
    page_size: int = Query(20),
    keyword: str = Query(""),
    region: str = Query(""),
):
    q = Q()
    if keyword:
        q &= Q(name__contains=keyword) | Q(region_name__contains=keyword) | Q(start_ip__contains=keyword) | Q(end_ip__contains=keyword)
    if region:
        q &= Q(region_code=normalize_region_key(region))
    total = await CloudDhcpPool.filter(q).count()
    rows = await CloudDhcpPool.filter(q).order_by("region_code", "vlan", "id").offset((page - 1) * page_size).limit(page_size)
    return SuccessExtra(data=[await pool_dict(item) for item in rows], total=total, page=page, page_size=page_size)


@router.get("/options", summary="Cloud DHCP pool options")
async def dhcp_pool_options(
    region: str = Query(""),
    pool_id: int | None = Query(None),
    region_id: int | None = Query(None),
):
    rows = await active_pools_for_region(region, pool_id=pool_id, region_id=region_id)
    return Success(data=[await pool_dict(item) for item in rows])


@router.post("", summary="Create DHCP pool")
async def create_dhcp_pool(payload: DhcpPoolPayload):
    data = await build_pool_data(payload)
    if error := validate_pool_ips(data):
        return Fail(msg=error)
    pool = await CloudDhcpPool.create(**data)
    return Success(msg="DHCP池已创建", data=await pool_dict(pool))


@router.put("/{pool_id}", summary="Update DHCP pool")
async def update_dhcp_pool(pool_id: int, payload: DhcpPoolPayload):
    data = await build_pool_data(payload)
    if error := validate_pool_ips(data):
        return Fail(msg=error)
    await CloudDhcpPool.filter(id=pool_id).update(**data)
    return Success(msg="DHCP池已更新", data=await pool_dict(await CloudDhcpPool.get(id=pool_id)))


@router.delete("/{pool_id}", summary="Delete DHCP pool")
async def delete_dhcp_pool(pool_id: int):
    used = await CloudDhcpLease.filter(pool_id=pool_id, status=ACTIVE_LEASE_STATUS).count()
    if used:
        return Fail(msg=f"DHCP池已有 {used} 个占用地址，请先释放后再删除")
    await CloudDhcpPool.filter(id=pool_id).delete()
    return Success(msg="DHCP池已删除")
