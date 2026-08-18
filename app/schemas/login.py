from datetime import datetime

from pydantic import BaseModel, Field


class CredentialsSchema(BaseModel):
    username: str = Field(..., description="用户名称", example="admin")
    password: str = Field(..., description="密码", example="123456")


class JWTOut(BaseModel):
    access_token: str
    username: str


class JWTPayload(BaseModel):
    user_id: int
    username: str
    is_superuser: bool
    exp: datetime


class FeishuOAuthLogin(BaseModel):
    code: str = Field(..., description="Feishu OAuth authorization code")
    redirect_uri: str = Field("", description="OAuth redirect URI used to request the code")
    state: str = Field("", description="OAuth state")
