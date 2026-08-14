"""AI Provider 管理 API。

提供多 Provider 的 CRUD 管理接口：
- GET    /api/v1/ai/providers              - 列出所有 Provider（脱敏）
- POST   /api/v1/ai/providers              - 添加 Provider（Admin）
- DELETE /api/v1/ai/providers/{id}         - 删除 Provider（Admin）
- POST   /api/v1/ai/providers/{id}/activate - 切换激活
- POST   /api/v1/ai/providers/ollama/models - 获取 Ollama 模型列表
"""

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.api.deps import get_current_user
from app.core.permissions import require_roles
from app.models.user import User
from app.schemas.common import ApiResponse
from app.services.provider_factory import ProviderFactory

router = APIRouter(prefix="/ai/providers", tags=["AI Provider 管理"])


@router.get("", summary="列出所有 Provider（脱敏）")
async def list_providers(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """列出所有 Provider 配置，API Key 已脱敏。"""
    data = await ProviderFactory.list_providers(db)
    return ApiResponse(data=data)


@router.post(
    "",
    summary="添加 Provider",
    dependencies=[Depends(require_roles("admin"))],
)
async def add_provider(
    body: Dict[str, Any],
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """添加 Provider（API Key 加密存储）。"""
    data = await ProviderFactory.add_provider(db, body, user_id=current_user.id)
    return ApiResponse(data=data)


@router.delete(
    "/{provider_id}",
    summary="删除 Provider",
    dependencies=[Depends(require_roles("admin"))],
)
async def delete_provider(
    provider_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """删除 Provider（禁止删除当前激活的）。"""
    data = await ProviderFactory.delete_provider(db, provider_id, user_id=current_user.id)
    return ApiResponse(data=data)


@router.post("/{provider_id}/activate", summary="切换激活的 Provider")
async def activate_provider(
    provider_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """切换当前激活的 Provider。"""
    data = await ProviderFactory.activate_provider(db, provider_id, user_id=current_user.id)
    return ApiResponse(data=data)


@router.post("/ollama/models", summary="获取 Ollama 可用模型列表")
async def fetch_ollama_models(
    body: Dict[str, Any] = {},
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取指定 Ollama 服务的可用模型列表。"""
    import httpx

    base_url = body.get("base_url", "http://ollama:11434").rstrip("/")
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{base_url}/api/tags")
            resp.raise_for_status()
            models = resp.json().get("models", [])
            return ApiResponse(
                data={
                    "models": [
                        {
                            "name": m["name"],
                            "size": m["size"],
                            "modified_at": m.get("modified_at", ""),
                        }
                        for m in models
                    ]
                }
            )
    except Exception as e:
        raise HTTPException(
            status_code=502, detail=f"连接 Ollama 失败: {str(e)}"
        )