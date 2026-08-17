"""书籍接口（Stage 7，对齐 PRD §5.7）。

提供书籍 CRUD、文件上传、内容解析触发、章节管理、全文搜索、
RAG 问答、笔记管理、AI 知识提取接口。
"""

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.config import settings
from app.core.exceptions import NotFoundException
from app.core.permissions import reject_viewer_write
from app.core.rate_limit import rate_limit
from app.models.user import User
from app.schemas.book import (
    BookAnalyzeRequest,
    BookAnalyzeResponse,
    BookChapterResponse,
    BookChapterTOC,
    BookCreate,
    BookNoteCreate,
    BookNoteResponse,
    BookNoteUpdate,
    BookProgressUpdate,
    BookQARequest,
    BookQAResponse,
    BookResponse,
    BookSearchRequest,
    BookSearchResult,
    BookUpdate,
    KnowledgeExtractionRequest,
    KnowledgeExtractionResponse,
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
@rate_limit(settings.RATE_LIMIT_UPLOAD_PER_MIN)
async def upload_book(
    request: Request,
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
    """获取书籍详情（含关联策略统计）。"""
    service = BookService(db)
    book = await service.get_book_with_strategy_count(book_id)
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
    """删除书籍（同时删除关联的章节、笔记和知识块）。"""
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

    返回任务 ID，可通过 Celery 结果后端或 SSE 进度接口查询任务状态。
    """
    service = BookService(db)
    result = await service.trigger_parse(book_id)
    return ApiResponse(data=result)


@router.post("/{book_id}/reparse", summary="重新解析书籍内容")
async def reparse_book(
    book_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """重新解析书籍内容（异步任务）。

    与 `POST /{book_id}/parse` 的区别：
    - 显式清除旧章节和知识块数据，确保完全重新生成
    - 重置解析进度和统计信息
    - 适用于解析失败后重试，或需要重新提取章节/知识块的场景

    返回任务 ID 和 `reparse: true` 标记。
    """
    service = BookService(db)
    result = await service.trigger_reparse(book_id)
    return ApiResponse(data=result)


@router.get(
    "/{book_id}/parse/progress", summary="查询解析进度"
)
async def get_parse_progress(
    book_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """查询书籍解析进度（轮询方式）。优先从 Redis 缓存读取实时进度。"""
    from app.core.database import redis_client
    from json import loads as json_loads

    # 1. 尝试从 Redis 缓存读取实时进度
    if redis_client:
        try:
            cached = await redis_client.get(f"book:parse:progress:{book_id}")
            if cached:
                data = json_loads(cached)
                return ApiResponse(data=data)
        except Exception:
            pass

    # 2. 回退到数据库读取
    service = BookService(db)
    book = await service.get_book(book_id)
    if book is None:
        raise NotFoundException(
            message="书籍不存在", detail={"book_id": str(book_id)}
        )
    return ApiResponse(
        data={
            "book_id": str(book_id),
            "status": book.parse_status or "pending",
            "progress": book.parse_progress,
            "stage": book.parse_stage,
            "stage_progress": book.parse_stage_progress,
            "stage_description": book.parse_stage_description,
            "total_chapters": book.total_chapters,
            "total_chunks": book.total_chunks,
            "parsed_chapters": book.parsed_chapters,
            "parsed_chunks": book.parsed_chunks,
            "error_message": book.parse_error_message,
        }
    )


@router.get("/{book_id}/parse/stream", summary="SSE 解析进度推送")
async def parse_progress_sse(
    book_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """SSE 流式推送解析进度，替代轮询。

    事件格式：`data: {"book_id": "...", "stage": "chunking", "progress": 50, ...}\\n\\n`
    结束标记：`data: [DONE]\\n\\n`
    """
    import asyncio
    import json

    from fastapi.responses import StreamingResponse

    from app.core.database import redis_client

    bt_id = str(book_id)

    async def event_generator():
        if redis_client is None:
            yield f"data: {json.dumps({'error': 'Redis 不可用'}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
            return

        pubsub = redis_client.pubsub()
        channel = f"book:parse:progress:{bt_id}"
        await pubsub.subscribe(channel)

        try:
            # 先推送当前状态
            service = BookService(db)
            book = await service.get_book(book_id)
            if book:
                payload = {
                    "book_id": bt_id,
                    "status": book.parse_status or "pending",
                    "progress": book.parse_progress,
                    "stage": book.parse_stage or "pending",
                    "stage_progress": book.parse_stage_progress,
                    "stage_description": book.parse_stage_description or "",
                    "total_chapters": book.total_chapters,
                    "total_chunks": book.total_chunks,
                    "parsed_chapters": book.parsed_chapters,
                    "parsed_chunks": book.parsed_chunks,
                    "error_message": book.parse_error_message,
                }
                yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
                if book.parse_status in ("completed", "failed"):
                    yield "data: [DONE]\n\n"
                    return

            # 订阅实时更新
            timeout = 600
            start = asyncio.get_event_loop().time()
            while True:
                if asyncio.get_event_loop().time() - start > timeout:
                    break
                msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=5.0)
                if msg is None:
                    continue
                if msg.get("type") == "message":
                    yield f"data: {msg.get('data')}\n\n"
                    try:
                        payload = json.loads(msg.get("data"))
                        if payload.get("status") in ("completed", "failed"):
                            break
                    except Exception:
                        pass
        finally:
            await pubsub.unsubscribe(channel)
            await pubsub.close()
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ---------- 章节管理（Stage 7.4） ----------


@router.get("/{book_id}/chapters", summary="获取书籍目录")
async def list_chapters(
    book_id: uuid.UUID,
    include_content: bool = Query(
        False, description="是否包含正文（默认仅目录）"
    ),
    page: int = Query(None, ge=1, description="页码，不传则返回全部"),
    page_size: int = Query(20, ge=1, le=100, description="每页条数"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取书籍章节列表。
    - page 和 page_size 不传：返回全部章节（前端目录使用）
    - page 和 page_size 传：返回分页（兼容旧接口）
    """
    service = BookService(db)
    if page is None:
        # 不需要分页，直接返回全部
        chapters = await service.list_chapters(book_id, include_content)
        schema = BookChapterResponse if include_content else BookChapterTOC
        return ApiResponse(
            data={
                "items": [schema.model_validate(c) for c in chapters],
                "total": len(chapters),
                "page": 1,
                "page_size": len(chapters),
            }
        )
    # 需要分页（兼容旧调用）
    chapters, total = await service.list_chapters_paginated(
        book_id, include_content=include_content,
        page=page, page_size=page_size,
    )
    schema = BookChapterResponse if include_content else BookChapterTOC
    return ApiResponse(
        data={
            "items": [schema.model_validate(c) for c in chapters],
            "total": total,
            "page": page,
            "page_size": page_size,
        }
    )


@router.get(
    "/{book_id}/chapters/{chapter_order}", summary="获取章节详情"
)
async def get_chapter(
    book_id: uuid.UUID,
    chapter_order: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取指定章节详情（含正文）。"""
    service = BookService(db)
    chapter = await service.get_chapter(book_id, chapter_order)
    if chapter is None:
        raise NotFoundException(
            message="章节不存在",
            detail={"book_id": str(book_id), "chapter_order": chapter_order},
        )
    return ApiResponse(data=BookChapterResponse.model_validate(chapter))


# ---------- 全文搜索（Stage 7.4） ----------


@router.post("/{book_id}/search", summary="书籍全文搜索")
async def search_in_book(
    book_id: uuid.UUID,
    data: BookSearchRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """在书籍知识块中全文搜索，返回匹配片段及上下文。"""
    service = BookService(db)
    results = await service.search_in_book(
        book_id, data.keyword, limit=data.limit
    )
    return ApiResponse(
        data=[BookSearchResult(**r) for r in results]
    )


# ---------- RAG 问答 ----------


@router.post("/{book_id}/qa", summary="书籍 RAG 问答")
async def book_qa(
    book_id: uuid.UUID,
    data: BookQARequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """基于书籍内容的 RAG 问答。

    使用余弦相似度向量检索相关知识片段，结合 LLM 生成回答。
    """
    service = BookService(db)
    result = await service.qa(book_id, data)
    return ApiResponse(data=BookQAResponse(**result))


# ---------- AI 知识提取（Stage 7.5） ----------


@router.post(
    "/{book_id}/extract", summary="AI 知识提取（6 部分策略草稿）"
)
async def extract_knowledge(
    book_id: uuid.UUID,
    data: KnowledgeExtractionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """从书籍章节中提取交易策略知识，生成 6 部分策略草稿。

    可指定 `chapter_order` 提取单章节，留空则全书检索相关内容。
    返回内容包含可直接保存为策略的草稿 DSL。
    """
    service = BookService(db)
    result = await service.extract_knowledge(book_id, data)
    return ApiResponse(data=result)


# ---------- 书籍 AI 分析 + 交易系统生成（Stage 7.6）----------


@router.post(
    "/{book_id}/analyze", summary="AI 分析书籍并生成完整交易系统"
)
async def analyze_book(
    book_id: uuid.UUID,
    data: BookAnalyzeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """用大模型深度分析整本书籍，并生成一个完整可运行的交易系统。

    两步流程：
    1. LLM 分析书籍内容（交易哲学、策略框架、适用场景等）
    2. LLM 根据分析结果生成完整的结构化交易系统 DSL

    **请求体：**
    | 字段 | 类型 | 必填 | 说明 |
    |------|------|------|------|
    | save_strategy | bool | 否 | 是否自动保存为策略（默认 true） |
    | strategy_name | string | 否 | 策略名称（留空自动生成） |
    | focus_areas | string[] | 否 | 重点关注领域 |

    **返回结果：**
    ```json
    {
      "code": 0,
      "message": "ok",
      "data": {
        "book_analysis": "书籍分析报告（Markdown）",
        "core_concepts": ["概念1", "概念2"],
        "trading_system": { "name": "...", "entry_rules": [...], ... },
        "system_summary": "交易系统摘要",
        "saved_strategy_id": "uuid（若 save_strategy=true）",
        "source_chapters": [1, 2, 3]
      }
    }
    ```
    """
    service = BookService(db)
    result = await service.analyze_book(book_id, data, current_user.id)
    return ApiResponse(data=result)


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


@router.patch("/notes/{note_id}", summary="更新笔记")
async def update_note(
    note_id: uuid.UUID,
    data: BookNoteUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """更新笔记内容或类型。"""
    service = BookService(db)
    note = await service.update_note(note_id, data)
    if note is None:
        raise NotFoundException(
            message="笔记不存在", detail={"note_id": str(note_id)}
        )
    return ApiResponse(data=BookNoteResponse.model_validate(note))


@router.delete("/notes/{note_id}", summary="删除笔记")
async def delete_note(
    note_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """删除笔记。"""
    service = BookService(db)
    deleted = await service.delete_note(note_id)
    if not deleted:
        raise NotFoundException(
            message="笔记不存在", detail={"note_id": str(note_id)}
        )
    return ApiResponse(data={"deleted": True})


# ---------- 书籍关联策略 ----------


@router.get("/{book_id}/strategies", summary="获取书籍生成的策略列表")
async def list_book_strategies(
    book_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取从该书 AI 分析生成的策略列表。"""
    from app.models.strategy import Strategy
    from app.schemas.strategy import StrategyResponse

    from sqlalchemy import select

    result = await db.execute(
        select(Strategy)
        .where(Strategy.source_book_id == book_id)
        .order_by(Strategy.created_at.desc())
    )
    strategies = list(result.scalars().all())
    return ApiResponse(
        data=[StrategyResponse.model_validate(s) for s in strategies]
    )
