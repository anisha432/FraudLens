import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { getTransactions } from '../api';

export default function Transactions() {
  const [txns, setTxns] = useState<any[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [riskFilter, setRiskFilter] = useState('');
  const [predFilter, setPredFilter] = useState('');
  const [search, setSearch] = useState('');
  const navigate = useNavigate();

  useEffect(() => {
    const params: Record<string, string | number> = { page, page_size: 30 };
    if (riskFilter) params.risk_level = riskFilter;
    if (predFilter) params.prediction = predFilter;
    if (search) params.search = search;
    getTransactions(params).then(d => {
      setTxns(d.transactions || []);
      setTotal(d.total || 0);
    }).catch(() => {});
  }, [page, riskFilter, predFilter, search]);

  const totalPages = Math.ceil(total / 30);

  return (
    <div className="fade-in" style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
        <div>
          <h1 style={{ fontSize: 18, fontWeight: 800 }}>Transaction Explorer</h1>
          <p style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>
            Search and filter processed transactions
          </p>
        </div>
        <span style={{ fontSize: 11, color: 'var(--text-muted)', fontFamily: 'var(--mono)' }}>
          {total.toLocaleString()} total
        </span>
      </div>

      {/* Filters */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 12, alignItems: 'center', flexWrap: 'wrap' }}>
        <input
          className="input"
          placeholder="Search transaction ID..."
          value={search}
          onChange={e => { setSearch(e.target.value); setPage(1); }}
          style={{ width: 220 }}
        />
        <select className="select" value={riskFilter} onChange={e => { setRiskFilter(e.target.value); setPage(1); }}>
          <option value="">All Risk Levels</option>
          <option value="LOW">Low</option>
          <option value="MEDIUM">Medium</option>
          <option value="HIGH">High</option>
          <option value="CRITICAL">Critical</option>
        </select>
        <select className="select" value={predFilter} onChange={e => { setPredFilter(e.target.value); setPage(1); }}>
          <option value="">All Predictions</option>
          <option value="FRAUD">Fraud</option>
          <option value="GENUINE">Genuine</option>
        </select>
        {totalPages > 1 && (
          <div style={{ marginLeft: 'auto', display: 'flex', gap: 6, alignItems: 'center' }}>
            <button className="btn btn-sm" disabled={page <= 1} onClick={() => setPage(p => p - 1)}>← Prev</button>
            <span style={{ fontSize: 11, color: 'var(--text-muted)', fontFamily: 'var(--mono)' }}>
              {page} / {totalPages}
            </span>
            <button className="btn btn-sm" disabled={page >= totalPages} onClick={() => setPage(p => p + 1)}>Next →</button>
          </div>
        )}
      </div>

      {/* Table */}
      <div className="card" style={{ flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
        <div style={{ flex: 1, overflow: 'auto' }}>
          <table className="data-table">
            <thead>
              <tr>
                <th>Transaction ID</th>
                <th>Amount</th>
                <th>Prediction</th>
                <th>Fraud Prob</th>
                <th>Anomaly</th>
                <th>Risk</th>
                <th>Risk Level</th>
                <th>Merchant</th>
                <th>Location</th>
              </tr>
            </thead>
            <tbody>
              {txns.map((t, i) => {
                const isFraud = t.prediction === 'FRAUD';
                return (
                  <tr key={i} style={{ cursor: 'pointer' }} onClick={() => navigate(`/investigate/${t.transaction_id}`)}>
                    <td style={{ fontFamily: 'var(--mono)', fontSize: 11 }}>{t.transaction_id}</td>
                    <td style={{
                      fontFamily: 'var(--mono)', fontWeight: 600,
                      color: isFraud ? 'var(--red)' : 'var(--text-primary)',
                    }}>
                      ${t.amount?.toLocaleString(undefined, { maximumFractionDigits: 2 })}
                    </td>
                    <td>
                      <span className={isFraud ? 'pred-fraud' : 'pred-genuine'}>{t.prediction || '—'}</span>
                    </td>
                    <td style={{ fontFamily: 'var(--mono)' }}>
                      {t.fraud_probability ? (t.fraud_probability * 100).toFixed(1) + '%' : '—'}
                    </td>
                    <td style={{ fontFamily: 'var(--mono)' }}>
                      {t.anomaly_score?.toFixed(2) ?? '—'}
                    </td>
                    <td style={{ fontFamily: 'var(--mono)' }}>
                      {t.risk_score?.toFixed(0) ?? '—'}
                    </td>
                    <td>
                      <span className={`risk-badge risk-${t.risk_level?.toLowerCase()}`}>{t.risk_level || '—'}</span>
                    </td>
                    <td>{t.merchant || '—'}</td>
                    <td>{t.location || '—'}</td>
                  </tr>
                );
              })}
              {txns.length === 0 && (
                <tr>
                  <td colSpan={9} style={{ textAlign: 'center', padding: 48, color: 'var(--text-muted)' }}>
                    <div style={{ fontSize: 32, marginBottom: 8, opacity: 0.3 }}>📋</div>
                    <div style={{ fontSize: 12 }}>No transactions found</div>
                    <div style={{ fontSize: 11, color: 'var(--text-dim)', marginTop: 4 }}>
                      Upload data, train models, and start simulation to see transactions
                    </div>
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
