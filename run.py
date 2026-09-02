import os
import signal
import socket
import subprocess
import sys
import time

import uvicorn
from uvicorn.config import LOGGING_CONFIG

def parse_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


def is_port_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            sock.bind(("0.0.0.0", port))
        except OSError:
            return False
    return True


def process_looks_like_backend(command_line: str) -> bool:
    command = (command_line or "").lower()
    return "run.py" in command or "uvicorn" in command or "app:app" in command


def process_looks_like_backend_child(proc: dict) -> bool:
    name = (proc.get("Name") or "").lower()
    command = (proc.get("CommandLine") or "").lower()
    return (
        process_looks_like_backend(command)
        or (name == "python.exe" and "multiprocessing.spawn" in command)
    )


def powershell_json(command: str):
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", command],
            capture_output=True,
            text=True,
            timeout=8,
            check=False,
        )
    except Exception:
        return []
    if result.returncode != 0 or not result.stdout.strip():
        return []
    import json

    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        return []
    return data if isinstance(data, list) else [data]


def windows_port_processes(port: int) -> dict[int, dict]:
    command = rf"""
$owners = Get-NetTCPConnection -LocalPort {port} -State Listen -ErrorAction SilentlyContinue |
  Select-Object -ExpandProperty OwningProcess -Unique
$items = @()
foreach ($owner in $owners) {{
  $proc = Get-CimInstance Win32_Process -Filter "ProcessId=$owner" -ErrorAction SilentlyContinue
  if ($proc) {{
    $items += [PSCustomObject]@{{
      ProcessId = [int]$proc.ProcessId
      ParentProcessId = [int]$proc.ParentProcessId
      Name = [string]$proc.Name
      CommandLine = [string]$proc.CommandLine
    }}
  }}
}}
$items | ConvertTo-Json -Depth 3
"""
    processes = {}
    for item in powershell_json(command):
        try:
            processes[int(item["ProcessId"])] = item
        except (KeyError, TypeError, ValueError):
            continue
    if not processes:
        processes = windows_port_processes_from_netstat(port)
    return processes


def windows_port_processes_from_netstat(port: int) -> dict[int, dict]:
    try:
        result = subprocess.run(
            ["netstat", "-ano"],
            capture_output=True,
            text=True,
            timeout=8,
            check=False,
        )
    except Exception:
        return {}
    processes = {}
    for line in result.stdout.splitlines():
        parts = line.split()
        if len(parts) < 5 or parts[0].upper() != "TCP":
            continue
        local_address = parts[1]
        state = parts[3].upper()
        if state != "LISTENING" or not local_address.endswith(f":{port}"):
            continue
        try:
            pid = int(parts[-1])
        except ValueError:
            continue
        if pid == 0:
            continue
        processes[pid] = {
            "ProcessId": pid,
            "ParentProcessId": 0,
            "Name": "",
            "CommandLine": "",
        }
    return enrich_windows_processes(processes)


def enrich_windows_processes(processes: dict[int, dict]) -> dict[int, dict]:
    if not processes:
        return {}
    pid_filter = ",".join(str(pid) for pid in processes)
    command = rf"""
$ids = @({pid_filter})
$items = @()
foreach ($owner in $ids) {{
  $proc = Get-CimInstance Win32_Process -Filter "ProcessId=$owner" -ErrorAction SilentlyContinue
  if ($proc) {{
    $items += [PSCustomObject]@{{
      ProcessId = [int]$proc.ProcessId
      ParentProcessId = [int]$proc.ParentProcessId
      Name = [string]$proc.Name
      CommandLine = [string]$proc.CommandLine
    }}
  }}
}}
$items | ConvertTo-Json -Depth 3
"""
    enriched = {}
    for item in powershell_json(command):
        try:
            enriched[int(item["ProcessId"])] = item
        except (KeyError, TypeError, ValueError):
            continue
    return {pid: enriched.get(pid, proc) for pid, proc in processes.items()}


def windows_related_backend_processes(seed_pids: set[int]) -> dict[int, dict]:
    command = """
Get-CimInstance Win32_Process |
  Select-Object ProcessId,ParentProcessId,Name,CommandLine |
  ConvertTo-Json -Depth 3
"""
    all_processes = {}
    for item in powershell_json(command):
        try:
            all_processes[int(item["ProcessId"])] = item
        except (KeyError, TypeError, ValueError):
            continue

    related = {}
    queue = list(seed_pids)
    current_pid = os.getpid()
    while queue:
        pid = queue.pop()
        if pid in related or pid == current_pid:
            continue
        proc = all_processes.get(pid)
        if proc and process_looks_like_backend(proc.get("CommandLine", "")):
            related[pid] = proc
            parent = int(proc.get("ParentProcessId") or 0)
            if parent:
                queue.append(parent)
        for child_pid, child in all_processes.items():
            if int(child.get("ParentProcessId") or 0) == pid and process_looks_like_backend_child(child):
                queue.append(child_pid)
    return related


def terminate_processes(processes: dict[int, dict], port: int) -> None:
    print(f"Port {port} is used by an older backend process; stopping it first:")
    for pid, proc in sorted(processes.items()):
        print(f"  PID {pid}: {proc.get('CommandLine') or proc.get('Name')}")
    for pid in sorted(processes.keys(), reverse=True):
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            pass
    deadline = time.time() + 5
    while time.time() < deadline:
        if is_port_free(port):
            return
        time.sleep(0.2)
    for pid in sorted(processes.keys(), reverse=True):
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True, text=True, check=False)
    deadline = time.time() + 3
    while time.time() < deadline:
        if is_port_free(port):
            return
        time.sleep(0.2)


def ensure_single_backend_instance(port: int) -> None:
    if is_port_free(port):
        return
    if os.name != "nt":
        raise RuntimeError(f"Port {port} is already in use. Stop the old backend before starting a new one.")

    owners = windows_port_processes(port)
    related = windows_related_backend_processes(set(owners))
    kill_unknown_owner = parse_bool(os.getenv("BACKEND_KILL_UNKNOWN_PORT_OWNER"), default=True)
    if not related and owners and kill_unknown_owner:
        related = owners
    if related:
        terminate_processes(related, port)
    if not is_port_free(port):
        owner_text = "; ".join(
            f"PID {pid}: {proc.get('CommandLine') or proc.get('Name')}"
            for pid, proc in owners.items()
        ) or "unknown process"
        raise RuntimeError(f"Port {port} is still in use by {owner_text}")


if __name__ == "__main__":
    # 修改默认日志配置
    LOGGING_CONFIG["formatters"]["default"]["fmt"] = "%(asctime)s - %(levelname)s - %(message)s"
    LOGGING_CONFIG["formatters"]["default"]["datefmt"] = "%Y-%m-%d %H:%M:%S"
    LOGGING_CONFIG["formatters"]["access"][
        "fmt"
    ] = '%(asctime)s - %(levelname)s - %(client_addr)s - "%(request_line)s" %(status_code)s'
    LOGGING_CONFIG["formatters"]["access"]["datefmt"] = "%Y-%m-%d %H:%M:%S"

    port = int(os.getenv("PORT", "9999"))
    reload = parse_bool(os.getenv("BACKEND_RELOAD"), default=True)
    single_instance = parse_bool(os.getenv("BACKEND_SINGLE_INSTANCE"), default=True)
    if single_instance:
        try:
            ensure_single_backend_instance(port)
        except RuntimeError as exc:
            print(str(exc), file=sys.stderr)
            sys.exit(1)

    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=port,
        reload=reload,
        reload_excludes=["migrations/*", "**/__pycache__/*"],
        log_config=LOGGING_CONFIG,
    )
