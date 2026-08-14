"""书籍内容解析任务（Stage 7.2，对齐 PRD §5.7.2）。

由 BookService.trigger_parse 派发，负责：
1. 读取上传的文件（pdf / epub / txt）
2. 提取纯文本 + 目录/章节结构（PyMuPDF 优先，PyPDF2 降级）
3. 按语义边界 + 固定长度切分知识块
4. 生成向量嵌入（若配置了 LLM API Key）
5. 写入 book_chapters 表 + knowledge_chunks 表
6. 更新 book.parse_status / parse_progress / total_chapters / total_chunks
"""

import asyncio
import json
import os
import re
import uuid
import zipfile
from typing import Any, Dict, List, Optional, Tuple

from loguru import logger

from app.tasks import celery_app

# 分块参数
CHUNK_SIZE = 1000  # 每块字符数
CHUNK_OVERLAP = 100  # 块之间的重叠字符数
EMBED_BATCH_SIZE = 16  # embedding 接口单次批量大小


# ---------- PDF 文本 + 章节提取 ----------

def _extract_pdf_with_fitz(file_path: str) -> Tuple[str, List[Dict[str, Any]]]:
    """使用 PyMuPDF (fitz) 提取 PDF 文本和目录。

    Returns:
        (full_text, chapters) — chapters 每项包含 title / page_start / page_end / content / level
    """
    import fitz  # PyMuPDF

    doc = fitz.open(file_path)
    total_pages = len(doc)

    # 提取目录（TOC）
    toc = doc.get_toc(simple=True)  # [[level, title, page], ...]

    # 提取每页文本
    page_texts: List[str] = []
    for i, page in enumerate(doc):
        try:
            text = page.get_text("text") or ""
        except Exception as e:
            logger.warning("PDF 第 {} 页提取失败: {}", i + 1, e)
            text = ""
        page_texts.append(text)

    doc.close()

    full_text = "\n\n".join(page_texts)

    # 构建章节
    chapters: List[Dict[str, Any]] = []
    if toc:
        for idx, (level, title, page_num) in enumerate(toc):
            page_start = page_num - 1  fitz 页码从 1 开始
            page_end = (toc[idx + 1][2] - 1) if idx + 1 < len(toc) else total_pages
            page_end = min(page_end, total_pages)
            content = "\n\n".join(page_texts[page_start:page_end])
            chapters.append({
                "title": title.strip(),
                "chapter_order": idx + 1,
                "page_start": page_start + 1,
                "page_end": page_end,
                "content": content,
                "char_count": len(content),
                "level": level,
            })
    else:
        # 无 TOC，按页码每 10 页一章
        pages_per_chapter = max(1, total_pages // 20)  # 目标 ~20 章
        ch_idx = 1
        for start in range(0, total_pages, pages_per_chapter):
            end = min(start + pages_per_chapter, total_pages)
            content = "\n\n".join(page_texts[start:end])
            title = f"第 {start + 1}-{end} 页"
            chapters.append({
                "title": title,
                "chapter_order": ch_idx,
                "page_start": start + 1,
                "page_end": end,
                "content": content,
                "char_count": len(content),
                "level": 1,
            })
            ch_idx += 1

    return full_text, chapters


def _extract_pdf_with_pypdf2(file_path: str) -> Tuple[str, List[Dict[str, Any]]]:
    """降级方案：使用 PyPDF2 提取 PDF 文本（无目录）。"""
    from PyPDF2 import PdfReader

    reader = PdfReader(file_path)
    total_pages = len(reader.pages)
    page_texts: List[str] = []
    for i, page in enumerate(reader.pages):
        try:
            text = page.extract_text() or ""
        except Exception as e:
            logger.warning("PDF 第 {} 页提取失败: {}", i + 1, e)
            text = ""
        page_texts.append(text)

    full_text = "\n\n".join(page_texts)

    # 按页码分章
    chapters: List[Dict[str, Any]] = []
    pages_per_chapter = max(1, total_pages // 20)
    ch_idx = 1
    for start in range(0, total_pages, pages_per_chapter):
        end = min(start + pages_per_chapter, total_pages)
        content = "\n\n".join(page_texts[start:end])
        chapters.append({
            "title": f"第 {start + 1}-{end} 页",
            "chapter_order": ch_idx,
            "page_start": start + 1,
            "page_end": end,
            "content": content,
            "char_count": len(content),
            "level": 1,
        })
        ch_idx += 1

    return full_text, chapters


def _extract_pdf(file_path: str) -> Tuple[str, List[Dict[str, Any]]]:
    """提取 PDF 文本和章节（PyMuPDF 优先，PyPDF2 降级）。"""
    try:
        return _extract_pdf_with_fitz(file_path)
    except ImportError:
        logger.info("PyMuPDF 未安装，降级使用 PyPDF2")
        return _extract_pdf_with_pypdf2(file_path)


# ---------- TXT / EPUB 提取 ----------

def _extract_txt(file_path: str) -> Tuple[str, List[Dict[str, Any]]]:
    """从 TXT 文件提取文本，按章节标题分章。"""
    for encoding in ("utf-8", "gbk", "latin-1"):
        try:
            with open(file_path, "r", encoding=encoding) as f:
                text = f.read()
            break
        except UnicodeDecodeError:
            continue
    else:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            text = f.read()

    # 尝试按章节标题分章（常见模式：第X章 / Chapter X）
    chapter_pattern = re.compile(
        r"^(第[一二三四五六七八九十百千零\d]+[章节回卷]|Chapter\s+\d+|CHAPTER\s+\d+).*$",
        re.MULTILINE,
    )
    matches = list(chapter_pattern.finditer(text))

    chapters: List[Dict[str, Any]] = []
    if matches:
        for idx, match in enumerate(matches):
            start = match.start()
            end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
            content = text[start:end].strip()
            title = match.group(0).strip()
            chapters.append({
                "title": title,
                "chapter_order": idx + 1,
                "page_start": None,
                "page_end": None,
                "content": content,
                "char_count": len(content),
                "level": 1,
            })
    else:
        # 无章节标题，按固定长度分章
        ch_size = 5000
        for idx, start in enumerate(range(0, len(text), ch_size)):
            content = text[start : start + ch_size]
            chapters.append({
                "title": f"段落 {idx + 1}",
                "chapter_order": idx + 1,
                "page_start": None,
                "page_end": None,
                "content": content,
                "char_count": len(content),
                "level": 1,
            })

    return text, chapters


def _strip_html(text: str) -> str:
    """简单去除 HTML 标签并还原常见实体。"""
    text = re.sub(r"<[^>]+>", "", text)
    text = text.replace("&nbsp;", " ").replace("&amp;", "&")
    text = text.replace("&lt;", "<").replace("&gt;", ">")
    return text


def _extract_epub(file_path: str) -> Tuple[str, List[Dict[str, Any]]]:
    """从 EPUB 文件提取文本和章节。"""
    chapters: List[Dict[str, Any]] = []
    all_texts: List[str] = []

    with zipfile.ZipFile(file_path, "r") as zf:
        html_files = sorted(
            [n for n in zf.namelist() if n.lower().endswith((".xhtml", ".html", ".htm"))]
        )
        for idx, name in enumerate(html_files):
            try:
                raw = zf.read(name).decode("utf-8", errors="ignore")
                text = _strip_html(raw).strip()
                if not text:
                    continue
                all_texts.append(text)
                chapters.append({
                    "title": f"章节 {idx + 1}",
                    "chapter_order": idx + 1,
                    "page_start": None,
                    "page_end": None,
                    "content": text,
                    "char_count": len(text),
                    "level": 1,
                })
            except Exception as e:
                logger.warning("EPUB 解析文件 {} 失败: {}", name, e)

    return "\n\n".join(all_texts), chapters


def extract_text_and_chapters(
    file_path: str, file_type: str
) -> Tuple[str, List[Dict[str, Any]]]:
    """根据文件类型提取文本和章节结构。"""
    ft = (file_type or "").lower()
    if ft == "pdf":
        return _extract_pdf(file_path)
    if ft == "txt":
        return _extract_txt(file_path)
    if ft == "epub":
        return _extract_epub(file_path)
    return _extract_txt(file_path)


# ---------- 分块 ----------

def split_into_chunks(
    text: str,
    chapter_order: Optional[int] = None,
    chunk_size: int = CHUNK_SIZE,
    overlap: int = CHUNK_OVERLAP,
) -> List[Dict[str, Any]]:
    """将文本切分为带元数据的块。"""
    if not text:
        return []

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
            chunks.append({
                "content": piece,
                "chapter_order": chapter_order,
                "metadata": {
                    "chunk_index": idx,
                    "char_start": start,
                    "char_end": end,
                    "chapter_order": chapter_order,
                },
            })
            idx += 1
        if end >= total:
            break
        start += step
    return chunks


# ---------- 向量嵌入 ----------

async def _generate_embeddings(chunks: List[Dict[str, Any]]) -> None:
    """为 chunks 生成向量嵌入（原地写入 embedding 字段）。"""
    from app.services.llm_provider import get_llm_provider
    from app.core.config import settings

    if not settings.LLM_API_KEY:
        logger.info("未配置 LLM_API_KEY，跳过向量嵌入生成")
        return

    provider = get_llm_provider()
    texts = [c["content"] for c in chunks]
    for i in range(0, len(texts), EMBED_BATCH_SIZE):
        batch = texts[i : i + EMBED_BATCH_SIZE]
        try:
            vectors = await provider.embed(batch)
            for j, vec in enumerate(vectors):
                chunks[i + j]["embedding"] = json.dumps(vec)
        except Exception as e:
            logger.warning("Embedding 生成失败（batch {}）: {}", i, e)


# ---------- 异步解析主流程 ----------

async def _parse_book_async(book_id: str) -> dict:
    """异步执行书籍解析。"""
    from sqlalchemy import select, delete

    from app.core.database import async_session_maker, redis_client
    from app.models.book import Book, BookChapter, KnowledgeChunk
    from app.services.book_service import BookService

    book_uuid = uuid.UUID(book_id)
    async with async_session_maker() as session:
        result = await session.execute(select(Book).where(Book.id == book_uuid))
        book = result.scalar_one_or_none()
        if book is None:
            logger.error("书籍不存在: {}", book_id)
            return {"book_id": book_id, "status": "failed", "reason": "book_not_found"}

        if not book.file_path or not os.path.exists(book.file_path):
            service = BookService(session)
            await service.update_parse_status(book_uuid, "failed")
            await session.commit()
            return {"book_id": book_id, "status": "failed", "reason": "file_not_found"}

        try:
            # 发布进度辅助
            async def publish_progress(stage: str, progress: int, message: str = ""):
                book.parse_progress = progress
                await session.flush()
                if redis_client:
                    try:
                        import datetime as _dt
                        payload = json.dumps({
                            "book_id": book_id, "stage": stage, "progress": progress,
                            "message": message,
                            "timestamp": _dt.datetime.now(_dt.timezone.utc).isoformat(),
                        }, ensure_ascii=False)
                        await redis_client.publish(f"book:progress:{book_id}", payload)
                    except Exception:
                        pass

            # 1. 提取文本 + 章节
            await publish_progress("extracting", 10, "提取文本和章节")
            full_text, chapters = extract_text_and_chapters(
                book.file_path, book.file_type or ""
            )
            logger.info(
                "书籍提取完成 | book_id={} 字符数={} 章节数={}",
                book_id, len(full_text), len(chapters),
            )

            # 2. 清除旧章节和知识块
            await session.execute(delete(BookChapter).where(BookChapter.book_id == book_uuid))
            await session.execute(delete(KnowledgeChunk).where(KnowledgeChunk.book_id == book_uuid))

            # 3. 保存章节
            await publish_progress("chapters", 30, f"保存 {len(chapters)} 个章节")
            for ch in chapters:
                chapter = BookChapter(
                    book_id=book_uuid,
                    title=ch["title"],
                    chapter_order=ch["chapter_order"],
                    content=ch["content"],
                    page_start=ch.get("page_start"),
                    page_end=ch.get("page_end"),
                    char_count=ch.get("char_count", len(ch["content"])),
                    level=ch.get("level", 1),
                )
                session.add(chapter)

            book.total_chapters = len(chapters)
            await session.flush()

            # 4. 按章节分块
            await publish_progress("chunking", 50, "切分知识块")
            all_chunks: List[Dict[str, Any]] = []
            for ch in chapters:
                ch_chunks = split_into_chunks(
                    ch["content"], chapter_order=ch["chapter_order"]
                )
                all_chunks.extend(ch_chunks)

            logger.info("切分为 {} 个知识块 | book_id={}", len(all_chunks), book_id)

            # 5. 生成嵌入
            await publish_progress("embedding", 70, "生成向量嵌入")
            await _generate_embeddings(all_chunks)

            # 6. 保存知识块
            await publish_progress("saving", 85, "保存知识块")
            service = BookService(session)
            saved = await service.save_chunks(book_uuid, all_chunks)
            book.total_chunks = saved

            # 7. 完成
            book.parse_status = "completed"
            book.parse_progress = 100
            await session.commit()

            await publish_progress("done", 100, f"解析完成：{len(chapters)} 章 / {saved} 块")
            logger.info("书籍解析完成 | book_id={} chapters={} chunks={}", book_id, len(chapters), saved)
            return {"book_id": book_id, "status": "completed", "chapters": len(chapters), "chunks": saved}

        except Exception as e:
            logger.exception("书籍解析失败 | book_id={}", book_id)
            book.parse_status = "failed"
            await session.commit()
            return {"book_id": book_id, "status": "failed", "reason": str(e)}


@celery_app.task(name="parse_book", bind=True)
def parse_book(self, book_id: str) -> dict:
    """解析书籍内容并提取章节和知识块。

    Args:
        book_id: 书籍 ID（字符串形式的 UUID）

    Returns:
        解析结果字典
    """
    logger.info("开始解析书籍 | book_id={} task_id={}", book_id, self.request.id)
    return asyncio.run(_parse_book_async(book_id))
