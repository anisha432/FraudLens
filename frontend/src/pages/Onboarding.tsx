import { useState } from 'react';
import { uploadDataset, trainModel, generateDemo } from '../api';

interface Props {
  onReady: () => void;
}

interface StageResult {
  label: string;
  status: 'pending' | 'active' | 'done' | 'error';
  detail?: string;
}

const INITIAL_STAGES: StageResult[] = [
  { label: 'Dataset Ingestion', status: 'pending' },
  { label: 'Schema Intelligence', status: 'pending' },
  { label: 'Data Quality Analysis', status: 'pending' },
  { label: 'Feature Engineering', status: 'pending' },
  { label: 'Model Training', status: 'pending' },
  { label: 'Detection Engine', status: 'pending' },
];

export default function Onboarding({ onReady }: Props) {
  const [view, setView] = useState<'ready' | 'processing' | 'done' | 'error'>('ready');
  const [stages, setStages] = useState<StageResult[]>(INITIAL_STAGES);
  const [error, setError] = useState('');
  const [drag, setDrag] = useState(false);

  const updateStage = (index: number, status: StageResult['status'], detail?: string) => {
    setStages(prev => prev.map((s, i) => i === index ? { ...s, status, detail } : s));
  };

  const processUpload = async (file: File) => {
    setView('processing');
    setStages([...INITIAL_STAGES]);
    setError('');

    try {
      // Stage 1: Ingestion
      updateStage(0, 'active');
      const res = await uploadDataset(file);
      if (!res.dataset_id) {
        updateStage(0, 'error', res.message);
        setError(res.message || 'Upload failed');
        setView('error');
        return;
      }
      const profile = res.profile;
      updateStage(0, 'done', `${profile.row_count.toLocaleString()} rows × ${profile.column_count} columns`);

      // Stage 2: Schema Intelligence
      updateStage(1, 'active');
      const detectedCols = [profile.possible_target ? `Target: ${profile.possible_target}` : 'No target']
        .concat(profile.columns?.slice(0, 3).map((c: any) => `${c.name} (${c.dtype})`) || []);
      updateStage(1, 'done', detectedCols.join(', '));

      // Stage 3: Data Quality
      updateStage(2, 'active');
      const dupInfo = profile.duplicate_rows > 0 ? `${profile.duplicate_rows} duplicates removed` : 'No duplicates';
      const missingInfo = Object.keys(profile.missing_values || {}).length > 0
        ? `${Object.keys(profile.missing_values).length} cols with gaps`
        : 'No missing values';
      updateStage(2, 'done', `Quality: ${profile.quality_score}/100 — ${missingInfo}, ${dupInfo}`);

      // Stage 4 + 5 + 6: Training (all in one request)
      updateStage(3, 'active');
      updateStage(4, 'active');
      const trainRes = await trainModel(res.dataset_id);
      if (trainRes.error) {
        updateStage(4, 'error', trainRes.error);
        setError(trainRes.error);
        setView('error');
        return;
      }
      updateStage(3, 'done', `${trainRes.n_features || '?'} features engineered`);
      const modelsList = (trainRes.models_trained || []).join(' + ');
      updateStage(4, 'done', `Best: ${trainRes.best_model || '?'} — ${modelsList}`);
      updateStage(5, 'done', 'Risk scoring active');

      setView('done');
    } catch (e: any) {
      const failIdx = stages.findIndex(s => s.status === 'active');
      if (failIdx >= 0) updateStage(failIdx, 'error', e.message);
      setError(e.message || 'Failed');
      setView('error');
    }
  };

  const handleDemo = async () => {
    setView('processing');
    setStages([...INITIAL_STAGES]);
    setError('');
    try {
      updateStage(0, 'active');
      updateStage(1, 'active');
      const res = await generateDemo();
      if (res.status === 'error') {
        updateStage(0, 'error', res.message);
        setError(res.message);
        setView('error');
        return;
      }
      updateStage(0, 'done', `${res.profile?.row_count?.toLocaleString() || '500'} rows generated`);
      updateStage(1, 'done', `Target: ${res.profile?.possible_target || 'fraud'}, ${res.profile?.column_count || '?'} columns`);
      updateStage(2, 'done', `Quality: ${res.profile?.quality_score || '100'}/100 — Synthetic data, clean`);
      updateStage(3, 'done', `${res.training?.n_features || '?'} features engineered`);
      updateStage(4, 'done', `Best: ${res.training?.best_model || 'xgboost'} — ${(res.training?.models_trained || []).join(' + ')}`);
      updateStage(5, 'done', 'Risk scoring active');
      setView('done');
    } catch (e: any) {
      setError(e.message || 'Failed to generate demo');
      setView('error');
    }
  };

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDrag(false);
    const f = e.dataTransfer.files[0];
    if (f) processUpload(f);
  };

  const completedCount = stages.filter(s => s.status === 'done').length;
  const progressPct = (completedCount / stages.length) * 100;

  return (
    <div className="onboarding">
      <div className="onboarding-card fade-in">
        {/* Logo + Title */}
        <div style={{ marginBottom: 32 }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 10, marginBottom: 12 }}>
            <div className="brand-icon" style={{ width: 36, height: 36, borderRadius: 10 }}>
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>
            </div>
            <span style={{ fontSize: 24, fontWeight: 800, letterSpacing: '-0.5px' }}>FraudLens</span>
          </div>
          <p style={{ fontSize: 13, color: 'var(--text-muted)', maxWidth: 400, margin: '0 auto' }}>
            Real-Time Fraud & Anomaly Detection Intelligence Platform
          </p>
        </div>

        {/* Ready state — upload zone */}
        {view === 'ready' && (
          <>
            <div
              className={`upload-zone ${drag ? 'drag' : ''}`}
              onDragOver={e => { e.preventDefault(); setDrag(true); }}
              onDragLeave={() => setDrag(false)}
              onDrop={onDrop}
              onClick={() => document.getElementById('onboard-file')?.click()}
              style={{ marginBottom: 16 }}
            >
              <div style={{ fontSize: 32, marginBottom: 8 }}>📁</div>
              <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 4 }}>Drop your transaction dataset here</div>
              <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 12 }}>CSV • XLSX • XLS</div>
              <button className="btn btn-primary" onClick={e => { e.stopPropagation(); document.getElementById('onboard-file')?.click(); }}>
                Browse Files
              </button>
              <input id="onboard-file" type="file" accept=".csv,.xlsx,.xls" hidden onChange={e => e.target.files?.[0] && processUpload(e.target.files[0])} />
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16 }}>
              <div style={{ flex: 1, height: 1, background: 'var(--border)' }} />
              <span style={{ fontSize: 10, color: 'var(--text-dim)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: 1 }}>or</span>
              <div style={{ flex: 1, height: 1, background: 'var(--border)' }} />
            </div>

            <button className="btn" onClick={handleDemo} style={{ width: '100%', justifyContent: 'center', padding: '10px 16px' }}>
              ⚡ Use Demo Dataset
            </button>
            <div style={{ fontSize: 10, color: 'var(--text-dim)', marginTop: 8 }}>
              500 synthetic transactions with 5% fraud rate — instant setup
            </div>
          </>
        )}

        {/* Processing — real stages from backend */}
        {view === 'processing' && (
          <div className="fade-in">
            <div className="progress-bar" style={{ height: 4, marginBottom: 16 }}>
              <div className="progress-fill" style={{ width: `${progressPct}%`, background: 'var(--accent)', transition: 'width 0.3s' }} />
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              {stages.map((s, i) => (
                <div key={i} className="setup-check">
                  <div className={`setup-check-icon ${s.status === 'done' ? 'done' : s.status === 'error' ? '' : 'pending'}`}
                    style={s.status === 'active' ? { background: 'var(--accent-dim)', color: 'var(--accent)', border: '1px solid var(--accent)' } : undefined}
                  >
                    {s.status === 'done' ? '✓' : s.status === 'active' ? <span className="spinner" style={{ width: 10, height: 10, borderWidth: 1.5 }} /> : s.status === 'error' ? '✗' : (i + 1)}
                  </div>
                  <div style={{ flex: 1 }}>
                    <span style={{
                      fontSize: 12, fontWeight: 600,
                      color: s.status === 'done' ? 'var(--text-primary)' : s.status === 'active' ? 'var(--accent)' : s.status === 'error' ? 'var(--red)' : 'var(--text-dim)',
                    }}>{s.label}</span>
                    {s.detail && (
                      <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 1, fontFamily: 'var(--mono)' }}>{s.detail}</div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Done — show real results */}
        {view === 'done' && (
          <div className="fade-in">
            <div style={{ textAlign: 'center', marginBottom: 16 }}>
              <div style={{ fontSize: 40, marginBottom: 8 }}>✓</div>
              <div style={{ fontSize: 16, fontWeight: 700, marginBottom: 4 }}>Detection Environment Ready</div>
              <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>All pipeline stages completed successfully</div>
            </div>
            <div style={{ marginBottom: 20 }}>
              {stages.filter(s => s.status === 'done').map((s, i) => (
                <div key={i} className="setup-check">
                  <div className="setup-check-icon done">✓</div>
                  <div>
                    <span style={{ fontSize: 12, fontWeight: 600 }}>{s.label}</span>
                    {s.detail && <div style={{ fontSize: 10, color: 'var(--text-muted)', fontFamily: 'var(--mono)' }}>{s.detail}</div>}
                  </div>
                </div>
              ))}
            </div>
            <button className="btn btn-primary" onClick={onReady} style={{ width: '100%', justifyContent: 'center', padding: '10px 16px', fontSize: 13 }}>
              Enter Command Center →
            </button>
          </div>
        )}

        {/* Error */}
        {view === 'error' && (
          <div className="fade-in">
            <div style={{ textAlign: 'center', marginBottom: 16 }}>
              <div style={{ fontSize: 40, marginBottom: 8 }}>⚠️</div>
              <div style={{ fontSize: 16, fontWeight: 700, marginBottom: 4 }}>Setup Failed</div>
              <div style={{ fontSize: 12, color: 'var(--red)', marginBottom: 16 }}>{error}</div>
              <button className="btn btn-primary" onClick={() => { setView('ready'); setError(''); setStages([...INITIAL_STAGES]); }}>
                Try Again
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
