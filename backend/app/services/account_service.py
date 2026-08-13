"""交易所账号服务。"""

import uuid
from datetime import datetime
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ServiceUnavailableException
from app.exchange.ccxt_client import CCXTClient
from app.models.account import ExchangeAccount
from app.schemas.account import ExchangeAccountCreate, ExchangeAccountUpdate
from app.utils.crypto import decrypt, encrypt


class AccountService:
    """交易所账号服务。

    处理账号的增删改查和 API 凭证加密，
    以及交易所连接测试、余额查询等操作。
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_account(
        self, user_id: uuid.UUID, data: ExchangeAccountCreate
    ) -> ExchangeAccount:
        """创建交易所账号（加密存储凭证）。"""
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
        for key, value in update_data.items():
            setattr(account, key, value)
        await self.db.flush()
        return account

    async def delete_account(
        self, account_id: uuid.UUID
    ) -> bool:
        """删除账号。"""
        account = await self.get_account(account_id)
        if account is None:
            return False
        await self.db.delete(account)
        await self.db.flush()
        return True

    def get_decrypted_credentials(
        self, account: ExchangeAccount
    ) -> dict:
        """解密账号凭证（仅在调用交易所 API 时使用）。"""
        return {
            "api_key": decrypt(account.api_key_encrypted),
            "api_secret": decrypt(account.api_secret_encrypted),
            "passphrase": (
                decrypt(account.passphrase_encrypted)
                if account.passphrase_encrypted
                else None
            ),
        }

    def _build_client(self, account: ExchangeAccount) -> CCXTClient:
        """根据账号构建 CCXT 客户端。"""
        credentials = self.get_decrypted_credentials(account)
        return CCXTClient(
            exchange=account.exchange,
            api_key=credentials["api_key"],
            api_secret=credentials["api_secret"],
            passphrase=credentials.get("passphrase"),
            is_testnet=account.is_testnet,
        )

    async def test_connection(
        self, account: ExchangeAccount
    ) -> dict:
        """测试交易所连接。

        Returns:
            包含 success / exchange / balance 的字典
        """
        client = self._build_client(account)
        try:
            balance = await client.fetch_balance()
            return {
                "success": True,
                "exchange": account.exchange,
                "is_testnet": account.is_testnet,
                "total": balance.get("total", {}),
            }
        except Exception as e:
            raise ServiceUnavailableException(
                message=f"交易所连接失败: {str(e)}",
                detail={"exchange": account.exchange},
            )
        finally:
            await client.close()

    async def get_balance(
        self, account: ExchangeAccount
    ) -> dict:
        """查询账号余额。"""
        client = self._build_client(account)
        try:
            balance = await client.fetch_balance()
            # 提取非零余额
            total = balance.get("total", {})
            non_zero = {
                k: v for k, v in total.items() if v and float(v) > 0
            }
            return {
                "exchange": account.exchange,
                "is_testnet": account.is_testnet,
                "total": non_zero,
                "free": {
                    k: v
                    for k, v in balance.get("free", {}).items()
                    if v and float(v) > 0
                },
                "used": {
                    k: v
                    for k, v in balance.get("used", {}).items()
                    if v and float(v) > 0
                },
            }
        except Exception as e:
            raise ServiceUnavailableException(
                message=f"获取余额失败: {str(e)}",
                detail={"exchange": account.exchange},
            )
        finally:
            await client.close()

    async def update_sync_time(
        self, account_id: uuid.UUID
    ) -> None:
        """更新账号最后同步时间。"""
        account = await self.get_account(account_id)
        if account is not None:
            account.last_sync_at = datetime.utcnow()
            await self.db.flush()
