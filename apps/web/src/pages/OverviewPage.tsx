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
  Info,
  ChevronDown,
  ChevronUp,
  Cpu,
} from 'lucide-react';

interface OverviewPageProps {
  onSelectMachine: (machineId: string) => void;
  onNavigateToRegistry: () => void;
}

export const OverviewPage: React.FC<OverviewPageProps> = ({ onSelectMachine, onNavigateToRegistry }) => {
  const { activeTenant } = useAuth();
  const [data, setData] = useState<MaintenancePrioritiesResponse | null>(null);
  const [selectedBand, setSelectedBand] = useState<PriorityBand | 'all'>('all');
  const [selectedSubset, setSelectedSubset] = useState<'all' | 'FD001' | 'FD002' | 'FD003' | 'FD004'>('all');
  const [limit] = useState(50);
  const [offset, setOffset] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<{ message: string; requestId?: string } | null>(null);
  const [autoRefresh, setAutoRefresh] = useState(false);
  const [showGuide, setShowGuide] = useState(false);

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
        message: err.message || 'Unable to check fleet engine health right now. Please try again.',
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

  const getLaymanExplanation = (item: MaintenancePriorityItem) => {
    if (item.priority_band === 'urgent') {
      const left = item.rul_cycles !== null ? Math.round(item.rul_cycles) : '<15';
      return `Critical wear: only about ${left} operating cycles left. Needs immediate inspection before operating again.`;
    }
    if (item.priority_band === 'high') {
      const left = item.rul_cycles !== null ? Math.round(item.rul_cycles) : '15-35';
      return `Noticeable wear: about ${left} cycles left. Schedule a maintenance check in the next few days.`;
    }
    if (item.priority_band === 'medium') {
      const left = item.rul_cycles !== null ? Math.round(item.rul_cycles) : '35-75';
      return `Normal wear: about ${left} cycles left. Plan regular checkup during upcoming standard maintenance.`;
    }
    if (item.priority_band === 'low') {
      const left = item.rul_cycles !== null ? Math.round(item.rul_cycles) : '>75';
      return `Engine is healthy: plenty of machine operating life left (${left} cycles). Running smoothly, no action needed.`;
    }
    return item.explanation || 'Waiting for more machine sensor recordings to estimate remaining life.';
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      {/* Title & Refresh Controls */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.75rem' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <Cpu size={24} style={{ color: 'var(--primary)' }} />
            <h1 style={{ fontSize: '1.5rem', fontWeight: 700, margin: 0 }}>Engine Health & Maintenance Dashboard</h1>
          </div>
          <p style={{ fontSize: '0.875rem', color: 'var(--text-secondary)', marginTop: '0.35rem' }}>
            A simple overview showing which engines need attention first, so your team can fix issues before a breakdown happens.
          </p>
        </div>
        <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', flexWrap: 'wrap' }}>
          <button
            type="button"
            className="btn btn-secondary"
            onClick={() => setShowGuide(!showGuide)}
            style={{ fontSize: '0.8125rem', display: 'inline-flex', alignItems: 'center', gap: '0.4rem' }}
          >
            <Info size={14} style={{ color: 'var(--primary)' }} />
            <span>{showGuide ? 'Hide Simple Guide' : 'How It Works (Simple Guide)'}</span>
            {showGuide ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
          </button>

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
            <span>{autoRefresh ? 'Live Auto-Update: ON' : 'Live Auto-Update: OFF'}</span>
          </button>

          <button
            type="button"
            className="btn btn-secondary"
            onClick={() => fetchPriorities(false)}
            disabled={isLoading}
            style={{ fontSize: '0.8125rem' }}
          >
            <RefreshCw size={14} className={isLoading ? 'animate-spin' : ''} />
            <span>Refresh Status</span>
          </button>
        </div>
      </div>

      {/* Plain English Beginner's Guide (Collapsible) */}
      {showGuide && (
        <div
          className="card card-elevated"
          style={{
            backgroundColor: 'rgba(14, 165, 233, 0.05)',
            border: '1px solid rgba(14, 165, 233, 0.3)',
            padding: '1.25rem',
            borderRadius: 'var(--radius-md)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.75rem', color: 'var(--primary)' }}>
            <Info size={18} />
            <h3 style={{ fontSize: '1rem', fontWeight: 700, margin: 0 }}>Beginner's Guide to this Dashboard</h3>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '1rem', fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>
            <div style={{ padding: '0.75rem', backgroundColor: 'var(--bg-surface)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)' }}>
              <strong style={{ color: 'var(--text-primary)', display: 'block', marginBottom: '0.25rem' }}>1. What is a "Cycle"?</strong>
              In engine and machine operations, <strong>1 cycle = 1 full operating run</strong> (engine startup, operation under load, and shutdown).
            </div>
            <div style={{ padding: '0.75rem', backgroundColor: 'var(--bg-surface)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)' }}>
              <strong style={{ color: 'var(--text-primary)', display: 'block', marginBottom: '0.25rem' }}>2. What are "Cycles Left"?</strong>
              Our smart sensor checks calculate how many more operating cycles this engine or machine can safely run before requiring service.
            </div>
            <div style={{ padding: '0.75rem', backgroundColor: 'var(--bg-surface)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)' }}>
              <strong style={{ color: 'var(--text-primary)', display: 'block', marginBottom: '0.25rem' }}>3. How Urgency is Decided:</strong>
              <span style={{ color: '#ef4444' }}>Red (&le;15 cycles)</span> = Service now. <br />
              <span style={{ color: '#f59e0b' }}>Yellow (15-35 cycles)</span> = Plan checkup soon. <br />
              <span style={{ color: '#10b981' }}>Green (&gt;75 cycles)</span> = Healthy, safe to operate.
            </div>
            <div style={{ padding: '0.75rem', backgroundColor: 'var(--bg-surface)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)' }}>
              <strong style={{ color: 'var(--text-primary)', display: 'block', marginBottom: '0.25rem' }}>4. Safety Always Comes First:</strong>
              Computers only give recommendations. A real human maintenance engineer must review and approve every single repair job.
            </div>
          </div>
        </div>
      )}

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
            <span style={{ fontSize: '0.8125rem', fontWeight: 700, textTransform: 'uppercase' }}>Needs Immediate Service</span>
            <ShieldAlert size={18} />
          </div>
          <div style={{ fontSize: '2rem', fontWeight: 700, marginTop: '0.5rem', lineHeight: 1 }} className="mono">
            {summary.urgent}
          </div>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.5rem' }}>
            &le; 15 cycles remaining &bull; Inspect immediately
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
            <span style={{ fontSize: '0.8125rem', fontWeight: 700, textTransform: 'uppercase' }}>Needs Service Soon</span>
            <AlertTriangle size={18} />
          </div>
          <div style={{ fontSize: '2rem', fontWeight: 700, marginTop: '0.5rem', lineHeight: 1 }} className="mono">
            {summary.high}
          </div>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.5rem' }}>
            15 to 35 cycles remaining &bull; Plan repair this week
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
            <span style={{ fontSize: '0.8125rem', fontWeight: 700, textTransform: 'uppercase' }}>Normal Checkup Due</span>
            <Clock size={18} />
          </div>
          <div style={{ fontSize: '2rem', fontWeight: 700, marginTop: '0.5rem', lineHeight: 1 }} className="mono">
            {summary.medium}
          </div>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.5rem' }}>
            35 to 75 cycles remaining &bull; Standard routine wear
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
            <span style={{ fontSize: '0.8125rem', fontWeight: 700, textTransform: 'uppercase' }}>Healthy & Good to Fly</span>
            <CheckCircle size={18} />
          </div>
          <div style={{ fontSize: '2rem', fontWeight: 700, marginTop: '0.5rem', lineHeight: 1 }} className="mono">
            {summary.low}
          </div>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.5rem' }}>
            &gt; 75 cycles remaining &bull; Running smoothly
          </div>
        </div>
      </div>

      {/* Outdated / Unknown Simple Notice Bar */}
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
          {summary.outdated > 0 && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.375rem', color: 'var(--outdated-text)' }}>
              <AlertCircle size={16} />
              <span>
                <strong>{summary.outdated} Engine{summary.outdated === 1 ? '' : 's'} Need Update:</strong> Newer machine sensor recordings have arrived. Click 'Refresh Status' to recalculate.
              </span>
            </div>
          )}

          {summary.unknown > 0 && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.375rem', color: 'var(--unknown-text)' }}>
              <HelpCircle size={16} />
              <span>
                <strong>{summary.unknown} Waiting for Sensor Data:</strong> Needs more sensor recordings before remaining cycles can be calculated.
              </span>
            </div>
          )}
        </div>
      )}

      {/* Filter Tabs & Fleet Group Selector */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '0.75rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
          <span style={{ fontSize: '0.8125rem', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
            <Filter size={14} /> Filter by Urgency:
          </span>
          {[
            { id: 'all', label: `All Engines (${totalMachines})` },
            { id: 'urgent', label: `Immediate Service (${summary.urgent})` },
            { id: 'high', label: `Service Soon (${summary.high})` },
            { id: 'medium', label: `Normal Checkup (${summary.medium})` },
            { id: 'low', label: `Healthy (${summary.low})` },
            { id: 'unknown', label: `Needs Data (${summary.unknown})` },
          ].map((tab) => (
            <button
              key={tab.id}
              type="button"
              className={`btn ${selectedBand === tab.id ? 'btn-primary' : 'btn-secondary'}`}
              style={{ fontSize: '0.75rem', padding: '0.25rem 0.625rem' }}
              onClick={() => {
                setSelectedBand(tab.id as any);
                setOffset(0);
              }}
            >
              {tab.label}
            </button>
          ))}
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
          <span style={{ fontSize: '0.8125rem', color: 'var(--text-muted)' }}>
            Engine Fleet Group:
          </span>
          {[
            { id: 'all', label: 'All Fleets' },
            { id: 'FD001', label: 'Fleet 1 (Sea Level)' },
            { id: 'FD002', label: 'Fleet 2 (Multi-altitude)' },
            { id: 'FD003', label: 'Fleet 3 (Dual Faults)' },
            { id: 'FD004', label: 'Fleet 4 (Heavy Operations)' },
          ].map((sub) => (
            <button
              key={sub.id}
              type="button"
              className={`btn ${selectedSubset === sub.id ? 'btn-primary' : 'btn-secondary'}`}
              style={{ fontSize: '0.75rem', padding: '0.25rem 0.625rem' }}
              onClick={() => setSelectedSubset(sub.id as any)}
            >
              {sub.label}
            </button>
          ))}
        </div>
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
        <LoadingState message="Checking engine health and calculating remaining flights..." />
      ) : !data || data.items.length === 0 ? (
        <EmptyState
          title={selectedBand === 'all' ? 'No Registered Engines Found' : `No Engines in this Urgency Category`}
          description={
            selectedBand === 'all'
              ? 'No engines or equipment are registered in this organization yet. Add an engine to begin checking health.'
              : `There are currently no engines classified in the selected category.`
          }
          action={
            selectedBand === 'all' ? (
              <button
                type="button"
                className="btn btn-primary"
                onClick={onNavigateToRegistry}
              >
                Go to Engine Setup
              </button>
            ) : (
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => setSelectedBand('all')}
              >
                Show All Engines
              </button>
            )
          }
        />
      ) : (
        <div className="table-container">
          <table className="table">
            <thead>
              <tr>
                <th>Engine Code &amp; Name</th>
                <th>Engine Type</th>
                <th>Estimated Cycles Left</th>
                <th>Urgency Level</th>
                <th>Last Cycle Checked</th>
                <th>Data Freshness</th>
                <th>Why this status? (Simple Reason)</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {data.items
                .filter((item: MaintenancePriorityItem) => selectedSubset === 'all' || item.asset_code.includes(selectedSubset))
                .map((item: MaintenancePriorityItem) => {
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
                        {item.machine_type === 'cmapss_engine' ? 'Simulated Test Engine' : 'Real Factory Engine'}
                      </span>
                    </td>

                    <td>
                      {item.status === 'available' && item.rul_cycles !== null ? (
                        <div style={{ display: 'flex', alignItems: 'baseline', gap: '0.35rem' }}>
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
                            cycles left
                          </span>
                        </div>
                      ) : (
                        <span style={{ color: 'var(--text-muted)', fontSize: '0.8125rem', fontStyle: 'italic' }}>
                          Waiting for data ({item.reason || 'unmeasured'})
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
                        <span className="badge badge-outdated" title="New sensor readings have arrived since this was calculated">
                          <AlertCircle size={12} />
                          <span>Needs Recalculate (New Data)</span>
                        </span>
                      ) : item.is_current ? (
                        <span className="badge badge-low">
                          <CheckCircle size={12} />
                          <span>Up to Date</span>
                        </span>
                      ) : (
                        <span className="badge badge-unknown">
                          <HelpCircle size={12} />
                          <span>Waiting for Readings</span>
                        </span>
                      )}
                    </td>

                    <td style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)', maxWidth: '300px', lineHeight: '1.4' }}>
                      {getLaymanExplanation(item)}
                    </td>

                    <td onClick={(e) => e.stopPropagation()}>
                      <button
                        type="button"
                        className="btn btn-secondary"
                        onClick={() => onSelectMachine(item.machine_id)}
                        style={{ padding: '0.3rem 0.65rem', fontSize: '0.75rem', display: 'inline-flex', alignItems: 'center', gap: '0.3rem' }}
                      >
                        <span>View Details</span>
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
              Showing {data.items.length} of {totalMachines} engines in your fleet
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
