import request from './request';

export interface QueuedTaskInfo {
  task_id: string;
  task_name: string;
  queue_name: string;
  received_at: string | null;
  eta: string | null;
}

export interface QueueStats {
  redis_connected: boolean;
  queues: Record<string, number>;
}

export const taskApi = {
  /** 获取队列统计信息 */
  async getQueueStats(): Promise<QueueStats> {
    const res = await request.get<QueueStats>('/tasks/info');
    return res.data;
  },

  /** 获取排队中任务列表 */
  async getQueuedTasks(taskNameFilter?: string): Promise<{ tasks: QueuedTaskInfo[]; total: number }> {
    const params: any = {};
    if (taskNameFilter) params.task_name_filter = taskNameFilter;
    const res = await request.get<{ tasks: QueuedTaskInfo[]; total: number }>('/tasks/queued', { params });
    return res.data;
  },

  /** 从队列中删除排队任务 */
  async deleteQueuedTask(taskId: string): Promise<void> {
    await request.delete(`/tasks/queued/${taskId}`);
  },

  /** 终止正在运行的 AI 回测 */
  async cancelRunningAiBacktest(backtestId: string): Promise<void> {
    await request.post(`/tasks/cancel-running/ai-backtest/${backtestId}`);
  },
};