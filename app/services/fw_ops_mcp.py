"""Bounded Operations Center readers for snapshots, Syslog and Akvorado."""

import ipaddress
import json
import re
from datetime import datetime, timedelta, timezone
from typing import Literal

import httpx
from fastapi import HTTPException, Request
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, ConfigDict, Field

from app.core.dependency import PermissionControl
from app.models.asset import CloudResourceSnapshot
from app.settings import settings

ACTION_PERMISSIONS = {
    "cloud_nodes": "/api/v1/pve/nodes",
    "cloud_vms": "/api/v1/pve/vms",
    "syslog_devices": "/api/v1/syslog/devices",
    "syslog_files": "/api/v1/syslog/files",
    "syslog_logs": "/api/v1/syslog/logs",
    # Akvorado's existing proxy is login-only; do not invent a menu permission.
    "traffic_regions": None,
    "traffic_widget": None,
    "traffic_graph": None,
}


class OpsReadInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal[
        "cloud_nodes",
        "cloud_vms",
        "syslog_devices",
        "syslog_files",
        "syslog_logs",
        "traffic_regions",
        "traffic_widget",
        "traffic_graph",
    ]
    offset: int = Field(default=0, ge=0, le=10000, strict=True)
    limit: int = Field(default=20, ge=1, le=100, strict=True)
    mode: Literal["rows", "count"] = "rows"
    remote: str = Field(default="", max_length=100)
    status: str = Field(default="", max_length=40)
    vmid: int | None = Field(default=None, gt=0)
    customer_id: int | None = Field(default=None, gt=0)
    keyword: str = Field(default="", max_length=200)
    device: str = Field(default="", max_length=64)
    file: str = Field(default="", max_length=200)
    level: str = Field(default="", max_length=30)
    vendor: str = Field(default="", max_length=50)
    tail: int = Field(default=1000, ge=100, le=5000, strict=True)
    region: str = Field(default="", max_length=12)
    widget: Literal[
        "flow-last",
        "flow-rate",
        "exporters",
        "top/src-as",
        "top/dst-as",
        "top/protocol",
        "top/src-country",
        "top/dst-country",
        "top/src-port",
        "top/dst-port",
        "top/exporter",
    ] = "flow-rate"
    start: datetime | None = None
    end: datetime | None = None
    dimensions: list[
        Literal[
            "ExporterName",
            "SrcAS",
            "DstAS",
            "SrcCountry",
            "DstCountry",
            "Proto",
            "SrcAddr",
            "DstAddr",
            "SrcPort",
            "DstPort",
            "InIfName",
            "OutIfName",
        ]
    ] = Field(default_factory=lambda: ["ExporterName"], max_length=4)
    filter: str = Field(default="", max_length=1000)
    units: Literal["l3bps", "l2bps", "pps", "fps"] = "l3bps"


def definition():
    return {
        "name": "finwork_ops_read",
        "description": (
            "运维查询：cloud_nodes/cloud_vms读取云资源快照，返回synced_at/stale，不能声称实时；"
            "syslog_devices发现设备，syslog_files列文件，syslog_logs按device/file查询末尾tail行并筛选；"
            "traffic_regions列流量区域，traffic_widget取区域概览，traffic_graph按带时区start/end查询最多24小时流量。"
            "limit/offset用于分页，mode=count用于云资源或Syslog查询计数。flow图按dimensions分组、limit取Top N。"
            "禁止任意URL、SSH命令、原始SQL、写操作；不可用时返回明确错误。"
        ),
        "inputSchema": OpsReadInput.model_json_schema(),
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False},
    }


async def authorize_action(action, user):
    if not user or not user.is_active:
        raise HTTPException(401, "当前用户不可用")
    path = ACTION_PERMISSIONS[action]
    if path:
        await PermissionControl.has_permission(
            Request({"type": "http", "method": "GET", "path": path, "headers": []}), user
        )


async def available_actions(user):
    actions = []
    for name in ACTION_PERMISSIONS:
        try:
            await authorize_action(name, user)
        except HTTPException:
            continue
        actions.append(name)
    return actions


SECRET_TEXT = re.compile(
    r"(?i)(?:bearer\s+\S+|sk-[\w.\-]+|(?:password|passwd|token|secret|api[_-]?key)\s*[:=]\s*[^\s,;]+)"
)


def sanitize(value, depth=0):
    if depth > 8:
        return "[truncated]"
    if isinstance(value, str):
        if "PRIVATE KEY" in value:
            return "[redacted]"
        return SECRET_TEXT.sub("[redacted]", value)[:1000]
    if isinstance(value, list):
        return [sanitize(item, depth + 1) for item in value[:100]]
    if isinstance(value, dict):
        return {
            key: sanitize(item, depth + 1)
            for key, item in list(value.items())[:100]
                if not re.search(r"(?i)password|passwd|token|secret|authorization|credential|private.?key|密码|密钥|令牌|口令", key)
        }
    return value


def page_result(rows, args, **metadata):
    total = len(rows)
    if args.mode == "count":
        return {"source": args.action, "count": total, "rows": [], **metadata}
    limit = min(args.limit, max(1, min(settings.FW_ASSISTANT_DB_QUERY_LIMIT, 100)))
    selected, used, truncated = [], 0, False
    for row in rows[args.offset : args.offset + limit]:
        cleaned = sanitize(jsonable_encoder(row))
        truncated |= cleaned != row
        size = len(json.dumps(cleaned, ensure_ascii=False).encode("utf-8"))
        if used + size > 30000:
            truncated = True
            break
        selected.append(cleaned)
        used += size
    next_offset = args.offset + len(selected)
    return {
        "source": args.action,
        "rows": selected,
        "row_count": len(selected),
        "total": total,
        "offset": args.offset,
        "has_more": next_offset < total,
        "next_offset": next_offset if next_offset < total else None,
        "truncated": truncated,
        **metadata,
    }


CLOUD_FIELDS = tuple(
    (
        "id remote vmid name label node type status ip region_id region_name location_id location_name device_id "
        "customer_id customer_name cpu maxcpu cpu_total cpu_usage mem maxmem mem_percent mem_usage "
        "disk maxdisk disk_percent disk_usage uptime vm_count node_count online_node_count os_type created_at "
        "cpu_cores memory_gb disk_gb remark ips"
    ).split()
)


async def cloud_read(args):
    row = await CloudResourceSnapshot.get_or_none(key="fleet")
    if row is None or row.synced_at is None:
        raise ValueError("云资源快照尚未同步，请先在云资源页面刷新")
    synced_at = row.synced_at
    if synced_at.tzinfo is None:
        synced_at = synced_at.replace(tzinfo=timezone.utc)
    stale = row.dirty or bool(row.error) or datetime.now(timezone.utc) - synced_at > timedelta(minutes=5)
    key = "nodes" if args.action == "cloud_nodes" else "items"
    if not isinstance(row.payload, dict) or not isinstance(row.payload.get(key), list):
        raise ValueError("云资源快照内容不完整，请在云资源页面刷新")
    rows = []
    for item in (row.payload or {}).get(key, []):
        if args.remote and item.get("remote") != args.remote:
            continue
        if args.status and item.get("status") != args.status:
            continue
        if args.vmid is not None and item.get("vmid") != args.vmid:
            continue
        if args.customer_id is not None and item.get("customer_id") != args.customer_id:
            continue
        projected = {key: item[key] for key in CLOUD_FIELDS if key in item}
        if args.keyword and args.keyword.casefold() not in json.dumps(projected, ensure_ascii=False).casefold():
            continue
        rows.append(projected)
    return page_result(
        rows,
        args,
        synced_at=synced_at.isoformat(),
        stale=stale,
        note="云资源快照，不是实时状态；内存和磁盘原始值单位为字节",
    )


async def syslog_read(args):
    from app.api.v1.syslog import syslog

    if args.action != "syslog_devices":
        try:
            ipaddress.ip_address(args.device)
        except ValueError:
            raise ValueError("device 必须为有效IP地址") from None
    if args.action == "syslog_devices":
        response = await syslog.list_syslog_devices()
    elif args.action == "syslog_files":
        response = await syslog.list_syslog_files(device=args.device)
    else:
        if not args.file or args.file in {".", ".."} or "/" in args.file or "\\" in args.file:
            raise ValueError("file 必须为日志文件列表中的文件名")
        response = await syslog.query_syslog_logs(
            page=1,
            page_size=args.tail,
            device=args.device,
            file=args.file,
            keyword=args.keyword,
            level=args.level,
            vendor=args.vendor,
            tail=args.tail,
        )
    data = json.loads(response.body)
    if response.status_code >= 400 or data.get("code") != 200:
        raise ValueError("Syslog 数据源读取失败，请检查服务连接或文件是否存在")
    return page_result(
        data.get("data") or [],
        args,
        observed_at=datetime.now(timezone.utc).isoformat(),
        scope=f"末尾{args.tail}行内匹配结果" if args.action == "syslog_logs" else "目录列表",
    )


async def traffic_request(base, path, payload=None):
    # Only fixed read endpoints call this; no model-supplied URL or redirect target is accepted.
    async with httpx.AsyncClient(timeout=8, trust_env=False, follow_redirects=False) as client:
        async with client.stream(
            "POST" if payload is not None else "GET",
            base.rstrip("/") + path,
            json=payload,
            headers={"Accept": "application/json"},
        ) as response:
            if response.status_code != 200:
                raise ValueError("流量服务不可用或API版本不兼容")
            body = bytearray()
            async for chunk in response.aiter_bytes():
                body.extend(chunk)
                if len(body) > 1024 * 1024:
                    raise ValueError("流量结果过大，请缩小时间或维度范围")
    try:
        return json.loads(body)
    except ValueError:
        raise ValueError("流量服务未返回有效JSON") from None


async def traffic_read(args):
    from app.api.v1.akvorado import AKVORADO_REGIONS

    if args.action == "traffic_regions":
        return page_result([{"region": name} for name in AKVORADO_REGIONS], args)
    region = args.region.upper()
    if region not in AKVORADO_REGIONS:
        raise ValueError("未知流量区域，请先调用 traffic_regions")
    if args.mode != "rows" or args.offset:
        raise ValueError("流量统计不支持mode=count或offset；limit指定图表Top N")
    if args.action == "traffic_widget":
        result = await traffic_request(AKVORADO_REGIONS[region], "/api/v0/console/widget/" + args.widget)
    else:
        if not args.start or not args.end or args.start.tzinfo is None or args.end.tzinfo is None:
            raise ValueError("流量图查询需要带时区的start/end")
        if not timedelta(0) < args.end - args.start <= timedelta(hours=24):
            raise ValueError("流量时间范围须大于0且不超过24小时")
        payload = {
            "start": args.start.isoformat(),
            "end": args.end.isoformat(),
            "dimensions": args.dimensions,
            "limit": min(args.limit, 20),
            "limitType": "avg",
            "filter": args.filter,
            "units": args.units,
            "points": 20,
            "bidirectional": False,
            "previous-period": False,
        }
        result = await traffic_request(AKVORADO_REGIONS[region], "/api/v0/console/graph/line", payload)
    if isinstance(result, dict) and result.get("error"):
        raise ValueError("流量服务查询失败，请检查筛选条件或服务状态")
    # Keep graph arrays aligned. Refuse oversized results rather than silently truncate series/time axes.
    cleaned = sanitize(result)
    if args.action == "traffic_graph" and cleaned != result:
        raise ValueError("流量图结果超出安全返回范围，请减少维度或时间范围")
    truncated = cleaned != result
    result = cleaned
    if len(json.dumps(result, ensure_ascii=False).encode("utf-8")) > 30000:
        raise ValueError("流量结果过大，请减少维度或limit")
    return {
        "source": args.action,
        "region": region,
        "data": result,
        "units": args.units if args.action == "traffic_graph" else None,
        "truncated": truncated,
        "start": args.start.isoformat() if args.start else None,
        "end": args.end.isoformat() if args.end else None,
        "observed_at": datetime.now(timezone.utc).isoformat(),
    }


async def read_operations(arguments, user):
    args = OpsReadInput.model_validate(arguments)
    await authorize_action(args.action, user)
    if args.action.startswith("cloud_"):
        return await cloud_read(args)
    if args.action.startswith("syslog_"):
        return await syslog_read(args)
    return await traffic_read(args)
