'use client';

import { useEffect, useState, useCallback, useRef } from 'react';
import { StreamUpdate, Game } from '@/lib/types';
import { api } from '@/lib/api';

interface UseRealtimeOptions {
  gameId?: string;
  onUpdate?: (update: StreamUpdate) => void;
  onError?: (error: Error) => void;
  reconnectInterval?: number;
  maxReconnects?: number;
}

export function useRealtime(options: UseRealtimeOptions = {}) {
  const { gameId, onUpdate, onError, reconnectInterval = 5000, maxReconnects = 10 } = options;
  const [isConnected, setIsConnected] = useState(false);
  const [lastUpdate, setLastUpdate] = useState<StreamUpdate | null>(null);
  const [reconnectCount, setReconnectCount] = useState(0);
  const eventSourceRef = useRef<EventSource | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  const connect = useCallback(() => {
    if (eventSourceRef.current?.readyState === EventSource.OPEN) {
      return;
    }

    try {
      const es = api.stream.connect(gameId);
      eventSourceRef.current = es;

      es.onopen = () => {
        setIsConnected(true);
        setReconnectCount(0);
      };

      es.onmessage = (event) => {
        try {
          const data: StreamUpdate = JSON.parse(event.data);
          setLastUpdate(data);
          onUpdate?.(data);
        } catch (err) {
          console.error('Failed to parse SSE data:', err);
        }
      };

      es.onerror = (error) => {
        setIsConnected(false);
        es.close();
        
        if (reconnectCount < maxReconnects) {
          reconnectTimeoutRef.current = setTimeout(() => {
            setReconnectCount(prev => prev + 1);
            connect();
          }, reconnectInterval);
        }
        
        onError?.(error as Error);
      };
    } catch (err) {
      onError?.(err as Error);
    }
  }, [gameId, onUpdate, onError, reconnectInterval, maxReconnects, reconnectCount]);

  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
    }
    eventSourceRef.current?.close();
    setIsConnected(false);
  }, []);

  useEffect(() => {
    connect();
    return () => disconnect();
  }, [connect, disconnect]);

  return {
    isConnected,
    lastUpdate,
    reconnectCount,
    connect,
    disconnect,
  };
}

export function useRealtimeGame(gameId: string) {
  const [game, setGame] = useState<Game | null>(null);
  const { isConnected, lastUpdate } = useRealtime({ gameId });

  useEffect(() => {
    if (lastUpdate?.type === 'GRADE_UPDATE' || lastUpdate?.type === 'LINE_MOVEMENT') {
      setGame(prev => prev ? { ...prev, ...lastUpdate.data } : null);
    }
  }, [lastUpdate]);

  return { game, isConnected, lastUpdate };
}
