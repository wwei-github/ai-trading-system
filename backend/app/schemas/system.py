"""系统管理 Schema。"""

import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class UserBase(BaseModel):
    """用户基础字段。"""

    email: str = Field(..., description="邮箱")
    nickname: str = Field(..., description="昵称")
    role: str = Field("trader", description="角色：admin / trader / viewer")
    is_active: bool = Field(True, description="是否激活")


class UserCreate(UserBase):
    """创建用户请求。"""

    pass


class UserUpdate(BaseModel):
    """更新用户请求。"""

    email: Optional[str] = None
    nickname: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None


class UserResponse(UserBase):
    """用户响应。"""

    id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SystemConfigResponse(BaseModel):
    """系统配置响应。"""

    app_name: str
    app_env: str
    api_prefix: str
    debug: bool
    llm_provider: str
    llm_model: str

    model_config = {"from_attributes": False}


class SystemConfigUpdate(BaseModel):
    """系统配置更新（当前仅支持部分运行时配置）。"""

    pass


class NotificationSettings(BaseModel):
    """通知设置。"""

    email_notification: bool = True
    desktop_notification: bool = True
    trade_signal_alert: bool = True
    sync_failure_alert: bool = True
    report_frequency: str = "daily"  # daily / weekly / monthly


class AuditLogResponse(BaseModel):
    """审计日志响应。"""

    id: uuid.UUID
    user_id: Optional[uuid.UUID] = None
    action: str
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    detail: Optional[Dict[str, Any]] = None
    ip: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}
