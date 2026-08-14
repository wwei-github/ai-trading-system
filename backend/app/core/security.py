"""安全工具集合。

包含：
- 密码哈希（passlib + bcrypt）
- JWT 编解码（python-jose）
- TOTP 2FA（pyotp + qrcode）
- 敏感信息脱敏（API Key / 邮箱 / 手机号）
"""

import base64
import hashlib
import io
import re
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import pyotp
import qrcode
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings


# ---------- 密码哈希 ----------

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """生成 bcrypt 密码哈希。"""
    return _pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    """校验明文密码与哈希是否匹配。"""
    try:
        return _pwd_context.verify(plain, hashed)
    except Exception:
        return False


# ---------- JWT ----------


def _jwt_secret() -> str:
    return settings.JWT_SECRET_KEY or settings.SECRET_KEY


def create_access_token(
    sub: str, extra: Optional[Dict[str, Any]] = None
) -> str:
    """生成 Access Token。"""
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload: Dict[str, Any] = {
        "sub": sub,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
        "type": "access",
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, _jwt_secret(), algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(sub: str, remember_me: bool = False) -> tuple[str, datetime]:
    """生成 Refresh Token。返回 (token, expires_at)。

    原文仅返回给客户端一次；DB 中只存 SHA-256(token)。
    """
    now = datetime.now(timezone.utc)
    days = settings.REMEMBER_ME_DAYS if remember_me else settings.REFRESH_TOKEN_EXPIRE_DAYS
    expire = now + timedelta(days=days)
    payload = {
        "sub": sub,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
        "type": "refresh",
        "jti": secrets.token_hex(16),
    }
    token = jwt.encode(payload, _jwt_secret(), algorithm=settings.JWT_ALGORITHM)
    return token, expire


def decode_token(token: str) -> Dict[str, Any]:
    """解码并校验 JWT。失败抛 JWTError。"""
    return jwt.decode(token, _jwt_secret(), algorithms=[settings.JWT_ALGORITHM])


def hash_token(token: str) -> str:
    """对 token 取 SHA-256，用于 DB 唯一索引存储。"""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


# ---------- TOTP 2FA ----------


def generate_totp_secret() -> str:
    """生成随机 TOTP 密钥（base32）。"""
    return pyotp.random_base32()


def build_totp_uri(secret: str, account: str) -> str:
    """构建 otpauth:// URI。"""
    issuer = settings.APP_NAME
    return pyotp.totp.TOTP(secret).provisioning_uri(name=account, issuer_name=issuer)


def verify_totp(secret: str, code: str) -> bool:
    """校验 TOTP 验证码（允许 ±1 个 30s 窗口）。"""
    try:
        totp = pyotp.totp.TOTP(secret)
        return totp.verify(code, valid_window=1)
    except Exception:
        return False


def generate_qr_base64(uri: str) -> str:
    """将 otpauth URI 渲染为 base64 PNG（data URL）。"""
    img = qrcode.make(uri)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/png;base64,{b64}"


# ---------- 一次性验证码 ----------


def generate_numeric_code(length: int = 6) -> str:
    """生成数字验证码（默认 6 位）。"""
    return "".join(secrets.choice("0123456789") for _ in range(length))


# ---------- 脱敏 ----------


def mask_api_key(key: str) -> str:
    """API Key 脱敏：首尾各 4 位，中间 ****。"""
    if not key or len(key) <= 8:
        return "****"
    return f"{key[:4]}****{key[-4:]}"


def mask_email(email: str) -> str:
    """邮箱脱敏：前 2 位 + ****@域名。"""
    if not email or "@" not in email:
        return email
    name, domain = email.split("@", 1)
    if len(name) <= 2:
        return f"{'*' * len(name)}@{domain}"
    return f"{name[:2]}{'*' * max(3, len(name) - 2)}@{domain}"


def mask_phone(phone: str) -> str:
    """手机号脱敏：保留前 3 后 4。"""
    if not phone or len(phone) < 7:
        return "****"
    return f"{phone[:3]}****{phone[-4:]}"


def mask_secret_in_dict(d: Dict[str, Any], keys: Optional[set] = None) -> Dict[str, Any]:
    """递归将字典中指定键的值脱敏。

    默认对常见敏感字段名脱敏。
    """
    if not isinstance(d, dict):
        return d
    sensitive = keys or {
        "api_key", "api_secret", "secret", "passphrase",
        "password", "hashed_password", "totp_secret",
        "token", "access_token", "refresh_token",
    }
    out: Dict[str, Any] = {}
    for k, v in d.items():
        if isinstance(v, dict):
            out[k] = mask_secret_in_dict(v, sensitive)
        elif isinstance(v, list):
            out[k] = [mask_secret_in_dict(x, sensitive) if isinstance(x, dict) else x for x in v]
        elif k.lower() in sensitive and v:
            out[k] = "****"
        else:
            out[k] = v
    return out
