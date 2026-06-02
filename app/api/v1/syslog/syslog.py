import asyncio
import ipaddress
import os
import re
import shlex
import subprocess
from datetime import datetime
from pathlib import PurePosixPath
from typing import Any

from fastapi import APIRouter, Query

from app.schemas.base import Fail, Success, SuccessExtra

router = APIRouter()

SYSLOG_HOST = os.getenv("SYSLOG_HOST", "45.67.201.229")
SYSLOG_USER = os.getenv("SYSLOG_USER", "root")
SYSLOG_BASE_DIR = os.getenv("SYSLOG_BASE_DIR", "/log")
SYSLOG_SSH_PORT = int(os.getenv("SYSLOG_SSH_PORT", "22"))
SYSLOG_SSH_KEY = os.getenv("SYSLOG_SSH_KEY", "")
SYSLOG_TIMEOUT = int(os.getenv("SYSLOG_TIMEOUT", "20"))

SYSLOG_TS_RE = re.compile(r"^(?P<mon>[A-Z][a-z]{2})\s+(?P<day>\d{1,2})\s+(?P<time>\d{2}:\d{2}:\d{2})")
ISO_TS_RE = re.compile(r"^(?P<ts>\d{4}-\d{2}-\d{2}[T\s]\d{2}:\d{2}:\d{2}(?:[.,]\d+)?)")
LEADING_TS_PATTERNS = [
    re.compile(r"^[A-Z][a-z]{2}\s+\d{1,2}\s+\d{4}\s+\d{2}:\d{2}:\d{2}(?:[+-]\d{2}:?\d{2})?\s+"),
    re.compile(r"^[A-Z][a-z]{2}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2}\s+"),
    re.compile(r"^\d{4}-\d{2}-\d{2}[T\s]\d{2}:\d{2}:\d{2}(?:[.,]\d+)?(?:[+-]\d{2}:?\d{2})?\s+"),
]

LEVEL_PATTERNS = [
    ("emergency", re.compile(r"\b(emerg|emergency|panic)\b|%%\d?EMERG", re.I)),
    ("alert", re.compile(r"\balert\b|%%\d?ALERT", re.I)),
    ("critical", re.compile(r"\b(crit|critical|fatal)\b|%%\d?CRIT", re.I)),
    ("error", re.compile(r"\b(err|error|failed|failure|down)\b|%%\d?ERR|%[A-Z0-9_-]+-[0-3]-", re.I)),
    ("warning", re.compile(r"\b(warn|warning|alarm|threshold)\b|%%\d?WARN|%[A-Z0-9_-]+-4-", re.I)),
    ("notice", re.compile(r"\bnotice\b|%[A-Z0-9_-]+-5-", re.I)),
    ("info", re.compile(r"\b(info|informational)\b|%[A-Z0-9_-]+-6-", re.I)),
    ("debug", re.compile(r"\bdebug\b|%[A-Z0-9_-]+-7-", re.I)),
]

VENDOR_PATTERNS = [
    ("Huawei", re.compile(r"%%\d{2}|huawei|vrp|hw[a-z0-9_-]*", re.I)),
    ("Ruijie", re.compile(r"ruijie|rgos|rg-[a-z0-9-]+|%[A-Z0-9_-]+-\d-", re.I)),
    ("Cisco", re.compile(r"cisco|ios|ios-xe|nx-os|%[A-Z0-9_-]+-\d-", re.I)),
    ("Juniper", re.compile(r"juniper|junos|rpd\[\d+\]|mgd\[\d+\]|chassisd\[\d+\]", re.I)),
    ("Arista", re.compile(r"arista|eos|super-server|ProcMgr|Ebra", re.I)),
]


def run_ssh(remote_command: str) -> str:
    cmd = [
        "ssh",
        "-p",
        str(SYSLOG_SSH_PORT),
        "-o",
        "BatchMode=yes",
        "-o",
        "ConnectTimeout=8",
        "-o",
        "StrictHostKeyChecking=accept-new",
    ]
    if SYSLOG_SSH_KEY:
        cmd.extend(["-i", SYSLOG_SSH_KEY])
    cmd.append(f"{SYSLOG_USER}@{SYSLOG_HOST}")
    cmd.append(remote_command)

    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=SYSLOG_TIMEOUT, check=False)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip() or "ssh command failed")
    return proc.stdout


async def run_ssh_async(remote_command: str) -> str:
    return await asyncio.to_thread(run_ssh, remote_command)


def safe_device_name(device: str) -> str:
    device = str(device or "").strip()
    try:
        ipaddress.ip_address(device)
        return device
    except ValueError as exc:
        raise ValueError("invalid device ip") from exc


def safe_log_path(device: str, filename: str = "") -> str:
    device = safe_device_name(device)
    base = PurePosixPath(SYSLOG_BASE_DIR)
    path = base / device
    if filename:
        clean = PurePosixPath(filename).name
        if not clean or clean in {".", ".."}:
            raise ValueError("invalid filename")
        path = path / clean
    return shlex.quote(str(path))


def detect_level(line: str) -> str:
    for level, pattern in LEVEL_PATTERNS:
        if pattern.search(line):
            return level
    return "unknown"


def detect_vendor(line: str) -> str:
    for vendor, pattern in VENDOR_PATTERNS:
        if pattern.search(line):
            return vendor
    return "Unknown"


def parse_timestamp(line: str) -> str:
    iso_match = ISO_TS_RE.search(line)
    if iso_match:
        return iso_match.group("ts").replace("T", " ")

    syslog_match = SYSLOG_TS_RE.search(line)
    if not syslog_match:
        return ""

    year = datetime.now().year
    text = f"{year} {syslog_match.group('mon')} {syslog_match.group('day')} {syslog_match.group('time')}"
    try:
        return datetime.strptime(text, "%Y %b %d %H:%M:%S").strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        return ""


def parse_host(line: str, fallback: str) -> str:
    text = line.strip()
    changed = True
    while changed:
        changed = False
        for pattern in LEADING_TS_PATTERNS:
            next_text = pattern.sub("", text, count=1)
            if next_text != text:
                text = next_text.lstrip()
                changed = True
                break

    host = text.split(maxsplit=1)[0] if text else ""
    return host or fallback


def parse_syslog_line(line: str, device: str, index: int) -> dict[str, Any]:
    return {
        "id": index,
        "time": parse_timestamp(line),
        "device": device,
        "host": parse_host(line, device),
        "vendor": detect_vendor(line),
        "level": detect_level(line),
        "message": line.strip(),
    }


def parse_lines(lines: list[str], device: str, keyword: str, level: str, vendor: str) -> list[dict[str, Any]]:
    items = []
    keyword_lower = keyword.strip().lower()
    level_lower = level.strip().lower()
    vendor_lower = vendor.strip().lower()

    for index, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        item = parse_syslog_line(line, device, index)
        if keyword_lower and keyword_lower not in item["message"].lower():
            continue
        if level_lower and item["level"] != level_lower:
            continue
        if vendor_lower and item["vendor"].lower() != vendor_lower:
            continue
        items.append(item)
    return items


@router.get("/devices", summary="Syslog 设备目录")
async def list_syslog_devices():
    try:
        output = await run_ssh_async(
            f"find {shlex.quote(SYSLOG_BASE_DIR)} -mindepth 1 -maxdepth 1 -type d -printf '%f\\n' | sort -V"
        )
    except Exception as exc:
        return Fail(msg=f"读取 Syslog 设备目录失败: {exc}")

    devices = []
    for name in output.splitlines():
        try:
            ipaddress.ip_address(name.strip())
        except ValueError:
            continue
        devices.append({"label": name.strip(), "value": name.strip()})
    return Success(data=devices)


@router.get("/files", summary="Syslog 日志文件列表")
async def list_syslog_files(device: str = Query(...)):
    try:
        path = safe_log_path(device)
        output = await run_ssh_async(
            f"find {path} -maxdepth 1 -type f -printf '%f\\t%s\\t%TY-%Tm-%Td %TH:%TM:%TS\\n' | sort -r"
        )
    except Exception as exc:
        return Fail(msg=f"读取 Syslog 文件列表失败: {exc}")

    files = []
    for line in output.splitlines():
        parts = line.split("\t", 2)
        if len(parts) != 3:
            continue
        files.append({"name": parts[0], "size": int(parts[1] or 0), "mtime": parts[2].split(".", 1)[0]})
    return Success(data=files)


@router.get("/logs", summary="Syslog 日志查询")
async def query_syslog_logs(
    page: int = Query(1),
    page_size: int = Query(50),
    device: str = Query(...),
    file: str = Query(...),
    keyword: str = Query(""),
    level: str = Query(""),
    vendor: str = Query(""),
    tail: int = Query(2000, ge=100, le=20000),
):
    if not file.strip():
        return Fail(msg="请选择日志文件后再查询")
    try:
        path = safe_log_path(device, file)
        remote_command = f"tail -n {int(tail)} {path}"
        output = await run_ssh_async(remote_command)
    except Exception as exc:
        return Fail(msg=f"读取 Syslog 日志失败: {exc}")

    items = parse_lines(output.splitlines(), device=device, keyword=keyword, level=level, vendor=vendor)
    total = len(items)
    start = max(page - 1, 0) * page_size
    data = items[start : start + page_size]
    return SuccessExtra(data=data, total=total, page=page, page_size=page_size)


@router.get("/raw", summary="Syslog 原始日志")
async def get_syslog_raw(
    device: str = Query(...),
    file: str = Query(...),
    tail: int = Query(300, ge=10, le=5000),
):
    if not file.strip():
        return Fail(msg="请选择日志文件后再查看原始日志")
    try:
        path = safe_log_path(device, file)
        remote_command = f"tail -n {int(tail)} {path}"
        output = await run_ssh_async(remote_command)
    except Exception as exc:
        return Fail(msg=f"读取 Syslog 原始日志失败: {exc}")
    return Success(data={"content": output})
