"""鉴权 API。

Stage 1.1-1.3 接口：
- POST /auth/register  注册
- POST /auth/verify-email  邮箱验证
- POST /auth/resend-verification  重发验证码
- POST /auth/login  登录
- POST /auth/logout  登出
- POST /auth/refresh  刷新 token
- POST /auth/forgot-password/send  发送密码找回验证码
- POST /auth/forgot-password/reset  重设密码
- POST /auth/2fa/setup  2FA 设置（返回 QR）
- POST /auth/2fa/enable  确认开启 2FA
- POST /auth/2fa/disable  关闭 2FA
- GET  /auth/devices  登录设备列表
- DELETE /auth/devices/{device_id}  强制下线
- POST /auth/change-password  修改密码
"""

from typing import List

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.auth import (
    ChangePasswordRequest,
    ForgotPasswordResetRequest,
    ForgotPasswordSendRequest,
    LoginDeviceBrief,
    LoginRequest,
    LogoutRequest,
    MessageResponse,
    RefreshRequest,
    RegisterRequest,
    ResendVerificationRequest,
    TOTPDisableRequest,
    TOTPEnableConfirmRequest,
    TOTPSetupResponse,
    TokenPair,
    UserBrief,
    VerifyEmailRequest,
)
from app.schemas.common import success
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["鉴权"])


@router.post("/register", response_model=dict, summary="注册")
async def register(data: RegisterRequest, db: AsyncSession = Depends(get_db)):
    user = await auth_service.register(db, data)
    await db.commit()
    return success({"user_id": str(user.id), "email": user.email}, "注册成功，请查收邮箱验证码")


@router.post("/verify-email", response_model=dict, summary="邮箱验证")
async def verify_email(data: VerifyEmailRequest, db: AsyncSession = Depends(get_db)):
    user = await auth_service.verify_email(db, data)
    await db.commit()
    return success({"email": user.email}, "邮箱验证成功")


@router.post("/resend-verification", response_model=dict, summary="重发邮箱验证码")
async def resend_verification(
    data: ResendVerificationRequest, db: AsyncSession = Depends(get_db)
):
    await auth_service.resend_verification(db, data)
    await db.commit()
    return success(None, "若邮箱存在，验证码已发送")


@router.post("/login", response_model=dict, summary="登录")
async def login(
    data: LoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    pair: TokenPair = await auth_service.login(db, data, request)
    await db.commit()
    return success(pair.model_dump(mode="json"), "登录成功")


@router.post("/logout", response_model=dict, summary="登出")
async def logout(
    data: LogoutRequest,
    db: AsyncSession = Depends(get_db),
):
    await auth_service.logout(db, RefreshRequest(refresh_token=data.refresh_token))
    await db.commit()
    return success(None, "已登出")


@router.post("/refresh", response_model=dict, summary="刷新 Access Token")
async def refresh(data: RefreshRequest, db: AsyncSession = Depends(get_db)):
    pair: TokenPair = await auth_service.refresh_token_pair(db, data)
    await db.commit()
    return success(pair.model_dump(mode="json"), "刷新成功")


@router.post("/forgot-password/send", response_model=dict, summary="发送密码找回验证码")
async def forgot_password_send(
    data: ForgotPasswordSendRequest, db: AsyncSession = Depends(get_db)
):
    await auth_service.forgot_password_send(db, data)
    await db.commit()
    return success(None, "若邮箱存在，验证码已发送")


@router.post("/forgot-password/reset", response_model=dict, summary="重设密码")
async def forgot_password_reset(
    data: ForgotPasswordResetRequest, db: AsyncSession = Depends(get_db)
):
    await auth_service.forgot_password_reset(db, data)
    await db.commit()
    return success(None, "密码重置成功，请重新登录")


@router.post("/change-password", response_model=dict, summary="修改密码")
async def change_password(
    data: ChangePasswordRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await auth_service.change_password(db, current_user, data.old_password, data.new_password)
    await db.commit()
    return success(None, "密码修改成功，所有设备已下线")


# ---------- 2FA ----------


@router.post("/2fa/setup", response_model=dict, summary="2FA 设置（返回 QR）")
async def totp_setup(current_user: User = Depends(get_current_user)):
    data = await auth_service.totp_setup(current_user)
    return success(TOTPSetupResponse(**data).model_dump(mode="json"), "请用 Google Authenticator 扫码")


@router.post("/2fa/enable", response_model=dict, summary="确认开启 2FA")
async def totp_enable(
    data: TOTPEnableConfirmRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await auth_service.totp_enable_confirm(db, current_user, data)
    await db.commit()
    return success(None, "2FA 已启用")


@router.post("/2fa/disable", response_model=dict, summary="关闭 2FA")
async def totp_disable(
    data: TOTPDisableRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await auth_service.totp_disable(db, current_user, data)
    await db.commit()
    return success(None, "2FA 已关闭")


# ---------- 登录设备 ----------


@router.get("/devices", response_model=dict, summary="登录设备列表")
async def list_devices(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    devices = await auth_service.list_login_devices(db, current_user.id)
    items = [
        LoginDeviceBrief(
            id=str(d.id),
            device_name=d.device_name,
            ip=d.ip,
            last_active_at=d.last_active_at,
            is_revoked=d.is_revoked,
        ).model_dump(mode="json")
        for d in devices
    ]
    return success(items)


@router.delete("/devices/{device_id}", response_model=dict, summary="强制下线设备")
async def revoke_device(
    device_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await auth_service.revoke_login_device(db, current_user.id, device_id)
    await db.commit()
    return success(None, "设备已下线")


@router.get("/me", response_model=dict, summary="当前用户信息")
async def me(current_user: User = Depends(get_current_user)):
    brief = UserBrief(
        id=str(current_user.id),
        email=current_user.email,
        nickname=current_user.nickname,
        role=current_user.role,
        email_verified=current_user.email_verified,
        totp_enabled=current_user.totp_enabled,
        risk_agreed_at=current_user.risk_agreed_at,
    )
    return success(brief.model_dump(mode="json"))
