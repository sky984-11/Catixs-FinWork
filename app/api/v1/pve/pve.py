from typing import Any

import httpx
from fastapi import APIRouter, Query
from pydantic import BaseModel

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


async def pdm_get(path: str, params: dict[str, Any] | None = None, timeout: float | None = None) -> Any:
    headers = {"Authorization": pdm_auth_header(), "Accept": "application/json"}
    async with httpx.AsyncClient(timeout=timeout or settings.PDM_TIMEOUT, verify=False) as client:
        response = await client.get(pdm_api_url(path), params=params or {}, headers=headers)
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise RuntimeError(f"PDM API HTTP {response.status_code}: {response.text[:500]}") from exc
        payload = response.json()
    return payload.get("data", [])


async def pdm_post(path: str, payload: dict[str, Any]) -> Any:
    headers = {"Authorization": pdm_auth_header(), "Accept": "application/json"}
    async with httpx.AsyncClient(timeout=settings.PDM_TIMEOUT, verify=False) as client:
        response = await client.post(pdm_api_url(path), json=payload, headers=headers)
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise RuntimeError(f"PDM API HTTP {response.status_code}: {response.text[:500]}") from exc
        data = response.json()
    return data.get("data")


class VMMigrateRequest(BaseModel):
    remote: str
    vmid: int
    type: str = "pve-qemu"
    target: str
    target_vmid: int | None = None
    target_storage: str
    target_bridge: str
    delete_source: bool = True
    online: bool = False
    bwlimit: int | None = None
    node: str | None = None
    target_endpoint: str | None = None


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


def guest_kind(vm_type: str | None) -> str:
    return "lxc" if vm_type == "pve-lxc" else "qemu"


def remote_resources(data: list[dict[str, Any]], remote: str) -> dict[str, Any]:
    for group in data:
        if str(group.get("remote") or "") == remote:
            resources = group.get("resources") or []
            return {
                "remote": remote,
                "nodes": sorted(
                    {str(item.get("node") or "") for item in resources if item.get("type") == "pve-node" and item.get("node")}
                ),
                "storages": sorted(
                    {
                        str(item.get("storage") or "")
                        for item in resources
                        if item.get("type") == "pve-storage" and item.get("storage") and item.get("status") != "unknown"
                    }
                ),
                "networks": sorted(
                    {
                        str(item.get("network") or "")
                        for item in resources
                        if item.get("type") == "pve-network" and item.get("network") and item.get("status") != "unknown"
                    }
                ),
                "endpoints": [],
            }
    return {"remote": remote, "nodes": [], "storages": [], "networks": [], "endpoints": []}


async def remote_migration_resources(data: list[dict[str, Any]], remote: str) -> dict[str, Any]:
    resources = remote_resources(data, remote)
    bridges: set[str] = set()
    endpoints: set[str] = set()

    for node in resources["nodes"]:
        try:
            networks = await pdm_get(f"/pve/remotes/{remote}/nodes/{node}/network")
        except Exception:
            networks = []
        for network in networks:
            if network.get("type") == "bridge" and network.get("iface"):
                bridges.add(str(network["iface"]))
                if network.get("address"):
                    endpoints.add(str(network["address"]))

    if bridges:
        resources["networks"] = sorted(bridges)
    resources["endpoints"] = sorted(endpoints)
    return resources


def mapped_values(sources: list[str], target: str) -> list[str]:
    if not target:
        return []
    if not sources:
        return [target]
    return [f"{source}:{target}" for source in sources]


def task_state(task: dict[str, Any] | None) -> dict[str, Any]:
    if not task:
        return {"state": "unknown", "finished": False, "success": False}

    finished = bool(task.get("endtime"))
    status = str(task.get("status") or "")
    if not finished:
        state = "running"
        success = False
    elif status == "OK":
        state = "success"
        success = True
    elif status.startswith("WARNINGS"):
        state = "warning"
        success = True
    else:
        state = "error"
        success = False

    return {"state": state, "finished": finished, "success": success}


def task_upid_candidates(upid: str) -> set[str]:
    values = {upid}
    if "!" in upid:
        values.add(upid.split("!", 1)[1])
    if upid.startswith("pve:"):
        parts = upid.split("!", 1)
        if len(parts) == 2:
            values.add(parts[1])
    return {value for value in values if value}


def task_upid_remote(upid: str) -> str:
    if not upid.startswith("pve:") or "!" not in upid:
        return ""
    remote_part = upid.split("!", 1)[0]
    return remote_part.removeprefix("pve:")


def same_task(upid: str, task_upid: str | None) -> bool:
    if not task_upid:
        return False
    candidates = task_upid_candidates(upid)
    if task_upid in candidates:
        return True
    return any(candidate.endswith(task_upid) or task_upid.endswith(candidate) for candidate in candidates)


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
):
    try:
        data = await pdm_get("/resources/list")
    except Exception as exc:
        return Fail(msg=f"读取 PDM 虚拟机失败: {exc}")

    vms = all_vms(data)
    if node:
        vms = [vm for vm in vms if vm.get("remote") == node]
    vms.sort(key=lambda row: (str(row.get("remote") or ""), str(row.get("node") or ""), int(row.get("vmid") or 0)))
    summary = {
        "total": len(vms),
        "running": len([vm for vm in vms if vm.get("status") == "running"]),
        "stopped": len([vm for vm in vms if vm.get("status") == "stopped"]),
    }
    return Success(data={"items": vms, "summary": summary})


@router.get("/tasks/status", summary="PDM remote task status")
async def task_status(
    upid: str = Query(...),
    remote: str = Query(""),
):
    errors: list[str] = []
    try:
        data = await pdm_get("/resources/list")
        all_remotes = [str(group.get("remote") or "") for group in data if group.get("remote")]
        preferred_remotes = [remote, task_upid_remote(upid)]
        remotes = []
        for remote_id in [*preferred_remotes, *all_remotes]:
            if remote_id and remote_id not in remotes:
                remotes.append(remote_id)

        for remote_id in remotes:
            try:
                tasks = await pdm_get(f"/pve/remotes/{remote_id}/tasks", timeout=4)
            except Exception as exc:
                errors.append(f"{remote_id}: {exc}")
                continue
            for task in tasks:
                if same_task(upid, task.get("upid")):
                    return Success(data={**task, **task_state(task), "remote": remote_id})
    except Exception as exc:
        return Fail(msg=f"读取 PDM 任务状态失败: {exc}")

    return Success(data={"upid": upid, "remote": remote, "errors": errors, **task_state(None)})


@router.get("/vms/migration-options", summary="PDM virtual machine migration options")
async def migration_options(
    remote: str = Query(...),
    vmid: int = Query(...),
    type: str = Query("pve-qemu"),
):
    try:
        data = await pdm_get("/resources/list")
        kind = guest_kind(type)
        try:
            wizard = await pdm_get(f"/pve/remotes/{remote}/{kind}/{vmid}/migrate")
        except Exception:
            wizard = {}
    except Exception as exc:
        return Fail(msg=f"读取 PDM 迁移选项失败: {exc}")

    remotes = []
    for group in data:
        remote_id = str(group.get("remote") or "")
        if not remote_id:
            continue
        remotes.append(await remote_migration_resources(data, remote_id))
    remotes.sort(key=lambda row: row["remote"])

    return Success(
        data={
            "source": await remote_migration_resources(data, remote),
            "remotes": remotes,
            "wizard": wizard,
        }
    )


@router.post("/vms/migrate", summary="PDM virtual machine remote migration")
async def migrate_vm(payload: VMMigrateRequest):
    try:
        data = await pdm_get("/resources/list")
        source = await remote_migration_resources(data, payload.remote)
        kind = guest_kind(payload.type)
        request_payload: dict[str, Any] = {
            "remote": payload.remote,
            "vmid": payload.vmid,
            "target": payload.target,
            "target-storage": mapped_values(source["storages"], payload.target_storage),
            "target-bridge": mapped_values(source["networks"], payload.target_bridge),
            "delete": payload.delete_source,
            "online": payload.online,
        }
        if payload.target_vmid:
            request_payload["target-vmid"] = payload.target_vmid
        if payload.bwlimit is not None:
            request_payload["bwlimit"] = payload.bwlimit
        if payload.node:
            request_payload["node"] = payload.node
        if payload.target_endpoint:
            request_payload["target-endpoint"] = payload.target_endpoint

        task_id = await pdm_post(f"/pve/remotes/{payload.remote}/{kind}/{payload.vmid}/remote-migrate", request_payload)
    except Exception as exc:
        return Fail(msg=f"发起 PDM 迁移失败: {exc}")

    return Success(msg="迁移任务已发起", data={"upid": task_id, "source_remote": payload.remote, "target_remote": payload.target})
