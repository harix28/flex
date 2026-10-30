import React, { useState, useEffect } from 'react';
import { useAuth } from '../../context/AuthContext';
import {
  LayoutDashboard,
  Cpu,
  AlertTriangle,
  Activity,
  Clock,
  Wrench,
  FileText,
  Settings,
  Search,
  Bell,
  LogOut,
  Menu,
  X,
  Layers,
  Users,
} from 'lucide-react';

export type NavigationPage =
  | 'overview'
  | 'machines'
  | 'machine-detail'
  | 'maintenance-priority'
  | 'sensor-analytics'
  | 'failure-predictions'
  | 'maintenance-history'
  | 'work-orders'
  | 'work-order-detail'
  | 'reports'
  | 'settings'
  | 'model-monitoring'
  | 'registry'
  | 'members';

interface ShellProps {
  currentPage: NavigationPage;
  onNavigate: (page: NavigationPage, params?: Record<string, string>) => void;
  children: React.ReactNode;
}

export const Shell: React.FC<ShellProps> = ({ currentPage, onNavigate, children }) => {
  const { user, activeTenant, logout, canManageRegistry, canManageMembers } = useAuth();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [lastUpdated, setLastUpdated] = useState('');

  useEffect(() => {
    const updateTime = () => {
      const now = new Date();
      setLastUpdated(
        now.toLocaleDateString('en-US', {
          month: 'short',
          day: 'numeric',
          year: 'numeric',
        }) +
          ', ' +
          now.toLocaleTimeString('en-US', {
            hour: '2-digit',
            minute: '2-digit',
          })
      );
    };
    updateTime();
    const interval = setInterval(updateTime, 60000);
    return () => clearInterval(interval);
  }, []);

  const navItems = [
    { id: 'overview' as NavigationPage, label: 'Overview', icon: LayoutDashboard },
    { id: 'machines' as NavigationPage, label: 'Machines', icon: Cpu },
    { id: 'maintenance-priority' as NavigationPage, label: 'Maintenance Priority', icon: AlertTriangle },
    { id: 'sensor-analytics' as NavigationPage, label: 'Sensor Analytics', icon: Activity },
    { id: 'failure-predictions' as NavigationPage, label: 'Failure Predictions', icon: Clock },
    { id: 'maintenance-history' as NavigationPage, label: 'Maintenance History', icon: Wrench },
    { id: 'reports' as NavigationPage, label: 'Reports', icon: FileText },
    { id: 'settings' as NavigationPage, label: 'Settings', icon: Settings },
  ];

  // Extra admin / management links if applicable
  const adminNavItems = [
    ...(canManageRegistry()
      ? [{ id: 'registry' as NavigationPage, label: 'Registry Config', icon: Layers }]
      : []),
    ...(canManageMembers()
      ? [{ id: 'members' as NavigationPage, label: 'Organization Members', icon: Users }]
      : []),
  ];

  // Derive text initials from user display name or email
  const getInitials = () => {
    if (user?.display_name) {
      const parts = user.display_name.trim().split(/\s+/);
      if (parts.length >= 2) {
        return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
      }
      return user.display_name.slice(0, 2).toUpperCase();
    }
    if (user?.email) {
      return user.email.slice(0, 2).toUpperCase();
    }
    return 'PM';
  };

  const handleSearchKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && searchQuery.trim()) {
      onNavigate('machines', { search: searchQuery.trim() });
    }
  };

  return (
    <div style={{ display: 'flex', height: '100vh', overflow: 'hidden', backgroundColor: 'var(--bg-canvas)' }}>
      {/* 1. DARK NAVY SIDEBAR */}
      <aside
        className={`portal-sidebar ${mobileMenuOpen ? 'mobile-open' : ''}`}
        style={{
          width: '240px',
          backgroundColor: '#0f172a', // Dark Navy
          borderRight: '1px solid #1e293b',
          display: 'flex',
          flexDirection: 'column',
          flexShrink: 0,
          zIndex: 50,
          transition: 'transform 200ms ease',
        }}
      >
        {/* Plain Text Branding: "Predictive Maintenance" (No logo, no icon, no graphic) */}
        <div
          style={{
            padding: '1.25rem 1.25rem',
            borderBottom: '1px solid #1e293b',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <div
            onClick={() => onNavigate('overview')}
            style={{
              fontSize: '1.05rem',
              fontWeight: 700,
              color: '#ffffff',
              letterSpacing: '-0.02em',
              fontFamily: 'var(--font-heading)',
              cursor: 'pointer',
              userSelect: 'none',
              lineHeight: 1.2,
            }}
          >
            Predictive Maintenance
          </div>
          <button
            type="button"
            className="mobile-close-btn"
            onClick={() => setMobileMenuOpen(false)}
            style={{
              display: 'none',
              background: 'none',
              border: 'none',
              color: '#94a3b8',
              cursor: 'pointer',
              padding: '0.25rem',
            }}
          >
            <X size={18} />
          </button>
        </div>

        {/* Navigation Items */}
        <div
          style={{
            flex: 1,
            padding: '1rem 0.75rem',
            display: 'flex',
            flexDirection: 'column',
            gap: '0.25rem',
            overflowY: 'auto',
          }}
        >
          <div
            style={{
              fontSize: '0.6875rem',
              fontWeight: 600,
              color: '#64748b',
              textTransform: 'uppercase',
              letterSpacing: '0.05em',
              padding: '0 0.5rem 0.35rem',
            }}
          >
            Navigation
          </div>

          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive =
              currentPage === item.id ||
              (item.id === 'machines' && currentPage === 'machine-detail') ||
              (item.id === 'maintenance-history' && (currentPage === 'work-orders' || currentPage === 'work-order-detail'));

            return (
              <button
                key={item.id}
                type="button"
                onClick={() => {
                  if (item.id === 'maintenance-history') {
                    onNavigate('work-orders');
                  } else {
                    onNavigate(item.id);
                  }
                  setMobileMenuOpen(false);
                }}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.75rem',
                  padding: '0.625rem 0.75rem',
                  fontSize: '0.875rem',
                  fontWeight: isActive ? 600 : 500,
                  color: isActive ? '#ffffff' : '#94a3b8',
                  backgroundColor: isActive ? '#1e293b' : 'transparent',
                  border: 'none',
                  borderLeft: isActive ? '3px solid #2563eb' : '3px solid transparent',
                  borderRadius: '4px',
                  cursor: 'pointer',
                  textAlign: 'left',
                  transition: 'background-color 150ms ease, color 150ms ease',
                  width: '100%',
                }}
                onMouseEnter={(e) => {
                  if (!isActive) {
                    e.currentTarget.style.backgroundColor = '#1e293b';
                    e.currentTarget.style.color = '#f8fafc';
                  }
                }}
                onMouseLeave={(e) => {
                  if (!isActive) {
                    e.currentTarget.style.backgroundColor = 'transparent';
                    e.currentTarget.style.color = '#94a3b8';
                  }
                }}
              >
                <Icon
                  size={18}
                  style={{
                    color: isActive ? '#38bdf8' : '#64748b',
                    flexShrink: 0,
                  }}
                />
                <span style={{ whiteSpace: 'nowrap' }}>{item.label}</span>
              </button>
            );
          })}

          {adminNavItems.length > 0 && (
            <>
              <div
                style={{
                  fontSize: '0.6875rem',
                  fontWeight: 600,
                  color: '#64748b',
                  textTransform: 'uppercase',
                  letterSpacing: '0.05em',
                  padding: '0.85rem 0.5rem 0.35rem',
                }}
              >
                System & Admin
              </div>
              {adminNavItems.map((item) => {
                const Icon = item.icon;
                const isActive = currentPage === item.id;
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
                      color: isActive ? '#ffffff' : '#94a3b8',
                      backgroundColor: isActive ? '#1e293b' : 'transparent',
                      border: 'none',
                      borderLeft: isActive ? '3px solid #2563eb' : '3px solid transparent',
                      borderRadius: '4px',
                      cursor: 'pointer',
                      textAlign: 'left',
                      transition: 'background-color 150ms ease, color 150ms ease',
                      width: '100%',
                    }}
                    onMouseEnter={(e) => {
                      if (!isActive) {
                        e.currentTarget.style.backgroundColor = '#1e293b';
                        e.currentTarget.style.color = '#f8fafc';
                      }
                    }}
                    onMouseLeave={(e) => {
                      if (!isActive) {
                        e.currentTarget.style.backgroundColor = 'transparent';
                        e.currentTarget.style.color = '#94a3b8';
                      }
                    }}
                  >
                    <Icon size={18} style={{ color: isActive ? '#38bdf8' : '#64748b', flexShrink: 0 }} />
                    <span style={{ whiteSpace: 'nowrap' }}>{item.label}</span>
                  </button>
                );
              })}
            </>
          )}
        </div>

        {/* Sidebar Footer */}
        <div
          style={{
            padding: '1rem 0.875rem',
            borderTop: '1px solid #1e293b',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.625rem' }}>
            <div
              style={{
                width: '32px',
                height: '32px',
                borderRadius: '50%',
                backgroundColor: '#2563eb',
                color: '#ffffff',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: '0.8125rem',
                fontWeight: 600,
                letterSpacing: '0.02em',
                flexShrink: 0,
              }}
              title={user?.display_name || user?.email || 'User'}
            >
              {getInitials()}
            </div>
            <div style={{ overflow: 'hidden' }}>
              <div
                style={{
                  fontSize: '0.8125rem',
                  fontWeight: 600,
                  color: '#ffffff',
                  whiteSpace: 'nowrap',
                  textOverflow: 'ellipsis',
                  overflow: 'hidden',
                }}
              >
                {user?.display_name || 'Operator'}
              </div>
              <div
                style={{
                  fontSize: '0.6875rem',
                  color: '#64748b',
                  whiteSpace: 'nowrap',
                  textOverflow: 'ellipsis',
                  overflow: 'hidden',
                }}
              >
                {activeTenant?.name || 'Fleet'}
              </div>
            </div>
          </div>
          <button
            type="button"
            onClick={logout}
            title="Log out"
            style={{
              background: 'none',
              border: 'none',
              color: '#94a3b8',
              cursor: 'pointer',
              padding: '0.35rem',
              borderRadius: '4px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <LogOut size={16} />
          </button>
        </div>
      </aside>

      {/* 2. MAIN LAYOUT (TOPBAR + SCROLLABLE CONTENT) */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0, height: '100vh', overflow: 'hidden' }}>
        {/* Topbar */}
        <header
          style={{
            backgroundColor: '#ffffff',
            borderBottom: '1px solid var(--border-subtle)',
            padding: '0.75rem 1.5rem',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: '1rem',
            flexShrink: 0,
            zIndex: 40,
          }}
        >
          {/* Left: Mobile hamburger & Search Machines */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', flex: 1, maxWidth: '480px' }}>
            <button
              type="button"
              className="mobile-hamburger-btn"
              onClick={() => setMobileMenuOpen(true)}
              style={{
                display: 'none',
                background: 'none',
                border: '1px solid var(--border-subtle)',
                borderRadius: '6px',
                padding: '0.4rem',
                cursor: 'pointer',
              }}
              aria-label="Open navigation menu"
            >
              <Menu size={18} />
            </button>

            {/* Search machines */}
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '0.5rem',
                backgroundColor: 'var(--bg-canvas)',
                border: '1px solid var(--border-subtle)',
                borderRadius: '6px',
                padding: '0.4rem 0.75rem',
                width: '100%',
              }}
            >
              <Search size={16} color="var(--text-muted)" />
              <input
                type="text"
                placeholder="Search machines by ID or name..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                onKeyDown={handleSearchKeyDown}
                style={{
                  border: 'none',
                  background: 'transparent',
                  outline: 'none',
                  fontSize: '0.8125rem',
                  color: 'var(--text-primary)',
                  width: '100%',
                }}
              />
            </div>
          </div>

          {/* Right: Demo badge, Last Updated, Notifications, User Initials */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
            {/* Simulation/Demo Mode Badge */}
            <span
              style={{
                fontSize: '0.6875rem',
                fontWeight: 600,
                textTransform: 'uppercase',
                padding: '0.2rem 0.5rem',
                borderRadius: '4px',
                backgroundColor: '#f1f5f9',
                color: '#475569',
                border: '1px solid #cbd5e1',
                whiteSpace: 'nowrap',
              }}
            >
              Demo Mode · NASA C-MAPSS
            </span>

            {/* Last Updated Timestamp */}
            {lastUpdated && (
              <span
                style={{
                  fontSize: '0.75rem',
                  color: 'var(--text-secondary)',
                  whiteSpace: 'nowrap',
                  display: 'none',
                }}
                className="topbar-timestamp"
              >
                Last updated: <strong>{lastUpdated}</strong>
              </span>
            )}

            {/* Notification Icon */}
            <div
              style={{
                position: 'relative',
                cursor: 'pointer',
                color: 'var(--text-secondary)',
                padding: '0.35rem',
                borderRadius: '4px',
              }}
              title="Notifications"
            >
              <Bell size={18} />
              <span
                style={{
                  position: 'absolute',
                  top: '2px',
                  right: '2px',
                  width: '7px',
                  height: '7px',
                  borderRadius: '50%',
                  backgroundColor: '#ef4444',
                }}
              />
            </div>

            {/* User Profile - Text Initials Only */}
            <div
              style={{
                width: '32px',
                height: '32px',
                borderRadius: '50%',
                backgroundColor: '#2563eb',
                color: '#ffffff',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: '0.8125rem',
                fontWeight: 600,
                letterSpacing: '0.02em',
                cursor: 'pointer',
                flexShrink: 0,
              }}
              title={user?.display_name || user?.email || 'User'}
            >
              {getInitials()}
            </div>
          </div>
        </header>

        {/* Scrollable Main Content View */}
        <main
          style={{
            flex: 1,
            overflowY: 'auto',
            padding: '1.5rem',
            backgroundColor: 'var(--bg-canvas)',
          }}
        >
          <div style={{ maxWidth: '1440px', margin: '0 auto' }}>
            {children}
          </div>
        </main>
      </div>

      <style>{`
        @media (min-width: 992px) {
          .topbar-timestamp {
            display: inline-block !important;
          }
        }
        @media (max-width: 768px) {
          .mobile-hamburger-btn {
            display: inline-flex !important;
          }
          .mobile-close-btn {
            display: inline-block !important;
          }
          .portal-sidebar {
            position: fixed;
            top: 0;
            bottom: 0;
            left: 0;
            transform: translateX(-100%);
          }
          .portal-sidebar.mobile-open {
            transform: translateX(0);
          }
        }
      `}</style>
    </div>
  );
};
