from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, Field, field_validator


class TokenSettings(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=100)
    description: str = Field(default="", max_length=500)
    is_enabled: bool = True
    expires_at: datetime | None = Field(default=None, description="null 表示永久有效；时间必须包含时区")

    @field_validator("expires_at")
    @classmethod
    def validate_expiry(cls, value):
        if value is not None:
            if value.tzinfo is None or value.utcoffset() is None:
                raise ValueError("到期时间必须包含时区")
            if value <= datetime.now(timezone.utc):
                raise ValueError("到期时间必须晚于当前时间")
        return value


class TokenCreate(TokenSettings):
    user_id: int = Field(gt=0)


class TokenToggle(BaseModel):
    model_config = ConfigDict(extra="forbid")
    is_enabled: bool


class TokenInfo(BaseModel):
    id: int
    name: str
    description: str
    user_id: int
    username: str
    user_active: bool
    created_by_id: int | None
    created_by_name: str | None
    is_enabled: bool
    expires_at: datetime | None
    last_used_at: datetime | None
    created_at: datetime
    updated_at: datetime
    status: str


class TokenResult(BaseModel):
    code: int = 200
    msg: str = "OK"
    data: TokenInfo


class TokenSecret(TokenInfo):
    token: str


class TokenSecretResult(TokenResult):
    data: TokenSecret


class TokenListResult(BaseModel):
    code: int = 200
    msg: str = "OK"
    data: list[TokenInfo]
    total: int
    page: int
    page_size: int


class TokenUserOption(BaseModel):
    id: int
    username: str
    alias: str | None


class TokenUserResult(BaseModel):
    code: int = 200
    msg: str = "OK"
    data: list[TokenUserOption]


class TokenDeleted(BaseModel):
    code: int = 200
    msg: str = "已删除"
    data: None = None
