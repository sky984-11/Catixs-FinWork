import logging
import time
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.core.dependency import AuthControl
from app.schemas.base import Success
from app.services.monitor_event_config import SettingsPayload, load_settings, save_settings
from app.services.monitor_events import ZabbixClient, dashboard, detail, get_hosts, host_view

router = APIRouter()
logger = logging.getLogger(__name__)
EventId = Path(pattern=r"^[1-9][0-9]{0,19}$")


class EventAction(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    action: Literal["acknowledge", "unacknowledge", "comment", "suppress", "unsuppress", "close", "severity"]
    message: str = Field(min_length=1, max_length=1500)
    minutes: int = Field(default=60, ge=1, le=10080)
    severity: int | None = Field(default=None, ge=0, le=5)

    @model_validator(mode="after")
    def validate_severity(self):
        if self.action == "severity" and self.severity is None:
            raise ValueError("修改级别时必须选择严重程度")
        return self


@router.get("", summary="Zabbix 事件仪表盘")
async def list_events(history: bool = False):
    config = await load_settings()
    if not config["hosts"]:
        return Success(data=await dashboard(None, history, config))
    async with ZabbixClient() as client:
        return Success(data=await dashboard(client, history, config))


@router.get("/settings", summary="读取事件分类与已选 Zabbix 主机")
async def get_settings():
    config = await load_settings()
    if config["hosts"]:
        try:
            async with ZabbixClient() as client:
                hosts = await get_hosts(client, [h["hostid"] for h in config["hosts"]])
            lookup = {h["hostid"]: h for h in hosts}
            config["hosts"] = [{**h, "tags": lookup.get(h["hostid"], {}).get("tags", [])} for h in config["hosts"]]
        except HTTPException:
            config["tags_warning"] = "当前无法刷新 Zabbix 标签，仍可调整或清空监控范围"
    return Success(data=config)


@router.get("/host-groups", summary="读取可选择的 Zabbix 主机组")
async def host_groups():
    async with ZabbixClient() as client:
        groups = await client.call(
            "hostgroup.get", {"output": ["groupid", "name"], "with_monitored_hosts": True, "sortfield": "name"}
        )
        return Success(data=groups)


@router.get("/host-options", summary="读取选定主机组中的候选主机")
async def host_options(
    group_id: str = Query(pattern=r"^[1-9][0-9]{0,19}$"), keyword: str = Query(default="", max_length=100)
):
    async with ZabbixClient() as client:
        params = {
            "output": ["hostid"],
            "filter": {"status": 0},
            "groupids": [group_id],
            "sortfield": "name",
            "limit": 101,
        }
        if keyword.strip():
            params.update(search={"host": keyword.strip(), "name": keyword.strip()}, searchByAny=True)
        candidates = await client.call(
            "host.get",
            params,
        )
        hosts = await get_hosts(client, [h["hostid"] for h in candidates[:100]])
        return Success(data={"rows": [host_view(h) for h in hosts], "truncated": len(candidates) > 100})


@router.put("/settings", summary="保存事件分类与监控范围")
async def put_settings(payload: SettingsPayload, user=Depends(AuthControl.is_authed)):
    hosts = []
    if payload.hosts:
        async with ZabbixClient() as client:
            hosts = await get_hosts(client, [h.hostid for h in payload.hosts])
    result = await save_settings(payload, hosts, user.id)
    logger.info("monitor_event settings actor_id=%s host_count=%s revision=%s", user.id, len(hosts), result["revision"])
    return Success(data=result)


@router.get("/{eventid}", summary="事件定位、指标现值、建议与处置记录")
async def event_detail(eventid: str = EventId):
    config = await load_settings()
    if not config["hosts"]:
        raise HTTPException(404, "请先选择监控主机")
    async with ZabbixClient() as client:
        return Success(data=await detail(client, eventid, config))


@router.post("/{eventid}/actions", summary="确认、备注、抑制、解除抑制、调整级别或手动关闭事件")
async def event_action(payload: EventAction, eventid: str = EventId, user=Depends(AuthControl.is_authed)):
    config = await load_settings()
    if not config["hosts"]:
        raise HTTPException(404, "请先选择监控主机")
    async with ZabbixClient() as client:
        row = await detail(client, eventid, config)
        if row["recovered"] and payload.action not in {"comment", "acknowledge", "unacknowledge"}:
            raise HTTPException(409, "事件已经恢复，请刷新后操作")
        if payload.action == "close" and not row["manual_close"]:
            raise HTTPException(409, "该触发器不允许手动关闭；请排除故障后等待 Zabbix 自动恢复")
        if (await load_settings())["revision"] != config["revision"]:
            raise HTTPException(409, "监控范围刚刚发生变化，请刷新后重新操作")
        bits = {
            "acknowledge": 2,
            "unacknowledge": 16,
            "comment": 0,
            "suppress": 32,
            "unsuppress": 64,
            "close": 1,
            "severity": 8,
        }
        params = {
            "eventids": [eventid],
            "action": bits[payload.action] | 4,
            "message": f"[FinWork user:{user.id}] {payload.message}",
        }
        if payload.action == "suppress":
            params["suppress_until"] = int(time.time()) + payload.minutes * 60
        if payload.action == "severity":
            params["severity"] = payload.severity
        result = await client.call("event.acknowledge", params)
        if eventid not in [str(value) for value in result.get("eventids", [])]:
            raise HTTPException(502, "Zabbix 未确认操作结果，请刷新核实")
        logger.info("monitor_event action=%s event_id=%s actor_id=%s", payload.action, eventid, user.id)
        return Success(data={"eventid": eventid, "submitted": True}, msg="操作已提交至 Zabbix，请刷新查看最新状态")
