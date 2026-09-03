import { useState } from 'react';
import { register as apiRegister, setAuthToken } from '../api';

interface Props {
  onAuthenticated: () => void;
  onBackToLogin: () => void;
}

interface ValidationErrors {
  name?: string;
  email?: string;
  password?: string;
  confirm_password?: string;
}

export default function Register({ onAuthenticated, onBackToLogin }: Props) {
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [fieldErrors, setFieldErrors] = useState<ValidationErrors>({});

  const validate = (): boolean => {
    const errs: ValidationErrors = {};
    if (!name.trim() || name.trim().length < 2) errs.name = 'Name must be at least 2 characters';
    if (!email.trim() || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim())) errs.email = 'Valid email is required';
    if (password.length < 6) errs.password = 'Password must be at least 6 characters';
    if (password !== confirmPassword) errs.confirm_password = 'Passwords do not match';
    setFieldErrors(errs);
    return Object.keys(errs).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!validate()) return;
    setLoading(true);
    setError('');
    setSuccess('');
    try {
      const res = await apiRegister(name.trim(), email.trim().toLowerCase(), password);
      setAuthToken(res.token);
      onAuthenticated();
    } catch (e: any) {
      setError(e.message || 'Registration failed');
    }
    setLoading(false);
  };

  const fieldStyle = (hasError: boolean) => ({
    width: '100%',
    borderColor: hasError ? 'var(--red)' : undefined,
  });

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
        maxWidth: 420, width: '100%', position: 'relative',
        background: 'var(--bg-card)', border: '1px solid var(--border)',
        borderRadius: 12, padding: '36px 32px',
      }}>
        {/* Brand */}
        <div style={{ textAlign: 'center', marginBottom: 28 }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 10, marginBottom: 12 }}>
            <div className="brand-icon" style={{ width: 36, height: 36, borderRadius: 10 }}>
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>
            </div>
            <span style={{ fontSize: 22, fontWeight: 800, letterSpacing: '-0.5px' }}>FraudLens</span>
          </div>
          <p style={{ fontSize: 12, color: 'var(--text-muted)' }}>
            Create your fraud detection account
          </p>
        </div>

        {/* Registration Form */}
        <form onSubmit={handleSubmit}>
          {/* Full Name */}
          <div style={{ marginBottom: 14 }}>
            <label style={{ fontSize: 10, fontWeight: 600, color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: 0.5, display: 'block', marginBottom: 6 }}>
              Full Name
            </label>
            <input
              className="input"
              type="text"
              value={name}
              onChange={e => { setName(e.target.value); setFieldErrors(p => ({ ...p, name: undefined })); }}
              placeholder="John Analyst"
              autoFocus
              style={fieldStyle(!!fieldErrors.name)}
            />
            {fieldErrors.name && <div style={{ fontSize: 10, color: 'var(--red)', marginTop: 4 }}>{fieldErrors.name}</div>}
          </div>

          {/* Email */}
          <div style={{ marginBottom: 14 }}>
            <label style={{ fontSize: 10, fontWeight: 600, color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: 0.5, display: 'block', marginBottom: 6 }}>
              Email
            </label>
            <input
              className="input"
              type="email"
              value={email}
              onChange={e => { setEmail(e.target.value); setFieldErrors(p => ({ ...p, email: undefined })); }}
              placeholder="analyst@company.com"
              style={fieldStyle(!!fieldErrors.email)}
            />
            {fieldErrors.email && <div style={{ fontSize: 10, color: 'var(--red)', marginTop: 4 }}>{fieldErrors.email}</div>}
          </div>

          {/* Password */}
          <div style={{ marginBottom: 14 }}>
            <label style={{ fontSize: 10, fontWeight: 600, color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: 0.5, display: 'block', marginBottom: 6 }}>
              Password
            </label>
            <div style={{ position: 'relative' }}>
              <input
                className="input"
                type={showPassword ? 'text' : 'password'}
                value={password}
                onChange={e => { setPassword(e.target.value); setFieldErrors(p => ({ ...p, password: undefined })); }}
                placeholder="Min. 6 characters"
                style={{ ...fieldStyle(!!fieldErrors.password), paddingRight: 60 }}
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
            {fieldErrors.password && <div style={{ fontSize: 10, color: 'var(--red)', marginTop: 4 }}>{fieldErrors.password}</div>}
          </div>

          {/* Confirm Password */}
          <div style={{ marginBottom: 18 }}>
            <label style={{ fontSize: 10, fontWeight: 600, color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: 0.5, display: 'block', marginBottom: 6 }}>
              Confirm Password
            </label>
            <input
              className="input"
              type={showPassword ? 'text' : 'password'}
              value={confirmPassword}
              onChange={e => { setConfirmPassword(e.target.value); setFieldErrors(p => ({ ...p, confirm_password: undefined })); }}
              placeholder="Re-enter password"
              style={fieldStyle(!!fieldErrors.confirm_password)}
            />
            {fieldErrors.confirm_password && <div style={{ fontSize: 10, color: 'var(--red)', marginTop: 4 }}>{fieldErrors.confirm_password}</div>}
          </div>

          {error && (
            <div style={{
              padding: '8px 12px', marginBottom: 14, borderRadius: 4,
              background: 'var(--red-dim)', border: '1px solid rgba(239,68,68,0.3)',
              fontSize: 12, color: 'var(--red)',
            }}>
              {error}
            </div>
          )}

          {success && (
            <div style={{
              padding: '8px 12px', marginBottom: 14, borderRadius: 4,
              background: 'var(--green-dim)', border: '1px solid rgba(34,197,94,0.3)',
              fontSize: 12, color: 'var(--green)',
            }}>
              {success}
            </div>
          )}

          <button
            type="submit"
            className="btn btn-primary"
            disabled={loading}
            style={{ width: '100%', justifyContent: 'center', padding: '10px 16px', fontSize: 13 }}
          >
            {loading ? <><span className="spinner" style={{ width: 14, height: 14 }} /> Creating account...</> : 'Create Account'}
          </button>
        </form>

        {/* Back to Login */}
        <div style={{
          marginTop: 16, textAlign: 'center', fontSize: 12, color: 'var(--text-muted)',
        }}>
          Already have an account?{' '}
          <button
            type="button"
            onClick={onBackToLogin}
            style={{
              background: 'none', border: 'none', color: 'var(--accent)', fontSize: 12,
              cursor: 'pointer', fontFamily: 'var(--font)', fontWeight: 600, padding: 0,
            }}
          >
            Sign In
          </button>
        </div>
      </div>
    </div>
  );
}
