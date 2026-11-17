from tortoise import fields

from .base import BaseModel, TimestampMixin


class DeviceSecretUnlockAttempt(BaseModel, TimestampMixin):
    user_id = fields.BigIntField(unique=True)
    window_start = fields.BigIntField(default=0)
    attempts = fields.IntField(default=0)

    class Meta:
        table = "device_secret_unlock_attempt"
