import { useState, useEffect } from 'react';
import { getModelComparison, getThresholdAnalysis, getFeatureImportance } from '../api';

export default function ModelLab() {
  const [models, setModels] = useState<any[]>([]);
  const [thresholds, setThresholds] = useState<any[]>([]);
  const [features, setFeatures] = useState<any>(null);
  const [selectedThreshold, setSelectedThreshold] = useState(0.5);
  const [activeTab, setActiveTab] = useState<'compare' | 'threshold' | 'features'>('compare');

  useEffect(() => {
    getModelComparison().then(d => setModels(d.models || [])).catch(() => {});
    getThresholdAnalysis().then(d => setThresholds(d.thresholds || [])).catch(() => {});
    getFeatureImportance().then(d => setFeatures(d)).catch(() => {});
  }, []);

  const currentThreshold = thresholds.find(t => Math.abs(t.threshold - selectedThreshold) < 0.01);

  return (
    <div className="fade-in">
      <div style={{ marginBottom: 12 }}>
        <h1 style={{fontSize:18, fontWeight:800}}>Model Lab</h1>
        <p style={{fontSize:11, color:'var(--text-muted)', marginTop:2}}>Machine learning model comparison, diagnostics, and threshold optimization</p>
      </div>

      <div className="tabs">
        <button className={`tab ${activeTab === 'compare' ? 'active' : ''}`} onClick={() => setActiveTab('compare')}>Model Comparison</button>
        <button className={`tab ${activeTab === 'threshold' ? 'active' : ''}`} onClick={() => setActiveTab('threshold')}>Threshold Tuning</button>
        <button className={`tab ${activeTab === 'features' ? 'active' : ''}`} onClick={() => setActiveTab('features')}>Feature Importance</button>
      </div>

      {activeTab === 'compare' && (
        <div className="fade-in">
          {models.length === 0 ? (
            <div className="card"><div className="empty-state"><div className="empty-state-icon">🧪</div><div className="empty-state-text">No models trained yet. Upload a dataset and train models first.</div></div></div>
          ) : (
            <div className="card">
              <div className="card-header"><span className="card-title">Model Performance Comparison</span></div>
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Model</th><th>Precision</th><th>Recall</th><th>F1 Score</th><th>PR-AUC</th><th>ROC-AUC</th><th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {models.map((m, i) => (
                    <tr key={i}>
                      <td style={{fontWeight:700, color:'var(--text-primary)'}}>{m.model_name}</td>
                      <td style={{fontFamily:'var(--mono)'}}>{((m.metrics?.precision ?? 0) * 100).toFixed(1)}%</td>
                      <td style={{fontFamily:'var(--mono)'}}>{((m.metrics?.recall ?? 0) * 100).toFixed(1)}%</td>
                      <td style={{fontFamily:'var(--mono)', fontWeight:700, color:'var(--accent)'}}>{((m.metrics?.f1 ?? 0) * 100).toFixed(1)}%</td>
                      <td style={{fontFamily:'var(--mono)'}}>{((m.metrics?.pr_auc ?? 0) * 100).toFixed(1)}%</td>
                      <td style={{fontFamily:'var(--mono)'}}>{((m.metrics?.roc_auc ?? 0) * 100).toFixed(1)}%</td>
                      <td><span className="risk-badge risk-low">Active</span></td>
                    </tr>
                  ))}
                </tbody>
              </table>

              {/* Visual comparison bars */}
              <div style={{marginTop:20}}>
                <div className="section-title">F1 Score Comparison</div>
                {models.map((m, i) => (
                  <div key={i} className="explain-bar">
                    <div className="explain-bar-label">{m.model_name}</div>
                    <div className="explain-bar-track">
                      <div className="explain-bar-fill" style={{width:`${m.metrics.f1 * 100}%`, background:'var(--accent)'}} />
                    </div>
                    <div className="explain-bar-value">{((m.metrics?.f1 ?? 0) * 100).toFixed(1)}%</div>
                  </div>
                ))}
              </div>

              <div style={{marginTop:16}}>
                <div className="section-title">ROC-AUC Comparison</div>
                {models.map((m, i) => (
                  <div key={i} className="explain-bar">
                    <div className="explain-bar-label">{m.model_name}</div>
                    <div className="explain-bar-track">
                      <div className="explain-bar-fill" style={{width:`${(m.metrics?.roc_auc ?? 0) * 100}%`, background:'var(--purple)'}} />
                    </div>
                    <div className="explain-bar-value">{((m.metrics?.roc_auc ?? 0) * 100).toFixed(1)}%</div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {activeTab === 'threshold' && (
        <div className="fade-in">
          <div className="card" style={{marginBottom:16}}>
            <div className="card-header"><span className="card-title">Threshold Tuning</span></div>
            <p style={{fontSize:12, color:'var(--text-secondary)', marginBottom:16}}>
              Adjust the classification threshold to balance precision and recall for fraud detection.
              Lower thresholds catch more fraud but increase false positives.
            </p>

            <div style={{marginBottom:16}}>
              <div style={{display:'flex', justifyContent:'space-between', marginBottom:4}}>
                <span style={{fontSize:12, color:'var(--text-secondary)'}}>Threshold</span>
                <span style={{fontSize:16, fontWeight:700, fontFamily:'var(--mono)', color:'var(--accent)'}}>{(selectedThreshold * 100).toFixed(0)}%</span>
              </div>
              <input
                type="range"
                min={0.05}
                max={0.95}
                step={0.05}
                value={selectedThreshold}
                onChange={e => setSelectedThreshold(parseFloat(e.target.value))}
              />
              <div style={{display:'flex', justifyContent:'space-between', fontSize:10, color:'var(--text-muted)', marginTop:4}}>
                <span>More Fraud Caught (lower threshold)</span>
                <span>Fewer False Positives (higher threshold)</span>
              </div>
            </div>

            {currentThreshold && (
              <div className="stats-row">
                <div className="stat-card">
                  <div className="stat-label">Precision</div>
                  <div className="stat-value">{((currentThreshold?.precision ?? 0) * 100).toFixed(1)}%</div>
                </div>
                <div className="stat-card">
                  <div className="stat-label">Recall</div>
                  <div className="stat-value">{((currentThreshold?.recall ?? 0) * 100).toFixed(1)}%</div>
                </div>
                <div className="stat-card">
                  <div className="stat-label">F1 Score</div>
                  <div className="stat-value" style={{color:'var(--accent)'}}>{((currentThreshold?.f1 ?? 0) * 100).toFixed(1)}%</div>
                </div>
                <div className="stat-card">
                  <div className="stat-label">Flagged</div>
                  <div className="stat-value">{currentThreshold.flagged_count}</div>
                </div>
              </div>
            )}
          </div>

          {/* Threshold analysis table */}
          {thresholds.length > 0 && (
            <div className="card">
              <div className="card-header"><span className="card-title">Threshold Analysis</span></div>
              <table className="data-table">
                <thead>
                  <tr><th>Threshold</th><th>Precision</th><th>Recall</th><th>F1</th><th>Flagged Count</th></tr>
                </thead>
                <tbody>
                  {thresholds.map((t, i) => (
                    <tr key={i} style={{
                      background: Math.abs(t.threshold - selectedThreshold) < 0.01 ? 'rgba(59,130,246,0.1)' : 'transparent',
                    }}>
                      <td style={{fontFamily:'var(--mono)', fontWeight: Math.abs(t.threshold - selectedThreshold) < 0.01 ? 700 : 400}}>
                        {((t.threshold ?? 0) * 100).toFixed(0)}%
                      </td>
                      <td style={{fontFamily:'var(--mono)'}}>{((t.precision ?? 0) * 100).toFixed(1)}%</td>
                      <td style={{fontFamily:'var(--mono)'}}>{((t.recall ?? 0) * 100).toFixed(1)}%</td>
                      <td style={{fontFamily:'var(--mono)', fontWeight:700}}>{((t.f1 ?? 0) * 100).toFixed(1)}%</td>
                      <td style={{fontFamily:'var(--mono)'}}>{t.flagged_count}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {activeTab === 'features' && (
        <div className="fade-in">
          <div className="card">
            <div className="card-header"><span className="card-title">Feature Importance (SHAP / Model-Based)</span></div>
            {!features || features.features?.length === 0 ? (
              <div className="empty-state"><div className="empty-state-text">No feature importance data available</div></div>
            ) : (
              <div>
                {features.features?.slice(0, 20).map((f: any, i: number) => {
                  const maxImp = features.features[0]?.importance || 1;
                  return (
                    <div key={i} className="explain-bar">
                      <div className="explain-bar-label">{f.feature}</div>
                      <div className="explain-bar-track">
                        <div className="explain-bar-fill" style={{width:`${(f.importance / maxImp) * 100}%`, background: i < 5 ? 'var(--accent)' : 'var(--text-muted)'}} />
                      </div>
                      <div className="explain-bar-value">{(f.importance ?? 0).toFixed(4)}</div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
