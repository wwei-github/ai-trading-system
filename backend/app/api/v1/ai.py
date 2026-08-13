"""AI 助手接口。"""

import json
import uuid

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.exceptions import NotFoundException
from app.models.user import User
from app.schemas.ai import (
    AIChatResponse,
    AIConversationCreate,
    AIConversationResponse,
    AIMessageCreate,
    AIMessageResponse,
    AIReportRequest,
    AISignalRequest,
)
from app.schemas.common import ApiResponse
from app.services.ai_service import AIService

router = APIRouter(prefix="/ai", tags=["AI 助手"])


@router.get("/health", summary="健康检查")
async def health_check():
    """AI 助手模块健康检查。"""
    return ApiResponse(data={"status": "ok", "module": "ai"})


# ---------- 会话管理 ----------


@router.get("/conversations", summary="获取会话列表")
async def list_conversations(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取当前用户的 AI 会话列表。"""
    service = AIService(db)
    convs = await service.list_conversations(current_user.id)
    return ApiResponse(
        data=[AIConversationResponse.model_validate(c) for c in convs]
    )


@router.post("/conversations", summary="创建会话", status_code=201)
async def create_conversation(
    data: AIConversationCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """创建 AI 会话。"""
    service = AIService(db)
    conv = await service.create_conversation(current_user.id, data)
    return ApiResponse(data=AIConversationResponse.model_validate(conv))


@router.get("/conversations/{conversation_id}", summary="获取会话详情")
async def get_conversation(
    conversation_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取 AI 会话详情。"""
    service = AIService(db)
    conv = await service.get_conversation(conversation_id)
    if conv is None:
        raise NotFoundException(
            message="会话不存在",
            detail={"conversation_id": str(conversation_id)},
        )
    return ApiResponse(data=AIConversationResponse.model_validate(conv))


@router.delete("/conversations/{conversation_id}", summary="删除会话")
async def delete_conversation(
    conversation_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """删除 AI 会话。"""
    service = AIService(db)
    deleted = await service.delete_conversation(conversation_id)
    if not deleted:
        raise NotFoundException(
            message="会话不存在",
            detail={"conversation_id": str(conversation_id)},
        )
    return ApiResponse(data={"deleted": True})


@router.get(
    "/conversations/{conversation_id}/messages", summary="获取消息列表"
)
async def list_messages(
    conversation_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取会话的消息列表。"""
    service = AIService(db)
    msgs = await service.list_messages(conversation_id)
    return ApiResponse(
        data=[AIMessageResponse.model_validate(m) for m in msgs]
    )


@router.post(
    "/conversations/{conversation_id}/messages", summary="发送消息"
)
async def send_message(
    conversation_id: uuid.UUID,
    data: AIMessageCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """发送消息并获取 AI 回复。"""
    service = AIService(db)
    result = await service.send_message(
        current_user.id, conversation_id, data
    )
    if result["user_message"] is None:
        raise NotFoundException(
            message="会话不存在",
            detail={"conversation_id": str(conversation_id)},
        )
    return ApiResponse(
        data=AIChatResponse(
            user_message=AIMessageResponse.model_validate(
                result["user_message"]
            ),
            assistant_message=AIMessageResponse.model_validate(
                result["assistant_message"]
            ),
        )
    )


@router.post(
    "/conversations/{conversation_id}/stream", summary="流式对话"
)
async def stream_message(
    conversation_id: uuid.UUID,
    data: AIMessageCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """流式对话（SSE）。"""

    async def event_generator():
        service = AIService(db)
        try:
            async for chunk in service.stream_message(
                current_user.id, conversation_id, data
            ):
                yield f"data: {json.dumps({'content': chunk}, ensure_ascii=False)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ---------- 信号与报告 ----------


@router.post("/signal", summary="生成交易信号")
async def generate_signal(
    data: AISignalRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """生成交易信号。"""
    service = AIService(db)
    signal = await service.generate_signal(current_user.id, data)
    return ApiResponse(data=signal)


@router.post("/report", summary="生成分析报告")
async def generate_report(
    data: AIReportRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """生成分析报告。"""
    service = AIService(db)
    report = await service.generate_report(current_user.id, data)
    return ApiResponse(data=report)
