"""AI 助手服务。"""

from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai import AIConversation, AIMessage
from app.schemas.ai import AIConversationCreate, AIMessageCreate


class AIService:
    """AI 助手服务。

    处理 AI 会话管理和消息交互。
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_conversation(
        self, user_id: str, data: AIConversationCreate
    ) -> AIConversation:
        """创建 AI 会话。"""
        conversation = AIConversation(
            user_id=user_id,
            mode=data.mode,
            title=data.title,
            context=data.context,
        )
        self.db.add(conversation)
        await self.db.flush()
        return conversation

    async def get_conversation(
        self, conversation_id: str
    ) -> Optional[AIConversation]:
        """获取会话详情。"""
        result = await self.db.execute(
            select(AIConversation).where(AIConversation.id == conversation_id)
        )
        return result.scalar_one_or_none()

    async def list_conversations(self, user_id: str) -> List[AIConversation]:
        """获取用户的会话列表。"""
        result = await self.db.execute(
            select(AIConversation)
            .where(AIConversation.user_id == user_id)
            .order_by(AIConversation.created_at.desc())
        )
        return list(result.scalars().all())

    async def list_messages(self, conversation_id: str) -> List[AIMessage]:
        """获取会话消息列表。"""
        result = await self.db.execute(
            select(AIMessage)
            .where(AIMessage.conversation_id == conversation_id)
            .order_by(AIMessage.created_at.asc())
        )
        return list(result.scalars().all())

    async def send_message(
        self, conversation_id: str, data: AIMessageCreate
    ) -> dict:
        """发送消息并获取 AI 回复。"""
        # TODO: 接入 LLM API，实现实际对话逻辑
        # 1. 保存用户消息
        # 2. 构建上下文调用 LLM
        # 3. 保存 AI 回复
        # 4. 返回响应
        return {"user_message": None, "assistant_message": None}

    async def delete_conversation(self, conversation_id: str) -> bool:
        """删除会话。"""
        conversation = await self.get_conversation(conversation_id)
        if conversation is None:
            return False
        await self.db.delete(conversation)
        await self.db.flush()
        return True
