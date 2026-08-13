"""v1 版本路由聚合。

将所有 v1 版本的路由模块聚合到一个路由器中。
"""

from fastapi import APIRouter

from app.api.v1 import (
    accounts,
    ai,
    books,
    coins,
    statistics,
    strategies,
    system,
    trades,
)

api_router = APIRouter()

# 注册各业务模块路由
api_router.include_router(accounts.router)
api_router.include_router(trades.router)
api_router.include_router(statistics.router)
api_router.include_router(coins.router)
api_router.include_router(strategies.router)
api_router.include_router(books.router)
api_router.include_router(ai.router)
api_router.include_router(system.router)

__all__ = ["api_router"]
