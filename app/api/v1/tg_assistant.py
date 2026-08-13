import json

from fastapi import APIRouter, Request

from app.core.ctx import CTX_USER_ID
from app.core.dependency import DependAuth
from app.log import logger
from app.models.tg_assistant import TGAssistantDeliveryLog
from app.schemas import Fail, Success
from app.schemas.tg_assistant import TGAssistantConfigUpdate
from app.services.tg_assistant import (
    get_or_create_user_config,
    process_chatwoot_payload,
    verify_chatwoot_signature,
    webhook_url,
)

router = APIRouter()


@router.get("/config", summary="查看TG助手配置", dependencies=[DependAuth])
async def get_config():
    user_id = CTX_USER_ID.get()
    config = await get_or_create_user_config(user_id)
    data = await config.to_dict(exclude_fields=["user_id"])
    data["webhook_url"] = webhook_url()
    return Success(data=data)


@router.post("/config", summary="保存TG助手配置", dependencies=[DependAuth])
async def save_config(config_in: TGAssistantConfigUpdate):
    user_id = CTX_USER_ID.get()
    config = await get_or_create_user_config(user_id)
    data = config_in.model_dump()
    for key, value in data.items():
        setattr(config, key, value)
    await config.save()
    return Success(msg="保存成功", data=await config.to_dict(exclude_fields=["user_id"]))


@router.get("/logs", summary="查看TG助手投递记录", dependencies=[DependAuth])
async def list_logs(limit: int = 20):
    user_id = CTX_USER_ID.get()
    bounded_limit = max(1, min(int(limit or 20), 100))
    logs = await TGAssistantDeliveryLog.filter(user_id=user_id).order_by("-created_at", "-id").limit(bounded_limit)
    return Success(data=[await item.to_dict(exclude_fields=["user_id"]) for item in logs])


@router.post("/chatwoot", summary="Chatwoot TG助手Webhook")
async def chatwoot_webhook(request: Request):
    raw_body = await request.body()
    try:
        await verify_chatwoot_signature(request, raw_body)
        payload = json.loads(raw_body.decode("utf-8") or "{}")
        result = await process_chatwoot_payload(payload)
        return Success(data=result)
    except ValueError as exc:
        logger.warning("tg assistant webhook rejected: %s", exc)
        return Fail(code=401, msg=str(exc))
    except Exception as exc:
        logger.exception("tg assistant webhook failed")
        return Fail(code=500, msg=str(exc))
