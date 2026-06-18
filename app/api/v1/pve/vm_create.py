import asyncio
import ipaddress
import shlex
import time
from uuid import uuid4
from typing import Any

import httpx
from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from app.schemas.base import Fail, Success
from app.settings.config import settings

router = APIRouter()


class VMNetworkConfig(BaseModel):
    mode: str = Field("dhcp", description="dhcp or static")
    ip: str | None = None
    mask: str | None = None
    dns: str | None = None
    gw: str | None = None
    vlan: int | None = None
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
    network: VMNetworkConfig


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


def strip_cidr(address: str) -> str:
    return address.split("/", 1)[0].strip()


def is_ip_address(value: str) -> bool:
    host = value.rsplit(":", 1)[0] if ":" in value and value.count(":") == 1 else value
    try:
        ipaddress.ip_address(host)
    except ValueError:
        return False
    return True


async def resolve_create_host(remote_or_host: str) -> str:
    if not remote_or_host:
        return remote_or_host

    if is_ip_address(remote_or_host):
        return remote_or_host

    try:
        data = await pdm_get("/resources/list", timeout=3)
        candidates: list[tuple[int, str]] = []
        for node in remote_nodes(data, remote_or_host):
            try:
                networks = await pdm_get(f"/pve/remotes/{remote_or_host}/nodes/{node}/network", timeout=4)
            except Exception:
                continue
            for network in networks:
                if network.get("type") != "bridge" or not network.get("address"):
                    continue
                iface = str(network.get("iface") or "")
                priority = 0 if iface == "vmbr10" else 1
                candidates.append((priority, strip_cidr(str(network["address"]))))
        if candidates:
            candidates.sort(key=lambda item: item[0])
            return candidates[0][1]
    except Exception:
        pass

    return remote_or_host


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
    background_command = (
        "cd /root && "
        "test -f ./create-vm.sh && "
        f"nohup {command} > {shlex.quote(log_file)} 2>&1 < /dev/null &"
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
            error = stderr.read().decode("utf-8", errors="replace").strip()
            if exit_status != 0:
                return exit_status, "", error or "提交创建任务失败"

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
        bridge = "vmbr10" if payload.network.vlan == 10 else "vmbr20"
        args.extend(["--bridge", bridge])
        if payload.network.vlan and payload.network.vlan != 10:
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
            return Fail(msg=fail_message("读取 PVE 存储列表失败", stdout, stderr))
        return Success(data={"storages": parse_storage_output(stdout), "os_options": os_options(), "ssh_host": ssh_host})
    except Exception as exc:
        return Fail(msg=f"读取 PVE 创建选项失败: {exc}")


@router.post("/vms/create", summary="PVE virtual machine create")
async def create_vm(payload: VMCreateRequest):
    ssh_host = payload.region
    stdout = ""
    try:
        ssh_host = await resolve_create_host(payload.region)
        command = create_vm_command(payload)
        exit_status, stdout, stderr = await submit_remote_script(ssh_host, command)
        if exit_status != 0:
            return Fail(msg=fail_message("提交创建任务失败", stdout, stderr))
    except Exception as exc:
        return Fail(msg=f"提交创建任务失败: {exc}")

    return Success(
        msg="创建任务已提交",
        data={
            "region": payload.region,
            "ssh_host": ssh_host,
            "vm_name": payload.vm_name,
            "task": stdout,
            "config": payload.model_dump(),
        },
    )
