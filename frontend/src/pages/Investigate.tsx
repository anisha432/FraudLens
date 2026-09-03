import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { getTransaction, getExplanation } from '../api';

export default function Investigate() {
  const { txId } = useParams();
  const navigate = useNavigate();
  const [tx, setTx] = useState<any>(null);
  const [explanation, setExplanation] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!txId) return;
    setLoading(true);
    Promise.all([
      getTransaction(txId).catch(() => null),
      getExplanation(txId).catch(() => null),
    ]).then(([txData, expData]) => {
      setTx(txData);
      setExplanation(expData);
      setLoading(false);
    });
  }, [txId]);

  if (!txId) {
    return (
      <div className="fade-in">
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
          <h1 style={{ fontSize: 18, fontWeight: 800 }}>Investigation Workspace</h1>
        </div>
        <p style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 16 }}>
          Select a transaction from the Live Feed or Transaction Explorer to begin investigation
        </p>
        <div className="card">
          <div className="empty-state" style={{ padding: 60 }}>
            <div style={{ fontSize: 48, marginBottom: 12, opacity: 0.3 }}>🔍</div>
            <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-secondary)' }}>No Transaction Selected</div>
            <div style={{ fontSize: 11, color: 'var(--text-dim)', marginTop: 4 }}>
              Click any transaction from the Command Center or Live Feed to open the investigation workspace
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (loading) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '60vh' }}>
        <div style={{ textAlign: 'center' }}>
          <div className="spinner" style={{ width: 24, height: 24 }} />
          <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 8 }}>Loading investigation...</div>
        </div>
      </div>
    );
  }

  if (!tx || tx.error) {
    return (
      <div className="fade-in">
        <h1 style={{ fontSize: 18, fontWeight: 800, marginBottom: 4 }}>Transaction Not Found</h1>
        <p style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 16 }}>
          Transaction {txId} not found. It may be a simulated transaction not stored in the database.
        </p>
        <button className="btn btn-sm" onClick={() => navigate('/transactions')}>← Back to Transactions</button>
      </div>
    );
  }

  const riskColor = tx.risk_level === 'CRITICAL' ? 'var(--red)' : tx.risk_level === 'HIGH' ? 'var(--orange)' : tx.risk_level === 'MEDIUM' ? 'var(--yellow)' : 'var(--green)';
  const topFeatures = explanation?.contributions?.slice(0, 10) || [];
  const maxShap = topFeatures.length > 0 ? Math.max(...topFeatures.map((f: any) => Math.abs(f.shap_value ?? 0)), 0.001) : 0.001;
  const isFraud = tx.prediction === 'FRAUD';

  // Build network nodes for the behavioral graph
  const networkNodes = [
    { id: 'tx', label: 'Transaction', value: tx.transaction_id, color: riskColor, x: 200, y: 40 },
    { id: 'user', label: 'User', value: tx.user_id || 'N/A', color: 'var(--cyan)', x: 60, y: 130 },
    { id: 'merchant', label: 'Merchant', value: tx.merchant || 'N/A', color: 'var(--purple)', x: 200, y: 130 },
    { id: 'location', label: 'Location', value: tx.location || 'N/A', color: 'var(--yellow)', x: 340, y: 130 },
    { id: 'device', label: 'Device', value: tx.device || 'N/A', color: 'var(--orange)', x: 120, y: 220 },
    { id: 'payment', label: 'Payment', value: tx.payment_method || 'N/A', color: 'var(--green)', x: 280, y: 220 },
  ];

  return (
    <div className="fade-in" style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <button className="btn btn-sm" onClick={() => navigate(-1)}>←</button>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <h1 style={{ fontSize: 18, fontWeight: 800 }}>Investigation</h1>
              <span style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--text-muted)' }}>{tx.transaction_id}</span>
            </div>
            <p style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 1 }}>
              Deep-dive analysis of transaction risk factors and behavioral patterns
            </p>
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span className={`risk-badge risk-${tx.risk_level?.toLowerCase()}`} style={{ fontSize: 11, padding: '4px 10px' }}>
            {tx.risk_level}
          </span>
          {isFraud && (
            <span style={{
              fontSize: 10, fontWeight: 800, padding: '4px 10px', borderRadius: 3,
              background: 'var(--red-dim)', color: 'var(--red)', letterSpacing: 0.5,
            }}>⚠ FRAUD</span>
          )}
        </div>
      </div>

      {/* Top Row: Transaction Details + Risk Score */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 320px', gap: 12 }}>
        {/* Transaction Identity */}
        <div className="card">
          <div className="card-header" style={{ padding: '8px 14px' }}>
            <span className="card-title">Transaction Details</span>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 0 }}>
            {[
              ['Amount', `$${tx.amount?.toLocaleString(undefined, { maximumFractionDigits: 2 })}`, 'var(--mono)', true],
              ['User ID', tx.user_id || '—', 'var(--mono)', false],
              ['Merchant', tx.merchant || '—', '', false],
              ['Category', tx.category || '—', '', false],
              ['Location', tx.location || '—', '', false],
              ['Country', tx.country || '—', '', false],
              ['Device', tx.device || '—', '', false],
              ['Payment', tx.payment_method || '—', '', false],
              ['Timestamp', tx.timestamp ? new Date(tx.timestamp).toLocaleString() : '—', 'var(--mono)', false],
            ].map(([label, value, font, highlight]) => (
              <div key={label as string} style={{ padding: '8px 14px', borderBottom: '1px solid rgba(30,41,59,0.5)' }}>
                <div style={{ fontSize: 9, fontWeight: 600, textTransform: 'uppercase', letterSpacing: 0.5, color: 'var(--text-dim)' }}>
                  {label}
                </div>
                <div style={{
                  fontSize: highlight ? 18 : 12, fontWeight: highlight ? 700 : 500,
                  fontFamily: font || 'inherit', color: highlight ? riskColor : 'var(--text-primary)',
                  marginTop: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                }}>
                  {value}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Risk Analysis Panel */}
        <div className="card" style={{ display: 'flex', flexDirection: 'column' }}>
          <div className="card-header" style={{ padding: '8px 14px' }}>
            <span className="card-title">Risk Analysis</span>
          </div>
          <div style={{ flex: 1, padding: '0 14px 14px', display: 'flex', flexDirection: 'column', gap: 10 }}>
            {/* Risk Score Circle */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
              <div style={{
                width: 80, height: 80, borderRadius: '50%',
                border: `4px solid ${riskColor}`,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                flexDirection: 'column', flexShrink: 0,
              }}>
                <div style={{ fontSize: 24, fontWeight: 800, fontFamily: 'var(--mono)', color: riskColor, lineHeight: 1 }}>
                  {tx.risk_score?.toFixed(0) ?? '—'}
                </div>
                <div style={{ fontSize: 8, color: 'var(--text-dim)' }}>/ 100</div>
              </div>
              <div style={{ flex: 1 }}>
                <div style={{ marginBottom: 6 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, marginBottom: 2 }}>
                    <span style={{ color: 'var(--text-muted)' }}>Fraud Probability</span>
                    <span style={{ fontFamily: 'var(--mono)', fontWeight: 700, color: isFraud ? 'var(--red)' : 'var(--text-primary)' }}>
                      {tx.fraud_probability ? (tx.fraud_probability * 100).toFixed(1) + '%' : '—'}
                    </span>
                  </div>
                  <div style={{ height: 4, background: 'var(--bg-primary)', borderRadius: 2, overflow: 'hidden' }}>
                    <div style={{ height: '100%', width: `${(tx.fraud_probability ?? 0) * 100}%`, background: isFraud ? 'var(--red)' : 'var(--accent)', borderRadius: 2 }} />
                  </div>
                </div>
                <div style={{ marginBottom: 6 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, marginBottom: 2 }}>
                    <span style={{ color: 'var(--text-muted)' }}>Anomaly Score</span>
                    <span style={{ fontFamily: 'var(--mono)', fontWeight: 700 }}>
                      {tx.anomaly_score?.toFixed(2) ?? '—'}
                    </span>
                  </div>
                  <div style={{ height: 4, background: 'var(--bg-primary)', borderRadius: 2, overflow: 'hidden' }}>
                    <div style={{ height: '100%', width: `${(tx.anomaly_score ?? 0) * 100}%`, background: 'var(--purple)', borderRadius: 2 }} />
                  </div>
                </div>
              </div>
            </div>

            {/* Prediction */}
            <div style={{
              padding: '8px 10px', borderRadius: 4,
              background: isFraud ? 'var(--red-dim)' : 'var(--green-dim)',
              border: `1px solid ${isFraud ? 'rgba(239,68,68,0.3)' : 'rgba(34,197,94,0.3)'}`,
            }}>
              <div style={{ fontSize: 9, fontWeight: 600, textTransform: 'uppercase', letterSpacing: 0.5, color: 'var(--text-dim)' }}>
                ML Prediction
              </div>
              <div style={{ fontSize: 16, fontWeight: 800, color: isFraud ? 'var(--red)' : 'var(--green)', marginTop: 2 }}>
                {tx.prediction || 'UNKNOWN'}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Middle Row: Why Flagged + Behavioral Network */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
        {/* WHY FLAGGED — Forensic explanation */}
        <div className="card" style={{ display: 'flex', flexDirection: 'column' }}>
          <div className="card-header" style={{ padding: '8px 14px' }}>
            <span className="card-title" style={{ color: isFraud ? 'var(--red)' : undefined }}>
              {isFraud ? 'Why Was This Flagged?' : 'Risk Analysis'}
            </span>
          </div>
          <div style={{ flex: 1, padding: '0 14px 14px', overflowY: 'auto' }}>
            {topFeatures.length > 0 ? (
              <div>
                {topFeatures.map((f: any, i: number) => {
                  const absVal = Math.abs(f.shap_value ?? 0);
                  const pct = (absVal / maxShap) * 100;
                  const isPositive = (f.shap_value ?? 0) > 0;
                  return (
                    <div key={i} style={{ marginBottom: 8 }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 3 }}>
                        <span style={{ fontSize: 11, color: 'var(--text-secondary)', fontWeight: 500, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: 200 }}>
                          {f.feature}
                        </span>
                        <span style={{
                          fontSize: 11, fontFamily: 'var(--mono)', fontWeight: 700,
                          color: isPositive ? 'var(--red)' : 'var(--green)',
                        }}>
                          {isPositive ? '+' : ''}{(f.shap_value ?? 0).toFixed(4)}
                        </span>
                      </div>
                      <div style={{ height: 6, background: 'var(--bg-primary)', borderRadius: 3, overflow: 'hidden' }}>
                        <div style={{
                          height: '100%', width: `${pct}%`,
                          background: isPositive ? 'var(--red)' : 'var(--green)',
                          borderRadius: 3, transition: 'width 0.5s',
                        }} />
                      </div>
                      {f.direction && (
                        <span style={{ fontSize: 9, color: isPositive ? 'var(--red)' : 'var(--green)', fontWeight: 600 }}>
                          {isPositive ? '↑ Increases risk' : '↓ Decreases risk'}
                        </span>
                      )}
                    </div>
                  );
                })}
              </div>
            ) : explanation?.explanation_text ? (
              <div>
                {explanation.explanation_text.map((t: string, i: number) => (
                  <div key={i} style={{
                    fontSize: 12, color: 'var(--text-secondary)', padding: '6px 10px',
                    background: 'var(--bg-primary)', borderRadius: 4, marginBottom: 4,
                    borderLeft: '2px solid var(--accent)',
                  }}>
                    {t}
                  </div>
                ))}
              </div>
            ) : (
              <div style={{ padding: 20, textAlign: 'center', fontSize: 12, color: 'var(--text-muted)' }}>
                No explanation available. Train a model first.
              </div>
            )}
          </div>
        </div>

        {/* Behavioral Network Graph */}
        <div className="card" style={{ display: 'flex', flexDirection: 'column' }}>
          <div className="card-header" style={{ padding: '8px 14px' }}>
            <span className="card-title">Behavioral Network</span>
          </div>
          <div style={{ flex: 1, padding: 10, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <svg width="400" height="260" viewBox="0 0 400 260" style={{ maxWidth: '100%' }}>
              {/* Edges */}
              {networkNodes.slice(1).map(node => (
                <line
                  key={`edge-${node.id}`}
                  x1={networkNodes[0].x}
                  y1={networkNodes[0].y + 18}
                  x2={node.x}
                  y2={node.y - 4}
                  stroke="var(--border-light)"
                  strokeWidth="1"
                  strokeDasharray="4,3"
                  opacity="0.5"
                />
              ))}

              {/* Nodes */}
              {networkNodes.map(node => {
                const textLen = node.value.length * 6 + 20;
                const w = Math.max(90, Math.min(textLen, 140));
                return (
                  <g key={node.id} style={{ cursor: 'pointer' }}>
                    <rect
                      x={node.x - w / 2}
                      y={node.y - 12}
                      width={w}
                      height={node.id === 'tx' ? 36 : 30}
                      rx="6"
                      fill="var(--bg-card)"
                      stroke={node.color}
                      strokeWidth={node.id === 'tx' ? 2 : 1}
                      opacity="0.95"
                    />
                    <text
                      x={node.x}
                      y={node.y + 2}
                      textAnchor="middle"
                      fill={node.color}
                      fontSize="8"
                      fontWeight="700"
                      letterSpacing="0.5"
                    >
                      {node.label.toUpperCase()}
                    </text>
                    <text
                      x={node.x}
                      y={node.y + 13}
                      textAnchor="middle"
                      fill="var(--text-secondary)"
                      fontSize="10"
                      fontWeight="600"
                      fontFamily="var(--mono)"
                    >
                      {node.value.length > 18 ? node.value.slice(0, 16) + '…' : node.value}
                    </text>
                  </g>
                );
              })}
            </svg>
          </div>
        </div>
      </div>
    </div>
  );
}
