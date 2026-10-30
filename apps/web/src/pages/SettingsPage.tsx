import React from 'react';
import { useAuth } from '../context/AuthContext';
import { Server, Globe } from 'lucide-react';

export const SettingsPage: React.FC = () => {
  const { user, activeTenant } = useAuth();

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      <div>
        <h1 style={{ fontSize: '1.5rem', fontWeight: 700, margin: 0, color: 'var(--text-primary)' }}>
          System &amp; Organization Settings
        </h1>
        <p style={{ fontSize: '0.875rem', color: 'var(--text-secondary)', marginTop: '0.25rem' }}>
          Predictive maintenance runtime parameters, tenant isolation boundaries, and user profile configuration.
        </p>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(360px, 1fr))', gap: '1.5rem' }}>
        {/* Organization / Tenant Card */}
        <div className="card" style={{ padding: '1.5rem', backgroundColor: '#ffffff' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '1rem' }}>
            <Globe size={18} color="#2563eb" />
            <h2 style={{ fontSize: '1rem', fontWeight: 600, margin: 0 }}>Organization Profile</h2>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', fontSize: '0.8125rem' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid var(--border-subtle)', paddingBottom: '0.5rem' }}>
              <span style={{ color: 'var(--text-muted)' }}>Authenticated User</span>
              <strong>{user?.display_name || user?.email || 'Administrator'}</strong>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid var(--border-subtle)', paddingBottom: '0.5rem' }}>
              <span style={{ color: 'var(--text-muted)' }}>Tenant Name</span>
              <strong>{activeTenant?.name || 'Default Organization'}</strong>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid var(--border-subtle)', paddingBottom: '0.5rem' }}>
              <span style={{ color: 'var(--text-muted)' }}>Tenant Slug</span>
              <code style={{ fontSize: '0.75rem' }}>{activeTenant?.slug || 'meridian-a'}</code>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid var(--border-subtle)', paddingBottom: '0.5rem' }}>
              <span style={{ color: 'var(--text-muted)' }}>Assigned Roles</span>
              <span style={{ fontWeight: 600, color: '#2563eb' }}>{activeTenant?.roles.join(', ') || 'Viewer'}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: 'var(--text-muted)' }}>Tenant Boundary Status</span>
              <span style={{ color: '#16a34a', fontWeight: 600 }}>Active &amp; Enforced</span>
            </div>
          </div>
        </div>

        {/* Runtime Environment Card */}
        <div className="card" style={{ padding: '1.5rem', backgroundColor: '#ffffff' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '1rem' }}>
            <Server size={18} color="#059669" />
            <h2 style={{ fontSize: '1rem', fontWeight: 600, margin: 0 }}>Runtime &amp; Telemetry Mode</h2>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', fontSize: '0.8125rem' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid var(--border-subtle)', paddingBottom: '0.5rem' }}>
              <span style={{ color: 'var(--text-muted)' }}>Operating Mode</span>
              <span style={{ fontWeight: 600, color: '#d97706' }}>NASA C-MAPSS Simulation</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid var(--border-subtle)', paddingBottom: '0.5rem' }}>
              <span style={{ color: 'var(--text-muted)' }}>Feature Extraction Pipeline</span>
              <code>cmapss-trailing-v1 (W=30)</code>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid var(--border-subtle)', paddingBottom: '0.5rem' }}>
              <span style={{ color: 'var(--text-muted)' }}>Database Backend</span>
              <strong>PostgreSQL 18 (Local Isolated)</strong>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: 'var(--text-muted)' }}>Hardware Gateway Interface</span>
              <span style={{ color: 'var(--text-muted)' }}>Ready for Modbus / MQTT Stream</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
