import { useEffect, useRef, useCallback, useState } from 'react';

interface SSEOptions {
  url: string;
  onMessage: (data: any) => void;
  onDone?: () => void;
  onError?: (error: Event) => void;
  enabled?: boolean;
}

const MAX_RETRIES = 999;  // 几乎无限重试，直到回测完成
const RETRY_DELAY_MS = 3000;  // 重连间隔 3 秒

export function useSSE({ url, onMessage, onDone, onError, enabled = true }: SSEOptions) {
  const eventSourceRef = useRef<EventSource | null>(null);
  const retryCountRef = useRef(0);
  const retryTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [shouldReconnect, setShouldReconnect] = useState(0);  // 触发重连的计数器

  const close = useCallback(() => {
    if (retryTimeoutRef.current) {
      clearTimeout(retryTimeoutRef.current);
      retryTimeoutRef.current = null;
    }
    eventSourceRef.current?.close();
    eventSourceRef.current = null;
    retryCountRef.current = 0;
  }, []);

  const connect = useCallback(() => {
    if (!enabled || !url) return;

    const es = new EventSource(url);
    eventSourceRef.current = es;

    es.onmessage = (event) => {
      // 心跳注释（以 : 开头）也会触发 onmessage，但 event.data 为空
      if (!event.data || event.data === '' || event.data.startsWith(':')) {
        return;
      }
      if (event.data === '[DONE]') {
        onDone?.();
        es.close();
        eventSourceRef.current = null;
        retryCountRef.current = 0;
        return;
      }
      try {
        const data = JSON.parse(event.data);
        // 成功收到数据，重置重试计数
        retryCountRef.current = 0;
        onMessage(data);
      } catch (e) {
        console.error('SSE parse error:', e);
      }
    };

    es.onerror = (error) => {
      retryCountRef.current += 1;
      console.warn(`SSE connection broken (retry #${retryCountRef.current}):`, error);
      onError?.(error);

      // 关闭当前坏连接
      es.close();
      eventSourceRef.current = null;

      // 超过最大重试次数，彻底关闭
      if (retryCountRef.current >= MAX_RETRIES) {
        console.error('SSE max retries reached, giving up');
        onDone?.();
        return;
      }

      // 延迟后自动重连
      retryTimeoutRef.current = setTimeout(() => {
        console.info(`SSE reconnecting... (attempt ${retryCountRef.current + 1}/${MAX_RETRIES})`);
        setShouldReconnect(prev => prev + 1);  // 触发 useEffect 重新连接
      }, RETRY_DELAY_MS);
    };
  }, [url, enabled, onMessage, onDone, onError]);

  useEffect(() => {
    connect();
    return () => close();
  }, [connect, close, shouldReconnect]);  // shouldReconnect 变化时重新连接

  return { close };
}