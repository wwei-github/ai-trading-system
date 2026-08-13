import axios, { type AxiosResponse, type InternalAxiosRequestConfig } from 'axios';
import { message } from 'antd';
import type { ApiResponse } from '@/types/api';

/**
 * 根据运行模式与环境变量确定实际 baseURL。
 *
 * 规则：
 * - local / docker 模式：VITE_API_BASE_URL 默认 /api/v1，请求由 Vite 代理转发
 * - online 模式：
 *     VITE_USE_PROXY=true（默认）→ 依旧 /api/v1 走 Vite 代理
 *     VITE_USE_PROXY=false        → 拼接 VITE_API_ONLINE_URL 直接跨域调用
 */
function resolveBaseURL(): string {
  const baseUrl = import.meta.env.VITE_API_BASE_URL || '/api/v1';
  const useProxy = import.meta.env.VITE_USE_PROXY !== 'false';

  if (!useProxy && import.meta.env.VITE_API_ONLINE_URL) {
    // 去重 URL 末尾斜杠，避免拼成 https://host//api/v1
    const prefix = import.meta.env.VITE_API_ONLINE_URL.endsWith('/')
      ? import.meta.env.VITE_API_ONLINE_URL.slice(0, -1)
      : import.meta.env.VITE_API_ONLINE_URL;
    const suffix = baseUrl.startsWith('/') ? baseUrl : `/${baseUrl}`;
    return `${prefix}${suffix}`;
  }

  return baseUrl;
}

/** 当前运行模式，用于调试或 UI 展示。 */
export const RUN_MODE: string = (import.meta.env.VITE_RUN_MODE || 'local').toString();

// 创建 axios 实例
const request = axios.create({
  baseURL: resolveBaseURL(),
  timeout: 15000,
});

// 请求拦截器
request.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    // 预留 Token 注入（暂未启用登录流程）
    // const token = localStorage.getItem('token');
    // if (token) {
    //   config.headers.Authorization = `Bearer ${token}`;
    // }
    return config;
  },
  (error) => Promise.reject(error),
);

// 响应拦截器：统一处理 code !== 0 的错误
request.interceptors.response.use(
  (response: AxiosResponse<ApiResponse>) => {
    const res = response.data;
    // 非 0 视为业务错误
    if (res.code !== 0) {
      message.error(res.message || '请求失败');
      return Promise.reject(new Error(res.message || 'Error'));
    }
    return res as unknown as AxiosResponse;
  },
  (error) => {
    message.error(error.message || '网络异常，请稍后重试');
    return Promise.reject(error);
  },
);

export default request;
