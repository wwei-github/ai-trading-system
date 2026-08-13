"""AI 助手服务。

处理 AI 会话管理、消息交互、交易信号生成、分析报告生成。
支持 5 种会话模式：trade_analysis / strategy / book_qa / general / report。
"""

import json
import uuid
from datetime import datetime
from typing import Any, AsyncGenerator, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai import AIConversation, AIMessage
from app.models.book import KnowledgeChunk
from app.schemas.ai import (
    AIConversationCreate,
    AIMessageCreate,
    AIReportRequest,
    AISignalRequest,
)
from app.services.llm_provider import get_llm_provider

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
    "general": "你是一位友好的 AI 助手，请帮助用户解答各类问题。",
    "report": (
        "你是一位专业的交易报告撰写专家。请根据用户提供的数据，"
        "生成结构清晰、内容详实的分析报告，包含关键指标、趋势分析、风险评估和建议。"
    ),
}


class AIService:
    """AI 助手服务。"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.llm = get_llm_provider()

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

        # book_qa 模式：检索知识库
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
        try:
            reply = await self.llm.chat(messages)
        except Exception as e:
            reply = f"AI 回复失败：{str(e)}"

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

        # 保存用户消息
        user_msg = AIMessage(
            conversation_id=conversation_id,
            role="user",
            content=data.content,
        )
        self.db.add(user_msg)
        await self.db.flush()

        # 流式调用 LLM
        messages = self._build_messages(conversation, history, data.content)
        full_reply = []
        try:
            async for chunk in self.llm.chat_stream(messages):
                full_reply.append(chunk)
                yield chunk
        except Exception as e:
            full_reply.append(f"\n[错误] {str(e)}")
            yield f"\n[错误] {str(e)}"

        # 保存完整 AI 回复
        assistant_msg = AIMessage(
            conversation_id=conversation_id,
            role="assistant",
            content="".join(full_reply),
        )
        self.db.add(assistant_msg)
        await self.db.flush()

    # ---------- RAG 知识检索 ----------

    async def _retrieve_knowledge(
        self, book_id: uuid.UUID, query: str, top_k: int = 3
    ) -> Optional[str]:
        """从书籍知识库检索相关片段（简化版：基于关键词匹配）。

        生产环境应使用向量相似度检索（pgvector）。
        """
        result = await self.db.execute(
            select(KnowledgeChunk)
            .where(KnowledgeChunk.book_id == book_id)
            .limit(50)
        )
        chunks = list(result.scalars().all())
        if not chunks:
            return None

        # 简化：按关键词匹配排序
        query_words = set(query.lower().split())

        def score(chunk: KnowledgeChunk) -> int:
            content = chunk.content.lower()
            return sum(1 for w in query_words if w in content)

        ranked = sorted(chunks, key=score, reverse=True)[:top_k]
        return "\n---\n".join(c.content for c in ranked if score(c) > 0) or None

    # ---------- 交易信号生成 ----------

    async def generate_signal(
        self, user_id: uuid.UUID, data: AISignalRequest
    ) -> dict:
        """生成交易信号。"""
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
        reply = await self.llm.chat(messages)

        # 解析 JSON 响应
        try:
            # 尝试提取 JSON
            start = reply.find("{")
            end = reply.rfind("}") + 1
            if start >= 0 and end > start:
                signal = json.loads(reply[start:end])
            else:
                signal = {"side": "hold", "strength": 0.5, "reason": reply}
        except json.JSONDecodeError:
            signal = {"side": "hold", "strength": 0.5, "reason": reply}

        return {
            "symbol": data.symbol,
            "side": signal.get("side", "hold"),
            "strength": float(signal.get("strength", 0.5)),
            "reason": signal.get("reason", ""),
            "strategy_id": data.strategy_id,
        }

    # ---------- 分析报告生成 ----------

    async def generate_report(
        self, user_id: uuid.UUID, data: AIReportRequest
    ) -> dict:
        """生成分析报告。"""
        report_prompts = {
            "trade": "交易表现分析报告",
            "strategy": "策略评估报告",
            "portfolio": "投资组合报告",
        }
        title = report_prompts.get(data.report_type, "分析报告")

        messages = [
            {
                "role": "system",
                "content": (
                    "你是一位专业的交易分析报告撰写专家。"
                    "请根据用户提供的信息，生成一份结构化的分析报告，"
                    "包含：1. 概述 2. 关键指标分析 3. 趋势分析 4. 风险评估 5. 改进建议。"
                    "使用 Markdown 格式输出。"
                ),
            },
            {
                "role": "user",
                "content": (
                    f"报告类型：{title}\n"
                    f"时间范围：{data.start_date or '全部'} 至 {data.end_date or '至今'}\n"
                    f"附加上下文：{json.dumps(data.context, ensure_ascii=False) if data.context else '无'}\n"
                    "请生成详细的分析报告。"
                ),
            },
        ]
        content = await self.llm.chat(messages)

        return {
            "report_type": data.report_type,
            "title": title,
            "content": content,
            "generated_at": datetime.utcnow().isoformat(),
        }
