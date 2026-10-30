import React, { useState, useEffect, useMemo } from 'react';
import { useAuth } from '../context/AuthContext';
import { predictionsApi } from '../services/api';
import { MaintenancePrioritiesResponse, PriorityBand } from '../services/types';
import { PriorityBadge } from '../components/common/Badge';
import { LoadingState } from '../components/common/LoadingState';
import {
  AlertTriangle,
  ShieldAlert,
  Clock,
  CheckCircle,
  Info,
  RefreshCw,
  TrendingDown,
  AlertCircle,
  Search,
} from 'lucide-react';

interface MaintenancePriorityPageProps {
  onSelectMachine: (machineId: string) => void;
}

export const MaintenancePriorityPage: React.FC<MaintenancePriorityPageProps> = ({ onSelectMachine }) => {
  const { activeTenant } = useAuth();
  const [data, setData] = useState<MaintenancePrioritiesResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [selectedBand, setSelectedBand] = useState<PriorityBand | 'all'>('all');
  const [searchQuery, setSearchQuery] = useState('');

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

  const summary = data?.summary || {
    urgent: 0,
    high: 0,
    medium: 0,
    low: 0,
    outdated: 0,
    unknown: 0,
  };

  // Fleet statistical KPI calculations
  const { avgRul, lowestRulItem } = useMemo(() => {
    if (!data?.items || data.items.length === 0) {
      return { avgRul: '—', lowestRulItem: null };
    }
    const validItems = data.items.filter((item) => item.rul_cycles !== null);
    if (validItems.length === 0) {
      return { avgRul: '—', lowestRulItem: null };
    }
    const sum = validItems.reduce((acc, curr) => acc + (curr.rul_cycles || 0), 0);
    const avg = (sum / validItems.length).toFixed(1);

    // Find lowest RUL item
    const sorted = [...validItems].sort((a, b) => (a.rul_cycles || 0) - (b.rul_cycles || 0));
    return { avgRul: `${avg} cycles`, lowestRulItem: sorted[0] };
  }, [data]);

  // Filtered queue items
  const filteredItems = useMemo(() => {
    if (!data?.items) return [];
    return data.items.filter((item) => {
      if (selectedBand !== 'all' && item.priority_band !== selectedBand) {
        return false;
      }
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase();
        const code = item.asset_code.toLowerCase();
        const name = (item.machine_name || '').toLowerCase();
        if (!code.includes(q) && !name.includes(q)) return false;
      }
      return true;
    });
  }, [data, selectedBand, searchQuery]);

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

      {/* KPI METRIC CARDS */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(210px, 1fr))',
          gap: '1rem',
        }}
      >
        {/* KPI 1: Urgent Action Required */}
        <div
          className="card"
          onClick={() => setSelectedBand(selectedBand === 'urgent' ? 'all' : 'urgent')}
          style={{
            padding: '1.25rem',
            backgroundColor: '#ffffff',
            borderLeft: '4px solid #dc2626',
            cursor: 'pointer',
            boxShadow: selectedBand === 'urgent' ? '0 0 0 2px #dc2626' : undefined,
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', color: '#dc2626' }}>
            <span style={{ fontSize: '0.75rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
              Urgent Priority
            </span>
            <ShieldAlert size={18} />
          </div>
          <div style={{ fontSize: '2rem', fontWeight: 700, marginTop: '0.5rem', color: '#dc2626', lineHeight: 1 }}>
            {summary.urgent}
          </div>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.5rem' }}>
            Estimated RUL &le; 15 cycles
          </div>
        </div>

        {/* KPI 2: High Risk Queue */}
        <div
          className="card"
          onClick={() => setSelectedBand(selectedBand === 'high' ? 'all' : 'high')}
          style={{
            padding: '1.25rem',
            backgroundColor: '#ffffff',
            borderLeft: '4px solid #d97706',
            cursor: 'pointer',
            boxShadow: selectedBand === 'high' ? '0 0 0 2px #d97706' : undefined,
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', color: '#d97706' }}>
            <span style={{ fontSize: '0.75rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
              High Priority
            </span>
            <AlertTriangle size={18} />
          </div>
          <div style={{ fontSize: '2rem', fontWeight: 700, marginTop: '0.5rem', color: '#d97706', lineHeight: 1 }}>
            {summary.high}
          </div>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.5rem' }}>
            15 &lt; RUL &le; 35 cycles
          </div>
        </div>

        {/* KPI 3: Fleet Average RUL */}
        <div
          className="card"
          style={{
            padding: '1.25rem',
            backgroundColor: '#ffffff',
            borderLeft: '4px solid #2563eb',
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', color: '#2563eb' }}>
            <span style={{ fontSize: '0.75rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
              Average Fleet RUL
            </span>
            <Clock size={18} />
          </div>
          <div style={{ fontSize: '1.65rem', fontWeight: 700, marginTop: '0.5rem', color: '#1e40af', lineHeight: 1 }}>
            {avgRul}
          </div>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.5rem' }}>
            Mean life across evaluated units
          </div>
        </div>

        {/* KPI 4: Lowest Predicted RUL */}
        <div
          className="card"
          onClick={() => lowestRulItem && onSelectMachine(lowestRulItem.machine_id)}
          style={{
            padding: '1.25rem',
            backgroundColor: '#ffffff',
            borderLeft: '4px solid #991b1b',
            cursor: lowestRulItem ? 'pointer' : 'default',
          }}
          title={lowestRulItem ? `Click to inspect ${lowestRulItem.asset_code}` : undefined}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', color: '#991b1b' }}>
            <span style={{ fontSize: '0.75rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
              Lowest Fleet RUL
            </span>
            <TrendingDown size={18} />
          </div>
          <div style={{ fontSize: '1.65rem', fontWeight: 700, marginTop: '0.5rem', color: '#991b1b', lineHeight: 1 }}>
            {lowestRulItem?.rul_cycles !== null && lowestRulItem?.rul_cycles !== undefined
              ? `${lowestRulItem.rul_cycles.toFixed(1)} cyc`
              : '—'}
          </div>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.5rem', fontFamily: 'monospace' }}>
            {lowestRulItem?.asset_code || 'None critical'}
          </div>
        </div>

        {/* KPI 5: Pending Outdated Telemetry */}
        <div
          className="card"
          style={{
            padding: '1.25rem',
            backgroundColor: '#ffffff',
            borderLeft: '4px solid #7c3aed',
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', color: '#7c3aed' }}>
            <span style={{ fontSize: '0.75rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
              Pending Refresh
            </span>
            <AlertCircle size={18} />
          </div>
          <div style={{ fontSize: '2rem', fontWeight: 700, marginTop: '0.5rem', color: '#7c3aed', lineHeight: 1 }}>
            {summary.outdated}
          </div>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.5rem' }}>
            New telemetry awaiting inference
          </div>
        </div>
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
              <ShieldAlert size={14} /> Urgent Priority (&le; 15 cyc)
            </div>
            <div style={{ color: '#7f1d1d', marginTop: '0.25rem' }}>
              High risk of imminent component wearout. Immediate inspection work order scheduled.
            </div>
          </div>

          <div style={{ padding: '0.75rem', borderRadius: '6px', backgroundColor: '#fffbeb', border: '1px solid #fde68a' }}>
            <div style={{ fontWeight: 600, color: '#92400e', display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
              <AlertTriangle size={14} /> High Priority (16–35 cyc)
            </div>
            <div style={{ color: '#78350f', marginTop: '0.25rem' }}>
              Accelerated wear progression detected. Proactive maintenance drafting recommended.
            </div>
          </div>

          <div style={{ padding: '0.75rem', borderRadius: '6px', backgroundColor: '#eff6ff', border: '1px solid #bfdbfe' }}>
            <div style={{ fontWeight: 600, color: '#1d4ed8', display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
              <Clock size={14} /> Medium Priority (36–75 cyc)
            </div>
            <div style={{ color: '#1e3a8a', marginTop: '0.25rem' }}>
              Stable operational degradation. Standard scheduled maintenance planning window.
            </div>
          </div>

          <div style={{ padding: '0.75rem', borderRadius: '6px', backgroundColor: '#f0fdf4', border: '1px solid #bbf7d0' }}>
            <div style={{ fontWeight: 600, color: '#166534', display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
              <CheckCircle size={14} /> Low Priority (&gt; 75 cyc)
            </div>
            <div style={{ color: '#14532d', marginTop: '0.25rem' }}>
              Normal operational baseline. Continuous telemetry tracking without action requirement.
            </div>
          </div>
        </div>
      </div>

      {/* Ranked Priority Table */}
      <div className="card" style={{ padding: '1.25rem', backgroundColor: '#ffffff' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '0.75rem', marginBottom: '1rem' }}>
          <div>
            <h2 style={{ fontSize: '1.05rem', fontWeight: 600, margin: 0, color: 'var(--text-primary)' }}>
              Prioritized Fleet Queue ({filteredItems.length} Monitored Units)
            </h2>
            <div style={{ fontSize: '0.8125rem', color: 'var(--text-muted)', marginTop: '0.2rem' }}>
              Sorted deterministically by maintenance urgency.
            </div>
          </div>

          {/* Filter & Search Bar */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
            <div style={{ position: 'relative' }}>
              <input
                type="text"
                placeholder="Search asset..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                style={{
                  padding: '0.35rem 0.65rem 0.35rem 1.75rem',
                  fontSize: '0.8125rem',
                  borderRadius: '6px',
                  border: '1px solid var(--border-subtle)',
                  backgroundColor: 'var(--bg-canvas)',
                  width: '180px',
                }}
              />
              <Search size={14} style={{ position: 'absolute', left: '0.5rem', top: '0.55rem', color: 'var(--text-muted)' }} />
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '0.25rem', border: '1px solid var(--border-subtle)', borderRadius: '6px', padding: '0.15rem' }}>
              {(['all', 'urgent', 'high', 'medium', 'low'] as const).map((band) => (
                <button
                  key={band}
                  type="button"
                  onClick={() => setSelectedBand(band)}
                  style={{
                    border: 'none',
                    padding: '0.25rem 0.55rem',
                    fontSize: '0.75rem',
                    borderRadius: '4px',
                    backgroundColor: selectedBand === band ? '#2563eb' : 'transparent',
                    color: selectedBand === band ? '#ffffff' : 'var(--text-secondary)',
                    fontWeight: selectedBand === band ? 600 : 400,
                    textTransform: 'capitalize',
                    cursor: 'pointer',
                  }}
                >
                  {band}
                </button>
              ))}
            </div>
          </div>
        </div>

        {isLoading ? (
          <LoadingState message="Evaluating priority queue..." />
        ) : filteredItems.length === 0 ? (
          <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-muted)' }}>
            No units match the selected criteria.
          </div>
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
                {filteredItems.map((item, idx) => (
                  <tr
                    key={item.machine_id}
                    style={{ borderBottom: '1px solid var(--border-subtle)', cursor: 'pointer' }}
                    onClick={() => onSelectMachine(item.machine_id)}
                  >
                    <td style={{ padding: '0.5rem', fontWeight: 600, color: 'var(--text-muted)' }}>#{idx + 1}</td>
                    <td style={{ padding: '0.5rem', fontWeight: 600, fontFamily: 'monospace', color: 'var(--text-primary)' }}>
                      {item.asset_code}
                    </td>
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
                        onClick={(e) => {
                          e.stopPropagation();
                          onSelectMachine(item.machine_id);
                        }}
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
