"""书籍与知识库模型。"""

import uuid
from typing import Any, Optional

from sqlalchemy import Float, ForeignKey, String, Text
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

    # 章节
    chapter: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    # 笔记内容
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # 高亮范围：{"page": 10, "start": 100, "end": 200}
    highlight_range: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)


class KnowledgeChunk(Base):
    """知识库分块表（RAG 向量检索）。

    将书籍内容切分为文本块，存储向量嵌入用于语义检索。
    """

    __tablename__ = "knowledge_chunks"

    # 所属书籍
    book_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("books.id"), index=True, nullable=False
    )

    # 文本内容
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # 向量嵌入：当前使用 Text 类型存储向量的 JSON 字符串。
    # 实际生产环境应使用 pgvector 扩展（VECTOR(1536) 类型）以支持高效向量检索。
    embedding: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # 元数据：页码、章节等
    chunk_metadata: Mapped[Optional[dict]] = mapped_column(
        "metadata", JSONB, nullable=True
    )
