"""AES-256 加密/解密工具。

用于加密交易所 API Key 等敏感信息。
使用 Fernet 对称加密（基于 AES-128-CBC + HMAC-SHA256），
密钥从 ENCRYPTION_KEY 配置派生。
"""

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings


def _derive_key() -> bytes:
    """从配置的 ENCRYPTION_KEY 派生 Fernet 密钥。

    使用 SHA-256 哈希将任意长度的密钥派生为 32 字节，
    再进行 base64 编码以符合 Fernet 密钥格式。
    """
    raw_key = settings.ENCRYPTION_KEY.encode("utf-8")
    hashed = hashlib.sha256(raw_key).digest()
    return base64.urlsafe_b64encode(hashed)


def encrypt(plaintext: str) -> str:
    """加密明文。

    Args:
        plaintext: 待加密的明文字符串

    Returns:
        加密后的密文字符串（base64 编码）
    """
    if not plaintext:
        return ""
    fernet = Fernet(_derive_key())
    encrypted = fernet.encrypt(plaintext.encode("utf-8"))
    return encrypted.decode("utf-8")


def decrypt(ciphertext: str) -> str:
    """解密密文。

    Args:
        ciphertext: 待解密的密文字符串

    Returns:
        解密后的明文字符串

    Raises:
        InvalidToken: 密文无效或密钥不匹配时抛出
    """
    if not ciphertext:
        return ""
    fernet = Fernet(_derive_key())
    decrypted = fernet.decrypt(ciphertext.encode("utf-8"))
    return decrypted.decode("utf-8")
