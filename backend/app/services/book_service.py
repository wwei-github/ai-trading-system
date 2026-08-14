"""书籍服务。

处理书籍管理、笔记、文件上传、RAG 知识检索与问答、章节管理、
全文搜索、AI 知识提取。

文件解析、向量化分块通过 Celery 异步任务执行（见 app/tasks/book_tasks.py）。
向量检索采用余弦相似度（Stage 7.3），未配置 LLM API Key 时降级为关键词匹配。
"""

import json
import math
import os
import uuid
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import BadRequestException, NotFoundException
from app.models.book import Book, BookChapter, BookNote, KnowledgeChunk
from app.schemas.book import (
    BookCreate,
    BookNoteCreate,
    BookNoteUpdate,
    BookQARequest,
    BookUpdate,
    KnowledgeExtractionRequest,
    KnowledgeExtractionResponse,
)
from app.services.llm_provider import get_llm_provider

# 允许上传的文件扩展名
ALLOWED_EXTENSIONS = {"pdf", "epub", "txt"}

# 单用户最大书籍数（PRD §5.7.2 R1：上传数量限制）
MAX_BOOKS_PER_USER = 50


def _cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
    """计算两个向量的余弦相似度。

    Returns:
        相似度分数 [-1, 1]，越接近 1 越相似
    """
    if not vec_a or not vec_b or len(vec_a) != len(vec_b):
        return 0.0
    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


class BookService:
    """书籍服务。

    处理书籍管理、笔记、章节导航、知识库检索与 AI 知识提取。
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.llm = get_llm_provider()

    # ---------- 书籍 CRUD ----------

    async def create_book(
        self, user_id: uuid.UUID, data: BookCreate
    ) -> Book:
        """创建书籍记录。"""
        await self._check_user_book_quota(user_id)

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

    async def _check_user_book_quota(self, user_id: uuid.UUID) -> None:
        """校验用户书籍数量是否超过上限。"""
        result = await self.db.execute(
            select(func.count(Book.id)).where(Book.user_id == user_id)
        )
        count = result.scalar_one()
        if count >= MAX_BOOKS_PER_USER:
            raise BadRequestException(
                message=f"书籍数量已达上限（{MAX_BOOKS_PER_USER} 本），请先删除不再需要的书籍",
                detail={"current": count, "limit": MAX_BOOKS_PER_USER},
            )

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
        """删除书籍（同时删除关联笔记、章节和知识块）。"""
        book = await self.get_book(book_id)
        if book is None:
            return False
        # 删除关联章节
        await self.db.execute(
            delete(BookChapter).where(BookChapter.book_id == book_id)
        )
        # 删除关联笔记
        await self.db.execute(
            delete(BookNote).where(BookNote.book_id == book_id)
        )
        # 删除关联知识块
        await self.db.execute(
            delete(KnowledgeChunk).where(KnowledgeChunk.book_id == book_id)
        )
        # 删除文件
        if book.file_path and os.path.exists(book.file_path):
            try:
                os.remove(book.file_path)
            except OSError:
                pass
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
        # 校验上传数量
        await self._check_user_book_quota(user_id)

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
        book.parse_progress = 0
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
            chunks: 知识块列表，每项包含 content / metadata / embedding / chapter_order

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
                chapter_order=chunk.get("chapter_order"),
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

    # ---------- 章节管理（Stage 7.4） ----------

    async def list_chapters(
        self, book_id: uuid.UUID, include_content: bool = False
    ) -> List[BookChapter]:
        """获取书籍的章节列表。

        Args:
            book_id: 书籍 ID
            include_content: 是否包含正文（目录导航时为 False）
        """
        stmt = (
            select(BookChapter)
            .where(BookChapter.book_id == book_id)
            .order_by(BookChapter.chapter_order.asc())
        )
        result = await self.db.execute(stmt)
        chapters = list(result.scalars().all())
        # 不包含正文时清空 content 字段以减少响应体积
        if not include_content:
            for ch in chapters:
                ch.content = ""  # type: ignore[assignment]
        return chapters

    async def get_chapter(
        self, book_id: uuid.UUID, chapter_order: int
    ) -> Optional[BookChapter]:
        """获取指定章节详情（含正文）。"""
        result = await self.db.execute(
            select(BookChapter).where(
                BookChapter.book_id == book_id,
                BookChapter.chapter_order == chapter_order,
            )
        )
        return result.scalar_one_or_none()

    # ---------- 全文搜索（Stage 7.4） ----------

    async def search_in_book(
        self, book_id: uuid.UUID, keyword: str, limit: int = 20
    ) -> List[Dict[str, Any]]:
        """在书籍知识块中全文搜索。

        使用 PostgreSQL ILIKE 进行模糊匹配，返回匹配片段及其元数据。
        """
        if not keyword.strip():
            return []

        pattern = f"%{keyword}%"
        result = await self.db.execute(
            select(KnowledgeChunk)
            .where(
                KnowledgeChunk.book_id == book_id,
                KnowledgeChunk.content.ilike(pattern),
            )
            .limit(limit)
        )
        chunks = list(result.scalars().all())

        results: List[Dict[str, Any]] = []
        for c in chunks:
            # 截取关键词上下文片段
            content = c.content
            lower = content.lower()
            kw_lower = keyword.lower()
            pos = lower.find(kw_lower)
            if pos == -1:
                snippet = content[:200]
            else:
                start = max(0, pos - 80)
                end = min(len(content), pos + len(keyword) + 120)
                snippet = ("..." if start > 0 else "") + content[start:end] + (
                    "..." if end < len(content) else ""
                )
            results.append({
                "chunk_id": str(c.id),
                "chapter_order": c.chapter_order,
                "content": snippet,
                "score": 1.0,  # 关键词匹配固定为 1.0
                "metadata": c.chunk_metadata,
            })
        return results

    # ---------- 向量检索（Stage 7.3） ----------

    async def retrieve_relevant_chunks(
        self, book_id: uuid.UUID, query: str, top_k: int = 5
    ) -> List[Tuple[KnowledgeChunk, float]]:
        """从书籍知识库检索相关片段（余弦相似度向量检索）。

        优先使用向量检索；若知识块无 embedding 或未配置 LLM API Key，
        则降级为关键词匹配。

        Args:
            book_id: 书籍 ID
            query: 查询文本
            top_k: 返回的最相关知识块数量

        Returns:
            [(chunk, score), ...] 列表，按相似度降序
        """
        # 加载所有知识块
        result = await self.db.execute(
            select(KnowledgeChunk)
            .where(KnowledgeChunk.book_id == book_id)
            .order_by(KnowledgeChunk.chapter_order.asc())
        )
        chunks = list(result.scalars().all())
        if not chunks:
            return []

        # 尝试向量检索
        if settings.LLM_API_KEY:
            try:
                query_emb = await self.llm.embed([query])
                if query_emb and query_emb[0]:
                    q_vec = query_emb[0]
                    scored: List[Tuple[KnowledgeChunk, float]] = []
                    for c in chunks:
                        if not c.embedding:
                            continue
                        try:
                            c_vec = json.loads(c.embedding)
                        except (json.JSONDecodeError, TypeError):
                            continue
                        sim = _cosine_similarity(q_vec, c_vec)
                        scored.append((c, sim))
                    if scored:
                        scored.sort(key=lambda x: x[1], reverse=True)
                        return scored[:top_k]
            except Exception as e:  # noqa: BLE001
                # 向量检索失败，降级到关键词匹配
                import logging
                logging.getLogger(__name__).warning(
                    "向量检索失败，降级关键词匹配: %s", e
                )

        # 降级：关键词匹配
        return self._keyword_match(chunks, query, top_k)

    @staticmethod
    def _keyword_match(
        chunks: List[KnowledgeChunk], query: str, top_k: int
    ) -> List[Tuple[KnowledgeChunk, float]]:
        """基于关键词匹配的降级检索。"""
        query_words = {w for w in query.lower().split() if w}

        def score(chunk: KnowledgeChunk) -> float:
            content = chunk.content.lower()
            if not query_words:
                return 0.0
            return sum(1.0 for w in query_words if w in content) / len(
                query_words
            )

        ranked = sorted(
            ((c, score(c)) for c in chunks), key=lambda x: x[1], reverse=True
        )
        return [(c, s) for c, s in ranked[:top_k] if s > 0]

    # ---------- RAG 问答 ----------

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

        if book.parse_status != "completed":
            raise BadRequestException(
                message="书籍尚未解析完成，无法进行问答",
                detail={
                    "book_id": str(book_id),
                    "parse_status": book.parse_status or "pending",
                },
            )

        # 检索相关知识块（向量检索）
        scored_chunks = await self.retrieve_relevant_chunks(
            book_id, data.question, top_k=data.top_k
        )
        if not scored_chunks:
            return {
                "answer": "未在书中找到与问题相关的内容，请尝试更换关键词或确认书籍已解析完成。",
                "sources": [],
            }

        # 构建上下文
        context_text = "\n---\n".join(
            f"[片段 {i + 1}]（第 {c.chapter_order or '?'} 章，相似度 {s:.2f}）{c.content}"
            for i, (c, s) in enumerate(scored_chunks)
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
                    "chapter_order": c.chapter_order,
                    "content": c.content[:200],
                    "score": round(s, 4),
                    "metadata": c.chunk_metadata,
                }
                for c, s in scored_chunks
            ],
        }

    # ---------- AI 知识提取（Stage 7.5） ----------

    async def extract_knowledge(
        self,
        book_id: uuid.UUID,
        data: KnowledgeExtractionRequest,
    ) -> KnowledgeExtractionResponse:
        """从书籍章节中提取交易策略知识（6 部分策略草稿）。

        Args:
            book_id: 书籍 ID
            data: 提取请求（可指定章节序号）

        Returns:
            包含 6 部分策略草稿的响应

        Raises:
            NotFoundException: 书籍不存在
            BadRequestException: 书籍未解析完成或指定章节不存在
        """
        book = await self.get_book(book_id)
        if book is None:
            raise NotFoundException(
                message="书籍不存在", detail={"book_id": str(book_id)}
            )

        if book.parse_status != "completed":
            raise BadRequestException(
                message="书籍尚未解析完成，无法进行知识提取",
                detail={
                    "book_id": str(book_id),
                    "parse_status": book.parse_status or "pending",
                },
            )

        # 选择源章节
        if data.chapter_order is not None:
            chapter = await self.get_chapter(book_id, data.chapter_order)
            if chapter is None:
                raise BadRequestException(
                    message="指定章节不存在",
                    detail={"chapter_order": data.chapter_order},
                )
            source_text = chapter.content
            source_chapters = [data.chapter_order]
        else:
            # 全书：用向量检索获取与"交易策略"相关的内容
            scored = await self.retrieve_relevant_chunks(
                book_id,
                "交易策略 入场 出场 止损 仓位管理 风险控制",
                top_k=data.context_chunks,
            )
            if not scored:
                raise BadRequestException(
                    message="书中未找到与交易策略相关的内容",
                    detail={"book_id": str(book_id)},
                )
            source_text = "\n---\n".join(c.content for c, _ in scored)
            source_chapters = sorted({
                c.chapter_order for c, _ in scored if c.chapter_order
            })

        # 6 部分策略草稿 Prompt
        messages = [
            {
                "role": "system",
                "content": (
                    "你是一位资深交易策略分析师。请基于以下书籍内容提取交易策略知识，"
                    "并按照 6 个部分结构化输出（每部分使用标题前缀）：\n\n"
                    "【入场规则】明确具体的入场条件、信号、指标阈值等\n"
                    "【出场规则】明确止盈、平仓、退出信号\n"
                    "【仓位管理】明确资金分配、加仓减仓、风险敞口\n"
                    "【风控规则】明确止损、最大回撤、单笔风险\n"
                    "【适用场景】明确市场、品种、周期、波动环境\n"
                    "【备注】其他补充说明\n\n"
                    "请确保提取的策略忠实于原文，不要凭空臆造。"
                    "若原文未涉及某个部分，请填写\"原文未明确\"。\n\n"
                    f"书籍内容片段：\n{source_text[:8000]}"
                ),
            },
            {
                "role": "user",
                "content": "请基于以上内容提取交易策略知识。",
            },
        ]
        raw = await self.llm.chat(messages, temperature=0.3)

        # 解析 6 部分
        parts = self._parse_strategy_sections(raw)

        # 生成草稿策略 DSL（简化版）
        draft_strategy = self._build_draft_strategy_dsl(parts)

        return KnowledgeExtractionResponse(
            entry_rules=parts.get("入场规则", "原文未明确"),
            exit_rules=parts.get("出场规则", "原文未明确"),
            sizing=parts.get("仓位管理", "原文未明确"),
            risk_control=parts.get("风控规则", "原文未明确"),
            applicability=parts.get("适用场景", "原文未明确"),
            notes=parts.get("备注", "原文未明确"),
            draft_strategy=draft_strategy,
            source_chapters=source_chapters,
        )

    @staticmethod
    def _parse_strategy_sections(text: str) -> Dict[str, str]:
        """从 LLM 输出中解析 6 部分策略草稿。"""
        import re

        sections = {}
        # 匹配【xxx】标题及后续内容
        pattern = re.compile(
            r"【([^】]+)】\s*\n?(.*?)(?=【[^】]+】|$)",
            re.DOTALL,
        )
        for match in pattern.finditer(text):
            title = match.group(1).strip()
            content = match.group(2).strip()
            sections[title] = content
        return sections

    @staticmethod
    def _build_draft_strategy_dsl(
        parts: Dict[str, str]
    ) -> Optional[Dict[str, Any]]:
        """根据提取的 6 部分构建简化的策略 DSL 草稿。

        返回符合 StrategyDSL 基础结构的字典，便于用户保存为策略后微调。
        """
        if not parts:
            return None
        return {
            "name": "AI 提取策略草稿",
            "description": parts.get("适用场景", "从书籍中提取的策略草稿"),
            "symbol": "BTC/USDT",
            "timeframe": "1h",
            "entry_rules": [
                {
                    "logic": "AND",
                    "conditions": [
                        {
                            "indicator": "price",
                            "operator": "custom",
                            "value": parts.get("入场规则", ""),
                            "description": "由 AI 从书籍中提取的入场规则",
                        }
                    ],
                }
            ],
            "exit_rules": [
                {
                    "logic": "AND",
                    "conditions": [
                        {
                            "indicator": "price",
                            "operator": "custom",
                            "value": parts.get("出场规则", ""),
                            "description": "由 AI 从书籍中提取的出场规则",
                        }
                    ],
                }
            ],
            "position_sizing": {
                "method": "fixed_fraction",
                "fraction": 0.1,
                "description": parts.get("仓位管理", ""),
            },
            "risk_control": {
                "stop_loss_pct": 0.05,
                "take_profit_pct": 0.15,
                "max_drawdown_pct": 0.2,
                "description": parts.get("风控规则", ""),
            },
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
            chapter_order=data.chapter_order,
            note_type=data.note_type,
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

    async def update_note(
        self, note_id: uuid.UUID, data: BookNoteUpdate
    ) -> Optional[BookNote]:
        """更新笔记。"""
        note = await self.get_note(note_id)
        if note is None:
            return None
        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(note, key, value)
        await self.db.flush()
        return note

    async def delete_note(self, note_id: uuid.UUID) -> bool:
        """删除笔记。"""
        note = await self.get_note(note_id)
        if note is None:
            return False
        await self.db.delete(note)
        await self.db.flush()
        return True
