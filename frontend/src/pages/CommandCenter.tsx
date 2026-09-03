import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { getDashboardSummary } from '../api';
import type { LiveTransaction } from '../hooks/useWebSocket';

interface Props {
  ws: {
    connected: boolean;
    transactions: LiveTransaction[];
    alerts: any[];
    stats: { total: number; fraud: number; critical: number };
    sendMessage: (msg: any) => void;
  };
}

export default function CommandCenter({ ws }: Props) {
  const [summary, setSummary] = useState<any>(null);
  const [simRunning, setSimRunning] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    getDashboardSummary().then(setSummary).catch(() => {});
    const interval = setInterval(() => {
      getDashboardSummary().then(setSummary).catch(() => {});
    }, 10000);
    return () => clearInterval(interval);
  }, []);

  // Track simulation state from WebSocket
  useEffect(() => {
    if (ws.connected && ws.stats.total > 0) {
      setSimRunning(true);
    }
  }, [ws.connected, ws.stats.total]);

  const toggleSim = useCallback(() => {
    if (simRunning) {
      ws.sendMessage({ action: 'stop_simulation' });
      setSimRunning(false);
    } else {
      ws.sendMessage({ action: 'start_simulation', interval: 3 });
      setSimRunning(true);
    }
  }, [simRunning, ws]);

  const liveTotal = ws.stats.total || summary?.total_transactions || 0;
  const liveFraud = ws.stats.fraud || summary?.fraud_transactions || 0;
  const liveCritical = ws.stats.critical || summary?.critical_alerts || 0;

  const riskCounts = { CRITICAL: 0, HIGH: 0, MEDIUM: 0, LOW: 0 };
  ws.transactions.forEach(t => {
    const lvl = (t.risk_level || '').toUpperCase();
    if (lvl in riskCounts) riskCounts[lvl as keyof typeof riskCounts]++;
  });

  return (
    <div className="fade-in" style={{ height: '100%', display: 'flex', flexDirection: 'column', gap: 12 }}>
      {/* Header Bar */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h1 style={{ fontSize: 18, fontWeight: 800, letterSpacing: '-0.5px' }}>
            Fraud Intelligence Command Center
          </h1>
          <p style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 1 }}>
            Real-time risk intelligence monitoring
          </p>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <span style={{
              width: 7, height: 7, borderRadius: '50%',
              background: simRunning ? 'var(--green)' : 'var(--red)',
              display: 'inline-block', animation: simRunning ? 'pulse 2s infinite' : 'none',
            }} />
            <span style={{ fontSize: 10, fontWeight: 700, color: simRunning ? 'var(--green)' : 'var(--text-muted)', letterSpacing: 0.5 }}>
              {simRunning ? 'LIVE' : 'IDLE'}
            </span>
          </div>
          <button
            className={`btn btn-sm ${simRunning ? 'btn-danger' : 'btn-primary'}`}
            onClick={toggleSim}
            disabled={!ws.connected}
          >
            {simRunning ? '■ Stop' : '▶ Start Simulation'}
          </button>
        </div>
      </div>

      {/* Compact KPI Strip */}
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        {[
          { label: 'TOTAL', value: liveTotal.toLocaleString(), color: 'var(--text-primary)' },
          { label: 'FRAUD', value: String(liveFraud), color: 'var(--red)' },
          { label: 'CRITICAL', value: String(liveCritical), color: 'var(--orange)' },
          { label: 'RATE', value: liveTotal > 0 ? ((liveFraud / liveTotal) * 100).toFixed(1) + '%' : '0.0%', color: 'var(--yellow)' },
          { label: 'MODELS', value: summary?.model_version ? '3 Active' : '—', color: 'var(--cyan)' },
          { label: 'RISK AVG', value: summary?.avg_risk_score ? String(summary.avg_risk_score) : '—', color: 'var(--purple)' },
        ].map(k => (
          <div key={k.label} style={{
            flex: '1 1 0', minWidth: 100, padding: '8px 10px',
            background: 'var(--bg-card)', border: '1px solid var(--border)',
            borderRadius: 'var(--radius)',
          }}>
            <div style={{ fontSize: 9, fontWeight: 700, textTransform: 'uppercase', letterSpacing: 0.8, color: 'var(--text-dim)' }}>{k.label}</div>
            <div style={{ fontSize: 18, fontWeight: 800, fontFamily: 'var(--mono)', color: k.color, lineHeight: 1.2 }}>{k.value}</div>
          </div>
        ))}
      </div>

      {/* Main Content */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 300px', gap: 12, flex: 1, minHeight: 0 }}>
        {/* Left: Live Transaction Stream */}
        <div className="card" style={{ display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
          <div className="card-header" style={{ marginBottom: 0, padding: '10px 14px', borderBottom: '1px solid var(--border)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span className="card-title">Live Transaction Stream</span>
              {simRunning && (
                <span style={{ fontSize: 9, fontWeight: 700, padding: '2px 6px', borderRadius: 3, background: 'var(--red-dim)', color: 'var(--red)', letterSpacing: 0.5, animation: 'pulse 2s infinite' }}>● REC</span>
              )}
            </div>
            <span style={{ fontSize: 10, color: 'var(--text-muted)', fontFamily: 'var(--mono)' }}>{ws.transactions.length} events</span>
          </div>
          <div style={{ flex: 1, overflowY: 'auto' }}>
            {ws.transactions.length === 0 ? (
              <div className="empty-state" style={{ padding: 40 }}>
                <div style={{ fontSize: 32, marginBottom: 8, opacity: 0.4 }}>📡</div>
                <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                  {simRunning ? 'Waiting for transactions...' : 'Start simulation to begin monitoring'}
                </div>
              </div>
            ) : (
              ws.transactions.slice(0, 50).map((tx, i) => {
                const riskColor = tx.risk_level === 'CRITICAL' ? 'var(--red)' : tx.risk_level === 'HIGH' ? 'var(--orange)' : tx.risk_level === 'MEDIUM' ? 'var(--yellow)' : 'var(--green)';
                const isSuspicious = tx.prediction === 'FRAUD';
                return (
                  <div
                    key={`${tx.transaction_id}-${i}`}
                    className="tx-item"
                    onClick={() => navigate(`/investigate/${tx.transaction_id}`)}
                    style={{ animationDelay: `${Math.min(i * 20, 400)}ms`, borderLeft: isSuspicious ? `3px solid ${riskColor}` : '3px solid transparent' }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 1 }}>
                          <span className="tx-item-id" style={{ fontFamily: 'var(--mono)', fontSize: 10 }}>{tx.transaction_id}</span>
                          {isSuspicious && <span style={{ fontSize: 8, fontWeight: 800, padding: '1px 5px', borderRadius: 2, background: 'var(--red-dim)', color: 'var(--red)', letterSpacing: 0.5 }}>FRAUD</span>}
                        </div>
                        <div className="tx-item-amount" style={{ color: isSuspicious ? riskColor : 'var(--text-primary)', fontSize: 14, fontWeight: 700 }}>
                          ${tx.amount?.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                        </div>
                        <div className="tx-item-meta" style={{ gap: 4 }}>
                          <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{tx.merchant}</span>
                          <span style={{ color: 'var(--text-dim)' }}>·</span>
                          <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{tx.location}</span>
                        </div>
                      </div>
                      <div style={{ textAlign: 'right', flexShrink: 0, marginLeft: 12 }}>
                        <span className={`risk-badge risk-${tx.risk_level?.toLowerCase()}`} style={{ fontSize: 9 }}>{tx.risk_level}</span>
                        <div style={{ fontFamily: 'var(--mono)', fontSize: 13, fontWeight: 700, marginTop: 3, color: isSuspicious ? riskColor : 'var(--text-secondary)' }}>
                          {((tx.fraud_probability ?? 0) * 100).toFixed(0)}%
                        </div>
                      </div>
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>

        {/* Right: Risk + Alerts + ML Status */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <div className="card">
            <div className="card-header" style={{ padding: '8px 12px' }}><span className="card-title">Risk Distribution</span></div>
            <div style={{ padding: '0 12px 10px', display: 'flex', flexDirection: 'column', gap: 6 }}>
              {([{ level: 'CRITICAL', color: 'var(--red)', count: riskCounts.CRITICAL }, { level: 'HIGH', color: 'var(--orange)', count: riskCounts.HIGH }, { level: 'MEDIUM', color: 'var(--yellow)', count: riskCounts.MEDIUM }, { level: 'LOW', color: 'var(--green)', count: riskCounts.LOW }] as const).map(r => {
                const total = liveTotal || 1;
                const pct = (r.count / total) * 100;
                return (
                  <div key={r.level}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, marginBottom: 2 }}>
                      <span style={{ color: r.color, fontWeight: 700, letterSpacing: 0.5 }}>{r.level}</span>
                      <span style={{ fontFamily: 'var(--mono)', color: 'var(--text-muted)' }}>{r.count}</span>
                    </div>
                    <div style={{ height: 4, background: 'var(--bg-primary)', borderRadius: 2, overflow: 'hidden' }}>
                      <div style={{ height: '100%', width: `${Math.min(pct, 100)}%`, background: r.color, borderRadius: 2, transition: 'width 0.3s' }} />
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          <div className="card" style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
            <div className="card-header" style={{ padding: '8px 12px' }}>
              <span className="card-title">Active Alerts</span>
              {ws.alerts.length > 0 && <span style={{ fontSize: 9, fontWeight: 700, padding: '1px 6px', borderRadius: 3, background: 'var(--red-dim)', color: 'var(--red)' }}>{ws.alerts.length}</span>}
            </div>
            <div style={{ flex: 1, overflowY: 'auto' }}>
              {ws.alerts.length === 0 ? (
                <div style={{ padding: 20, textAlign: 'center', fontSize: 11, color: 'var(--text-dim)' }}>No active alerts</div>
              ) : (
                ws.alerts.slice(0, 10).map((alert, i) => (
                  <div key={i} style={{ padding: '8px 12px', borderBottom: '1px solid var(--border)', cursor: 'pointer', borderLeft: `3px solid ${alert.severity === 'CRITICAL' ? 'var(--red)' : 'var(--orange)'}` }} onClick={() => navigate(`/investigate/${alert.transaction_id}`)}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <span className={`risk-badge risk-${alert.severity?.toLowerCase()}`} style={{ fontSize: 8 }}>{alert.severity}</span>
                      <span style={{ fontSize: 9, fontFamily: 'var(--mono)', color: 'var(--text-dim)' }}>{alert.alert_id}</span>
                    </div>
                    <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 3 }}>{alert.reasons?.[0] || 'Suspicious activity'}</div>
                  </div>
                ))
              )}
            </div>
          </div>

          <div className="card" style={{ padding: 10 }}>
            <div className="card-title" style={{ fontSize: 9, marginBottom: 6 }}>ML PIPELINE</div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6 }}>
              {[{ label: 'MODELS', value: summary?.model_version ? '3 Active' : '—', color: 'var(--text-primary)' }, { label: 'ANOMALY', value: 'IsoForest', color: 'var(--cyan)' }, { label: 'RISK', value: 'Hybrid', color: 'var(--purple)' }, { label: 'VERSION', value: summary?.model_version ?? '—', color: 'var(--text-primary)' }].map(s => (
                <div key={s.label} style={{ padding: '4px 6px', background: 'var(--bg-primary)', borderRadius: 3 }}>
                  <div style={{ fontSize: 8, fontWeight: 600, color: 'var(--text-dim)', letterSpacing: 0.5 }}>{s.label}</div>
                  <div style={{ fontSize: 12, fontWeight: 700, fontFamily: 'var(--mono)', color: s.color }}>{s.value}</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
