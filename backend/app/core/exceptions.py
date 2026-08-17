"""自定义异常与全局异常处理器。"""

from typing import Any, Dict, Optional

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from loguru import logger


class AppException(Exception):
    """应用基础异常类。

    所有自定义业务异常应继承此类。
    """

    def __init__(
        self,
        message: str = "服务内部错误",
        code: int = 500,
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail: Optional[Any] = None,
    ):
        self.message = message
        self.code = code
        self.status_code = status_code
        self.detail = detail
        super().__init__(message)


class NotFoundException(AppException):
    """资源未找到异常。"""

    def __init__(self, message: str = "资源不存在", detail: Optional[Any] = None):
        super().__init__(
            message=message,
            code=404,
            status_code=status.HTTP_404_NOT_FOUND,
            detail=detail,
        )


class BadRequestException(AppException):
    """请求参数错误异常。"""

    def __init__(self, message: str = "请求参数错误", detail: Optional[Any] = None):
        super().__init__(
            message=message,
            code=400,
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=detail,
        )


class ConflictException(AppException):
    """资源冲突异常。"""

    def __init__(self, message: str = "资源冲突", detail: Optional[Any] = None):
        super().__init__(
            message=message,
            code=409,
            status_code=status.HTTP_409_CONFLICT,
            detail=detail,
        )


class ServiceUnavailableException(AppException):
    """服务不可用异常（如数据库、交易所连接失败）。"""

    def __init__(
        self, message: str = "服务暂时不可用", detail: Optional[Any] = None
    ):
        super().__init__(
            message=message,
            code=503,
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=detail,
        )


# ---------- Stage 1 业务错误码（对齐方案 §6.3） ----------


class UnauthorizedException(AppException):
    """未认证 / Token 无效（code=40001）。"""

    def __init__(self, message: str = "未认证或 Token 无效", detail: Optional[Any] = None):
        super().__init__(
            message=message,
            code=40001,
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
        )


class TokenExpiredException(AppException):
    """Token 过期，需 refresh（code=40002）。"""

    def __init__(self, message: str = "Token 已过期，请刷新", detail: Optional[Any] = None):
        super().__init__(
            message=message,
            code=40002,
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
        )


class AccountLockedException(AppException):
    """账号锁定（code=40003，HTTP 423）。"""

    def __init__(self, message: str = "账号已锁定", detail: Optional[Any] = None):
        super().__init__(
            message=message,
            code=40003,
            status_code=423,
            detail=detail,
        )


class ForbiddenException(AppException):
    """无此角色权限（code=40101）。"""

    def __init__(self, message: str = "无此操作权限", detail: Optional[Any] = None):
        super().__init__(
            message=message,
            code=40101,
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail,
        )


class ViewerWriteForbiddenException(AppException):
    """Viewer 不允许写操作（code=40102）。"""

    def __init__(self, message: str = "Viewer 角色不允许写操作", detail: Optional[Any] = None):
        super().__init__(
            message=message,
            code=40102,
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail,
        )


class EmailAlreadyRegisteredException(AppException):
    """邮箱已注册（code=40201）。"""

    def __init__(self, message: str = "邮箱已注册", detail: Optional[Any] = None):
        super().__init__(
            message=message,
            code=40201,
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=detail,
        )


class EmailNotVerifiedException(AppException):
    """邮箱未验证（code=40202）。"""

    def __init__(self, message: str = "邮箱未验证", detail: Optional[Any] = None):
        super().__init__(
            message=message,
            code=40202,
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=detail,
        )


class PasswordTooWeakException(AppException):
    """密码复杂度不足（code=40203）。"""

    def __init__(self, message: str = "密码复杂度不足", detail: Optional[Any] = None):
        super().__init__(
            message=message,
            code=40203,
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=detail,
        )


class TOTPCodeInvalidException(AppException):
    """2FA 验证码错误（code=40301）。"""

    def __init__(self, message: str = "2FA 验证码错误", detail: Optional[Any] = None):
        super().__init__(
            message=message,
            code=40301,
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=detail,
        )


class RateLimitException(AppException):
    """限流（code=42901，HTTP 429）。"""

    def __init__(self, message: str = "请求过于频繁", detail: Optional[Any] = None):
        super().__init__(
            message=message,
            code=42901,
            status_code=429,
            detail=detail,
        )


class RiskControlException(AppException):
    """风控拦截（code=45001）。"""

    def __init__(self, message: str = "风控拦截", detail: Optional[Any] = None):
        super().__init__(
            message=message,
            code=45001,
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=detail,
        )


def _build_error_response(
    message: str, code: int, detail: Optional[Any] = None
) -> Dict[str, Any]:
    """构建统一错误响应体。"""
    resp: Dict[str, Any] = {"code": code, "message": message, "data": None}
    if detail is not None:
        resp["data"] = detail
    return resp


async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    """处理自定义应用异常。"""
    logger.warning(
        "应用异常: {} | 路径: {} | 详情: {}",
        exc.message,
        request.url.path,
        exc.detail,
    )
    return JSONResponse(
        status_code=exc.status_code,
        content=_build_error_response(exc.message, exc.code, exc.detail),
    )


async def unhandled_exception_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    """处理未捕获的异常。"""
    logger.exception("未处理异常 | 路径: {} | 错误: {}", request.url.path, exc)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=_build_error_response(f"服务内部错误: {str(exc)}", 500),
    )


def register_exception_handlers(app: FastAPI) -> None:
    """注册全局异常处理器到 FastAPI 应用。"""
    app.add_exception_handler(AppException, app_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
