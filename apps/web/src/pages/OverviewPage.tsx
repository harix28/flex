import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../context/AuthContext';
import { predictionsApi } from '../services/api';
import { MaintenancePrioritiesResponse, PriorityBand, MaintenancePriorityItem } from '../services/types';
import { PriorityBadge } from '../components/common/Badge';
import { LoadingState } from '../components/common/LoadingState';
import { EmptyState } from '../components/common/EmptyState';
import { ErrorState } from '../components/common/ErrorState';
import {
  ShieldAlert,
  AlertTriangle,
  Clock,
  CheckCircle,
  HelpCircle,
  AlertCircle,
  ChevronRight,
  Filter,
  RefreshCw,
} from 'lucide-react';

interface OverviewPageProps {
  onSelectMachine: (machineId: string) => void;
  onNavigateToRegistry: () => void;
}

export const OverviewPage: React.FC<OverviewPageProps> = ({ onSelectMachine, onNavigateToRegistry }) => {
  const { activeTenant } = useAuth();
  const [data, setData] = useState<MaintenancePrioritiesResponse | null>(null);
  const [selectedBand, setSelectedBand] = useState<PriorityBand | 'all'>('all');
  const [limit] = useState(25);
  const [offset, setOffset] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<{ message: string; requestId?: string } | null>(null);
  const [autoRefresh, setAutoRefresh] = useState(false);

  const fetchPriorities = useCallback(async (silent = false) => {
    if (!activeTenant) return;
    if (!silent) setIsLoading(true);
    setError(null);

    try {
      const res = await predictionsApi.getMaintenancePriorities(activeTenant.id, {
        limit,
        offset,
        priority_band: selectedBand === 'all' ? undefined : selectedBand,
      });
      setData(res);
    } catch (err: any) {
      setError({
        message: err.message || 'Failed to fetch fleet maintenance priorities',
        requestId: err.requestId,
      });
    } finally {
      setIsLoading(false);
    }
  }, [activeTenant, selectedBand, limit, offset]);

  useEffect(() => {
    fetchPriorities();
  }, [fetchPriorities]);

  useEffect(() => {
    let interval: NodeJS.Timeout | null = null;
    if (autoRefresh) {
      interval = setInterval(() => {
        fetchPriorities(true);
      }, 3000);
    }
    return () => {
      if (interval) clearInterval(interval);
    };
  }, [autoRefresh, fetchPriorities]);

  const summary = data?.summary || {
    urgent: 0,
    high: 0,
    medium: 0,
    low: 0,
    outdated: 0,
    unknown: 0,
  };

  const totalMachines = data?.total ?? 0;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      {/* Title & Refresh */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.75rem' }}>
        <div>
          <h1 style={{ fontSize: '1.5rem', fontWeight: 700 }}>Fleet Maintenance Overview</h1>
          <p style={{ fontSize: '0.875rem', color: 'var(--text-secondary)', marginTop: '0.25rem' }}>
            Deterministic priority ranking based on causal trailing RUL predictions ({data?.policy_version || 'v1-experimental'}).
          </p>
        </div>
        <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
          <button
            type="button"
            className={`btn ${autoRefresh ? 'btn-primary' : 'btn-secondary'}`}
            onClick={() => setAutoRefresh(!autoRefresh)}
            style={{
              fontSize: '0.8125rem',
              borderColor: autoRefresh ? '#16a34a' : undefined,
              backgroundColor: autoRefresh ? 'rgba(34, 197, 94, 0.12)' : undefined,
              color: autoRefresh ? '#15803d' : undefined,
              display: 'inline-flex',
              alignItems: 'center',
              gap: '0.4rem',
            }}
          >
            <span
              style={{
                width: '7px',
                height: '7px',
                borderRadius: '50%',
                backgroundColor: autoRefresh ? '#16a34a' : 'var(--text-muted)',
                display: 'inline-block',
                boxShadow: autoRefresh ? '0 0 6px #22c55e' : 'none',
              }}
            />
            <span>{autoRefresh ? 'Auto-Refresh: ON' : 'Auto-Refresh: OFF'}</span>
          </button>

          <button
            type="button"
            className="btn btn-secondary"
            onClick={() => fetchPriorities(false)}
            disabled={isLoading}
            style={{ fontSize: '0.8125rem' }}
          >
            <RefreshCw size={14} className={isLoading ? 'animate-spin' : ''} />
            <span>Refresh Fleet Status</span>
          </button>
        </div>
      </div>

      {/* Fleet Priority Metric Summary Cards */}
      <div className="grid-cols-4">
        {/* Urgent */}
        <div
          className="card"
          style={{
            cursor: 'pointer',
            borderLeft: '4px solid var(--urgent-text)',
            backgroundColor: selectedBand === 'urgent' ? 'var(--bg-surface-hover)' : 'var(--bg-surface)',
          }}
          onClick={() => setSelectedBand(selectedBand === 'urgent' ? 'all' : 'urgent')}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', color: 'var(--urgent-text)' }}>
            <span style={{ fontSize: '0.8125rem', fontWeight: 600, textTransform: 'uppercase' }}>Urgent Priority</span>
            <ShieldAlert size={18} />
          </div>
          <div style={{ fontSize: '2rem', fontWeight: 700, marginTop: '0.5rem', lineHeight: 1 }} className="mono">
            {summary.urgent}
          </div>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.5rem' }}>
            Estimated RUL &le; 15 cycles
          </div>
        </div>

        {/* High */}
        <div
          className="card"
          style={{
            cursor: 'pointer',
            borderLeft: '4px solid var(--high-text)',
            backgroundColor: selectedBand === 'high' ? 'var(--bg-surface-hover)' : 'var(--bg-surface)',
          }}
          onClick={() => setSelectedBand(selectedBand === 'high' ? 'all' : 'high')}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', color: 'var(--high-text)' }}>
            <span style={{ fontSize: '0.8125rem', fontWeight: 600, textTransform: 'uppercase' }}>High Priority</span>
            <AlertTriangle size={18} />
          </div>
          <div style={{ fontSize: '2rem', fontWeight: 700, marginTop: '0.5rem', lineHeight: 1 }} className="mono">
            {summary.high}
          </div>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.5rem' }}>
            15 &lt; RUL &le; 35 cycles
          </div>
        </div>

        {/* Medium */}
        <div
          className="card"
          style={{
            cursor: 'pointer',
            borderLeft: '4px solid var(--medium-text)',
            backgroundColor: selectedBand === 'medium' ? 'var(--bg-surface-hover)' : 'var(--bg-surface)',
          }}
          onClick={() => setSelectedBand(selectedBand === 'medium' ? 'all' : 'medium')}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', color: 'var(--medium-text)' }}>
            <span style={{ fontSize: '0.8125rem', fontWeight: 600, textTransform: 'uppercase' }}>Medium Priority</span>
            <Clock size={18} />
          </div>
          <div style={{ fontSize: '2rem', fontWeight: 700, marginTop: '0.5rem', lineHeight: 1 }} className="mono">
            {summary.medium}
          </div>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.5rem' }}>
            35 &lt; RUL &le; 75 cycles
          </div>
        </div>

        {/* Low */}
        <div
          className="card"
          style={{
            cursor: 'pointer',
            borderLeft: '4px solid var(--low-text)',
            backgroundColor: selectedBand === 'low' ? 'var(--bg-surface-hover)' : 'var(--bg-surface)',
          }}
          onClick={() => setSelectedBand(selectedBand === 'low' ? 'all' : 'low')}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', color: 'var(--low-text)' }}>
            <span style={{ fontSize: '0.8125rem', fontWeight: 600, textTransform: 'uppercase' }}>Low Priority</span>
            <CheckCircle size={18} />
          </div>
          <div style={{ fontSize: '2rem', fontWeight: 700, marginTop: '0.5rem', lineHeight: 1 }} className="mono">
            {summary.low}
          </div>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.5rem' }}>
            RUL &gt; 75 cycles
          </div>
        </div>
      </div>

      {/* Outdated / Unknown Notice Bar */}
      {(summary.outdated > 0 || summary.unknown > 0) && (
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '1.25rem',
            padding: '0.75rem 1rem',
            backgroundColor: 'var(--bg-surface)',
            border: '1px solid var(--border-subtle)',
            borderRadius: 'var(--radius-md)',
            fontSize: '0.8125rem',
            flexWrap: 'wrap',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.375rem', color: 'var(--outdated-text)' }}>
            <AlertCircle size={16} />
            <span>
              <strong>{summary.outdated} Outdated Prediction{summary.outdated === 1 ? '' : 's'}:</strong> Newer telemetry ingested since evaluation.
            </span>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '0.375rem', color: 'var(--unknown-text)' }}>
            <HelpCircle size={16} />
            <span>
              <strong>{summary.unknown} Unpredicted / Unavailable:</strong> Telemetry insufficient or missing cycles.
            </span>
          </div>
        </div>
      )}

      {/* Filter Tabs */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
        <span style={{ fontSize: '0.8125rem', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
          <Filter size={14} /> Filter band:
        </span>
        {(['all', 'urgent', 'high', 'medium', 'low', 'unknown'] as const).map((band) => (
          <button
            key={band}
            type="button"
            className={`btn ${selectedBand === band ? 'btn-primary' : 'btn-secondary'}`}
            style={{ fontSize: '0.75rem', padding: '0.25rem 0.625rem', textTransform: 'capitalize' }}
            onClick={() => {
              setSelectedBand(band);
              setOffset(0);
            }}
          >
            {band === 'all' ? 'All Machines' : band}
          </button>
        ))}
      </div>

      {/* Error State */}
      {error && (
        <ErrorState
          message={error.message}
          requestId={error.requestId}
          onRetry={fetchPriorities}
        />
      )}

      {/* Main Table / Loading / Empty */}
      {isLoading ? (
        <LoadingState message="Fetching deterministic maintenance priorities..." />
      ) : !data || data.items.length === 0 ? (
        <EmptyState
          title={selectedBand === 'all' ? 'No Registered Machines Found' : `No ${selectedBand} Priority Machines`}
          description={
            selectedBand === 'all'
              ? 'No machines are currently registered in this organization. Register test engines or physical assets to begin tracking degradation.'
              : `There are currently no machines classified under the ${selectedBand} maintenance priority band.`
          }
          action={
            selectedBand === 'all' ? (
              <button
                type="button"
                className="btn btn-primary"
                onClick={onNavigateToRegistry}
              >
                Go to Registry Management
              </button>
            ) : (
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => setSelectedBand('all')}
              >
                Clear Filter
              </button>
            )
          }
        />
      ) : (
        <div className="table-container">
          <table className="table">
            <thead>
              <tr>
                <th>Machine Asset Code</th>
                <th>Source Type</th>
                <th>Estimated Remaining Cycles</th>
                <th>Maintenance Priority</th>
                <th>Prediction Cutoff</th>
                <th>Evidence Status</th>
                <th>Policy Rule Explanation</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((item: MaintenancePriorityItem) => {
                return (
                  <tr
                    key={item.machine_id}
                    style={{ cursor: 'pointer' }}
                    onClick={() => onSelectMachine(item.machine_id)}
                  >
                    <td>
                      <div style={{ fontWeight: 600, color: 'var(--text-primary)' }} className="mono">
                        {item.asset_code}
                      </div>
                      <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                        {item.machine_name}
                      </div>
                    </td>

                    <td>
                      <span className="badge badge-unknown" style={{ fontSize: '0.7rem' }}>
                        {item.machine_type === 'cmapss_engine' ? 'NASA C-MAPSS Replay' : 'Physical Asset'}
                      </span>
                    </td>

                    <td>
                      {item.status === 'available' && item.rul_cycles !== null ? (
                        <div style={{ display: 'flex', alignItems: 'baseline', gap: '0.25rem' }}>
                          <span
                            className="mono"
                            style={{
                              fontSize: '1.125rem',
                              fontWeight: 700,
                              color: 'var(--text-primary)',
                            }}
                          >
                            {item.rul_cycles.toFixed(1)}
                          </span>
                          <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
                            cycles
                          </span>
                        </div>
                      ) : (
                        <span style={{ color: 'var(--text-muted)', fontSize: '0.8125rem', fontStyle: 'italic' }}>
                          Unavailable ({item.reason || 'unpredicted'})
                        </span>
                      )}
                    </td>

                    <td>
                      <PriorityBadge priority={item.priority_band} />
                    </td>

                    <td>
                      {item.prediction_cutoff_cycle ? (
                        <span className="mono" style={{ fontSize: '0.8125rem' }}>
                          Cycle {item.prediction_cutoff_cycle}
                        </span>
                      ) : (
                        <span style={{ color: 'var(--text-muted)', fontSize: '0.8125rem' }}>—</span>
                      )}
                    </td>

                    <td>
                      {item.is_outdated ? (
                        <span className="badge badge-outdated" title="Newer telemetry has arrived">
                          <AlertCircle size={12} />
                          <span>Outdated (C{item.latest_observation_cycle})</span>
                        </span>
                      ) : item.is_current ? (
                        <span className="badge badge-low">
                          <CheckCircle size={12} />
                          <span>Current</span>
                        </span>
                      ) : (
                        <span className="badge badge-unknown">
                          <HelpCircle size={12} />
                          <span>Unmeasured</span>
                        </span>
                      )}
                    </td>

                    <td style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)', maxWidth: '280px' }}>
                      {item.explanation}
                    </td>

                    <td onClick={(e) => e.stopPropagation()}>
                      <button
                        type="button"
                        className="btn btn-secondary"
                        onClick={() => onSelectMachine(item.machine_id)}
                        style={{ padding: '0.3rem 0.6rem', fontSize: '0.75rem' }}
                      >
                        <span>Details</span>
                        <ChevronRight size={13} />
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>

          {/* Bounded Pagination Footer */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              padding: '0.75rem 1rem',
              backgroundColor: 'var(--bg-surface-elevated)',
              borderTop: '1px solid var(--border-subtle)',
              fontSize: '0.8125rem',
              color: 'var(--text-secondary)',
            }}
          >
            <span>
              Showing {data.items.length} of {totalMachines} registered fleet machines
            </span>

            <div style={{ display: 'flex', gap: '0.5rem' }}>
              <button
                type="button"
                className="btn btn-secondary"
                disabled={offset === 0}
                onClick={() => setOffset(Math.max(0, offset - limit))}
                style={{ padding: '0.25rem 0.5rem', fontSize: '0.75rem' }}
              >
                Previous Page
              </button>
              <button
                type="button"
                className="btn btn-secondary"
                disabled={offset + limit >= totalMachines}
                onClick={() => setOffset(offset + limit)}
                style={{ padding: '0.25rem 0.5rem', fontSize: '0.75rem' }}
              >
                Next Page
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
