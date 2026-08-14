import request from './request';
import type {
  SystemUser,
  UserCreateData,
  UserUpdateData,
  SystemConfig,
  NotificationConfig,
  AuditLog,
  SystemInfo,
  AuditLogParams,
  UserListParams,
} from '@/types';
import type { ErrorLogItem, ErrorLogStats, ErrorLogParams } from '@/types';
import type { PaginatedResponse } from '@/types/api';

export const systemApi = {
  async getInfo(): Promise<SystemInfo> {
    const res = await request.get<SystemInfo>('/system/info');
    return res.data;
  },

  async getUsers(params?: UserListParams): Promise<PaginatedResponse<SystemUser>> {
    const res = await request.get<PaginatedResponse<SystemUser>>('/system/users', { params });
    return res.data;
  },

  async createUser(data: UserCreateData): Promise<SystemUser> {
    const res = await request.post<SystemUser>('/system/users', data);
    return res.data;
  },

  async updateUser(id: string, data: UserUpdateData): Promise<SystemUser> {
    const res = await request.patch<SystemUser>(`/system/users/${id}`, data);
    return res.data;
  },

  async getConfig(): Promise<SystemConfig> {
    const res = await request.get<SystemConfig>('/system/config');
    return res.data;
  },

  async updateConfig(data: Partial<SystemConfig>): Promise<SystemConfig> {
    const res = await request.patch<SystemConfig>('/system/config', data);
    return res.data;
  },

  async getNotificationConfig(): Promise<NotificationConfig> {
    const res = await request.get<NotificationConfig>('/system/notifications');
    return res.data;
  },

  async updateNotificationConfig(data: NotificationConfig): Promise<NotificationConfig> {
    const res = await request.patch<NotificationConfig>('/system/notifications', data);
    return res.data;
  },

  async getAuditLogs(params?: AuditLogParams): Promise<PaginatedResponse<AuditLog>> {
    const res = await request.get<PaginatedResponse<AuditLog>>('/system/audit-logs', { params });
    return res.data;
  },

  // 错误日志
  async getErrorLogs(params: ErrorLogParams): Promise<PaginatedResponse<ErrorLogItem>> {
    const res = await request.get<PaginatedResponse<ErrorLogItem>>('/system/error-logs', { params });
    return res.data;
  },

  async getErrorLog(id: string): Promise<ErrorLogItem> {
    const res = await request.get<ErrorLogItem>(`/system/error-logs/${id}`);
    return res.data;
  },

  async getErrorLogStats(): Promise<ErrorLogStats> {
    const res = await request.get<ErrorLogStats>('/system/error-logs/stats');
    return res.data;
  },

  async cleanErrorLogs(data: { before_days: number; level?: string }): Promise<{ deleted_count: number }> {
    const res = await request.post<{ deleted_count: number }>('/system/error-logs/clean', data);
    return res.data;
  },
};

export default systemApi;
