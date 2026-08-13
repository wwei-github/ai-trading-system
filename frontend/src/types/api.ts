// 统一 API 响应结构
export interface ApiResponse<T = any> {
  code: number;
  message: string;
  data: T;
}

// 分页响应结构
export interface PaginatedResponse<T = any> {
  total: number;
  page: number;
  page_size: number;
  items: T[];
}

// 分页查询参数
export interface PageParams {
  page?: number;
  page_size?: number;
}
