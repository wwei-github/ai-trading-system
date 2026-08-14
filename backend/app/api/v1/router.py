"""v1 版本路由聚合。

将所有 v1 版本的路由模块聚合到一个路由器中。
"""

from fastapi import APIRouter

from app.api.v1 import (
    accounts,
    ai,
    ai_backtest_routes,
    ai_providers,
    auth,
    books,
    coins,
    error_log_routes,
    statistics,
    strategies,
    system,
    trade_tags,
    trades,
    users,
)

api_router = APIRouter()

# 鉴权 + 用户管理（公开/登录后）
api_router.include_router(auth.router)
api_router.include_router(users.router)

# 业务模块路由
api_router.include_router(accounts.router)
api_router.include_router(trades.router)
api_router.include_router(trade_tags.router)
api_router.include_router(statistics.router)
api_router.include_router(coins.router)
api_router.include_router(strategies.router)
api_router.include_router(books.router)
api_router.include_router(ai.router)
api_router.include_router(ai_providers.router)
api_router.include_router(ai_backtest_routes.router)
api_router.include_router(system.router)
api_router.include_router(error_log_routes.router)

__all__ = ["api_router"]
