import React, { useState, useEffect } from 'react';
import { useAuth } from '../../context/AuthContext';
import { systemApi } from '../../services/api';
import {
  LayoutDashboard,
  Cpu,
  Wrench,
  Layers,
  Users,
  LogOut,
  Building,
  Menu,
  X,
  Activity,
  ShieldCheck,
  AlertTriangle,
} from 'lucide-react';

export type NavigationPage = 'overview' | 'machines' | 'machine-detail' | 'work-orders' | 'work-order-detail' | 'model-monitoring' | 'registry' | 'members';

interface ShellProps {
  currentPage: NavigationPage;
  onNavigate: (page: NavigationPage, params?: Record<string, string>) => void;
  children: React.ReactNode;
}

export const Shell: React.FC<ShellProps> = ({ currentPage, onNavigate, children }) => {
  const { user, activeTenant, organizations, switchTenant, logout, canManageRegistry, canManageMembers } = useAuth();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [backendHealth, setBackendHealth] = useState<'checking' | 'healthy' | 'degraded'>('checking');

  useEffect(() => {
    let mounted = true;
    const checkHealth = async () => {
      try {
        const live = await systemApi.getHealth();
        if (mounted) {
          setBackendHealth(live.status === 'ok' ? 'healthy' : 'degraded');
        }
      } catch {
        if (mounted) {
          setBackendHealth('degraded');
        }
      }
    };
    checkHealth();
    const interval = setInterval(checkHealth, 30000);
    return () => {
      mounted = false;
      clearInterval(interval);
    };
  }, []);

  const navItems = [
    { id: 'overview' as NavigationPage, label: 'Overview', icon: LayoutDashboard },
    { id: 'machines' as NavigationPage, label: 'Fleet Machines', icon: Cpu },
    { id: 'work-orders' as NavigationPage, label: 'Work Orders', icon: Wrench },
    { id: 'model-monitoring' as NavigationPage, label: 'Model & Monitoring', icon: Activity },
    ...(canManageRegistry()
      ? [{ id: 'registry' as NavigationPage, label: 'Registry Config', icon: Layers }]
      : []),
    ...(canManageMembers()
      ? [{ id: 'members' as NavigationPage, label: 'Organization Members', icon: Users }]
      : []),
  ];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', minHeight: '100vh', backgroundColor: 'var(--bg-canvas)' }}>
      {/* Simulation & Regulatory Top Banner */}
      <div
        style={{
          backgroundColor: 'var(--bg-subtle)',
          borderBottom: '1px solid var(--border-subtle)',
          padding: '0.35rem 1rem',
          fontSize: '0.75rem',
          color: 'var(--text-secondary)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: '0.5rem',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <span
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '0.25rem',
              color: 'var(--high-text)',
              fontWeight: 600,
            }}
          >
            <AlertTriangle size={13} aria-hidden="true" />
            <span>NASA C-MAPSS REPLAY</span>
          </span>
          <span style={{ color: 'var(--text-muted)' }}>•</span>
          <span>Experimental Turbofan RUL Simulation Demonstration</span>
          <span style={{ color: 'var(--text-muted)' }}>•</span>
          <span style={{ color: 'var(--text-muted)' }}>Not for production flight dispatch without certification</span>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.35rem' }}>
            <span
              style={{
                width: '7px',
                height: '7px',
                borderRadius: '50%',
                backgroundColor:
                  backendHealth === 'healthy'
                    ? 'var(--low-text)'
                    : backendHealth === 'checking'
                    ? 'var(--high-text)'
                    : 'var(--urgent-text)',
              }}
            />
            <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>
              Backend: {backendHealth === 'healthy' ? 'Live & Ready' : backendHealth === 'checking' ? 'Checking' : 'Unavailable'}
            </span>
          </span>
        </div>
      </div>

      {/* Main Header / Topbar */}
      <header className="portal-header"
        style={{
          backgroundColor: 'var(--bg-surface)',
          borderBottom: '1px solid var(--border-subtle)',
          position: 'sticky',
          top: 0,
          zIndex: 40,
        }}
      >
        <div
          style={{
            maxWidth: '1440px',
            margin: '0 auto',
            padding: '0.75rem 1.5rem',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: '1rem',
          }}
        >
          {/* Logo & Platform Name */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
            <button
              type="button"
              className="btn btn-secondary mobile-menu-btn"
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              style={{ display: 'none', padding: '0.4rem' }}
              aria-label="Toggle navigation menu"
            >
              {mobileMenuOpen ? <X size={18} /> : <Menu size={18} />}
            </button>

            <div
              style={{ display: 'flex', alignItems: 'center', gap: '0.625rem', cursor: 'pointer' }}
              onClick={() => onNavigate('overview')}
            >
              <div
                style={{
                  width: '32px',
                  height: '32px',
                  borderRadius: 'var(--radius-sm)',
                  backgroundColor: 'var(--bg-canvas)',
                  border: '1px solid var(--primary)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: 'var(--primary)',
                }}
              >
                <Activity size={18} />
              </div>
              <div>
                <span
                  style={{
                    fontFamily: 'var(--font-heading)',
                    fontSize: '1.125rem',
                    fontWeight: 700,
                    letterSpacing: '-0.02em',
                    color: 'var(--text-primary)',
                  }}
                >
                  MERIDIAN SENTINEL
                </span>
                <span
                  style={{
                    fontSize: '0.6875rem',
                    color: 'var(--text-muted)',
                    display: 'block',
                    marginTop: '-2px',
                    letterSpacing: '0.04em',
                    textTransform: 'uppercase',
                  }}
                >
                  Condition Monitoring Portal
                </span>
              </div>
            </div>
          </div>

          {/* User & Organization Context */}
          <div className="portal-user-context" style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
            {/* Organization Switcher */}
            {organizations.length > 1 ? (
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.375rem' }}>
                <Building size={14} style={{ color: 'var(--text-muted)' }} />
                <select
                  className="form-control"
                  style={{ padding: '0.3rem 0.6rem', fontSize: '0.8125rem' }}
                  value={activeTenant?.id || ''}
                  onChange={(e) => switchTenant(e.target.value)}
                  aria-label="Active Organization"
                >
                  {organizations.map((org) => (
                    <option key={org.id} value={org.id}>
                      {org.name} ({org.slug || 'local'})
                    </option>
                  ))}
                </select>
              </div>
            ) : activeTenant ? (
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.375rem',
                  fontSize: '0.8125rem',
                  color: 'var(--text-secondary)',
                  backgroundColor: 'var(--bg-surface-elevated)',
                  padding: '0.35rem 0.65rem',
                  borderRadius: 'var(--radius-sm)',
                  border: '1px solid var(--border-subtle)',
                }}
              >
                <Building size={14} style={{ color: 'var(--primary)' }} />
                <span style={{ fontWeight: 500 }}>{activeTenant.name}</span>
              </div>
            ) : null}

            {/* User Profile & Role Badges */}
            {user && (
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.625rem' }}>
                <div style={{ textAlign: 'right', display: 'none' }} className="user-text-details">
                  <div style={{ fontSize: '0.8125rem', fontWeight: 600 }}>{user.display_name}</div>
                  <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>{user.email}</div>
                </div>

                <div style={{ display: 'flex', gap: '0.25rem' }}>
                  {activeTenant?.roles.map((role) => (
                    <span
                      key={role}
                      className="badge badge-medium"
                      style={{ fontSize: '0.6875rem', padding: '0.15rem 0.4rem' }}
                    >
                      <ShieldCheck size={11} />
                      <span>{role}</span>
                    </span>
                  ))}
                </div>

                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={logout}
                  style={{ padding: '0.35rem 0.65rem', fontSize: '0.8125rem' }}
                  title="Log out and clear session"
                >
                  <LogOut size={14} />
                  <span className="logout-text">Logout</span>
                </button>
              </div>
            )}
          </div>
        </div>
      </header>

      {/* Primary Layout (Sidebar + Content) */}
      <div
        style={{
          display: 'flex',
          flex: 1,
          maxWidth: '1440px',
          width: '100%',
          margin: '0 auto',
        }}
      >
        {/* Navigation Sidebar */}
        <aside
          className={`portal-sidebar ${mobileMenuOpen ? 'mobile-open' : ''}`}
          style={{
            width: '240px',
            backgroundColor: 'var(--bg-surface)',
            borderRight: '1px solid var(--border-subtle)',
            padding: '1.25rem 0.75rem',
            display: 'flex',
            flexDirection: 'column',
            gap: '0.35rem',
            flexShrink: 0,
          }}
        >
          <div style={{ fontSize: '0.7rem', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', padding: '0 0.75rem 0.5rem', letterSpacing: '0.05em' }}>
            Navigation
          </div>
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive =
              currentPage === item.id ||
              (item.id === 'machines' && currentPage === 'machine-detail') ||
              (item.id === 'work-orders' && currentPage === 'work-order-detail');
            return (
              <button
                key={item.id}
                type="button"
                onClick={() => {
                  onNavigate(item.id);
                  setMobileMenuOpen(false);
                }}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.75rem',
                  padding: '0.625rem 0.75rem',
                  fontSize: '0.875rem',
                  fontWeight: isActive ? 600 : 500,
                  color: isActive ? 'var(--primary)' : 'var(--text-secondary)',
                  backgroundColor: isActive ? 'rgba(14, 165, 233, 0.1)' : 'transparent',
                  border: '1px solid',
                  borderColor: isActive ? 'var(--primary)' : 'transparent',
                  borderRadius: 'var(--radius-sm)',
                  cursor: 'pointer',
                  textAlign: 'left',
                  transition: 'all var(--transition-fast)',
                }}
              >
                <Icon size={18} style={{ color: isActive ? 'var(--primary)' : 'var(--text-muted)' }} />
                <span>{item.label}</span>
              </button>
            );
          })}

          <div
            style={{
              marginTop: 'auto',
              padding: '0.75rem',
              backgroundColor: 'var(--bg-subtle)',
              borderRadius: 'var(--radius-sm)',
              fontSize: '0.75rem',
              color: 'var(--text-muted)',
              border: '1px solid var(--border-subtle)',
            }}
          >
            <div>Model: <strong className="mono" style={{ color: 'var(--text-secondary)' }}>FD001-v1</strong></div>
            <div>Dataset: <strong style={{ color: 'var(--text-secondary)' }}>C-MAPSS Replay</strong></div>
            <div style={{ marginTop: '0.25rem' }}>Units: <span className="mono">Operating Cycles</span></div>
          </div>
        </aside>

        {/* Main Content View */}
        <main
          style={{
            flex: 1,
            padding: '1.5rem',
            overflowY: 'auto',
            minWidth: 0,
          }}
        >
          {children}
        </main>
      </div>

      <style>{`
        @media (min-width: 768px) {
          .user-text-details {
            display: block !important;
          }
        }
        @media (max-width: 768px) {
          .mobile-menu-btn {
            display: inline-flex !important;
          }
          .portal-sidebar {
            position: fixed;
            top: 76px;
            bottom: 0;
            left: -260px;
            z-index: 50;
            transition: left 200ms ease;
          }
          .portal-sidebar.mobile-open {
            left: 0;
            box-shadow: var(--shadow-lg);
          }
          .logout-text {
            display: none;
          }
        }
      `}</style>
    </div>
  );
};
