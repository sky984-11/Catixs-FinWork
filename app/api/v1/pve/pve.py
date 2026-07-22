import asyncio
import ipaddress
import logging
import json
import shlex
import time
import re
from typing import Any
from urllib.parse import quote, urlparse

import httpx
from fastapi import APIRouter, Query, Request, Response
from pydantic import BaseModel

from app.schemas.base import Fail, Success
from app.core.dependency import AuthControl
from app.settings.config import settings
from app.utils.zabbix_api import sync_pve_host_to_zabbix

router = APIRouter()
grafana_router = APIRouter()
logger = logging.getLogger(__name__)

_PDM_RESOURCE_CACHE: list[dict[str, Any]] = []
_PVE_VM_IP_CACHE: dict[tuple[str, str, int], tuple[float, list[str]]] = {}


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


def grafana_base_url() -> str:
    if not settings.GRAFANA_URL:
        raise RuntimeError("Grafana URL is not configured")
    return settings.GRAFANA_URL.rstrip("/")


def grafana_proxy_prefix() -> str:
    return "/api/v1/pve/grafana/proxy"


def rewrite_grafana_html(content: bytes, embed: bool = False) -> bytes:
    prefix = grafana_proxy_prefix()
    text = content.decode("utf-8", errors="replace")
    text = text.replace('<base href="/">', f'<base href="{prefix}/">')
    text = text.replace('"appSubUrl":""', f'"appSubUrl":"{prefix}"')
    text = text.replace('href="/', f'href="{prefix}/')
    text = text.replace('src="/', f'src="{prefix}/')
    if embed:
        embed_style = """
<style id="catixs-grafana-embed-style">
  header,
  aside,
  nav,
  .sidemenu,
  .navbar,
  .page-header,
  .page-toolbar,
  .dashboard-toolbar,
  .dashboard-submenu,
  .submenu-controls,
  .dashboard-controls,
  .drawer,
  .drawer-content,
  .drawerContent,
  .right-side-drawer,
  .right-sidebar,
  .dashboard-right-sidebar,
  .css-1q5rl7h,
  [data-testid="sidemenu"],
  [data-testid="nav-toolbar"],
  [data-testid="dashboard-toolbar"],
  [data-testid="dashboard-submenu"],
  [data-testid="dashboard-drawer"],
  [data-testid="drawer"],
  [data-testid="data-testid NavToolbar"],
  [aria-label="Download"],
  [aria-label="Inspect"],
  [aria-label="Panel inspector"],
  [aria-label="Right sidebar"],
  [aria-label="Dashboard actions"],
  [aria-label="Dashboard controls"],
  [class*="Drawer"],
  [class*="drawer"],
  [class*="RightSidebar"],
  [class*="RightSide"],
  [class*="NavToolbar"],
  [class*="DashboardToolbar"],
  [class*="DashboardSubMenu"],
  [class*="SubMenu"],
  nav[aria-label="Main menu"] {
    display: none !important;
  }
  body.catixs-grafana-embed header,
  body.catixs-grafana-embed nav,
  body.catixs-grafana-embed aside,
  body.catixs-grafana-embed .catixs-grafana-hidden {
    display: none !important;
  }
  body.catixs-grafana-embed [style*="right: 0px"],
  body.catixs-grafana-embed [style*="right:0px"] {
    display: none !important;
  }
  body.catixs-grafana-embed {
    overflow: auto !important;
  }
  html,
  body.catixs-grafana-embed,
  body.catixs-grafana-embed #reactRoot,
  body.catixs-grafana-embed .grafana-app,
  body.catixs-grafana-embed main {
    margin: 0 !important;
    padding: 0 !important;
  }
  .main-view,
  .page-container,
  .dashboard-container,
  .dashboard-page,
  .dashboard-content,
  .dashboard-scroll,
  .scrollbar-view,
  .view,
  [data-testid="dashboard-scene"],
  [data-testid="dashboard-container"],
  [class*="Page"] {
    margin: 0 !important;
    padding: 0 !important;
    padding-right: 0 !important;
    inset: auto !important;
    right: auto !important;
    max-width: none !important;
    width: 100% !important;
  }
  .react-grid-layout,
  [data-testid="dashboard-canvas"] {
    margin: 0 !important;
    padding: 0 !important;
    width: 100% !important;
  }
  footer,
  [class*="Footer"],
  [class*="footer"],
  [aria-label="Grafana"] {
    display: none !important;
  }
</style>
<script id="catixs-grafana-embed-script">
(() => {
  const hideElement = (element) => {
    if (element && element.style) {
      element.classList.add('catixs-grafana-hidden')
      element.style.setProperty('display', 'none', 'important')
    }
  }
  const hideCompactParent = (element) => {
    let current = element
    for (let i = 0; current && i < 6; i += 1) {
      const height = current.getBoundingClientRect?.().height || 0
      const width = current.getBoundingClientRect?.().width || 0
      if (height > 0 && height < 150 && width > window.innerWidth * 0.35) {
        hideElement(current)
        return
      }
      current = current.parentElement
    }
  }
  const resetBox = (element) => {
    if (!element?.style) return
    element.style.setProperty('margin', '0', 'important')
    element.style.setProperty('padding', '0', 'important')
    element.style.setProperty('padding-right', '0', 'important')
    element.style.setProperty('right', 'auto', 'important')
    element.style.setProperty('max-width', 'none', 'important')
    element.style.setProperty('width', '100%', 'important')
  }
  const tightenDashboard = () => {
    document
      .querySelectorAll([
        'main',
        '#reactRoot',
        '.grafana-app',
        '.main-view',
        '.page-container',
        '.dashboard-container',
        '.dashboard-page',
        '.dashboard-content',
        '.dashboard-scroll',
        '.scrollbar-view',
        '.react-grid-layout',
        '[data-testid="dashboard-scene"]',
        '[data-testid="dashboard-container"]',
        '[data-testid="dashboard-canvas"]'
      ].join(','))
      .forEach(resetBox)

    const canvas = document.querySelector('[data-testid="dashboard-canvas"], .react-grid-layout')
    let current = canvas?.parentElement
    for (let i = 0; current && i < 8; i += 1) {
      resetBox(current)
      current = current.parentElement
    }
  }
  const hideRightChrome = () => {
    const rightLimit = window.innerWidth - 180
    document.querySelectorAll('div, aside, section, button').forEach((element) => {
      const rect = element.getBoundingClientRect?.()
      if (!rect || rect.width <= 0 || rect.height <= 0) return
      const text = (element.innerText || element.getAttribute?.('aria-label') || '').replace(/\\s+/g, ' ')
      const isRightRail = rect.left > rightLimit && rect.width < 130 && rect.height > 120
      const hasRightToolText = ['Download', 'Inspect', 'Panel inspector', 'Drawer', 'List view'].some((value) =>
        text.includes(value)
      )
      const hasRightToolButton = element.querySelector?.(
        '[aria-label="Download"], [aria-label="Inspect"], [aria-label="Panel inspector"], [data-testid*="drawer"], [class*="Drawer"], [class*="drawer"]'
      )
      if (isRightRail || hasRightToolText || hasRightToolButton) {
        hideCompactParent(element)
        hideElement(element)
      }
    })
  }
  const hideGrafanaChrome = () => {
    document.body?.classList.add('catixs-grafana-embed')
    document
      .querySelectorAll([
        'header',
        'aside',
        'nav',
        '.sidemenu',
        '.navbar',
        '.page-header',
        '.page-toolbar',
        '.dashboard-toolbar',
        '.dashboard-submenu',
        '.submenu-controls',
        '.drawer',
        '.drawer-content',
        '.drawerContent',
        '.right-side-drawer',
        '.right-sidebar',
        '.dashboard-right-sidebar',
        '[data-testid="sidemenu"]',
        '[data-testid="nav-toolbar"]',
        '[data-testid="dashboard-toolbar"]',
        '[data-testid="dashboard-submenu"]',
        '[data-testid="dashboard-drawer"]',
        '[data-testid="drawer"]',
        '[aria-label="Download"]',
        '[aria-label="Inspect"]',
        '[aria-label="Panel inspector"]',
        '[aria-label="Right sidebar"]',
        '[class*="Drawer"]',
        '[class*="drawer"]',
        '[class*="RightSidebar"]',
        '[class*="RightSide"]',
        '[class*="NavToolbar"]',
        '[class*="DashboardToolbar"]',
        '[class*="DashboardSubMenu"]',
        '[class*="SubMenu"]'
      ].join(','))
      .forEach(hideElement)

    document.querySelectorAll('div, section').forEach((element) => {
      const text = (element.innerText || '').replace(/\\s+/g, ' ')
      if (
        (text.includes('Datasource') && text.includes('Group') && text.includes('Host')) ||
        (text.includes('PVE') && text.includes('ctrl+k')) ||
        (text.includes('Refresh') && text.includes('Share')) ||
        (text.includes('Datasource') && text.includes('Item tag'))
      ) {
        hideCompactParent(element)
      }
    })
    hideRightChrome()
    tightenDashboard()
  }
  hideGrafanaChrome()
  window.addEventListener('load', hideGrafanaChrome)
  setInterval(hideGrafanaChrome, 500)
  new MutationObserver(hideGrafanaChrome).observe(document.documentElement, {
    childList: true,
    subtree: true
  })
})()
</script>
"""
        if "</head>" in text:
            text = text.replace("</head>", f"{embed_style}</head>", 1)
        else:
            text = f"{embed_style}{text}"
    return text.encode("utf-8")


def pve_api_host(hostname: str) -> str:
    value = hostname.strip()
    if not value or "://" in value or ":" in value:
        return value
    return f"{value}:8006"


def pve_remote_node_entry(hostname: str, fingerprint: str | None = None) -> str:
    value = hostname.strip()
    if "://" in value:
        parsed = urlparse(value)
        value = parsed.netloc or parsed.path
    value = value.split("/", 1)[0]
    if value.endswith(":8006"):
        value = value[:-5]
    if fingerprint:
        return f"{value},fingerprint={fingerprint.strip()}"
    return value


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


def pve_zabbix_token_id(authid: str, create_token: str | None = None) -> str:
    value = (authid or "").strip()
    token_name = (create_token or "").strip()
    if token_name and "!" not in value:
        return f"{value}!{token_name}"
    return value


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


async def pdm_remote_list() -> list[str]:
    remotes = configured_remotes()
    if remotes:
        return remotes

    data = await pdm_get_first(["/remotes/remote", "/config/remotes", "/pve/remotes", "/remotes"], timeout=3)
    remotes = [remote_id(item) for item in list_data(data)]
    return sorted({remote for remote in remotes if remote})


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
    configs: list[dict[str, Any]] = []
    for path in ("/remotes/remote", "/config/remotes", "/pve/remotes", "/remotes"):
        try:
            data = await pdm_get(path, timeout=3)
        except Exception:
            continue
        configs = [item for item in list_data(data) if isinstance(item, dict)]
        if configs:
            return configs
    return configs


async def pdm_remote_config_detail_map() -> dict[str, dict[str, Any]]:
    details: dict[str, dict[str, Any]] = {}
    for item in await pdm_remote_configs():
        remote = remote_id(item)
        if not remote:
            continue
        nodes = item.get("nodes") if isinstance(item.get("nodes"), list) else []
        parsed = parse_remote_node_entry(nodes[0]) if nodes else {"host": remote_config_address(item), "fingerprint": ""}
        details[remote] = {
            "config": item,
            "address": parsed.get("host") or remote_config_address(item),
            "fingerprint": parsed.get("fingerprint", ""),
        }
    return details


async def pdm_remote_config_map() -> dict[str, str]:
    configs: dict[str, str] = {}
    for remote, detail in (await pdm_remote_config_detail_map()).items():
        address = str(detail.get("address") or "")
        if address:
            configs[remote] = address
    return configs


def resource_node_names(resources: list[dict[str, Any]]) -> list[str]:
    return sorted(
        {
            str(item.get("node") or "")
            for item in resources
            if canonical_resource_type(item.get("type")) == "pve-node" and item.get("node")
        }
    )


def network_address_from_items(items: list[dict[str, Any]]) -> str:
    candidates: list[tuple[int, str]] = []
    for item in items:
        if canonical_resource_type(item.get("type")) not in {"pve-network", "network"}:
            continue
        if item.get("type") not in {"bridge", "pve-network", "network"} and item.get("type") != "pve-network":
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


async def pdm_remote_network_address(remote: str, resources: list[dict[str, Any]]) -> str:
    address = network_address_from_items(resources)
    if address:
        return address

    candidates: list[tuple[int, str]] = []
    for node in resource_node_names(resources):
        try:
            networks = await pdm_get(f"/pve/remotes/{remote}/nodes/{node}/network", timeout=3)
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


async def pdm_remote_address_map(data: list[dict[str, Any]], remote_configs: dict[str, str]) -> dict[str, str]:
    address_map: dict[str, str] = {}
    pending: list[tuple[str, list[dict[str, Any]]]] = []

    for group in data:
        remote = str(group.get("remote") or "")
        if not remote:
            continue
        config_address = remote_configs.get(remote, "")
        if config_address and is_ip_address(config_address):
            address_map[remote] = strip_cidr(config_address)
            continue
        if is_ip_address(remote):
            address_map[remote] = strip_cidr(remote)
            continue
        pending.append((remote, group.get("resources") or []))

    results = await asyncio.gather(
        *(pdm_remote_network_address(remote, resources) for remote, resources in pending),
        return_exceptions=True,
    )
    for (remote, _), result in zip(pending, results):
        if isinstance(result, str) and result:
            address_map[remote] = result

    return address_map


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


async def pdm_put(path: str, payload: dict[str, Any]) -> Any:
    headers = {"Authorization": pdm_auth_header(), "Accept": "application/json"}
    async with httpx.AsyncClient(timeout=settings.PDM_TIMEOUT, verify=False, trust_env=False) as client:
        response = await client.put(pdm_api_url(path), json=payload, headers=headers)
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise RuntimeError(f"PDM API HTTP {response.status_code}: {response.text[:500]}") from exc
        data = response.json()
    return data.get("data")


async def pdm_delete(path: str) -> Any:
    headers = {"Authorization": pdm_auth_header(), "Accept": "application/json"}
    async with httpx.AsyncClient(timeout=settings.PDM_TIMEOUT, verify=False, trust_env=False) as client:
        response = await client.delete(pdm_api_url(path), headers=headers)
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


class VMDeleteRequest(BaseModel):
    remote: str
    vmid: int
    type: str = "pve-qemu"
    node: str | None = None
    status: str | None = None


class VMPowerRequest(BaseModel):
    remote: str
    vmid: int
    type: str = "pve-qemu"
    node: str | None = None
    action: str


class VMNetworkDeviceRequest(BaseModel):
    key: str | None = None
    model: str = "virtio"
    macaddr: str | None = None
    bridge: str = "vmbr10"
    vlan: int | None = None
    mtu: int | None = None
    rate: float | None = None
    firewall: bool = False
    delete: bool = False


class VMConfigUpdateRequest(BaseModel):
    remote: str
    vmid: int
    type: str = "pve-qemu"
    node: str | None = None
    cores: int | None = None
    memory_gb: float | None = None
    disk_gb: float | None = None
    disk_key: str | None = None
    networks: list[VMNetworkDeviceRequest] = []


class PDMAddRemoteRequest(BaseModel):
    hostname: str
    authid: str | None = None
    token: str | None = None
    fingerprint: str | None = None
    remote_id: str | None = None
    create_token: str | None = None
    web_url: str | None = None


class PDMProbeRemoteRequest(BaseModel):
    hostname: str
    fingerprint: str | None = None


class PDMUpdateRemoteRequest(BaseModel):
    hostname: str
    fingerprint: str | None = None
    original_hostname: str | None = None


class PDMRemoteRemarkRequest(BaseModel):
    remark: str = ""
    host: str | None = None


def percent(value: Any) -> float:
    try:
        number = float(value or 0)
    except (TypeError, ValueError):
        return 0
    if number <= 1:
        return round(number * 100, 2)
    return round(number, 2)


def first_text_value(items: list[dict[str, Any]], keys: tuple[str, ...]) -> str:
    for item in items:
        for key in keys:
            value = item.get(key)
            if value:
                return str(value)
    return ""


def number_value(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0


def node_resource_summary(nodes: list[dict[str, Any]]) -> dict[str, Any]:
    cpu_total = sum(number_value(item.get("maxcpu")) for item in nodes)
    cpu_weighted = sum(number_value(item.get("cpu")) * number_value(item.get("maxcpu")) for item in nodes)
    cpu_avg = sum(number_value(item.get("cpu")) for item in nodes) / len(nodes) if nodes else 0
    cpu_ratio = cpu_weighted / cpu_total if cpu_total else cpu_avg

    mem = sum(number_value(item.get("mem")) for item in nodes)
    maxmem = sum(number_value(item.get("maxmem")) for item in nodes)
    disk = sum(number_value(item.get("disk")) for item in nodes)
    maxdisk = sum(number_value(item.get("maxdisk")) for item in nodes)

    return {
        "cpu_usage": percent(cpu_ratio),
        "cpu_total": int(cpu_total),
        "mem": int(mem),
        "maxmem": int(maxmem),
        "mem_usage": round(mem / maxmem * 100, 2) if maxmem else 0,
        "disk": int(disk),
        "maxdisk": int(maxdisk),
        "disk_usage": round(disk / maxdisk * 100, 2) if maxdisk else 0,
    }


def node_status_summary(statuses: list[dict[str, Any]]) -> dict[str, Any]:
    if not statuses:
        return {}

    cpu_total = sum(number_value(item.get("cpuinfo", {}).get("cpus") or item.get("maxcpu")) for item in statuses)
    cpu_weighted = sum(
        number_value(item.get("cpu")) * number_value(item.get("cpuinfo", {}).get("cpus") or item.get("maxcpu"))
        for item in statuses
    )
    cpu_avg = sum(number_value(item.get("cpu")) for item in statuses) / len(statuses)
    cpu_ratio = cpu_weighted / cpu_total if cpu_total else cpu_avg

    mem = sum(number_value((item.get("memory") or {}).get("used") or item.get("mem")) for item in statuses)
    maxmem = sum(number_value((item.get("memory") or {}).get("total") or item.get("maxmem")) for item in statuses)
    disk = sum(number_value((item.get("rootfs") or {}).get("used") or item.get("disk")) for item in statuses)
    maxdisk = sum(number_value((item.get("rootfs") or {}).get("total") or item.get("maxdisk")) for item in statuses)

    return {
        "cpu_usage": percent(cpu_ratio),
        "cpu_total": int(cpu_total),
        "mem": int(mem),
        "maxmem": int(maxmem),
        "mem_usage": round(mem / maxmem * 100, 2) if maxmem else 0,
        "disk": int(disk),
        "maxdisk": int(maxdisk),
        "disk_usage": round(disk / maxdisk * 100, 2) if maxdisk else 0,
    }


async def pdm_remote_node_status_summary(remote: str, resources: list[dict[str, Any]]) -> dict[str, Any]:
    statuses: list[dict[str, Any]] = []
    for node in resource_node_names(resources):
        try:
            status = await pdm_get(f"/pve/remotes/{remote}/nodes/{node}/status", timeout=3)
        except Exception:
            continue
        if isinstance(status, dict):
            statuses.append(status)
    return node_status_summary(statuses)


async def pdm_remote_summary_map(data: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    tasks: list[Any] = []
    remotes: list[str] = []
    for group in data:
        remote = str(group.get("remote") or "")
        if not remote:
            continue
        remotes.append(remote)
        tasks.append(pdm_remote_node_status_summary(remote, group.get("resources") or []))

    results = await asyncio.gather(*tasks, return_exceptions=True)
    summaries: dict[str, dict[str, Any]] = {}
    for remote, result in zip(remotes, results):
        if isinstance(result, dict) and result:
            summaries[remote] = result
    return summaries


def resource_groups(
    data: list[dict[str, Any]],
    remote_configs: dict[str, str] | None = None,
    remote_summaries: dict[str, dict[str, Any]] | None = None,
    remote_details: dict[str, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    groups: list[dict[str, Any]] = []
    remote_configs = remote_configs or {}
    remote_summaries = remote_summaries or {}
    remote_details = remote_details or {}
    for group in data:
        resources = group.get("resources") or []
        remote = str(group.get("remote") or "")
        has_resources = bool(resources)
        queried = bool(group.get("queried")) or has_resources
        vms = [item for item in resources if canonical_resource_type(item.get("type")) in {"pve-qemu", "pve-lxc"}]
        nodes = [item for item in resources if canonical_resource_type(item.get("type")) == "pve-node"]
        online_nodes = [item for item in nodes if item.get("status") == "online"]
        node_summary = {**node_resource_summary(nodes), **remote_summaries.get(remote, {})}
        address = remote_configs.get(remote) or first_text_value(
            [group, *nodes, *resources],
            ("ip", "address", "host", "hostname", "endpoint", "server"),
        )
        groups.append(
            {
                "id": remote,
                "label": remote,
                "value": remote,
                "remote": remote,
                "ip": address,
                "address": address,
                "fingerprint": remote_details.get(remote, {}).get("fingerprint") or "",
                "status": "online" if online_nodes or (queried and not group.get("error")) else "unknown",
                "node_count": len(nodes),
                "online_node_count": len(online_nodes),
                "vm_count": len(vms) if queried else None,
                "error": group.get("error") or "",
                "queried": queried,
                "cpu": node_summary["cpu_usage"],
                **node_summary,
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
    remark = (
        item.get("description")
        or item.get("comment")
        or item.get("comments")
        or item.get("notes")
        or item.get("remark")
        or ""
    )
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
        "remark": str(remark),
        "ips": [],
        "ip_addresses": [],
        "primary_ip": "",
    }


def vm_cpu_topology(config: dict[str, Any]) -> tuple[int, int, int]:
    cores = max(1, int(float(config.get("cores") or config.get("vcpus") or 1)))
    sockets = max(1, int(float(config.get("sockets") or 1)))
    return cores, sockets, cores * sockets


def guest_agent_ips_from_payload(data: Any) -> list[str]:
    interfaces = data.get("result") if isinstance(data, dict) else data
    if not isinstance(interfaces, list):
        return []

    ips: list[str] = []
    for interface in interfaces:
        if not isinstance(interface, dict):
            continue
        if str(interface.get("name") or "").lower() == "lo":
            continue
        for item in interface.get("ip-addresses") or []:
            if not isinstance(item, dict):
                continue
            address = str(item.get("ip-address") or "").strip()
            if not address or address in {"127.0.0.1", "::1"}:
                continue
            if address.startswith("169.254.") or address.lower().startswith("fe80:"):
                continue
            if address not in ips:
                ips.append(address)
    return ips


async def fetch_vm_guest_agent_ips(vm: dict[str, Any], host: str = "") -> list[str]:
    if vm.get("type") != "pve-qemu" or vm.get("status") != "running" or not vm.get("vmid"):
        return []

    cache_key = (
        str(vm.get("remote") or ""),
        str(vm.get("node") or ""),
        int(vm.get("vmid") or 0),
    )
    cached = _PVE_VM_IP_CACHE.get(cache_key)
    cache_ttl = max(0, float(settings.PVE_GUEST_AGENT_IP_CACHE_TTL or 0))
    if cached and cache_ttl and time.time() - cached[0] <= cache_ttl:
        return list(cached[1])

    if not host:
        try:
            host = await pdm_remote_config_host(str(vm.get("remote") or ""))
        except Exception:
            host = ""
    if not host:
        return []

    node = str(vm.get("node") or "")
    node_path = shlex.quote(node) if node else "$(hostname -s)"
    timeout_seconds = max(1, min(int(settings.PVE_GUEST_AGENT_IP_TIMEOUT or 2), 10))
    command = (
        f"timeout {timeout_seconds}s "
        f"pvesh get /nodes/{node_path}/qemu/{int(vm['vmid'])}/agent/network-get-interfaces "
        "--output-format json"
    )
    code, output, error = await asyncio.to_thread(ssh_execute_pve, host, command)
    if code != 0:
        logger.debug("Failed to read guest agent IPs for VM %s: %s", vm.get("vmid"), error or output)
        return []
    try:
        ips = guest_agent_ips_from_payload(json.loads(output or "[]"))
        _PVE_VM_IP_CACHE[cache_key] = (time.time(), ips)
        return ips
    except Exception as exc:
        logger.debug("Failed to parse guest agent IPs for VM %s: %s", vm.get("vmid"), exc)
        return []


async def enrich_vm_ips(vms: list[dict[str, Any]]) -> None:
    pending = [vm for vm in vms if vm.get("type") == "pve-qemu" and vm.get("status") == "running"]
    if not pending:
        return

    remote_hosts: dict[str, str] = {}
    for remote in sorted({str(vm.get("remote") or "") for vm in pending if vm.get("remote")}):
        try:
            remote_hosts[remote] = await pdm_remote_config_host(remote)
        except Exception as exc:
            logger.debug("Failed to resolve PVE host for %s: %s", remote, exc)

    semaphore = asyncio.Semaphore(8)

    async def load(vm: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
        async with semaphore:
            host = remote_hosts.get(str(vm.get("remote") or ""), "")
            return vm, await fetch_vm_guest_agent_ips(vm, host)

    results = await asyncio.gather(*(load(vm) for vm in pending), return_exceptions=True)
    for result in results:
        if isinstance(result, Exception):
            logger.debug("Failed to enrich VM IPs: %s", result)
            continue
        vm, ips = result
        vm["ips"] = ips
        vm["ip_addresses"] = ips
        vm["primary_ip"] = ips[0] if ips else ""


def vm_remark_from_config(data: Any) -> str:
    if not isinstance(data, dict):
        return ""
    for key in ("description", "comment", "comments", "notes", "remark"):
        value = data.get(key)
        if value:
            return str(value)
    return ""


def parse_qemu_kv(value: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for part in str(value or "").split(","):
        if "=" not in part:
            continue
        key, item_value = part.split("=", 1)
        result[key.strip()] = item_value.strip()
    return result


def parse_qemu_size_gb(value: str) -> float:
    size = parse_qemu_kv(value).get("size", "")
    match = re.match(r"^([\d.]+)\s*([kmgtp]?i?b?|[kmgtp])?$", str(size).strip(), re.I)
    if not match:
        return 0
    number = float(match.group(1))
    unit = (match.group(2) or "g").lower().replace("ib", "").replace("b", "")
    factors = {"": 1 / 1024 / 1024 / 1024, "k": 1 / 1024 / 1024, "m": 1 / 1024, "g": 1, "t": 1024, "p": 1024 * 1024}
    return round(number * factors.get(unit, 1), 2)


def vm_disk_devices(config: dict[str, Any]) -> list[dict[str, Any]]:
    disks: list[dict[str, Any]] = []
    for key, value in config.items():
        if not re.match(r"^(scsi|virtio|sata|ide)\d+$", str(key)):
            continue
        text = str(value or "")
        if "media=cdrom" in text or "cloudinit" in text:
            continue
        disks.append({"key": str(key), "value": text, "size_gb": parse_qemu_size_gb(text)})
    return sorted(disks, key=lambda item: item["key"])


def vm_network_devices(config: dict[str, Any]) -> list[dict[str, Any]]:
    networks: list[dict[str, Any]] = []
    for key, value in config.items():
        if not re.match(r"^net\d+$", str(key)):
            continue
        text = str(value or "")
        first, *rest = text.split(",", 1)
        model = "virtio"
        macaddr = ""
        if "=" in first:
            model, macaddr = first.split("=", 1)
        options = parse_qemu_kv(rest[0] if rest else "")
        networks.append(
            {
                "key": str(key),
                "model": model or "virtio",
                "macaddr": macaddr,
                "bridge": options.get("bridge") or "vmbr10",
                "vlan": int(options["tag"]) if str(options.get("tag") or "").isdigit() else None,
                "mtu": int(options["mtu"]) if str(options.get("mtu") or "").isdigit() else None,
                "rate": float(options["rate"]) if str(options.get("rate") or "").replace(".", "", 1).isdigit() else None,
                "firewall": str(options.get("firewall") or "0") == "1",
                "raw": text,
            }
        )
    return sorted(networks, key=lambda item: item["key"])


def qemu_net_value(network: VMNetworkDeviceRequest) -> str:
    model = (network.model or "virtio").strip()
    macaddr = (network.macaddr or "").strip()
    head = f"{model}={macaddr}" if macaddr else model
    parts = [head, f"bridge={(network.bridge or 'vmbr10').strip()}"]
    if network.vlan is not None:
        parts.append(f"tag={int(network.vlan)}")
    if network.mtu is not None and int(network.mtu) > 0:
        parts.append(f"mtu={int(network.mtu)}")
    if network.rate is not None and float(network.rate) > 0:
        parts.append(f"rate={float(network.rate):g}")
    if network.firewall:
        parts.append("firewall=1")
    return ",".join(parts)


def qemu_hotplug_without_network(value: Any) -> str:
    items = [item.strip() for item in str(value or "disk,network,usb").split(",") if item.strip()]
    filtered = [item for item in items if item != "network"]
    return ",".join(filtered) or "0"


def next_net_key(existing: set[str]) -> str:
    for index in range(32):
        key = f"net{index}"
        if key not in existing:
            return key
    raise RuntimeError("No free network slot")


async def vm_config_from_pve(remote: str, vmid: int, vm_type: str = "pve-qemu") -> tuple[str, dict[str, Any]]:
    host = await pdm_remote_config_host(remote)
    if not host:
        raise RuntimeError("PVE node IP not found")
    kind = guest_kind(vm_type)
    command = f"pvesh get /nodes/$(hostname -s)/{kind}/{int(vmid)}/config --output-format json"
    code, output, error = await asyncio.to_thread(ssh_execute_pve, host, command)
    if code != 0:
        raise RuntimeError(error or output or "Failed to read VM config")
    return host, json.loads(output or "{}")


async def fetch_vm_config_remark(vm: dict[str, Any]) -> str:
    remote = str(vm.get("remote") or "")
    vmid = vm.get("vmid")
    if not remote or not vmid:
        return ""

    kind = guest_kind(str(vm.get("type") or ""))
    node = str(vm.get("node") or "")
    paths = [f"/pve/remotes/{remote}/{kind}/{vmid}/config"]
    if node:
        paths.append(f"/pve/remotes/{remote}/nodes/{node}/{kind}/{vmid}/config")

    for path in paths:
        try:
            remark = vm_remark_from_config(await pdm_get(path, timeout=3))
        except Exception:
            continue
        if remark:
            return remark

    try:
        host = await pdm_remote_config_host(remote)
    except Exception:
        host = ""
    if not host:
        return ""

    command = f"pvesh get /nodes/$(hostname -s)/{kind}/{int(vmid)}/config --output-format json"
    code, output, _error = await asyncio.to_thread(ssh_execute_pve, host, command)
    if code != 0:
        return ""
    try:
        return vm_remark_from_config(json.loads(output or "{}"))
    except Exception:
        return ""
    return ""


async def enrich_vm_remarks(vms: list[dict[str, Any]]) -> None:
    pending = [vm for vm in vms if not str(vm.get("remark") or "").strip()]
    if not pending:
        return

    results = await asyncio.gather(*(fetch_vm_config_remark(vm) for vm in pending), return_exceptions=True)
    for vm, result in zip(pending, results):
        if isinstance(result, str) and result:
            vm["remark"] = result


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
            used_vmids = sorted(
                {
                    int(item.get("vmid"))
                    for item in resources
                    if canonical_resource_type(item.get("type")) in {"pve-qemu", "pve-lxc"}
                    and str(item.get("vmid") or "").isdigit()
                }
            )
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
                "used_vmids": used_vmids,
            }
    return {
        "remote": remote,
        "nodes": [],
        "storages": [],
        "networks": [],
        "endpoints": [],
        "used_vmids": [],
    }


def next_available_vmid(used_vmids: list[int], preferred: int | None = None) -> int:
    used = {int(vmid) for vmid in used_vmids if int(vmid) >= 100}
    if preferred is not None and int(preferred) >= 100 and int(preferred) not in used:
        return int(preferred)

    candidate = 100
    while candidate in used:
        candidate += 1
    return candidate


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


async def pdm_remote_config(remote: str) -> dict[str, Any]:
    for item in await pdm_remote_configs():
        if remote_id(item) == remote:
            return dict(item)
    raise RuntimeError(f"PDM Remote not found: {remote}")


async def resolve_pdm_remote_config(remote: str, *hosts: str | None) -> tuple[str, dict[str, Any]]:
    configs = await pdm_remote_configs()
    for item in configs:
        item_id = remote_id(item)
        if item_id == remote:
            return item_id, dict(item)

    host_candidates = {strip_cidr(str(host or "")).strip() for host in hosts if str(host or "").strip()}
    host_candidates.discard("")
    if host_candidates:
        for item in configs:
            address = strip_cidr(remote_config_address(item))
            if address and address in host_candidates:
                item_id = remote_id(item)
                if item_id:
                    return item_id, dict(item)

    raise RuntimeError(f"PDM Remote not found: {remote}")


async def pdm_remote_config_host(remote: str) -> str:
    config = await pdm_remote_config(remote)
    nodes = config.get("nodes") if isinstance(config.get("nodes"), list) else []
    if nodes:
        return parse_remote_node_entry(nodes[0]).get("host", "")
    return remote_config_address(config)


async def resolve_remark_host(remote: str, fallback_host: str | None = None) -> str:
    try:
        host = await pdm_remote_config_host(remote)
    except Exception:
        host = ""
    return host or (fallback_host or "").strip()


def ssh_execute_pve(host: str, command: str) -> tuple[int, str, str]:
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
        transport = client.get_transport()
        if transport is None:
            return -1, "", "SSH transport is not available"
        channel = transport.open_session(timeout=settings.PVE_CREATE_SSH_TIMEOUT)
        channel.settimeout(settings.PVE_CREATE_SSH_TIMEOUT)
        channel.exec_command(command)
        stdout_chunks: list[bytes] = []
        stderr_chunks: list[bytes] = []
        while True:
            while channel.recv_ready():
                stdout_chunks.append(channel.recv(65535))
            while channel.recv_stderr_ready():
                stderr_chunks.append(channel.recv_stderr(65535))
            if channel.exit_status_ready():
                exit_status = channel.recv_exit_status()
                while channel.recv_ready():
                    stdout_chunks.append(channel.recv(65535))
                while channel.recv_stderr_ready():
                    stderr_chunks.append(channel.recv_stderr(65535))
                break
            time.sleep(0.05)
        output = b"".join(stdout_chunks).decode("utf-8", errors="replace")
        error = b"".join(stderr_chunks).decode("utf-8", errors="replace")
        channel.close()
        return exit_status, output, error
    except Exception as exc:
        return -1, "", str(exc)
    finally:
        client.close()


@router.get("/nodes", summary="PDM remote list")
async def list_nodes():
    try:
        data = await pdm_nodes_list()
        remote_details = await pdm_remote_config_detail_map()
        remote_configs = {
            remote: str(detail.get("address") or "")
            for remote, detail in remote_details.items()
            if detail.get("address")
        }
        remote_addresses = await pdm_remote_address_map(data, remote_configs)
        remote_summaries = await pdm_remote_summary_map(data)
    except Exception as exc:
        return Fail(msg=f"读取 PDM 数据失败: {error_detail(exc)}")
    return Success(data=resource_groups(data, remote_addresses, remote_summaries, remote_details))


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
    await enrich_vm_remarks(vms)
    vms.sort(key=lambda row: (str(row.get("remote") or ""), str(row.get("node") or ""), int(row.get("vmid") or 0)))
    summary = {
        "total": len(vms),
        "running": len([vm for vm in vms if vm.get("status") == "running"]),
        "stopped": len([vm for vm in vms if vm.get("status") == "stopped"]),
    }
    return Success(data={"items": vms, "summary": summary})


@router.get("/vms/ips", summary="PVE virtual machine guest-agent IP list")
async def list_vm_ips(
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
        return Fail(msg=f"读取 PVE 虚拟机 IP 失败: {error_detail(exc)}")

    vms = all_vms(data)
    if node:
        vms = [vm for vm in vms if vm.get("remote") == node]
    await enrich_vm_ips(vms)
    items = [
        {
            "remote": vm.get("remote") or "",
            "node": vm.get("node") or "",
            "vmid": vm.get("vmid"),
            "type": vm.get("type") or "",
            "ips": vm.get("ips") or [],
            "ip_addresses": vm.get("ip_addresses") or [],
            "primary_ip": vm.get("primary_ip") or "",
        }
        for vm in vms
    ]
    return Success(data={"items": items})


@grafana_router.api_route(
    "/grafana/proxy/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    summary="Proxy Grafana with service account token",
)
async def grafana_proxy(path: str, request: Request, token: str = Query("")):
    auth_token = token or request.cookies.get("grafana_proxy_token", "")
    try:
        await AuthControl.is_authed(token=auth_token)
    except Exception:
        return Response("Unauthorized", status_code=401)

    if not settings.GRAFANA_API_TOKEN:
        return Response("Grafana token is not configured", status_code=500)

    target_url = f"{grafana_base_url()}/{path.lstrip('/')}"
    upstream_params = [(key, value) for key, value in request.query_params.multi_items() if key != "token"]

    headers = {
        "Authorization": f"Bearer {settings.GRAFANA_API_TOKEN}",
        "Accept": request.headers.get("accept", "*/*"),
        "User-Agent": request.headers.get("user-agent", "Catixs-FinWork"),
    }
    content_type = request.headers.get("content-type")
    if content_type:
        headers["Content-Type"] = content_type

    body = await request.body()
    try:
        async with httpx.AsyncClient(timeout=settings.PDM_TIMEOUT, verify=False, trust_env=False, follow_redirects=False) as client:
            upstream = await client.request(
                request.method,
                target_url,
                params=upstream_params,
                content=body,
                headers=headers,
            )
    except httpx.RequestError as exc:
        return Response(
            f"Grafana upstream request failed: {type(exc).__name__}: {exc}",
            status_code=502,
            media_type="text/plain; charset=utf-8",
        )

    response_headers = {}
    for key, value in upstream.headers.items():
        lower = key.lower()
        if lower in {"content-length", "transfer-encoding", "connection", "content-encoding"}:
            continue
        if lower == "location" and value.startswith(grafana_base_url()):
            response_headers[key] = value.replace(grafana_base_url(), grafana_proxy_prefix(), 1)
            continue
        response_headers[key] = value

    media_type = upstream.headers.get("content-type", "")
    content = upstream.content
    if "text/html" in media_type:
        content = rewrite_grafana_html(content, embed=request.query_params.get("catixs_embed") == "1")
        response_headers["content-length"] = str(len(content))

    response = Response(content=content, status_code=upstream.status_code, headers=response_headers)
    if token:
        response.set_cookie(
            "grafana_proxy_token",
            token,
            max_age=60 * 60,
            httponly=True,
            samesite="lax",
        )
    return response


@router.post("/nodes/add", summary="Add PVE remote to PDM")
async def add_pve_remote(payload: PDMAddRemoteRequest):
    global _PDM_RESOURCE_CACHE

    authid = (payload.authid or f"{settings.PVE_CREATE_SSH_USER}@pam").strip()
    token = payload.token or settings.PVE_CREATE_SSH_PASSWORD
    if not authid or not token:
        return Fail(msg="添加 PVE 节点失败: 缺少默认认证信息")
    if not payload.remote_id:
        return Fail(msg="添加 PVE 节点失败: 请填写远程 ID")

    target_host = pve_api_host(payload.hostname)
    scan_payload: dict[str, Any] = {
        "hostname": target_host,
        "authid": authid,
        "token": token,
    }
    if payload.fingerprint:
        scan_payload["fingerprint"] = payload.fingerprint.strip()

    remote_payload: dict[str, Any] = {}
    zabbix_sync: dict[str, Any] = {"enabled": False, "synced": False}
    try:
        try:
            scanned = await pdm_post("/pve/scan", scan_payload)
        except Exception as scan_exc:
            if "Connect" not in error_detail(scan_exc):
                raise RuntimeError(f"扫描 PVE 节点失败: {error_detail(scan_exc)}") from scan_exc
            scanned = {}
        remote_payload = dict(scanned or {})
        remote_payload["type"] = "pve"
        remote_payload["authid"] = remote_payload.get("authid") or scan_payload["authid"]
        remote_payload["token"] = remote_payload.get("token") or scan_payload["token"]

        remote_payload["id"] = payload.remote_id.strip()
        if payload.create_token:
            remote_payload["create-token"] = payload.create_token.strip()
        if payload.web_url:
            remote_payload["web-url"] = payload.web_url.strip()

        remote_payload["nodes"] = [
            pve_remote_node_entry(payload.hostname, payload.fingerprint)
        ]

        try:
            await pdm_post("/remotes/remote", remote_payload)
        except Exception as save_exc:
            raise RuntimeError(f"写入 PDM Remote 配置失败: {error_detail(save_exc)}") from save_exc
        _PDM_RESOURCE_CACHE = []
    except Exception as exc:
        return Fail(msg=f"添加 PVE 节点失败: {error_detail(exc)}")

    try:
        zabbix_sync = await sync_pve_host_to_zabbix(
            remote_id=str(remote_payload.get("id") or payload.remote_id or ""),
            hostname=target_host,
            token_id=pve_zabbix_token_id(str(remote_payload.get("authid") or authid), payload.create_token),
            token_secret=str(remote_payload.get("token") or token),
        )
    except Exception as exc:
        logger.error("sync PVE remote to Zabbix failed: %s", error_detail(exc))
        zabbix_sync = {"enabled": True, "synced": False, "message": error_detail(exc)}

    return Success(
        msg="PVE 节点已添加",
        data={
            "remote": remote_payload.get("id"),
            "nodes": remote_payload.get("nodes", []),
            "zabbix_sync": zabbix_sync,
        },
    )


@router.put("/nodes/remote/{remote}", summary="Update PVE remote")
async def update_pve_remote(remote: str, payload: PDMUpdateRemoteRequest):
    global _PDM_RESOURCE_CACHE

    if not payload.hostname:
        return Fail(msg="编辑 PVE 节点失败: 请填写节点 IP")

    try:
        actual_remote, current = await resolve_pdm_remote_config(remote, payload.original_hostname, payload.hostname)
        nodes = current.get("nodes") if isinstance(current.get("nodes"), list) else []
        old_node = parse_remote_node_entry(nodes[0]) if nodes else {"fingerprint": ""}
        fingerprint = (payload.fingerprint or old_node.get("fingerprint") or "").strip()

        remote_payload = {
            key: value
            for key, value in current.items()
            if key in {"id", "authid", "token", "web-url", "nodes"}
        }
        remote_payload["id"] = actual_remote
        remote_payload["nodes"] = [pve_remote_node_entry(payload.hostname, fingerprint)]
        if not remote_payload.get("token"):
            remote_payload.pop("token", None)

        await pdm_put(f"/remotes/remote/{quote(actual_remote, safe='')}", remote_payload)
        _PDM_RESOURCE_CACHE = []
        remote = actual_remote
    except Exception as exc:
        return Fail(msg=f"编辑 PVE 节点失败: {error_detail(exc)}")

    return Success(msg="PVE 节点已更新", data={"remote": remote, "nodes": remote_payload["nodes"]})


@router.delete("/nodes/remote/{remote}", summary="Delete PVE remote")
async def delete_pve_remote(remote: str):
    global _PDM_RESOURCE_CACHE

    try:
        await pdm_delete(f"/remotes/remote/{quote(remote, safe='')}")
        _PDM_RESOURCE_CACHE = []
    except Exception as exc:
        return Fail(msg=f"删除 PVE 节点失败: {error_detail(exc)}")

    return Success(msg="PVE 节点已删除")


@router.get("/nodes/remote/{remote}/remark", summary="Read PVE node remark")
async def get_pve_remote_remark(remote: str, host: str = Query("")):
    try:
        host = await resolve_remark_host(remote, host)
        if not host:
            return Fail(msg="读取 PVE 节点备注失败: 未找到节点 IP")
        command = "pvesh get /nodes/$(hostname -s)/config --output-format json"
        code, output, error = await asyncio.to_thread(ssh_execute_pve, host, command)
        if code != 0:
            return Fail(msg=f"读取 PVE 节点备注失败: {error or output}")
        data = json.loads(output or "{}")
        return Success(data={"remote": remote, "host": host, "remark": data.get("description") or ""})
    except Exception as exc:
        return Fail(msg=f"读取 PVE 节点备注失败: {error_detail(exc)}")


@router.put("/nodes/remote/{remote}/remark", summary="Update PVE node remark")
async def update_pve_remote_remark(remote: str, payload: PDMRemoteRemarkRequest):
    try:
        host = await resolve_remark_host(remote, payload.host)
        if not host:
            return Fail(msg="更新 PVE 节点备注失败: 未找到节点 IP")
        remark = (payload.remark or "").replace("\r\n", "\n")
        command = f"pvesh set /nodes/$(hostname -s)/config --description {shlex.quote(remark)}"
        code, output, error = await asyncio.to_thread(ssh_execute_pve, host, command)
        if code != 0:
            return Fail(msg=f"更新 PVE 节点备注失败: {error or output}")
    except Exception as exc:
        return Fail(msg=f"更新 PVE 节点备注失败: {error_detail(exc)}")

    return Success(msg="PVE 节点备注已更新")


@router.post("/nodes/probe", summary="Probe PVE remote TLS")
async def probe_pve_remote(payload: PDMProbeRemoteRequest):
    request_payload: dict[str, Any] = {"hostname": pve_api_host(payload.hostname)}
    if payload.fingerprint:
        request_payload["fingerprint"] = payload.fingerprint.strip()

    try:
        data = await pdm_post("/pve/probe-tls", request_payload)
    except Exception as exc:
        return Fail(msg=f"探测 PVE 节点失败: {error_detail(exc)}")

    return Success(msg="PVE 节点探测通过", data=data or {})


@router.get("/nodes/realms", summary="PVE remote realms")
async def pve_remote_realms(hostname: str = Query(...), fingerprint: str = Query("")):
    params = {"hostname": pve_api_host(hostname)}
    if fingerprint:
        params["fingerprint"] = fingerprint.strip()

    try:
        data = await pdm_get("/pve/realms", params=params)
    except Exception as exc:
        return Fail(msg=f"读取 PVE 认证域失败: {error_detail(exc)}")

    return Success(data=data or [])


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
        remotes = await pdm_remote_list()
        kind = guest_kind(type)
        try:
            wizard = await pdm_get(f"/pve/remotes/{remote}/{kind}/{vmid}/migrate")
        except Exception:
            wizard = {}
    except Exception as exc:
        return Fail(msg=f"读取 PDM 数据失败: {error_detail(exc)}")

    return Success(
        data={
            "source": {"remote": remote},
            "remotes": [{"remote": remote_id} for remote_id in sorted(remotes)],
            "wizard": wizard,
        }
    )


@router.get("/vms/migration-target-options", summary="PDM migration options for one target remote")
async def migration_target_options(
    remote: str = Query(...),
    preferred_vmid: int = Query(...),
):
    try:
        live_resources = await pdm_remote_resources(remote)
        if live_resources:
            data = [{"remote": remote, "resources": live_resources}]
        else:
            data = await pdm_resources_list()
        target = await remote_migration_resources(data, remote)
        target["suggested_vmid"] = next_available_vmid(target["used_vmids"], preferred_vmid)
        return Success(data=target)
    except Exception as exc:
        return Fail(msg=f"读取目标 PVE 迁移选项失败: {error_detail(exc)}")


@router.post("/vms/migrate", summary="PDM virtual machine remote migration")
async def migrate_vm(payload: VMMigrateRequest):
    try:
        data = await pdm_resources_list()
        source = await remote_migration_resources(data, payload.remote)
        try:
            live_target_resources = await pdm_remote_resources(payload.target)
        except Exception:
            live_target_resources = []
        if live_target_resources:
            target = remote_resources(
                [{"remote": payload.target, "resources": live_target_resources}],
                payload.target,
            )
        else:
            target = remote_resources(data, payload.target)
        target_vmid = next_available_vmid(
            target["used_vmids"],
            payload.target_vmid or payload.vmid,
        )
        kind = guest_kind(payload.type)
        request_payload: dict[str, Any] = {
            "remote": payload.remote,
            "vmid": payload.vmid,
            "target": payload.target,
            "target-storage": mapped_values(source["storages"], payload.target_storage),
            "target-bridge": mapped_values(source["networks"], payload.target_bridge),
            "delete": payload.delete_source,
            "online": payload.online,
            "target-vmid": target_vmid,
        }
        if payload.bwlimit is not None:
            request_payload["bwlimit"] = payload.bwlimit
        if payload.node:
            request_payload["node"] = payload.node
        if payload.target_endpoint:
            request_payload["target-endpoint"] = payload.target_endpoint

        task_id = await pdm_post(f"/pve/remotes/{payload.remote}/{kind}/{payload.vmid}/remote-migrate", request_payload)
    except Exception as exc:
        return Fail(msg=f"读取 PDM 数据失败: {error_detail(exc)}")

    return Success(
        msg=f"迁移任务已发起，目标 VMID: {target_vmid}",
        data={
            "upid": task_id,
            "source_remote": payload.remote,
            "target_remote": payload.target,
            "target_vmid": target_vmid,
        },
    )


@router.post("/vms/delete", summary="Delete PDM virtual machine")
async def delete_vm(payload: VMDeleteRequest):
    global _PDM_RESOURCE_CACHE

    if not payload.remote or not payload.vmid:
        return Fail(msg="删除虚拟机失败: 缺少远程或 VMID")
    if payload.status == "running":
        return Fail(msg="删除虚拟机失败: 请先关机后再删除")

    kind = guest_kind(payload.type)
    api_kind = "lxc" if kind == "lxc" else "qemu"

    try:
        host = await pdm_remote_config_host(payload.remote)
    except Exception as exc:
        return Fail(msg=f"删除虚拟机失败: {error_detail(exc)}")

    if not host:
        return Fail(msg="删除虚拟机失败: 未找到 PVE 节点 IP")

    command = (
        f"pvesh delete /nodes/$(hostname -s)/{api_kind}/{int(payload.vmid)} "
        "--purge 1 --destroy-unreferenced-disks 1"
    )
    exit_status, output, error = ssh_execute_pve(host, command)
    if exit_status != 0:
        detail = (error or output or "未知错误").strip()
        return Fail(msg=f"删除虚拟机失败: {detail}")

    _PDM_RESOURCE_CACHE = []
    return Success(msg="虚拟机删除任务已提交", data={"remote": payload.remote, "vmid": payload.vmid})


@router.post("/vms/power", summary="Start or shutdown PDM virtual machine")
async def power_vm(payload: VMPowerRequest):
    if not payload.remote or not payload.vmid:
        return Fail(msg="虚拟机操作失败: 缺少远程或 VMID")

    action = (payload.action or "").strip().lower()
    if action not in {"start", "stop"}:
        return Fail(msg="虚拟机操作失败: 不支持的操作")

    kind = guest_kind(payload.type)
    request_payload: dict[str, Any] = {}
    if payload.node:
        request_payload["node"] = payload.node

    try:
        task_id = await pdm_post(f"/pve/remotes/{payload.remote}/{kind}/{payload.vmid}/{action}", request_payload)
    except Exception as exc:
        return Fail(msg=f"虚拟机{'开机' if action == 'start' else '停止'}失败: {error_detail(exc)}")

    return Success(
        msg=f"{'开机' if action == 'start' else '停止'}请求已发送",
        data={"upid": task_id, "remote": payload.remote, "vmid": payload.vmid, "action": action},
    )


@router.get("/vms/config", summary="Read PVE virtual machine core config")
async def vm_config(
    remote: str = Query(...),
    vmid: int = Query(...),
    type: str = Query("pve-qemu"),
):
    try:
        host, config = await vm_config_from_pve(remote, vmid, type)
        disks = vm_disk_devices(config)
        networks = vm_network_devices(config)
        bridges: list[str] = []
        code, output, _error = await asyncio.to_thread(
            ssh_execute_pve,
            host,
            "pvesh get /nodes/$(hostname -s)/network --output-format json",
        )
        if code == 0:
            for item in json.loads(output or "[]"):
                if item.get("type") == "bridge" and item.get("iface"):
                    bridges.append(str(item["iface"]))
    except Exception as exc:
        return Fail(msg=f"读取虚拟机配置失败: {error_detail(exc)}")

    cores_per_socket, sockets, total_cores = vm_cpu_topology(config)
    return Success(
        data={
            "remote": remote,
            "vmid": vmid,
            "type": type,
            "cores": total_cores,
            "total_cores": total_cores,
            "cores_per_socket": cores_per_socket,
            "sockets": sockets,
            "memory_gb": round(number_value(config.get("memory")) / 1024, 2),
            "disks": disks,
            "disk_gb": disks[0]["size_gb"] if disks else 0,
            "disk_key": disks[0]["key"] if disks else "",
            "networks": networks,
            "bridges": sorted(set(bridges)) or ["vmbr10", "vmbr20"],
        }
    )


@router.post("/vms/config", summary="Update PVE virtual machine core config")
async def update_vm_config(payload: VMConfigUpdateRequest):
    if payload.type != "pve-qemu":
        return Fail(msg="编辑虚拟机配置失败: 当前只支持 QEMU 虚拟机")

    try:
        host, current = await vm_config_from_pve(payload.remote, payload.vmid, payload.type)
        commands: list[str] = []
        set_args: list[str] = []

        if payload.cores is not None:
            desired_total_cores = max(1, int(payload.cores))
            _current_cores_per_socket, current_sockets, current_total_cores = vm_cpu_topology(current)
            if desired_total_cores != current_total_cores:
                if current_sockets > 1 and desired_total_cores % current_sockets == 0:
                    set_args.extend(["--cores", str(desired_total_cores // current_sockets)])
                else:
                    set_args.extend(["--sockets", "1", "--cores", str(desired_total_cores)])
        if payload.memory_gb is not None:
            set_args.extend(["--memory", str(max(1, int(float(payload.memory_gb) * 1024)))])

        current_networks = {item["key"]: item for item in vm_network_devices(current)}
        used_keys = set(current_networks.keys())
        delete_keys: list[str] = []
        has_network_changes = False
        for network in payload.networks:
            key = (network.key or "").strip()
            if network.delete:
                if key and key in used_keys:
                    delete_keys.append(key)
                    has_network_changes = True
                continue
            if not key:
                key = next_net_key(used_keys)
                used_keys.add(key)
            set_args.extend([f"--{key}", qemu_net_value(network)])
            has_network_changes = True
        if delete_keys:
            set_args.extend(["--delete", ",".join(delete_keys)])

        if set_args:
            if has_network_changes:
                original_hotplug = str(current.get("hotplug") or "").strip()
                config_path = f"/nodes/$(hostname -s)/qemu/{int(payload.vmid)}/config"
                commands.append(
                    " ".join(
                        [
                            "pvesh",
                            "set",
                            config_path,
                            "--hotplug",
                            shlex.quote(qemu_hotplug_without_network(original_hotplug)),
                        ]
                    )
                )
            commands.append(
                " ".join(
                    [
                        "pvesh",
                        "set",
                        f"/nodes/$(hostname -s)/qemu/{int(payload.vmid)}/config",
                        *[shlex.quote(value) for value in set_args],
                    ]
                )
            )
            if has_network_changes:
                if original_hotplug:
                    commands.append(
                        " ".join(
                            [
                                "pvesh",
                                "set",
                                config_path,
                                "--hotplug",
                                shlex.quote(original_hotplug),
                            ]
                        )
                    )
                else:
                    commands.append(" ".join(["pvesh", "set", config_path, "--delete", "hotplug"]))

        if payload.disk_gb is not None:
            disk_key = (payload.disk_key or "").strip()
            current_disks = {item["key"]: item for item in vm_disk_devices(current)}
            current_disk = current_disks.get(disk_key) or (next(iter(current_disks.values())) if current_disks else None)
            if current_disk:
                target_size = float(payload.disk_gb)
                current_size = float(current_disk.get("size_gb") or 0)
                if target_size + 0.001 < current_size:
                    return Fail(msg="编辑虚拟机配置失败: 磁盘不支持缩小，只能扩容")
                if target_size > current_size + 0.001:
                    grow_size = round(target_size - current_size, 2)
                    commands.append(
                        " ".join(
                            [
                                "pvesh",
                                "set",
                                f"/nodes/$(hostname -s)/qemu/{int(payload.vmid)}/resize",
                                "--disk",
                                shlex.quote(str(current_disk["key"])),
                                "--size",
                                shlex.quote(f"+{grow_size:g}G"),
                            ]
                        )
                    )

        if not commands:
            return Success(msg="没有需要更新的配置")

        command = " && ".join(commands)
        code, output, error = await asyncio.to_thread(ssh_execute_pve, host, command)
        if code != 0:
            return Fail(msg=f"编辑虚拟机配置失败: {error or output}")
    except Exception as exc:
        return Fail(msg=f"编辑虚拟机配置失败: {error_detail(exc)}")

    return Success(msg="虚拟机配置已更新，部分配置需重启虚拟机后生效")


@router.post("/vms/reboot", summary="Reboot PVE virtual machine")
async def reboot_vm(payload: VMDeleteRequest):
    try:
        host = await pdm_remote_config_host(payload.remote)
        if not host:
            return Fail(msg="重启虚拟机失败: 未找到 PVE 节点 IP")
        command = f"pvesh create /nodes/$(hostname -s)/qemu/{int(payload.vmid)}/status/reboot"
        code, output, error = await asyncio.to_thread(ssh_execute_pve, host, command)
        if code != 0:
            return Fail(msg=f"重启虚拟机失败: {error or output}")
    except Exception as exc:
        return Fail(msg=f"重启虚拟机失败: {error_detail(exc)}")

    return Success(msg="重启请求已发送")

