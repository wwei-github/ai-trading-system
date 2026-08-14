"""AI 助手接口。"""

import json
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.config import settings
from app.core.exceptions import NotFoundException
from app.core.rate_limit import rate_limit
from app.models.user import User
from app.schemas.ai import (
    AIChatResponse,
    AIConversationCreate,
    AIConversationResponse,
    AIConversationUpdate,
    AIMessageCreate,
    AIMessageFeedback,
    AIMessageResponse,
    AIReportRequest,
    AIReportResponse,
    AISignalRequest,
    AISignalResponse,
    SignalMarkRequest,
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


@router.patch("/conversations/{conversation_id}", summary="重命名会话")
async def update_conversation(
    conversation_id: uuid.UUID,
    data: AIConversationUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """更新 AI 会话（目前仅支持重命名）。"""
    service = AIService(db)
    conv = await service.update_conversation(conversation_id, data)
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
@rate_limit(settings.RATE_LIMIT_AI_PER_MIN)
async def send_message(
    conversation_id: uuid.UUID,
    data: AIMessageCreate,
    request: Request,
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
@rate_limit(settings.RATE_LIMIT_AI_PER_MIN)
async def stream_message(
    conversation_id: uuid.UUID,
    data: AIMessageCreate,
    request: Request,
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


# ---------- 消息反馈 ----------


@router.post(
    "/messages/{message_id}/feedback", summary="消息反馈（点赞/点踩）"
)
async def set_message_feedback(
    message_id: uuid.UUID,
    data: AIMessageFeedback,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """对 AI 消息进行反馈（like / dislike / none）。"""
    service = AIService(db)
    msg = await service.set_message_feedback(message_id, data)
    if msg is None:
        raise NotFoundException(
            message="消息不存在",
            detail={"message_id": str(message_id)},
        )
    return ApiResponse(data=AIMessageResponse.model_validate(msg))


# ---------- 交易信号 ----------


@router.post("/signals/generate", summary="生成交易信号", status_code=201)
@rate_limit(settings.RATE_LIMIT_AI_PER_MIN)
async def generate_signal(
    data: AISignalRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """生成 AI 交易信号并持久化。"""
    service = AIService(db)
    signal = await service.generate_signal(current_user.id, data)
    return ApiResponse(data=AISignalResponse.model_validate(signal))


@router.get("/signals", summary="获取信号列表")
async def list_signals(
    symbol: Optional[str] = Query(None, description="按交易对过滤"),
    status: Optional[str] = Query(
        None, description="按状态过滤：pending/adopted/ignored/executed"
    ),
    source: Optional[str] = Query(
        None, description="按来源过滤：ai/rule"
    ),
    limit: int = Query(50, ge=1, le=200, description="返回条数"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取当前用户的交易信号列表。"""
    service = AIService(db)
    signals = await service.list_signals(
        current_user.id,
        symbol=symbol,
        status=status,
        source=source,
        limit=limit,
    )
    return ApiResponse(
        data=[AISignalResponse.model_validate(s) for s in signals]
    )


@router.post("/signals/{signal_id}/mark", summary="标记信号状态")
async def mark_signal(
    signal_id: uuid.UUID,
    data: SignalMarkRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """标记信号状态：adopted（采纳）/ ignored（忽略）/ executed（已执行）。"""
    service = AIService(db)
    signal = await service.mark_signal(
        current_user.id, signal_id, data.status
    )
    if signal is None:
        raise NotFoundException(
            message="信号不存在",
            detail={"signal_id": str(signal_id)},
        )
    return ApiResponse(data=AISignalResponse.model_validate(signal))


# ---------- 分析报告 ----------


@router.post("/reports/generate", summary="生成分析报告", status_code=201)
@rate_limit(settings.RATE_LIMIT_AI_PER_MIN)
async def generate_report(
    data: AIReportRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """生成 AI 分析报告并持久化。"""
    service = AIService(db)
    report = await service.generate_report(current_user.id, data)
    return ApiResponse(data=AIReportResponse.model_validate(report))


@router.get("/reports", summary="获取报告列表")
async def list_reports(
    report_type: Optional[str] = Query(
        None, description="按类型过滤：trade/strategy/portfolio"
    ),
    period: Optional[str] = Query(
        None, description="按周期过滤：daily/weekly/monthly/custom"
    ),
    limit: int = Query(20, ge=1, le=100, description="返回条数"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取当前用户的分析报告列表。"""
    service = AIService(db)
    reports = await service.list_reports(
        current_user.id,
        report_type=report_type,
        period=period,
        limit=limit,
    )
    return ApiResponse(
        data=[AIReportResponse.model_validate(r) for r in reports]
    )


@router.get("/reports/{report_id}", summary="获取报告详情")
async def get_report(
    report_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取指定分析报告的完整内容。"""
    service = AIService(db)
    report = await service.get_report(current_user.id, report_id)
    if report is None:
        raise NotFoundException(
            message="报告不存在",
            detail={"report_id": str(report_id)},
        )
    return ApiResponse(data=AIReportResponse.model_validate(report))
