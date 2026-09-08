import { useEffect, useRef, useState, useCallback } from 'react';
import { createWS, getAuthToken } from '../api';

export interface LiveTransaction {
  type: string;
  transaction_id: string;
  amount: number;
  merchant: string;
  category: string;
  location: string;
  country: string;
  device: string;
  payment_method: string;
  user_id: string;
  prediction: string;
  fraud_probability: number;
  anomaly_score: number;
  risk_score: number;
  risk_level: string;
  reasons: string[];
  timestamp: string;
  is_simulation: boolean;
}

export interface LiveAlert {
  type: string;
  alert_id: string;
  transaction_id: string;
  severity: string;
  risk_score: number;
  reasons: string[];
  timestamp: string;
}

export function useWebSocket() {
  const [connected, setConnected] = useState(false);
  const [transactions, setTransactions] = useState<LiveTransaction[]>([]);
  const [alerts, setAlerts] = useState<LiveAlert[]>([]);
  const [stats, setStats] = useState({ total: 0, fraud: 0, critical: 0 });
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const badAuthRef = useRef(false);
  const consecutive1006Ref = useRef(0);
  const reconnectAttemptRef = useRef(0);
  const pendingWsRef = useRef<WebSocket | null>(null);

  // Close any existing connection and cancel pending reconnect timers.
  // Called before creating a new connection to guarantee only one WebSocket
  // and one reconnect timer exist at any time.
  const cleanup = useCallback(() => {
    if (reconnectTimerRef.current) {
      clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
    }
    if (pendingWsRef.current) {
      pendingWsRef.current.close();
      pendingWsRef.current = null;
    }
    if (wsRef.current && wsRef.current.readyState !== WebSocket.CLOSED) {
      wsRef.current.close();
    }
    wsRef.current = null;
    consecutive1006Ref.current = 0;
    reconnectAttemptRef.current = 0;
  }, []);

  // Exponential backoff: 1s, 2s, 4s, 8s, 16s, capped at 30s.
  const backoffDelay = (attempt: number): number => {
    return Math.min(1000 * Math.pow(2, attempt), 30000);
  };

  const connect = useCallback(() => {
    // Guard: no token or previously determined bad auth.
    if (!getAuthToken()) {
      badAuthRef.current = true;
      setConnected(false);
      return;
    }
    if (badAuthRef.current) {
      return;
    }
    // Cleanup any stale connection before creating a new one.
    cleanup();

    try {
      const ws = createWS();
      if (!ws) {
        badAuthRef.current = true;
        setConnected(false);
        return;
      }
      pendingWsRef.current = ws;
      wsRef.current = ws;

      ws.onopen = () => {
        pendingWsRef.current = null;
        setConnected(true);
        badAuthRef.current = false;
        consecutive1006Ref.current = 0;
        reconnectAttemptRef.current = 0;
        console.log('WebSocket connected');
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.type === 'pong' || data.type === 'heartbeat') return;

          if (data.type === 'transaction') {
            setTransactions(prev => {
              const next = [data, ...prev].slice(0, 200);
              return next;
            });
            setStats(prev => ({
              total: prev.total + 1,
              fraud: prev.fraud + (data.prediction === 'FRAUD' ? 1 : 0),
              critical: prev.critical + (data.risk_level === 'CRITICAL' ? 1 : 0),
            }));
          }

          if (data.type === 'alert') {
            setAlerts(prev => [data, ...prev].slice(0, 50));
          }
        } catch (e) { /* ignore parse errors */ }
      };

      ws.onclose = (event) => {
        pendingWsRef.current = null;
        setConnected(false);

        // Auth rejection by server (custom close code >= 4000).
        if (badAuthEvent(event)) {
          badAuthRef.current = true;
          console.warn('WebSocket auth rejected (close code ' + event.code + '); stopping reconnect loop');
          return;
        }

        // Token was cleared (logout/expiry) while connected.
        if (getAuthToken() === null) {
          badAuthRef.current = true;
          return;
        }

        // Browser reports server 401/403 upgrade rejection as 1006.
        // Track consecutive 1006s: after 2 in a row, treat as auth failure.
        if (event.code === 1006) {
          consecutive1006Ref.current = (consecutive1006Ref.current || 0) + 1;
          if (consecutive1006Ref.current >= 2) {
            badAuthRef.current = true;
            console.warn('WebSocket closed with 1006 twice; treating as auth failure and stopping reconnect loop');
            return;
          }
        } else {
          consecutive1006Ref.current = 0;
        }

        // Network drop with valid token — reconnect with exponential backoff.
        const attempt = ++reconnectAttemptRef.current;
        const delay = backoffDelay(attempt);
        console.log('WebSocket disconnected (code ' + event.code + '); reconnecting in ' + (delay / 1000) + 's (attempt ' + attempt + ')');
        reconnectTimerRef.current = setTimeout(() => connect(), delay);
      };

      ws.onerror = () => {
        // onerror fires for transport-level errors; onclose will decide.
      };
    } catch (e) {
      setConnected(false);
    }
  }, [cleanup]);

  useEffect(() => {
    if (!getAuthToken()) {
      badAuthRef.current = true;
      setConnected(false);
      return;
    }
    // Reset badAuth on fresh mount so re-login works.
    badAuthRef.current = false;
    connect();
    return () => {
      cleanup();
    };
  }, [connect, cleanup]);

  const sendMessage = useCallback((msg: any) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(msg));
    }
  }, []);

  return { connected, transactions, alerts, stats, sendMessage };
}

function badAuthEvent(event: CloseEvent): boolean {
  if (event && typeof event.code === 'number') {
    if (event.code >= 4000 || event.code === 1008) {
      return true;
    }
  }
  return false;
}
