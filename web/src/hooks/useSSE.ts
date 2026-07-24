import { useEffect, useState, useRef, useCallback } from 'react';

interface SSEEvent {
  event: string;
  id: string;
  data: any;
}

interface UseSSEOptions {
  onEvent?: (event: SSEEvent) => void;
  onDeviceUpdate?: (deviceId: string, properties: any) => void;
  onDeviceEvent?: (deviceId: string, eventType: string, payload: any) => void;
  enabled?: boolean;
}

export function useSSE({ 
  onEvent, 
  onDeviceUpdate, 
  onDeviceEvent, 
  enabled = true 
}: UseSSEOptions = {}) {
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [reconnectCounter, setReconnectCounter] = useState(0);
  
  const onEventRef = useRef(onEvent);
  const onDeviceUpdateRef = useRef(onDeviceUpdate);
  const onDeviceEventRef = useRef(onDeviceEvent);
  const enabledRef = useRef(enabled);
  const reconnectTimeoutRef = useRef<number | null>(null);
  const reconnectAttemptRef = useRef(0);
  const eventSourceRef = useRef<EventSource | null>(null);
  const hasOpenedRef = useRef(false);

  useEffect(() => {
    onEventRef.current = onEvent;
  }, [onEvent]);

  useEffect(() => {
    onDeviceUpdateRef.current = onDeviceUpdate;
  }, [onDeviceUpdate]);

  useEffect(() => {
    onDeviceEventRef.current = onDeviceEvent;
  }, [onDeviceEvent]);

  useEffect(() => {
    enabledRef.current = enabled;
  }, [enabled]);

  const clearReconnectTimeout = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
  }, []);

  const scheduleReconnect = useCallback(() => {
    if (!enabledRef.current) return;
    
    clearReconnectTimeout();
    
    const baseDelay = 1000;
    const maxDelay = 30000;
    const delay = Math.min(
      baseDelay * Math.pow(2, reconnectAttemptRef.current),
      maxDelay
    );
    
    reconnectAttemptRef.current += 1;
    
    reconnectTimeoutRef.current = window.setTimeout(() => {
      console.log(`[SSE] Reconnecting attempt ${reconnectAttemptRef.current} after ${delay}ms`);
      setReconnectCounter(c => c + 1);
    }, delay);
  }, [clearReconnectTimeout]);

  const resetReconnectAttempts = useCallback(() => {
    reconnectAttemptRef.current = 0;
    clearReconnectTimeout();
  }, [clearReconnectTimeout]);

  const connect = useCallback(() => {
    if (!enabledRef.current) return;

    clearReconnectTimeout();
    hasOpenedRef.current = false;

    const url = '/api/events/stream';
    const eventSource = new EventSource(url);
    eventSourceRef.current = eventSource;

    eventSource.onopen = () => {
      hasOpenedRef.current = true;
      setConnected(true);
      setError(null);
      resetReconnectAttempts();
      console.log('[SSE] Connection opened');
    };

    eventSource.onerror = (e) => {
      setConnected(false);
      console.error('[SSE] Connection error:', e);

      // 401 未认证:连接从未 opened 过,说明是认证失败,不要重连(避免死循环)
      if (!hasOpenedRef.current) {
        eventSource.close();
        eventSourceRef.current = null;
        setError('Authentication failed');
        console.error('[SSE] Auth failure (401) detected, stopping reconnection');
        return;
      }

      if (eventSource.readyState === EventSource.CLOSED) {
        setError('Connection closed');
        scheduleReconnect();
      }
    };

    eventSource.addEventListener('device_update', (e: MessageEvent) => {
      try {
        const data = JSON.parse(e.data);
        console.log('[SSE] Device update:', data);
        if (onDeviceUpdateRef.current && data.device_id && data.properties) {
          onDeviceUpdateRef.current(data.device_id, data.properties);
        }
        if (onEventRef.current) {
          onEventRef.current({ event: 'device_update', id: data.id || '', data });
        }
      } catch (err) {
        console.error('[SSE] Failed to parse device_update:', err);
      }
    });

    eventSource.addEventListener('device_event', (e: MessageEvent) => {
      try {
        const data = JSON.parse(e.data);
        console.log('[SSE] Device event:', data);
        if (onDeviceEventRef.current && data.device_id && data.event_type) {
          onDeviceEventRef.current(data.device_id, data.event_type, data.payload);
        }
        if (onEventRef.current) {
          onEventRef.current({ event: 'device_event', id: data.id || '', data });
        }
      } catch (err) {
        console.error('[SSE] Failed to parse device_event:', err);
      }
    });

    eventSource.onmessage = (e: MessageEvent) => {
      if (e.data === ': keep-alive') {
        return;
      }
      try {
        const eventData = JSON.parse(e.data);
        console.log('[SSE] Generic message:', eventData);
        if (onEventRef.current) {
          onEventRef.current({ event: eventData.event || 'message', id: eventData.id || '', data: eventData.data || eventData });
        }
      } catch (err) {
        console.error('[SSE] Failed to parse message:', err);
      }
    };

    return () => {
      clearReconnectTimeout();
      eventSource.close();
      eventSourceRef.current = null;
      setConnected(false);
      console.log('[SSE] Connection closed');
    };
  }, [clearReconnectTimeout, resetReconnectAttempts, scheduleReconnect]);

  useEffect(() => {
    if (!enabled) return;
    const cleanup = connect();
    return cleanup;
  }, [connect, enabled, reconnectCounter]);

  const reconnect = useCallback(() => {
    setReconnectCounter(c => c + 1);
  }, []);

  return { connected, error, reconnect };
}