import { useState, useEffect, useCallback } from 'react';
import { Routes, Route, NavLink, Navigate, useNavigate } from 'react-router-dom';
import { useWebSocket } from './hooks/useWebSocket';
import { getSystemStatus, getAuthToken, clearAuthToken, getMe, logout as apiLogout } from './api';
import CommandCenter from './pages/CommandCenter';
import LiveFeed from './pages/LiveFeed';
import Transactions from './pages/Transactions';
import ModelLab from './pages/ModelLab';
import Analytics from './pages/Analytics';
import Investigate from './pages/Investigate';
import Alerts from './pages/Alerts';
import Onboarding from './pages/Onboarding';
import Explainability from './pages/Explainability';
import Login from './pages/Login';
import Register from './pages/Register';

export default function App() {
  const [authenticated, setAuthenticated] = useState<boolean | null>(null);
  const [systemStatus, setSystemStatus] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [authView, setAuthView] = useState<'login' | 'register'>('login');
  const [currentUser, setCurrentUser] = useState<any>(null);
  const [showProfile, setShowProfile] = useState(false);
  const navigate = useNavigate();
  const ws = useWebSocket();

  useEffect(() => {
    const token = getAuthToken();
    if (!token) {
      setAuthenticated(false);
      setLoading(false);
      return;
    }
    getMe()
      .then((data: any) => {
        setCurrentUser(data.user);
        setAuthenticated(true);
        setLoading(false);
      })
      .catch(() => { clearAuthToken(); setAuthenticated(false); setLoading(false); });
  }, []);

  const checkStatus = useCallback(() => {
    getSystemStatus().then(s => setSystemStatus(s)).catch(() => {});
  }, []);

  useEffect(() => {
    if (authenticated) checkStatus();
  }, [authenticated, checkStatus]);

  const handleLogout = async () => {
    try { await apiLogout(); } catch {}
    ws.sendMessage({ action: 'stop_simulation' });
    clearAuthToken();
    setCurrentUser(null);
    setAuthenticated(false);
    setSystemStatus(null);
    setShowProfile(false);
  };

  const handleAuthenticated = () => {
    setAuthenticated(true);
  };

  if (loading || authenticated === null) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100vh', background: 'var(--bg-primary)' }}>
        <div style={{ textAlign: 'center' }}>
          <div className="spinner" style={{ width: 24, height: 24, marginBottom: 12 }} />
          <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>Initializing FraudLens...</div>
        </div>
      </div>
    );
  }

  if (!authenticated) {
    if (authView === 'register') {
      return <Register onAuthenticated={handleAuthenticated} onBackToLogin={() => setAuthView('login')} />;
    }
    return <Login onAuthenticated={handleAuthenticated} onShowRegister={() => setAuthView('register')} />;
  }

  const hasDataset = systemStatus?.hasDataset && systemStatus?.modelsLoaded > 0;

  if (systemStatus !== null && !hasDataset) {
    return <Onboarding onReady={() => { checkStatus(); }} />;
  }

  return (
    <div className="app-layout">
      <nav className="top-nav">
        <div className="nav-brand">
          <div className="brand-icon">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>
          </div>
          <span>FraudLens</span>
        </div>
        <div className="nav-links">
          <NavLink to="/command" end className={({isActive}: {isActive: boolean}) => `nav-link ${isActive ? 'active' : ''}`}>Command Center</NavLink>
          <NavLink to="/live" className={({isActive}: {isActive: boolean}) => `nav-link ${isActive ? 'active' : ''}`}>Live Feed</NavLink>
          <NavLink to="/transactions" className={({isActive}: {isActive: boolean}) => `nav-link ${isActive ? 'active' : ''}`}>Transactions</NavLink>
          <NavLink to="/alerts" className={({isActive}: {isActive: boolean}) => `nav-link ${isActive ? 'active' : ''}`}>Alerts</NavLink>
          <NavLink to="/investigate" className={({isActive}: {isActive: boolean}) => `nav-link ${isActive ? 'active' : ''}`}>Investigate</NavLink>
          <NavLink to="/model-lab" className={({isActive}: {isActive: boolean}) => `nav-link ${isActive ? 'active' : ''}`}>Model Lab</NavLink>
          <NavLink to="/explainability" className={({isActive}: {isActive: boolean}) => `nav-link ${isActive ? 'active' : ''}`}>Explainability</NavLink>
          <NavLink to="/analytics" className={({isActive}: {isActive: boolean}) => `nav-link ${isActive ? 'active' : ''}`}>Analytics</NavLink>
        </div>
        <div className="nav-right">
          <div className="nav-status">
            <span className="nav-status-badge" style={{ background: 'var(--green-dim)', color: 'var(--green)' }}>
              ● SYSTEM ACTIVE
            </span>
            <span className="nav-status-text">
              {systemStatus?.modelsLoaded || 0} models
            </span>
          </div>
          <div className={`conn-dot ${ws.connected ? 'connected' : ''}`} title={ws.connected ? 'WebSocket Connected' : 'Disconnected'} />
          <button className="btn btn-sm" onClick={() => navigate('/onboarding')} title="Change dataset">
            New Analysis
          </button>

          {/* User Profile Dropdown */}
          <div style={{ position: 'relative' }}>
            <button
              className="btn btn-sm"
              onClick={() => setShowProfile(!showProfile)}
              style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 10 }}
            >
              <div style={{
                width: 20, height: 20, borderRadius: '50%',
                background: 'var(--accent)', display: 'flex', alignItems: 'center',
                justifyContent: 'center', fontSize: 9, fontWeight: 700, color: 'white',
              }}>
                {currentUser?.name?.[0]?.toUpperCase() || '?'}
              </div>
              <span style={{ maxWidth: 80, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {currentUser?.name || 'User'}
              </span>
            </button>
            {showProfile && (
              <div style={{
                position: 'absolute', right: 0, top: '100%', marginTop: 4,
                background: 'var(--bg-card)', border: '1px solid var(--border)',
                borderRadius: 6, padding: '8px 0', minWidth: 200, zIndex: 100,
                boxShadow: '0 8px 24px rgba(0,0,0,0.3)',
              }}>
                <div style={{ padding: '8px 14px', borderBottom: '1px solid var(--border)' }}>
                  <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-primary)' }}>{currentUser?.name}</div>
                  <div style={{ fontSize: 10, color: 'var(--text-muted)', fontFamily: 'var(--mono)' }}>{currentUser?.email}</div>
                  <div style={{ fontSize: 9, color: 'var(--text-dim)', marginTop: 2, textTransform: 'uppercase', letterSpacing: 0.5 }}>
                    {currentUser?.role || 'analyst'}
                  </div>
                </div>
                <button
                  style={{
                    display: 'block', width: '100%', padding: '8px 14px', textAlign: 'left',
                    background: 'none', border: 'none', color: 'var(--text-secondary)',
                    fontSize: 11, cursor: 'pointer', fontFamily: 'var(--font)',
                  }}
                  onClick={() => { navigate('/analytics'); setShowProfile(false); }}
                >
                  📊 Activity & Analytics
                </button>
                <button
                  style={{
                    display: 'block', width: '100%', padding: '8px 14px', textAlign: 'left',
                    background: 'none', border: 'none', color: 'var(--red)',
                    fontSize: 11, cursor: 'pointer', fontFamily: 'var(--font)',
                  }}
                  onClick={handleLogout}
                >
                  ↩ Logout
                </button>
              </div>
            )}
          </div>
        </div>
      </nav>
      <main className="page-content">
        <Routes>
          <Route path="/" element={<Navigate to="/command" replace />} />
          <Route path="/command" element={<CommandCenter ws={ws} />} />
          <Route path="/live" element={<LiveFeed ws={ws} />} />
          <Route path="/transactions" element={<Transactions />} />
          <Route path="/alerts" element={<Alerts />} />
          <Route path="/investigate" element={<Investigate />} />
          <Route path="/investigate/:txId" element={<Investigate />} />
          <Route path="/model-lab" element={<ModelLab />} />
          <Route path="/explainability" element={<Explainability />} />
          <Route path="/analytics" element={<Analytics />} />
          <Route path="/onboarding" element={<Onboarding onReady={() => { checkStatus(); navigate('/command'); }} />} />
        </Routes>
      </main>
    </div>
  );
}
