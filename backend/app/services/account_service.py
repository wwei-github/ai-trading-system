"""交易所账号服务。"""

from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.account import ExchangeAccount
from app.schemas.account import ExchangeAccountCreate, ExchangeAccountUpdate
from app.utils.crypto import decrypt, encrypt


class AccountService:
    """交易所账号服务。

    处理账号的增删改查和 API 凭证加密。
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_account(
        self, user_id: str, data: ExchangeAccountCreate
    ) -> ExchangeAccount:
        """创建交易所账号（加密存储凭证）。"""
        account = ExchangeAccount(
            user_id=user_id,
            exchange=data.exchange,
            label=data.label,
            api_key_encrypted=encrypt(data.api_key),
            api_secret_encrypted=encrypt(data.api_secret),
            passphrase_encrypted=encrypt(data.passphrase) if data.passphrase else None,
            permissions=data.permissions,
            is_testnet=data.is_testnet,
        )
        self.db.add(account)
        await self.db.flush()
        return account

    async def get_account(self, account_id: str) -> Optional[ExchangeAccount]:
        """获取账号详情。"""
        result = await self.db.execute(
            select(ExchangeAccount).where(ExchangeAccount.id == account_id)
        )
        return result.scalar_one_or_none()

    async def list_accounts(self, user_id: str) -> List[ExchangeAccount]:
        """获取用户的全部账号。"""
        result = await self.db.execute(
            select(ExchangeAccount).where(ExchangeAccount.user_id == user_id)
        )
        return list(result.scalars().all())

    async def update_account(
        self, account_id: str, data: ExchangeAccountUpdate
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

    async def delete_account(self, account_id: str) -> bool:
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
