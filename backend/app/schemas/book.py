"""书籍 Schema。"""

import uuid
from datetime import datetime
from typing import Any, Dict, Optional

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


class BookResponse(BookBase):
    """书籍响应。"""

    id: uuid.UUID
    user_id: uuid.UUID
    file_path: Optional[str] = None
    progress: float
    metadata: Optional[Dict[str, Any]] = Field(None, alias="metadata_")
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True, "populate_by_name": True}


class BookNoteBase(BaseModel):
    """笔记基础字段。"""

    chapter: Optional[str] = None
    content: str
    highlight_range: Optional[Dict[str, Any]] = None


class BookNoteCreate(BookNoteBase):
    """创建笔记请求。"""

    book_id: uuid.UUID


class BookNoteResponse(BookNoteBase):
    """笔记响应。"""

    id: uuid.UUID
    book_id: uuid.UUID
    user_id: uuid.UUID
    created_at: datetime

    model_config = {"from_attributes": True}
