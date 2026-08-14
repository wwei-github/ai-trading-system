import type { PageParams } from './api';
import type { Strategy } from './strategies';

export type ParseStatus = 'pending' | 'parsing' | 'completed' | 'failed';

export interface Book {
  id: string;
  user_id: string;
  title: string;
  author?: string;
  category?: string;
  file_path?: string;
  file_type?: string;
  cover_url?: string;
  progress: number;
  metadata?: Record<string, unknown>;
  parse_status?: ParseStatus;
  parse_progress: number;
  parse_stage?: string;
  parse_stage_description?: string;
  parse_error_message?: string;
  parse_stage_progress: number;
  parsed_chapters: number;
  parsed_chunks: number;
  total_chapters: number;
  total_chunks: number;
  strategy_count: number;
  created_at: string;
  updated_at: string;
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
  stage?: string;
  stage_description?: string;
  total_chapters: number;
  total_chunks: number;
  parsed_chapters: number;
  parsed_chunks: number;
  error_message?: string;
}

/** AI 分析结果 */
export interface BookAnalyzeResult {
  book_analysis: string;
  core_concepts: string[];
  trading_system: {
    name: string;
    category: string;
    symbol?: string;
    timeframe?: string;
    entry_rules: any[];
    exit_rules: any[];
    position_sizing: any;
    risk_control: any;
  };
  strategies: Strategy[];
}