import base64
import binascii
import os
import uuid
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode, unquote, urlparse

import httpx
from fastapi import APIRouter, HTTPException, Query, Request

from app.controllers.user import user_controller
from app.core.ctx import CTX_USER_ID
from app.core.dependency import DependAuth, has_admin_role
from app.core.runtime_context import get_frontend_origin_from_request, is_local_origin
from app.log import logger
from app.models.admin import Api, Menu, Role, User
from app.schemas.base import Fail, Success
from app.schemas.login import *
from app.schemas.users import UpdatePassword, UserAvatarUpload, UserProfileUpdate
from app.settings import settings
from app.utils.jwt_utils import create_access_token
from app.utils.password import get_password_hash, verify_password

router = APIRouter()

FEISHU_API_BASE = "https://open.feishu.cn/open-apis"
FEISHU_OAUTH_AUTHORIZE_URL = "https://accounts.feishu.cn/open-apis/authen/v1/authorize"
FEISHU_OAUTH_TOKEN_URL = f"{FEISHU_API_BASE}/authen/v2/oauth/token"
FEISHU_USER_INFO_URL = f"{FEISHU_API_BASE}/authen/v1/user_info"
MENU_ICON_FALLBACKS = {
    "/syslog": "mdi:text-box-search-outline",
}

DEFAULT_AVATAR = "https://avatars.githubusercontent.com/u/54677442?v=4"
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))
AVATAR_UPLOAD_DIR = os.path.join(PROJECT_ROOT, "uploads", "avatars")
AVATAR_MAX_SIZE = 2 * 1024 * 1024
AVATAR_EXT_MAP = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/gif": ".gif",
    "image/webp": ".webp",
    "image/svg+xml": ".svg",
}


def normalize_avatar_url(avatar: str | None) -> str:
    avatar = str(avatar or "").strip()
    if not avatar:
        return DEFAULT_AVATAR

    parsed = urlparse(avatar)
    local_path = parsed.path if parsed.scheme or parsed.netloc else avatar
    if not local_path.startswith("/uploads/avatars/"):
        return avatar

    filename = os.path.basename(unquote(local_path))
    if not filename:
        return DEFAULT_AVATAR

    file_path = os.path.abspath(os.path.join(AVATAR_UPLOAD_DIR, filename))
    avatar_root = os.path.abspath(AVATAR_UPLOAD_DIR)
    if os.path.commonpath([avatar_root, file_path]) != avatar_root or not os.path.isfile(file_path):
        return DEFAULT_AVATAR
    return avatar


def clean_text(value) -> str:
    return str(value or "").strip()


def split_csv(value: str | None) -> set[str]:
    return {item.strip() for item in str(value or "").split(",") if item.strip()}


def feishu_oauth_enabled() -> bool:
    return bool(clean_text(settings.FEISHU_APP_ID) and clean_text(settings.FEISHU_APP_SECRET))


def is_dev_redirect_uri(redirect_uri: str) -> bool:
    try:
        parsed = urlparse(redirect_uri)
        dev_parsed = urlparse(clean_text(settings.WEB_DEV_BASE_URL))
    except ValueError:
        return False

    hostname = (parsed.hostname or "").lower()
    if hostname in {"localhost", "127.0.0.1", "::1"}:
        return True
    return bool(dev_parsed.scheme and dev_parsed.netloc and parsed.scheme == dev_parsed.scheme and parsed.netloc == dev_parsed.netloc)


def get_feishu_redirect_uri(redirect_uri: str | None = None) -> str:
    supplied = clean_text(redirect_uri)
    if supplied and is_dev_redirect_uri(supplied):
        return supplied

    configured = clean_text(settings.FEISHU_OAUTH_REDIRECT_URI)
    if configured:
        return configured
    if supplied:
        return supplied
    web_base_url = settings.get_web_base_url()
    return f"{web_base_url}/login" if web_base_url else ""


def get_feishu_redirect_uri_for_request(request: Request, redirect_uri: str | None = None) -> str:
    supplied = clean_text(redirect_uri)
    if supplied:
        return get_feishu_redirect_uri(supplied)

    origin = get_frontend_origin_from_request(request)
    if origin and is_local_origin(origin):
        return f"{origin.rstrip('/')}/login"

    return get_feishu_redirect_uri()


def build_feishu_oauth_url(*, redirect_uri: str, state: str) -> str:
    params = {
        "client_id": clean_text(settings.FEISHU_APP_ID),
        "redirect_uri": redirect_uri,
        "scope": clean_text(settings.FEISHU_OAUTH_SCOPE),
        "state": state,
    }
    return f"{FEISHU_OAUTH_AUTHORIZE_URL}?{urlencode(params)}"


def feishu_data(response: httpx.Response, action: str) -> dict:
    try:
        data = response.json()
    except ValueError:
        raise HTTPException(status_code=502, detail=f"{action} failed: Feishu returned non-json response")
    if response.status_code != 200 or data.get("code") not in (0, None):
        raise HTTPException(status_code=502, detail=f"{action} failed: {data.get('msg') or data}")
    payload = data.get("data")
    return payload if isinstance(payload, dict) else data


async def fetch_feishu_user_info(code: str, redirect_uri: str) -> dict:
    if not feishu_oauth_enabled():
        raise HTTPException(status_code=400, detail="Feishu OAuth is not configured")
    token_payload = {
        "grant_type": "authorization_code",
        "client_id": clean_text(settings.FEISHU_APP_ID),
        "client_secret": clean_text(settings.FEISHU_APP_SECRET),
        "code": clean_text(code),
        "redirect_uri": redirect_uri,
    }
    async with httpx.AsyncClient(timeout=10.0) as client:
        token_response = await client.post(FEISHU_OAUTH_TOKEN_URL, json=token_payload)
        token_data = feishu_data(token_response, "Feishu OAuth token exchange")
        user_access_token = clean_text(token_data.get("access_token") or token_data.get("user_access_token"))
        if not user_access_token:
            raise HTTPException(status_code=502, detail="Feishu OAuth token response missing access_token")
        token_scope = clean_text(token_data.get("scope"))

        user_response = await client.get(
            FEISHU_USER_INFO_URL,
            headers={"Authorization": f"Bearer {user_access_token}"},
        )
        user_info = feishu_data(user_response, "Feishu user info")
        user_info["_token_scope"] = token_scope
        logger.info(
            "feishu oauth user_info received: token_scope=%s fields=%s",
            token_scope or "<empty>",
            sorted(key for key in user_info.keys() if not key.startswith("_")),
        )
        return user_info


async def ensure_feishu_allowed_tenant(user_info: dict) -> None:
    tenant_key = clean_text(user_info.get("tenant_key"))
    allowed_tenant_keys = split_csv(settings.FEISHU_ALLOWED_TENANT_KEYS)

    if allowed_tenant_keys and tenant_key not in allowed_tenant_keys:
        raise HTTPException(status_code=403, detail="仅允许科特思网络科技公司员工使用飞书登录。")


async def resolve_feishu_login_user(user_info: dict) -> User:
    open_id = clean_text(user_info.get("open_id") or user_info.get("sub"))
    union_id = clean_text(user_info.get("union_id"))
    user_id = clean_text(user_info.get("user_id"))
    email = clean_text(user_info.get("email") or user_info.get("enterprise_email")).lower()

    await ensure_feishu_allowed_tenant(user_info)

    if not email:
        token_scope = clean_text(user_info.get("_token_scope")) or "<empty>"
        fields = ", ".join(sorted(key for key in user_info.keys() if not key.startswith("_"))) or "<empty>"
        raise HTTPException(
            status_code=403,
            detail=(
                "飞书未返回邮箱，无法匹配 FinWork 用户。"
                f"当前 user_access_token scope={token_scope}，user_info 字段={fields}。"
                "请确认飞书应用已在用户身份权限中开通并授权获取用户邮箱信息，且飞书员工资料已维护邮箱。"
            ),
        )

    user = await User.filter(email__iexact=email).first()
    if not user:
        raise HTTPException(
            status_code=403,
            detail=f"飞书邮箱 {email} 未匹配到 FinWork 用户，请确认数据库用户邮箱是否一致。",
        )
    if not user.is_active:
        raise HTTPException(status_code=403, detail="User is disabled")

    update_fields = []
    for field, value in (
        ("feishu_open_id", open_id),
        ("feishu_union_id", union_id),
        ("feishu_user_id", user_id),
    ):
        if value and getattr(user, field, None) != value:
            setattr(user, field, value)
            update_fields.append(field)

    avatar = clean_text(
        user_info.get("avatar_url")
        or user_info.get("picture")
        or user_info.get("avatar_big")
        or user_info.get("avatar_middle")
        or user_info.get("avatar_thumb")
    )
    if avatar and not user.avatar:
        user.avatar = avatar
        update_fields.append("avatar")

    name = clean_text(user_info.get("name") or user_info.get("en_name"))
    if name and not user.alias:
        user.alias = name[:30]
        update_fields.append("alias")

    if update_fields:
        update_fields.append("updated_at")
        await user.save(update_fields=list(dict.fromkeys(update_fields)))
    return user


def build_jwt_response(user: User) -> JWTOut:
    access_token_expires = timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    expire = datetime.now(timezone.utc) + access_token_expires
    return JWTOut(
        access_token=create_access_token(
            data=JWTPayload(
                user_id=user.id,
                username=user.username,
                is_superuser=user.is_superuser,
                exp=expire,
            )
        ),
        username=user.username,
    )


async def menu_to_dict_with_fallback(menu: Menu) -> dict:
    data = await menu.to_dict()
    if data.get("path") in MENU_ICON_FALLBACKS:
        data["icon"] = MENU_ICON_FALLBACKS[data["path"]]
    return data


@router.post("/access_token", summary="获取token")
async def login_access_token(credentials: CredentialsSchema):
    user: User = await user_controller.authenticate(credentials)
    await user_controller.update_last_login(user.id)
    data = build_jwt_response(user)
    return Success(data=data.model_dump())


@router.get("/feishu/oauth/config", summary="Feishu OAuth login config")
async def feishu_oauth_config(
    request: Request,
    redirect_uri: str | None = Query(default=None),
    state: str | None = Query(default=None),
):
    redirect_uri = get_feishu_redirect_uri_for_request(request, redirect_uri)
    state = clean_text(state) or uuid.uuid4().hex
    enabled = feishu_oauth_enabled() and bool(redirect_uri)
    data = {
        "enabled": enabled,
        "client_id": clean_text(settings.FEISHU_APP_ID),
        "redirect_uri": redirect_uri,
        "scope": clean_text(settings.FEISHU_OAUTH_SCOPE),
        "state": state,
        "auth_url": build_feishu_oauth_url(redirect_uri=redirect_uri, state=state) if enabled else "",
    }
    return Success(data=data)


@router.post("/feishu/oauth/login", summary="Feishu OAuth login")
async def feishu_oauth_login(payload: FeishuOAuthLogin):
    code = clean_text(payload.code)
    if not code:
        return Fail(code=400, msg="Feishu OAuth code is required")
    redirect_uri = get_feishu_redirect_uri(payload.redirect_uri)
    user_info = await fetch_feishu_user_info(code=code, redirect_uri=redirect_uri)
    user = await resolve_feishu_login_user(user_info)
    await user_controller.update_last_login(user.id)
    data = build_jwt_response(user)
    return Success(data=data.model_dump())


@router.get("/userinfo", summary="查看用户信息", dependencies=[DependAuth])
async def get_userinfo():
    user_id = CTX_USER_ID.get()
    user_obj = await user_controller.get(id=user_id)
    data = await user_obj.to_dict(m2m=True, exclude_fields=["password"])
    data["avatar"] = normalize_avatar_url(data.get("avatar"))
    return Success(data=data)


@router.post("/profile", summary="更新当前用户信息", dependencies=[DependAuth])
async def update_user_profile(profile_in: UserProfileUpdate):
    user_id = CTX_USER_ID.get()
    duplicated_user = await User.filter(email=profile_in.email).exclude(id=user_id).first()
    if duplicated_user:
        return Fail(code=400, msg="The user with this email already exists in the system.")

    user = await user_controller.get(id=user_id)
    user.username = profile_in.username
    user.email = str(profile_in.email)
    user.avatar = profile_in.avatar or None
    await user.save(update_fields=["username", "email", "avatar", "updated_at"])
    data = await user.to_dict(m2m=True, exclude_fields=["password"])
    data["avatar"] = normalize_avatar_url(data.get("avatar"))
    return Success(msg="Updated Successfully", data=data)


def decode_avatar_image(upload: UserAvatarUpload) -> tuple[bytes, str]:
    content_type = str(upload.content_type or "").strip().lower()
    base64_data = str(upload.data or "").strip()

    if base64_data.startswith("data:"):
        header, _, payload = base64_data.partition(",")
        if not payload:
            return b"", content_type
        if ";" in header:
            content_type = header[5:].split(";", 1)[0].strip().lower() or content_type
        base64_data = payload

    if content_type not in AVATAR_EXT_MAP:
        return b"", content_type

    try:
        content = base64.b64decode(base64_data, validate=True)
    except (binascii.Error, ValueError):
        return b"", content_type

    return content, content_type


@router.post("/avatar", summary="上传当前用户头像", dependencies=[DependAuth])
async def upload_user_avatar(upload: UserAvatarUpload):
    content, content_type = decode_avatar_image(upload)
    file_ext = AVATAR_EXT_MAP.get(content_type)
    if not content or not file_ext:
        return Fail(code=400, msg="Only JPG, PNG, GIF, WebP and SVG images are allowed.")

    if len(content) > AVATAR_MAX_SIZE:
        return Fail(code=400, msg="Avatar image must be smaller than 2MB.")

    user_id = CTX_USER_ID.get()
    os.makedirs(AVATAR_UPLOAD_DIR, exist_ok=True)
    filename = f"user_{user_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:8]}{file_ext}"
    file_path = os.path.join(AVATAR_UPLOAD_DIR, filename)
    with open(file_path, "wb") as f:
        f.write(content)

    avatar_url = f"/uploads/avatars/{filename}"
    user = await user_controller.get(id=user_id)
    user.avatar = avatar_url
    await user.save(update_fields=["avatar", "updated_at"])
    return Success(msg="上传成功", data={"avatar": avatar_url})


@router.get("/usermenu", summary="查看用户菜单", dependencies=[DependAuth])
async def get_user_menu():
    user_id = CTX_USER_ID.get()
    user_obj = await User.filter(id=user_id).first()
    if not user_obj:
        raise HTTPException(status_code=401, detail="Authentication failed")
    menus: list[Menu] = []
    if user_obj.is_superuser or await has_admin_role(user_obj):
        menus = await Menu.all()
    else:
        role_objs: list[Role] = await user_obj.roles
        for role_obj in role_objs:
            menu = await role_obj.menus
            menus.extend(menu)
        menus = list(set(menus))
        
        # 确保所有用户都能看到工单管理菜单
        ticket_menu = await Menu.filter(path="/ticket").first()
        if ticket_menu and ticket_menu not in menus:
            menus.append(ticket_menu)
        if ticket_menu:
            # 获取工单管理的子菜单
            ticket_sub_menus = await Menu.filter(parent_id=ticket_menu.id).all()
            for ticket_sub_menu in ticket_sub_menus:
                if ticket_sub_menu not in menus:
                    menus.append(ticket_sub_menu)
            ticket_route_menus = await Menu.filter(path__startswith="/ticket/").all()
            for ticket_route_menu in ticket_route_menus:
                if ticket_route_menu not in menus:
                    menus.append(ticket_route_menu)
    
    menu_ids = {menu.id for menu in menus}
    pending_parent_ids = {menu.parent_id for menu in menus if menu.parent_id}
    while pending_parent_ids:
        parent_id = pending_parent_ids.pop()
        if parent_id in menu_ids:
            continue
        parent_menu = await Menu.filter(id=parent_id).first()
        if not parent_menu:
            continue
        menus.append(parent_menu)
        menu_ids.add(parent_menu.id)
        if parent_menu.parent_id and parent_menu.parent_id not in menu_ids:
            pending_parent_ids.add(parent_menu.parent_id)

    parent_menus: list[Menu] = []
    for menu in menus:
        if menu.parent_id == 0:
            parent_menus.append(menu)
    res = []
    for parent_menu in parent_menus:
        parent_menu_dict = await menu_to_dict_with_fallback(parent_menu)
        parent_menu_dict["children"] = []
        for menu in menus:
            if menu.parent_id == parent_menu.id:
                parent_menu_dict["children"].append(await menu_to_dict_with_fallback(menu))
        res.append(parent_menu_dict)
    return Success(data=res)


@router.get("/userapi", summary="查看用户API", dependencies=[DependAuth])
async def get_user_api():
    user_id = CTX_USER_ID.get()
    user_obj = await User.filter(id=user_id).first()
    if not user_obj:
        raise HTTPException(status_code=401, detail="Authentication failed")
    if user_obj.is_superuser or await has_admin_role(user_obj):
        api_objs: list[Api] = await Api.all()
        apis = [api.method.lower() + api.path for api in api_objs]
        return Success(data=apis)
    role_objs: list[Role] = await user_obj.roles
    apis = []
    for role_obj in role_objs:
        api_objs: list[Api] = await role_obj.apis
        apis.extend([api.method.lower() + api.path for api in api_objs])
    apis = list(set(apis))
    return Success(data=apis)


@router.post("/update_password", summary="修改密码", dependencies=[DependAuth])
async def update_user_password(req_in: UpdatePassword):
    user_id = CTX_USER_ID.get()
    user = await user_controller.get(user_id)
    verified = verify_password(req_in.old_password, user.password)
    if not verified:
        return Fail(msg="旧密码验证错误！")
    user.password = get_password_hash(req_in.new_password)
    await user.save()
    return Success(msg="修改成功")
