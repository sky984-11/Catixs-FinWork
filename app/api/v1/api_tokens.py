from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from tortoise.expressions import Q
from tortoise.timezone import now

from app.core.dependency import DependAuth, has_admin_role
from app.models.admin import ApiToken, User
from app.schemas.api_tokens import (
    TokenCreate,
    TokenDeleted,
    TokenListResult,
    TokenResult,
    TokenSecretResult,
    TokenSettings,
    TokenToggle,
    TokenUserResult,
)
from app.services.api_tokens import generate_token


async def require_token_admin(request: Request, response: Response, user: User = DependAuth):
    response.headers["Cache-Control"] = "no-store"
    credential = request.headers.get("token") or request.headers.get("authorization", "").partition(" ")[2].strip()
    if credential == "dev":
        raise HTTPException(status_code=401, detail="管理 API tokens 需要正式登录凭据")
    if not user.is_superuser and not await has_admin_role(user):
        raise HTTPException(status_code=403, detail="仅管理员可管理 API tokens")
    return user


router = APIRouter(
    tags=["API tokens"],
    dependencies=[Depends(require_token_admin)],
    responses={
        401: {"description": "未登录或 token 无效、停用、过期"},
        403: {"description": "仅管理员可管理 API tokens"},
        404: {"description": "API token 不存在"},
        400: {"description": "绑定用户不存在或已停用"},
    },
)


async def token_info(item: ApiToken) -> dict:
    await item.fetch_related("user", "created_by")
    status = "enabled"
    if not item.user.is_active:
        status = "user_disabled"
    elif not item.is_enabled:
        status = "disabled"
    elif item.expires_at and item.expires_at <= now():
        status = "expired"
    return {
        "id": item.id,
        "name": item.name,
        "description": item.description,
        "user_id": item.user_id,
        "username": item.user.username,
        "user_active": item.user.is_active,
        "created_by_id": item.created_by_id,
        "created_by_name": item.created_by.username if item.created_by else None,
        "is_enabled": item.is_enabled,
        "expires_at": item.expires_at,
        "last_used_at": item.last_used_at,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
        "status": status,
    }


async def get_token(token_id: int) -> ApiToken:
    item = await ApiToken.get_or_none(id=token_id)
    if not item:
        raise HTTPException(status_code=404, detail="API token 不存在")
    return item


@router.get("", summary="查询 API tokens", response_model=TokenListResult)
async def list_tokens(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    name: str = Query("", max_length=100),
    user_id: int | None = Query(None, gt=0),
    status: Literal["enabled", "disabled", "expired", "user_disabled"] | None = None,
):
    query = ApiToken.all()
    if name:
        query = query.filter(name__icontains=name)
    if user_id:
        query = query.filter(user_id=user_id)
    if status == "user_disabled":
        query = query.filter(user__is_active=False)
    elif status:
        query = query.filter(user__is_active=True)
        if status == "disabled":
            query = query.filter(is_enabled=False)
        elif status == "expired":
            query = query.filter(is_enabled=True, expires_at__lte=now())
        else:
            query = query.filter(Q(expires_at=None) | Q(expires_at__gt=now()), is_enabled=True)
    total = await query.count()
    items = await query.order_by("-id").offset((page - 1) * page_size).limit(page_size)
    return {"data": [await token_info(item) for item in items], "total": total, "page": page, "page_size": page_size}


@router.get("/users", summary="查询可绑定 token 的用户", response_model=TokenUserResult)
async def token_users():
    return {"data": await User.filter(is_active=True).order_by("username").values("id", "username", "alias")}


@router.post("", summary="创建 API token（明文仅返回一次）", response_model=TokenSecretResult)
async def create_token(data: TokenCreate, creator: User = Depends(require_token_admin)):
    if not await User.filter(id=data.user_id, is_active=True).exists():
        raise HTTPException(status_code=400, detail="请选择有效的启用用户")
    secret, digest = generate_token()
    item = await ApiToken.create(**data.model_dump(), token_hash=digest, created_by_id=creator.id)
    return {"data": {**await token_info(item), "token": secret}}


@router.put("/{token_id}", summary="编辑 API token（归属用户不可修改）", response_model=TokenResult)
async def update_token(token_id: int, data: TokenSettings):
    item = await get_token(token_id)
    item.update_from_dict(data.model_dump())
    await item.save(update_fields=[*data.model_fields, "updated_at"])
    return {"data": await token_info(item)}


@router.post("/{token_id}/status", summary="启用或停用 API token", response_model=TokenResult)
async def toggle_token(token_id: int, data: TokenToggle):
    item = await get_token(token_id)
    item.is_enabled = data.is_enabled
    await item.save(update_fields=["is_enabled", "updated_at"])
    return {"data": await token_info(item)}


@router.post("/{token_id}/regenerate", summary="重新生成 API token（旧值立即失效）", response_model=TokenSecretResult)
async def regenerate_token(token_id: int):
    item = await get_token(token_id)
    secret, item.token_hash = generate_token()
    item.last_used_at = None
    await item.save(update_fields=["token_hash", "last_used_at", "updated_at"])
    return {"data": {**await token_info(item), "token": secret}}


@router.delete("/{token_id}", summary="删除并撤销 API token", response_model=TokenDeleted)
async def delete_token(token_id: int):
    item = await get_token(token_id)
    await item.delete()
    return {}
