"""数据同步任务。

定时从交易所同步交易记录和资产快照。

任务清单：
- sync_trades(account_id)：同步指定账号交易记录（增量）
- sync_asset_snapshot(account_id)：记录指定账号资产快照
- sync_all_accounts()：同步所有活跃账号数据（由 Celery Beat 定时触发）
"""

import asyncio
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List

from loguru import logger

from app.tasks import celery_app


async def _get_account_with_credentials(account_id: str):
    """加载账号并返回 (account, credentials)。"""
    from sqlalchemy import select

    from app.core.database import async_session_maker
    from app.models.account import ExchangeAccount
    from app.services.account_service import AccountService

    async with async_session_maker() as session:
        service = AccountService(session)
        account = await service.get_account(uuid.UUID(account_id))
        if account is None:
            return None, None
        credentials = service.get_decrypted_credentials(account)
        # 让 account 脱离 session 仍可访问属性
        await session.refresh(account)
        return account, credentials


async def _sync_trades_async(account_id: str) -> dict:
    """异步同步交易记录。"""
    from sqlalchemy import select

    from app.core.database import async_session_maker
    from app.exchange.ccxt_client import CCXTClient
    from app.models.account import ExchangeAccount
    from app.models.trade import Trade

    account, credentials = await _get_account_with_credentials(account_id)
    if account is None:
        logger.warning("账号不存在: {}", account_id)
        return {"account_id": account_id, "synced": 0, "reason": "account_not_found"}

    if account.status != "active":
        logger.warning("账号非活跃状态: {} status={}", account_id, account.status)
        return {
            "account_id": account_id,
            "synced": 0,
            "reason": f"account_status_{account.status}",
        }

    # 增量同步：从上次同步时间开始
    since_ms: int
    if account.last_sync_at:
        since_ms = int(account.last_sync_at.timestamp() * 1000)
    else:
        # 默认拉取最近 30 天
        since_ms = int(
            datetime.now(timezone.utc).timestamp() * 1000
        ) - 30 * 24 * 3600 * 1000

    client = CCXTClient(
        exchange=account.exchange,
        api_key=credentials["api_key"],
        api_secret=credentials["api_secret"],
        passphrase=credentials.get("passphrase"),
        is_testnet=account.is_testnet,
    )

    synced_count = 0
    try:
        await client.load_markets()
        # 遍历所有交易对（公开市场）拉取该账户成交记录
        # 限制为常见交易对，避免过多调用
        symbols_to_sync = ["BTC/USDT", "ETH/USDT"]
        # 若账号权限中有更多偏好，可在此扩展
        all_trades: List[Dict[str, Any]] = []
        for symbol in symbols_to_sync:
            try:
                trades = await client.fetch_trades(
                    symbol, since=since_ms, limit=1000
                )
                all_trades.extend(trades)
            except Exception as e:
                logger.warning(
                    "拉取交易记录失败 | account={} symbol={} err={}",
                    account_id,
                    symbol,
                    e,
                )

        async with async_session_maker() as session:
            # 查询已存在的订单 ID 用于去重
            existing_ids: set = set()
            if all_trades:
                order_ids = [
                    t.get("order") or t.get("id")
                    for t in all_trades
                    if t.get("order") or t.get("id")
                ]
                if order_ids:
                    res = await session.execute(
                        select(Trade.exchange_order_id).where(
                            Trade.account_id == account.id,
                            Trade.exchange_order_id.in_(order_ids),
                        )
                    )
                    existing_ids = {r[0] for r in res.all()}

            for t in all_trades:
                order_id = t.get("order") or t.get("id")
                if order_id and order_id in existing_ids:
                    continue

                # 解析成交时间
                ts = t.get("timestamp")
                executed_at = (
                    datetime.fromtimestamp(ts / 1000, tz=timezone.utc)
                    if ts
                    else datetime.now(timezone.utc)
                )

                trade = Trade(
                    user_id=account.user_id,
                    account_id=account.id,
                    exchange=account.exchange,
                    symbol=t.get("symbol", ""),
                    market_type="spot",  # 默认现货，可按账号配置扩展
                    side=t.get("side", ""),
                    order_type=t.get("type", "market"),
                    price=Decimal(str(t.get("price", 0))),
                    quantity=Decimal(str(t.get("amount", 0))),
                    fee=Decimal(str(t.get("fee", {}).get("cost", 0)))
                    if t.get("fee")
                    else None,
                    fee_currency=t.get("fee", {}).get("currency")
                    if t.get("fee")
                    else None,
                    status="filled",
                    exchange_order_id=order_id,
                    executed_at=executed_at,
                )
                session.add(trade)
                synced_count += 1

            # 更新最后同步时间
            acc_result = await session.execute(
                select(ExchangeAccount).where(ExchangeAccount.id == account.id)
            )
            acc = acc_result.scalar_one_or_none()
            if acc is not None:
                acc.last_sync_at = datetime.now(timezone.utc)

            await session.commit()

        logger.info(
            "交易记录同步完成 | account={} synced={}", account_id, synced_count
        )
        return {"account_id": account_id, "synced": synced_count}
    finally:
        await client.close()


async def _sync_asset_snapshot_async(account_id: str) -> dict:
    """异步记录资产快照。"""
    from sqlalchemy import select

    from app.core.database import async_session_maker
    from app.exchange.ccxt_client import CCXTClient
    from app.models.account import ExchangeAccount
    from app.models.asset import AssetSnapshot

    account, credentials = await _get_account_with_credentials(account_id)
    if account is None:
        return {"account_id": account_id, "total_usd": 0, "reason": "account_not_found"}

    if account.status != "active":
        return {
            "account_id": account_id,
            "total_usd": 0,
            "reason": f"account_status_{account.status}",
        }

    client = CCXTClient(
        exchange=account.exchange,
        api_key=credentials["api_key"],
        api_secret=credentials["api_secret"],
        passphrase=credentials.get("passphrase"),
        is_testnet=account.is_testnet,
    )

    try:
        balance = await client.fetch_balance()
        total = balance.get("total", {})
        # 过滤非零余额
        non_zero = {
            k: float(v) for k, v in total.items() if v and float(v) > 0
        }

        # USD 估值简化处理：USDT 按 1:1，其他币种需要行情转换（此处略）
        # 仅将 USDT/USD 部分计入 total_usd
        total_usd = sum(
            v for k, v in non_zero.items() if k in ("USDT", "USD", "BUSD", "USDC")
        )

        async with async_session_maker() as session:
            snapshot = AssetSnapshot(
                user_id=account.user_id,
                account_id=account.id,
                total_usd=Decimal(str(round(total_usd, 2))),
                balances={
                    "total": non_zero,
                    "free": {
                        k: float(v)
                        for k, v in balance.get("free", {}).items()
                        if v and float(v) > 0
                    },
                    "used": {
                        k: float(v)
                        for k, v in balance.get("used", {}).items()
                        if v and float(v) > 0
                    },
                },
                snapshot_at=datetime.now(timezone.utc),
            )
            session.add(snapshot)

            # 更新账号最后同步时间
            acc_result = await session.execute(
                select(ExchangeAccount).where(ExchangeAccount.id == account.id)
            )
            acc = acc_result.scalar_one_or_none()
            if acc is not None:
                acc.last_sync_at = datetime.now(timezone.utc)

            await session.commit()

        logger.info(
            "资产快照已记录 | account={} total_usd={:.2f}",
            account_id,
            total_usd,
        )
        return {"account_id": account_id, "total_usd": round(total_usd, 2)}
    finally:
        await client.close()


async def _sync_all_accounts_async() -> dict:
    """异步同步所有活跃账号。"""
    from sqlalchemy import select

    from app.core.database import async_session_maker
    from app.models.account import ExchangeAccount

    async with async_session_maker() as session:
        result = await session.execute(
            select(ExchangeAccount).where(ExchangeAccount.status == "active")
        )
        accounts = list(result.scalars().all())

    total = len(accounts)
    synced = 0
    for acc in accounts:
        try:
            # 顺序同步避免触发交易所限频
            await _sync_trades_async(str(acc.id))
            await _sync_asset_snapshot_async(str(acc.id))
            synced += 1
        except Exception as e:
            logger.exception("账号同步失败 | account={} err={}", acc.id, e)

    logger.info("全部账号同步完成 | total={} synced={}", total, synced)
    return {"total_accounts": total, "synced": synced}


@celery_app.task(name="sync_trades", bind=True)
def sync_trades(self, account_id: str) -> dict:
    """同步指定账号的交易记录。

    Args:
        account_id: 交易所账号 ID（字符串形式 UUID）

    Returns:
        同步结果
    """
    logger.info("开始同步交易记录 | account={} task={}", account_id, self.request.id)
    return asyncio.run(_sync_trades_async(account_id))


@celery_app.task(name="sync_asset_snapshot", bind=True)
def sync_asset_snapshot(self, account_id: str) -> dict:
    """记录指定账号的资产快照。

    Args:
        account_id: 交易所账号 ID（字符串形式 UUID）

    Returns:
        同步结果
    """
    logger.info("开始记录资产快照 | account={} task={}", account_id, self.request.id)
    return asyncio.run(_sync_asset_snapshot_async(account_id))


@celery_app.task(name="sync_all_accounts", bind=True)
def sync_all_accounts(self) -> dict:
    """同步所有活跃账号数据。

    Returns:
        同步结果
    """
    logger.info("开始同步所有账号数据 | task={}", self.request.id)
    return asyncio.run(_sync_all_accounts_async())
