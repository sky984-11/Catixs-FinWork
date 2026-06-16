from typing import Any

import httpx
from fastapi import APIRouter, Query

from app.schemas.base import Fail, Success
from app.settings.config import settings

router = APIRouter()


def pdm_base_url() -> str:
    if not settings.PDM_API_URL:
        raise RuntimeError("PDM API URL is not configured")
    return settings.PDM_API_URL.rstrip("/")


def pdm_api_url(path: str) -> str:
    clean_path = path if path.startswith("/") else f"/{path}"
    return f"{pdm_base_url()}/api2/json{clean_path}"


def pdm_auth_header() -> str:
    if settings.PDM_API_TOKEN:
        return settings.PDM_API_TOKEN

    if not settings.PDM_TOKEN_ID or not settings.PDM_TOKEN_SECRET:
        raise RuntimeError("PDM token is not configured")

    return f"PDMAPIToken {settings.PDM_TOKEN_ID}:{settings.PDM_TOKEN_SECRET}"


async def pdm_get(path: str, params: dict[str, Any] | None = None) -> Any:
    headers = {"Authorization": pdm_auth_header(), "Accept": "application/json"}
    async with httpx.AsyncClient(timeout=settings.PDM_TIMEOUT, verify=False) as client:
        response = await client.get(pdm_api_url(path), params=params or {}, headers=headers)
        response.raise_for_status()
        payload = response.json()
    return payload.get("data", [])


def percent(value: Any) -> float:
    try:
        number = float(value or 0)
    except (TypeError, ValueError):
        return 0
    if number <= 1:
        return round(number * 100, 2)
    return round(number, 2)


def resource_groups(data: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: list[dict[str, Any]] = []
    for group in data:
        resources = group.get("resources") or []
        vms = [item for item in resources if item.get("type") in {"pve-qemu", "pve-lxc"}]
        nodes = [item for item in resources if item.get("type") == "pve-node"]
        online_nodes = [item for item in nodes if item.get("status") == "online"]
        groups.append(
            {
                "id": group.get("remote"),
                "label": group.get("remote"),
                "value": group.get("remote"),
                "remote": group.get("remote"),
                "status": "online" if online_nodes else "unknown",
                "node_count": len(nodes),
                "online_node_count": len(online_nodes),
                "vm_count": len(vms),
                "cpu": percent(sum(float(item.get("cpu") or 0) for item in nodes) / len(nodes)) if nodes else 0,
            }
        )
    groups.sort(key=lambda row: str(row.get("label") or ""))
    return groups


def normalize_vm(item: dict[str, Any], remote: str) -> dict[str, Any]:
    maxmem = int(item.get("maxmem") or 0)
    mem = int(item.get("mem") or 0)
    maxdisk = int(item.get("maxdisk") or 0)
    disk = int(item.get("disk") or 0)
    maxcpu = int(float(item.get("maxcpu") or 0))
    return {
        "id": item.get("id") or f"remote/{remote}/guest/{item.get('vmid')}",
        "remote": remote,
        "vmid": item.get("vmid"),
        "name": item.get("name") or item.get("id") or "-",
        "node": item.get("node") or "",
        "type": item.get("type") or "",
        "status": item.get("status") or "unknown",
        "cpu": percent(item.get("cpu")),
        "maxcpu": maxcpu,
        "mem": mem,
        "maxmem": maxmem,
        "mem_percent": round(mem / maxmem * 100, 2) if maxmem else 0,
        "disk": disk,
        "maxdisk": maxdisk,
        "disk_percent": round(disk / maxdisk * 100, 2) if maxdisk else 0,
        "uptime": int(item.get("uptime") or 0),
        "template": bool(item.get("template")),
        "tags": item.get("tags") or [],
        "pool": item.get("pool") or "",
        "remark": "",
    }


def all_vms(data: list[dict[str, Any]]) -> list[dict[str, Any]]:
    vms: list[dict[str, Any]] = []
    for group in data:
        remote = str(group.get("remote") or "")
        for item in group.get("resources") or []:
            if item.get("type") in {"pve-qemu", "pve-lxc"}:
                vms.append(normalize_vm(item, remote))
    return vms


def matches_keyword(vm: dict[str, Any], keyword: str) -> bool:
    text = keyword.strip().lower()
    if not text:
        return True
    values = [vm.get("name"), vm.get("vmid"), vm.get("remote"), vm.get("node"), vm.get("type"), vm.get("status")]
    return any(text in str(value or "").lower() for value in values)


@router.get("/nodes", summary="PDM remote list")
async def list_nodes():
    try:
        data = await pdm_get("/resources/list")
    except Exception as exc:
        return Fail(msg=f"读取 PDM 地区列表失败: {exc}")
    return Success(data=resource_groups(data))


@router.get("/vms", summary="PDM virtual machine list")
async def list_vms(
    node: str = Query(""),
    keyword: str = Query(""),
    status: str = Query(""),
):
    try:
        data = await pdm_get("/resources/list")
    except Exception as exc:
        return Fail(msg=f"读取 PDM 虚拟机失败: {exc}")

    vms = all_vms(data)
    if node:
        vms = [vm for vm in vms if vm.get("remote") == node]
    if status:
        vms = [vm for vm in vms if vm.get("status") == status]
    vms = [vm for vm in vms if matches_keyword(vm, keyword)]
    vms.sort(key=lambda row: (str(row.get("remote") or ""), str(row.get("node") or ""), int(row.get("vmid") or 0)))
    summary = {
        "total": len(vms),
        "running": len([vm for vm in vms if vm.get("status") == "running"]),
        "stopped": len([vm for vm in vms if vm.get("status") == "stopped"]),
    }
    return Success(data={"items": vms, "summary": summary})
