import { useEffect, useRef, useCallback } from 'react';

interface SSEOptions {
  url: string;
  onMessage: (data: any) => void;
  onDone?: () => void;
  onError?: (error: Event) => void;
  enabled?: boolean;
}

const MAX_RETRIES = 20;

export function useSSE({ url, onMessage, onDone, onError, enabled = true }: SSEOptions) {
  const eventSourceRef = useRef<EventSource | null>(null);
  const retryCountRef = useRef(0);

  const close = useCallback(() => {
    eventSourceRef.current?.close();
    eventSourceRef.current = null;
    retryCountRef.current = 0;
  }, []);

  useEffect(() => {
    if (!enabled || !url) return;

    const es = new EventSource(url);
    eventSourceRef.current = es;
    retryCountRef.current = 0;

    es.onmessage = (event) => {
      // 心跳注释（以 : 开头）也会触发 onmessage，但 event.data 为空
      if (!event.data || event.data === '' || event.data.startsWith(':')) {
        return;
      }
      if (event.data === '[DONE]') {
        onDone?.();
        es.close();
        eventSourceRef.current = null;
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
      console.warn(`SSE error (retry #${retryCountRef.current}):`, error);
      onError?.(error);

      // 超过最大重试次数，彻底关闭
      if (retryCountRef.current >= MAX_RETRIES) {
        console.error('SSE max retries reached, closing connection');
        es.close();
        eventSourceRef.current = null;
        onDone?.();
      }
      // 注意：不主动 es.close()，让浏览器 EventSource 自动重连
    };

    return () => {
      es.close();
      eventSourceRef.current = null;
      retryCountRef.current = 0;
    };
  }, [url, enabled, onMessage, onDone, onError]);

  return { close };
}