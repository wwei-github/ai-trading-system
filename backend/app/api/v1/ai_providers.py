"""本地模型配置 API。

云端 AI（OpenAI 兼容接口）完全由环境变量（LLM_*）配置，不再提供 UI 管理。
这里只管理本地模型（Ollama）：
- GET    /api/v1/ai/providers/local-model    - 获取本地模型配置
- PATCH  /api/v1/ai/providers/local-model    - 更新本地模型配置
- POST   /api/v1/ai/providers/ollama/models  - 获取 Ollama 模型列表
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

router = APIRouter(prefix="/ai/providers", tags=["本地模型管理"])


@router.get("/local-model", summary="获取本地模型配置")
async def get_local_model(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取本地模型配置（含运行时 base_url，用于展示）。"""
    from app.core.config import settings

    config = await ProviderFactory.get_local_model_config(db)
    return ApiResponse(
        data={**config, "base_url": settings.OLLAMA_BASE_URL.rstrip("/")}
    )


@router.patch(
    "/local-model",
    summary="更新本地模型配置",
    dependencies=[Depends(require_roles("admin"))],
)
async def update_local_model(
    body: Dict[str, Any],
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """更新本地模型配置（模型名 / Temperature / Max Tokens / Embedding 模型）。"""
    config = await ProviderFactory.save_local_model_config(db, body)
    return ApiResponse(data=config)


@router.post("/ollama/models", summary="获取 Ollama 可用模型列表")
async def fetch_ollama_models(
    body: Dict[str, Any] = {},
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取指定 Ollama 服务的可用模型列表。"""
    import httpx

    from app.core.config import settings

    base_url = body.get("base_url", settings.OLLAMA_BASE_URL).rstrip("/")
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
