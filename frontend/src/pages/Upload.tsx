import { useState, useRef } from 'react';
import { uploadDataset, trainModel, getEDA } from '../api';

export default function Upload() {
  const [, setFile] = useState<File | null>(null);
  const [uploadResult, setUploadResult] = useState<any>(null);
  const [trainResult, setTrainResult] = useState<any>(null);
  const [eda, setEda] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [step, setStep] = useState<'upload' | 'profile' | 'training' | 'done'>('upload');
  const [drag, setDrag] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleFile = async (f: File) => {
    setFile(f);
    setLoading(true);
    setStep('profile');
    try {
      const res = await uploadDataset(f);
      setUploadResult(res);
      setStep('profile');
    } catch (e: any) {
      alert('Upload failed: ' + e.message);
    }
    setLoading(false);
  };

  const handleTrain = async () => {
    if (!uploadResult) return;
    setLoading(true);
    setStep('training');
    try {
      const res = await trainModel(uploadResult.dataset_id);
      setTrainResult(res);
      const edaRes = await getEDA();
      setEda(edaRes);
      setStep('done');
    } catch (e: any) {
      alert('Training failed: ' + e.message);
    }
    setLoading(false);
  };

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDrag(false);
    const f = e.dataTransfer.files[0];
    if (f) handleFile(f);
  };

  return (
    <div className="fade-in">
      <h1 style={{fontSize:22, fontWeight:700, marginBottom:4}}>Dataset Upload & Training</h1>
      <p style={{fontSize:12, color:'var(--text-muted)', marginBottom:16}}>Upload a CSV or Excel transaction dataset to train fraud detection models</p>

      {/* Progress Steps */}
      <div style={{display:'flex', gap:0, marginBottom:24}}>
        {(['upload', 'profile', 'training', 'done'] as const).map((s, i) => (
          <div key={s} style={{
            flex:1, padding:'8px 16px', fontSize:11, fontWeight:600, textTransform:'uppercase',
            letterSpacing:1, textAlign:'center',
            background: step === s ? 'var(--accent)' : i < ['upload','profile','training','done'].indexOf(step) ? 'var(--green-dim)' : 'var(--bg-card)',
            color: step === s ? 'white' : 'var(--text-secondary)',
            borderTop: '1px solid var(--border)',
            borderBottom: '2px solid ' + (step === s ? 'var(--accent)' : 'var(--border)'),
          }}>
            {s === 'upload' ? '1. Upload' : s === 'profile' ? '2. Profile' : s === 'training' ? '3. Train' : '4. Complete'}
          </div>
        ))}
      </div>

      {/* Upload Zone */}
      {step === 'upload' && (
        <div
          className={`upload-zone ${drag ? 'drag' : ''}`}
          onDragOver={e => { e.preventDefault(); setDrag(true); }}
          onDragLeave={() => setDrag(false)}
          onDrop={onDrop}
          onClick={() => inputRef.current?.click()}
        >
          <div style={{fontSize:48, marginBottom:12}}>📁</div>
          <div style={{fontSize:16, fontWeight:600, marginBottom:4}}>Drop your dataset here</div>
          <div style={{fontSize:12, color:'var(--text-muted)', marginBottom:16}}>Supports CSV and Excel files (.csv, .xlsx, .xls)</div>
          <button className="btn btn-primary">Browse Files</button>
          <input ref={inputRef} type="file" accept=".csv,.xlsx,.xls" hidden onChange={e => e.target.files?.[0] && handleFile(e.target.files[0])} />
        </div>
      )}

      {/* Profile Results */}
      {(step === 'profile' || step === 'training' || step === 'done') && uploadResult && (
        <div className="fade-in">
          <div className="card" style={{marginBottom:16}}>
            <div className="card-header">
              <span className="card-title">Data Profile — {uploadResult.profile.filename}</span>
              <span style={{
                fontSize:11, fontWeight:700, padding:'4px 12px', borderRadius:4,
                background: uploadResult.profile.quality_score >= 70 ? 'rgba(34,197,94,0.15)' : uploadResult.profile.quality_score >= 40 ? 'rgba(234,179,8,0.15)' : 'rgba(239,68,68,0.15)',
                color: uploadResult.profile.quality_score >= 70 ? 'var(--green)' : uploadResult.profile.quality_score >= 40 ? 'var(--yellow)' : 'var(--red)',
              }}>
                Quality: {uploadResult.profile.quality_score}/100
              </span>
            </div>

            <div className="stats-row">
              <div className="stat-card">
                <div className="stat-label">Rows</div>
                <div className="stat-value">{(uploadResult.profile.row_count ?? 0).toLocaleString()}</div>
              </div>
              <div className="stat-card">
                <div className="stat-label">Columns</div>
                <div className="stat-value">{uploadResult.profile.column_count}</div>
              </div>
              <div className="stat-card">
                <div className="stat-label">Duplicates</div>
                <div className="stat-value">{uploadResult.profile.duplicate_rows}</div>
              </div>
              <div className="stat-card">
                <div className="stat-label">Fraud Label</div>
                <div className="stat-value" style={{color: uploadResult.profile.has_fraud_label ? 'var(--green)' : 'var(--yellow)', fontSize:16}}>
                  {uploadResult.profile.has_fraud_label ? `Yes (${uploadResult.profile.possible_target})` : 'No — Anomaly Mode'}
                </div>
              </div>
            </div>

            {/* Class distribution */}
            {uploadResult.profile.class_distribution && (
              <div style={{marginBottom:12}}>
                <div className="section-title">Class Distribution</div>
                <div style={{display:'flex', gap:16}}>
                  {Object.entries(uploadResult.profile.class_distribution).map(([k, v]) => (
                    <div key={k} style={{fontSize:12}}>
                      <span style={{color:'var(--text-muted)'}}>Class {k}: </span>
                      <span style={{fontWeight:700, fontFamily:'var(--mono)'}}>{String(v)}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Warnings */}
            {uploadResult.profile.warnings?.length > 0 && (
              <div style={{marginBottom:12}}>
                <div className="section-title">Warnings</div>
                {uploadResult.profile.warnings.map((w: string, i: number) => (
                  <div key={i} style={{fontSize:12, color:'var(--yellow)', padding:'4px 0'}}>⚠ {w}</div>
                ))}
              </div>
            )}

            {/* Columns */}
            <div style={{marginBottom:12}}>
              <div className="section-title">Columns</div>
              <div style={{display:'flex', flexWrap:'wrap', gap:6}}>
                {uploadResult.profile.columns?.map((col: any) => (
                  <span key={col.name} style={{
                    fontSize:11, padding:'3px 8px', borderRadius:4, background:'var(--bg-primary)',
                    border:'1px solid var(--border)', color:'var(--text-secondary)',
                    fontFamily:'var(--mono)',
                  }}>
                    {col.name} <span style={{color:'var(--text-muted)'}}>({col.dtype})</span>
                  </span>
                ))}
              </div>
            </div>

            {!uploadResult.profile.has_fraud_label && (
              <div style={{padding:12, background:'rgba(234,179,8,0.1)', borderRadius:8, border:'1px solid rgba(234,179,8,0.3)', fontSize:12, color:'var(--yellow)', marginBottom:12}}>
                ⚠ No fraud label detected. The system will operate in <strong>anomaly-detection mode</strong>. Supervised ML models will not be trained.
              </div>
            )}

            <button className="btn btn-primary" onClick={handleTrain} disabled={loading}>
              {loading ? <><span className="spinner" /> Training...</> : '🚀 Train Models'}
            </button>
          </div>

          {/* Training Results */}
          {trainResult && (
            <div className="card fade-in" style={{marginBottom:16}}>
              <div className="card-header">
                <span className="card-title">Training Complete</span>
                {trainResult.best_model && <span className="risk-badge risk-low">Best: {trainResult.best_model}</span>}
              </div>

              {trainResult.models_trained && (
                <div style={{marginBottom:12}}>
                  <div className="section-title">Models Trained</div>
                  <div style={{display:'flex', gap:8}}>
                    {trainResult.models_trained.map((m: string) => (
                      <span key={m} style={{fontSize:12, padding:'4px 12px', borderRadius:4, background:'var(--bg-primary)', border:'1px solid var(--border)', fontWeight:600}}>
                        {m}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {trainResult.metrics && (
                <div style={{marginBottom:12}}>
                  <div className="section-title">Model Comparison</div>
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>Model</th><th>Precision</th><th>Recall</th><th>F1</th><th>PR-AUC</th><th>ROC-AUC</th>
                      </tr>
                    </thead>
                    <tbody>
                      {Object.entries(trainResult.metrics).map(([name, m]: [string, any]) => (
                        <tr key={name}>
                          <td style={{fontWeight:600, color:'var(--text-primary)'}}>{name}</td>
                          <td>{((m.precision ?? 0) * 100).toFixed(1)}%</td>
                          <td>{((m.recall ?? 0) * 100).toFixed(1)}%</td>
                          <td style={{fontWeight:700, color: name === trainResult.best_model ? 'var(--green)' : 'inherit'}}>{((m.f1 ?? 0) * 100).toFixed(1)}%</td>
                          <td>{((m.pr_auc ?? 0) * 100).toFixed(1)}%</td>
                          <td>{((m.roc_auc ?? 0) * 100).toFixed(1)}%</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}

              {trainResult.optimal_threshold !== undefined && (
                <div style={{fontSize:12, color:'var(--text-secondary)'}}>
                  Optimal threshold: <strong style={{color:'var(--accent)'}}>{((trainResult.optimal_threshold ?? 0) * 100).toFixed(0)}%</strong>
                </div>
              )}
            </div>
          )}

          {/* EDA */}
          {eda && !eda.message && (
            <div className="card fade-in">
              <div className="card-header">
                <span className="card-title">Exploratory Data Analysis</span>
              </div>

              {eda.amount_stats && (
                <div style={{marginBottom:12}}>
                  <div className="section-title">Amount Statistics</div>
                  <div className="grid-4" style={{gap:8}}>
                    {Object.entries(eda.amount_stats).map(([k, v]) => (
                      <div key={k} style={{padding:8, background:'var(--bg-primary)', borderRadius:4}}>
                        <div style={{fontSize:10, color:'var(--text-muted)', textTransform:'uppercase'}}>{k}</div>
                        <div style={{fontSize:14, fontWeight:700, fontFamily:'var(--mono)'}}>{typeof v === 'number' ? v.toLocaleString(undefined, {maximumFractionDigits:2}) : String(v)}</div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {eda.class_distribution && (
                <div style={{marginBottom:12}}>
                  <div className="section-title">Class Distribution</div>
                  <div style={{display:'flex', gap:24}}>
                    <div>
                      <div style={{fontSize:10, color:'var(--text-muted)'}}>Genuine</div>
                      <div style={{fontSize:20, fontWeight:700, color:'var(--green)', fontFamily:'var(--mono)'}}>{eda.class_distribution.genuine?.toLocaleString()}</div>
                    </div>
                    <div>
                      <div style={{fontSize:10, color:'var(--text-muted)'}}>Fraud</div>
                      <div style={{fontSize:20, fontWeight:700, color:'var(--red)', fontFamily:'var(--mono)'}}>{eda.class_distribution.fraud?.toLocaleString()}</div>
                    </div>
                    <div>
                      <div style={{fontSize:10, color:'var(--text-muted)'}}>Fraud Rate</div>
                      <div style={{fontSize:20, fontWeight:700, fontFamily:'var(--mono)'}}>{eda.class_distribution.fraud_rate}%</div>
                    </div>
                  </div>
                </div>
              )}

              {eda.fraud_amount_stats && (
                <div>
                  <div className="section-title">Fraud vs Genuine Amount</div>
                  <div className="grid-2" style={{gap:8}}>
                    <div style={{padding:8, background:'var(--bg-primary)', borderRadius:4}}>
                      <div style={{fontSize:10, color:'var(--green)', fontWeight:600}}>Genuine Avg</div>
                      <div style={{fontSize:16, fontWeight:700, fontFamily:'var(--mono)'}}>${eda.fraud_amount_stats.genuine_mean?.toLocaleString(undefined, {maximumFractionDigits:2})}</div>
                    </div>
                    <div style={{padding:8, background:'var(--bg-primary)', borderRadius:4}}>
                      <div style={{fontSize:10, color:'var(--red)', fontWeight:600}}>Fraud Avg</div>
                      <div style={{fontSize:16, fontWeight:700, fontFamily:'var(--mono)'}}>${eda.fraud_amount_stats.fraud_mean?.toLocaleString(undefined, {maximumFractionDigits:2})}</div>
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {loading && (
        <div style={{display:'flex', alignItems:'center', gap:8, padding:12, fontSize:12, color:'var(--text-secondary)'}}>
          <span className="spinner" /> Processing...
        </div>
      )}
    </div>
  );
}
