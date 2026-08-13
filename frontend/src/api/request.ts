import axios, { type AxiosResponse, type InternalAxiosRequestConfig } from 'axios';
import { message } from 'antd';
import type { ApiResponse } from '@/types/api';

// 创建 axios 实例
const request = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api/v1',
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
