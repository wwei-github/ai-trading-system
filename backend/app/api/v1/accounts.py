"""交易所账号接口。"""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.exceptions import NotFoundException
from app.models.user import User
from app.schemas.account import (
    ExchangeAccountCreate,
    ExchangeAccountResponse,
    ExchangeAccountUpdate,
)
from app.schemas.common import ApiResponse
from app.services.account_service import AccountService
from app.utils.audit import write_audit_log

router = APIRouter(prefix="/accounts", tags=["交易所账号"])


@router.get("/health", summary="健康检查")
async def health_check():
    """账号模块健康检查。"""
    return ApiResponse(data={"status": "ok", "module": "accounts"})


@router.get("", summary="获取账号列表")
async def list_accounts(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取当前用户的全部交易所账号。"""
    service = AccountService(db)
    accounts = await service.list_accounts(current_user.id)
    return ApiResponse(
        data=[
            ExchangeAccountResponse.model_validate(acc) for acc in accounts
        ]
    )


@router.post("", summary="创建交易所账号", status_code=201)
async def create_account(
    data: ExchangeAccountCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """创建交易所账号（API Key 加密存储）。"""
    service = AccountService(db)
    account = await service.create_account(current_user.id, data)
    await write_audit_log(
        db,
        user_id=current_user.id,
        action="create",
        resource_type="account",
        resource_id=account.id,
        detail={"exchange": account.exchange, "label": account.label},
    )
    return ApiResponse(data=ExchangeAccountResponse.model_validate(account))


@router.get("/{account_id}", summary="获取账号详情")
async def get_account(
    account_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取交易所账号详情。"""
    service = AccountService(db)
    account = await service.get_account(account_id)
    if account is None:
        raise NotFoundException(
            message="账号不存在", detail={"account_id": str(account_id)}
        )
    return ApiResponse(data=ExchangeAccountResponse.model_validate(account))


@router.patch("/{account_id}", summary="更新账号信息")
async def update_account(
    account_id: uuid.UUID,
    data: ExchangeAccountUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """更新交易所账号信息。"""
    service = AccountService(db)
    account = await service.update_account(account_id, data)
    if account is None:
        raise NotFoundException(
            message="账号不存在", detail={"account_id": str(account_id)}
        )
    await write_audit_log(
        db,
        user_id=current_user.id,
        action="update",
        resource_type="account",
        resource_id=account.id,
        detail=data.model_dump(exclude_unset=True),
    )
    return ApiResponse(data=ExchangeAccountResponse.model_validate(account))


@router.delete("/{account_id}", summary="删除账号")
async def delete_account(
    account_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """删除交易所账号。"""
    service = AccountService(db)
    deleted = await service.delete_account(account_id)
    if not deleted:
        raise NotFoundException(
            message="账号不存在", detail={"account_id": str(account_id)}
        )
    await write_audit_log(
        db,
        user_id=current_user.id,
        action="delete",
        resource_type="account",
        resource_id=account_id,
    )
    return ApiResponse(data={"deleted": True})


@router.post("/{account_id}/test", summary="测试交易所连接")
async def test_connection(
    account_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """测试交易所连接是否正常。"""
    service = AccountService(db)
    account = await service.get_account(account_id)
    if account is None:
        raise NotFoundException(
            message="账号不存在", detail={"account_id": str(account_id)}
        )
    result = await service.test_connection(account)
    return ApiResponse(data=result)


@router.get("/{account_id}/balance", summary="查询账号余额")
async def get_balance(
    account_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """查询交易所账号余额。"""
    service = AccountService(db)
    account = await service.get_account(account_id)
    if account is None:
        raise NotFoundException(
            message="账号不存在", detail={"account_id": str(account_id)}
        )
    balance = await service.get_balance(account)
    return ApiResponse(data=balance)


@router.post("/{account_id}/sync", summary="触发订单/交易同步")
async def sync_account(
    account_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """触发指定账号的交易记录同步（异步任务）。"""
    service = AccountService(db)
    account = await service.get_account(account_id)
    if account is None:
        raise NotFoundException(
            message="账号不存在", detail={"account_id": str(account_id)}
        )

    # 异步任务触发（Celery 不可用时降级为提示）
    try:
        from app.tasks.sync_tasks import sync_trades

        task = sync_trades.delay(str(account_id))
        task_id = task.id
    except Exception:
        # Celery/Redis 未启动时，返回提示信息
        task_id = None

    await write_audit_log(
        db,
        user_id=current_user.id,
        action="sync",
        resource_type="account",
        resource_id=account_id,
        detail={"task_id": task_id},
    )

    return ApiResponse(
        data={
            "account_id": str(account_id),
            "task_id": task_id,
            "message": "同步任务已触发" if task_id else "同步任务排队失败，请检查 Celery 服务",
        }
    )
