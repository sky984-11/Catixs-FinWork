import base64
import binascii
import os
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException

from app.controllers.user import user_controller
from app.core.ctx import CTX_USER_ID
from app.core.dependency import DependAuth, has_admin_role
from app.models.admin import Api, Menu, Role, User
from app.schemas.base import Fail, Success
from app.schemas.login import *
from app.schemas.users import UpdatePassword, UserAvatarUpload, UserProfileUpdate
from app.settings import settings
from app.utils.jwt_utils import create_access_token
from app.utils.password import get_password_hash, verify_password

router = APIRouter()

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


async def menu_to_dict_with_fallback(menu: Menu) -> dict:
    data = await menu.to_dict()
    if data.get("path") in MENU_ICON_FALLBACKS:
        data["icon"] = MENU_ICON_FALLBACKS[data["path"]]
    return data


@router.post("/access_token", summary="获取token")
async def login_access_token(credentials: CredentialsSchema):
    user: User = await user_controller.authenticate(credentials)
    await user_controller.update_last_login(user.id)
    access_token_expires = timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    expire = datetime.now(timezone.utc) + access_token_expires

    data = JWTOut(
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
    return Success(data=data.model_dump())


@router.get("/userinfo", summary="查看用户信息", dependencies=[DependAuth])
async def get_userinfo():
    user_id = CTX_USER_ID.get()
    user_obj = await user_controller.get(id=user_id)
    data = await user_obj.to_dict(m2m=True, exclude_fields=["password"])
    data["avatar"] = data.get("avatar") or DEFAULT_AVATAR
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
    data["avatar"] = data.get("avatar") or DEFAULT_AVATAR
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
