"""鉴权 Schema。

注册、登录、Refresh、密码找回、2FA 等请求/响应模型。
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, field_validator


# ---------- 通用 ----------


class TokenPair(BaseModel):
    """登录/refresh 成功返回的 token 对。"""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = Field(..., description="Access Token 有效期（秒）")
    user: "UserBrief"


class UserBrief(BaseModel):
    """用户简要信息（嵌入 token 响应）。"""

    id: str
    email: EmailStr
    nickname: str
    role: str
    email_verified: bool
    totp_enabled: bool
    risk_agreed_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class MessageResponse(BaseModel):
    """仅含消息的简单响应。"""

    message: str
    detail: Optional[dict] = None


# ---------- 注册 ----------


class RegisterRequest(BaseModel):
    """注册请求。"""

    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    nickname: str = Field(..., min_length=1, max_length=100)
    risk_agreed: bool = Field(..., description="必须勾选风险提示同意")

    @field_validator("password")
    @classmethod
    def check_password_strength(cls, v: str) -> str:
        """密码复杂度：≥8 位，至少包含字母和数字。"""
        if len(v) < 8:
            raise ValueError("密码长度至少 8 位")
        if not any(c.isalpha() for c in v):
            raise ValueError("密码必须包含字母")
        if not any(c.isdigit() for c in v):
            raise ValueError("密码必须包含数字")
        return v

    @field_validator("risk_agreed")
    @classmethod
    def must_agree_risk(cls, v: bool) -> bool:
        if not v:
            raise ValueError("必须勾选风险提示同意")
        return v


# ---------- 登录 ----------


class LoginRequest(BaseModel):
    """登录请求。"""

    email: EmailStr
    password: str
    remember_me: bool = False
    totp_code: Optional[str] = Field(None, min_length=6, max_length=6)


# ---------- Refresh / 登出 ----------


class RefreshRequest(BaseModel):
    """刷新 token 请求。"""

    refresh_token: str


class LogoutRequest(BaseModel):
    """登出请求。"""

    refresh_token: str


# ---------- 邮箱验证 ----------


class VerifyEmailRequest(BaseModel):
    """邮箱验证请求。"""

    code: str = Field(..., min_length=4, max_length=64)


class ResendVerificationRequest(BaseModel):
    """重发邮箱验证码。"""

    email: EmailStr


# ---------- 密码找回 ----------


class ForgotPasswordSendRequest(BaseModel):
    """发送密码找回验证码。"""

    email: EmailStr


class ForgotPasswordResetRequest(BaseModel):
    """重设密码。"""

    email: EmailStr
    code: str = Field(..., min_length=4, max_length=64)
    new_password: str = Field(..., min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def check_password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("密码长度至少 8 位")
        if not any(c.isalpha() for c in v):
            raise ValueError("密码必须包含字母")
        if not any(c.isdigit() for c in v):
            raise ValueError("密码必须包含数字")
        return v


# ---------- 修改密码 ----------


class ChangePasswordRequest(BaseModel):
    """修改密码（已登录）。"""

    old_password: str
    new_password: str = Field(..., min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def check_password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("密码长度至少 8 位")
        if not any(c.isalpha() for c in v):
            raise ValueError("密码必须包含字母")
        if not any(c.isdigit() for c in v):
            raise ValueError("密码必须包含数字")
        return v


# ---------- 2FA ----------


class TOTPEnableRequest(BaseModel):
    """开启 2FA：返回 secret + qr_uri，需要用户用 App 扫码后再调用 confirm。"""

    pass


class TOTPEnableConfirmRequest(BaseModel):
    """确认开启 2FA：用户扫码后输入验证码。"""

    secret: str
    code: str = Field(..., min_length=6, max_length=6)


class TOTPDisableRequest(BaseModel):
    """关闭 2FA。"""

    code: str = Field(..., min_length=6, max_length=6)


class TOTPChallengeRequest(BaseModel):
    """高危动作 2FA 二次校验。"""

    code: str = Field(..., min_length=6, max_length=6)


class TOTPSetupResponse(BaseModel):
    """2FA 设置响应：返回 secret 与 otpauth URI。"""

    secret: str
    otpauth_uri: str
    qr_base64: str


# ---------- 设备 ----------


class LoginDeviceBrief(BaseModel):
    """登录设备简要。"""

    id: str
    device_name: str
    ip: Optional[str] = None
    last_active_at: datetime
    is_revoked: bool

    model_config = {"from_attributes": True}


# 解决前向引用
TokenPair.model_rebuild()
