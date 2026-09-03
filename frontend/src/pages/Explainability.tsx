import { useState, useEffect } from 'react';
import { getGlobalExplanation, getExplanation, getTransactions } from '../api';

export default function Explainability() {
  const [globalExp, setGlobalExp] = useState<any>(null);
  const [txList, setTxList] = useState<any[]>([]);
  const [selectedTx, setSelectedTx] = useState('');
  const [txExp, setTxExp] = useState<any>(null);

  useEffect(() => {
    getGlobalExplanation().then(setGlobalExp).catch(() => {});
    getTransactions({ page: 1, page_size: 50 }).then(d => setTxList(d.transactions || [])).catch(() => {});
  }, []);

  useEffect(() => {
    if (selectedTx) {
      getExplanation(selectedTx).then(setTxExp).catch(() => {});
    }
  }, [selectedTx]);

  const globalFeatures = globalExp?.features || [];
  const maxGlobalImp = globalFeatures.length > 0 ? Math.max(...globalFeatures.map((f: any) => f.importance ?? 0), 0.001) : 0.001;

  return (
    <div className="fade-in">
      <div style={{ marginBottom: 12 }}>
        <h1 style={{fontSize:18, fontWeight:800}}>Explainability Lab</h1>
        <p style={{fontSize:11, color:'var(--text-muted)', marginTop:2}}>Understand why the model makes predictions using SHAP-based explanations</p>
      </div>

      <div className="grid-2" style={{marginBottom:16}}>
        {/* Global Feature Importance */}
        <div className="card">
          <div className="card-header"><span className="card-title">Global Feature Importance</span></div>
          <p style={{fontSize:11, color:'var(--text-muted)', marginBottom:12}}>
            Features ranked by their overall contribution to fraud detection across the dataset.
          </p>
          {globalFeatures.length === 0 ? (
            <div className="empty-state"><div className="empty-state-text">Train a model to see global feature importance</div></div>
          ) : (
            <div>
              {globalFeatures.slice(0, 15).map((f: any, i: number) => (
                <div key={i} className="explain-bar">
                  <div className="explain-bar-label" style={{width:140}}>{f.feature}</div>
                  <div className="explain-bar-track">
                    <div className="explain-bar-fill" style={{
                      width: `${((f.importance ?? 0) / maxGlobalImp) * 100}%`,
                      background: i < 3 ? 'var(--red)' : i < 7 ? 'var(--orange)' : 'var(--accent)',
                    }} />
                  </div>
                  <div className="explain-bar-value">{(f.importance ?? 0).toFixed(4)}</div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Transaction Explanation */}
        <div className="card">
          <div className="card-header"><span className="card-title">Transaction Explanation</span></div>

          <div style={{marginBottom:16}}>
            <label style={{fontSize:11, color:'var(--text-muted)', display:'block', marginBottom:4}}>Select a Transaction</label>
            <select className="select" style={{width:'100%'}} value={selectedTx} onChange={e => setSelectedTx(e.target.value)}>
              <option value="">Choose transaction...</option>
              {txList.map(t => (
                <option key={t.transaction_id} value={t.transaction_id}>
                  {t.transaction_id} — ${(t.amount ?? 0).toLocaleString()} — {t.prediction}
                </option>
              ))}
            </select>
          </div>

          {txExp && (
            <div>
              {/* Method & explanation text */}
              <div style={{padding:8, background:'var(--bg-primary)', borderRadius:6, marginBottom:12}}>
                <div style={{fontSize:10, color:'var(--text-muted)'}}>
                  Method: {txExp.method || 'none'}
                  {txExp.prediction && (
                    <span style={{marginLeft:8, fontWeight:700, color: txExp.prediction === 'FRAUD' ? 'var(--red)' : 'var(--green)'}}>
                      {txExp.prediction} ({((txExp.fraud_probability ?? 0) * 100).toFixed(1)}%)
                    </span>
                  )}
                </div>
                {txExp.explanation_text?.map((t: string, i: number) => (
                  <div key={i} style={{fontSize:12, color:'var(--text-secondary)', marginTop:4}}>• {t}</div>
                ))}
              </div>

              {/* Feature contributions */}
              {txExp.contributions && txExp.contributions.length > 0 && (
                <>
                  <div className="section-title">Feature Contributions</div>
                  {(() => {
                    const contribs = txExp.contributions.slice(0, 15);
                    const maxVal = contribs.length > 0 ? Math.max(...contribs.map((x: any) => Math.abs(x.shap_value ?? 0)), 0.001) : 0.001;
                    return contribs.map((c: any, i: number) => (
                      <div key={i} className="explain-bar">
                        <div className="explain-bar-label" style={{width:140}}>
                          <span>{c.feature}</span>
                          <span style={{fontSize:9, color:'var(--text-muted)', display:'block', fontFamily:'var(--mono)'}}>val: {(c.value ?? 0).toFixed(2)}</span>
                        </div>
                        <div className="explain-bar-track">
                          <div className="explain-bar-fill" style={{
                            width: `${(Math.abs(c.shap_value ?? 0) / maxVal) * 100}%`,
                            background: (c.direction === 'positive' || (c.shap_value ?? 0) > 0) ? 'var(--red)' : 'var(--green)',
                          }} />
                        </div>
                        <div className="explain-bar-value" style={{color: (c.direction === 'positive' || (c.shap_value ?? 0) > 0) ? 'var(--red)' : 'var(--green)'}}>
                          {(c.shap_value ?? 0) > 0 ? '+' : ''}{(c.shap_value ?? 0).toFixed(4)}
                        </div>
                      </div>
                    ));
                  })()}
                </>
              )}

              {/* No contributions fallback */}
              {(!txExp.contributions || txExp.contributions.length === 0) && txExp.method === 'none' && (
                <div style={{padding:12, textAlign:'center', fontSize:12, color:'var(--text-muted)'}}>
                  {txExp.explanation_text?.[0] || 'Explanation unavailable. Ensure a model is trained and the transaction has valid features.'}
                </div>
              )}
            </div>
          )}

          {selectedTx && !txExp && (
            <div style={{padding:12, textAlign:'center', color:'var(--text-muted)', fontSize:12}}>
              <span className="spinner" /> Loading explanation...
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
