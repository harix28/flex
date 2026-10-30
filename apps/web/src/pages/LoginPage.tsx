import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { Activity, Lock, Mail, AlertCircle, Loader2, ShieldCheck } from 'lucide-react';

interface LoginPageProps {
  onLoginSuccess: () => void;
}

export const LoginPage: React.FC<LoginPageProps> = ({ onLoginSuccess }) => {
  const { login, isLoading, authError } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [localError, setLocalError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLocalError(null);

    if (!email.trim() || !password) {
      setLocalError('Please enter both email and password.');
      return;
    }

    try {
      await login(email.trim(), password);
      onLoginSuccess();
    } catch (err: any) {
      // Error handled by AuthContext
    }
  };

  return (
    <div
      style={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '1.5rem',
        backgroundColor: 'var(--bg-canvas)',
      }}
    >
      <div
        className="card"
        style={{
          width: '100%',
          maxWidth: '440px',
          padding: '2rem',
          backgroundColor: 'var(--bg-surface)',
          border: '1px solid var(--border-strong)',
          boxShadow: 'var(--shadow-lg)',
        }}
      >
        {/* Brand Header */}
        <div style={{ textAlign: 'center', marginBottom: '1.75rem' }}>
          <div
            style={{
              width: '48px',
              height: '48px',
              borderRadius: 'var(--radius-md)',
              backgroundColor: 'rgba(14, 165, 233, 0.1)',
              border: '1px solid var(--primary)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: 'var(--primary)',
              margin: '0 auto 0.75rem',
            }}
          >
            <Activity size={26} />
          </div>
          <h1 style={{ fontSize: '1.375rem', fontWeight: 700, letterSpacing: '-0.02em' }}>
            MERIDIAN SENTINEL
          </h1>
          <p style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)', marginTop: '0.25rem' }}>
            Condition-Based Maintenance &amp; Turbofan Fleet Portal
          </p>
        </div>

        {/* Disclaimer Notice */}
        <div
          style={{
            backgroundColor: 'var(--bg-subtle)',
            border: '1px solid var(--border-subtle)',
            borderRadius: 'var(--radius-sm)',
            padding: '0.625rem 0.75rem',
            fontSize: '0.75rem',
            color: 'var(--text-muted)',
            marginBottom: '1.25rem',
            display: 'flex',
            alignItems: 'flex-start',
            gap: '0.5rem',
          }}
        >
          <ShieldCheck size={16} style={{ color: 'var(--primary)', flexShrink: 0, marginTop: '2px' }} />
          <span>
            <strong>Simulated Replay Demonstration:</strong> Powered by the NASA C-MAPSS dataset and verified XGBoost RUL regression bundle (<code className="mono">fd001-v1</code>).
          </span>
        </div>

        {/* Errors */}
        {(authError || localError) && (
          <div className="alert alert-danger" style={{ marginBottom: '1.25rem' }}>
            <AlertCircle size={18} style={{ flexShrink: 0 }} />
            <div>{localError || authError}</div>
          </div>
        )}

        {/* Login Form */}
        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          <div className="form-group" style={{ margin: 0 }}>
            <label className="form-label" htmlFor="login-email">
              <Mail size={14} />
              <span>Email Address</span>
            </label>
            <input
              id="login-email"
              type="email"
              className="form-control"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="e.g., admin@example.com"
              required
              autoComplete="username"
              disabled={isLoading}
            />
          </div>

          <div className="form-group" style={{ margin: 0 }}>
            <label className="form-label" htmlFor="login-password">
              <Lock size={14} />
              <span>Password</span>
            </label>
            <input
              id="login-password"
              type="password"
              className="form-control"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••••••"
              required
              autoComplete="current-password"
              disabled={isLoading}
            />
          </div>

          <button
            type="submit"
            className="btn btn-primary"
            disabled={isLoading}
            style={{ width: '100%', marginTop: '0.5rem', padding: '0.625rem' }}
          >
            {isLoading ? (
              <>
                <Loader2 size={16} className="animate-spin" />
                <span>Authenticating Session...</span>
              </>
            ) : (
              <span>Sign In to Portal</span>
            )}
          </button>
        </form>

        {/* Demo Accounts Quick-Select */}
        <div
          style={{
            marginTop: '1.25rem',
            paddingTop: '1rem',
            borderTop: '1px solid var(--border-subtle)',
          }}
        >
          <div style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '0.5rem', textAlign: 'center' }}>
            Quick Demo Login (Click to Fill):
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr', gap: '0.4rem' }}>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => {
                setEmail('admin@meridian.example.com');
                setPassword('Password12345!');
              }}
              style={{ fontSize: '0.75rem', padding: '0.35rem 0.65rem', justifyContent: 'space-between', display: 'flex' }}
            >
              <span>👔 <strong>General Manager</strong> (Admin)</span>
              <span className="mono" style={{ color: 'var(--text-muted)', fontSize: '0.7rem' }}>admin@meridian.example.com</span>
            </button>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => {
                setEmail('manager@meridian.example.com');
                setPassword('Password12345!');
              }}
              style={{ fontSize: '0.75rem', padding: '0.35rem 0.65rem', justifyContent: 'space-between', display: 'flex' }}
            >
              <span>⚙️ <strong>Maintenance Engineer</strong> (Lead)</span>
              <span className="mono" style={{ color: 'var(--text-muted)', fontSize: '0.7rem' }}>manager@meridian.example.com</span>
            </button>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => {
                setEmail('tech@meridian.example.com');
                setPassword('Password12345!');
              }}
              style={{ fontSize: '0.75rem', padding: '0.35rem 0.65rem', justifyContent: 'space-between', display: 'flex' }}
            >
              <span>🔧 <strong>Maintenance Technician</strong> (A&P)</span>
              <span className="mono" style={{ color: 'var(--text-muted)', fontSize: '0.7rem' }}>tech@meridian.example.com</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
