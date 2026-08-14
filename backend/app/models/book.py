"""书籍与知识库模型（Stage 7，对齐 PRD §5.7）。"""

import uuid
from typing import Any, Optional

from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Book(Base):
    """书籍表。

    存储交易相关书籍的元数据和阅读进度。
    """

    __tablename__ = "books"

    # 所属用户
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), index=True, nullable=False
    )

    # 书名
    title: Mapped[str] = mapped_column(String(500), nullable=False)

    # 作者
    author: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    # 分类
    category: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # 文件路径
    file_path: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)

    # 文件类型：pdf / epub / txt
    file_type: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    # 封面 URL
    cover_url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)

    # 阅读进度（0.0 ~ 1.0）
    progress: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    # 元数据：页数、出版社、ISBN 等
    metadata_: Mapped[Optional[dict]] = mapped_column("metadata", JSONB, nullable=True)

    # 解析状态：pending / parsing / completed / failed
    parse_status: Mapped[Optional[str]] = mapped_column(
        String(20), default="pending", nullable=True
    )

    # 解析进度（0-100）
    parse_progress: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # 总章节数
    total_chapters: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # 总知识块数
    total_chunks: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class BookChapter(Base):
    """书籍章节表（Stage 7.2，对齐 PRD §5.7.2 R2）。

    存储解析后的章节结构和文本内容，支持阅读器目录导航。
    """

    __tablename__ = "book_chapters"

    # 所属书籍
    book_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("books.id", ondelete="CASCADE"),
        index=True, nullable=False,
    )

    # 章节标题
    title: Mapped[str] = mapped_column(String(500), nullable=False)

    # 章节序号（从 1 开始）
    chapter_order: Mapped[int] = mapped_column(Integer, nullable=False)

    # 章节文本内容
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # 起始页码（PDF）
    page_start: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # 结束页码
    page_end: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # 字符数
    char_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # 层级（1=一级标题，2=二级标题，3=三级标题）
    level: Mapped[int] = mapped_column(Integer, default=1, nullable=False)


class BookNote(Base):
    """书籍笔记/高亮表。"""

    __tablename__ = "book_notes"

    # 所属书籍
    book_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("books.id"), index=True, nullable=False
    )

    # 所属用户
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), index=True, nullable=False
    )

    # 章节标题
    chapter: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # 章节序号
    chapter_order: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # 笔记类型：highlight / note / bookmark
    note_type: Mapped[str] = mapped_column(
        String(20), default="note", nullable=False
    )

    # 笔记内容
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # 高亮范围：{"page": 10, "start": 100, "end": 200}
    highlight_range: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)


class KnowledgeChunk(Base):
    """知识库分块表（RAG 向量检索，Stage 7.3）。

    将书籍内容切分为文本块，存储向量嵌入用于语义检索。
    向量以 JSON 字符串存储，检索时通过余弦相似度计算（Python 层）。
    生产环境可升级为 pgvector 扩展以获得更好性能。
    """

    __tablename__ = "knowledge_chunks"

    # 所属书籍
    book_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("books.id"), index=True, nullable=False
    )

    # 所属章节序号
    chapter_order: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # 文本内容
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # 向量嵌入（JSON 字符串，如 "[0.1, 0.2, ...]"）
    embedding: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # 元数据：页码、章节、字符位置等
    chunk_metadata: Mapped[Optional[dict]] = mapped_column(
        "metadata", JSONB, nullable=True
    )
