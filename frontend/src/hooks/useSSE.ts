import { useEffect, useRef, useCallback } from 'react';

interface SSEOptions {
  url: string;
  onMessage: (data: any) => void;
  onDone?: () => void;
  onError?: (error: Event) => void;
  enabled?: boolean;
}

export function useSSE({ url, onMessage, onDone, onError, enabled = true }: SSEOptions) {
  const eventSourceRef = useRef<EventSource | null>(null);

  const close = useCallback(() => {
    eventSourceRef.current?.close();
    eventSourceRef.current = null;
  }, []);

  useEffect(() => {
    if (!enabled || !url) return;

    const es = new EventSource(url);
    eventSourceRef.current = es;

    es.onmessage = (event) => {
      if (event.data === '[DONE]') {
        onDone?.();
        es.close();
        return;
      }
      try {
        const data = JSON.parse(event.data);
        onMessage(data);
      } catch (e) {
        console.error('SSE parse error:', e);
      }
    };

    es.onerror = (error) => {
      console.error('SSE error:', error);
      onError?.(error);
      es.close();
    };

    return () => {
      es.close();
    };
  }, [url, enabled, onMessage, onDone, onError]);

  return { close };
}