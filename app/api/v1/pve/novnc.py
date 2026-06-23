import asyncio
import ssl
import time
import uuid
from typing import Any
from urllib.parse import urlencode, urlparse

import httpx
import websockets
from fastapi import APIRouter, HTTPException, WebSocket
from starlette.websockets import WebSocketDisconnect
from pydantic import BaseModel

from app.core.dependency import AuthControl
from app.schemas.base import Fail, Success
from app.settings.config import settings

router = APIRouter()
ws_router = APIRouter()
_NOVNC_SESSIONS: dict[str, dict[str, Any]] = {}
_NOVNC_SESSION_TTL = 120


class NoVNCRequest(BaseModel):
    remote: str
    vmid: int
    type: str = "pve-qemu"
    node: str | None = None


def pdm_base_url() -> str:
    if not settings.PDM_API_URL:
        raise RuntimeError("PDM API URL is not configured")
    return settings.PDM_API_URL.rstrip("/")


def pdm_api_url(path: str) -> str:
    clean_path = path if path.startswith("/") else f"/{path}"
    return f"{pdm_base_url()}/api2/json{clean_path}"


def pve_base_url(host: str) -> str:
    value = host.strip().split(",", 1)[0].strip()
    if not value:
        raise RuntimeError("PVE host is empty")
    if "://" not in value:
        value = f"https://{value}"
    parsed = urlparse(value)
    if not parsed.netloc:
        raise RuntimeError(f"Invalid PVE host: {host}")
    if ":" not in parsed.netloc:
        value = value.rstrip("/") + ":8006"
    return value.rstrip("/")


def pve_api_url(host: str, path: str) -> str:
    clean_path = path if path.startswith("/") else f"/{path}"
    return f"{pve_base_url(host)}/api2/json{clean_path}"


def pdm_auth_header() -> str:
    if settings.PDM_API_TOKEN:
        return settings.PDM_API_TOKEN
    if not settings.PDM_TOKEN_ID or not settings.PDM_TOKEN_SECRET:
        raise RuntimeError("PDM token is not configured")
    return f"PDMAPIToken {settings.PDM_TOKEN_ID}:{settings.PDM_TOKEN_SECRET}"


async def pdm_post(path: str, payload: dict[str, Any] | None = None) -> Any:
    headers = {"Authorization": pdm_auth_header(), "Accept": "application/json"}
    async with httpx.AsyncClient(timeout=settings.PDM_TIMEOUT, verify=False, trust_env=False) as client:
        response = await client.post(pdm_api_url(path), json=payload or {}, headers=headers)
        response.raise_for_status()
        data = response.json()
    return data.get("data")


async def pdm_get(path: str) -> Any:
    headers = {"Authorization": pdm_auth_header(), "Accept": "application/json"}
    async with httpx.AsyncClient(timeout=settings.PDM_TIMEOUT, verify=False, trust_env=False) as client:
        response = await client.get(pdm_api_url(path), headers=headers)
        response.raise_for_status()
        data = response.json()
    return data.get("data")


def pve_auth_header(authid: str, token: str) -> str:
    if not authid or not token:
        raise RuntimeError("PVE token is not configured in PDM remote")
    return f"PVEAPIToken={authid}={token}"


def pve_login_user(authid: str) -> str:
    if authid and "!" in authid:
        return authid.split("!", 1)[0]
    if authid and "@" in authid:
        return authid
    return f"{settings.PVE_CREATE_SSH_USER}@pam"


async def pve_login(host: str, authid: str) -> dict[str, str]:
    username = pve_login_user(authid)
    if not username or not settings.PVE_CREATE_SSH_PASSWORD:
        raise RuntimeError("PVE login user or password is not configured")

    async with httpx.AsyncClient(timeout=settings.PDM_TIMEOUT, verify=False, trust_env=False) as client:
        response = await client.post(
            pve_api_url(host, "/access/ticket"),
            data={"username": username, "password": settings.PVE_CREATE_SSH_PASSWORD},
            headers={"Accept": "application/json"},
        )
        response.raise_for_status()
        data = response.json().get("data") or {}
    ticket = data.get("ticket")
    csrf = data.get("CSRFPreventionToken")
    if not ticket or not csrf:
        raise RuntimeError("PVE login did not return auth ticket")
    return {"ticket": str(ticket), "csrf": str(csrf)}


async def pve_post_with_token(host: str, authid: str, token: str, path: str, payload: dict[str, Any] | None = None) -> Any:
    headers = {"Authorization": pve_auth_header(authid, token), "Accept": "application/json"}
    async with httpx.AsyncClient(timeout=settings.PDM_TIMEOUT, verify=False, trust_env=False) as client:
        response = await client.post(pve_api_url(host, path), data=payload or {}, headers=headers)
        response.raise_for_status()
        data = response.json()
    return data.get("data")


async def pve_post_with_ticket(host: str, authid: str, path: str, payload: dict[str, Any] | None = None) -> Any:
    login = await pve_login(host, authid)
    headers = {
        "Accept": "application/json",
        "CSRFPreventionToken": login["csrf"],
        "Cookie": f"PVEAuthCookie={login['ticket']}",
    }
    async with httpx.AsyncClient(timeout=settings.PDM_TIMEOUT, verify=False, trust_env=False) as client:
        response = await client.post(pve_api_url(host, path), data=payload or {}, headers=headers)
        response.raise_for_status()
        data = response.json()
    return data.get("data")


async def pve_post(host: str, authid: str, token: str, path: str, payload: dict[str, Any] | None = None) -> Any:
    if token:
        return await pve_post_with_token(host, authid, token, path, payload)
    return await pve_post_with_ticket(host, authid, path, payload)


def list_data(data: Any) -> list[Any]:
    if isinstance(data, list):
        return data
    if not isinstance(data, dict):
        return []
    for key in ("data", "items", "remotes", "nodes"):
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
        row.setdefault("id", key)
        row.setdefault("remote", key)
        values.append(row)
    return values


def remote_id(remote: dict[str, Any]) -> str:
    for key in ("id", "remote", "name"):
        value = remote.get(key)
        if value:
            return str(value)
    return ""


def remote_host(remote: dict[str, Any]) -> str:
    nodes = remote.get("nodes")
    if isinstance(nodes, list) and nodes:
        first = nodes[0]
        if isinstance(first, str):
            return first
        if isinstance(first, dict):
            for key in ("hostname", "host", "address", "node"):
                value = first.get(key)
                if value:
                    return str(value)
    for key in ("hostname", "host", "address", "ip", "endpoint", "server", "node"):
        value = remote.get(key)
        if value:
            return str(value)
    return ""


async def pdm_remote_config(remote: str) -> dict[str, Any]:
    errors: list[str] = []
    for path in ("/remotes/remote", "/config/remotes", "/remotes", "/pve/remotes"):
        try:
            data = await pdm_get(path)
        except Exception as exc:
            errors.append(f"{path}: {exc}")
            continue
        for item in list_data(data):
            if isinstance(item, dict) and remote_id(item) == remote:
                return item
    raise RuntimeError(f"未找到 PDM Remote 配置: {remote}; {'; '.join(errors)}")


def guest_kind(value: str) -> str:
    return "lxc" if value in {"lxc", "pve-lxc"} else "qemu"


def direct_url(data: Any) -> str:
    if isinstance(data, str) and data.startswith(("http://", "https://", "/")):
        return data
    if not isinstance(data, dict):
        return ""
    for key in ("url", "href", "console", "novnc_url", "novnc-url"):
        value = data.get(key)
        if isinstance(value, str) and value:
            if value.startswith(("http://", "https://")):
                return value
            if value.startswith("/"):
                return f"{pdm_base_url()}{value}"
    return ""


def build_pdm_novnc_url(remote: str, vmid: int, kind: str, data: dict[str, Any]) -> str:
    port = data.get("port")
    ticket = data.get("ticket") or data.get("vncticket")
    cert = data.get("cert")
    params = [
        ("console", kind),
        ("novnc", "1"),
        ("resize", "scale"),
        ("vmid", str(vmid)),
        ("remote", remote),
    ]
    if port:
        params.append(("port", str(port)))
    if ticket:
        params.append(("vncticket", str(ticket)))
    if cert:
        params.append(("cert", str(cert)))
    query = urlencode(params)
    return f"{pdm_base_url()}/?{query}"


def build_pve_novnc_url(host: str, node: str, vmid: int, kind: str, data: dict[str, Any]) -> str:
    console = "lxc" if kind == "lxc" else "kvm"
    params = {
        "console": console,
        "novnc": "1",
        "resize": "scale",
        "vmid": str(vmid),
        "node": node,
    }
    if data.get("port"):
        params["port"] = str(data["port"])
    if data.get("ticket") or data.get("vncticket"):
        params["vncticket"] = str(data.get("ticket") or data.get("vncticket"))
    if data.get("cert"):
        params["cert"] = str(data["cert"])
    return f"{pve_base_url(host)}/?{urlencode(params)}"


def build_pve_websocket_url(host: str, node: str, vmid: int, kind: str, data: dict[str, Any]) -> str:
    base = pve_base_url(host)
    scheme = "wss" if base.startswith("https://") else "ws"
    netloc = urlparse(base).netloc
    ticket = data.get("ticket") or data.get("vncticket")
    if not data.get("port") or not ticket:
        raise RuntimeError("PVE did not return websocket port or ticket")
    query = urlencode({"port": str(data["port"]), "vncticket": str(ticket)})
    return f"{scheme}://{netloc}/api2/json/nodes/{node}/{kind}/{vmid}/vncwebsocket?{query}"


async def request_direct_pve_novnc(payload: NoVNCRequest) -> dict[str, Any]:
    if not payload.node:
        raise RuntimeError("缺少虚拟机所在 PVE 节点名称")

    remote = await pdm_remote_config(payload.remote)
    host = remote_host(remote)
    if not host:
        raise RuntimeError(f"PDM Remote 未记录 PVE 地址: {payload.remote}")

    authid = str(remote.get("authid") or "")
    token = str(remote.get("token") or "")
    kind = guest_kind(payload.type)
    data = await pve_post(host, authid, token, f"/nodes/{payload.node}/{kind}/{payload.vmid}/vncproxy")
    if not isinstance(data, dict):
        raise RuntimeError("PVE did not return noVNC ticket data")
    url = build_pve_novnc_url(host, payload.node, payload.vmid, kind, data)
    session_id = create_novnc_session(payload, host, authid, kind, data)
    ws_url = build_proxy_websocket_url(payload, session_id)
    return {
        "url": url,
        "wsUrl": ws_url,
        "password": str(data.get("ticket") or data.get("vncticket") or ""),
        "remote": payload.remote,
        "node": payload.node,
        "vmid": payload.vmid,
        "type": kind,
        "ticket": data,
    }


def cleanup_sessions() -> None:
    now = time.time()
    expired = [key for key, value in _NOVNC_SESSIONS.items() if now - float(value.get("created_at") or 0) > _NOVNC_SESSION_TTL]
    for key in expired:
        _NOVNC_SESSIONS.pop(key, None)


def create_novnc_session(payload: NoVNCRequest, host: str, authid: str, kind: str, ticket_data: dict[str, Any]) -> str:
    cleanup_sessions()
    session_id = uuid.uuid4().hex
    _NOVNC_SESSIONS[session_id] = {
        "created_at": time.time(),
        "remote": payload.remote,
        "node": payload.node,
        "vmid": payload.vmid,
        "type": payload.type,
        "host": host,
        "authid": authid,
        "kind": kind,
        "ticket": ticket_data,
    }
    return session_id


def build_proxy_websocket_url(payload: NoVNCRequest, session_id: str) -> str:
    query = urlencode(
        {
            "session": session_id,
            "remote": payload.remote,
            "vmid": str(payload.vmid),
            "node": payload.node or "",
            "type": payload.type,
        }
    )
    return f"/api/v1/pve/vms/novnc/ws?{query}"


async def pve_websocket_connection(payload: NoVNCRequest, session: dict[str, Any] | None = None) -> tuple[str, dict[str, str], list[str]]:
    if session:
        host = str(session.get("host") or "")
        authid = str(session.get("authid") or "")
        kind = str(session.get("kind") or guest_kind(payload.type))
        ticket_data = session.get("ticket") or {}
        if not host or not isinstance(ticket_data, dict):
            raise RuntimeError("noVNC session is invalid")
        login = await pve_login(host, authid)
        ws_url = build_pve_websocket_url(host, payload.node or str(session.get("node") or ""), payload.vmid, kind, ticket_data)
        headers = {"Cookie": f"PVEAuthCookie={login['ticket']}"}
        return ws_url, headers, ["binary"]

    if not payload.node:
        raise RuntimeError("缺少虚拟机所在 PVE 节点名称")

    remote = await pdm_remote_config(payload.remote)
    host = remote_host(remote)
    if not host:
        raise RuntimeError(f"PDM Remote 未记录 PVE 地址: {payload.remote}")

    authid = str(remote.get("authid") or "")
    kind = guest_kind(payload.type)
    ticket_data = await pve_post(host, authid, str(remote.get("token") or ""), f"/nodes/{payload.node}/{kind}/{payload.vmid}/vncproxy")
    if not isinstance(ticket_data, dict):
        raise RuntimeError("PVE did not return noVNC ticket data")

    login = await pve_login(host, authid)
    ws_url = build_pve_websocket_url(host, payload.node, payload.vmid, kind, ticket_data)
    headers = {"Cookie": f"PVEAuthCookie={login['ticket']}"}
    return ws_url, headers, ["binary"]


async def request_novnc(payload: NoVNCRequest) -> dict[str, Any]:
    try:
        return await request_direct_pve_novnc(payload)
    except Exception as direct_exc:
        direct_error = direct_exc

    kind = guest_kind(payload.type)
    paths = [
        f"/pve/remotes/{payload.remote}/{kind}/{payload.vmid}/vncproxy",
        f"/pve/remotes/{payload.remote}/{kind}/{payload.vmid}/novnc",
        f"/pve/remotes/{payload.remote}/{kind}/{payload.vmid}/console",
    ]
    if payload.node:
        paths.extend(
            [
                f"/pve/remotes/{payload.remote}/nodes/{payload.node}/{kind}/{payload.vmid}/vncproxy",
                f"/pve/remotes/{payload.remote}/nodes/{payload.node}/{kind}/{payload.vmid}/novnc",
            ]
        )

    errors: list[str] = []
    for path in paths:
        try:
            data = await pdm_post(path)
        except Exception as exc:
            errors.append(f"{path}: {exc}")
            continue
        url = direct_url(data)
        if not url and isinstance(data, dict):
            url = build_pdm_novnc_url(payload.remote, payload.vmid, kind, data)
        if url:
            return {"url": url, "remote": payload.remote, "vmid": payload.vmid, "type": kind, "ticket": data}

    all_errors = [f"PVE direct: {direct_error}", *errors]
    raise RuntimeError("; ".join(all_errors) or "PDM did not return noVNC console data")


@router.post("/vms/novnc", summary="PDM virtual machine noVNC console")
async def novnc_console(payload: NoVNCRequest):
    try:
        data = await request_novnc(payload)
    except Exception as exc:
        return Fail(msg=f"打开 noVNC 失败: {exc}")
    return Success(data=data)


@ws_router.websocket("/vms/novnc/ws")
async def novnc_websocket_proxy(
    websocket: WebSocket,
    remote: str,
    vmid: int,
    node: str,
    session: str = "",
    type: str = "pve-qemu",
    token: str = "",
):
    try:
        await AuthControl.is_authed(token)
    except HTTPException as exc:
        await websocket.close(code=1008, reason=str(exc.detail)[:120])
        return

    await websocket.accept(subprotocol="binary")
    payload = NoVNCRequest(remote=remote, vmid=vmid, node=node, type=type)
    try:
        cleanup_sessions()
        novnc_session = _NOVNC_SESSIONS.get(session) if session else None
        pve_ws_url, headers, protocols = await pve_websocket_connection(payload, novnc_session)
        try:
            pve_ws = await websockets.connect(
                pve_ws_url,
                ssl=ssl._create_unverified_context(),
                subprotocols=protocols,
                additional_headers=headers,
                open_timeout=settings.PDM_TIMEOUT,
            )
        except TypeError:
            pve_ws = await websockets.connect(
                pve_ws_url,
                ssl=ssl._create_unverified_context(),
                subprotocols=protocols,
                extra_headers=headers,
                open_timeout=settings.PDM_TIMEOUT,
            )
    except Exception as exc:
        await websocket.close(code=1011, reason=str(exc)[:120])
        return

    async def client_to_pve():
        while True:
            message = await websocket.receive()
            if message.get("type") == "websocket.disconnect":
                await pve_ws.close()
                return
            if message.get("bytes") is not None:
                await pve_ws.send(message["bytes"])
            elif message.get("text") is not None:
                await pve_ws.send(message["text"])

    async def pve_to_client():
        async for message in pve_ws:
            if isinstance(message, bytes):
                await websocket.send_bytes(message)
            else:
                await websocket.send_text(message)

    tasks = [asyncio.create_task(client_to_pve()), asyncio.create_task(pve_to_client())]
    try:
        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for task in done:
            task.result()
        for task in pending:
            task.cancel()
    except (WebSocketDisconnect, websockets.ConnectionClosed):
        pass
    except Exception as exc:
        try:
            await websocket.close(code=1011, reason=str(exc)[:120])
        except Exception:
            pass
    finally:
        for task in tasks:
            task.cancel()
        await pve_ws.close()
