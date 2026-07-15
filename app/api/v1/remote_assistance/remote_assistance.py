from __future__ import annotations

import asyncio
from typing import Any, Literal

import httpx
from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict

from app.schemas.base import Fail, Success
from app.settings.config import settings

router = APIRouter()

_session_token = ""


class RemoteHandsPayload(BaseModel):
    model_config = ConfigDict(extra="allow")

    customer: str = ""
    ticket: str = ""
    engineer_id: int | None = None
    engineer_name: str = ""
    engineer_contact: str = ""
    engineer_wechat: str = ""
    engineer_group: str = ""
    region: str = ""
    site: str = ""
    rack: str = ""
    timezone: str = "UTC"
    arrived_at: str = ""
    left_at: str = ""
    work_minutes: int = 0
    status: Literal["scheduled", "arrived", "done", "cancelled"] = "scheduled"
    note: str = ""


class EngineerPayload(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str = ""
    contact: str = ""
    wechat_id: str = ""
    wechat_group: str = ""
    region: str = ""
    is_active: int = 1
    note: str = ""


def _base_url() -> str:
    url = settings.DATACENTER_PARTS_API_URL.strip().rstrip("/")
    if not url:
        raise RuntimeError("未配置 DATACENTER_PARTS_API_URL")
    return url


def _api_url(path: str) -> str:
    normalized = path.lstrip("/")
    if normalized.startswith("api/"):
        return f"{_base_url()}/{normalized}"
    return f"{_base_url()}/api/{normalized}"


async def _login(client: httpx.AsyncClient) -> str:
    global _session_token

    configured_token = settings.DATACENTER_PARTS_API_TOKEN.strip()
    if configured_token:
        return configured_token.removeprefix("Bearer ").strip()
    if _session_token:
        return _session_token

    username = settings.DATACENTER_PARTS_API_USERNAME.strip()
    password = settings.DATACENTER_PARTS_API_PASSWORD
    if not username or not password:
        raise RuntimeError(
            "未配置备件系统认证信息，请设置 DATACENTER_PARTS_API_TOKEN，"
            "或设置 DATACENTER_PARTS_API_USERNAME 和 DATACENTER_PARTS_API_PASSWORD"
        )

    response = await client.post(
        _api_url("login"),
        json={"username": username, "password": password},
    )
    response.raise_for_status()
    payload = response.json()
    data = payload.get("data") if isinstance(payload, dict) else None
    token = str(
        (payload.get("token") if isinstance(payload, dict) else "")
        or (data.get("token") if isinstance(data, dict) else "")
        or ""
    ).strip()
    if not token:
        raise RuntimeError("备件系统登录成功，但响应中没有 token")
    _session_token = token
    return token


def _error_message(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return response.text.strip() or response.reason_phrase
    error = payload.get("error") if isinstance(payload, dict) else None
    if isinstance(error, dict):
        return str(error.get("message") or error)
    if isinstance(payload, dict):
        return str(error or payload.get("message") or response.reason_phrase)
    return str(payload)


def _response_data(response: httpx.Response) -> Any:
    value = response.json()
    if isinstance(value, dict) and "data" in value:
        return value["data"]
    return value


async def _request(method: str, path: str, payload: dict[str, Any] | None = None) -> Any:
    global _session_token

    timeout = httpx.Timeout(settings.DATACENTER_PARTS_API_TIMEOUT)
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        token = await _login(client)
        response = await client.request(
            method,
            _api_url(path),
            headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
            json=payload,
        )
        if response.status_code == 401 and not settings.DATACENTER_PARTS_API_TOKEN.strip():
            _session_token = ""
            token = await _login(client)
            response = await client.request(
                method,
                _api_url(path),
                headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
                json=payload,
            )
        if response.is_error:
            raise RuntimeError(f"备件系统 API HTTP {response.status_code}: {_error_message(response)}")
        if not response.content:
            return None
        return _response_data(response)


async def _success(method: str, path: str, payload: dict[str, Any] | None = None):
    try:
        return Success(data=await _request(method, path, payload))
    except (httpx.HTTPError, RuntimeError, ValueError) as exc:
        return Fail(msg=f"运维记录操作失败: {exc}")


@router.get("/overview", summary="运维记录页面数据")
async def overview():
    global _session_token

    try:
        timeout = httpx.Timeout(settings.DATACENTER_PARTS_API_TIMEOUT)
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            token = await _login(client)
            headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
            responses = await asyncio.gather(
                client.get(_api_url("remote-hands"), headers=headers),
                client.get(_api_url("engineers"), headers=headers),
                client.get(_api_url("datacenters"), headers=headers),
            )
            if any(response.status_code == 401 for response in responses) and not settings.DATACENTER_PARTS_API_TOKEN.strip():
                _session_token = ""
                token = await _login(client)
                headers["Authorization"] = f"Bearer {token}"
                responses = await asyncio.gather(
                    client.get(_api_url("remote-hands"), headers=headers),
                    client.get(_api_url("engineers"), headers=headers),
                    client.get(_api_url("datacenters"), headers=headers),
                )
        for response in responses:
            if response.is_error:
                raise RuntimeError(f"备件系统 API HTTP {response.status_code}: {_error_message(response)}")

        return Success(
            data={
                "remote_hands": _response_data(responses[0]),
                "engineers": _response_data(responses[1]),
                "datacenters": _response_data(responses[2]),
            }
        )
    except (httpx.HTTPError, RuntimeError, ValueError) as exc:
        return Fail(msg=f"读取运维记录数据失败: {exc}")


@router.post("/remote-hands", summary="新增运维记录")
async def create_remote_hands(payload: RemoteHandsPayload):
    return await _success("POST", "remote-hands", payload.model_dump())


@router.put("/remote-hands/{item_id}", summary="更新运维记录")
async def update_remote_hands(item_id: int, payload: RemoteHandsPayload):
    return await _success("PUT", f"remote-hands/{item_id}", payload.model_dump())


@router.delete("/remote-hands/{item_id}", summary="删除运维记录")
async def delete_remote_hands(item_id: int):
    return await _success("DELETE", f"remote-hands/{item_id}")


@router.post("/engineers", summary="新增工程师")
async def create_engineer(payload: EngineerPayload):
    return await _success("POST", "engineers", payload.model_dump())


@router.put("/engineers/{engineer_id}", summary="更新工程师")
async def update_engineer(engineer_id: int, payload: EngineerPayload):
    return await _success("PUT", f"engineers/{engineer_id}", payload.model_dump())


@router.delete("/engineers/{engineer_id}", summary="删除工程师")
async def delete_engineer(engineer_id: int):
    return await _success("DELETE", f"engineers/{engineer_id}")
