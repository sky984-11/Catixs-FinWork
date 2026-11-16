"""Inventory-driven ICMP enrolment; Zabbix alone performs the checks."""

import asyncio
import copy
import hashlib
import ipaddress
import json
import time
import uuid
from collections import Counter

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator
from tortoise.transactions import in_transaction

from app.models import (
    AssetDevice,
    CabinetMonitorConfig,
    CabinetMonitorTarget,
    CrmCustomer,
    MonitorNotificationConfig,
    User,
)

CATEGORY = "cabinet_customer"
FIELDS = [
    {"key": k, "label": v}
    for k, v in [
        ("customer", "客户"),
        ("location", "机房"),
        ("cabinet", "机柜"),
        ("position", "U 位 / 节点"),
    ]
]


async def ensure_platform_category():
    """Persist the automatic category once; subsequent user edits remain authoritative."""
    from app.models import MonitorEventConfig
    from app.services.monitor_event_config import DEFAULT_CATEGORIES

    config = await CabinetMonitorConfig.get_or_none(id=1)
    if not config or not config.enabled:
        return
    current = await MonitorEventConfig.get_or_none(id=1)
    if current and any(c["key"] == CATEGORY for c in current.categories):
        return
    async with in_transaction():
        await MonitorEventConfig.get_or_create(
            id=1, defaults={"categories": copy.deepcopy(DEFAULT_CATEGORIES), "hosts": [], "updated_by_id": 0}
        )
        row = await MonitorEventConfig.filter(id=1).select_for_update().get()
        if any(c["key"] == CATEGORY for c in row.categories):
            return
        names = {c["label"] for c in row.categories}
        label = "机柜客户机器"
        suffix = 1
        while label in names:
            label = f"机柜客户机器（自动纳管 {suffix}）"
            suffix += 1
        row.categories = [*row.categories, {"key": CATEGORY, "label": label, "fields": copy.deepcopy(FIELDS)}]
        row.revision += 1
        await row.save(update_fields=["categories", "revision", "updated_at"])


def normalize_ip(value):
    try:
        address = ipaddress.ip_address(str(value or "").strip())
        if address.is_unspecified or address.is_multicast or address.is_loopback or address.is_link_local:
            return ""
        return str(address)
    except ValueError:
        return ""


class CabinetSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")
    revision: int = Field(ge=0)
    enabled: bool
    template_id: str = Field(pattern=r"^[1-9][0-9]{0,19}$")
    group_id: str = Field(pattern=r"^[1-9][0-9]{0,19}$")
    proxy_id: str = Field(default="", pattern=r"^([1-9][0-9]{0,19})?$")
    overrides: dict[str, str] = Field(default_factory=dict, max_length=10000)

    @model_validator(mode="after")
    def validate_addresses(self):
        for key, value in self.overrides.items():
            if len(key) > 64 or not normalize_ip(value):
                raise ValueError("监控地址必须为有效的单个 IPv4 / IPv6 地址")
        self.overrides = {k: normalize_ip(v) for k, v in self.overrides.items()}
        return self


def device_targets(device, customers, overrides):
    """Four-node chassis must never be mistaken for four identical IPMI targets."""
    attrs = device.attributes or {}
    nodes = attrs.get("nodes") if attrs.get("form_factor") == "four_node" else None
    units = nodes if isinstance(nodes, list) else [None]
    result = []
    for node in units:
        if node is not None and not isinstance(node, dict):
            continue
        ids = (
            [node.get("customer_id")]
            if node is not None
            else device.customer_ids or [device.customer_id or device.cabinet.customer_id]
        )
        ids = [str(i) for i in ids if i and str(i) in customers]
        status = node.get("status", 0) if node is not None else device.status
        if not ids or status not in (1, 2, 3) or not device.cabinet.status:
            continue
        suffix = str(node.get("name", "")) if node is not None else "device"
        key = f"{device.id}:{suffix}"
        source = node if node is not None else attrs
        ipmi_keys = ("ipmi_host", "ipmiHost", "IPMI地址") if node is not None else ("ipmi_host", "IPMI地址")
        default_ip = next((str(source[k]).strip() for k in ipmi_keys if str(source.get(k) or "").strip()), "")
        ip = normalize_ip(overrides.get(key) or default_ip)
        result.append(
            {
                "key": key,
                "device_id": device.id,
                "name": (node.get("device_name") or f"{device.name} / {suffix}") if node is not None else device.name,
                "ip": ip,
                "address_source": "指定地址" if key in overrides else "IPMI 地址",
                "customer": " / ".join(customers[i] for i in ids),
                "location": device.location.name,
                "cabinet": device.cabinet.name,
                "position": f"{device.u_position or '-'}U" + (f" / {suffix}" if node is not None else ""),
            }
        )
    return result


async def inventory(overrides):
    customers = {str(c.id): c.name for c in await CrmCustomer.all()}
    devices = await AssetDevice.all().select_related("cabinet", "location")
    return [target for d in devices for target in device_targets(d, customers, overrides)]


async def view():
    config = await CabinetMonitorConfig.get_or_none(id=1) or CabinetMonitorConfig()
    saved = {r.target_key: r for r in await CabinetMonitorTarget.filter(active=True)}
    rows = []
    for target in await inventory(config.overrides):
        row = saved.get(target["key"])
        current = row and row.metadata.get("ip") == target["ip"]
        excluded = (config.host_policies or {}).get(target["key"], {}).get("excluded", False)
        rows.append(
            {
                **target,
                "status": "excluded" if excluded else row.status if current else "pending",
                "reason": "已手动移除，不再自动纳管" if excluded else row.reason if current else "等待同步",
                "host_id": row.host_id if row and (current or excluded) else "",
                "checked_at": row.checked_at if current else 0,
                "notification_error": row.notification_error if current else "",
            }
        )
    return {
        **{
            key: getattr(config, key)
            for key in (
                "enabled",
                "revision",
                "template_id",
                "group_id",
                "proxy_id",
                "overrides",
                "last_checked",
                "last_error",
            )
        },
        "overrides": {key: value for key, value in config.overrides.items() if key in {r["key"] for r in rows}},
        "rows": rows,
        "counts": dict(Counter(r["status"] for r in rows)),
    }


async def options(client):
    return {
        "templates": await client.call("template.get", {"output": ["templateid", "name"], "search": {"host": "ICMP"}}),
        "groups": await client.call("hostgroup.get", {"output": ["groupid", "name"]}),
        "proxies": await client.call("proxy.get", {"output": ["proxyid", "name"]}),
    }


async def save_config(payload):
    from app.services.monitor_events import ZabbixClient

    valid_keys = {r["key"] for r in await inventory({})}
    if set(payload.overrides) - valid_keys:
        raise HTTPException(422, "设备清单已变化，请刷新后保存")
    async with ZabbixClient() as client:
        choices = await options(client)
        if (
            payload.template_id not in {r["templateid"] for r in choices["templates"]}
            or payload.group_id not in {r["groupid"] for r in choices["groups"]}
            or (payload.proxy_id and payload.proxy_id not in {r["proxyid"] for r in choices["proxies"]})
        ):
            raise HTTPException(422, "主机组、ICMP 模板或代理不存在 / 无权限")
    async with in_transaction():
        await CabinetMonitorConfig.get_or_create(id=1)
        row = await CabinetMonitorConfig.filter(id=1).select_for_update().get()
        if row.lease_until > int(time.time()):
            raise HTTPException(409, "正在同步，请稍后保存")
        if row.revision != payload.revision:
            raise HTTPException(409, "配置已变化，请刷新后保存")
        for key, value in payload.model_dump(exclude={"revision"}).items():
            setattr(row, key, value)
        row.revision += 1
        await row.save()
    await ensure_platform_category()
    return await view()


def host_name(target):
    # Include the address so an inventory address change never silently repoints an existing host.
    digest = hashlib.sha256(f'{target["key"]}:{target["ip"]}'.encode()).hexdigest()[:24]
    return f"finwork-cabinet-{digest}"


def ping_items(items, target_ip, interface_ids, default_interface_matches=False):
    result = []
    for item in items:
        key = item.get("key_", "")
        if str(item.get("status")) != "0" or str(item.get("state", "0")) != "0":
            continue
        if key.split("[", 1)[0] not in {"icmpping", "icmppingloss", "icmppingsec"}:
            continue
        explicit = key.split("[", 1)[1].split(",", 1)[0].rstrip("]").strip('"') if "[" in key else ""
        if explicit in {"{HOST.CONN}", "{HOST.IP}"}:
            if str(item.get("interfaceid")) not in interface_ids and not (
                str(item.get("interfaceid")) == "0" and default_interface_matches
            ):
                continue
        elif explicit:
            if normalize_ip(explicit) != target_ip:
                continue
        elif str(item.get("interfaceid")) not in interface_ids:
            continue
        result.append(item["itemid"])
    return result


async def enrol(client, target, config):
    # Query only inventory addresses and our deterministic technical name, never all Zabbix hosts.
    interfaces = await client.call(
        "hostinterface.get",
        {
            "output": ["hostid", "interfaceid", "ip", "useip"],
            "filter": {"ip": target["ip"], "useip": 1},
        },
    )
    params = {
        "output": ["hostid", "host", "status"],
        "selectInterfaces": ["interfaceid", "ip", "useip", "main", "type"],
        "selectParentTemplates": ["templateid"],
    }
    owned = await client.call("host.get", {**params, "filter": {"host": host_name(target)}})
    candidates = (
        await client.call("host.get", {**params, "hostids": sorted({i["hostid"] for i in interfaces})})
        if interfaces
        else []
    )
    by_id = {h["hostid"]: h for h in candidates + owned}
    if len(by_id) > 1:
        raise HTTPException(422, "同一地址匹配多个 Zabbix 主机，请在 Zabbix 整理重复监控")
    host = next(iter(by_id.values()), None)
    if host and str(host["status"]) != "0":
        raise HTTPException(422, "已有 Zabbix 主机被停用，请先核实停用原因")
    if not host:
        data = {
            "host": host_name(target),
            "name": f'{target["customer"]} · {target["name"]} · {target["ip"]}'[:128],
            "groups": [{"groupid": config.group_id}],
            "templates": [{"templateid": config.template_id}],
            "interfaces": [{"type": 1, "main": 1, "useip": 1, "ip": target["ip"], "dns": "", "port": "10050"}],
            "tags": [{"tag": "managed_by", "value": "FinWork"}, {"tag": "finwork_target", "value": target["key"]}],
            "monitored_by": 1 if config.proxy_id else 0,
        }
        if config.proxy_id:
            data["proxyid"] = config.proxy_id
        created = await client.call("host.create", data)
        host = (await client.call("host.get", {**params, "hostids": created["hostids"]}))[0]
    interface_ids = {
        i["interfaceid"]
        for i in host["interfaces"]
        if normalize_ip(i.get("ip")) == target["ip"] and str(i.get("useip")) == "1"
    }
    main_interfaces = [i for i in host["interfaces"] if str(i.get("main")) == "1"]
    default_interface_matches = bool(main_interfaces) and all(
        i["interfaceid"] in interface_ids for i in main_interfaces
    )
    if not interface_ids:
        raise HTTPException(422, "已有主机的监控地址不匹配，请核实接口")

    async def items():
        return await client.call(
            "item.get",
            {
                "output": ["itemid", "key_", "status", "state", "interfaceid"],
                "hostids": [host["hostid"]],
                "search": {"key_": "icmpping"},
            },
        )

    found = await items()
    ids = ping_items(found, target["ip"], interface_ids, default_interface_matches)
    if not ids and not found:
        templates = {t["templateid"] for t in host.get("parentTemplates", [])}
        if config.template_id not in templates:
            # massadd preserves all unrelated templates/interfaces/proxy configuration.
            await client.call(
                "host.massadd",
                {"hosts": [{"hostid": host["hostid"]}], "templates": [{"templateid": config.template_id}]},
            )
            found = await items()
            ids = ping_items(found, target["ip"], interface_ids, default_interface_matches)
    reachable = {i["itemid"] for i in found if i["key_"].split("[", 1)[0] == "icmpping"}
    if not (set(ids) & reachable):
        raise HTTPException(422, "未找到指向该地址且启用、受支持的 icmpping 监控项，请检查模板 / 接口")
    triggers = await client.call("trigger.get", {"output": ["triggerid"], "itemids": ids, "filter": {"status": 0}})
    if not triggers:
        raise HTTPException(422, "Ping 监控项未关联启用的触发器，无法产生告警")
    return host["hostid"], ids


async def notify_failure(row):
    await notify_failures([row])


async def notify_failures(rows):
    from app.services.monitor_notifications import send_to_user
    from app.utils.feishu_app import feishu_app_enabled

    cabinet = await CabinetMonitorConfig.get_or_none(id=1)
    policies = (cabinet.host_policies or {}) if cabinet else {}
    rows = [r for r in rows if not policies.get(r.target_key, {}).get("excluded")]
    if not rows:
        return
    config = await MonitorNotificationConfig.get_or_none(id=1)
    if not config or not config.enabled or not config.recipient_ids or not feishu_app_enabled():
        for row in rows:
            row.notification_error = "通知未启用或默认接收人 / 飞书未配置"
        return
    now = int(time.time())
    fingerprints = {r.id: hashlib.sha256(f'{r.metadata.get("ip")}:{r.reason}'.encode()).hexdigest()[:16] for r in rows}
    for row in rows:
        row.notification_error = ""
    for user in await User.filter(id__in=config.recipient_ids, is_active=True):
        live = await MonitorNotificationConfig.get_or_none(id=1)
        if not live or not live.enabled or user.id not in live.recipient_ids:
            continue
        key = str(user.id)
        pending = [
            r
            for r in rows
            if r.notified.get(key, {}).get("fingerprint") != fingerprints[r.id]
            or now - r.notified.get(key, {}).get("at", 0) >= 86400
        ]
        if not pending:
            continue
        blocks = []
        for row in pending[:20]:
            lines = [
                f'{label}：{str(row.metadata.get(k) or "未填写")[:160]}'
                for k, label in [
                    ("customer", "客户"),
                    ("name", "设备"),
                    ("location", "机房"),
                    ("cabinet", "机柜"),
                    ("position", "U 位 / 节点"),
                    ("ip", "监控地址"),
                ]
            ]
            blocks.append(
                {"tag": "div", "text": {"tag": "plain_text", "content": "\n".join(lines + [f"原因：{row.reason}"])}}
            )
        card = {
            "config": {"wide_screen_mode": True},
            "header": {
                "template": "orange",
                "title": {"tag": "plain_text", "content": f"客户机器未纳管 · {len(pending)} 台"},
            },
            "elements": blocks
            + [
                {
                    "tag": "div",
                    "text": {
                        "tag": "plain_text",
                        "content": f"共 {len(pending)} 台待处理，本卡片展示前 20 台。完整清单：事件管理 → 监控主机 → 机柜联动",
                    },
                }
            ],
        }
        digest = hashlib.sha256(json.dumps(sorted((r.id, fingerprints[r.id]) for r in pending)).encode()).hexdigest()
        try:
            delivered = await send_to_user(user, card, f"cabinet:{user.id}:{digest}:{now // 86400}")
            if not delivered:
                raise RuntimeError("delivery failed")
            for row in pending:
                row.notified[key] = {"at": now, "fingerprint": fingerprints[row.id]}
        except Exception:
            for row in pending:
                row.notification_error = "飞书发送失败，请检查接收用户及飞书配置；下轮重试"


async def synchronize(force=False, notify=True):
    from app.services.monitor_events import ZabbixClient

    config = await CabinetMonitorConfig.get_or_none(id=1)
    now = int(time.time())
    if not config or not config.enabled:
        return
    await ensure_platform_category()
    if not force and now - config.last_checked < 300:
        return
    token = str(uuid.uuid4())
    claimed = await CabinetMonitorConfig.filter(id=1, lease_until__lte=now).update(
        lease_until=now + 660, lease_token=token
    )
    if not claimed:
        raise HTTPException(409, "机柜监控正在同步")
    config = await CabinetMonitorConfig.get(id=1)
    try:
        async with asyncio.timeout(600):
            targets = await inventory(config.overrides)
            counts = Counter(t["ip"] for t in targets if t["ip"])
            keys = [t["key"] for t in targets]
            await CabinetMonitorTarget.filter(active=True).exclude(target_key__in=keys).update(active=False)
            try:
                async with ZabbixClient() as client:
                    for target in targets:
                        latest = await CabinetMonitorConfig.get(id=1)
                        row, _ = await CabinetMonitorTarget.get_or_create(target_key=target["key"])
                        row.metadata, row.active, row.checked_at = target, True, now
                        if (latest.host_policies or {}).get(target["key"], {}).get("excluded"):
                            row.status, row.reason = "excluded", "已手动移除，不再自动纳管"
                            await row.save()
                            continue
                        row.status, row.reason, row.item_ids, row.host_id = "failed", "", [], ""
                        try:
                            if not target["ip"]:
                                raise HTTPException(422, "缺少有效监控地址，请补充 IPMI 地址或指定监控地址")
                            if counts[target["ip"]] > 1:
                                raise HTTPException(422, "多台客户机器使用相同地址，请核实地址分配")
                            row.host_id, row.item_ids = await enrol(client, target, config)
                            row.status, row.notified, row.notification_error = "managed", {}, ""
                        except HTTPException as exc:
                            row.reason = str(exc.detail)[:300]
                        await row.save()
            except HTTPException as exc:
                # Connection failure is not equivalent to all machines disappearing.
                await CabinetMonitorConfig.filter(id=1).update(last_error=str(exc.detail)[:300])
                for target in targets:
                    row, _ = await CabinetMonitorTarget.get_or_create(target_key=target["key"])
                    row.metadata, row.active = target, True
                    if (config.host_policies or {}).get(target["key"], {}).get("excluded"):
                        row.status, row.reason = "excluded", "已手动移除，不再自动纳管"
                        await row.save()
                        continue
                    row.status, row.reason, row.checked_at = "failed", "无法连接 Zabbix，无法核实或完成纳管", now
                    await row.save()
                if notify:
                    failed = await CabinetMonitorTarget.filter(active=True, status="failed")
                    await notify_failures(failed)
                    for row in failed:
                        await row.save()
                return
            if notify:
                failed = await CabinetMonitorTarget.filter(active=True, status="failed")
                await notify_failures(failed)
                for row in failed:
                    await row.save()
            await CabinetMonitorConfig.filter(id=1).update(last_error="")
    except TimeoutError:
        await CabinetMonitorConfig.filter(id=1).update(last_error="同步超时，下次继续；已完成的设备不会重复创建")
    finally:
        await CabinetMonitorConfig.filter(id=1, lease_token=token).update(
            lease_until=0, lease_token="", last_checked=now
        )


async def effective_settings(base_scope=None):
    from app.services.monitor_event_config import load_settings

    scope = copy.deepcopy(base_scope if base_scope is not None else await load_settings())
    config = await CabinetMonitorConfig.get_or_none(id=1)
    scope["automatic_revision"] = config.revision if config else 0
    if not config or not config.enabled:
        return scope
    current = {t["key"]: t for t in await inventory(config.overrides)}
    selected = {h["hostid"]: h for h in scope["hosts"]}
    if not any(c["key"] == CATEGORY for c in scope["categories"]):
        scope["categories"].append({"key": CATEGORY, "label": "机柜客户机器", "fields": copy.deepcopy(FIELDS)})
    for row in await CabinetMonitorTarget.filter(active=True, status="managed"):
        policy = (config.host_policies or {}).get(row.target_key, {})
        if policy.get("excluded"):
            continue
        target = current.get(row.target_key)
        if not target or target["ip"] != row.metadata.get("ip") or not row.host_id or not row.item_ids:
            continue
        if row.host_id in selected:
            if selected[row.host_id].get("itemids") is not None:
                selected[row.host_id]["itemids"] = sorted(set(selected[row.host_id]["itemids"]) | set(row.item_ids))
        else:
            selected[row.host_id] = {
                "hostid": row.host_id,
                "name": target["name"],
                "category": policy.get("category", CATEGORY),
                "itemids": policy.get("itemids", row.item_ids),
                "attributes": {f["key"]: target[f["key"]] for f in FIELDS} | policy.get("attributes", {}),
                "scope_customized": "itemids" in policy,
            }
    scope["hosts"] = list(selected.values())
    scope["revision"] = hashlib.sha256(
        json.dumps(
            [scope["revision"], config.revision, sorted(scope["hosts"], key=lambda h: h["hostid"])],
            sort_keys=True,
        ).encode()
    ).hexdigest()
    return scope


async def update_host_policy(host_id, revision, selection=None, excluded=None):
    from app.services.monitor_events import ZabbixClient, get_hosts

    targets = await CabinetMonitorTarget.filter(host_id=host_id, active=True)
    if not targets:
        raise HTTPException(404, "未找到自动纳管主机，请刷新列表")
    config = await CabinetMonitorConfig.get_or_none(id=1)
    if not config or config.revision != revision:
        raise HTTPException(409, "机柜联动配置已变化，请刷新后重试")
    if selection is not None:
        scope = await effective_settings()
        category = next((c for c in scope["categories"] if c["key"] == selection.category), None)
        if selection.category is not None and category is None:
            raise HTTPException(422, "分类不存在，请刷新后选择")
        allowed = {f["key"] for f in (category or {}).get("fields", [])}
        if set(selection.attributes) - allowed:
            raise HTTPException(422, "包含不属于所选分类的属性")
        async with ZabbixClient() as client:
            if not await get_hosts(client, [host_id]):
                raise HTTPException(422, "主机已停用、删除或无权限")
            if selection.itemids is not None:
                items = await client.call(
                    "item.get",
                    {
                        "output": ["itemid", "hostid", "status"],
                        "hostids": [host_id],
                        "itemids": selection.itemids,
                        "filter": {"status": 0},
                    },
                )
                valid = {i["itemid"] for i in items if i["hostid"] == host_id and str(i["status"]) == "0"}
                if set(selection.itemids) - valid:
                    raise HTTPException(422, "监控项已停用、不可见或不属于该主机")
    async with in_transaction():
        row = await CabinetMonitorConfig.filter(id=1).select_for_update().get()
        if row.revision != revision:
            raise HTTPException(409, "机柜联动配置已变化，请刷新后重试")
        policies = dict(row.host_policies or {})
        for target in targets:
            policy = dict(policies.get(target.target_key, {}))
            if selection is not None:
                policy.update(category=selection.category, itemids=selection.itemids, attributes=selection.attributes)
            if excluded is not None:
                policy["excluded"] = excluded
            policies[target.target_key] = policy
        row.host_policies = policies
        row.revision += 1
        await row.save(update_fields=["host_policies", "revision", "updated_at"])
    return {"revision": row.revision}


async def update_monitor_items(payload, user_id):
    """Validate once and commit both sources atomically, independent of the enrolment lease."""
    from app.models import MonitorEventConfig
    from app.services.monitor_event_config import load_settings
    from app.services.monitor_events import ZabbixClient, get_hosts

    manual = await load_settings()
    scope = await effective_settings(manual)
    requested = {h.hostid: h.itemids for h in payload.hosts}
    visible = {h["hostid"] for h in scope["hosts"]}
    if set(requested) - visible:
        raise HTTPException(422, "主机已移除或不在纳管范围，请刷新后重试")
    manual_ids = set(requested) & {h["hostid"] for h in manual["hosts"]}
    automatic_ids = set(requested) - manual_ids
    async with ZabbixClient() as client:
        hosts = await get_hosts(client, list(requested))
        if set(requested) - {h["hostid"] for h in hosts}:
            raise HTTPException(422, "选择中包含已删除、停用或无权限的主机")
        item_ids = sorted({item for ids in requested.values() for item in ids or []})
        if item_ids:
            items = await client.call(
                "item.get",
                {
                    "output": ["itemid", "hostid", "status"],
                    "hostids": list(requested),
                    "itemids": item_ids,
                    "filter": {"status": 0},
                },
            )
            valid = {i["itemid"]: i["hostid"] for i in items if str(i.get("status")) == "0"}
            if any(valid.get(item) != host_id for host_id, ids in requested.items() for item in ids or []):
                raise HTTPException(422, "监控项已停用、不可见或不属于所选主机；本次未保存任何修改")
    async with in_transaction():
        event = await MonitorEventConfig.filter(id=1).select_for_update().get()
        if event.revision != payload.revision:
            raise HTTPException(409, "主机配置已变化，请刷新后重试")
        config = await CabinetMonitorConfig.filter(id=1).select_for_update().get_or_none()
        if automatic_ids and (not config or not config.enabled or config.revision != payload.automatic_revision):
            raise HTTPException(409, "自动纳管配置已变化，请刷新后重试")
        if manual_ids:
            event.hosts = [
                {**h, "itemids": requested[h["hostid"]]} if h["hostid"] in manual_ids else h for h in event.hosts
            ]
            event.revision += 1
            event.updated_by_id = user_id
            await event.save(update_fields=["hosts", "revision", "updated_by_id", "updated_at"])
        if automatic_ids:
            targets = await CabinetMonitorTarget.filter(host_id__in=list(automatic_ids), active=True)
            if automatic_ids - {t.host_id for t in targets}:
                raise HTTPException(409, "自动纳管清单已变化，请刷新后重试")
            policies = dict(config.host_policies or {})
            for target in targets:
                policy = dict(policies.get(target.target_key, {}))
                if policy.get("excluded"):
                    raise HTTPException(409, "主机已移除；本次未保存任何修改")
                policy["itemids"] = requested[target.host_id]
                policies[target.target_key] = policy
            config.host_policies = policies
            config.revision += 1
            await config.save(update_fields=["host_policies", "revision", "updated_at"])
    return {"revision": event.revision, "automatic_revision": config.revision if config else 0}
