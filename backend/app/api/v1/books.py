"""书籍接口。

提供书籍 CRUD、文件上传、内容解析触发、RAG 问答、笔记管理接口。
"""

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.exceptions import NotFoundException
from app.core.permissions import reject_viewer_write
from app.models.user import User
from app.schemas.book import (
    BookCreate,
    BookNoteCreate,
    BookNoteResponse,
    BookProgressUpdate,
    BookQARequest,
    BookQAResponse,
    BookResponse,
    BookUpdate,
)
from app.schemas.common import ApiResponse
from app.services.book_service import BookService

router = APIRouter(
    prefix="/books",
    tags=["书籍管理"],
    dependencies=[Depends(reject_viewer_write)],
)


@router.get("/health", summary="健康检查")
async def health_check():
    """书籍模块健康检查。"""
    return ApiResponse(data={"status": "ok", "module": "books"})


# ---------- 书籍 CRUD ----------


@router.get("", summary="获取书籍列表")
async def list_books(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取当前用户的书籍列表。"""
    service = BookService(db)
    books = await service.list_books(current_user.id)
    return ApiResponse(
        data=[BookResponse.model_validate(b) for b in books]
    )


@router.post("", summary="创建书籍记录", status_code=201)
async def create_book(
    data: BookCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """创建书籍记录（不包含文件上传，适用于手动录入）。"""
    service = BookService(db)
    book = await service.create_book(current_user.id, data)
    return ApiResponse(data=BookResponse.model_validate(book))


@router.post("/upload", summary="上传书籍文件", status_code=201)
async def upload_book(
    file: UploadFile = File(..., description="书籍文件 (pdf/epub/txt)"),
    title: Optional[str] = Form(None, description="书名（可选，默认使用文件名）"),
    author: Optional[str] = Form(None, description="作者"),
    category: Optional[str] = Form(None, description="分类"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """上传书籍文件并创建书籍记录。

    支持的文件类型：pdf / epub / txt
    上传后可通过 `POST /books/{book_id}/parse` 触发内容解析。
    """
    service = BookService(db)
    content = await file.read()
    book = await service.save_upload_file(
        user_id=current_user.id,
        filename=file.filename or "untitled.txt",
        file_content=content,
        title=title,
        author=author,
        category=category,
    )
    return ApiResponse(data=BookResponse.model_validate(book))


@router.get("/{book_id}", summary="获取书籍详情")
async def get_book(
    book_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取书籍详情。"""
    service = BookService(db)
    book = await service.get_book(book_id)
    if book is None:
        raise NotFoundException(
            message="书籍不存在", detail={"book_id": str(book_id)}
        )
    return ApiResponse(data=BookResponse.model_validate(book))


@router.patch("/{book_id}", summary="更新书籍信息")
async def update_book(
    book_id: uuid.UUID,
    data: BookUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """更新书籍信息。"""
    service = BookService(db)
    book = await service.update_book(book_id, data)
    if book is None:
        raise NotFoundException(
            message="书籍不存在", detail={"book_id": str(book_id)}
        )
    return ApiResponse(data=BookResponse.model_validate(book))


@router.delete("/{book_id}", summary="删除书籍")
async def delete_book(
    book_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """删除书籍（同时删除关联的笔记和知识块）。"""
    service = BookService(db)
    deleted = await service.delete_book(book_id)
    if not deleted:
        raise NotFoundException(
            message="书籍不存在", detail={"book_id": str(book_id)}
        )
    return ApiResponse(data={"deleted": True})


# ---------- 阅读进度 ----------


@router.patch("/{book_id}/progress", summary="更新阅读进度")
async def update_progress(
    book_id: uuid.UUID,
    data: BookProgressUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """更新阅读进度（0.0 ~ 1.0）。"""
    service = BookService(db)
    book = await service.update_progress(book_id, data.progress)
    if book is None:
        raise NotFoundException(
            message="书籍不存在", detail={"book_id": str(book_id)}
        )
    return ApiResponse(data=BookResponse.model_validate(book))


# ---------- 内容解析 ----------


@router.post("/{book_id}/parse", summary="触发内容解析")
async def parse_book(
    book_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """触发书籍内容解析+知识提取（异步任务）。

    返回任务 ID，可通过 Celery 结果后端查询任务状态。
    """
    service = BookService(db)
    result = await service.trigger_parse(book_id)
    return ApiResponse(data=result)


# ---------- RAG 问答 ----------


@router.post("/{book_id}/qa", summary="书籍 RAG 问答")
async def book_qa(
    book_id: uuid.UUID,
    data: BookQARequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """基于书籍内容的 RAG 问答。

    检索书中相关知识片段，结合 LLM 生成回答。
    """
    service = BookService(db)
    result = await service.qa(book_id, data)
    return ApiResponse(data=BookQAResponse(**result))


# ---------- 笔记管理 ----------


@router.get("/{book_id}/notes", summary="获取笔记列表")
async def list_notes(
    book_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取书籍的笔记列表。"""
    service = BookService(db)
    notes = await service.list_notes(book_id)
    return ApiResponse(
        data=[BookNoteResponse.model_validate(n) for n in notes]
    )


@router.post(
    "/{book_id}/notes", summary="创建笔记", status_code=201
)
async def create_note(
    book_id: uuid.UUID,
    data: BookNoteCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """创建书籍笔记。"""
    # 确保 book_id 一致
    note_data = data.model_copy(update={"book_id": book_id})
    service = BookService(db)
    note = await service.create_note(current_user.id, note_data)
    return ApiResponse(data=BookNoteResponse.model_validate(note))
