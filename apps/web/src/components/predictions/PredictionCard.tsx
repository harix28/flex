import React from 'react';
import { Prediction } from '../../services/types';
import { PriorityBadge } from '../common/Badge';
import { AlertCircle, Wrench, Shield } from 'lucide-react';

interface PredictionCardProps {
  prediction: Prediction;
  onCreateDraft?: () => void;
  canCreateDraft?: boolean;
}

export const PredictionCard: React.FC<PredictionCardProps> = ({
  prediction,
  onCreateDraft,
  canCreateDraft = false,
}) => {
  const isAvailable = prediction.status === 'available';
  const isOutdated = prediction.is_outdated;

  return (
    <div
      className="card card-elevated"
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: '1rem',
        borderLeft: `4px solid ${
          isAvailable
            ? prediction.priority_band === 'urgent'
              ? 'var(--urgent-text)'
              : prediction.priority_band === 'high'
              ? 'var(--high-text)'
              : prediction.priority_band === 'medium'
              ? 'var(--medium-text)'
              : 'var(--low-text)'
            : 'var(--unknown-text)'
        }`,
      }}
    >
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.5rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.625rem' }}>
          <PriorityBadge priority={prediction.priority_band} />
          {isOutdated && (
            <span
              className="badge badge-outdated"
              title="Newer observation cycles have been ingested since this prediction was evaluated."
            >
              <AlertCircle size={12} />
              <span>Evidence Outdated</span>
            </span>
          )}
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <span
            className="badge badge-unknown"
            style={{ fontSize: '0.7rem' }}
          >
            Model: {prediction.model_version}
          </span>
          <span
            className="badge badge-unknown"
            style={{ fontSize: '0.7rem' }}
          >
            Release: {prediction.release_status}
          </span>
        </div>
      </div>

      {/* Main RUL Display */}
      <div style={{ display: 'flex', alignItems: 'baseline', gap: '0.5rem' }}>
        {isAvailable && prediction.rul_cycles !== null ? (
          <>
            <span
              className="mono"
              style={{
                fontSize: '2.5rem',
                fontWeight: 700,
                color: 'var(--text-primary)',
                letterSpacing: '-0.02em',
                lineHeight: 1,
              }}
            >
              {prediction.rul_cycles.toFixed(1)}
            </span>
            <span style={{ fontSize: '1rem', color: 'var(--text-secondary)', fontWeight: 500 }}>
              operating cycles
            </span>
          </>
        ) : (
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--text-muted)' }}>
            <AlertCircle size={24} />
            <span style={{ fontSize: '1.25rem', fontWeight: 600 }}>
              Prediction Unavailable ({prediction.reason || 'unsupported'})
            </span>
          </div>
        )}
      </div>

      {/* Policy Explanation */}
      <div
        style={{
          fontSize: '0.875rem',
          color: 'var(--text-secondary)',
          backgroundColor: 'var(--bg-subtle)',
          padding: '0.625rem 0.875rem',
          borderRadius: 'var(--radius-sm)',
          borderLeft: '2px solid var(--border-strong)',
        }}
      >
        <strong>Policy rule:</strong> {prediction.priority_rule}
      </div>

      {/* Metric Breakdown Table */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
          gap: '0.75rem',
          fontSize: '0.8125rem',
        }}
      >
        <div>
          <span style={{ color: 'var(--text-muted)' }}>Cutoff Cycle:</span>{' '}
          <span className="mono" style={{ fontWeight: 600 }}>Cycle {prediction.requested_cutoff_cycle}</span>
        </div>
        <div>
          <span style={{ color: 'var(--text-muted)' }}>Input Window:</span>{' '}
          <span className="mono">
            {prediction.input_window_start_cycle} – {prediction.input_window_end_cycle} ({prediction.input_observation_count} cycles)
          </span>
        </div>
        <div>
          <span style={{ color: 'var(--text-muted)' }}>Failure Probability:</span>{' '}
          <span style={{ color: 'var(--text-muted)', fontStyle: 'italic' }}>Unavailable (regression only)</span>
        </div>
        <div>
          <span style={{ color: 'var(--text-muted)' }}>Subsystem Diagnosis:</span>{' '}
          <span style={{ color: 'var(--text-muted)', fontStyle: 'italic' }}>Unavailable (not modeled in FD001)</span>
        </div>
      </div>

      {/* Disclaimer */}
      <div
        style={{
          fontSize: '0.75rem',
          color: 'var(--text-muted)',
          display: 'flex',
          alignItems: 'center',
          gap: '0.375rem',
        }}
      >
        <Shield size={13} style={{ flexShrink: 0 }} />
        <span>
          Simulation demonstration on NASA C-MAPSS dataset. Not airworthiness certified. Human review required for all maintenance decisions.
        </span>
      </div>

      {/* Action: Create Draft */}
      {canCreateDraft && isAvailable && onCreateDraft && (
        <div style={{ marginTop: '0.25rem', paddingTop: '0.75rem', borderTop: '1px solid var(--border-subtle)' }}>
          <button
            type="button"
            className="btn btn-primary"
            onClick={onCreateDraft}
            style={{ width: '100%' }}
          >
            <Wrench size={16} />
            <span>Create Draft Work Order from this Prediction</span>
          </button>
        </div>
      )}
    </div>
  );
};
