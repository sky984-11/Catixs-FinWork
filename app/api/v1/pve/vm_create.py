import asyncio
import ipaddress
import shlex
import time
from uuid import uuid4
from typing import Any

import httpx
from fastapi import APIRouter, Query
from loguru import logger
from pydantic import BaseModel, Field

from app.schemas.base import Fail, Success
from app.settings.config import settings
from app.api.v1.pve.dhcp import release_dhcp_lease, reserve_dhcp_lease
from app.models.asset import CloudDhcpLease, PveVmMetadata
from app.models.customer_center import CrmCustomer

router = APIRouter()


class VMNetworkConfig(BaseModel):
    mode: str = Field("dhcp", description="dhcp or static")
    ip: str | None = None
    mask: str | None = None
    dns: str | None = None
    gw: str | None = None
    vlan: int | None = None
    dhcp_pool_id: int | None = None
    rate_limit: float | None = None


class VMCreateRequest(BaseModel):
    region: str
    storage: str
    vm_name: str
    description: str | None = ""
    os_type: str
    os_version: str
    cpu_cores: int
    memory_gb: int
    disk_gb: int
    password: str
    customer_id: int | None = None
    customer_name: str | None = None
    network: VMNetworkConfig
    expire_at: Any | None = None


def pdm_api_url(path: str) -> str:
    clean_path = path if path.startswith("/") else f"/{path}"
    return f"{settings.PDM_API_URL.rstrip('/')}/api2/json{clean_path}"


def pdm_auth_header() -> str:
    if settings.PDM_API_TOKEN:
        return settings.PDM_API_TOKEN
    return f"PDMAPIToken {settings.PDM_TOKEN_ID}:{settings.PDM_TOKEN_SECRET}"


async def pdm_get(path: str, timeout: float | None = None) -> Any:
    headers = {"Authorization": pdm_auth_header(), "Accept": "application/json"}
    async with httpx.AsyncClient(timeout=timeout or settings.PDM_TIMEOUT, verify=False, trust_env=False) as client:
        response = await client.get(pdm_api_url(path), headers=headers)
        response.raise_for_status()
        payload = response.json()
    return payload.get("data", [])


def remote_nodes(data: list[dict[str, Any]], remote: str) -> list[str]:
    for group in data:
        if str(group.get("remote") or "") != remote:
            continue
        resources = group.get("resources") or []
        return sorted(
            {str(item.get("node") or "") for item in resources if item.get("type") == "pve-node" and item.get("node")}
        )
    return []


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
    return []


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
        return []

    if not isinstance(data, list):
        return []

    if all(isinstance(item, dict) and isinstance(item.get("resources"), list) for item in data):
        return [
            {"remote": resource_group_id(item), "resources": item.get("resources") or []}
            for item in data
            if resource_group_id(item)
        ]

    grouped: dict[str, list[dict[str, Any]]] = {}
    for item in data:
        if not isinstance(item, dict):
            continue
        remote = str(item.get("remote") or item.get("id") or item.get("node") or "")
        if remote:
            grouped.setdefault(remote, []).append(item)
    return [{"remote": remote, "resources": resources} for remote, resources in grouped.items()]


def parse_remote_node_entry(value: Any) -> dict[str, str]:
    text = str(value or "").strip()
    if not text:
        return {"host": "", "fingerprint": ""}
    parts = [part.strip() for part in text.split(",") if part.strip()]
    host = parts[0] if parts else text
    fingerprint = ""
    for part in parts[1:]:
        if part.startswith("fingerprint="):
            fingerprint = part.split("=", 1)[1].strip()
            break
    return {"host": host, "fingerprint": fingerprint}


def remote_config_address(remote: Any) -> str:
    if not isinstance(remote, dict):
        return ""
    for key in ("node", "address", "ip", "host", "hostname", "endpoint", "server"):
        value = remote.get(key)
        if value:
            return str(value)
    nodes = remote.get("nodes")
    if isinstance(nodes, list) and nodes:
        return parse_remote_node_entry(nodes[0]).get("host", "")
    return ""


async def pdm_remote_configs() -> list[dict[str, Any]]:
    for path in ("/remotes/remote", "/config/remotes", "/pve/remotes", "/remotes"):
        try:
            data = await pdm_get(path, timeout=3)
        except Exception:
            continue
        configs = [item for item in list_data(data) if isinstance(item, dict)]
        if configs:
            return configs
    return []


def network_address_from_items(items: list[dict[str, Any]]) -> str:
    candidates: list[tuple[int, str]] = []
    for item in items:
        if canonical_resource_type(item.get("type")) not in {"pve-network", "network"}:
            continue
        address = item.get("address")
        if not address or not is_ip_address(str(address)):
            continue
        iface = str(item.get("iface") or item.get("name") or "")
        priority = 0 if iface == "vmbr10" else 1
        candidates.append((priority, strip_cidr(str(address))))
    if not candidates:
        return ""
    candidates.sort(key=lambda item: item[0])
    return candidates[0][1]


async def resolve_remote_network_address(remote: str, node: str = "", resources: list[dict[str, Any]] | None = None) -> str:
    address = "" if node else network_address_from_items(resources or [])
    if address:
        return address

    nodes = [node] if node else remote_nodes([{"remote": remote, "resources": resources or []}], remote)
    candidates: list[tuple[int, str]] = []
    for node_name in nodes:
        try:
            networks = await pdm_get(f"/pve/remotes/{remote}/nodes/{node_name}/network", timeout=4)
        except Exception:
            continue
        for network in list_data(networks):
            if not isinstance(network, dict):
                continue
            if network.get("type") != "bridge" or not network.get("address"):
                continue
            address = str(network.get("address") or "")
            if not is_ip_address(address):
                continue
            iface = str(network.get("iface") or "")
            priority = 0 if iface == "vmbr10" else 1
            candidates.append((priority, strip_cidr(address)))
    if not candidates:
        return ""
    candidates.sort(key=lambda item: item[0])
    return candidates[0][1]


def strip_cidr(address: str) -> str:
    return address.split("/", 1)[0].strip()


def is_ip_address(value: str) -> bool:
    host = strip_cidr(value)
    host = host.rsplit(":", 1)[0] if ":" in host and host.count(":") == 1 else host
    try:
        ipaddress.ip_address(host)
    except ValueError:
        return False
    return True


async def resolve_create_host(remote_or_host: str) -> str:
    value = str(remote_or_host or "").strip()
    if not value:
        return value

    if is_ip_address(value):
        return strip_cidr(value)

    try:
        for config in await pdm_remote_configs():
            item_id = remote_id(config)
            address = strip_cidr(remote_config_address(config))
            nodes = config.get("nodes") if isinstance(config.get("nodes"), list) else []
            node_hosts = {parse_remote_node_entry(node).get("host", "") for node in nodes}
            if value == item_id and address and is_ip_address(address):
                return address
            if value == address and is_ip_address(address):
                return address
            if value in node_hosts and address and is_ip_address(address):
                return address
    except Exception:
        pass

    try:
        data = normalize_resource_groups(await pdm_get("/resources/list", timeout=3))
        for group in data:
            remote = str(group.get("remote") or "")
            resources = [item for item in group.get("resources") or [] if isinstance(item, dict)]
            if remote == value:
                address = await resolve_remote_network_address(remote, resources=resources)
                if address:
                    return address
            for item in resources:
                if canonical_resource_type(item.get("type")) != "pve-node":
                    continue
                if str(item.get("node") or "") != value:
                    continue
                address = await resolve_remote_network_address(remote, value, resources)
                if address:
                    return address
                for key in ("ip", "address", "host", "hostname", "endpoint", "server"):
                    fallback = str(item.get(key) or "").strip()
                    if fallback and is_ip_address(fallback):
                        return strip_cidr(fallback)
    except Exception:
        pass

    return value


def ssh_execute(host: str, command: str) -> tuple[int, str, str]:
    try:
        import paramiko
    except ImportError as exc:
        return -1, "", f"paramiko is not installed: {exc}"

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(
            host,
            username=settings.PVE_CREATE_SSH_USER,
            password=settings.PVE_CREATE_SSH_PASSWORD,
            timeout=settings.PVE_CREATE_SSH_TIMEOUT,
        )
        _, stdout, stderr = client.exec_command(f"cd /root && {command}")
        exit_status = stdout.channel.recv_exit_status()
        output = stdout.read().decode("utf-8", errors="replace")
        error = stderr.read().decode("utf-8", errors="replace")
        return exit_status, output, error
    except Exception as exc:
        return -1, "", str(exc)
    finally:
        client.close()


def ssh_submit_background(host: str, command: str) -> tuple[int, str, str]:
    try:
        import paramiko
    except ImportError as exc:
        return -1, "", f"paramiko is not installed: {exc}"

    task_id = f"{int(time.time())}-{uuid4().hex[:8]}"
    log_file = f"/tmp/finwork-create-vm-{task_id}.log"
    pid_file = f"/tmp/finwork-create-vm-{task_id}.pid"
    background_command = (
        "set -u; "
        "cd /root || exit 1; "
        "if [ ! -x ./create-vm.sh ]; then echo './create-vm.sh not found or not executable' >&2; exit 127; fi; "
        f"nohup {command} > {shlex.quote(log_file)} 2>&1 < /dev/null & "
        f"pid=$!; echo $pid > {shlex.quote(pid_file)}; "
        "sleep 1; "
        "if kill -0 $pid 2>/dev/null; then "
        f"echo submitted pid=$pid log={shlex.quote(log_file)}; "
        "else "
        "wait $pid; status=$?; "
        f"echo immediate_exit status=$status log={shlex.quote(log_file)}; "
        f"tail -n 80 {shlex.quote(log_file)} 2>/dev/null; "
        "exit $status; "
        "fi"
    )

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(
            host,
            username=settings.PVE_CREATE_SSH_USER,
            password=settings.PVE_CREATE_SSH_PASSWORD,
            timeout=settings.PVE_CREATE_SSH_TIMEOUT,
        )
        _, stdout, stderr = client.exec_command(background_command, timeout=5)
        channel = stdout.channel
        time.sleep(0.8)

        if channel.exit_status_ready():
            exit_status = channel.recv_exit_status()
            output = stdout.read().decode("utf-8", errors="replace").strip()
            error = stderr.read().decode("utf-8", errors="replace").strip()
            if exit_status != 0:
                return exit_status, output, error or "提交创建任务失败"
            return 0, output or f"log={log_file}", ""

        return 0, f"log={log_file}", ""
    except Exception as exc:
        return -1, "", str(exc)
    finally:
        client.close()


async def run_remote_script(host: str, command: str) -> tuple[int, str, str]:
    return await asyncio.to_thread(ssh_execute, host, command)


async def submit_remote_script(host: str, command: str) -> tuple[int, str, str]:
    try:
        return await asyncio.wait_for(asyncio.to_thread(ssh_submit_background, host, command), timeout=6)
    except asyncio.TimeoutError:
        return 0, "创建任务可能已提交，远端 SSH 未及时关闭通道", ""


async def verify_vm_exists(host: str, vm_name: str, attempts: int = 12, delay: float = 5) -> bool:
    quoted_name = shlex.quote(vm_name)
    command = f"qm list | awk 'NR > 1 {{print $2}}' | grep -Fx -- {quoted_name}"
    for _ in range(attempts):
        exit_status, _stdout, _stderr = await run_remote_script(host, command)
        if exit_status == 0:
            return True
        await asyncio.sleep(delay)
    return False


async def find_vm_by_name(host: str, vm_name: str, attempts: int = 12, delay: float = 5) -> dict[str, Any] | None:
    quoted_name = shlex.quote(vm_name)
    command = f"qm list | awk -v name={quoted_name} 'NR > 1 && $2 == name {{print $1\" \"$2}}'"
    for _ in range(attempts):
        exit_status, stdout, _stderr = await run_remote_script(host, command)
        if exit_status == 0 and stdout.strip():
            parts = stdout.strip().split()
            if parts and parts[0].isdigit():
                return {"vmid": int(parts[0]), "name": " ".join(parts[1:])}
        await asyncio.sleep(delay)
    return None


async def selectable_customer(customer_id: int | None) -> CrmCustomer | None:
    if not customer_id:
        return None
    return await CrmCustomer.filter(id=customer_id, status=True).exclude(lifecycle="terminated").first()


def bridge_for_vm_ip(ip_value: str | None) -> str:
    text = str(ip_value or "").split("/", 1)[0].strip()
    try:
        ip = ipaddress.ip_address(text)
    except ValueError:
        return "vmbr20"
    return "vmbr10" if ip in ipaddress.ip_network("10.0.0.0/8") else "vmbr20"


async def remote_key_for_host(host: str, fallback: str) -> str:
    host_ip = strip_cidr(host)
    if not host_ip:
        return fallback
    for item in await pdm_remote_configs():
        remote = remote_id(item)
        if not remote:
            continue
        addresses = {
            strip_cidr(remote_config_address(item)),
            strip_cidr(str(item.get("address") or "")),
            strip_cidr(str(item.get("ip") or "")),
            strip_cidr(str(item.get("host") or "")),
            strip_cidr(str(item.get("hostname") or "")),
            strip_cidr(str(item.get("endpoint") or "")),
            strip_cidr(str(item.get("server") or "")),
        }
        nodes = item.get("nodes")
        if isinstance(nodes, list):
            addresses.update(strip_cidr(parse_remote_node_entry(node).get("host")) for node in nodes)
        if host_ip in {address for address in addresses if address}:
            return remote
    return fallback


def shell_join(parts: list[Any]) -> str:
    return " ".join(shlex.quote(str(part)) for part in parts if part is not None)


def create_vm_command(payload: VMCreateRequest) -> str:
    ram_mb = payload.memory_gb * 1024
    rate_limit = payload.network.rate_limit
    args: list[Any] = [
        "./create-vm.sh",
        "--ostype",
        payload.os_type,
        "--version",
        payload.os_version,
        "--name",
        payload.vm_name,
        "--cores",
        payload.cpu_cores,
        "--ram",
        ram_mb,
        "--disk",
        f"{payload.disk_gb}G",
        "--storage",
        payload.storage,
    ]

    if payload.network.mode == "dhcp":
        args.extend(["--bridge", "vmbr10"])
    else:
        bridge = bridge_for_vm_ip(payload.network.ip)
        args.extend(["--bridge", bridge])
        if payload.network.vlan and bridge != "vmbr10":
            args.extend(["--vlan", payload.network.vlan])

    if rate_limit:
        args.extend(["--rate", rate_limit])

    args.extend(["--password", payload.password, "--description", payload.description or ""])

    if payload.network.mode != "dhcp":
        args.extend(["--ip", payload.network.ip or "", "--gw", payload.network.gw or "", "--dns", payload.network.dns or ""])

    args.extend(["--start", "yes"])
    return shell_join(args)


def parse_storage_output(stdout: str) -> list[dict[str, Any]]:
    storages: list[dict[str, Any]] = []
    for line in stdout.splitlines()[1:]:
        parts = line.split()
        if len(parts) < 2:
            continue
        name = parts[0]
        storage_type = parts[1]
        enabled = parts[-1] if parts else "1"
        if enabled == "0":
            continue
        storages.append({"label": f"{name} ({storage_type})", "value": name, "type": storage_type})
    return storages


def storage_options_from_resources(resources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    storages: dict[str, dict[str, Any]] = {}
    for item in resources:
        if canonical_resource_type(item.get("type")) != "pve-storage":
            continue
        name = str(item.get("storage") or item.get("name") or "").strip()
        if not name or item.get("status") == "unknown":
            continue
        storage_type = str(item.get("plugintype") or item.get("storage_type") or item.get("content") or "").strip()
        label = f"{name} ({storage_type})" if storage_type else name
        storages[name] = {"label": label, "value": name, "type": storage_type}
    return sorted(storages.values(), key=lambda item: str(item["value"]))


async def pdm_storage_options(remote_or_node: str) -> list[dict[str, Any]]:
    value = str(remote_or_node or "").strip()
    if not value:
        return []
    try:
        data = normalize_resource_groups(await pdm_get("/resources/list", timeout=3))
    except Exception:
        return []

    for group in data:
        remote = str(group.get("remote") or "")
        resources = [item for item in group.get("resources") or [] if isinstance(item, dict)]
        if remote == value:
            return storage_options_from_resources(resources)
        if any(canonical_resource_type(item.get("type")) == "pve-node" and str(item.get("node") or "") == value for item in resources):
            return storage_options_from_resources(resources)
    return []


def os_options() -> list[dict[str, Any]]:
    return [
        {
            "label": "Debian",
            "value": "debian",
            "children": [
                {"label": "13 (trixie)", "value": "13"},
                {"label": "12 (Bookworm)", "value": "12"},
                {"label": "11 (Bullseye)", "value": "11"},
            ],
        },
        {
            "label": "Ubuntu",
            "value": "ubuntu",
            "children": [
                {"label": "25.04 LTS", "value": "25.04"},
                {"label": "24.04 LTS", "value": "24.04"},
                {"label": "22.04 LTS", "value": "22.04"},
                {"label": "20.04 LTS", "value": "20.04"},
            ],
        },
        {
            "label": "CentOS",
            "value": "centos",
            "children": [{"label": "7.9", "value": "7.9"}],
        },
    ]


def fail_message(prefix: str, stdout: str, stderr: str) -> str:
    detail = (stderr or stdout or "远端脚本没有返回错误输出").strip()
    return f"{prefix}: {detail}"


@router.get("/vms/create-options", summary="PVE virtual machine create options")
async def create_options(node_ip: str = Query(..., description="PVE node IP or PDM remote name")):
    try:
        ssh_host = await resolve_create_host(node_ip)
        exit_status, stdout, stderr = await run_remote_script(ssh_host, "pvesm status --content images")
        if exit_status != 0:
            storages = await pdm_storage_options(node_ip)
            if storages:
                return Success(data={"storages": storages, "os_options": os_options(), "ssh_host": ssh_host})
            return Fail(msg=fail_message("读取 PVE 存储列表失败", stdout, stderr))
        return Success(data={"storages": parse_storage_output(stdout), "os_options": os_options(), "ssh_host": ssh_host})
    except Exception as exc:
        return Fail(msg=f"读取 PVE 创建选项失败: {exc}")


@router.post("/vms/create", summary="PVE virtual machine create")
async def create_vm(payload: VMCreateRequest):
    ssh_host = payload.region
    stdout = ""
    reserved_lease_id = None
    customer = await selectable_customer(payload.customer_id)
    if payload.customer_id and not customer:
        return Fail(msg="所选客户不存在或已终止")
    if customer:
        payload.customer_name = customer.legal_name or customer.name
    try:
        if payload.network.mode == "dhcp" and payload.network.dhcp_pool_id:
            lease = await reserve_dhcp_lease(
                payload.network.dhcp_pool_id,
                os_type=payload.os_type,
                os_version=payload.os_version,
                cpu_cores=payload.cpu_cores,
                memory_gb=payload.memory_gb,
                disk_gb=payload.disk_gb,
                expiry_date=payload.expire_at,
                remote=payload.region,
                remark=payload.description or "",
            )
            if not lease:
                return Fail(msg="所选 DHCP 池没有可用地址")
            reserved_lease_id = lease.id
            payload.network.mode = "static"
            payload.network.ip = f"{lease.ip}/{str(lease.cidr).split('/', 1)[1]}" if "/" in str(lease.cidr) else lease.ip
            payload.network.gw = str(lease.gateway).split("/", 1)[0]
            payload.network.dns = payload.network.dns or "8.8.8.8"
            payload.network.vlan = lease.vlan
        ssh_host = await resolve_create_host(payload.region)
        command = create_vm_command(payload)
        logger.info(
            "submit PVE VM create: region={} ssh_host={} vm_name={} storage={} os={}/{}",
            payload.region,
            ssh_host,
            payload.vm_name,
            payload.storage,
            payload.os_type,
            payload.os_version,
        )
        exit_status, stdout, stderr = await run_remote_script(ssh_host, command)
        logger.info(
            "PVE VM create submit result: vm_name={} ssh_host={} exit_status={} stdout={} stderr={}",
            payload.vm_name,
            ssh_host,
            exit_status,
            stdout,
            stderr,
        )
        if exit_status != 0:
            await release_dhcp_lease(reserved_lease_id)
            return Fail(msg=fail_message("创建虚拟机失败", stdout, stderr))
        created_vm = await find_vm_by_name(ssh_host, payload.vm_name)
        if not created_vm:
            await release_dhcp_lease(reserved_lease_id)
            return Fail(
                msg=fail_message(
                    "创建虚拟机失败，目标 PVE 节点未发现新虚拟机",
                    stdout,
                    f"已在 {ssh_host} 执行创建脚本，但 qm list 未找到名称为 {payload.vm_name} 的虚拟机",
                )
            )
        created_vmid = created_vm["vmid"]
        metadata_remote = await remote_key_for_host(ssh_host, payload.region)
        if reserved_lease_id:
            await CloudDhcpLease.filter(id=reserved_lease_id).update(remote=metadata_remote, vmid=created_vmid)
        if customer:
            await PveVmMetadata.update_or_create(
                remote=metadata_remote,
                vmid=created_vmid,
                defaults={
                    "vm_name": payload.vm_name,
                    "customer_id": customer.id,
                    "customer_name": customer.legal_name or customer.name,
                },
            )
    except Exception as exc:
        await release_dhcp_lease(reserved_lease_id)
        logger.exception("submit PVE VM create failed: region={} vm_name={}", payload.region, payload.vm_name)
        return Fail(msg=f"创建虚拟机失败: {exc}")

    return Success(
        msg="虚拟机已创建",
        data={
            "region": payload.region,
            "ssh_host": ssh_host,
            "remote": metadata_remote,
            "vmid": created_vmid,
            "vm_name": payload.vm_name,
            "task": stdout,
            "config": payload.model_dump(),
        },
    )
