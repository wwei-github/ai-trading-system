import type { PageParams } from './api';

export type ParseStatus = 'pending' | 'parsing' | 'completed' | 'failed';

export interface Book {
  id: string;
  user_id: string;
  title: string;
  author?: string;
  category?: string;
  tags: string[];
  file_path?: string;
  file_type?: string;
  file_size?: number;
  parse_status?: ParseStatus;
  parse_progress?: number;
  reading_progress: number;
  cover_image_url?: string;
  description?: string;
  summary?: string;
  total_pages?: number;
  chapter_count?: number;
  created_at: string;
  updated_at: string;
  parsed_at?: string;
}

export interface BookCreateData {
  title: string;
  author?: string;
  category?: string;
  tags?: string[];
  description?: string;
}

export type BookUpdateData = Partial<BookCreateData>;

export interface Chapter {
  id: string;
  book_id: string;
  title: string;
  content_preview?: string;
  order_index: number;
}

export interface BookNote {
  id: string;
  book_id: string;
  chapter_id?: string;
  content: string;
  highlight_text?: string;
  page_num?: number;
  created_at: string;
}

export interface BookChapter {
  id: string;
  title: string;
  chapter_order: number;
  page_start?: number;
  page_end?: number;
  char_count: number;
  level: number;
  content?: string;
}

export interface BookListParams extends PageParams {
  keyword?: string;
  category?: string;
  parse_status?: ParseStatus;
}

export interface BookProgressUpdate {
  progress: number;
}

export interface BookNoteCreateData {
  chapter_id?: string;
  content: string;
  highlight_text?: string;
  page_num?: number;
}

export interface BookQARequest {
  question: string;
  context?: string;
  top_k?: number;
}

export interface BookQAResponse {
  answer: string;
  sources: Array<{
    content: string;
    chapter?: string;
    page_num?: number;
    score?: number;
  }>;
}

export interface BookParseResult {
  task_id: string;
  message: string;
}

export interface BookParseProgress {
  book_id: string;
  status: ParseStatus;
  progress: number;
  total_chapters?: number;
  total_chunks?: number;
}
