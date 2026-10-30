import React, { useState } from 'react';
import { useAuth } from '../../context/AuthContext';
import {
  LayoutDashboard,
  Cpu,
  Wrench,
  Layers,
  Users,
  LogOut,
  Menu,
  X,
  Activity,
  ShieldCheck,
  Boxes,
  ListChecks,
  Share2,
} from 'lucide-react';

export type NavigationPage = 'overview' | 'machines' | 'machine-detail' | 'work-orders' | 'work-order-detail' | 'planning' | 'jobs' | 'integrations' | 'model-monitoring' | 'registry' | 'members';

interface ShellProps {
  currentPage: NavigationPage;
  onNavigate: (page: NavigationPage, params?: Record<string, string>) => void;
  children: React.ReactNode;
}

export const Shell: React.FC<ShellProps> = ({ currentPage, onNavigate, children }) => {
  const {
    user,
    logout,
    canManageRegistry,
    canManageMembers,
    isGeneralManager,
    isMaintenanceEngineer,
    isTechnician,
    roleTitle,
  } = useAuth();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [sidebarHovered, setSidebarHovered] = useState(false);

  let navItems: Array<{ id: NavigationPage; label: string; icon: any }> = [];

  if (isTechnician) {
    // Role 3: Maintenance Technician Allocation (Execution, telemetry inspection, parts lookup)
    navItems = [
      { id: 'work-orders', label: 'My Assigned Work Orders', icon: Wrench },
      { id: 'machines', label: 'Assigned Engines & Telemetry', icon: Cpu },
      { id: 'planning', label: 'Warehouse Parts Lookup', icon: Boxes },
    ];
  } else if (isMaintenanceEngineer && !isGeneralManager) {
    // Role 2: Maintenance Engineer Allocation (Planning, approvals, fleet scoring, MLOps)
    navItems = [
      { id: 'overview', label: 'Engineering Dashboard', icon: LayoutDashboard },
      { id: 'machines', label: 'Fleet Machines & Health', icon: Cpu },
      { id: 'work-orders', label: 'Work Orders & Approvals', icon: Wrench },
      { id: 'planning', label: 'Maintenance Planning', icon: Boxes },
      { id: 'jobs', label: 'Fleet Scoring & Jobs', icon: ListChecks },
      { id: 'model-monitoring', label: 'Model Observability & MLOps', icon: Activity },
      ...(canManageRegistry() ? [{ id: 'registry' as NavigationPage, label: 'Registry Config', icon: Layers }] : []),
    ];
  } else {
    // Role 1: General Manager (Admin) Allocation (Executive oversight, members, integrations)
    navItems = [
      { id: 'overview', label: 'Executive Overview', icon: LayoutDashboard },
      { id: 'machines', label: 'Fleet Registry', icon: Cpu },
      { id: 'work-orders', label: 'Work Orders Oversight', icon: Wrench },
      { id: 'planning', label: 'Maintenance Planning', icon: Boxes },
      { id: 'jobs', label: 'Background Outbox Jobs', icon: ListChecks },
      { id: 'integrations', label: 'Live Integrations & Security', icon: Share2 },
      { id: 'model-monitoring', label: 'Model Observability', icon: Activity },
      ...(canManageRegistry() ? [{ id: 'registry' as NavigationPage, label: 'Registry Config', icon: Layers }] : []),
      ...(canManageMembers() ? [{ id: 'members' as NavigationPage, label: 'Organization Members', icon: Users }] : []),
    ];
  }

  const getRoleBadgeStyle = () => {
    if (isGeneralManager) {
      return {
        backgroundColor: 'rgba(99, 102, 241, 0.15)',
        color: '#6366f1',
        border: '1px solid rgba(99, 102, 241, 0.3)',
      };
    }
    if (isMaintenanceEngineer) {
      return {
        backgroundColor: 'rgba(14, 165, 233, 0.15)',
        color: 'var(--primary)',
        border: '1px solid rgba(14, 165, 233, 0.3)',
      };
    }
    if (isTechnician) {
      return {
        backgroundColor: 'rgba(34, 197, 94, 0.15)',
        color: 'var(--success)',
        border: '1px solid rgba(34, 197, 94, 0.3)',
      };
    }
    return {
      backgroundColor: 'rgba(148, 163, 184, 0.15)',
      color: 'var(--text-muted)',
      border: '1px solid var(--border-subtle)',
    };
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', overflow: 'hidden', backgroundColor: 'var(--bg-canvas)' }}>
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
            width: '100%',
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
            {/* User Profile & Role Badges */}
            {user && (
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.625rem' }}>

                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <span
                    style={{
                      ...getRoleBadgeStyle(),
                      padding: '0.25rem 0.65rem',
                      borderRadius: 'var(--radius-sm)',
                      fontSize: '0.75rem',
                      fontWeight: 600,
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '0.35rem',
                    }}
                    title={`Allocated Persona: ${roleTitle}`}
                  >
                    <ShieldCheck size={13} />
                    <span>{roleTitle}</span>
                  </span>
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
          width: '100%',
          minHeight: 0,
          overflow: 'hidden',
        }}
      >
        {/* Navigation Sidebar (Collapsible with Expand-on-Hover) */}
        <aside
          className={`portal-sidebar ${mobileMenuOpen ? 'mobile-open' : ''}`}
          onMouseEnter={() => setSidebarHovered(true)}
          onMouseLeave={() => setSidebarHovered(false)}
          style={{
            width: sidebarHovered ? '240px' : '68px',
            backgroundColor: 'var(--bg-surface)',
            borderRight: '1px solid var(--border-subtle)',
            padding: '1.25rem 0.5rem',
            display: 'flex',
            flexDirection: 'column',
            gap: '0.35rem',
            flexShrink: 0,
            overflowY: 'auto',
            overflowX: 'hidden',
            transition: 'width 250ms cubic-bezier(0.4, 0, 0.2, 1)',
            zIndex: 30,
            boxShadow: sidebarHovered ? 'var(--shadow-lg)' : 'none',
          }}
        >
          <div
            style={{
              fontSize: '0.7rem',
              fontWeight: 600,
              color: 'var(--text-muted)',
              textTransform: 'uppercase',
              padding: '0 0.5rem 0.5rem',
              letterSpacing: '0.05em',
              whiteSpace: 'nowrap',
              overflow: 'hidden',
              opacity: sidebarHovered ? 1 : 0,
              transition: 'opacity 150ms ease',
              height: '24px',
            }}
          >
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
                title={!sidebarHovered ? item.label : undefined}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.85rem',
                  padding: sidebarHovered ? '0.625rem 0.75rem' : '0.625rem 0.85rem',
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
                  whiteSpace: 'nowrap',
                  overflow: 'hidden',
                }}
              >
                <Icon size={20} style={{ color: isActive ? 'var(--primary)' : 'var(--text-muted)', flexShrink: 0 }} />
                <span
                  style={{
                    opacity: sidebarHovered ? 1 : 0,
                    transform: sidebarHovered ? 'translateX(0)' : 'translateX(-8px)',
                    transition: 'opacity 200ms ease, transform 200ms ease',
                    whiteSpace: 'nowrap',
                  }}
                >
                  {item.label}
                </span>
              </button>
            );
          })}


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
