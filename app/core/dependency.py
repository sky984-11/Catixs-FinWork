from typing import Optional

import jwt
from fastapi import Depends, Header, HTTPException, Request

from app.core.ctx import CTX_USER_ID
from app.models import Role, User
from app.settings import settings

ADMIN_ROLE_NAMES = {"admin", "管理员"}


async def has_admin_role(user: User) -> bool:
    roles: list[Role] = await user.roles
    role_names = {str(role.name or "").strip().lower() for role in roles}
    return bool(role_names & ADMIN_ROLE_NAMES)


class AuthControl:
    @classmethod
    async def is_authed(
        cls,
        token: str = Header(None, description="登录 JWT 或 API token"),
        authorization: str = Header(None, description="Bearer <API token>，与 token 请求头二选一"),
    ) -> Optional["User"]:
        try:
            # Direct callers (audit logging and WebSockets) only supply token.
            token = token if isinstance(token, str) else None
            authorization = authorization if isinstance(authorization, str) else None
            if authorization:
                scheme, _, credential = authorization.partition(" ")
                if scheme.lower() != "bearer" or not credential.strip():
                    raise HTTPException(status_code=401, detail="无效的 Authorization 请求头")
                if token and token != credential.strip():
                    raise HTTPException(status_code=401, detail="认证请求头冲突")
                token = credential.strip()
            if not token:
                raise HTTPException(status_code=401, detail="请提供认证 token")
            if token.startswith("fw_api_"):
                from app.services.api_tokens import authenticate_api_token

                user = await authenticate_api_token(token)
                CTX_USER_ID.set(int(user.id))
                return user
            if token == "dev":
                user = await User.filter().first()
                if not user:
                    raise HTTPException(status_code=401, detail="Authentication failed")
                user_id = user.id
            else:
                decode_data = jwt.decode(token, settings.SECRET_KEY, algorithms=settings.JWT_ALGORITHM)
                user_id = decode_data.get("user_id")
            user = await User.filter(id=user_id).first()
            if not user or not user.is_active:
                raise HTTPException(status_code=401, detail="Authentication failed")
            CTX_USER_ID.set(int(user_id))
            return user
        except HTTPException:
            raise
        except jwt.DecodeError:
            raise HTTPException(status_code=401, detail="无效的Token")
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="登录已过期")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"{repr(e)}")


class PermissionControl:
    @classmethod
    async def has_permission(cls, request: Request, current_user: User = Depends(AuthControl.is_authed)) -> None:
        if current_user.is_superuser:
            return
        if await has_admin_role(current_user):
            return
        method = request.method
        path = request.url.path
        roles: list[Role] = await current_user.roles
        if not roles:
            raise HTTPException(status_code=403, detail="The user is not bound to a role")
        apis = [await role.apis for role in roles]
        permission_apis = list(set((api.method, api.path) for api in sum(apis, [])))
        # path = "/api/v1/auth/userinfo"
        # method = "GET"
        route_path = getattr(request.scope.get("route"), "path", path)
        if (method, path) not in permission_apis and (method, route_path) not in permission_apis:
            raise HTTPException(status_code=403, detail=f"Permission denied method:{method} path:{path}")


DependAuth = Depends(AuthControl.is_authed)
DependPermission = Depends(PermissionControl.has_permission)
