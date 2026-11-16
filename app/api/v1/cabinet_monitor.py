import logging

from fastapi import APIRouter, BackgroundTasks, Depends, Path, Query
from pydantic import Field

from app.core.dependency import AuthControl
from app.schemas.base import Success
from app.services import cabinet_monitor as service
from app.services.monitor_events import ZabbixClient
from app.services.monitor_event_config import SelectedHost

router = APIRouter()
logger = logging.getLogger(__name__)


class HostPolicy(SelectedHost):
    revision: int = Field(ge=0)


@router.put("/hosts", summary="调整自动纳管主机的分类与监控项")
async def update_host(payload: HostPolicy, user=Depends(AuthControl.is_authed)):
    result = await service.update_host_policy(payload.hostid, payload.revision, selection=payload)
    logger.info("cabinet host policy actor_id=%s host_id=%s", user.id, payload.hostid)
    return Success(data=result)


@router.delete("/hosts/{host_id}", summary="移除自动纳管并禁止再次自动加入")
async def remove_host(
    host_id: str = Path(pattern=r"^[1-9][0-9]{0,19}$"), revision: int = Query(ge=0), user=Depends(AuthControl.is_authed)
):
    result = await service.update_host_policy(host_id, revision, excluded=True)
    logger.info("cabinet host excluded actor_id=%s host_id=%s", user.id, host_id)
    return Success(data=result)


@router.post("/hosts/{host_id}/restore", summary="恢复已移除主机的自动纳管")
async def restore_host(
    host_id: str = Path(pattern=r"^[1-9][0-9]{0,19}$"), revision: int = Query(ge=0), user=Depends(AuthControl.is_authed)
):
    result = await service.update_host_policy(host_id, revision, excluded=False)
    logger.info("cabinet host restored actor_id=%s host_id=%s", user.id, host_id)
    return Success(data=result)


@router.get("", summary="机柜客户机器 Ping 纳管清单")
async def get_inventory():
    return Success(data=await service.view())


@router.get("/options", summary="机柜联动可用 Ping 模板、主机组及代理")
async def get_options():
    async with ZabbixClient() as client:
        return Success(data=await service.options(client))


@router.put("", summary="保存机柜 Ping 自动纳管配置")
async def save(payload: service.CabinetSettings, user=Depends(AuthControl.is_authed)):
    result = await service.save_config(payload)
    logger.info("cabinet monitor settings actor_id=%s revision=%s", user.id, result["revision"])
    return Success(data=result)


async def run_sync():
    try:
        await service.synchronize(force=True)
    except Exception:
        logger.error("cabinet monitor sync incomplete; inspect coverage status")


@router.post("/sync", summary="立即触发机柜 Ping 自动纳管")
async def sync(background: BackgroundTasks, user=Depends(AuthControl.is_authed)):
    background.add_task(run_sync)
    logger.info("cabinet monitor sync actor_id=%s", user.id)
    return Success(data={"queued": True})
