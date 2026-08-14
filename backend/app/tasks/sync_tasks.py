"""数据同步任务。

定时从交易所同步交易记录和资产快照。

任务清单：
- sync_trades(account_id)：同步指定账号交易记录（增量）
- sync_asset_snapshot(account_id)：记录指定账号资产快照
- sync_all_accounts()：同步所有活跃账号数据（由 Celery Beat 定时触发）

Stage 2.4-2.5 增强：
- 使用 ExchangeFactory 适配器（替代直接 CCXTClient）
- is_enabled 过滤（同步任务只读取 enabled=True 的账号）
- 失败重试（Celery max_retries=3 + 指数退避）
- 失败标记账号 abnormal + 邮件通知用户
- exchange_order_id 去重（应用层查询，兼容 SQLite/Postgres）
- source="exchange_sync" 来源标记
"""

import asyncio
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional

from loguru import logger

from app.tasks import celery_app


# ---------- 内部辅助 ----------


async def _get_account_with_credentials(account_id: str):
    """加载账号并返回 (account, credentials, user_email)。"""
    from sqlalchemy import select

    from app.core.database import async_session_maker
    from app.models.account import ExchangeAccount
    from app.models.user import User
    from app.services.account_service import AccountService

    async with async_session_maker() as session:
        service = AccountService(session)
        account = await service.get_account(uuid.UUID(account_id))
        if account is None:
            return None, None, None
        credentials = service.get_decrypted_credentials(account)
        # 查询用户邮箱（用于同步失败通知）
        user_result = await session.execute(
            select(User.email).where(User.id == account.user_id)
        )
        user_email = user_result.scalar_one_or_none()
        # 让 account 脱离 session 仍可访问属性
        await session.refresh(account)
        return account, credentials, user_email


def _build_adapter(account, credentials):
    """根据账号构建交易所适配器。"""
    from app.exchange import ExchangeFactory

    return ExchangeFactory.create(
        exchange=account.exchange,
        api_key=credentials["api_key"],
        api_secret=credentials["api_secret"],
        passphrase=credentials.get("passphrase"),
        is_testnet=account.is_testnet,
        market_type="spot",  # V1 默认现货；后续可按 account.market_type 扩展
    )


async def _mark_account_abnormal(account_id: str, reason: str) -> None:
    """标记账号为异常状态。"""
    from sqlalchemy import select

    from app.core.database import async_session_maker
    from app.models.account import ExchangeAccount

    async with async_session_maker() as session:
        result = await session.execute(
            select(ExchangeAccount).where(ExchangeAccount.id == uuid.UUID(account_id))
        )
        account = result.scalar_one_or_none()
        if account is not None:
            account.status = "abnormal"
            await session.commit()
        logger.warning("账号已标记为异常 | account={} reason={}", account_id, reason)


async def _notify_sync_failed(
    user_email: Optional[str], account_alias: str, reason: str
) -> None:
    """通知用户同步失败（邮件）。"""
    if not user_email:
        return
    try:
        from app.integrations.email import send_sync_failed

        await send_sync_failed(user_email, account_alias, reason)
    except Exception as e:
        logger.warning("同步失败邮件通知异常 | to={} err={}", user_email, e)


# ---------- 同步交易记录 ----------


async def _sync_trades_async(account_id: str) -> dict:
    """异步同步交易记录（增量 + 去重 + source 标记）。"""
    from sqlalchemy import select

    from app.core.database import async_session_maker
    from app.models.account import ExchangeAccount
    from app.models.trade import Trade

    account, credentials, user_email = await _get_account_with_credentials(account_id)
    if account is None:
        logger.warning("账号不存在: {}", account_id)
        return {"account_id": account_id, "synced": 0, "reason": "account_not_found"}

    # is_enabled 过滤：只同步启用状态的账号
    if not account.is_enabled:
        logger.info("账号未启用，跳过同步: {}", account_id)
        return {"account_id": account_id, "synced": 0, "reason": "account_disabled"}

    if account.status not in ("active",):
        logger.warning("账号非活跃状态: {} status={}", account_id, account.status)
        return {
            "account_id": account_id,
            "synced": 0,
            "reason": f"account_status_{account.status}",
        }

    # 增量同步：从上次同步时间开始（容差 +1s 避免边界遗漏）
    since_ms: int
    if account.last_sync_at:
        since_ms = int(account.last_sync_at.timestamp() * 1000) - 1000
    else:
        # 默认拉取最近 30 天
        since_ms = int(datetime.now(timezone.utc).timestamp() * 1000) - 30 * 24 * 3600 * 1000

    adapter = _build_adapter(account, credentials)
    all_trades: List[Dict[str, Any]] = []
    try:
        # 拉取交易记录（不限定 symbol，由适配器内部处理）
        # 分页拉取（最多 10 页，每页 1000 条）
        for page in range(10):
            try:
                page_trades = await adapter.get_trades(
                    symbol=None, since=since_ms, limit=1000
                )
            except Exception as e:
                logger.warning(
                    "拉取交易记录失败 | account={} page={} err={}",
                    account_id, page, e,
                )
                break
            if not page_trades:
                break
            all_trades.extend(page_trades)
            if len(page_trades) < 1000:
                break
    except Exception as e:
        # 同步失败：标记账号异常 + 通知用户
        reason = str(e)
        logger.exception("同步交易记录失败 | account={} err={}", account_id, e)
        await _mark_account_abnormal(account_id, reason)
        await _notify_sync_failed(user_email, account.label, reason)
        return {
            "account_id": account_id,
            "synced": 0,
            "reason": "sync_failed",
            "error": reason,
        }
    finally:
        await adapter.close()

    # 写入数据库（去重 + source 标记）
    synced_count = 0
    skipped_count = 0
    async with async_session_maker() as session:
        # 查询已存在的订单 ID 用于去重（兼容 SQLite / Postgres）
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
                skipped_count += 1
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
                price=Decimal(str(t.get("price") or 0)),
                quantity=Decimal(str(t.get("amount") or 0)),
                fee=Decimal(str(t.get("fee", {}).get("cost", 0))) if t.get("fee") else None,
                fee_currency=t.get("fee", {}).get("currency") if t.get("fee") else None,
                status="filled",
                exchange_order_id=order_id,
                source="exchange_sync",  # 来源标记：交易所同步（关联关系不可删）
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
            # 同步成功后恢复 active 状态
            if acc.status == "abnormal":
                acc.status = "active"

        await session.commit()

    logger.info(
        "交易记录同步完成 | account={} synced={} skipped={}",
        account_id, synced_count, skipped_count,
    )
    return {
        "account_id": account_id,
        "synced": synced_count,
        "skipped": skipped_count,
    }


# ---------- 资产快照 ----------


async def _sync_asset_snapshot_async(account_id: str) -> dict:
    """异步记录资产快照。"""
    from sqlalchemy import select

    from app.core.database import async_session_maker
    from app.models.account import ExchangeAccount
    from app.models.asset import AssetSnapshot

    account, credentials, user_email = await _get_account_with_credentials(account_id)
    if account is None:
        return {"account_id": account_id, "total_usd": 0, "reason": "account_not_found"}

    if not account.is_enabled:
        return {"account_id": account_id, "total_usd": 0, "reason": "account_disabled"}

    if account.status not in ("active",):
        return {
            "account_id": account_id,
            "total_usd": 0,
            "reason": f"account_status_{account.status}",
        }

    adapter = _build_adapter(account, credentials)
    try:
        balance = await adapter.get_balance()
    except Exception as e:
        reason = str(e)
        logger.exception("记录资产快照失败 | account={} err={}", account_id, e)
        await _mark_account_abnormal(account_id, reason)
        await _notify_sync_failed(user_email, account.label, reason)
        return {
            "account_id": account_id,
            "total_usd": 0,
            "reason": "sync_failed",
            "error": reason,
        }
    finally:
        await adapter.close()

    total = balance.get("total", {})
    # 简化处理：仅将稳定币（USDT/USD/USDC/BUSD）计入 total_usd
    # 完整实现需在 Stage 5 接入行情服务转换
    total_usd = sum(
        v for k, v in total.items() if k in ("USDT", "USD", "BUSD", "USDC")
    )

    async with async_session_maker() as session:
        snapshot = AssetSnapshot(
            user_id=account.user_id,
            account_id=account.id,
            total_usd=Decimal(str(round(total_usd, 2))),
            balances={
                "total": total,
                "free": balance.get("free", {}),
                "used": balance.get("used", {}),
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
            if acc.status == "abnormal":
                acc.status = "active"

        await session.commit()

    logger.info(
        "资产快照已记录 | account={} total_usd={:.2f}",
        account_id, total_usd,
    )
    return {"account_id": account_id, "total_usd": round(total_usd, 2)}


# ---------- 同步所有账号 ----------


async def _sync_all_accounts_async() -> dict:
    """异步同步所有启用的活跃账号。"""
    from sqlalchemy import select

    from app.core.database import async_session_maker
    from app.models.account import ExchangeAccount

    async with async_session_maker() as session:
        result = await session.execute(
            select(ExchangeAccount).where(
                ExchangeAccount.is_enabled.is_(True),
                ExchangeAccount.status == "active",
            )
        )
        accounts = list(result.scalars().all())

    total = len(accounts)
    synced = 0
    failed = 0
    for acc in accounts:
        try:
            # 顺序同步避免触发交易所限频
            trades_result = await _sync_trades_async(str(acc.id))
            snapshot_result = await _sync_asset_snapshot_async(str(acc.id))
            if "error" not in trades_result and "error" not in snapshot_result:
                synced += 1
            else:
                failed += 1
        except Exception as e:
            failed += 1
            logger.exception("账号同步失败 | account={} err={}", acc.id, e)

    logger.info(
        "全部账号同步完成 | total={} synced={} failed={}", total, synced, failed,
    )
    return {"total_accounts": total, "synced": synced, "failed": failed}


# ---------- Celery 任务 ----------


@celery_app.task(
    name="sync_trades",
    bind=True,
    max_retries=3,
    retry_backoff=True,           # 指数退避
    retry_backoff_max=600,        # 最大退避 10 分钟
    retry_jitter=True,            # 抖动避免雪崩
    autoretry_for=(Exception,),
    retry_kwargs={"max_retries": 3},
)
def sync_trades(self, account_id: str) -> dict:
    """同步指定账号的交易记录。

    失败自动重试 3 次（指数退避）；
    最终失败时账号被标记为 abnormal 并邮件通知用户（在 _sync_trades_async 中处理）。
    """
    logger.info("开始同步交易记录 | account={} task={} attempt={}/3",
                account_id, self.request.id, self.request.retries + 1)
    try:
        return asyncio.run(_sync_trades_async(account_id))
    except Exception as e:
        logger.exception("同步交易记录任务异常 | account={} attempt={} err={}",
                         account_id, self.request.retries + 1, e)
        raise


@celery_app.task(
    name="sync_asset_snapshot",
    bind=True,
    max_retries=3,
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
    autoretry_for=(Exception,),
    retry_kwargs={"max_retries": 3},
)
def sync_asset_snapshot(self, account_id: str) -> dict:
    """记录指定账号的资产快照。"""
    logger.info("开始记录资产快照 | account={} task={} attempt={}/3",
                account_id, self.request.id, self.request.retries + 1)
    try:
        return asyncio.run(_sync_asset_snapshot_async(account_id))
    except Exception as e:
        logger.exception("资产快照任务异常 | account={} attempt={} err={}",
                         account_id, self.request.retries + 1, e)
        raise


@celery_app.task(name="sync_all_accounts", bind=True)
def sync_all_accounts(self) -> dict:
    """同步所有启用且活跃的账号数据（由 Celery Beat 定时触发）。"""
    logger.info("开始同步所有账号数据 | task={}", self.request.id)
    return asyncio.run(_sync_all_accounts_async())
