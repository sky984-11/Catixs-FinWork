import asyncio
from typing import Any

import httpx
from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.schemas.base import Fail, Success
from app.settings.config import settings

router = APIRouter()

_PDM_RESOURCE_CACHE: list[dict[str, Any]] = []


def pdm_base_url() -> str:
    if not settings.PDM_API_URL:
        raise RuntimeError("PDM API URL is not configured")
    return settings.PDM_API_URL.rstrip("/")


def pdm_api_url(path: str) -> str:
    clean_path = path if path.startswith("/") else f"/{path}"
    return f"{pdm_base_url()}/api2/json{clean_path}"


def error_detail(exc: Exception) -> str:
    detail = str(exc) or repr(exc)
    return f"{type(exc).__name__}: {detail}"


def pdm_auth_header() -> str:
    if settings.PDM_API_TOKEN:
        return settings.PDM_API_TOKEN

    if not settings.PDM_TOKEN_ID or not settings.PDM_TOKEN_SECRET:
        raise RuntimeError("PDM token is not configured")

    return f"PDMAPIToken {settings.PDM_TOKEN_ID}:{settings.PDM_TOKEN_SECRET}"


async def pdm_get(path: str, params: dict[str, Any] | None = None, timeout: float | None = None) -> Any:
    headers = {"Authorization": pdm_auth_header(), "Accept": "application/json"}
    async with httpx.AsyncClient(timeout=timeout or settings.PDM_TIMEOUT, verify=False, trust_env=False) as client:
        response = await client.get(pdm_api_url(path), params=params or {}, headers=headers)
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise RuntimeError(f"PDM API HTTP {response.status_code}: {response.text[:500]}") from exc
        payload = response.json()
    return payload.get("data", [])


def remote_id(remote: Any) -> str:
    if isinstance(remote, str):
        return remote
    if not isinstance(remote, dict):
        return ""
    for key in ("remote", "id", "name"):
        value = remote.get(key)
        if value:
            return str(value)
    return ""


def list_data(data: Any, keys: tuple[str, ...] = ("data", "items", "remotes", "resources", "nodes")) -> list[Any]:
    if isinstance(data, list):
        return data
    if not isinstance(data, dict):
        return []
    for key in keys:
        value = data.get(key)
        if isinstance(value, list):
            return value
        if isinstance(value, dict):
            return list_data(value)

    values: list[Any] = []
    for key, value in data.items():
        if not isinstance(value, dict):
            continue
        row = dict(value)
        row.setdefault("remote", key)
        row.setdefault("id", key)
        row.setdefault("name", key)
        values.append(row)
    if values:
        return values
    return []


def resource_group_id(group: dict[str, Any]) -> str:
    for key in ("remote", "id", "name", "node"):
        value = group.get(key)
        if value:
            return str(value)
    return ""


def canonical_resource_type(value: Any) -> str:
    item_type = str(value or "")
    type_map = {
        "node": "pve-node",
        "qemu": "pve-qemu",
        "vm": "pve-qemu",
        "lxc": "pve-lxc",
        "storage": "pve-storage",
        "network": "pve-network",
    }
    return type_map.get(item_type, item_type)


def normalize_resource_groups(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, dict):
        for key in ("data", "items", "remotes"):
            if key in data:
                return normalize_resource_groups(data[key])
        if isinstance(data.get("resources"), list):
            remote = resource_group_id(data)
            return [{"remote": remote, "resources": data["resources"]}] if remote else []

        groups: list[dict[str, Any]] = []
        for key, value in data.items():
            if isinstance(value, list):
                groups.append({"remote": str(key), "resources": value})
            elif isinstance(value, dict):
                resources = value.get("resources")
                if isinstance(resources, list):
                    groups.append({"remote": str(value.get("remote") or value.get("id") or key), "resources": resources})
                else:
                    row = dict(value)
                    row.setdefault("remote", key)
                    groups.append({"remote": str(row.get("remote") or key), "resources": [row]})
        return groups

    if not isinstance(data, list):
        return []

    if all(isinstance(item, dict) and isinstance(item.get("resources"), list) for item in data):
        groups = []
        for item in data:
            remote = resource_group_id(item)
            if remote:
                groups.append({"remote": remote, "resources": item.get("resources") or [], "error": item.get("error") or ""})
        return groups

    grouped: dict[str, list[dict[str, Any]]] = {}
    for item in data:
        if not isinstance(item, dict):
            continue
        remote = str(item.get("remote") or item.get("id") or item.get("node") or "")
        if not remote:
            continue
        grouped.setdefault(remote, []).append(item)
    return [{"remote": remote, "resources": resources} for remote, resources in grouped.items()]


async def pdm_get_first(paths: list[str], timeout: float | None = None) -> Any:
    last_error: Exception | None = None
    for path in paths:
        try:
            return await pdm_get(path, timeout=timeout)
        except Exception as exc:
            last_error = exc
    if last_error:
        raise last_error
    return []


def configured_remotes() -> list[str]:
    values = []
    for item in (settings.PDM_REMOTES or "").split(","):
        remote = item.strip()
        if remote and remote not in values:
            values.append(remote)
    return values


async def pdm_remote_list() -> list[str]:
    remotes = configured_remotes()
    if remotes:
        return remotes

    data = await pdm_get_first(["/config/remotes", "/pve/remotes", "/remotes"], timeout=3)
    remotes = [remote_id(item) for item in list_data(data)]
    return sorted({remote for remote in remotes if remote})


async def pdm_remote_groups() -> list[dict[str, Any]]:
    remotes = await pdm_remote_list()
    return [{"remote": remote, "resources": [], "error": ""} for remote in remotes]


async def pdm_remote_group_with_timeout(remote: str, timeout: float = 5) -> dict[str, Any]:
    try:
        resources = await asyncio.wait_for(pdm_remote_resources(remote), timeout=timeout)
    except asyncio.TimeoutError:
        return {"remote": remote, "resources": [], "error": "timeout", "queried": False}
    except Exception as exc:
        return {"remote": remote, "resources": [], "error": error_detail(exc), "queried": False}
    return {"remote": remote, "resources": resources, "error": "", "queried": True}


async def pdm_static_remote_groups_with_counts() -> list[dict[str, Any]]:
    remotes = await pdm_remote_list()
    if not remotes:
        return []
    tasks = [pdm_remote_group_with_timeout(remote) for remote in remotes]
    return list(await asyncio.gather(*tasks))


def normalize_remote_items(items: Any, remote: str, item_type: str) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for item in list_data(items):
        if not isinstance(item, dict):
            continue
        row = dict(item)
        row["type"] = item_type
        if item_type in {"pve-qemu", "pve-lxc"}:
            row["remote"] = row.get("remote") or remote
        normalized.append(row)
    return normalized


async def pdm_remote_resources(remote: str) -> list[dict[str, Any]]:
    resources: list[dict[str, Any]] = []
    for path in (
        f"/pve/remotes/{remote}/resources",
        f"/pve/remotes/{remote}/cluster/resources",
        f"/pve/remotes/{remote}/resources/list",
    ):
        try:
            data = pdm_resource_items(await pdm_get(path, timeout=3), remote)
        except Exception:
            continue
        if data:
            resources.extend(data)

    if has_resource_items(resources):
        return resources

    resources = []
    for path, item_type in (
        (f"/pve/remotes/{remote}/nodes", "pve-node"),
        (f"/pve/remotes/{remote}/qemu", "pve-qemu"),
        (f"/pve/remotes/{remote}/lxc", "pve-lxc"),
    ):
        try:
            data = await pdm_get(path, timeout=3)
        except Exception:
            continue
        resources.extend(normalize_remote_items(data, remote, item_type))

    nodes = [item.get("node") for item in resources if item.get("type") == "pve-node" and item.get("node")]
    for node in sorted({str(node) for node in nodes if node}):
        for path, item_type in (
            (f"/pve/remotes/{remote}/nodes/{node}/qemu", "pve-qemu"),
            (f"/pve/remotes/{remote}/nodes/{node}/lxc", "pve-lxc"),
            (f"/pve/remotes/{remote}/nodes/{node}/storage", "pve-storage"),
            (f"/pve/remotes/{remote}/nodes/{node}/network", "pve-network"),
        ):
            try:
                data = await pdm_get(path, timeout=4)
            except Exception:
                continue
            node_items = normalize_remote_items(data, remote, item_type)
            for item in node_items:
                item.setdefault("node", node)
            resources.extend(node_items)
    return resources


def pdm_resource_items(data: Any, remote: str) -> list[dict[str, Any]]:
    groups = normalize_resource_groups(data)
    resources: list[dict[str, Any]] = []
    for group in groups:
        group_remote = str(group.get("remote") or remote)
        for item in group.get("resources") or []:
            if not isinstance(item, dict):
                continue
            row = dict(item)
            row.setdefault("remote", group_remote)
            resources.append(row)
    return resources


def has_resource_items(resources: list[dict[str, Any]]) -> bool:
    for item in resources:
        item_type = item.get("type")
        if item_type in {"pve-node", "pve-qemu", "pve-lxc", "pve-storage", "pve-network"}:
            return True
        if item.get("vmid") or item.get("node") or item.get("storage") or item.get("network"):
            return True
    return False


def cached_remotes() -> list[str]:
    return sorted({str(group.get("remote") or "") for group in _PDM_RESOURCE_CACHE if group.get("remote")})


async def pdm_resources_list() -> list[dict[str, Any]]:
    global _PDM_RESOURCE_CACHE

    try:
        data = normalize_resource_groups(await pdm_get("/resources/list"))
        if data:
            _PDM_RESOURCE_CACHE = data
            return data
        raise RuntimeError("PDM resources list is empty")
    except Exception as primary_error:
        try:
            remotes = await pdm_remote_list()
        except Exception:
            remotes = cached_remotes()

        if not remotes:
            if _PDM_RESOURCE_CACHE:
                return _PDM_RESOURCE_CACHE
            raise primary_error

        groups: list[dict[str, Any]] = []
        for remote in remotes:
            try:
                resources = await pdm_remote_resources(remote)
            except Exception as exc:
                resources = []
                error = str(exc)
            else:
                error = ""
            groups.append({"remote": remote, "resources": resources, "error": error})

        if not groups:
            if _PDM_RESOURCE_CACHE:
                return _PDM_RESOURCE_CACHE
            raise primary_error
        if any(group.get("resources") for group in groups):
            _PDM_RESOURCE_CACHE = groups
        elif _PDM_RESOURCE_CACHE:
            return _PDM_RESOURCE_CACHE
        return groups


async def pdm_live_resources_list(timeout: float = 3) -> list[dict[str, Any]]:
    data = normalize_resource_groups(await pdm_get("/resources/list", timeout=timeout))
    if not data:
        raise RuntimeError("PDM resources list is empty")
    return data


async def pdm_nodes_list() -> list[dict[str, Any]]:
    global _PDM_RESOURCE_CACHE

    try:
        groups = await pdm_live_resources_list()
        _PDM_RESOURCE_CACHE = groups
        return groups
    except Exception:
        if _PDM_RESOURCE_CACHE:
            return _PDM_RESOURCE_CACHE

    groups = await pdm_static_remote_groups_with_counts()
    if groups:
        return groups

    return await pdm_resources_list()


async def pdm_post(path: str, payload: dict[str, Any]) -> Any:
    headers = {"Authorization": pdm_auth_header(), "Accept": "application/json"}
    async with httpx.AsyncClient(timeout=settings.PDM_TIMEOUT, verify=False, trust_env=False) as client:
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
        has_resources = bool(resources)
        queried = bool(group.get("queried")) or has_resources
        vms = [item for item in resources if canonical_resource_type(item.get("type")) in {"pve-qemu", "pve-lxc"}]
        nodes = [item for item in resources if canonical_resource_type(item.get("type")) == "pve-node"]
        online_nodes = [item for item in nodes if item.get("status") == "online"]
        groups.append(
            {
                "id": group.get("remote"),
                "label": group.get("remote"),
                "value": group.get("remote"),
                "remote": group.get("remote"),
                "status": "online" if online_nodes or (queried and not group.get("error")) else "unknown",
                "node_count": len(nodes),
                "online_node_count": len(online_nodes),
                "vm_count": len(vms) if queried else None,
                "error": group.get("error") or "",
                "queried": queried,
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
        "type": canonical_resource_type(item.get("type")),
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
    seen: set[tuple[str, str, int]] = set()
    for group in data:
        remote = str(group.get("remote") or "")
        for item in group.get("resources") or []:
            if canonical_resource_type(item.get("type")) in {"pve-qemu", "pve-lxc"}:
                key = (remote, canonical_resource_type(item.get("type")), int(item.get("vmid") or 0))
                if key in seen:
                    continue
                seen.add(key)
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
                    {
                        str(item.get("node") or "")
                        for item in resources
                        if canonical_resource_type(item.get("type")) == "pve-node" and item.get("node")
                    }
                ),
                "storages": sorted(
                    {
                        str(item.get("storage") or "")
                        for item in resources
                        if canonical_resource_type(item.get("type")) == "pve-storage"
                        and item.get("storage")
                        and item.get("status") != "unknown"
                    }
                ),
                "networks": sorted(
                    {
                        str(item.get("network") or "")
                        for item in resources
                        if canonical_resource_type(item.get("type")) == "pve-network"
                        and item.get("network")
                        and item.get("status") != "unknown"
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
        data = await pdm_nodes_list()
    except Exception as exc:
        return Fail(msg=f"读取 PDM 数据失败: {error_detail(exc)}")
    return Success(data=resource_groups(data))


@router.get("/vms", summary="PDM virtual machine list")
async def list_vms(
    node: str = Query(""),
):
    try:
        if node:
            try:
                resources = await pdm_remote_resources(node)
            except Exception:
                resources = []
            data = [{"remote": node, "resources": resources}]
        else:
            data = await pdm_resources_list()
    except Exception as exc:
        return Fail(msg=f"读取 PDM 数据失败: {error_detail(exc)}")

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
        data = await pdm_resources_list()
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
        return Fail(msg=f"读取 PDM 数据失败: {error_detail(exc)}")

    return Success(data={"upid": upid, "remote": remote, "errors": errors, **task_state(None)})


@router.get("/vms/migration-options", summary="PDM virtual machine migration options")
async def migration_options(
    remote: str = Query(...),
    vmid: int = Query(...),
    type: str = Query("pve-qemu"),
):
    try:
        data = await pdm_resources_list()
        kind = guest_kind(type)
        try:
            wizard = await pdm_get(f"/pve/remotes/{remote}/{kind}/{vmid}/migrate")
        except Exception:
            wizard = {}
    except Exception as exc:
        return Fail(msg=f"读取 PDM 数据失败: {error_detail(exc)}")

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
        data = await pdm_resources_list()
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
        return Fail(msg=f"读取 PDM 数据失败: {error_detail(exc)}")

    return Success(msg="迁移任务已发起", data={"upid": task_id, "source_remote": payload.remote, "target_remote": payload.target})

