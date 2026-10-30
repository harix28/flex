import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../context/AuthContext';
import { registryApi } from '../services/api';
import { Machine } from '../services/types';
import { LoadingState } from '../components/common/LoadingState';
import { EmptyState } from '../components/common/EmptyState';
import { ErrorState } from '../components/common/ErrorState';
import { Cpu, Search, Plus, ChevronRight, RefreshCw, Filter } from 'lucide-react';

interface MachinesPageProps {
  onSelectMachine: (machineId: string) => void;
  onNavigateToRegistry: () => void;
}

export const MachinesPage: React.FC<MachinesPageProps> = ({ onSelectMachine, onNavigateToRegistry }) => {
  const { activeTenant, canManageRegistry } = useAuth();
  const [machines, setMachines] = useState<Machine[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<{ message: string; requestId?: string } | null>(null);

  // Filters
  const [assetCodeQuery, setAssetCodeQuery] = useState('');
  const [lifecycleFilter, setLifecycleFilter] = useState<string>('');
  const [sourceFilter, setSourceFilter] = useState<string>('');
  const [offset, setOffset] = useState(0);
  const [nextOffset, setNextOffset] = useState<number | null>(null);
  const limit = 25;

  const fetchMachines = useCallback(async () => {
    if (!activeTenant) return;
    setIsLoading(true);
    setError(null);

    try {
      const res = await registryApi.listMachines(activeTenant.id, {
        limit,
        offset,
        asset_code: assetCodeQuery.trim() || undefined,
        lifecycle_status: lifecycleFilter || undefined,
        data_source: sourceFilter || undefined,
      });
      setMachines(res.items);
      setNextOffset(res.next_offset);
    } catch (err: any) {
      setError({ message: err.message || 'Failed to list machines', requestId: err.requestId });
    } finally {
      setIsLoading(false);
    }
  }, [activeTenant, limit, offset, assetCodeQuery, lifecycleFilter, sourceFilter]);

  useEffect(() => {
    fetchMachines();
  }, [fetchMachines]);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.75rem' }}>
        <div>
          <h1 style={{ fontSize: '1.5rem', fontWeight: 700 }}>All Engines & Equipment</h1>
          <p style={{ fontSize: '0.875rem', color: 'var(--text-secondary)', marginTop: '0.25rem' }}>
            List of all monitored engines and machinery in your fleet, with sensor history and flight cycles.
          </p>
        </div>

        <div style={{ display: 'flex', gap: '0.5rem' }}>
          <button
            type="button"
            className="btn btn-secondary"
            onClick={fetchMachines}
            disabled={isLoading}
          >
            <RefreshCw size={14} className={isLoading ? 'animate-spin' : ''} />
            <span>Refresh</span>
          </button>
          {canManageRegistry() && (
            <button
              type="button"
              className="btn btn-primary"
              onClick={onNavigateToRegistry}
            >
              <Plus size={16} />
              <span>Register Machine</span>
            </button>
          )}
        </div>
      </div>

      {/* Filter Bar */}
      <div
        className="card"
        style={{
          display: 'flex',
          flexWrap: 'wrap',
          gap: '1rem',
          alignItems: 'center',
          padding: '0.875rem 1rem',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flex: 1, minWidth: '220px' }}>
          <Search size={16} style={{ color: 'var(--text-muted)' }} />
          <input
            type="text"
            className="form-control"
            placeholder="Search by exact asset code (e.g., NASA-FD001-TEST-1)..."
            value={assetCodeQuery}
            onChange={(e) => {
              setAssetCodeQuery(e.target.value);
              setOffset(0);
            }}
            style={{ width: '100%' }}
          />
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <Filter size={14} style={{ color: 'var(--text-muted)' }} />
          <select
            className="form-control"
            value={lifecycleFilter}
            onChange={(e) => {
              setLifecycleFilter(e.target.value);
              setOffset(0);
            }}
            style={{ fontSize: '0.8125rem', padding: '0.35rem 0.65rem' }}
          >
            <option value="">All Lifecycles</option>
            <option value="active">Active</option>
            <option value="inactive">Inactive</option>
            <option value="archived">Archived</option>
          </select>

          <select
            className="form-control"
            value={sourceFilter}
            onChange={(e) => {
              setSourceFilter(e.target.value);
              setOffset(0);
            }}
            style={{ fontSize: '0.8125rem', padding: '0.35rem 0.65rem' }}
          >
            <option value="">All Data Sources</option>
            <option value="nasa_replay">NASA Replay (C-MAPSS)</option>
            <option value="physical_device">Physical Device</option>
          </select>
        </div>
      </div>

      {/* Error */}
      {error && (
        <ErrorState
          message={error.message}
          requestId={error.requestId}
          onRetry={fetchMachines}
        />
      )}

      {/* Table / Empty / Loading */}
      {isLoading ? (
        <LoadingState message="Loading machine registry..." />
      ) : machines.length === 0 ? (
        <EmptyState
          title="No Machines Found"
          description={
            assetCodeQuery || lifecycleFilter || sourceFilter
              ? 'No machines matched the selected filter criteria.'
              : 'There are no registered machines in this organization yet. Register a NASA replay engine or physical asset.'
          }
          icon={<Cpu size={24} />}
          action={
            canManageRegistry() ? (
              <button
                type="button"
                className="btn btn-primary"
                onClick={onNavigateToRegistry}
              >
                Register a Machine
              </button>
            ) : undefined
          }
        />
      ) : (
        <div className="table-container">
          <table className="table">
            <thead>
              <tr>
                <th>Asset Code</th>
                <th>Display Name</th>
                <th>Machine Type</th>
                <th>Data Source</th>
                <th>Lifecycle Status</th>
                <th>Site &amp; Location</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {machines.map((m) => (
                <tr
                  key={m.id}
                  style={{ cursor: 'pointer' }}
                  onClick={() => onSelectMachine(m.id)}
                >
                  <td className="mono" style={{ fontWeight: 600, color: 'var(--text-primary)' }}>
                    {m.asset_code}
                  </td>
                  <td>{m.name}</td>
                  <td>
                    <span className="mono" style={{ fontSize: '0.8125rem' }}>{m.machine_type}</span>
                  </td>
                  <td>
                    <span className="badge badge-unknown" style={{ fontSize: '0.7rem' }}>
                      {m.data_source === 'nasa_replay' ? 'NASA Replay' : 'Physical'}
                    </span>
                  </td>
                  <td>
                    <span
                      className={`badge ${
                        m.lifecycle_status === 'active'
                          ? 'badge-low'
                          : m.lifecycle_status === 'archived'
                          ? 'badge-unknown'
                          : 'badge-high'
                      }`}
                    >
                      {m.lifecycle_status}
                    </span>
                  </td>
                  <td style={{ fontSize: '0.8125rem', color: 'var(--text-muted)' }}>
                    {m.site ? `${m.site}${m.location ? ` / ${m.location}` : ''}` : '—'}
                  </td>
                  <td onClick={(e) => e.stopPropagation()}>
                    <button
                      type="button"
                      className="btn btn-secondary"
                      onClick={() => onSelectMachine(m.id)}
                      style={{ padding: '0.3rem 0.6rem', fontSize: '0.75rem' }}
                    >
                      <span>Details</span>
                      <ChevronRight size={13} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          {/* Pagination */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              padding: '0.75rem 1rem',
              backgroundColor: 'var(--bg-surface-elevated)',
              borderTop: '1px solid var(--border-subtle)',
              fontSize: '0.8125rem',
            }}
          >
            <span style={{ color: 'var(--text-secondary)' }}>
              Showing {machines.length} records (offset {offset})
            </span>
            <div style={{ display: 'flex', gap: '0.5rem' }}>
              <button
                type="button"
                className="btn btn-secondary"
                disabled={offset === 0}
                onClick={() => setOffset(Math.max(0, offset - limit))}
                style={{ padding: '0.25rem 0.5rem', fontSize: '0.75rem' }}
              >
                Previous
              </button>
              <button
                type="button"
                className="btn btn-secondary"
                disabled={nextOffset === null}
                onClick={() => nextOffset !== null && setOffset(nextOffset)}
                style={{ padding: '0.25rem 0.5rem', fontSize: '0.75rem' }}
              >
                Next
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
