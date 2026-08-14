"""交易所账号服务。"""

import time
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import (
    BadRequestException,
    ConflictException,
    ServiceUnavailableException,
)
from app.core.security import mask_api_key
from app.exchange import ExchangeAdapterError, ExchangeFactory
from app.models.account import ExchangeAccount
from app.models.trade import Trade
from app.schemas.account import ExchangeAccountCreate, ExchangeAccountUpdate
from app.utils.crypto import decrypt, encrypt

# 普通用户最大账号数
ACCOUNT_MAX_COUNT = 10


class AccountService:
    """交易所账号服务。

    处理账号的增删改查和 API 凭证加密，
    以及交易所连接测试、余额查询等操作。
    所有交易所交互通过 `ExchangeFactory` 创建的 adapter 完成。
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_account(
        self, user_id: uuid.UUID, data: ExchangeAccountCreate
    ) -> ExchangeAccount:
        """创建交易所账号（加密存储凭证）。

        - 数量限制：每用户最多 ACCOUNT_MAX_COUNT 个
        - 交易所校验：通过 ExchangeFactory.is_supported 校验
        - 加密存储：api_key / api_secret / passphrase 全部 AES 加密
        """
        # 交易所名称校验
        if not ExchangeFactory.is_supported(data.exchange):
            raise BadRequestException(
                f"不支持的交易所: {data.exchange}",
                detail={
                    "exchange": data.exchange,
                    "supported": ExchangeFactory.supported_exchanges(),
                },
            )

        # passphrase 必填校验：OKX / Coinbase 创建 API Key 时必须设置口令
        from app.exchange import SUPPORTED_EXCHANGES
        adapter_cls = SUPPORTED_EXCHANGES[
            ExchangeFactory._normalize_name(data.exchange)
        ]
        if adapter_cls.requires_passphrase and not data.passphrase:
            raise BadRequestException(
                f"{data.exchange} 交易所需要 passphrase（创建 API Key 时设置的口令）",
                detail={"exchange": data.exchange, "requires_passphrase": True},
            )

        # 数量限制检查
        count_result = await self.db.execute(
            select(func.count(ExchangeAccount.id)).where(
                ExchangeAccount.user_id == user_id
            )
        )
        count = count_result.scalar() or 0
        if count >= ACCOUNT_MAX_COUNT:
            raise BadRequestException(
                f"每个用户最多绑定 {ACCOUNT_MAX_COUNT} 个交易所账号",
                detail={"current_count": count, "max": ACCOUNT_MAX_COUNT},
            )

        account = ExchangeAccount(
            user_id=user_id,
            exchange=data.exchange,
            label=data.label,
            api_key_encrypted=encrypt(data.api_key),
            api_secret_encrypted=encrypt(data.api_secret),
            passphrase_encrypted=encrypt(data.passphrase)
            if data.passphrase
            else None,
            permissions=data.permissions,
            is_testnet=data.is_testnet,
        )
        self.db.add(account)
        await self.db.flush()
        await self.db.refresh(account)
        return account

    async def get_account(
        self, account_id: uuid.UUID
    ) -> Optional[ExchangeAccount]:
        """获取账号详情。"""
        result = await self.db.execute(
            select(ExchangeAccount).where(ExchangeAccount.id == account_id)
        )
        return result.scalar_one_or_none()

    async def list_accounts(
        self, user_id: uuid.UUID
    ) -> List[ExchangeAccount]:
        """获取用户的全部账号。"""
        result = await self.db.execute(
            select(ExchangeAccount)
            .where(ExchangeAccount.user_id == user_id)
            .order_by(ExchangeAccount.created_at.desc())
        )
        return list(result.scalars().all())

    async def update_account(
        self, account_id: uuid.UUID, data: ExchangeAccountUpdate
    ) -> Optional[ExchangeAccount]:
        """更新账号信息。"""
        account = await self.get_account(account_id)
        if account is None:
            return None
        update_data = data.model_dump(exclude_unset=True)
        # 如果更新了 API Key / Secret，需要重新加密
        if "api_key" in update_data:
            account.api_key_encrypted = encrypt(update_data.pop("api_key"))
        if "api_secret" in update_data:
            account.api_secret_encrypted = encrypt(update_data.pop("api_secret"))
        if "passphrase" in update_data:
            passphrase = update_data.pop("passphrase")
            account.passphrase_encrypted = encrypt(passphrase) if passphrase else None
        for key, value in update_data.items():
            setattr(account, key, value)
        await self.db.flush()
        await self.db.refresh(account)
        return account

    async def toggle_account(
        self, account_id: uuid.UUID, is_enabled: bool
    ) -> Optional[ExchangeAccount]:
        """启用/停用账号。

        - 启用：status 恢复为 active（除非之前是 abnormal）
        - 停用：仅设置 is_enabled=False，不影响 status（异常状态保留）
        """
        account = await self.get_account(account_id)
        if account is None:
            return None
        account.is_enabled = is_enabled
        if is_enabled and account.status == "disabled":
            account.status = "active"
        await self.db.flush()
        await self.db.refresh(account)
        return account

    async def delete_account(
        self, account_id: uuid.UUID
    ) -> bool:
        """删除账号（含依赖检查）。

        - 检查是否有近 30 天关联交易记录 → 拒绝删除
        - 检查账号是否处于同步中 → 拒绝删除（避免数据不一致）
        """
        account = await self.get_account(account_id)
        if account is None:
            return False

        # 依赖检查：是否有近期关联交易（最近 30 天）
        from datetime import timedelta

        recent_trades_result = await self.db.execute(
            select(func.count(Trade.id)).where(
                Trade.account_id == account_id,
                Trade.executed_at >= datetime.now(timezone.utc) - timedelta(days=30),
            )
        )
        recent_trades = recent_trades_result.scalar() or 0
        if recent_trades > 0:
            raise ConflictException(
                "该账号有近 30 天的关联交易记录，无法删除",
                detail={"recent_trades": recent_trades},
            )

        await self.db.delete(account)
        await self.db.flush()
        return True

    async def get_account_snapshots(
        self, account_id: uuid.UUID, limit: int = 100
    ) -> list:
        """获取账号资产快照历史。"""
        from app.models.asset import AssetSnapshot

        result = await self.db.execute(
            select(AssetSnapshot)
            .where(AssetSnapshot.account_id == account_id)
            .order_by(AssetSnapshot.snapshot_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    # ---------- 凭证管理（永不外泄明文） ----------

    def get_masked_api_key(self, account: ExchangeAccount) -> str:
        """获取脱敏的 API Key（仅展示首尾 4 位）。"""
        try:
            plaintext = decrypt(account.api_key_encrypted)
            return mask_api_key(plaintext)
        except Exception:
            return "****"

    def get_decrypted_credentials(
        self, account: ExchangeAccount
    ) -> dict:
        """解密账号凭证（仅在调用交易所 API 时使用）。

        ⚠️ 永远不要将返回值写入日志或响应。
        """
        return {
            "api_key": decrypt(account.api_key_encrypted),
            "api_secret": decrypt(account.api_secret_encrypted),
            "passphrase": (
                decrypt(account.passphrase_encrypted)
                if account.passphrase_encrypted
                else None
            ),
        }

    def _build_adapter(self, account: ExchangeAccount):
        """根据账号构建交易所适配器（使用 ExchangeFactory）。"""
        credentials = self.get_decrypted_credentials(account)
        return ExchangeFactory.create(
            exchange=account.exchange,
            api_key=credentials["api_key"],
            api_secret=credentials["api_secret"],
            passphrase=credentials.get("passphrase"),
            is_testnet=account.is_testnet,
        )

    # ---------- 交易所交互（通过 adapter） ----------

    async def test_connection(
        self, account: ExchangeAccount
    ) -> dict:
        """测试交易所连接。

        Returns:
            包含 success / latency_ms / permissions / message 的字典
        """
        adapter = self._build_adapter(account)
        try:
            result = await adapter.connect()
            # 同步账号权限（若交易所返回了权限信息）
            if result.get("permissions"):
                account.permissions = result["permissions"]
                await self.db.flush()
            return result
        except ExchangeAdapterError as e:
            raise ServiceUnavailableException(
                message=str(e),
                detail={"exchange": account.exchange},
            )
        except Exception as e:
            raise ServiceUnavailableException(
                message=f"交易所连接失败: {str(e)}",
                detail={"exchange": account.exchange},
            )
        finally:
            await adapter.close()

    async def get_balance(
        self, account: ExchangeAccount
    ) -> dict:
        """查询账号余额。"""
        adapter = self._build_adapter(account)
        try:
            balance = await adapter.get_balance()
            return {
                "exchange": account.exchange,
                "is_testnet": account.is_testnet,
                "total": balance.get("total", {}),
                "free": balance.get("free", {}),
                "used": balance.get("used", {}),
            }
        except ExchangeAdapterError as e:
            raise ServiceUnavailableException(
                message=str(e),
                detail={"exchange": account.exchange},
            )
        except Exception as e:
            raise ServiceUnavailableException(
                message=f"获取余额失败: {str(e)}",
                detail={"exchange": account.exchange},
            )
        finally:
            await adapter.close()

    async def mark_account_abnormal(
        self, account_id: uuid.UUID, reason: str
    ) -> None:
        """标记账号为异常状态。"""
        account = await self.get_account(account_id)
        if account is not None:
            account.status = "abnormal"
            await self.db.flush()

    async def update_sync_time(
        self, account_id: uuid.UUID
    ) -> None:
        """更新账号最后同步时间。"""
        account = await self.get_account(account_id)
        if account is not None:
            account.last_sync_at = datetime.now(timezone.utc)
            await self.db.flush()
