import { useEffect, useRef, useState, useCallback } from 'react';
import { createWS } from '../api';

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
  const reconnectRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const connect = useCallback(() => {
    try {
      const ws = createWS();
      wsRef.current = ws;

      ws.onopen = () => {
        setConnected(true);
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

      ws.onclose = () => {
        setConnected(false);
        // Reconnect after 3 seconds
        reconnectRef.current = setTimeout(() => connect(), 3000);
      };

      ws.onerror = () => {
        ws.close();
      };
    } catch (e) {
      setConnected(false);
    }
  }, []);

  useEffect(() => {
    connect();
    return () => {
      if (reconnectRef.current) clearTimeout(reconnectRef.current);
      wsRef.current?.close();
    };
  }, [connect]);

  const sendMessage = useCallback((msg: any) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(msg));
    }
  }, []);

  return { connected, transactions, alerts, stats, sendMessage };
}
