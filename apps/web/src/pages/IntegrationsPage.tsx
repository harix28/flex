import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../context/AuthContext';
import { integrationsApi, notificationsApi } from '../services/api';
import { IntegrationsStatus, WebhookSubscription, WebhookDispatch } from '../services/types';
import { ErrorState } from '../components/common/ErrorState';
import {
  Share2,
  Zap,
  Radio,
  Bell,
  CheckCircle2,
  AlertTriangle,
  RefreshCw,
  Plus,
  Trash2,
  Shield,
  Send,
} from 'lucide-react';

export const IntegrationsPage: React.FC = () => {
  const { activeTenant } = useAuth();
  const [activeTab, setActiveTab] = useState<'gateways' | 'cmms' | 'webhooks'>('gateways');

  // Integrations status state
  const [status, setStatus] = useState<IntegrationsStatus | null>(null);
  const [isLoadingStatus, setIsLoadingStatus] = useState(false);

  // Webhooks state
  const [webhooks, setWebhooks] = useState<WebhookSubscription[]>([]);
  const [dispatches, setDispatches] = useState<WebhookDispatch[]>([]);
  const [isLoadingWebhooks, setIsLoadingWebhooks] = useState(false);

  // New webhook form state
  const [showAddWebhook, setShowAddWebhook] = useState(false);
  const [newUrl, setNewUrl] = useState('');
  const [newSecret, setNewSecret] = useState('');
  const [newLabel, setNewLabel] = useState('');
  const [isCreatingWebhook, setIsCreatingWebhook] = useState(false);

  // CMMS export test state
  const [cmmsWoId, setCmmsWoId] = useState('');
  const [cmmsTarget, setCmmsTarget] = useState<'sap_pm' | 'maximo'>('sap_pm');
  const [cmmsResult, setCmmsResult] = useState<any>(null);
  const [cmmsError, setCmmsError] = useState<string | null>(null);
  const [isExportingCmms, setIsExportingCmms] = useState(false);

  const [feedback, setFeedback] = useState<{ type: 'success' | 'error'; message: string } | null>(null);

  const loadAll = useCallback(async () => {
    if (!activeTenant) return;
    setIsLoadingStatus(true);
    setIsLoadingWebhooks(true);
    try {
      const [statusRes, webhooksRes, historyRes] = await Promise.all([
        integrationsApi.getStatus(activeTenant.id),
        notificationsApi.listWebhooks(activeTenant.id),
        notificationsApi.getDispatchHistory(activeTenant.id, 20),
      ]);
      setStatus(statusRes);
      setWebhooks(webhooksRes.items || []);
      setDispatches(historyRes.items || []);
    } catch (err: any) {
      setFeedback({ type: 'error', message: err.message || 'Failed to load integrations status' });
    } finally {
      setIsLoadingStatus(false);
      setIsLoadingWebhooks(false);
    }
  }, [activeTenant]);

  useEffect(() => {
    loadAll();
  }, [loadAll]);

  const handleCreateWebhook = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!activeTenant || !newUrl.trim() || !newSecret.trim()) return;
    setIsCreatingWebhook(true);
    setFeedback(null);
    try {
      await notificationsApi.createWebhook(activeTenant.id, {
        url: newUrl.trim(),
        secret: newSecret.trim(),
        events: ['alert.urgent', 'alert.high'],
        label: newLabel.trim() || 'Hangar Alerting Webhook',
      });
      setFeedback({ type: 'success', message: 'Webhook registered successfully with HMAC-SHA256 signing.' });
      setNewUrl('');
      setNewSecret('');
      setNewLabel('');
      setShowAddWebhook(false);
      await loadAll();
    } catch (err: any) {
      setFeedback({ type: 'error', message: err.message || 'Failed to create webhook' });
    } finally {
      setIsCreatingWebhook(false);
    }
  };

  const handleDeleteWebhook = async (id: string) => {
    if (!activeTenant) return;
    if (!window.confirm('Are you sure you want to delete this webhook subscription?')) return;
    try {
      await notificationsApi.deleteWebhook(activeTenant.id, id);
      setFeedback({ type: 'success', message: 'Webhook subscription removed.' });
      await loadAll();
    } catch (err: any) {
      setFeedback({ type: 'error', message: err.message || 'Failed to delete webhook' });
    }
  };

  const handleTestDispatch = async () => {
    if (!activeTenant) return;
    setFeedback(null);
    try {
      const res = await notificationsApi.testDispatch(activeTenant.id, {
        event_type: 'alert.urgent',
        summary: 'Demo automated test dispatch for HMAC-SHA256 verification and anti-fatigue deduplication.',
        priority: 'urgent',
      });
      setFeedback({
        type: 'success',
        message: `Dispatched test alert. ${res.subscribers_notified} subscriber(s) notified with HMAC-SHA256 signature.`,
      });
      await loadAll();
    } catch (err: any) {
      setFeedback({ type: 'error', message: err.message || 'Failed to dispatch test notification' });
    }
  };

  const handleExportCmms = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!activeTenant || !cmmsWoId.trim()) return;
    setIsExportingCmms(true);
    setCmmsError(null);
    setCmmsResult(null);

    try {
      const res = await integrationsApi.exportToCmms(activeTenant.id, cmmsWoId.trim(), cmmsTarget);
      setCmmsResult(res);
    } catch (err: any) {
      setCmmsError(err.message || 'CMMS export failed. Remember that unapproved draft work orders are rejected by policy.');
    } finally {
      setIsExportingCmms(false);
    }
  };

  return (
    <div style={{ padding: '1.5rem', maxWidth: '1400px', margin: '0 auto', display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '1rem' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.625rem' }}>
            <Share2 size={24} style={{ color: 'var(--primary)' }} />
            <h1 style={{ fontSize: '1.5rem', fontWeight: 700, margin: 0 }}>Live Integrations, CMMS & Webhooks</h1>
          </div>
          <p style={{ margin: '0.35rem 0 0', color: 'var(--text-muted)', fontSize: '0.875rem' }}>
            Connect live factory sensors, export approved jobs to SAP or Maximo, and send instant alert notifications.
          </p>
        </div>

        <button
          type="button"
          className="btn btn-secondary"
          onClick={loadAll}
          disabled={isLoadingStatus || isLoadingWebhooks}
          style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', padding: '0.5rem 1rem' }}
        >
          <RefreshCw size={15} className={isLoadingStatus || isLoadingWebhooks ? 'spin' : ''} />
          Refresh Connectors
        </button>
      </div>

      {feedback && (
        <div
          style={{
            padding: '0.875rem 1.25rem',
            borderRadius: 'var(--radius-md)',
            backgroundColor: feedback.type === 'success' ? 'rgba(34, 197, 94, 0.1)' : 'rgba(239, 68, 68, 0.1)',
            border: `1px solid ${feedback.type === 'success' ? 'var(--success)' : 'var(--danger)'}`,
            color: feedback.type === 'success' ? 'var(--success)' : 'var(--danger)',
            fontSize: '0.875rem',
            display: 'flex',
            alignItems: 'center',
            gap: '0.5rem',
          }}
        >
          {feedback.type === 'success' ? <CheckCircle2 size={16} /> : <AlertTriangle size={16} />}
          {feedback.message}
        </div>
      )}

      {/* Tabs */}
      <div style={{ borderBottom: '1px solid var(--border-subtle)', display: 'flex', gap: '1rem' }}>
        <button
          type="button"
          onClick={() => setActiveTab('gateways')}
          style={{
            padding: '0.75rem 0.5rem',
            background: 'none',
            border: 'none',
            borderBottom: activeTab === 'gateways' ? '2px solid var(--primary)' : '2px solid transparent',
            color: activeTab === 'gateways' ? 'var(--primary)' : 'var(--text-muted)',
            fontWeight: activeTab === 'gateways' ? 600 : 500,
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: '0.5rem',
          }}
        >
          <Radio size={16} />
          IoT Edge Gateways
        </button>

        <button
          type="button"
          onClick={() => setActiveTab('cmms')}
          style={{
            padding: '0.75rem 0.5rem',
            background: 'none',
            border: 'none',
            borderBottom: activeTab === 'cmms' ? '2px solid var(--primary)' : '2px solid transparent',
            color: activeTab === 'cmms' ? 'var(--primary)' : 'var(--text-muted)',
            fontWeight: activeTab === 'cmms' ? 600 : 500,
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: '0.5rem',
          }}
        >
          <Zap size={16} />
          Enterprise CMMS (SAP PM & Maximo)
        </button>

        <button
          type="button"
          onClick={() => setActiveTab('webhooks')}
          style={{
            padding: '0.75rem 0.5rem',
            background: 'none',
            border: 'none',
            borderBottom: activeTab === 'webhooks' ? '2px solid var(--primary)' : '2px solid transparent',
            color: activeTab === 'webhooks' ? 'var(--primary)' : 'var(--text-muted)',
            fontWeight: activeTab === 'webhooks' ? 600 : 500,
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: '0.5rem',
          }}
        >
          <Bell size={16} />
          HMAC Webhook Alerting ({webhooks.length})
        </button>
      </div>

      {/* Tab 1: IoT Edge Gateways */}
      {activeTab === 'gateways' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          <div style={{ backgroundColor: 'var(--bg-surface)', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-subtle)', padding: '1.25rem' }}>
            <h2 style={{ fontSize: '1.0625rem', fontWeight: 600, margin: 0 }}>Edge Gateway Normalizer & Telemetry Ingestion</h2>
            <p style={{ margin: '0.35rem 0 1rem', color: 'var(--text-muted)', fontSize: '0.875rem' }}>
              Standardizes raw MQTT Sparkplug B and OPC-UA edge payload frames into immutable observation cycles.
            </p>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '1rem' }}>
              <div style={{ backgroundColor: 'var(--bg-canvas)', padding: '1rem', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)' }}>
                <span style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase' }}>Supported Protocols</span>
                <div style={{ marginTop: '0.35rem', display: 'flex', gap: '0.5rem' }}>
                  <span style={{ backgroundColor: 'rgba(14, 165, 233, 0.15)', color: 'var(--primary)', padding: '0.2rem 0.5rem', borderRadius: 'var(--radius-sm)', fontSize: '0.8125rem', fontWeight: 600 }}>
                    MQTT Sparkplug B
                  </span>
                  <span style={{ backgroundColor: 'rgba(14, 165, 233, 0.15)', color: 'var(--primary)', padding: '0.2rem 0.5rem', borderRadius: 'var(--radius-sm)', fontSize: '0.8125rem', fontWeight: 600 }}>
                    OPC-UA Part 8
                  </span>
                </div>
              </div>

              <div style={{ backgroundColor: 'var(--bg-canvas)', padding: '1rem', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)' }}>
                <span style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase' }}>Enforced Schema Bounds</span>
                <div style={{ marginTop: '0.35rem', fontSize: '0.8125rem', fontWeight: 500 }}>
                  3 Operating Settings & 21 Sensor Channels (Finite Float)
                </div>
              </div>

              <div style={{ backgroundColor: 'var(--bg-canvas)', padding: '1rem', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)' }}>
                <span style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase' }}>Gateway Status</span>
                <div style={{ marginTop: '0.35rem', display: 'flex', alignItems: 'center', gap: '0.35rem', color: 'var(--success)', fontWeight: 600, fontSize: '0.8125rem' }}>
                  <CheckCircle2 size={16} />
                  {(status?.edge_gateways.status || 'ready_for_ingestion').toUpperCase()}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Tab 2: CMMS Connectors */}
      {activeTab === 'cmms' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          <div style={{ backgroundColor: 'var(--bg-surface)', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-subtle)', padding: '1.25rem' }}>
            <h2 style={{ fontSize: '1.0625rem', fontWeight: 600, margin: 0 }}>Enterprise CMMS Synchronization</h2>
            <p style={{ margin: '0.35rem 0 1rem', color: 'var(--text-muted)', fontSize: '0.875rem' }}>
              Direct export adapters to SAP Plant Maintenance (PM01) and IBM Maximo (MIF).
            </p>

            {/* Policy Alert */}
            <div style={{ padding: '0.875rem 1rem', borderRadius: 'var(--radius-sm)', backgroundColor: 'rgba(217, 119, 6, 0.1)', border: '1px solid var(--warning)', marginBottom: '1.25rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <Shield size={18} style={{ color: 'var(--warning)', flexShrink: 0 }} />
              <div style={{ fontSize: '0.8125rem', color: 'var(--text-primary)' }}>
                <strong>Strict Human Approval Policy Enforced:</strong> Work orders in <code>draft</code> status are rejected. Only approved or completed work orders signed off by an authorized plant manager can synchronize to enterprise CMMS systems.
              </div>
            </div>

            {/* Test Export Form */}
            <form onSubmit={handleExportCmms} style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', maxWidth: '600px' }}>
              <label style={{ fontSize: '0.8125rem', fontWeight: 600 }}>Work Order UUID:</label>
              <input
                type="text"
                placeholder="Paste Work Order UUID..."
                value={cmmsWoId}
                onChange={(e) => setCmmsWoId(e.target.value)}
                style={{
                  padding: '0.5rem 0.75rem',
                  borderRadius: 'var(--radius-sm)',
                  border: '1px solid var(--border-subtle)',
                  backgroundColor: 'var(--bg-canvas)',
                  color: 'var(--text-primary)',
                  fontSize: '0.875rem',
                }}
              />

              <label style={{ fontSize: '0.8125rem', fontWeight: 600 }}>Target CMMS System:</label>
              <select
                value={cmmsTarget}
                onChange={(e) => setCmmsTarget(e.target.value as any)}
                style={{
                  padding: '0.5rem 0.75rem',
                  borderRadius: 'var(--radius-sm)',
                  border: '1px solid var(--border-subtle)',
                  backgroundColor: 'var(--bg-canvas)',
                  color: 'var(--text-primary)',
                  fontSize: '0.875rem',
                }}
              >
                <option value="sap_pm">SAP Plant Maintenance (PM01 Maintenance Order)</option>
                <option value="maximo">IBM Maximo (MIF Work Order Structure)</option>
              </select>

              <button
                type="submit"
                className="btn btn-primary"
                disabled={isExportingCmms || !cmmsWoId.trim()}
                style={{ marginTop: '0.5rem', width: 'fit-content', padding: '0.5rem 1.25rem' }}
              >
                {isExportingCmms ? 'Exporting Payload...' : `Generate ${cmmsTarget.toUpperCase()} Order`}
              </button>
            </form>

            {cmmsError && (
              <div style={{ marginTop: '1rem' }}>
                <ErrorState message={cmmsError} />
              </div>
            )}

            {cmmsResult && (
              <div style={{ marginTop: '1.25rem', backgroundColor: 'var(--bg-canvas)', padding: '1rem', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
                  <span style={{ fontWeight: 600, fontSize: '0.875rem', color: 'var(--success)' }}>
                    Export Payload Generated Successfully ({cmmsResult.target.toUpperCase()})
                  </span>
                </div>
                <pre style={{ margin: 0, padding: '0.75rem', borderRadius: 'var(--radius-sm)', backgroundColor: 'var(--bg-surface)', fontSize: '0.75rem', overflowX: 'auto', border: '1px solid var(--border-subtle)' }}>
                  {JSON.stringify(cmmsResult.payload, null, 2)}
                </pre>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Tab 3: Webhooks */}
      {activeTab === 'webhooks' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
          {/* Webhook Subscriptions Table */}
          <div style={{ backgroundColor: 'var(--bg-surface)', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-subtle)', padding: '1.25rem' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem', flexWrap: 'wrap', gap: '0.75rem' }}>
              <div>
                <h2 style={{ fontSize: '1rem', fontWeight: 600, margin: 0 }}>Registered Webhook Endpoints</h2>
                <span style={{ fontSize: '0.8125rem', color: 'var(--text-muted)' }}>Signed using HMAC-SHA256 headers</span>
              </div>

              <div style={{ display: 'flex', gap: '0.75rem' }}>
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={handleTestDispatch}
                  style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', padding: '0.4rem 0.85rem' }}
                >
                  <Send size={14} />
                  Test Dispatch Alert
                </button>

                <button
                  type="button"
                  className="btn btn-primary"
                  onClick={() => setShowAddWebhook(!showAddWebhook)}
                  style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', padding: '0.4rem 0.85rem' }}
                >
                  <Plus size={14} />
                  Register Endpoint
                </button>
              </div>
            </div>

            {/* Add Webhook Form */}
            {showAddWebhook && (
              <form onSubmit={handleCreateWebhook} style={{ backgroundColor: 'var(--bg-canvas)', padding: '1rem', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)', marginBottom: '1.25rem', display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                <h3 style={{ fontSize: '0.875rem', fontWeight: 600, margin: 0 }}>Register New Webhook</h3>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '0.75rem' }}>
                  <input
                    type="text"
                    placeholder="Label (e.g. Hangar 4 Webhook)..."
                    value={newLabel}
                    onChange={(e) => setNewLabel(e.target.value)}
                    style={{ padding: '0.5rem 0.75rem', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)', backgroundColor: 'var(--bg-surface)', fontSize: '0.8125rem' }}
                  />
                  <input
                    type="url"
                    placeholder="Webhook URL (https://...)..."
                    value={newUrl}
                    onChange={(e) => setNewUrl(e.target.value)}
                    required
                    style={{ padding: '0.5rem 0.75rem', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)', backgroundColor: 'var(--bg-surface)', fontSize: '0.8125rem' }}
                  />
                  <input
                    type="password"
                    placeholder="Shared HMAC Secret..."
                    value={newSecret}
                    onChange={(e) => setNewSecret(e.target.value)}
                    required
                    style={{ padding: '0.5rem 0.75rem', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)', backgroundColor: 'var(--bg-surface)', fontSize: '0.8125rem' }}
                  />
                </div>
                <div style={{ display: 'flex', gap: '0.5rem', justifyContent: 'flex-end', marginTop: '0.25rem' }}>
                  <button type="button" className="btn btn-secondary" onClick={() => setShowAddWebhook(false)}>Cancel</button>
                  <button type="submit" className="btn btn-primary" disabled={isCreatingWebhook}>
                    {isCreatingWebhook ? 'Registering...' : 'Save Subscription'}
                  </button>
                </div>
              </form>
            )}

            {webhooks.length === 0 ? (
              <div style={{ padding: '2rem 1rem', textAlign: 'center', color: 'var(--text-muted)', fontSize: '0.875rem' }}>
                No active webhooks registered for this organization.
              </div>
            ) : (
              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.875rem' }}>
                  <thead>
                    <tr style={{ borderBottom: '1px solid var(--border-subtle)', color: 'var(--text-muted)', fontSize: '0.75rem', textTransform: 'uppercase' }}>
                      <th style={{ padding: '0.75rem 1rem' }}>Label</th>
                      <th style={{ padding: '0.75rem 1rem' }}>Target URL</th>
                      <th style={{ padding: '0.75rem 1rem' }}>Events</th>
                      <th style={{ padding: '0.75rem 1rem' }}>Status</th>
                      <th style={{ padding: '0.75rem 1rem', textAlign: 'right' }}>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {webhooks.map((w) => (
                      <tr key={w.id} style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                        <td style={{ padding: '0.75rem 1rem', fontWeight: 600 }}>{w.label}</td>
                        <td style={{ padding: '0.75rem 1rem', fontFamily: 'monospace', fontSize: '0.8125rem' }}>{w.url}</td>
                        <td style={{ padding: '0.75rem 1rem' }}>
                          <div style={{ display: 'flex', gap: '0.25rem' }}>
                            {w.events.map((e) => (
                              <span key={e} style={{ backgroundColor: 'var(--bg-canvas)', border: '1px solid var(--border-subtle)', padding: '0.15rem 0.35rem', borderRadius: 'var(--radius-sm)', fontSize: '0.75rem' }}>
                                {e}
                              </span>
                            ))}
                          </div>
                        </td>
                        <td style={{ padding: '0.75rem 1rem' }}>
                          <span style={{ color: 'var(--success)', fontWeight: 600, fontSize: '0.75rem' }}>ACTIVE</span>
                        </td>
                        <td style={{ padding: '0.75rem 1rem', textAlign: 'right' }}>
                          <button
                            type="button"
                            onClick={() => handleDeleteWebhook(w.id)}
                            style={{ background: 'none', border: 'none', color: 'var(--danger)', cursor: 'pointer', padding: '0.25rem' }}
                            title="Delete Webhook"
                          >
                            <Trash2 size={16} />
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* Webhook Audit Log */}
          <div style={{ backgroundColor: 'var(--bg-surface)', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-subtle)', padding: '1.25rem' }}>
            <h3 style={{ fontSize: '0.9375rem', fontWeight: 600, margin: '0 0 0.75rem' }}>Recent Webhook Dispatches (Audit Trail)</h3>
            {dispatches.length === 0 ? (
              <div style={{ color: 'var(--text-muted)', fontSize: '0.8125rem' }}>No dispatch events logged yet.</div>
            ) : (
              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.8125rem' }}>
                  <thead>
                    <tr style={{ borderBottom: '1px solid var(--border-subtle)', color: 'var(--text-muted)' }}>
                      <th style={{ padding: '0.5rem 0.75rem' }}>Event Type</th>
                      <th style={{ padding: '0.5rem 0.75rem' }}>HMAC Signature</th>
                      <th style={{ padding: '0.5rem 0.75rem' }}>HTTP Status</th>
                      <th style={{ padding: '0.5rem 0.75rem' }}>Timestamp</th>
                    </tr>
                  </thead>
                  <tbody>
                    {dispatches.map((d) => (
                      <tr key={d.id} style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                        <td style={{ padding: '0.5rem 0.75rem', fontWeight: 600 }}>{d.event_type}</td>
                        <td style={{ padding: '0.5rem 0.75rem', fontFamily: 'monospace', color: 'var(--text-muted)' }}>
                          {d.signature.slice(0, 24)}...
                        </td>
                        <td style={{ padding: '0.5rem 0.75rem' }}>
                          <span style={{ color: d.response_status === 200 ? 'var(--success)' : 'var(--danger)', fontWeight: 600 }}>
                            {d.response_status}
                          </span>
                        </td>
                        <td style={{ padding: '0.5rem 0.75rem', color: 'var(--text-muted)' }}>
                          {new Date(d.dispatched_at).toLocaleString()}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
