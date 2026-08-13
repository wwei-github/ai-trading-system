"""书籍服务。

处理书籍管理、笔记、文件上传、RAG 知识检索与问答。
文件解析、向量化分块通过 Celery 异步任务执行（见 app/tasks/book_tasks.py）。
"""

import os
import uuid
from typing import Any, Dict, List, Optional

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import BadRequestException, NotFoundException
from app.models.book import Book, BookNote, KnowledgeChunk
from app.schemas.book import (
    BookCreate,
    BookNoteCreate,
    BookQARequest,
    BookUpdate,
)
from app.services.llm_provider import get_llm_provider

# 允许上传的文件扩展名
ALLOWED_EXTENSIONS = {"pdf", "epub", "txt"}


class BookService:
    """书籍服务。

    处理书籍管理、笔记和知识库检索。
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.llm = get_llm_provider()

    # ---------- 书籍 CRUD ----------

    async def create_book(
        self, user_id: uuid.UUID, data: BookCreate
    ) -> Book:
        """创建书籍记录。"""
        book = Book(
            user_id=user_id,
            title=data.title,
            author=data.author,
            category=data.category,
            file_path=data.file_path,
            file_type=data.file_type,
            cover_url=data.cover_url,
            metadata_=data.metadata,
        )
        self.db.add(book)
        await self.db.flush()
        return book

    async def get_book(self, book_id: uuid.UUID) -> Optional[Book]:
        """获取书籍详情。"""
        result = await self.db.execute(select(Book).where(Book.id == book_id))
        return result.scalar_one_or_none()

    async def list_books(self, user_id: uuid.UUID) -> List[Book]:
        """获取用户的全部书籍。"""
        result = await self.db.execute(
            select(Book)
            .where(Book.user_id == user_id)
            .order_by(Book.created_at.desc())
        )
        return list(result.scalars().all())

    async def update_book(
        self, book_id: uuid.UUID, data: BookUpdate
    ) -> Optional[Book]:
        """更新书籍信息。"""
        book = await self.get_book(book_id)
        if book is None:
            return None
        update_data = data.model_dump(exclude_unset=True)
        if "metadata" in update_data:
            update_data["metadata_"] = update_data.pop("metadata")
        for key, value in update_data.items():
            setattr(book, key, value)
        await self.db.flush()
        return book

    async def delete_book(self, book_id: uuid.UUID) -> bool:
        """删除书籍（同时删除关联笔记和知识块）。"""
        book = await self.get_book(book_id)
        if book is None:
            return False
        # 删除关联笔记
        await self.db.execute(
            delete(BookNote).where(BookNote.book_id == book_id)
        )
        # 删除关联知识块
        await self.db.execute(
            delete(KnowledgeChunk).where(KnowledgeChunk.book_id == book_id)
        )
        await self.db.delete(book)
        await self.db.flush()
        return True

    async def update_progress(
        self, book_id: uuid.UUID, progress: float
    ) -> Optional[Book]:
        """更新阅读进度。"""
        book = await self.get_book(book_id)
        if book is None:
            return None
        book.progress = progress
        await self.db.flush()
        return book

    # ---------- 文件上传 ----------

    async def save_upload_file(
        self,
        user_id: uuid.UUID,
        filename: str,
        file_content: bytes,
        title: Optional[str] = None,
        author: Optional[str] = None,
        category: Optional[str] = None,
    ) -> Book:
        """保存上传的书籍文件并创建书籍记录。

        Args:
            user_id: 用户 ID
            filename: 原始文件名
            file_content: 文件二进制内容
            title: 书名（可选，默认使用文件名）
            author: 作者
            category: 分类

        Returns:
            创建的 Book 实例

        Raises:
            BadRequestException: 文件类型不支持或超过大小限制
        """
        # 校验文件大小
        if len(file_content) > settings.MAX_UPLOAD_SIZE:
            raise BadRequestException(
                message=f"文件大小超过限制（最大 {settings.MAX_UPLOAD_SIZE // 1024 // 1024}MB）",
                detail={"size": len(file_content)},
            )

        # 校验扩展名
        ext = (
            filename.rsplit(".", 1)[-1].lower()
            if "." in filename
            else ""
        )
        if ext not in ALLOWED_EXTENSIONS:
            raise BadRequestException(
                message=f"不支持的文件类型: {ext}（允许: pdf/epub/txt）",
                detail={"extension": ext},
            )

        # 创建用户上传目录
        upload_dir = os.path.join(
            settings.UPLOAD_DIR, "books", str(user_id)
        )
        os.makedirs(upload_dir, exist_ok=True)

        # 生成唯一文件名
        saved_filename = f"{uuid.uuid4().hex}.{ext}"
        file_path = os.path.join(upload_dir, saved_filename)

        # 写入文件
        with open(file_path, "wb") as f:
            f.write(file_content)

        # 创建书籍记录
        book = Book(
            user_id=user_id,
            title=title or filename.rsplit(".", 1)[0],
            author=author,
            category=category,
            file_path=file_path,
            file_type=ext,
            parse_status="pending",
        )
        self.db.add(book)
        await self.db.flush()
        return book

    # ---------- 内容解析 ----------

    async def trigger_parse(self, book_id: uuid.UUID) -> dict:
        """触发书籍内容解析（异步任务）。

        Returns:
            包含 task_id 和 status 的字典

        Raises:
            NotFoundException: 书籍不存在
            BadRequestException: 文件路径为空
        """
        book = await self.get_book(book_id)
        if book is None:
            raise NotFoundException(
                message="书籍不存在", detail={"book_id": str(book_id)}
            )
        if not book.file_path:
            raise BadRequestException(
                message="书籍没有关联文件，无法解析",
                detail={"book_id": str(book_id)},
            )

        # 更新状态
        book.parse_status = "parsing"
        await self.db.flush()

        # 异步派发解析任务（延迟导入避免循环依赖）
        from app.tasks.book_tasks import parse_book

        task = parse_book.delay(str(book_id))
        return {
            "book_id": str(book_id),
            "task_id": task.id,
            "status": "parsing",
        }

    async def list_chunks(
        self, book_id: uuid.UUID, limit: Optional[int] = None
    ) -> List[KnowledgeChunk]:
        """获取书籍的知识块列表。"""
        stmt = select(KnowledgeChunk).where(
            KnowledgeChunk.book_id == book_id
        )
        if limit is not None:
            stmt = stmt.limit(limit)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def save_chunks(
        self, book_id: uuid.UUID, chunks: List[Dict[str, Any]]
    ) -> int:
        """保存解析后的知识块（由 parse_book 任务调用）。

        Args:
            book_id: 书籍 ID
            chunks: 知识块列表，每项包含 content / metadata / embedding

        Returns:
            保存的知识块数量
        """
        # 先清空旧知识块
        await self.db.execute(
            delete(KnowledgeChunk).where(KnowledgeChunk.book_id == book_id)
        )

        for chunk in chunks:
            kc = KnowledgeChunk(
                book_id=book_id,
                content=chunk["content"],
                embedding=chunk.get("embedding"),
                chunk_metadata=chunk.get("metadata"),
            )
            self.db.add(kc)
        await self.db.flush()
        return len(chunks)

    async def update_parse_status(
        self, book_id: uuid.UUID, status: str
    ) -> None:
        """更新书籍解析状态。"""
        book = await self.get_book(book_id)
        if book is not None:
            book.parse_status = status
            await self.db.flush()

    # ---------- RAG 问答 ----------

    async def retrieve_relevant_chunks(
        self, book_id: uuid.UUID, query: str, top_k: int = 3
    ) -> List[KnowledgeChunk]:
        """从书籍知识库检索相关片段。

        生产环境应使用向量相似度检索（pgvector）。
        当前实现为基于关键词匹配的简化版。
        """
        result = await self.db.execute(
            select(KnowledgeChunk)
            .where(KnowledgeChunk.book_id == book_id)
            .limit(100)
        )
        chunks = list(result.scalars().all())
        if not chunks:
            return []

        # 按关键词匹配排序
        query_words = set(query.lower().split())

        def score(chunk: KnowledgeChunk) -> int:
            content = chunk.content.lower()
            return sum(1 for w in query_words if w in content)

        ranked = sorted(chunks, key=score, reverse=True)
        # 仅返回有匹配的块
        return [c for c in ranked[:top_k] if score(c) > 0]

    async def qa(
        self, book_id: uuid.UUID, data: BookQARequest
    ) -> dict:
        """基于书籍内容的 RAG 问答。

        Args:
            book_id: 书籍 ID
            data: 问答请求

        Returns:
            包含 answer 和 sources 的字典

        Raises:
            NotFoundException: 书籍不存在
            BadRequestException: 书籍尚未解析完成
        """
        book = await self.get_book(book_id)
        if book is None:
            raise NotFoundException(
                message="书籍不存在", detail={"book_id": str(book_id)}
            )

        # 检索相关知识块
        chunks = await self.retrieve_relevant_chunks(
            book_id, data.question, top_k=data.top_k
        )
        if not chunks:
            return {
                "answer": "未在书中找到与问题相关的内容，请尝试更换关键词或先解析书籍内容。",
                "sources": [],
            }

        # 构建上下文
        context_text = "\n---\n".join(
            f"[片段 {i + 1}] {c.content}" for i, c in enumerate(chunks)
        )

        messages = [
            {
                "role": "system",
                "content": (
                    "你是一位交易知识助手。请基于以下书籍片段回答用户问题。"
                    "回答应忠实于原文，并在合适位置标注引用片段编号（如 [片段 1]）。"
                    "若片段不足以回答问题，请如实告知。\n\n"
                    f"参考片段：\n{context_text}"
                ),
            },
            {"role": "user", "content": data.question},
        ]
        answer = await self.llm.chat(messages)

        return {
            "answer": answer,
            "sources": [
                {
                    "chunk_id": str(c.id),
                    "content": c.content[:200],
                    "metadata": c.chunk_metadata,
                }
                for c in chunks
            ],
        }

    # ---------- 笔记管理 ----------

    async def create_note(
        self, user_id: uuid.UUID, data: BookNoteCreate
    ) -> BookNote:
        """创建书籍笔记。"""
        # 校验书籍存在
        book = await self.get_book(data.book_id)
        if book is None:
            raise NotFoundException(
                message="书籍不存在",
                detail={"book_id": str(data.book_id)},
            )

        note = BookNote(
            book_id=data.book_id,
            user_id=user_id,
            chapter=data.chapter,
            content=data.content,
            highlight_range=data.highlight_range,
        )
        self.db.add(note)
        await self.db.flush()
        return note

    async def list_notes(self, book_id: uuid.UUID) -> List[BookNote]:
        """获取书籍的笔记列表。"""
        result = await self.db.execute(
            select(BookNote)
            .where(BookNote.book_id == book_id)
            .order_by(BookNote.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_note(
        self, note_id: uuid.UUID
    ) -> Optional[BookNote]:
        """获取笔记详情。"""
        result = await self.db.execute(
            select(BookNote).where(BookNote.id == note_id)
        )
        return result.scalar_one_or_none()

    async def delete_note(self, note_id: uuid.UUID) -> bool:
        """删除笔记。"""
        note = await self.get_note(note_id)
        if note is None:
            return False
        await self.db.delete(note)
        await self.db.flush()
        return True
