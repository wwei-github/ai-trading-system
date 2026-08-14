"""书籍 Schema（Stage 7，对齐 PRD §5.7）。"""

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class BookBase(BaseModel):
    """书籍基础字段。"""

    title: str = Field(..., description="书名")
    author: Optional[str] = None
    category: Optional[str] = None
    file_type: Optional[str] = None
    cover_url: Optional[str] = None


class BookCreate(BookBase):
    """创建书籍请求。"""

    file_path: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class BookUpdate(BaseModel):
    """更新书籍请求。"""

    title: Optional[str] = None
    author: Optional[str] = None
    category: Optional[str] = None
    cover_url: Optional[str] = None
    progress: Optional[float] = Field(None, ge=0.0, le=1.0)
    metadata: Optional[Dict[str, Any]] = None


class BookProgressUpdate(BaseModel):
    """阅读进度更新。"""

    progress: float = Field(..., ge=0.0, le=1.0, description="阅读进度 0.0~1.0")


class BookResponse(BookBase):
    """书籍响应。"""

    id: uuid.UUID
    user_id: uuid.UUID
    file_path: Optional[str] = None
    progress: float
    metadata: Optional[Dict[str, Any]] = Field(None, alias="metadata_")
    parse_status: Optional[str] = None
    parse_progress: int = 0
    total_chapters: int = 0
    total_chunks: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True, "populate_by_name": True}


# ---------- 章节 ----------


class BookChapterResponse(BaseModel):
    """章节响应（含正文）。"""

    id: uuid.UUID
    book_id: uuid.UUID
    title: str
    chapter_order: int
    content: Optional[str] = None
    page_start: Optional[int] = None
    page_end: Optional[int] = None
    char_count: int
    level: int

    model_config = {"from_attributes": True}


class BookChapterTOC(BaseModel):
    """目录项（不含正文，用于阅读器导航）。"""

    id: uuid.UUID
    title: str
    chapter_order: int
    page_start: Optional[int] = None
    page_end: Optional[int] = None
    char_count: int
    level: int

    model_config = {"from_attributes": True}


# ---------- 笔记 ----------


class BookNoteBase(BaseModel):
    """笔记基础字段。"""

    chapter: Optional[str] = None
    chapter_order: Optional[int] = None
    note_type: str = Field("note", description="笔记类型：highlight / note / bookmark")
    content: str
    highlight_range: Optional[Dict[str, Any]] = None


class BookNoteCreate(BookNoteBase):
    """创建笔记请求。"""

    book_id: uuid.UUID


class BookNoteUpdate(BaseModel):
    """更新笔记请求。"""

    content: Optional[str] = None
    note_type: Optional[str] = None


class BookNoteResponse(BookNoteBase):
    """笔记响应。"""

    id: uuid.UUID
    book_id: uuid.UUID
    user_id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ---------- RAG 问答 ----------


class BookQARequest(BaseModel):
    """书籍 RAG 问答请求。"""

    question: str = Field(..., description="问题内容")
    top_k: int = Field(5, ge=1, le=20, description="检索的知识块数量")


class BookQAResponse(BaseModel):
    """书籍 RAG 问答响应。"""

    answer: str = Field(..., description="AI 回答")
    sources: list = Field(default_factory=list, description="引用来源知识块")


# ---------- 全文搜索 ----------


class BookSearchRequest(BaseModel):
    """全文搜索请求。"""

    keyword: str = Field(..., min_length=1, description="搜索关键词")
    limit: int = Field(20, ge=1, le=100, description="返回结果数")


class BookSearchResult(BaseModel):
    """搜索结果项。"""

    chunk_id: uuid.UUID
    chapter_order: Optional[int] = None
    content: str
    score: float = Field(..., description="相关度分数")
    metadata: Optional[Dict[str, Any]] = None


# ---------- AI 知识提取 ----------


class KnowledgeExtractionRequest(BaseModel):
    """AI 知识提取请求（PRD §5.7.3）。"""

    chapter_order: Optional[int] = Field(
        None, description="指定章节序号，留空则全书提取"
    )
    context_chunks: int = Field(
        5, ge=1, le=20, description="上下文知识块数量"
    )


class KnowledgeExtractionResponse(BaseModel):
    """AI 知识提取响应（6 部分策略草稿）。"""

    entry_rules: str = Field(..., description="入场规则")
    exit_rules: str = Field(..., description="出场规则")
    sizing: str = Field(..., description="仓位管理")
    risk_control: str = Field(..., description="风控规则")
    applicability: str = Field(..., description="适用场景")
    notes: str = Field(..., description="备注")
    draft_strategy: Optional[Dict[str, Any]] = Field(
        None, description="草稿策略 DSL（可保存为策略）"
    )
    source_chapters: List[int] = Field(
        default_factory=list, description="来源章节序号列表"
    )
