import hashlib
import re
import secrets
from datetime import timedelta

from fastapi import HTTPException
from tortoise.expressions import Q
from tortoise.timezone import now

from app.models.admin import ApiToken, User

TOKEN_PREFIX = "fw_api_"


def generate_token() -> tuple[str, str]:
    token = TOKEN_PREFIX + secrets.token_urlsafe(32)
    return token, hashlib.sha256(token.encode()).hexdigest()


async def authenticate_api_token(token: str) -> User:
    if not re.fullmatch(r"fw_api_[A-Za-z0-9_-]{43}", token):
        raise HTTPException(status_code=401, detail="无效的 API token")
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    item = await ApiToken.filter(token_hash=token_hash, is_enabled=True).select_related("user").first()
    current_time = now()
    if not item or (item.expires_at and item.expires_at <= current_time) or not item.user.is_active:
        raise HTTPException(status_code=401, detail="API token 无效、已停用或已过期")
    # Throttle usage timestamps without caching authorization or delaying revocation.
    await ApiToken.filter(id=item.id, token_hash=token_hash).filter(
        Q(last_used_at=None) | Q(last_used_at__lt=current_time - timedelta(minutes=1))
    ).update(last_used_at=current_time)
    return item.user
