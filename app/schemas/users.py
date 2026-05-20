from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, EmailStr, Field


class BaseUser(BaseModel):
    id: int
    email: Optional[EmailStr] = None
    username: Optional[str] = None
    avatar: Optional[str] = None
    is_active: Optional[bool] = True
    is_superuser: Optional[bool] = False
    created_at: Optional[datetime]
    updated_at: Optional[datetime]
    last_login: Optional[datetime]
    roles: Optional[list] = []


class UserCreate(BaseModel):
    email: EmailStr = Field(example="admin@qq.com")
    username: str = Field(example="admin")
    avatar: Optional[str] = None
    password: str = Field(example="123456")
    is_active: Optional[bool] = True
    is_superuser: Optional[bool] = False
    role_ids: Optional[List[int]] = []
    dept_id: Optional[int] = Field(0, description="部门ID")

    def create_dict(self):
        return self.model_dump(exclude_unset=True, exclude={"role_ids"})


class UserUpdate(BaseModel):
    id: int
    email: EmailStr
    username: str
    avatar: Optional[str] = None
    is_active: Optional[bool] = True
    is_superuser: Optional[bool] = False
    role_ids: Optional[List[int]] = []
    dept_id: Optional[int] = 0


class UpdatePassword(BaseModel):
    old_password: str = Field(description="旧密码")
    new_password: str = Field(description="新密码")


class UserProfileUpdate(BaseModel):
    username: str = Field(example="admin")
    email: EmailStr = Field(example="admin@qq.com")
    avatar: Optional[str] = None


class UserAvatarUpload(BaseModel):
    filename: str = Field(..., description="原始文件名", example="avatar.jpg")
    content_type: str = Field(..., description="文件 MIME 类型", example="image/jpeg")
    data: str = Field(..., description="Base64 内容，支持纯 base64 或 data URL")
