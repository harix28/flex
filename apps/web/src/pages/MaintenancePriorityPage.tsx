import React, { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import { predictionsApi } from '../services/api';
import { MaintenancePrioritiesResponse } from '../services/types';
import { PriorityBadge } from '../components/common/Badge';
import { LoadingState } from '../components/common/LoadingState';
import { AlertTriangle, ShieldAlert, Clock, CheckCircle, Info, RefreshCw } from 'lucide-react';

interface MaintenancePriorityPageProps {
  onSelectMachine: (machineId: string) => void;
}

export const MaintenancePriorityPage: React.FC<MaintenancePriorityPageProps> = ({ onSelectMachine }) => {
  const { activeTenant } = useAuth();
  const [data, setData] = useState<MaintenancePrioritiesResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const fetchPriorities = async () => {
    if (!activeTenant) return;
    setIsLoading(true);
    try {
      const res = await predictionsApi.getMaintenancePriorities(activeTenant.id, { limit: 100 });
      setData(res);
    } catch (err) {
      // handled
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchPriorities();
  }, [activeTenant]);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      {/* Page Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '0.75rem' }}>
        <div>
          <h1 style={{ fontSize: '1.5rem', fontWeight: 700, margin: 0, color: 'var(--text-primary)' }}>
            Maintenance Priority Decision Engine
          </h1>
          <p style={{ fontSize: '0.875rem', color: 'var(--text-secondary)', marginTop: '0.25rem' }}>
            Deterministic fleet ranking based on causal trailing Remaining Useful Life (RUL) and operational risk policies.
          </p>
        </div>
        <button type="button" className="btn btn-secondary" onClick={fetchPriorities} disabled={isLoading}>
          <RefreshCw size={14} className={isLoading ? 'animate-spin' : ''} />
          <span>Refresh Scoring</span>
        </button>
      </div>

      {/* Decision Engine Policy Matrix Card */}
      <div className="card" style={{ padding: '1.25rem', backgroundColor: '#ffffff' }}>
        <h2 style={{ fontSize: '0.95rem', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '0.75rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <Info size={16} color="#2563eb" />
          Deterministic Policy Thresholds &amp; Decision Criteria
        </h2>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '1rem', fontSize: '0.8125rem' }}>
          <div style={{ padding: '0.75rem', borderRadius: '6px', backgroundColor: '#fef2f2', border: '1px solid #fecaca' }}>
            <div style={{ fontWeight: 600, color: '#991b1b', display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
              <ShieldAlert size={14} /> Urgent Priority
            </div>
            <div style={{ color: '#7f1d1d', marginTop: '0.25rem' }}>
              Estimated RUL &le; 15 cycles. High risk of imminent component wearout. Immediate inspection scheduled.
            </div>
          </div>

          <div style={{ padding: '0.75rem', borderRadius: '6px', backgroundColor: '#fffbeb', border: '1px solid #fde68a' }}>
            <div style={{ fontWeight: 600, color: '#92400e', display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
              <AlertTriangle size={14} /> High Priority
            </div>
            <div style={{ color: '#78350f', marginTop: '0.25rem' }}>
              15 &lt; RUL &le; 35 cycles. Accelerated wear progression detected. Work order drafting recommended.
            </div>
          </div>

          <div style={{ padding: '0.75rem', borderRadius: '6px', backgroundColor: '#eff6ff', border: '1px solid #bfdbfe' }}>
            <div style={{ fontWeight: 600, color: '#1d4ed8', display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
              <Clock size={14} /> Medium Priority
            </div>
            <div style={{ color: '#1e3a8a', marginTop: '0.25rem' }}>
              35 &lt; RUL &le; 75 cycles. Stable operational degradation. Routine scheduled maintenance window.
            </div>
          </div>

          <div style={{ padding: '0.75rem', borderRadius: '6px', backgroundColor: '#f0fdf4', border: '1px solid #bbf7d0' }}>
            <div style={{ fontWeight: 600, color: '#166534', display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
              <CheckCircle size={14} /> Low Priority
            </div>
            <div style={{ color: '#14532d', marginTop: '0.25rem' }}>
              Estimated RUL &gt; 75 cycles. Normal operational baseline. Standard continuous telemetry monitoring.
            </div>
          </div>
        </div>
      </div>

      {/* Ranked Priority Table */}
      <div className="card" style={{ padding: '1.25rem', backgroundColor: '#ffffff' }}>
        <h2 style={{ fontSize: '1rem', fontWeight: 600, marginBottom: '1rem', color: 'var(--text-primary)' }}>
          Prioritized Fleet Queue ({data?.items?.length || 0} Monitored Units)
        </h2>

        {isLoading ? (
          <LoadingState message="Evaluating priority queue..." />
        ) : !data || data.items.length === 0 ? (
          <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-muted)' }}>No units in queue.</div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table className="table" style={{ width: '100%', fontSize: '0.8125rem', borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid var(--border-subtle)', textAlign: 'left', color: 'var(--text-secondary)' }}>
                  <th style={{ padding: '0.5rem' }}>Rank</th>
                  <th style={{ padding: '0.5rem' }}>Asset Code</th>
                  <th style={{ padding: '0.5rem' }}>Estimated RUL</th>
                  <th style={{ padding: '0.5rem' }}>Maintenance Priority</th>
                  <th style={{ padding: '0.5rem' }}>Policy Explanation</th>
                  <th style={{ padding: '0.5rem' }}>Cutoff Cycle</th>
                  <th style={{ padding: '0.5rem', textAlign: 'right' }}>Action</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((item, idx) => (
                  <tr key={item.machine_id} style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                    <td style={{ padding: '0.5rem', fontWeight: 600, color: 'var(--text-muted)' }}>#{idx + 1}</td>
                    <td style={{ padding: '0.5rem', fontWeight: 600, fontFamily: 'monospace' }}>{item.asset_code}</td>
                    <td style={{ padding: '0.5rem', fontWeight: 700, color: '#2563eb' }}>
                      {item.rul_cycles !== null ? `${item.rul_cycles.toFixed(1)} cycles` : '—'}
                    </td>
                    <td style={{ padding: '0.5rem' }}>
                      <PriorityBadge priority={item.priority_band} />
                    </td>
                    <td style={{ padding: '0.5rem', color: 'var(--text-secondary)' }}>
                      {item.explanation || 'Normal operational tracking'}
                    </td>
                    <td style={{ padding: '0.5rem', fontFamily: 'monospace', color: 'var(--text-muted)' }}>
                      Cycle {item.prediction_cutoff_cycle || '—'}
                    </td>
                    <td style={{ padding: '0.5rem', textAlign: 'right' }}>
                      <button
                        type="button"
                        className="btn btn-secondary"
                        onClick={() => onSelectMachine(item.machine_id)}
                        style={{ fontSize: '0.75rem', padding: '0.2rem 0.5rem' }}
                      >
                        Inspect &gt;
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};
