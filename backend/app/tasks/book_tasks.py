"""书籍内容解析任务。

由 BookService.trigger_parse 派发，负责：
1. 读取上传的文件（pdf / epub / txt）
2. 提取纯文本
3. 按固定长度切分为知识块
4. 生成向量嵌入（若配置了 LLM API Key）
5. 写入 knowledge_chunks 表
6. 更新 book.parse_status
"""

import asyncio
import json
import os
import re
import uuid
import zipfile
from typing import Any, Dict, List

from loguru import logger

from app.tasks import celery_app

# 分块参数
CHUNK_SIZE = 1000  # 每块字符数
CHUNK_OVERLAP = 100  # 块之间的重叠字符数
EMBED_BATCH_SIZE = 16  # embedding 接口单次批量大小


def _extract_pdf_text(file_path: str) -> str:
    """从 PDF 文件提取文本。"""
    from PyPDF2 import PdfReader

    reader = PdfReader(file_path)
    texts: List[str] = []
    for i, page in enumerate(reader.pages):
        try:
            text = page.extract_text() or ""
        except Exception as e:
            logger.warning("PDF 第 {} 页提取失败: {}", i + 1, e)
            text = ""
        texts.append(text)
    return "\n\n".join(texts)


def _extract_txt_text(file_path: str) -> str:
    """从 TXT 文件提取文本。"""
    # 尝试多种编码
    for encoding in ("utf-8", "gbk", "latin-1"):
        try:
            with open(file_path, "r", encoding=encoding) as f:
                return f.read()
        except UnicodeDecodeError:
            continue
    # 兜底
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        return f.read()


def _strip_html(text: str) -> str:
    """简单去除 HTML 标签并还原常见实体。"""
    text = re.sub(r"<[^>]+>", "", text)
    text = text.replace("&nbsp;", " ").replace("&amp;", "&")
    text = text.replace("&lt;", "<").replace("&gt;", ">")
    return text


def _extract_epub_text(file_path: str) -> str:
    """从 EPUB 文件提取文本。

    EPUB 本质是 zip 包，内部包含 XHTML 文件。
    这里采用简化方案：遍历所有 .xhtml/.html/.htm 文件并去除标签。
    """
    texts: List[str] = []
    with zipfile.ZipFile(file_path, "r") as zf:
        for name in zf.namelist():
            if name.lower().endswith((".xhtml", ".html", ".htm")):
                try:
                    raw = zf.read(name).decode("utf-8", errors="ignore")
                    texts.append(_strip_html(raw))
                except Exception as e:
                    logger.warning("EPUB 解析文件 {} 失败: {}", name, e)
    return "\n\n".join(texts)


def extract_text(file_path: str, file_type: str) -> str:
    """根据文件类型提取纯文本。"""
    ft = (file_type or "").lower()
    if ft == "pdf":
        return _extract_pdf_text(file_path)
    if ft == "txt":
        return _extract_txt_text(file_path)
    if ft == "epub":
        return _extract_epub_text(file_path)
    # 默认按文本读取
    return _extract_txt_text(file_path)


def split_into_chunks(
    text: str,
    chunk_size: int = CHUNK_SIZE,
    overlap: int = CHUNK_OVERLAP,
) -> List[Dict[str, Any]]:
    """将文本切分为带页码占位的块。

    Returns:
        列表，每项 {"content": str, "metadata": {"char_start": int}}
    """
    if not text:
        return []

    # 规范化空白
    text = re.sub(r"\r\n", "\n", text)
    text = re.sub(r"[ \t]+", " ", text)

    chunks: List[Dict[str, Any]] = []
    start = 0
    step = max(1, chunk_size - overlap)
    total = len(text)
    idx = 0
    while start < total:
        end = min(start + chunk_size, total)
        piece = text[start:end].strip()
        if piece:
            chunks.append(
                {
                    "content": piece,
                    "metadata": {
                        "chunk_index": idx,
                        "char_start": start,
                        "char_end": end,
                    },
                }
            )
            idx += 1
        if end >= total:
            break
        start += step
    return chunks


async def _generate_embeddings(
    chunks: List[Dict[str, Any]],
) -> None:
    """为 chunks 生成向量嵌入（原地写入 embedding 字段）。

    若未配置 LLM_API_KEY，则跳过嵌入生成（保留为 None）。
    """
    from app.services.llm_provider import get_llm_provider

    provider = get_llm_provider()
    # 检测是否为降级模式（无 API Key）
    from app.core.config import settings

    if not settings.LLM_API_KEY:
        logger.info("未配置 LLM_API_KEY，跳过向量嵌入生成")
        return

    texts = [c["content"] for c in chunks]
    for i in range(0, len(texts), EMBED_BATCH_SIZE):
        batch = texts[i : i + EMBED_BATCH_SIZE]
        try:
            vectors = await provider.embed(batch)
            for j, vec in enumerate(vectors):
                chunks[i + j]["embedding"] = json.dumps(vec)
        except Exception as e:
            logger.warning("Embedding 生成失败（batch {}）: {}", i, e)


async def _parse_book_async(book_id: str) -> dict:
    """异步执行书籍解析。"""
    from sqlalchemy import select

    from app.core.database import async_session_maker
    from app.models.book import Book
    from app.services.book_service import BookService

    book_uuid = uuid.UUID(book_id)
    async with async_session_maker() as session:
        result = await session.execute(
            select(Book).where(Book.id == book_uuid)
        )
        book = result.scalar_one_or_none()
        if book is None:
            logger.error("书籍不存在: {}", book_id)
            return {"book_id": book_id, "status": "failed", "reason": "book_not_found"}

        if not book.file_path or not os.path.exists(book.file_path):
            service = BookService(session)
            await service.update_parse_status(book_uuid, "failed")
            await session.commit()
            return {
                "book_id": book_id,
                "status": "failed",
                "reason": "file_not_found",
            }

        try:
            # 1. 提取文本
            text = extract_text(book.file_path, book.file_type or "")
            logger.info(
                "书籍文本提取完成 | book_id={} 字符数={}",
                book_id,
                len(text),
            )

            # 2. 切分块
            chunks = split_into_chunks(text)
            logger.info("切分为 {} 个知识块 | book_id={}", len(chunks), book_id)

            # 3. 生成嵌入
            await _generate_embeddings(chunks)

            # 4. 保存知识块
            service = BookService(session)
            saved = await service.save_chunks(book_uuid, chunks)
            await service.update_parse_status(book_uuid, "completed")
            await session.commit()

            logger.info(
                "书籍解析完成 | book_id={} chunks={}", book_id, saved
            )
            return {
                "book_id": book_id,
                "status": "completed",
                "chunks": saved,
            }
        except Exception as e:
            logger.exception("书籍解析失败 | book_id={}", book_id)
            service = BookService(session)
            await service.update_parse_status(book_uuid, "failed")
            await session.commit()
            return {"book_id": book_id, "status": "failed", "reason": str(e)}


@celery_app.task(name="parse_book", bind=True)
def parse_book(self, book_id: str) -> dict:
    """解析书籍内容并提取知识块。

    Args:
        book_id: 书籍 ID（字符串形式的 UUID）

    Returns:
        解析结果字典
    """
    logger.info("开始解析书籍 | book_id={} task_id={}", book_id, self.request.id)
    return asyncio.run(_parse_book_async(book_id))
