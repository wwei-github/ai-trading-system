"""用户 Schema。

用户资料更新（Admin / 本人）相关请求/响应模型。
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class UserUpdateRequest(BaseModel):
    """用户资料更新（本人）。"""

    nickname: Optional[str] = Field(None, min_length=1, max_length=100)
    email: Optional[EmailStr] = None


class UserAdminUpdateRequest(BaseModel):
    """Admin 更新用户。"""

    nickname: Optional[str] = Field(None, min_length=1, max_length=100)
    role: Optional[str] = Field(None, pattern="^(admin|trader|viewer)$")
    is_active: Optional[bool] = None
    email_verified: Optional[bool] = None


class UserListItem(BaseModel):
    """用户列表项。"""

    id: str
    email: EmailStr
    nickname: str
    role: str
    is_active: bool
    email_verified: bool
    totp_enabled: bool
    last_login_at: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class AdminResetPasswordRequest(BaseModel):
    """Admin 重置用户密码（直接设置新密码，要求首次登录修改）。"""

    new_password: str = Field(..., min_length=8, max_length=128)
