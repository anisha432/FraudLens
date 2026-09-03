import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { getAlerts, updateAlert } from '../api';

export default function Alerts() {
  const [alerts, setAlerts] = useState<any[]>([]);
  const [total, setTotal] = useState(0);
  const [statusFilter, setStatusFilter] = useState('');
  const [severityFilter, setSeverityFilter] = useState('');
  const navigate = useNavigate();

  const fetchAlerts = () => {
    const params: Record<string, string | number> = { page_size: 100 };
    if (statusFilter) params.status = statusFilter;
    if (severityFilter) params.severity = severityFilter;
    getAlerts(params).then(d => {
      setAlerts(d.alerts || []);
      setTotal(d.total || 0);
    }).catch(() => {});
  };

  useEffect(() => { fetchAlerts(); }, [statusFilter, severityFilter]);

  const handleStatusChange = async (alertId: string, newStatus: string) => {
    await updateAlert(alertId, { status: newStatus });
    fetchAlerts();
  };

  const sevCounts = { CRITICAL: 0, HIGH: 0, MEDIUM: 0, LOW: 0 };
  alerts.forEach(a => {
    const s = (a.severity || '').toUpperCase();
    if (s in sevCounts) sevCounts[s as keyof typeof sevCounts]++;
  });

  const statusBadgeColor: Record<string, string> = {
    OPEN: 'var(--red-dim)',
    REVIEWING: 'var(--yellow-dim)',
    RESOLVED: 'var(--green-dim)',
    FALSE_POSITIVE: 'var(--bg-elevated)',
  };

  return (
    <div className="fade-in">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
        <div>
          <h1 style={{ fontSize: 18, fontWeight: 800 }}>Alert Center</h1>
          <p style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>
            Investigate and manage fraud alerts
          </p>
        </div>
        <div style={{ display: 'flex', gap: 12 }}>
          {Object.entries(sevCounts).map(([k, v]) => v > 0 && (
            <div key={k} style={{ textAlign: 'center' }}>
              <div style={{
                fontSize: 9, fontWeight: 700, letterSpacing: 0.5,
                color: k === 'CRITICAL' ? 'var(--red)' : k === 'HIGH' ? 'var(--orange)' : k === 'MEDIUM' ? 'var(--yellow)' : 'var(--green)',
              }}>{k}</div>
              <div style={{
                fontSize: 14, fontWeight: 800, fontFamily: 'var(--mono)',
                color: k === 'CRITICAL' ? 'var(--red)' : k === 'HIGH' ? 'var(--orange)' : k === 'MEDIUM' ? 'var(--yellow)' : 'var(--green)',
              }}>{v}</div>
            </div>
          ))}
        </div>
      </div>

      {/* Filters */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 14, alignItems: 'center' }}>
        <select className="select" value={severityFilter} onChange={e => setSeverityFilter(e.target.value)}>
          <option value="">All Severities</option>
          <option value="CRITICAL">Critical</option>
          <option value="HIGH">High</option>
          <option value="MEDIUM">Medium</option>
          <option value="LOW">Low</option>
        </select>
        <select className="select" value={statusFilter} onChange={e => setStatusFilter(e.target.value)}>
          <option value="">All Statuses</option>
          <option value="OPEN">Open</option>
          <option value="REVIEWING">Reviewing</option>
          <option value="RESOLVED">Resolved</option>
          <option value="FALSE_POSITIVE">False Positive</option>
        </select>
        <span style={{ fontSize: 11, color: 'var(--text-muted)', marginLeft: 'auto' }}>{total} alerts</span>
      </div>

      {alerts.length === 0 ? (
        <div className="card">
          <div className="empty-state" style={{ padding: 60 }}>
            <div style={{ fontSize: 48, marginBottom: 12, opacity: 0.3 }}>🔔</div>
            <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-secondary)' }}>No Alerts</div>
            <div style={{ fontSize: 11, color: 'var(--text-dim)', marginTop: 4 }}>
              Alerts are generated when transactions exceed risk thresholds
            </div>
          </div>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          {alerts.map((a, i) => (
            <div
              key={i}
              className="card"
              style={{
                padding: '10px 14px',
                borderLeft: `3px solid ${a.severity === 'CRITICAL' ? 'var(--red)' : a.severity === 'HIGH' ? 'var(--orange)' : a.severity === 'MEDIUM' ? 'var(--yellow)' : 'var(--green)'}`,
                cursor: 'pointer',
              }}
              onClick={() => navigate(`/investigate/${a.transaction_id}`)}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
                    <span className={`risk-badge risk-${a.severity?.toLowerCase()}`} style={{ fontSize: 8 }}>{a.severity}</span>
                    <span style={{ fontFamily: 'var(--mono)', fontSize: 10, color: 'var(--text-dim)' }}>{a.alert_id}</span>
                    <span style={{
                      fontSize: 9, padding: '2px 6px', borderRadius: 3,
                      background: statusBadgeColor[a.status] || 'var(--bg-elevated)',
                      color: a.status === 'OPEN' ? 'var(--red)' : a.status === 'REVIEWING' ? 'var(--yellow)' : 'var(--text-secondary)',
                      fontWeight: 600,
                    }}>{a.status}</span>
                  </div>
                  <div style={{ fontSize: 11, color: 'var(--text-secondary)' }}>
                    TX: <span style={{ fontFamily: 'var(--mono)', color: 'var(--accent)' }}>{a.transaction_id}</span>
                  </div>
                  {a.reasons && a.reasons.length > 0 && (
                    <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4 }}>
                      {a.reasons.slice(0, 2).map((r: string, j: number) => <div key={j}>• {r}</div>)}
                    </div>
                  )}
                  <div style={{ fontSize: 10, color: 'var(--text-dim)', marginTop: 4, fontFamily: 'var(--mono)' }}>
                    Risk: {a.risk_score?.toFixed(0) ?? '—'} · {a.created_at ? new Date(a.created_at).toLocaleString() : '—'}
                  </div>
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 4, flexShrink: 0 }} onClick={e => e.stopPropagation()}>
                  {a.status === 'OPEN' && (
                    <>
                      <button className="btn btn-sm" onClick={() => handleStatusChange(a.alert_id, 'REVIEWING')}>Review</button>
                      <button className="btn btn-sm" onClick={() => handleStatusChange(a.alert_id, 'FALSE_POSITIVE')}>False Positive</button>
                    </>
                  )}
                  {a.status === 'REVIEWING' && (
                    <button className="btn btn-sm btn-success" onClick={() => handleStatusChange(a.alert_id, 'RESOLVED')}>Resolve</button>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
