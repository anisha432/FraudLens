import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { getAnalytics, getEDA, getExecutiveAnalytics } from '../api';

export default function Analytics() {
  const navigate = useNavigate();
  const [analytics, setAnalytics] = useState<any>(null);
  const [eda, setEda] = useState<any>(null);
  const [execData, setExecData] = useState<any>(null);
  const [activeTab, setActiveTab] = useState<'powerbi' | 'overview' | 'eda'>('powerbi');
  const [loading, setLoading] = useState(true);
  const [filters, setFilters] = useState<Record<string, string>>({});

  useEffect(() => {
    setLoading(true);
    Promise.all([
      getAnalytics().catch(() => null),
      getEDA().catch(() => null),
      getExecutiveAnalytics(filters).catch(() => null),
    ]).then(([a, e, ex]) => {
      setAnalytics(a);
      setEda(e);
      setExecData(ex);
      setLoading(false);
    });
  }, [JSON.stringify(filters)]);

  const kpi = execData?.kpi || {};
  const timeSeries = execData?.time_series || [];
  const riskIntel = execData?.risk_intelligence || {};
  const patterns = execData?.fraud_patterns || {};
  const temporal = execData?.temporal || {};
  const modelPerf = execData?.model_performance || {};
  const alertIntel = execData?.alert_intelligence || {};
  const topRisk = execData?.top_risk_transactions || [];
  const availFilters = execData?.available_filters || {};
  const riskDist = riskIntel.risk_distribution || {};
  const fpDist = riskIntel.fraud_probability_distribution || [];
  const rsDist = riskIntel.risk_score_distribution || [];

  // Simple bar chart component
  const BarChart = ({ data, labelKey, valueKey, fraudKey, maxH = 140, color = 'var(--accent)' }: any) => {
    const maxVal = Math.max(...(data || []).map((d: any) => d[valueKey] || 0), 1);
    return (
      <div style={{ display: 'flex', alignItems: 'flex-end', gap: 2, height: maxH, padding: '0 4px' }}>
        {(data || []).slice(0, 20).map((d: any, i: number) => (
          <div key={i} style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 1, minWidth: 20 }}>
            <span style={{ fontSize: 8, color: 'var(--text-muted)', fontFamily: 'var(--mono)' }}>{d[valueKey]}</span>
            <div style={{ position: 'relative', width: '100%' }}>
              <div style={{ width: '100%', height: `${((d[valueKey] || 0) / maxVal) * (maxH - 30)}px`, background: color, borderRadius: '2px 2px 0 0', minHeight: 2, opacity: 0.4 }} />
              {fraudKey && d[fraudKey] > 0 && (
                <div style={{ position: 'absolute', bottom: 0, width: '100%', height: `${((d[fraudKey] || 0) / maxVal) * (maxH - 30)}px`, background: 'var(--red)', borderRadius: '2px 2px 0 0', minHeight: 2 }} />
              )}
            </div>
            <span style={{ fontSize: 7, color: 'var(--text-muted)', textAlign: 'center', lineHeight: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: 60 }}>{d[labelKey]}</span>
          </div>
        ))}
      </div>
    );
  };

  // Horizontal bar chart
  const HBarChart = ({ data, labelKey, valueKey, fraudKey, maxH = 140 }: any) => {
    const maxVal = Math.max(...(data || []).map((d: any) => d[valueKey] || 0), 1);
    return (
      <div style={{ maxHeight: maxH, overflowY: 'auto' }}>
        {(data || []).slice(0, 12).map((d: any, i: number) => (
          <div key={i} style={{ marginBottom: 4 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, marginBottom: 1 }}>
              <span style={{ color: 'var(--text-secondary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: 120 }}>{d[labelKey]}</span>
              <span style={{ fontFamily: 'var(--mono)', color: 'var(--text-muted)', flexShrink: 0 }}>{d[valueKey]}</span>
            </div>
            <div style={{ display: 'flex', gap: 1, height: 6, borderRadius: 3, overflow: 'hidden' }}>
              <div style={{ width: `${((d[valueKey] || 0) / maxVal) * 100}%`, background: 'var(--accent)', opacity: 0.3, borderRadius: 3 }} />
              {fraudKey && d[fraudKey] > 0 && (
                <div style={{ width: `${((d[fraudKey] || 0) / maxVal) * 100}%`, background: 'var(--red)', borderRadius: 3 }} />
              )}
            </div>
          </div>
        ))}
      </div>
    );
  };

  const renderBar = (data: Record<string, number>, maxH = 120) => {
    const entries = Object.entries(data);
    const maxVal = Math.max(...entries.map(([, v]) => v), 1);
    return (
      <div style={{ display: 'flex', alignItems: 'flex-end', gap: 2, height: maxH, padding: '0 4px' }}>
        {entries.map(([k, v], i) => (
          <div key={i} style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 2 }}>
            <span style={{ fontSize: 8, color: 'var(--text-muted)', fontFamily: 'var(--mono)' }}>{v}</span>
            <div style={{ width: '100%', height: `${(v / maxVal) * (maxH - 20)}px`, background: 'var(--accent)', borderRadius: '2px 2px 0 0', minHeight: 2 }} />
            <span style={{ fontSize: 8, color: 'var(--text-muted)', textAlign: 'center', lineHeight: 1 }}>{k}</span>
          </div>
        ))}
      </div>
    );
  };

  return (
    <div className="fade-in">
      <div style={{ marginBottom: 12 }}>
        <h1 style={{ fontSize: 18, fontWeight: 800 }}>Analytics</h1>
        <p style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>Statistical analysis, fraud patterns and executive intelligence</p>
      </div>

      <div className="tabs">
        <button className={`tab ${activeTab === 'powerbi' ? 'active' : ''}`} onClick={() => setActiveTab('powerbi')}>Executive Dashboard</button>
        <button className={`tab ${activeTab === 'overview' ? 'active' : ''}`} onClick={() => setActiveTab('overview')}>Transaction Analytics</button>
        <button className={`tab ${activeTab === 'eda' ? 'active' : ''}`} onClick={() => setActiveTab('eda')}>EDA Summary</button>
      </div>

      {loading && (
        <div style={{ padding: 40, textAlign: 'center' }}>
          <div className="spinner" style={{ width: 20, height: 20 }} />
          <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 8 }}>Loading analytics...</div>
        </div>
      )}

      {/* ==================== POWER BI EXECUTIVE DASHBOARD ==================== */}
      {activeTab === 'powerbi' && !loading && (
        <div className="fade-in" style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {/* Dashboard Header */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div>
              <div style={{ fontSize: 13, fontWeight: 800, letterSpacing: '-0.3px' }}>FRAUD INTELLIGENCE — EXECUTIVE ANALYTICS</div>
              <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 2 }}>Transaction risk, fraud patterns and model intelligence</div>
            </div>
            {execData?.filters_applied && Object.keys(execData.filters_applied).length > 0 && (
              <button className="btn btn-sm" onClick={() => setFilters({})}>Clear Filters</button>
            )}
          </div>

          {/* Dashboard Filters / Slicers */}
          <div className="card" style={{ padding: '8px 14px' }}>
            <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
              <span style={{ fontSize: 9, fontWeight: 700, color: 'var(--text-dim)', letterSpacing: 0.5, textTransform: 'uppercase' }}>Filters:</span>
              <select className="select" style={{ width: 120, fontSize: 10, padding: '4px 8px' }} value={filters.risk_level || ''} onChange={e => setFilters(p => ({ ...p, risk_level: e.target.value }))}>
                <option value="">All Risk Levels</option>
                {(availFilters.risk_levels || []).map((r: string) => <option key={r} value={r}>{r}</option>)}
              </select>
              <select className="select" style={{ width: 110, fontSize: 10, padding: '4px 8px' }} value={filters.prediction || ''} onChange={e => setFilters(p => ({ ...p, prediction: e.target.value }))}>
                <option value="">All Predictions</option>
                {(availFilters.predictions || []).map((p: string) => <option key={p} value={p}>{p}</option>)}
              </select>
              <select className="select" style={{ width: 130, fontSize: 10, padding: '4px 8px' }} value={filters.merchant || ''} onChange={e => setFilters(p => ({ ...p, merchant: e.target.value }))}>
                <option value="">All Merchants</option>
                {(availFilters.merchants || []).slice(0, 20).map((m: string) => <option key={m} value={m}>{m}</option>)}
              </select>
              <select className="select" style={{ width: 120, fontSize: 10, padding: '4px 8px' }} value={filters.location || ''} onChange={e => setFilters(p => ({ ...p, location: e.target.value }))}>
                <option value="">All Locations</option>
                {(availFilters.locations || []).slice(0, 20).map((l: string) => <option key={l} value={l}>{l}</option>)}
              </select>
              {kpi.total_transactions === 0 && <span style={{ fontSize: 10, color: 'var(--text-muted)' }}>No data — start simulation to populate dashboard</span>}
            </div>
          </div>

          {/* ROW 1 — Executive KPI Cards */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', gap: 8 }}>
            {[
              { label: 'TOTAL TRANSACTIONS', value: kpi.total_transactions?.toLocaleString() || '0', color: 'var(--text-primary)' },
              { label: 'FRAUD TRANSACTIONS', value: kpi.fraud_transactions?.toLocaleString() || '0', color: 'var(--red)' },
              { label: 'FRAUD RATE', value: kpi.fraud_rate != null ? kpi.fraud_rate + '%' : '0%', color: 'var(--red)' },
              { label: 'HIGH + CRITICAL', value: kpi.high_critical_count?.toLocaleString() || '0', color: 'var(--orange)' },
              { label: 'TOTAL VALUE', value: kpi.total_value ? '$' + kpi.total_value.toLocaleString(undefined, { maximumFractionDigits: 0 }) : '$0', color: 'var(--text-primary)' },
              { label: 'FRAUD VALUE', value: kpi.fraud_value ? '$' + kpi.fraud_value.toLocaleString(undefined, { maximumFractionDigits: 0 }) : '$0', color: 'var(--red)' },
              { label: 'AVG RISK', value: kpi.avg_risk_score != null ? kpi.avg_risk_score.toFixed(1) : '—', color: 'var(--purple)' },
            ].map(k => (
              <div key={k.label} style={{ padding: '10px 12px', background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 6 }}>
                <div style={{ fontSize: 8, fontWeight: 700, textTransform: 'uppercase', letterSpacing: 0.5, color: 'var(--text-dim)', marginBottom: 4 }}>{k.label}</div>
                <div style={{ fontSize: 20, fontWeight: 800, fontFamily: 'var(--mono)', color: k.color, lineHeight: 1 }}>{k.value}</div>
              </div>
            ))}
          </div>

          {/* ROW 2 — Fraud Trend */}
          {timeSeries.length > 0 && (
            <div className="card">
              <div className="card-header"><span className="card-title">Fraud Trend — Transaction Volume vs Fraud Volume</span></div>
              <div style={{ padding: '0 14px 14px', overflowX: 'auto' }}>
                <BarChart data={timeSeries} labelKey="date" valueKey="total" fraudKey="fraud" maxH={160} />
                <div style={{ fontSize: 9, color: 'var(--text-muted)', textAlign: 'center', marginTop: 6 }}>Blue = Total Transactions | Red = Fraud</div>
              </div>
            </div>
          )}

          {/* ROW 3 — Risk Intelligence */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 12 }}>
            {/* Risk Distribution */}
            <div className="card">
              <div className="card-header"><span className="card-title">Risk Distribution</span></div>
              <div style={{ padding: '0 14px 14px' }}>
                {Object.entries(riskDist).map(([level, count]) => {
                  const total = kpi.total_transactions || 1;
                  const pct = ((count as number) / total) * 100;
                  const color = level === 'CRITICAL' ? 'var(--red)' : level === 'HIGH' ? 'var(--orange)' : level === 'MEDIUM' ? 'var(--yellow)' : 'var(--green)';
                  return (
                    <div key={level} style={{ marginBottom: 6 }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, marginBottom: 2 }}>
                        <span style={{ color, fontWeight: 700, letterSpacing: 0.5 }}>{level}</span>
                        <span style={{ fontFamily: 'var(--mono)', color: 'var(--text-muted)' }}>{String(count)}</span>
                      </div>
                      <div style={{ height: 6, background: 'var(--bg-primary)', borderRadius: 3, overflow: 'hidden' }}>
                        <div style={{ height: '100%', width: `${Math.min(pct, 100)}%`, background: color, borderRadius: 3 }} />
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Fraud Probability Distribution */}
            <div className="card">
              <div className="card-header"><span className="card-title">Fraud Probability Distribution</span></div>
              <div style={{ padding: '0 14px 14px' }}>
                <BarChart data={fpDist} labelKey="bucket" valueKey="count" maxH={120} color="var(--purple)" />
              </div>
            </div>

            {/* Risk Score Distribution */}
            <div className="card">
              <div className="card-header"><span className="card-title">Risk Score Distribution</span></div>
              <div style={{ padding: '0 14px 14px' }}>
                <BarChart data={rsDist} labelKey="bucket" valueKey="count" maxH={120} color="var(--orange)" />
              </div>
            </div>
          </div>

          {/* ROW 4 — Fraud Patterns */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 12 }}>
            <div className="card">
              <div className="card-header"><span className="card-title">Fraud by Merchant</span></div>
              <div style={{ padding: '0 14px 14px' }}>
                <HBarChart data={patterns.by_merchant} labelKey="merchant" valueKey="total" fraudKey="fraud" maxH={180} />
              </div>
            </div>
            <div className="card">
              <div className="card-header"><span className="card-title">Fraud by Location</span></div>
              <div style={{ padding: '0 14px 14px' }}>
                <HBarChart data={patterns.by_location} labelKey="location" valueKey="total" fraudKey="fraud" maxH={180} />
              </div>
            </div>
            <div className="card">
              <div className="card-header"><span className="card-title">Fraud by Amount Range</span></div>
              <div style={{ padding: '0 14px 14px' }}>
                <BarChart data={patterns.by_amount_range} labelKey="range" valueKey="total" fraudKey="fraud" maxH={140} />
              </div>
            </div>
          </div>

          {/* ROW 5 — Temporal Analytics */}
          {temporal.by_hour && temporal.by_hour.length > 0 && (
            <div className="card">
              <div className="card-header"><span className="card-title">Fraud by Hour of Day</span></div>
              <div style={{ padding: '0 14px 14px', overflowX: 'auto' }}>
                <BarChart data={temporal.by_hour} labelKey="hour" valueKey="total" fraudKey="fraud" maxH={120} />
                <div style={{ fontSize: 9, color: 'var(--text-muted)', textAlign: 'center', marginTop: 6 }}>Transaction activity by hour (0-23)</div>
              </div>
            </div>
          )}

          {/* ROW 6 — Model Performance */}
          {modelPerf.comparison && modelPerf.comparison.length > 0 && (
            <div className="card">
              <div className="card-header"><span className="card-title">Model Performance Comparison</span></div>
              <table className="data-table">
                <thead>
                  <tr><th>Model</th><th>Precision</th><th>Recall</th><th>F1</th><th>ROC-AUC</th></tr>
                </thead>
                <tbody>
                  {modelPerf.comparison.map((m: any, i: number) => (
                    <tr key={i}>
                      <td style={{ fontWeight: 700 }}>{m.model_name}</td>
                      <td style={{ fontFamily: 'var(--mono)' }}>{((m.metrics?.precision ?? 0) * 100).toFixed(1)}%</td>
                      <td style={{ fontFamily: 'var(--mono)' }}>{((m.metrics?.recall ?? 0) * 100).toFixed(1)}%</td>
                      <td style={{ fontFamily: 'var(--mono)', fontWeight: 700, color: 'var(--accent)' }}>{((m.metrics?.f1 ?? 0) * 100).toFixed(1)}%</td>
                      <td style={{ fontFamily: 'var(--mono)' }}>{((m.metrics?.roc_auc ?? 0) * 100).toFixed(1)}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* ROW 7 — Alert Intelligence */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
            <div className="card">
              <div className="card-header"><span className="card-title">Alert Intelligence</span></div>
              <div style={{ padding: '0 14px 14px' }}>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
                  <div style={{ padding: 8, background: 'var(--bg-primary)', borderRadius: 4 }}>
                    <div style={{ fontSize: 9, color: 'var(--text-dim)', textTransform: 'uppercase' }}>Total Alerts</div>
                    <div style={{ fontSize: 20, fontWeight: 800, fontFamily: 'var(--mono)' }}>{alertIntel.total_alerts}</div>
                  </div>
                  <div style={{ padding: 8, background: 'var(--bg-primary)', borderRadius: 4 }}>
                    <div style={{ fontSize: 9, color: 'var(--text-dim)', textTransform: 'uppercase' }}>Open</div>
                    <div style={{ fontSize: 20, fontWeight: 800, fontFamily: 'var(--mono)', color: 'var(--red)' }}>{alertIntel.open_alerts}</div>
                  </div>
                </div>
                <div style={{ marginTop: 8 }}>
                  <div style={{ fontSize: 9, color: 'var(--text-dim)', textTransform: 'uppercase', marginBottom: 4 }}>By Severity</div>
                  {Object.entries(alertIntel.by_severity || {}).map(([sev, count]) => (
                    <div key={sev} style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, padding: '2px 0' }}>
                      <span style={{ color: sev === 'CRITICAL' ? 'var(--red)' : sev === 'HIGH' ? 'var(--orange)' : 'var(--text-secondary)' }}>{sev}</span>
                      <span style={{ fontFamily: 'var(--mono)' }}>{String(count)}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* Top High-Risk Transactions */}
            <div className="card" style={{ overflow: 'hidden' }}>
              <div className="card-header"><span className="card-title">Top High-Risk Transactions</span></div>
              <div style={{ maxHeight: 250, overflowY: 'auto' }}>
                {topRisk.length === 0 ? (
                  <div style={{ padding: 20, textAlign: 'center', fontSize: 11, color: 'var(--text-muted)' }}>No transactions yet</div>
                ) : (
                  <table className="data-table" style={{ fontSize: 10 }}>
                    <thead>
                      <tr><th>Transaction</th><th>Amount</th><th>Fraud %</th><th>Risk</th><th>Level</th></tr>
                    </thead>
                    <tbody>
                      {topRisk.slice(0, 10).map((t: any, i: number) => (
                        <tr key={i} style={{ cursor: 'pointer' }} onClick={() => navigate(`/investigate/${t.transaction_id}`)}>
                          <td style={{ fontFamily: 'var(--mono)', fontSize: 9 }}>{t.transaction_id}</td>
                          <td style={{ fontFamily: 'var(--mono)', fontWeight: 600 }}>${t.amount?.toLocaleString(undefined, { maximumFractionDigits: 0 })}</td>
                          <td style={{ fontFamily: 'var(--mono)', color: t.fraud_probability > 50 ? 'var(--red)' : 'var(--text-secondary)' }}>{t.fraud_probability}%</td>
                          <td style={{ fontFamily: 'var(--mono)', fontWeight: 700, color: t.risk_score > 60 ? 'var(--red)' : 'var(--text-secondary)' }}>{t.risk_score}</td>
                          <td><span className={`risk-badge risk-${t.risk_level?.toLowerCase()}`} style={{ fontSize: 8 }}>{t.risk_level}</span></td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ==================== TRANSACTION ANALYTICS ==================== */}
      {activeTab === 'overview' && !loading && (
        <div className="fade-in">
          <div className="grid-2" style={{ marginBottom: 16 }}>
            <div className="card">
              <div className="card-header"><span className="card-title">Transaction Volume Over Time</span></div>
              {(!analytics?.time_series || analytics.time_series.length === 0) ? (
                <div className="empty-state" style={{ padding: 20 }}><div className="empty-state-text">No data yet</div></div>
              ) : (
                <div style={{ height: 180, overflowX: 'auto' }}>
                  <div style={{ display: 'flex', alignItems: 'flex-end', gap: 1, height: 140, padding: '0 4px', minWidth: analytics.time_series.length * 20 }}>
                    {analytics.time_series.map((d: any, i: number) => {
                      const maxTotal = Math.max(...analytics.time_series.map((x: any) => x.total), 1);
                      return (
                        <div key={i} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 1, minWidth: 16 }}>
                          <div style={{ width: 8, height: `${(d.total / maxTotal) * 120}px`, background: 'var(--accent)', borderRadius: '2px 2px 0 0', position: 'relative' }}>
                            {d.fraud > 0 && <div style={{ position: 'absolute', bottom: 0, width: '100%', height: `${(d.fraud / d.total) * 100}%`, background: 'var(--red)', borderRadius: '0 0 2px 2px' }} />}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                  <div style={{ fontSize: 9, color: 'var(--text-muted)', textAlign: 'center', marginTop: 4 }}>Blue = Total | Red portion = Fraud</div>
                </div>
              )}
            </div>

            <div className="card">
              <div className="card-header"><span className="card-title">Category Distribution</span></div>
              {(!analytics?.categories || analytics.categories.length === 0) ? (
                <div className="empty-state" style={{ padding: 20 }}><div className="empty-state-text">No data yet</div></div>
              ) : (
                <div style={{ maxHeight: 200, overflowY: 'auto' }}>
                  {analytics.categories.slice(0, 10).map((c: any, i: number) => {
                    const maxCat = analytics.categories[0]?.total || 1;
                    return (
                      <div key={i} style={{ marginBottom: 6 }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, marginBottom: 2 }}>
                          <span style={{ color: 'var(--text-secondary)' }}>{c.category}</span>
                          <span style={{ fontFamily: 'var(--mono)', color: 'var(--text-muted)' }}>{c.total}</span>
                        </div>
                        <div style={{ display: 'flex', gap: 2 }}>
                          <div style={{ height: 6, width: `${(c.total / maxCat) * 100}%`, background: 'var(--accent)', borderRadius: 3, opacity: 0.3 }} />
                          {c.fraud > 0 && <div style={{ height: 6, width: `${(c.fraud / c.total) * (c.total / maxCat) * 100}%`, background: 'var(--red)', borderRadius: 3 }} />}
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </div>

          {analytics?.ml_status && (
            <div className="card">
              <div className="card-header"><span className="card-title">ML Pipeline Status</span></div>
              <div className="grid-4">
                {Object.entries(analytics.ml_status).map(([k, v]) => (
                  <div key={k} style={{ padding: 8, background: 'var(--bg-primary)', borderRadius: 4 }}>
                    <div style={{ fontSize: 10, color: 'var(--text-muted)', textTransform: 'uppercase' }}>{k.replace(/_/g, ' ')}</div>
                    <div style={{ fontSize: 14, fontWeight: 700, fontFamily: 'var(--mono)', marginTop: 2 }}>{String(v)}</div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* ==================== EDA SUMMARY ==================== */}
      {activeTab === 'eda' && !loading && (
        <div className="fade-in">
          {!eda || (eda as any).message ? (
            <div className="card"><div className="empty-state"><div className="empty-state-icon">📊</div><div className="empty-state-text">Upload and process a dataset to see EDA results</div></div></div>
          ) : (
            <div className="grid-2">
              {(eda as any).amount_stats && (
                <div className="card">
                  <div className="card-header"><span className="card-title">Amount Statistics</span></div>
                  <div className="grid-2" style={{ gap: 8 }}>
                    {Object.entries((eda as any).amount_stats).map(([k, v]) => (
                      <div key={k} style={{ display: 'flex', justifyContent: 'space-between', padding: '6px 8px', background: 'var(--bg-primary)', borderRadius: 4 }}>
                        <span style={{ fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase' }}>{k}</span>
                        <span style={{ fontSize: 11, fontFamily: 'var(--mono)', fontWeight: 600 }}>{typeof v === 'number' ? v.toLocaleString(undefined, { maximumFractionDigits: 2 }) : String(v)}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
              {(eda as any).class_distribution && (
                <div className="card">
                  <div className="card-header"><span className="card-title">Class Distribution</span></div>
                  <div style={{ display: 'flex', gap: 24, marginBottom: 12 }}>
                    <div>
                      <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>Genuine</div>
                      <div style={{ fontSize: 24, fontWeight: 700, color: 'var(--green)', fontFamily: 'var(--mono)' }}>{(eda as any).class_distribution.genuine?.toLocaleString()}</div>
                    </div>
                    <div>
                      <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>Fraud</div>
                      <div style={{ fontSize: 24, fontWeight: 700, color: 'var(--red)', fontFamily: 'var(--mono)' }}>{(eda as any).class_distribution.fraud?.toLocaleString()}</div>
                    </div>
                  </div>
                  <div style={{ display: 'flex', height: 16, borderRadius: 4, overflow: 'hidden' }}>
                    <div style={{ width: `${((eda as any).class_distribution.genuine || 0) / (((eda as any).class_distribution.genuine || 0) + ((eda as any).class_distribution.fraud || 0)) * 100}%`, background: 'var(--green)', opacity: 0.6 }} />
                    <div style={{ width: `${((eda as any).class_distribution.fraud || 0) / (((eda as any).class_distribution.genuine || 0) + ((eda as any).class_distribution.fraud || 0)) * 100}%`, background: 'var(--red)', opacity: 0.8 }} />
                  </div>
                </div>
              )}
              {(eda as any).time_analysis?.hour_distribution && (
                <div className="card">
                  <div className="card-header"><span className="card-title">Hour Distribution</span></div>
                  {renderBar((eda as any).time_analysis.hour_distribution, 100)}
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
