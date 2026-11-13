"""Zabbix-backed operations. Never return raw upstream errors or credentials."""

import asyncio
import hashlib
import time
from collections import Counter
from urllib.parse import urlsplit, urlunsplit

import httpx
from fastapi import HTTPException

from app.services.monitor_event_config import load_settings
from app.settings.config import settings

CATEGORIES = {
    "server": "物理服务器",
    "network": "网络设备",
    "circuit": "国际线路",
    "pve": "PVE 虚拟化",
    "other": "其他 / 未分类",
}
LIMIT = 2000


class ZabbixClient:
    async def __aenter__(self):
        if not settings.ZABBIX_URL or not settings.ZABBIX_TOKEN:
            raise HTTPException(503, "未配置 ZABBIX_URL / ZABBIX_TOKEN")
        self.client = httpx.AsyncClient(timeout=25, verify=settings.ZABBIX_VERIFY_TLS, trust_env=False)
        try:
            version = await self.call("apiinfo.version", {}, anonymous=True)
            self.modern = tuple(int(v) for v in version.split(".")[:2]) >= (7, 2)
            self.version = version
            return self
        except Exception:
            await self.client.aclose()
            raise

    async def __aexit__(self, *args):
        await self.client.aclose()

    async def call(self, method, params, anonymous=False):
        payload = {"jsonrpc": "2.0", "method": method, "params": params, "id": 1}
        headers = {"Content-Type": "application/json-rpc"}
        if not anonymous:
            if self.modern:
                headers["Authorization"] = f"Bearer {settings.ZABBIX_TOKEN}"
            else:
                payload["auth"] = settings.ZABBIX_TOKEN
        try:
            response = await self.client.post(settings.ZABBIX_URL, json=payload, headers=headers)
            response.raise_for_status()
            result = response.json()
        except (httpx.HTTPError, ValueError):
            raise HTTPException(502, "Zabbix 请求失败；如刚提交操作，请刷新核实结果后再重试") from None
        if result.get("error"):
            raise HTTPException(502, "Zabbix 拒绝请求，请检查 API 账号权限、事件状态及服务器版本")
        if "result" not in result:
            raise HTTPException(502, "Zabbix 返回格式异常")
        return result["result"]


def classify(host):
    tags = {str(t.get("tag", "")).lower(): str(t.get("value", "")).lower() for t in host.get("tags", [])}
    explicit = tags.get("finwork_category") or tags.get("business_category")
    if explicit in CATEGORIES:
        return explicit
    text = " ".join(
        [host.get("name", ""), host.get("host", ""), *[g["name"] for g in host.get("hostgroups", [])]]
    ).lower()
    for category, words in [
        ("pve", ["pve", "proxmox", "虚拟化"]),
        ("circuit", ["iplc", "iepl", "circuit", "线路", "专线"]),
        ("network", ["switch", "router", "firewall", "交换机", "路由器", "防火墙", "network"]),
        ("server", ["server", "linux", "windows", "服务器", "idrac", "ilo"]),
    ]:
        if any(word in text for word in words):
            return category
    return "other"


def advice(name):
    text = name.lower()
    rules = [
        (
            ["unavailable", "unreachable", "不可达", "agent is not available", "icmp"],
            "连通性",
            [
                "从监控探针检查目标 IP 的连通性及丢包，区分单机与同站点共同故障。",
                "核查设备电源、管理口和上联端口；仅 Agent 异常时检查 Agent 服务及访问策略。",
            ],
        ),
        (
            ["disk", "ssd", "smart", "磁盘", "storage"],
            "存储",
            [
                "核对告警盘符、容量、inode 或 SMART 项目及当前值，区分容量告警和硬件故障。",
                "检查 I/O 错误及阵列状态，先确认备份；勿直接清理业务数据或重启阵列。",
            ],
        ),
        (
            ["cpu", "load average", "处理器"],
            "计算资源",
            [
                "核对 CPU/负载的持续时间与业务高峰，检查高占用进程及宿主机资源争用。",
                "对照最近发布、备份和迁移任务，确认影响后调整负载或容量。",
            ],
        ),
        (
            ["memory", "swap", "内存"],
            "内存",
            [
                "核对可用内存、Swap 和 OOM 日志，检查占用持续增长的进程。",
                "结合业务容量和最近变更定位泄漏或争用，变更前确认影响范围。",
            ],
        ),
        (
            ["interface", "bandwidth", "packet", "loss", "latency", "link down", "bgp", "端口", "丢包", "延迟"],
            "网络 / 线路",
            [
                "定位具体接口或邻居，检查接口状态、速率、误码、光功率及两端指标。",
                "核对路由/BGP 会话和运营商维护信息，对比同站点告警判断上游影响。",
            ],
        ),
        (
            ["temperature", "fan", "power", "温度", "风扇", "电源"],
            "硬件环境",
            [
                "定位具体传感器、电源或风扇，核对管理卡状态和机房环境。",
                "检查冗余是否仍正常，联系现场核查；避免在冗余失效时直接下电。",
            ],
        ),
    ]
    for words, category, steps in rules:
        if any(word in text for word in words):
            return {"type": category, "basis": "根据告警名称关键词匹配，需结合指标确认；不是已确认根因", "steps": steps}
    return {
        "type": "通用排查",
        "basis": "尚未匹配专项规则；不是已确认根因",
        "steps": [
            "核对触发条件、监控指标和主机定位信息。",
            "对照同主机事件、最近变更及恢复时间，确认影响范围后记录处置结论。",
        ],
    }


def event_url(eventid, triggerid):
    parts = urlsplit(settings.ZABBIX_URL)
    host = parts.hostname or ""
    if ":" in host:
        host = f"[{host}]"
    netloc = f"{host}:{parts.port}" if parts.port else host
    path = parts.path.rsplit("/", 1)[0] + "/tr_events.php"
    return urlunsplit((parts.scheme, netloc, path, f"triggerid={triggerid}&eventid={eventid}", ""))


async def get_hosts(client, hostids=None):
    if not hostids:
        return []
    params = {
        "output": ["hostid", "host", "name", "status", "maintenance_status"],
        "selectInterfaces": ["ip", "dns", "useip", "main", "type", "available"],
        "selectHostGroups": ["groupid", "name"],
        "selectTags": "extend",
        "selectInheritedTags": ["tag", "value"],
        "selectInventory": ["location", "site_address_a", "type", "name"],
        "limit": 10001,
        "filter": {"status": 0},
    }
    params["hostids"] = hostids
    hosts = await client.call("host.get", params)
    for host in hosts:
        pairs = {(t.get("tag", ""), t.get("value", "")) for t in host.get("tags", []) + host.get("inheritedTags", [])}
        host["tags"] = [{"tag": tag, "value": value} for tag, value in sorted(pairs)]
    return hosts


def host_view(host):
    inventory = host.get("inventory") or {}
    return {
        "hostid": host["hostid"],
        "name": host.get("name") or host.get("host"),
        "technical_name": host.get("host"),
        "addresses": list(
            dict.fromkeys(
                i.get("ip") if str(i.get("useip")) == "1" else i.get("dns")
                for i in host.get("interfaces", [])
                if i.get("ip") or i.get("dns")
            )
        ),
        "groups": [g["name"] for g in host.get("hostgroups", [])],
        "location": inventory.get("location") or inventory.get("site_address_a") or "",
        "category": classify(host),
        "tags": host.get("tags", []),
        "maintenance": str(host.get("maintenance_status")) == "1",
    }


def tag_categories(hosts, tag_name):
    assigned, labels = {}, {}
    for host in hosts:
        values = sorted(
            {
                str(t.get("value", "")).strip()
                for t in host.get("tags", [])
                if t.get("tag") == tag_name and str(t.get("value", "")).strip()
            }
        )
        keys = []
        for value in values:
            key = "tag_" + hashlib.sha256(value.encode()).hexdigest()
            labels[key] = value
            keys.append(key)
        if not keys:
            keys = ["untagged"]
            labels["untagged"] = "未分类（标签缺失或值为空）"
        assigned[host["hostid"]] = keys
    return assigned, [{"key": key, "label": label} for key, label in sorted(labels.items(), key=lambda item: item[1])]


async def enrich(client, events, hosts=None, categories=None):
    if not events:
        return []
    triggers = await client.call(
        "trigger.get",
        {
            "triggerids": list({e["objectid"] for e in events}),
            "output": ["triggerid", "manual_close"],
            "selectHosts": ["hostid"],
        },
    )
    trigger_map = {t["triggerid"]: t for t in triggers}
    recovery_ids = sorted(
        {
            str(e["r_eventid"])
            for e in events
            if str(e.get("r_eventid") or "0") != "0" and not int(e.get("r_clock") or 0)
        }
    )
    recovery_clocks = {}
    if recovery_ids:
        recoveries = await client.call(
            "event.get",
            {
                "eventids": recovery_ids,
                "output": ["eventid", "clock"],
            },
        )
        recovery_clocks = {e["eventid"]: int(e["clock"]) for e in recoveries}
    if hosts is None:
        hosts = await get_hosts(client, list({h["hostid"] for t in triggers for h in t.get("hosts", [])}))
    host_map = {h["hostid"]: host_view(h) for h in hosts}
    if categories is not None:
        for hostid, host in host_map.items():
            host["categories"] = categories.get(hostid, ["untagged"])
            host["category"] = host["categories"][0]
    output = []
    for event in events:
        trigger = trigger_map.get(event["objectid"], {})
        event_hosts = [host_map[h["hostid"]] for h in trigger.get("hosts", []) if h["hostid"] in host_map]
        recovered = str(event.get("r_eventid") or "0") != "0"
        recovery_clock = int(event.get("r_clock") or recovery_clocks.get(str(event.get("r_eventid")), 0))
        output.append(
            {
                "id": event["eventid"],
                "trigger_id": event["objectid"],
                "name": event["name"],
                "severity": int(event.get("severity", 0)),
                "clock": int(event["clock"]),
                "recovery_clock": recovery_clock,
                "duration_seconds": (
                    max(0, (recovery_clock if recovered else int(time.time())) - int(event["clock"]))
                    if not recovered or recovery_clock
                    else None
                ),
                "recovery_id": event.get("r_eventid", "0"),
                "recovered": recovered,
                "acknowledged": str(event.get("acknowledged")) == "1",
                "suppressed": str(event.get("suppressed")) == "1",
                "suppression": event.get("suppression_data", []),
                "hosts": event_hosts,
                "categories": sorted({key for h in event_hosts for key in h.get("categories", [h["category"]])})
                or ["untagged"],
                "tags": event.get("tags", []),
                "opdata": event.get("opdata", ""),
                "manual_close": str(trigger.get("manual_close")) == "1",
                "advice": advice(event["name"]),
                "url": event_url(event["eventid"], event["objectid"]),
            }
        )
    return output


async def dashboard(client, history=False, config=None):
    config = config if config is not None else await load_settings()
    hostids = [h["hostid"] for h in config["hosts"]]
    params = {
        "output": "extend",
        "source": 0,
        "object": 0,
        "selectTags": "extend",
        "selectSuppressionData": "extend",
        "sortfield": "eventid",
        "sortorder": "DESC",
        "limit": LIMIT + 1,
        "hostids": hostids,
    }
    problems, hosts = (
        await asyncio.gather(client.call("problem.get", params), get_hosts(client, hostids)) if hostids else ([], [])
    )
    assigned, category_options = tag_categories(hosts, config.get("category_tag", "business_category"))
    active_rows = await enrich(client, problems[:LIMIT], hosts[:10000], assigned)
    rows = active_rows
    truncated = len(problems) > LIMIT or len(hosts) > 10000
    if history and hostids:
        params.update(time_from=int(time.time()) - 7 * 86400, value=1)
        events = await client.call("event.get", params)
        rows = await enrich(client, events[:LIMIT], hosts[:10000], assigned)
        truncated = truncated or len(events) > LIMIT
    host_counts = Counter(key for keys in assigned.values() for key in keys)
    active = [r for r in active_rows if not r["recovered"]]
    abnormal = {h["hostid"] for r in active for h in r["hosts"]}
    categories = []
    for category in category_options:
        key, label = category["key"], category["label"]
        bad = {h["hostid"] for r in active for h in r["hosts"] if key in h.get("categories", [])}
        categories.append(
            {
                "key": key,
                "label": label,
                "total": host_counts[key],
                "abnormal": len(bad),
                "events": sum(key in r["categories"] for r in active),
            }
        )
    return {
        "rows": rows,
        "categories": categories,
        "summary": {
            "hosts": min(len(hosts), 10000),
            "abnormal_hosts": len(abnormal),
            "problems": len(active),
            "critical": sum(r["severity"] >= 4 for r in active),
            "suppressed": sum(r["suppressed"] for r in active),
        },
        "truncated": truncated,
        "scope": "已选主机近 7 天发生的问题事件" if history else "已选主机当前未恢复问题（含抑制）",
        "updated_at": int(time.time()),
        "version": client.version if client else "",
        "configured": bool(hostids),
        "category_tag": config.get("category_tag", "business_category"),
        "selected_hosts": len(hostids),
        "unavailable_hosts": len(set(hostids) - {h["hostid"] for h in hosts}),
    }


async def detail(client, eventid, config=None):
    config = config if config is not None else await load_settings()
    hostids = [h["hostid"] for h in config["hosts"]]
    if not hostids:
        raise HTTPException(404, "事件不在已选择的监控范围内")
    events = await client.call(
        "event.get",
        {
            "eventids": [eventid],
            "hostids": hostids,
            "source": 0,
            "object": 0,
            "value": 1,
            "output": "extend",
            "selectTags": "extend",
            "selectAcknowledges": "extend",
            "selectSuppressionData": "extend",
        },
    )
    if not events:
        raise HTTPException(404, "事件不存在或 Zabbix 账号不可见")
    event = events[0]
    hosts = await get_hosts(client, hostids)
    assigned, _ = tag_categories(hosts, config.get("category_tag", "business_category"))
    row = (await enrich(client, events, hosts, assigned))[0]
    if not row["hosts"]:
        raise HTTPException(404, "事件不在已选择的监控范围内")
    triggers = await client.call(
        "trigger.get",
        {
            "triggerids": [event["objectid"]],
            "output": ["triggerid", "expression", "recovery_expression", "comments", "manual_close"],
            "selectItems": ["itemid"],
            "expandExpression": True,
            "expandComment": True,
        },
    )
    trigger = triggers[0] if triggers else {}
    ids = [i["itemid"] for i in trigger.get("items", [])]
    items = (
        await client.call(
            "item.get",
            {
                "itemids": ids,
                "hostids": hostids,
                "output": ["itemid", "hostid", "name", "lastvalue", "lastclock", "units", "value_type"],
            },
        )
        if ids
        else []
    )
    items = [item for item in items if item.get("hostid") in hostids]
    row.update(
        expression=trigger.get("expression", ""),
        recovery_expression=trigger.get("recovery_expression", ""),
        description=trigger.get("comments", ""),
        items=items,
        history=event.get("acknowledges", []),
    )
    return row
