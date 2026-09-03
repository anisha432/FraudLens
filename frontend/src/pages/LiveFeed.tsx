import { useNavigate } from 'react-router-dom';
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

export default function LiveFeed({ ws }: Props) {
  const navigate = useNavigate();

  const riskCounts = { CRITICAL: 0, HIGH: 0, MEDIUM: 0, LOW: 0 };
  ws.transactions.forEach(t => {
    const lvl = (t.risk_level || '').toUpperCase();
    if (lvl in riskCounts) riskCounts[lvl as keyof typeof riskCounts]++;
  });

  return (
    <div className="fade-in" style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <h1 style={{ fontSize: 18, fontWeight: 800 }}>Live Transaction Feed</h1>
            {ws.connected && (
              <span style={{
                fontSize: 9, fontWeight: 700, padding: '2px 8px', borderRadius: 3,
                background: 'var(--green-dim)', color: 'var(--green)', letterSpacing: 0.5,
              }}>● LIVE</span>
            )}
          </div>
          <p style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>
            Real-time stream of monitored transactions
          </p>
        </div>
        <div style={{ display: 'flex', gap: 16, alignItems: 'center' }}>
          {([
            { level: 'CRITICAL', color: 'var(--red)', count: riskCounts.CRITICAL },
            { level: 'HIGH', color: 'var(--orange)', count: riskCounts.HIGH },
            { level: 'MEDIUM', color: 'var(--yellow)', count: riskCounts.MEDIUM },
            { level: 'LOW', color: 'var(--green)', count: riskCounts.LOW },
          ] as const).map(r => (
            <div key={r.level} style={{ textAlign: 'center' }}>
              <div style={{ fontSize: 9, fontWeight: 700, color: r.color, letterSpacing: 0.5 }}>{r.level}</div>
              <div style={{ fontSize: 16, fontWeight: 800, fontFamily: 'var(--mono)', color: r.color }}>{r.count}</div>
            </div>
          ))}
        </div>
      </div>

      {/* Compact KPI strip */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
        {[
          { label: 'STREAMED', value: ws.stats.total },
          { label: 'FRAUD', value: ws.stats.fraud, color: 'var(--red)' },
          { label: 'CRITICAL', value: ws.stats.critical, color: 'var(--orange)' },
          { label: 'DETECTION', value: ws.stats.total > 0 ? ((ws.stats.fraud / ws.stats.total) * 100).toFixed(1) + '%' : '0.0%', color: 'var(--accent)' },
        ].map(k => (
          <div key={k.label} style={{
            flex: 1, padding: '6px 10px',
            background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 'var(--radius)',
          }}>
            <div style={{ fontSize: 9, fontWeight: 700, textTransform: 'uppercase', letterSpacing: 0.5, color: 'var(--text-dim)' }}>{k.label}</div>
            <div style={{ fontSize: 16, fontWeight: 800, fontFamily: 'var(--mono)', color: k.color || 'var(--text-primary)', lineHeight: 1.2 }}>{k.value}</div>
          </div>
        ))}
      </div>

      {/* Transaction Stream */}
      <div className="card" style={{ flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
        <div style={{ flex: 1, overflowY: 'auto' }}>
          {ws.transactions.length === 0 ? (
            <div className="empty-state" style={{ padding: 60 }}>
              <div style={{ fontSize: 48, marginBottom: 12, opacity: 0.3 }}>📡</div>
              <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-secondary)' }}>Waiting for live transactions</div>
              <div style={{ fontSize: 11, color: 'var(--text-dim)', marginTop: 4 }}>Start the simulation from the Command Center</div>
            </div>
          ) : (
            ws.transactions.map((tx, i) => {
              const riskColor = tx.risk_level === 'CRITICAL' ? 'var(--red)' : tx.risk_level === 'HIGH' ? 'var(--orange)' : tx.risk_level === 'MEDIUM' ? 'var(--yellow)' : 'var(--green)';
              const isSuspicious = tx.prediction === 'FRAUD';
              return (
                <div
                  key={`${tx.transaction_id}-${i}`}
                  className="tx-item"
                  onClick={() => navigate(`/investigate/${tx.transaction_id}`)}
                  style={{
                    animationDelay: `${Math.min(i * 20, 400)}ms`,
                    borderLeft: isSuspicious ? `3px solid ${riskColor}` : '3px solid transparent',
                    padding: '10px 14px',
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 2 }}>
                        <span style={{ fontFamily: 'var(--mono)', fontSize: 10, color: 'var(--text-dim)' }}>
                          {tx.transaction_id}
                        </span>
                        <span className={`risk-badge risk-${tx.risk_level?.toLowerCase()}`} style={{ fontSize: 8 }}>
                          {tx.risk_level}
                        </span>
                        {isSuspicious && (
                          <span style={{
                            fontSize: 8, fontWeight: 800, padding: '1px 5px', borderRadius: 2,
                            background: 'var(--red-dim)', color: 'var(--red)', letterSpacing: 0.5,
                          }}>FRAUD</span>
                        )}
                      </div>
                      <div style={{
                        fontSize: 15, fontWeight: 700, fontFamily: 'var(--mono)', lineHeight: 1.1,
                        color: isSuspicious ? riskColor : 'var(--text-primary)',
                      }}>
                        ${tx.amount?.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                      </div>
                      <div style={{ display: 'flex', gap: 6, fontSize: 10, color: 'var(--text-muted)', marginTop: 2, flexWrap: 'wrap' }}>
                        <span>{tx.merchant}</span>
                        <span style={{ color: 'var(--text-dim)' }}>·</span>
                        <span>{tx.location}</span>
                        <span style={{ color: 'var(--text-dim)' }}>·</span>
                        <span>{tx.device}</span>
                        <span style={{ color: 'var(--text-dim)' }}>·</span>
                        <span>{tx.payment_method}</span>
                      </div>
                    </div>
                    <div style={{ textAlign: 'right', flexShrink: 0, marginLeft: 16 }}>
                      <div style={{
                        fontFamily: 'var(--mono)', fontSize: 18, fontWeight: 700,
                        color: isSuspicious ? riskColor : 'var(--text-primary)',
                      }}>
                        {((tx.fraud_probability ?? 0) * 100).toFixed(1)}%
                      </div>
                      <div style={{ fontSize: 9, color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: 0.5 }}>fraud prob</div>
                      <div style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--text-muted)', marginTop: 3 }}>
                        Risk {(tx.risk_score ?? 0).toFixed(0)} · Anom {(tx.anomaly_score ?? 0).toFixed(2)}
                      </div>
                    </div>
                  </div>
                </div>
              );
            })
          )}
        </div>
      </div>
    </div>
  );
}
