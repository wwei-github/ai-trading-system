import request from './request';
import type {
  Book,
  BookChapter,
  BookCreateData,
  BookUpdateData,
  BookListParams,
  BookProgressUpdate,
  BookNote,
  BookNoteCreateData,
  BookQAResponse,
  BookParseResult,
  BookParseProgress,
} from '@/types';

export const bookApi = {
  async getList(params: BookListParams = {}): Promise<Book[]> {
    const res = await request.get<Book[]>('/books', { params });
    return res.data;
  },

  async getDetail(id: string): Promise<Book> {
    const res = await request.get<Book>(`/books/${id}`);
    return res.data;
  },

  async create(data: BookCreateData): Promise<Book> {
    const res = await request.post<Book>('/books', data);
    return res.data;
  },

  async upload(formData: FormData): Promise<Book> {
    const res = await request.post<Book>('/books/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return res.data;
  },

  async update(id: string, data: BookUpdateData): Promise<Book> {
    const res = await request.patch<Book>(`/books/${id}`, data);
    return res.data;
  },

  async delete(id: string): Promise<void> {
    await request.delete(`/books/${id}`);
  },

  async updateProgress(id: string, data: BookProgressUpdate): Promise<Book> {
    const res = await request.patch<Book>(`/books/${id}/progress`, data);
    return res.data;
  },

  async parseContent(id: string): Promise<BookParseResult> {
    const res = await request.post<BookParseResult>(`/books/${id}/parse`);
    return res.data;
  },

  async reparseContent(id: string): Promise<BookParseResult> {
    const res = await request.post<BookParseResult>(`/books/${id}/reparse`);
    return res.data;
  },

  async getParseProgress(id: string): Promise<BookParseProgress> {
    const res = await request.get<BookParseProgress>(`/books/${id}/parse/progress`);
    return res.data;
  },

  async getChapters(id: string): Promise<BookChapter[]> {
    const res = await request.get<BookChapter[]>(`/books/${id}/chapters`);
    return res.data;
  },

  async getChapterContent(id: string, chapterOrder: number): Promise<BookChapter> {
    const res = await request.get<BookChapter>(`/books/${id}/chapters/${chapterOrder}`);
    return res.data;
  },

  async qa(
    bookId: string,
    question: string,
    context?: string,
  ): Promise<BookQAResponse> {
    const payload: { question: string; context?: string; top_k?: number } = {
      question,
    };
    if (context !== undefined) {
      payload.context = context;
    }
    const res = await request.post<BookQAResponse>(`/books/${bookId}/qa`, payload);
    return res.data;
  },

  async getNotes(id: string): Promise<BookNote[]> {
    const res = await request.get<BookNote[]>(`/books/${id}/notes`);
    return res.data;
  },

  async createNote(id: string, data: BookNoteCreateData): Promise<BookNote> {
    const res = await request.post<BookNote>(`/books/${id}/notes`, data);
    return res.data;
  },
};

export default bookApi;