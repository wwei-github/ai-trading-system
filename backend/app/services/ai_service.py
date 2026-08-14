"""AI 助手服务（Stage 8，对齐 PRD §5.8）。

处理 AI 会话管理、消息交互、交易信号生成、分析报告生成。
支持 5 种会话模式：trade_analysis / strategy / book_qa / risk_diagnosis / general。
所有 AI 回复自动追加免责声明。
信号和报告持久化到数据库。
"""

import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, AsyncGenerator, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestException, NotFoundException
from app.models.ai import AIConversation, AIMessage
from app.models.report import Report
from app.models.signal import Signal
from app.schemas.ai import (
    AIConversationCreate,
    AIConversationUpdate,
    AIMessageCreate,
    AIMessageFeedback,
    AIReportRequest,
    AISignalRequest,
)
from app.services.llm_provider import LLMProvider
from app.services.provider_factory import ProviderFactory

# 免责声明（自动追加到所有 AI 回复末尾）
DISCLAIMER = (
    "\n\n---\n⚠️ **免责声明**：以上内容由 AI 生成，仅供参考，不构成投资建议。"
    "交易有风险，投资需谨慎。"
)

# 会话模式系统提示词
SYSTEM_PROMPTS = {
    "trade_analysis": (
        "你是一位专业的加密货币交易分析师。请根据用户的交易数据，"
        "分析交易表现、识别问题并给出改进建议。"
        "回答应基于数据，逻辑清晰，包含具体的可执行建议。"
    ),
    "strategy": (
        "你是一位量化交易策略专家。请帮助用户设计、优化和评估交易策略，"
        "包括策略逻辑、参数选择、风险管理等方面。"
    ),
    "book_qa": (
        "你是一位交易知识助手。请基于提供的书籍知识片段回答用户问题，"
        "回答应忠实于原文，并在合适位置标注引用来源。"
        "若知识片段不足以回答问题，请如实告知。"
    ),
    "risk_diagnosis": (
        "你是一位风险管理专家。请根据用户的当前持仓、波动率和历史表现，"
        "诊断潜在风险，评估风险敞口，给出风险控制建议。"
    ),
    "general": "你是一位友好的 AI 助手，请帮助用户解答各类问题。",
}


class AIService:
    """AI 助手服务。"""

    def __init__(self, db: AsyncSession):
        self.db = db
        # 不再在构造函数中创建 Provider，改为每次调用时从 DB 动态加载

    async def _get_llm(self) -> LLMProvider:
        """从 DB 动态加载当前激活的 Provider。"""
        return await ProviderFactory.get_active_provider(self.db)

    # ---------- 会话管理 ----------

    async def create_conversation(
        self, user_id: uuid.UUID, data: AIConversationCreate
    ) -> AIConversation:
        """创建 AI 会话。"""
        conversation = AIConversation(
            user_id=user_id,
            mode=data.mode,
            title=data.title or f"会话-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
            context=data.context,
        )
        self.db.add(conversation)
        await self.db.flush()
        return conversation

    async def get_conversation(
        self, conversation_id: uuid.UUID
    ) -> Optional[AIConversation]:
        """获取会话详情。"""
        result = await self.db.execute(
            select(AIConversation).where(AIConversation.id == conversation_id)
        )
        return result.scalar_one_or_none()

    async def list_conversations(
        self, user_id: uuid.UUID
    ) -> List[AIConversation]:
        """获取用户的会话列表。"""
        result = await self.db.execute(
            select(AIConversation)
            .where(AIConversation.user_id == user_id)
            .order_by(AIConversation.created_at.desc())
        )
        return list(result.scalars().all())

    async def update_conversation(
        self, conversation_id: uuid.UUID, data: AIConversationUpdate
    ) -> Optional[AIConversation]:
        """更新会话（重命名）。"""
        conv = await self.get_conversation(conversation_id)
        if conv is None:
            return None
        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(conv, key, value)
        await self.db.flush()
        return conv

    async def delete_conversation(
        self, conversation_id: uuid.UUID
    ) -> bool:
        """删除会话（关联消息会级联删除，但当前未设置外键级联，需手动删除）。"""
        conversation = await self.get_conversation(conversation_id)
        if conversation is None:
            return False
        # 先删除关联消息
        msgs = await self.list_messages(conversation_id)
        for m in msgs:
            await self.db.delete(m)
        await self.db.delete(conversation)
        await self.db.flush()
        return True

    async def list_messages(
        self, conversation_id: uuid.UUID
    ) -> List[AIMessage]:
        """获取会话消息列表。"""
        result = await self.db.execute(
            select(AIMessage)
            .where(AIMessage.conversation_id == conversation_id)
            .order_by(AIMessage.created_at.asc())
        )
        return list(result.scalars().all())

    # ---------- 消息发送 ----------

    def _build_messages(
        self,
        conversation: AIConversation,
        history: List[AIMessage],
        user_content: str,
        extra_context: Optional[str] = None,
    ) -> List[Dict[str, str]]:
        """构建 LLM 消息上下文。"""
        messages = [
            {
                "role": "system",
                "content": SYSTEM_PROMPTS.get(
                    conversation.mode, SYSTEM_PROMPTS["general"]
                ),
            }
        ]

        # 携带会话上下文
        if conversation.context:
            messages.append(
                {
                    "role": "system",
                    "content": f"会话上下文：{json.dumps(conversation.context, ensure_ascii=False)}",
                }
            )

        # 额外上下文（如 RAG 检索结果）
        if extra_context:
            messages.append(
                {
                    "role": "system",
                    "content": f"参考信息：\n{extra_context}",
                }
            )

        # 历史消息（最多保留最近 20 条）
        for m in history[-20:]:
            messages.append({"role": m.role, "content": m.content})

        # 当前用户消息
        messages.append({"role": "user", "content": user_content})

        return messages

    async def send_message(
        self,
        user_id: uuid.UUID,
        conversation_id: uuid.UUID,
        data: AIMessageCreate,
    ) -> dict:
        """发送消息并获取 AI 回复。"""
        conversation = await self.get_conversation(conversation_id)
        if conversation is None:
            return {"user_message": None, "assistant_message": None}

        history = await self.list_messages(conversation_id)

        # book_qa 模式：向量检索知识库
        extra_context = None
        if conversation.mode == "book_qa" and conversation.context:
            book_id = conversation.context.get("book_id")
            if book_id:
                extra_context = await self._retrieve_knowledge(
                    uuid.UUID(book_id), data.content
                )

        # 保存用户消息
        user_msg = AIMessage(
            conversation_id=conversation_id,
            role="user",
            content=data.content,
        )
        self.db.add(user_msg)
        await self.db.flush()

        # 调用 LLM
        messages = self._build_messages(
            conversation, history, data.content, extra_context
        )
        llm = await self._get_llm()
        try:
            reply = await llm.chat(messages)
        except Exception as e:
            reply = f"AI 回复失败：{str(e)}"

        # 追加免责声明
        reply = self._append_disclaimer(reply)

        # 保存 AI 回复
        assistant_msg = AIMessage(
            conversation_id=conversation_id,
            role="assistant",
            content=reply,
        )
        self.db.add(assistant_msg)
        await self.db.flush()

        return {
            "user_message": user_msg,
            "assistant_message": assistant_msg,
        }

    async def stream_message(
        self,
        user_id: uuid.UUID,
        conversation_id: uuid.UUID,
        data: AIMessageCreate,
    ) -> AsyncGenerator[str, None]:
        """流式发送消息（SSE）。

        生成器产出 AI 回复的增量内容。
        """
        conversation = await self.get_conversation(conversation_id)
        if conversation is None:
            yield "会话不存在"
            return

        history = await self.list_messages(conversation_id)

        # book_qa 模式：向量检索知识库
        extra_context = None
        if conversation.mode == "book_qa" and conversation.context:
            book_id = conversation.context.get("book_id")
            if book_id:
                extra_context = await self._retrieve_knowledge(
                    uuid.UUID(book_id), data.content
                )

        # 保存用户消息
        user_msg = AIMessage(
            conversation_id=conversation_id,
            role="user",
            content=data.content,
        )
        self.db.add(user_msg)
        await self.db.flush()

        # 流式调用 LLM
        messages = self._build_messages(
            conversation, history, data.content, extra_context
        )
        full_reply = []
        llm = await self._get_llm()
        try:
            async for chunk in llm.chat_stream(messages):
                full_reply.append(chunk)
                yield chunk
        except Exception as e:
            full_reply.append(f"\n[错误] {str(e)}")
            yield f"\n[错误] {str(e)}"

        # 追加免责声明
        disclaimer = DISCLAIMER
        full_reply.append(disclaimer)
        yield disclaimer

        # 保存完整 AI 回复
        assistant_msg = AIMessage(
            conversation_id=conversation_id,
            role="assistant",
            content="".join(full_reply),
        )
        self.db.add(assistant_msg)
        await self.db.flush()

    # ---------- 消息反馈 ----------

    async def set_message_feedback(
        self, message_id: uuid.UUID, data: AIMessageFeedback
    ) -> Optional[AIMessage]:
        """设置消息反馈（点赞/点踩）。"""
        result = await self.db.execute(
            select(AIMessage).where(AIMessage.id == message_id)
        )
        msg = result.scalar_one_or_none()
        if msg is None:
            return None
        if data.feedback not in ("none", "like", "dislike"):
            raise BadRequestException(
                message="无效的反馈类型",
                detail={"feedback": data.feedback},
            )
        msg.feedback = data.feedback
        await self.db.flush()
        return msg

    # ---------- RAG 知识检索（向量检索） ----------

    async def _retrieve_knowledge(
        self, book_id: uuid.UUID, query: str, top_k: int = 5
    ) -> Optional[str]:
        """从书籍知识库向量检索相关片段。

        使用 BookService 的余弦相似度向量检索（Stage 7.3），
        未配置 LLM_API_KEY 时降级为关键词匹配。
        """
        from app.services.book_service import BookService

        book_service = BookService(self.db)
        scored_chunks = await book_service.retrieve_relevant_chunks(
            book_id, query, top_k=top_k
        )
        if not scored_chunks:
            return None

        parts = []
        for i, (chunk, score) in enumerate(scored_chunks):
            parts.append(
                f"[片段 {i + 1}]（第 {chunk.chapter_order or '?'} 章，相似度 {score:.2f}）"
                f"{chunk.content}"
            )
        return "\n---\n".join(parts)

    # ---------- 交易信号生成 + 持久化 ----------

    async def generate_signal(
        self, user_id: uuid.UUID, data: AISignalRequest
    ) -> Signal:
        """生成交易信号并保存到数据库。"""
        messages = [
            {
                "role": "system",
                "content": (
                    "你是一位交易信号生成专家。请根据用户提供的信息，"
                    "生成一个交易信号。必须以 JSON 格式返回，包含字段：\n"
                    '{"side": "buy/sell/hold", "strength": 0.0-1.0, "reason": "原因说明"}'
                ),
            },
            {
                "role": "user",
                "content": (
                    f"交易对：{data.symbol}\n"
                    f"策略ID：{data.strategy_id or '无'}\n"
                    f"附加上下文：{json.dumps(data.context, ensure_ascii=False) if data.context else '无'}\n"
                    "请生成交易信号。"
                ),
            },
        ]
        llm = await self._get_llm()
        reply = await llm.chat(messages)

        # 解析 JSON 响应
        try:
            start = reply.find("{")
            end = reply.rfind("}") + 1
            if start >= 0 and end > start:
                signal_data = json.loads(reply[start:end])
            else:
                signal_data = {"side": "hold", "strength": 0.5, "reason": reply}
        except json.JSONDecodeError:
            signal_data = {"side": "hold", "strength": 0.5, "reason": reply}

        # 保存到数据库
        signal = Signal(
            user_id=user_id,
            strategy_id=data.strategy_id,
            symbol=data.symbol,
            side=signal_data.get("side", "hold"),
            strength=float(signal_data.get("strength", 0.5)),
            reason=signal_data.get("reason", ""),
            source="ai",
            status="pending",
            context=data.context,
        )
        self.db.add(signal)
        await self.db.flush()
        return signal

    async def list_signals(
        self,
        user_id: uuid.UUID,
        symbol: Optional[str] = None,
        status: Optional[str] = None,
        source: Optional[str] = None,
        limit: int = 50,
    ) -> List[Signal]:
        """获取用户的信号列表。"""
        stmt = (
            select(Signal)
            .where(Signal.user_id == user_id)
            .order_by(Signal.created_at.desc())
        )
        if symbol:
            stmt = stmt.where(Signal.symbol == symbol)
        if status:
            stmt = stmt.where(Signal.status == status)
        if source:
            stmt = stmt.where(Signal.source == source)
        stmt = stmt.limit(limit)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def mark_signal(
        self,
        user_id: uuid.UUID,
        signal_id: uuid.UUID,
        status: str,
    ) -> Optional[Signal]:
        """标记信号状态（采纳/忽略/已执行）。"""
        if status not in ("adopted", "ignored", "executed", "pending"):
            raise BadRequestException(
                message="无效的信号状态",
                detail={"status": status},
            )
        result = await self.db.execute(
            select(Signal).where(
                Signal.id == signal_id, Signal.user_id == user_id
            )
        )
        signal = result.scalar_one_or_none()
        if signal is None:
            return None
        signal.status = status
        await self.db.flush()
        return signal

    # ---------- 分析报告生成 + 持久化 ----------

    async def generate_report(
        self, user_id: uuid.UUID, data: AIReportRequest
    ) -> Report:
        """生成分析报告并保存到数据库。"""
        report_titles = {
            "trade": "交易表现分析报告",
            "strategy": "策略评估报告",
            "portfolio": "投资组合报告",
        }
        title = report_titles.get(data.report_type, "分析报告")

        # 解析时间范围
        period_start = None
        period_end = None
        if data.start_date:
            try:
                period_start = datetime.fromisoformat(data.start_date).replace(
                    tzinfo=timezone.utc
                )
            except ValueError:
                pass
        if data.end_date:
            try:
                period_end = datetime.fromisoformat(data.end_date).replace(
                    tzinfo=timezone.utc
                )
            except ValueError:
                pass

        messages = [
            {
                "role": "system",
                "content": (
                    "你是一位专业的交易分析报告撰写专家。"
                    "请根据用户提供的信息，生成一份结构化的分析报告，"
                    "包含以下 5 章：\n"
                    "1. 概述\n2. 关键指标分析\n3. 趋势分析\n4. 风险评估\n5. 改进建议\n"
                    "使用 Markdown 格式输出。"
                ),
            },
            {
                "role": "user",
                "content": (
                    f"报告类型：{title}\n"
                    f"报告周期：{data.period}\n"
                    f"时间范围：{data.start_date or '全部'} 至 {data.end_date or '至今'}\n"
                    f"附加上下文：{json.dumps(data.context, ensure_ascii=False) if data.context else '无'}\n"
                    "请生成详细的分析报告。"
                ),
            },
        ]
        llm = await self._get_llm()
        content = await llm.chat(messages)
        content = self._append_disclaimer(content)

        # 生成 AI 摘要（前 200 字）
        summary = content[:200].replace("#", "").strip()
        if len(content) > 200:
            summary += "..."

        # 保存到数据库
        report = Report(
            user_id=user_id,
            report_type=data.report_type,
            period=data.period,
            title=title,
            content=content,
            summary=summary,
            period_start=period_start,
            period_end=period_end,
            context=data.context,
        )
        self.db.add(report)
        await self.db.flush()
        return report

    async def list_reports(
        self,
        user_id: uuid.UUID,
        report_type: Optional[str] = None,
        period: Optional[str] = None,
        limit: int = 20,
    ) -> List[Report]:
        """获取用户的报告列表。"""
        stmt = (
            select(Report)
            .where(Report.user_id == user_id)
            .order_by(Report.created_at.desc())
        )
        if report_type:
            stmt = stmt.where(Report.report_type == report_type)
        if period:
            stmt = stmt.where(Report.period == period)
        stmt = stmt.limit(limit)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_report(
        self, user_id: uuid.UUID, report_id: uuid.UUID
    ) -> Optional[Report]:
        """获取报告详情。"""
        result = await self.db.execute(
            select(Report).where(
                Report.id == report_id, Report.user_id == user_id
            )
        )
        return result.scalar_one_or_none()

    # ---------- 工具方法 ----------

    @staticmethod
    def _append_disclaimer(text: str) -> str:
        """在 AI 回复末尾追加免责声明（若尚未追加）。"""
        if DISCLAIMER.strip() in text:
            return text
        return text + DISCLAIMER
