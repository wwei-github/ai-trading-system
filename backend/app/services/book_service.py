"""书籍服务。"""

from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.book import Book, BookNote
from app.schemas.book import BookCreate, BookUpdate, BookNoteCreate


class BookService:
    """书籍服务。

    处理书籍管理、笔记和知识库检索。
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_book(self, user_id: str, data: BookCreate) -> Book:
        """创建书籍记录。"""
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

    async def get_book(self, book_id: str) -> Optional[Book]:
        """获取书籍详情。"""
        result = await self.db.execute(select(Book).where(Book.id == book_id))
        return result.scalar_one_or_none()

    async def list_books(self, user_id: str) -> List[Book]:
        """获取用户的全部书籍。"""
        result = await self.db.execute(
            select(Book).where(Book.user_id == user_id)
        )
        return list(result.scalars().all())

    async def update_book(
        self, book_id: str, data: BookUpdate
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

    async def delete_book(self, book_id: str) -> bool:
        """删除书籍。"""
        book = await self.get_book(book_id)
        if book is None:
            return False
        await self.db.delete(book)
        await self.db.flush()
        return True

    async def create_note(
        self, user_id: str, data: BookNoteCreate
    ) -> BookNote:
        """创建书籍笔记。"""
        note = BookNote(
            book_id=data.book_id,
            user_id=user_id,
            chapter=data.chapter,
            content=data.content,
            highlight_range=data.highlight_range,
        )
        self.db.add(note)
        await self.db.flush()
        return note

    async def list_notes(self, book_id: str) -> List[BookNote]:
        """获取书籍的笔记列表。"""
        result = await self.db.execute(
            select(BookNote).where(BookNote.book_id == book_id)
        )
        return list(result.scalars().all())
