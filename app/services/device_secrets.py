"""IPMI secrets never belong in ordinary device payloads or audit bodies."""

import asyncio
import time
from copy import deepcopy

from fastapi import HTTPException
from tortoise.transactions import in_transaction

from app.models import DeviceSecretUnlockAttempt, User
from app.utils.password import verify_password

MASK = "******"


def is_ipmi_password(key):
    return str(key).replace("_", "").replace("-", "").replace(" ", "").lower() in {"ipmipassword", "ipmi密码"}


def mask_ipmi(value):
    if isinstance(value, dict):
        return {k: MASK if is_ipmi_password(k) and v else mask_ipmi(v) for k, v in value.items()}
    if isinstance(value, list):
        return [mask_ipmi(v) for v in value]
    return value


def ipmi_password(attributes):
    for key in ("ipmi_password", "ipmiPassword", "IPMI密码"):
        if attributes.get(key):
            return str(attributes[key])
    return next((str(v) for k, v in attributes.items() if is_ipmi_password(k) and v), "")


def preserve_ipmi(incoming, previous, can_edit=True):
    """Resolve masks by node identity, never by a node's array position."""
    result = deepcopy(incoming)
    keys = [k for k in result if is_ipmi_password(k)]
    old_keys = [k for k in previous if is_ipmi_password(k)]
    if not can_edit:
        for key in keys:
            result.pop(key)
        for key in old_keys:
            result[key] = previous[key]
    elif not keys:
        for key in old_keys:
            result[key] = previous[key]
    else:
        for key in keys:
            if result[key] == MASK:
                result[key] = previous.get(key) or ipmi_password(previous)
    old_nodes = {n.get("name"): n for n in previous.get("nodes", []) if isinstance(n, dict)}
    if isinstance(result.get("nodes"), list):
        result["nodes"] = [
            preserve_ipmi(n, old_nodes.get(n.get("name"), {}), can_edit) if isinstance(n, dict) else n
            for n in result["nodes"]
        ]
    return result


async def verify_unlock(user_id, password):
    user = await User.get_or_none(id=user_id, is_active=True)
    if not user:
        raise HTTPException(403, "账号不可用")
    if not user.password:
        raise HTTPException(400, "当前账号未设置登录密码，请先设置后解锁")
    now = int(time.time())
    async with in_transaction():
        await DeviceSecretUnlockAttempt.get_or_create(user_id=user.id)
        attempt = await DeviceSecretUnlockAttempt.filter(user_id=user.id).select_for_update().get()
        if now - attempt.window_start >= 900:
            attempt.window_start, attempt.attempts = now, 0
        if attempt.attempts >= 5:
            raise HTTPException(429, "解锁验证失败次数过多，请 15 分钟后重试")
        attempt.attempts += 1
        await attempt.save()
    try:
        valid = await asyncio.to_thread(verify_password, password, user.password)
    except (ValueError, TypeError):
        valid = False
    if not valid:
        raise HTTPException(400, "登录密码不正确")
    await DeviceSecretUnlockAttempt.filter(user_id=user.id).update(attempts=0, window_start=0)
