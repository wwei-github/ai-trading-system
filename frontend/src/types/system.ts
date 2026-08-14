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
