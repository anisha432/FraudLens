import { useState } from 'react';
import { login as apiLogin, setAuthToken } from '../api';

interface Props {
  onAuthenticated: () => void;
  onShowRegister: () => void;
}

export default function Login({ onAuthenticated, onShowRegister }: Props) {
  const [email, setEmail] = useState('admin@fraudlens.io');
  const [password, setPassword] = useState('fraudlens');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [showPassword, setShowPassword] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email || !password) { setError('Enter email and password'); return; }
    setLoading(true);
    setError('');
    try {
      const res = await apiLogin(email, password);
      setAuthToken(res.token);
      onAuthenticated();
    } catch (e: any) {
      setError(e.message || 'Authentication failed');
    }
    setLoading(false);
  };

  return (
    <div style={{
      minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center',
      background: 'var(--bg-primary)', padding: 20,
    }}>
      {/* Subtle grid background */}
      <div style={{
        position: 'fixed', inset: 0, opacity: 0.03, pointerEvents: 'none',
        backgroundImage: 'linear-gradient(var(--border) 1px, transparent 1px), linear-gradient(90deg, var(--border) 1px, transparent 1px)',
        backgroundSize: '40px 40px',
      }} />

      <div className="fade-in" style={{
        maxWidth: 400, width: '100%', position: 'relative',
        background: 'var(--bg-card)', border: '1px solid var(--border)',
        borderRadius: 12, padding: '40px 36px',
      }}>
        {/* Brand */}
        <div style={{ textAlign: 'center', marginBottom: 32 }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 10, marginBottom: 12 }}>
            <div className="brand-icon" style={{ width: 36, height: 36, borderRadius: 10 }}>
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>
            </div>
            <span style={{ fontSize: 22, fontWeight: 800, letterSpacing: '-0.5px' }}>FraudLens</span>
          </div>
          <p style={{ fontSize: 12, color: 'var(--text-muted)' }}>
            Secure access to your fraud detection environment
          </p>
        </div>

        {/* Login Form */}
        <form onSubmit={handleSubmit}>
          <div style={{ marginBottom: 16 }}>
            <label style={{ fontSize: 10, fontWeight: 600, color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: 0.5, display: 'block', marginBottom: 6 }}>
              Email
            </label>
            <input
              className="input"
              type="email"
              value={email}
              onChange={e => setEmail(e.target.value)}
              placeholder="analyst@fraudlens.io"
              autoFocus
              style={{ width: '100%' }}
            />
          </div>

          <div style={{ marginBottom: 16 }}>
            <label style={{ fontSize: 10, fontWeight: 600, color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: 0.5, display: 'block', marginBottom: 6 }}>
              Password
            </label>
            <div style={{ position: 'relative' }}>
              <input
                className="input"
                type={showPassword ? 'text' : 'password'}
                value={password}
                onChange={e => setPassword(e.target.value)}
                placeholder="Enter password"
                style={{ width: '100%', paddingRight: 60 }}
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                style={{
                  position: 'absolute', right: 8, top: '50%', transform: 'translateY(-50%)',
                  background: 'none', border: 'none', color: 'var(--text-dim)', fontSize: 10,
                  cursor: 'pointer', padding: '4px 6px',
                }}
              >
                {showPassword ? 'HIDE' : 'SHOW'}
              </button>
            </div>
          </div>

          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
            <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 11, color: 'var(--text-muted)', cursor: 'pointer' }}>
              <input type="checkbox" defaultChecked style={{ accentColor: 'var(--accent)' }} />
              Remember me
            </label>
            <button type="button" style={{
              background: 'none', border: 'none', color: 'var(--text-dim)', fontSize: 11,
              cursor: 'not-allowed', padding: 0, fontFamily: 'var(--font)', opacity: 0.5,
            }}>
              Forgot password?
            </button>
          </div>

          {error && (
            <div style={{
              padding: '8px 12px', marginBottom: 16, borderRadius: 4,
              background: 'var(--red-dim)', border: '1px solid rgba(239,68,68,0.3)',
              fontSize: 12, color: 'var(--red)',
            }}>
              {error}
            </div>
          )}

          <button
            type="submit"
            className="btn btn-primary"
            disabled={loading}
            style={{ width: '100%', justifyContent: 'center', padding: '10px 16px', fontSize: 13 }}
          >
            {loading ? <><span className="spinner" style={{ width: 14, height: 14 }} /> Authenticating...</> : 'Sign In'}
          </button>
        </form>

        {/* Create Account link */}
        <div style={{
          marginTop: 16, textAlign: 'center', fontSize: 12, color: 'var(--text-muted)',
        }}>
          Don't have an account?{' '}
          <button
            type="button"
            onClick={onShowRegister}
            style={{
              background: 'none', border: 'none', color: 'var(--accent)', fontSize: 12,
              cursor: 'pointer', fontFamily: 'var(--font)', fontWeight: 600, padding: 0,
            }}
          >
            Create Account
          </button>
        </div>

        {/* Demo credentials hint */}
        <div style={{
          marginTop: 16, padding: '10px 14px', background: 'var(--bg-primary)',
          borderRadius: 6, fontSize: 10, color: 'var(--text-dim)', lineHeight: 1.6,
        }}>
          <div style={{ fontWeight: 600, color: 'var(--text-muted)', marginBottom: 2 }}>Demo Credentials</div>
          <div>Email: <span style={{ fontFamily: 'var(--mono)', color: 'var(--text-secondary)' }}>admin@fraudlens.io</span></div>
          <div>Password: <span style={{ fontFamily: 'var(--mono)', color: 'var(--text-secondary)' }}>fraudlens</span></div>
        </div>
      </div>
    </div>
  );
}
