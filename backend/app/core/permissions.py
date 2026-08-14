"""RBAC 权限中间件。

提供 require_roles(...) 依赖工厂，用于路由级别权限校验。

3 角色：
- admin：所有权限
- trader：写操作 + 查询
- viewer：只读（不允许 POST/PUT/PATCH/DELETE）
"""

from typing import Iterable, Optional

from fastapi import Depends, Request

from app.api.deps import get_current_user
from app.core.exceptions import ForbiddenException, ViewerWriteForbiddenException
from app.models.user import User


# 写操作 HTTP 方法集合
WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def require_roles(*roles: str):
    """要求当前用户角色在 roles 列表中，否则抛 ForbiddenException。

    用法：
        @router.post("/...", dependencies=[Depends(require_roles("admin", "trader"))])
    """

    allowed = set(roles)

    async def _checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in allowed:
            raise ForbiddenException(
                message=f"当前角色 {user.role} 无权访问此资源",
                detail={"required_roles": list(allowed), "current_role": user.role},
            )
        return user

    return _checker


async def reject_viewer_write(
    request: Request,
    user: User = Depends(get_current_user),
) -> User:
    """通用依赖：Viewer 不能执行写操作。

    可挂在路由器级别：
        router = APIRouter(dependencies=[Depends(reject_viewer_write)])
    """
    if user.role == "viewer" and request.method.upper() in WRITE_METHODS:
        raise ViewerWriteForbiddenException(
            detail={"method": request.method, "path": request.url.path},
        )
    return user
