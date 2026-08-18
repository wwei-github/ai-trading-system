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

# OCR 阈值：当平均每页文本少于该值时视为扫描版 PDF，启用 OCR
OCR_TEXT_THRESHOLD = 50  # 每页平均字符数


def _ocr_page(page: Any, dpi: int = 200) -> str:
    """对 PDF 页面执行 OCR 识别。

    使用 Tesseract 识别中文（chi_sim）和英文（eng）混合文本。
    """
    import pytesseract
    from PIL import Image
    import io

    pix = page.get_pixmap(dpi=dpi)
    img = Image.open(io.BytesIO(pix.tobytes("png")))
    text = pytesseract.image_to_string(img, lang="chi_sim+eng")
    return text.strip()


def _extract_pdf_with_fitz(
    file_path: str,
    progress_callback: Optional[Any] = None,
) -> Tuple[str, List[Dict[str, Any]]]:
    """使用 PyMuPDF (fitz) 提取 PDF 文本和目录。

    自动检测扫描版 PDF 并降级到 OCR 识别。

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

    # 检测是否为扫描版 PDF（文本提取很少或为空）
    total_chars = sum(len(t) for t in page_texts)
    avg_chars_per_page = total_chars / max(total_pages, 1)
    is_scanned = avg_chars_per_page < OCR_TEXT_THRESHOLD

    if is_scanned:
        logger.info(
            "检测为扫描版 PDF（{} 页，平均每页 {} 字符），启用 OCR 识别...",
            total_pages,
            round(avg_chars_per_page, 1),
        )
        ocr_texts: List[str] = []
        for i in range(total_pages):
            try:
                text = _ocr_page(doc[i])
            except Exception as e:
                logger.warning("OCR 第 {} 页识别失败: {}", i + 1, e)
                text = ""
            ocr_texts.append(text)
            if (i + 1) % 20 == 0 or i == total_pages - 1:
                pct = int((i + 1) / total_pages * 100)
                logger.info(
                    "OCR 进度: {}/{} 页 ({:.0f}%)",
                    i + 1,
                    total_pages,
                    (i + 1) / total_pages * 100,
                )
                if progress_callback:
                    progress_callback(10, min(10 + pct // 9, 90), f"OCR 识别中（第 {i+1}/{total_pages} 页）")
        page_texts = ocr_texts

    doc.close()

    full_text = "\n\n".join(page_texts)

    # 构建章节
    chapters: List[Dict[str, Any]] = []
    if toc:
        # 合并相同页面的连续条目（父标题和子标题同页时，保留父标题）
        merged_toc = []
        for entry in toc:
            if merged_toc and entry[2] == merged_toc[-1][2]:
                # 同页条目：保留前一个（父标题），跳过当前（子标题）
                continue
            merged_toc.append(entry)

        for idx, (level, title, page_num) in enumerate(merged_toc):
            page_start = page_num - 1  # fitz 页码从 1 开始
            page_end = (merged_toc[idx + 1][2] - 1) if idx + 1 < len(merged_toc) else total_pages
            page_end = min(page_end, total_pages)
            if page_start >= page_end:
                continue
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


def _extract_pdf_with_pypdf2(
    file_path: str,
    progress_callback: Optional[Any] = None,
) -> Tuple[str, List[Dict[str, Any]]]:
    """降级方案：使用 PyPDF2 提取 PDF 文本（无目录），支持扫描版 OCR 降级。"""
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

    # 检测是否为扫描版 PDF
    total_chars = sum(len(t) for t in page_texts)
    avg_chars_per_page = total_chars / max(total_pages, 1)
    is_scanned = avg_chars_per_page < OCR_TEXT_THRESHOLD

    if is_scanned:
        logger.info(
            "检测为扫描版 PDF（PyPDF2，{} 页），启用 OCR 识别...",
            total_pages,
        )
        from pdf2image import convert_from_path
        import pytesseract

        images = convert_from_path(file_path, dpi=200)
        ocr_texts: List[str] = []
        for i, img in enumerate(images):
            try:
                text = pytesseract.image_to_string(img, lang="chi_sim+eng")
            except Exception as e:
                logger.warning("OCR 第 {} 页识别失败: {}", i + 1, e)
                text = ""
            ocr_texts.append(text.strip())
            if (i + 1) % 20 == 0 or i == total_pages - 1:
                pct = int((i + 1) / total_pages * 100)
                logger.info(
                    "OCR 进度: {}/{} 页 ({:.0f}%)",
                    i + 1,
                    total_pages,
                    (i + 1) / total_pages * 100,
                )
                if progress_callback:
                    progress_callback(10, min(10 + pct // 9, 90), f"OCR 识别中（第 {i+1}/{total_pages} 页）")
        page_texts = ocr_texts

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


def _extract_pdf(
    file_path: str,
    progress_callback: Optional[Any] = None,
) -> Tuple[str, List[Dict[str, Any]]]:
    """提取 PDF 文本和章节（PyMuPDF 优先，PyPDF2 降级）。"""
    try:
        return _extract_pdf_with_fitz(file_path, progress_callback)
    except ImportError:
        logger.info("PyMuPDF 未安装，降级使用 PyPDF2")
        return _extract_pdf_with_pypdf2(file_path, progress_callback)


# ---------- TXT / EPUB 提取 ----------

def _extract_txt(file_path: str) -> Tuple[str, List[Dict[str, Any]]]:
    """从 TXT 文件提取文本，按章节标题分章。"""
    text = ""
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


def _epub_parse_ncx(ncx_content: str) -> List[Dict[str, Any]]:
    """解析 EPUB NCX 目录文件（toc.ncx），提取章节层级结构。

    NCX 格式包含 <navMap> / <navPoint> 层级结构，
    每个 navPoint 有 playOrder（序号）、text（标题）、content（src 文件引用）。

    Returns:
        [{"order": 1, "title": "第一章", "src": "chapter1.xhtml", "level": 1}, ...]
    """
    import xml.etree.ElementTree as ET

    entries: List[Dict[str, Any]] = []

    try:
        root = ET.fromstring(ncx_content)
        # NCX 命名空间通常是 urn:oasis:names:tc:opendocument:xmlns:ns:epub+package
        ns = {"ncx": "urn:oasis:names:tc:opendocument:xmlns:ns:epub+package"}

        def _parse_nav_points(parent, level: int = 1):
            for np in parent.findall("ncx:navPoint", ns):
                order = np.get("playOrder")
                label = np.find("ncx:navLabel/ncx:text", ns)
                content = np.find("ncx:content", ns)
                src = content.get("src") if content is not None else ""
                title = label.text.strip() if label is not None and label.text else ""
                if title:
                    entries.append({
                        "order": int(order) if order else len(entries) + 1,
                        "title": title,
                        "src": src,
                        "level": level,
                    })
                # 递归子章节
                sub = np.find("ncx:navPoint", ns)
                if sub is not None:
                    # 查找所有子 navPoint
                    for child in np.findall("ncx:navPoint", ns):
                        _parse_nav_points(child, level + 1)
                # 遍历兄弟节点
                for sibling in np.findall("ncx:navPoint", ns):
                    if sibling is not np:
                        _parse_nav_points(sibling, level)

        # 兼容不同命名空间和结构
        body = root.find(".//ncx:navMap/ncx:navPoint", ns)
        if body is not None:
            for np in root.findall(".//ncx:navMap/ncx:navPoint", ns):
                _parse_nav_points(np)
        # 如果命名空间不匹配，尝试无命名空间解析
        if not entries:
            for np in root.findall(".//navMap/navPoint"):
                order = np.get("playOrder")
                label = np.find("navLabel/text")
                content = np.find("content")
                src = content.get("src") if content is not None else ""
                title = label.text.strip() if label is not None and label.text else ""
                if title:
                    entries.append({
                        "order": int(order) if order else len(entries) + 1,
                        "title": title,
                        "src": src,
                        "level": 1,
                    })
    except Exception as e:
        logger.warning("EPUB NCX 解析失败: {}", e)

    return entries


def _epub_parse_nav(nav_html: str) -> List[Dict[str, Any]]:
    """解析 EPUB Nav 文件（nav.xhtml），提取章节层级结构。

    HTML5 Nav 格式使用 <nav epub:type="toc"> 包含 <ol>/<li>/<a> 结构。

    Returns:
        [{"order": 1, "title": "第一章", "src": "chapter1.xhtml", "level": 1}, ...]
    """
    entries: List[Dict[str, Any]] = []
    try:
        import xml.etree.ElementTree as ET

        root = ET.fromstring(nav_html)
        # 查找 nav[epub:type="toc"] 或 nav 元素
        ns = {
            "xhtml": "http://www.w3.org/1999/xhtml",
            "epub": "http://www.idpf.org/2007/ops",
        }
        nav = root.find(".//xhtml:nav[@epub:type='toc']", ns)
        if nav is None:
            nav = root.find(".//nav[@epub:type='toc']", ns)
        if nav is None:
            nav = root.find(".//xhtml:nav", ns)
        if nav is None:
            nav = root.find(".//nav", ns)
        if nav is None:
            return entries

        order = [0]  # 可变计数器

        def _parse_list_items(parent, level: int = 1):
            for li in parent.findall(".//xhtml:li", ns) if "{http://www.w3.org/1999/xhtml}li" in [  # 尝试 xhtml ns
                c.tag for c in parent
            ] else parent.findall("li"):
                a = li.find("xhtml:a", ns) if "{http://www.w3.org/1999/xhtml}a" in ''.join(
                    [c.tag for c in li]
                ) else li.find("a")
                if a is None:
                    # 尝试无命名空间
                    a = li.find("{http://www.w3.org/1999/xhtml}a") or li.find("a")
                title = a.text.strip() if a is not None and a.text else ""
                href = a.get("href", "") if a is not None else ""
                if title:
                    order[0] += 1
                    entries.append({
                        "order": order[0],
                        "title": title,
                        "src": href.split("#")[0],  # 去掉锚点
                        "level": level,
                    })
                # 子列表
                sub_ol = None
                for tag in ("ol", "ul"):
                    sub_ol = li.find(f"xhtml:{tag}", ns) or li.find(tag) or li.find(f"{{{ns['xhtml']}}}{tag}")
                    if sub_ol is not None:
                        break
                if sub_ol is not None:
                    for sub_li in sub_ol.findall("xhtml:li", ns) if "{http://www.w3.org/1999/xhtml}li" in [
                        c.tag for c in sub_ol
                    ] else sub_ol.findall("li"):
                        _parse_list_items(sub_li, level + 1)

        ol = nav.find("xhtml:ol", ns) or nav.find("ol")
        if ol is not None:
            _parse_list_items(ol)

        # 如果无命名空间解析失败，尝试纯 HTML 解析（re 方式）
        if not entries:
            import re as _re
            pattern = _re.compile(r'<a\s+href="([^"]+)"[^>]*>([^<]+)</a>', _re.IGNORECASE)
            for match in pattern.finditer(nav_html):
                href, title = match.group(1), match.group(2).strip()
                if title and href:
                    order[0] += 1
                    entries.append({
                        "order": order[0],
                        "title": title,
                        "src": href.split("#")[0],
                        "level": 1,
                    })
    except Exception as e:
        logger.warning("EPUB Nav 解析失败: {}", e)

    return entries


def _extract_epub(file_path: str) -> Tuple[str, List[Dict[str, Any]]]:
    """从 EPUB 文件提取文本和章节（支持标准 TOC 目录导航）。

    改进：
    1. 优先解析 toc.ncx 或 nav.xhtml 获取真实目录结构
    2. 按目录层级映射到 HTML 文件内容
    3. 保留章节层级（level 1/2/3）供前端树形展示
    4. 降级：无 TOC 时按文件名排序
    """
    chapters: List[Dict[str, Any]] = []
    all_texts: List[str] = []
    html_contents: Dict[str, str] = {}  # filename -> text
    html_order: Dict[str, int] = {}  # filename -> display order

    with zipfile.ZipFile(file_path, "r") as zf:
        # 读取所有 HTML 文件内容
        html_files = sorted(
            [n for n in zf.namelist() if n.lower().endswith((".xhtml", ".html", ".htm"))]
        )
        for idx, name in enumerate(html_files):
            try:
                raw = zf.read(name).decode("utf-8", errors="ignore")
                text = _strip_html(raw).strip()
                if not text:
                    continue
                # 从文件名中提取标题（去掉路径和扩展名）
                basename = name.split("/")[-1]
                html_contents[name] = text
                html_order[name] = idx
                all_texts.append(text)
            except Exception as e:
                logger.warning("EPUB 解析文件 {} 失败: {}", name, e)

        # 尝试解析 TOC（NCX 优先，Nav 次之）
        toc_entries: List[Dict[str, Any]] = []

        # 查找 NCX 文件
        for n in zf.namelist():
            if n.lower().endswith(".ncx") or "toc.ncx" in n.lower():
                try:
                    ncx_raw = zf.read(n).decode("utf-8", errors="ignore")
                    toc_entries = _epub_parse_ncx(ncx_raw)
                    if toc_entries:
                        logger.info("EPUB NCX 目录解析成功: {} 条目", len(toc_entries))
                        break
                except Exception as e:
                    logger.warning("EPUB NCX 读取失败 {}: {}", n, e)

        # 未找到 NCX，尝试 Nav
        if not toc_entries:
            for n in zf.namelist():
                if "nav" in n.lower() and n.lower().endswith((".xhtml", ".html")):
                    try:
                        nav_raw = zf.read(n).decode("utf-8", errors="ignore")
                        toc_entries = _epub_parse_nav(nav_raw)
                        if toc_entries:
                            logger.info("EPUB Nav 目录解析成功: {} 条目", len(toc_entries))
                            break
                    except Exception as e:
                        logger.warning("EPUB Nav 读取失败 {}: {}", n, e)

        # 使用 TOC 构建章节
        if toc_entries and html_contents:
            # 建立 src -> content 的映射
            src_content: Dict[str, str] = {}
            for entry in toc_entries:
                src = entry["src"]
                # 匹配 HTML 文件（支持部分路径匹配）
                matched = False
                for hname, htext in html_contents.items():
                    if hname.endswith(src) or src in hname or hname == src:
                        src_content[src] = htext
                        matched = True
                        break
                if not matched:
                    src_content[src] = ""

            # 按 TOC 顺序构建章节
            for entry in toc_entries:
                src = entry["src"]
                content = src_content.get(src, "")
                if not content:
                    continue
                chapters.append({
                    "title": entry["title"],
                    "chapter_order": entry["order"],
                    "page_start": None,
                    "page_end": None,
                    "content": content,
                    "char_count": len(content),
                    "level": entry.get("level", 1),
                })
        else:
            # 降级：按文件名排序
            logger.info("EPUB 无有效 TOC，使用文件名排序降级方案")
            for idx, (name, text) in enumerate(sorted(html_contents.items(), key=lambda x: html_order.get(x[0], 0))):
                chapters.append({
                    "title": f"章节 {idx + 1}",
                    "chapter_order": idx + 1,
                    "page_start": None,
                    "page_end": None,
                    "content": text,
                    "char_count": len(text),
                    "level": 1,
                })

    return "\n\n".join(all_texts), chapters


def extract_text_and_chapters(
    file_path: str, file_type: str,
    progress_callback: Optional[Any] = None,
) -> Tuple[str, List[Dict[str, Any]]]:
    """根据文件类型提取文本和章节结构。"""
    ft = (file_type or "").lower()
    if ft == "pdf":
        return _extract_pdf(file_path, progress_callback)
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

async def _generate_embeddings(
    chunks: List[Dict[str, Any]],
    db_session,
) -> None:
    """为 chunks 生成向量嵌入（原地写入 embedding 字段）。"""
    from app.services.provider_factory import ProviderFactory

    if not chunks:
        return

    try:
        provider = await ProviderFactory.get_active_provider(db_session)
        texts = [c["content"] for c in chunks]
        success_count = 0
        for i in range(0, len(texts), EMBED_BATCH_SIZE):
            batch = texts[i : i + EMBED_BATCH_SIZE]
            try:
                vectors = await provider.embed(batch)
                for j, vec in enumerate(vectors):
                    chunks[i + j]["embedding"] = json.dumps(vec)
                success_count += len(vectors)
            except Exception as e:
                logger.warning("Embedding 生成失败（batch {}）: {}", i, e)
        logger.info("向量嵌入生成完成: {} / {} 块成功", success_count, len(texts))
    except Exception as e:
        logger.warning("获取 LLM Provider 失败，跳过向量嵌入生成: {}", e)


# ---------- 异步解析主流程 ----------

async def _parse_book_async(book_id: str) -> dict:
    """异步执行书籍解析。

    注意：为避免 Celery 事件循环冲突，在函数内部动态创建 engine 和 session maker，
    确保与当前 asyncio 事件循环一致。
    """
    from sqlalchemy import select, delete
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

    from app.core.config import settings
    from app.core.database import redis_client
    from app.models.book import Book, BookChapter, KnowledgeChunk
    from app.services.book_service import BookService

    # 动态创建 engine（确保与当前事件循环一致）
    database_url = settings.effective_database_url()
    engine = create_async_engine(
        database_url,
        echo=settings.DEBUG,
        pool_pre_ping=True,
        pool_size=1,
        max_overflow=0,
    )
    session_maker = async_sessionmaker(
        engine, expire_on_commit=False, autoflush=False
    )

    book_uuid = uuid.UUID(book_id)
    async with session_maker() as session:
        result = await session.execute(select(Book).where(Book.id == book_uuid))
        book = result.scalar_one_or_none()
        if book is None:
            logger.error("书籍不存在: {}", book_id)
            return {"book_id": book_id, "status": "failed", "reason": "book_not_found"}

        # 使用绝对路径
        if not book.file_path:
            service = BookService(session)
            await service.update_parse_status(book_uuid, "failed")
            await session.commit()
            return {"book_id": book_id, "status": "failed", "reason": "file_not_found"}
        
        # 如果是相对路径，基于当前工作目录转为绝对路径
        if not os.path.isabs(book.file_path):
            abs_path = os.path.join(os.getcwd(), book.file_path)
        else:
            abs_path = book.file_path
        
        if not os.path.exists(abs_path):
            logger.error("文件不存在: {}", abs_path)
            service = BookService(session)
            await service.update_parse_status(book_uuid, "failed")
            await session.commit()
            return {"book_id": book_id, "status": "failed", "reason": f"file_not_found: {abs_path}"}

        try:
            # 更新阶段辅助函数
            async def update_parse_stage(
                stage: str, progress: int, description: str
            ) -> None:
                book.parse_stage = stage
                book.parse_progress = progress
                book.parse_stage_progress = progress
                book.parse_stage_description = description
                await session.flush()
                if redis_client:
                    try:
                        import datetime as _dt
                        payload = json.dumps({
                            "book_id": book_id,
                            "status": book.parse_status,
                            "progress": progress,
                            "stage": stage,
                            "stage_progress": progress,
                            "stage_description": description,
                            "total_chapters": book.total_chapters,
                            "total_chunks": book.total_chunks,
                            "parsed_chapters": book.parsed_chapters,
                            "parsed_chunks": book.parsed_chunks,
                            "timestamp": _dt.datetime.now(_dt.timezone.utc).isoformat(),
                        }, ensure_ascii=False)
                        # 同时写入 Redis 缓存（供轮询端点读取）和 Pub/Sub 通道（供 SSE 推送）
                        await redis_client.set(
                            f"book:parse:progress:{book_id}",
                            payload,
                            ex=3600,  # 1 小时过期
                        )
                        await redis_client.publish(f"book:parse:progress:{book_id}", payload)
                    except Exception:
                        pass

            # 阶段 1: 文件解析
            await update_parse_stage("file_parsing", 10, "正在解析文件格式")

            # 创建同步进度回调（在 OCR 循环中实时更新数据库进度）
            def _ocr_progress_callback(stage_progress: int, overall_progress: int, desc: str) -> None:
                """同步的 OCR 进度回调，通过 Redis 发布进度更新。"""
                try:
                    import redis as sync_redis
                    from app.core.config import settings as _settings
                    import datetime as _dt
                    r = sync_redis.from_url(_settings.REDIS_URL)
                    payload = json.dumps({
                        "book_id": book_id,
                        "status": "parsing",
                        "progress": overall_progress,
                        "stage": "file_parsing",
                        "stage_progress": stage_progress,
                        "stage_description": desc,
                        "total_chapters": 0,
                        "total_chunks": 0,
                        "parsed_chapters": 0,
                        "parsed_chunks": 0,
                        "timestamp": _dt.datetime.now(_dt.timezone.utc).isoformat(),
                    }, ensure_ascii=False)
                    r.publish(f"book:parse:progress:{book_id}", payload)
                    r.set(f"book:parse:progress:{book_id}", payload, ex=3600)
                    r.close()
                except Exception:
                    pass

            full_text, chapters = extract_text_and_chapters(
                abs_path, book.file_type or "",
                progress_callback=_ocr_progress_callback,
            )
            logger.info("提取完成 | full_text_len={} chapters={}", len(full_text), len(chapters))
            if chapters:
                logger.info("首章 | title={} content_len={}", chapters[0]["title"], len(chapters[0].get("content", "") or ""))
            logger.info(
                "书籍提取完成 | book_id={} 字符数={} 章节数={}",
                book_id, len(full_text), len(chapters),
            )

            # 阶段 2: 清除旧数据并保存章节
            await update_parse_stage("chunking", 20, "正在提取章节结构")
            await session.execute(delete(BookChapter).where(BookChapter.book_id == book_uuid))
            await session.execute(delete(KnowledgeChunk).where(KnowledgeChunk.book_id == book_uuid))

            for ch in chapters:
                ch_content = ch["content"] or ""
                logger.debug("保存章节 | title={} content_len={}", ch["title"], len(ch_content))
                chapter = BookChapter(
                    book_id=book_uuid,
                    title=ch["title"],
                    chapter_order=ch["chapter_order"],
                    content=ch_content,
                    page_start=ch.get("page_start"),
                    page_end=ch.get("page_end"),
                    char_count=ch.get("char_count", len(ch_content)),
                    level=ch.get("level", 1),
                )
                session.add(chapter)

            book.total_chapters = len(chapters)
            book.parsed_chapters = len(chapters)
            await session.flush()

            # 阶段 3: 分块处理
            await update_parse_stage(
                "embedding", 50,
                f"正在分块处理（第 {len(chapters)}/{len(chapters)} 章）"
            )
            all_chunks: List[Dict[str, Any]] = []
            for idx, ch in enumerate(chapters):
                ch_chunks = split_into_chunks(
                    ch["content"], chapter_order=ch["chapter_order"]
                )
                all_chunks.extend(ch_chunks)
                book.parsed_chunks = len(all_chunks)
                if idx % 5 == 0:
                    await update_parse_stage(
                        "embedding",
                        50 + int(20 * (idx + 1) / len(chapters)),
                        f"正在分块处理（第 {idx+1}/{len(chapters)} 章）"
                    )

            logger.info("切分为 {} 个知识块 | book_id={}", len(all_chunks), book_id)

            # 阶段 4: 生成向量嵌入
            await update_parse_stage("knowledge", 80, "正在生成向量嵌入")
            await _generate_embeddings(all_chunks, session)

            # 阶段 5: 保存知识块
            await update_parse_stage("knowledge", 85, "正在保存知识块")
            service = BookService(session)
            saved = await service.save_chunks(book_uuid, all_chunks)
            book.total_chunks = saved
            book.parsed_chunks = saved

            # 完成
            book.parse_status = "completed"
            book.parse_progress = 100
            book.parse_stage = "done"
            book.parse_stage_progress = 100
            book.parse_stage_description = f"解析完成：{len(chapters)} 章 / {saved} 块"
            await session.commit()

            logger.info("书籍解析完成 | book_id={} chapters={} chunks={}", book_id, len(chapters), saved)
            return {"book_id": book_id, "status": "completed", "chapters": len(chapters), "chunks": saved}

        except Exception as e:
            logger.exception("书籍解析失败 | book_id={}", book_id)
            book.parse_status = "failed"
            book.parse_stage = "failed"
            book.parse_error_message = str(e)
            await session.commit()
            return {"book_id": book_id, "status": "failed", "reason": str(e)}
        finally:
            await engine.dispose()


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
