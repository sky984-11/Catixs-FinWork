import logging
from typing import Any
from urllib.parse import urlparse

import httpx

from app.settings.config import settings

logger = logging.getLogger(__name__)


def zabbix_enabled() -> bool:
    return bool(settings.ZABBIX_URL and settings.ZABBIX_TOKEN)


async def zabbix_call(method: str, params: dict[str, Any]) -> Any:
    if not zabbix_enabled():
        raise RuntimeError("Zabbix URL or token is not configured")

    payload = {
        "jsonrpc": "2.0",
        "method": method,
        "params": params,
        "auth": settings.ZABBIX_TOKEN,
        "id": 1,
    }
    async with httpx.AsyncClient(timeout=20, verify=False, trust_env=False) as client:
        response = await client.post(
            settings.ZABBIX_URL,
            json=payload,
            headers={
                "Content-Type": "application/json-rpc",
                "Authorization": f"Bearer {settings.ZABBIX_TOKEN}",
            },
        )
        if response.status_code in {401, 403}:
            response = await client.post(settings.ZABBIX_URL, json=payload, headers={"Content-Type": "application/json"})
        response.raise_for_status()
        data = response.json()

    if data.get("error"):
        error = data["error"]
        raise RuntimeError(f"{method} failed: {error.get('message')} {error.get('data')}")
    return data.get("result")


def normalize_pve_endpoint(hostname: str) -> tuple[str, str]:
    value = (hostname or "").strip()
    if "://" not in value:
        value = f"https://{value}"
    parsed = urlparse(value)
    host = parsed.hostname or value.split(":", 1)[0]
    port = str(parsed.port or 8006)
    return host, port


def clone_interfaces(reference_interfaces: list[dict[str, Any]], pve_host: str, pve_port: str) -> list[dict[str, Any]]:
    interfaces = []
    for item in reference_interfaces:
        row = {
            "type": int(item.get("type") or 1),
            "main": int(item.get("main") or 1),
            "useip": int(item.get("useip") or 1),
            "ip": pve_host,
            "dns": "" if int(item.get("useip") or 1) else pve_host,
            "port": str(item.get("port") or pve_port),
        }
        if item.get("details"):
            row["details"] = item["details"]
        interfaces.append(row)
    return interfaces


def macro_payload(macro: str, value: str) -> dict[str, str]:
    return {"macro": macro, "value": value}


async def get_reference_host() -> dict[str, Any]:
    result = await zabbix_call(
        "host.get",
        {
            "output": ["hostid", "host", "name"],
            "hostids": [settings.ZABBIX_PVE_REFERENCE_HOSTID],
            "selectGroups": ["groupid"],
            "selectParentTemplates": ["templateid"],
            "selectInterfaces": "extend",
        },
    )
    if not result:
        raise RuntimeError(f"reference host {settings.ZABBIX_PVE_REFERENCE_HOSTID} not found")
    return result[0]


async def find_host(host: str) -> dict[str, Any] | None:
    result = await zabbix_call(
        "host.get",
        {
            "output": ["hostid", "host", "name"],
            "filter": {"host": [host]},
            "selectMacros": ["hostmacroid", "macro", "value"],
        },
    )
    return result[0] if result else None


async def upsert_host_macros(hostid: str, macros: list[dict[str, str]]) -> None:
    host = await zabbix_call(
        "host.get",
        {
            "output": ["hostid"],
            "hostids": [hostid],
            "selectMacros": ["hostmacroid", "macro", "value"],
        },
    )
    existing = {item["macro"]: item for item in (host[0].get("macros") if host else [])}
    for macro in macros:
        current = existing.get(macro["macro"])
        if current:
            await zabbix_call("usermacro.update", {"hostmacroid": current["hostmacroid"], "value": macro["value"]})
        else:
            await zabbix_call("usermacro.create", {"hostid": hostid, **macro})


async def sync_pve_host_to_zabbix(
    remote_id: str,
    hostname: str,
    token_id: str,
    token_secret: str,
) -> dict[str, Any]:
    if not zabbix_enabled():
        return {"enabled": False, "synced": False, "message": "Zabbix is not configured"}

    pve_host, pve_port = normalize_pve_endpoint(hostname)
    host_name = remote_id.strip() or pve_host
    reference = await get_reference_host()
    groups = [{"groupid": item["groupid"]} for item in reference.get("groups", [])]
    templates = [{"templateid": item["templateid"]} for item in reference.get("parentTemplates", [])]
    macros = [
        macro_payload("{$PVE.TOKEN.ID}", token_id),
        macro_payload("{$PVE.TOKEN.SECRET}", token_secret),
        macro_payload("{$PVE.URL.HOST}", pve_host),
        macro_payload("{$PVE.URL.PORT}", pve_port),
    ]

    existing = await find_host(host_name)
    if existing:
        await zabbix_call(
            "host.update",
            {
                "hostid": existing["hostid"],
                "name": host_name,
                "groups": groups,
                "templates": templates,
            },
        )
        await upsert_host_macros(existing["hostid"], macros)
        return {"enabled": True, "synced": True, "created": False, "hostid": existing["hostid"], "host": host_name}

    interfaces = clone_interfaces(reference.get("interfaces", []), pve_host, pve_port)
    payload: dict[str, Any] = {
        "host": host_name,
        "name": host_name,
        "groups": groups,
        "templates": templates,
        "macros": macros,
    }
    if interfaces:
        payload["interfaces"] = interfaces

    result = await zabbix_call("host.create", payload)
    hostids = result.get("hostids") or []
    hostid = hostids[0] if hostids else ""
    return {"enabled": True, "synced": True, "created": True, "hostid": hostid, "host": host_name}
