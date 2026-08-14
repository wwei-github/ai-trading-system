import type { PageParams } from './api';

export type UserRole = 'admin' | 'trader' | 'viewer' | 'user';
export type UserStatus = 'active' | 'disabled';

export interface SystemUser {
  id: string;
  username?: string;
  nickname?: string;
  email: string;
  role: UserRole;
  status: UserStatus;
  is_active?: boolean;
  last_login_at?: string;
  created_at: string;
  updated_at?: string;
}

export interface UserCreateData {
  username?: string;
  nickname: string;
  email: string;
  password: string;
  role?: UserRole;
  is_active?: boolean;
}

export interface UserUpdateData {
  email?: string;
  nickname?: string;
  role?: UserRole;
  status?: UserStatus;
  is_active?: boolean;
}

export interface SystemConfig {
  app_name?: string;
  app_env?: string;
  api_prefix?: string;
  debug?: boolean;
  default_exchange?: string;
  price_precision?: number;
  currency_precision?: number;
  ai_model?: string;
  llm_provider?: string;
  llm_model?: string;
  data_refresh_interval?: number;
  timezone?: string;
  theme?: string;
  locale?: string;
  version?: string;
}

export interface NotificationChannels {
  email?: boolean;
  desktop?: boolean;
  sms?: boolean;
  push?: boolean;
}

export interface NotificationConfig {
  channels?: NotificationChannels;
  events?: Record<string, boolean>;
  email_notification?: boolean;
  desktop_notification?: boolean;
  trade_signal_alert?: boolean;
  sync_failure_alert?: boolean;
  report_frequency?: 'daily' | 'weekly' | 'monthly' | string;
}

export interface AuditLog {
  id: string;
  user_id: string | null;
  username?: string;
  action_type: string;
  action?: string;
  target_type?: string;
  resource_type?: string;
  target_id?: string | null;
  resource_id?: string | null;
  ip?: string | null;
  user_agent?: string;
  details?: Record<string, unknown>;
  detail?: Record<string, unknown> | null;
  created_at: string;
}

export interface SystemInfo {
  version?: string;
  build_time?: string;
  python_version?: string;
  db_type?: string;
  db_status?: string;
  ai_model_status?: string;
  uptime_seconds?: number;
  last_health_check_at?: string;
  app_name?: string;
  app_env?: string;
  api_prefix?: string;
  debug?: boolean;
  status?: string;
  module?: string;
}

export interface AuditLogParams extends PageParams {
  action_type?: string;
  action?: string;
  target_type?: string;
  resource_type?: string;
  user_id?: string;
  start_date?: string;
  end_date?: string;
}

export interface UserListParams extends PageParams {
  role?: UserRole;
  status?: UserStatus;
  is_active?: boolean;
  keyword?: string;
}

// 错误日志
export interface ErrorLogItem {
  id: string;
  request_id?: string;
  level: 'ERROR' | 'WARNING' | 'INFO';
  module: string;
  message: string;
  exception_type?: string;
  traceback?: string;
  request_path?: string;
  request_method?: string;
  request_params?: any;
  status_code?: number;
  user_id?: string;
  user_ip?: string;
  user_agent?: string;
  duration_ms?: number;
  detail?: Record<string, any>;
  created_at: string;
}

export interface ErrorLogStats {
  total_errors: number;
  error_count: number;
  warning_count: number;
  info_count: number;
  module_distribution: Record<string, number>;
  recent_errors: ErrorLogItem[];
}

export interface ErrorLogParams extends PageParams {
  level?: string;
  module?: string;
  status_code?: number;
  keyword?: string;
  start_time?: string;
  end_time?: string;
}
