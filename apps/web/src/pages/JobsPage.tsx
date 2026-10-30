import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../context/AuthContext';
import { jobsApi } from '../services/api';
import { OutboxJob } from '../services/types';
import { LoadingState } from '../components/common/LoadingState';
import { ErrorState } from '../components/common/ErrorState';
import {
  ListChecks,
  Play,
  RefreshCw,
  Clock,
  CheckCircle2,
  AlertCircle,
  Server,
} from 'lucide-react';

export const JobsPage: React.FC = () => {
  const { activeTenant } = useAuth();
  const [jobs, setJobs] = useState<OutboxJob[]>([]);
  const [totalJobs, setTotalJobs] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<{ type: 'success' | 'error'; message: string } | null>(null);

  const fetchJobs = useCallback(async () => {
    if (!activeTenant) return;
    setError(null);
    try {
      const res = await jobsApi.listJobs(activeTenant.id, 50);
      setJobs(res.items || []);
      setTotalJobs(res.total || 0);
    } catch (err: any) {
      setError(err.message || 'Failed to fetch outbox jobs');
    } finally {
      setIsLoading(false);
    }
  }, [activeTenant]);

  useEffect(() => {
    fetchJobs();
  }, [fetchJobs]);

  const handleEnqueueFleetScore = async () => {
    if (!activeTenant) return;
    setIsSubmitting(true);
    setFeedback(null);
    try {
      const res = await jobsApi.submitFleetScore(activeTenant.id);
      setFeedback({
        type: 'success',
        message: `Fleet scoring job #${res.job_id.slice(0, 8)} enqueued successfully. Background worker processing via SKIP LOCKED leasing.`,
      });
      await fetchJobs();
    } catch (err: any) {
      setFeedback({
        type: 'error',
        message: err.message || 'Failed to submit fleet scoring job',
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  const pendingCount = jobs.filter((j) => j.status === 'pending' || j.status === 'leased').length;
  const deliveredCount = jobs.filter((j) => j.status === 'delivered').length;
  const deadLetterCount = jobs.filter((j) => j.status === 'dead_letter').length;

  return (
    <div style={{ padding: '1.5rem', maxWidth: '1400px', margin: '0 auto', display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      {/* Page Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '1rem' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.625rem' }}>
            <ListChecks size={24} style={{ color: 'var(--primary)' }} />
            <h1 style={{ fontSize: '1.5rem', fontWeight: 700, margin: 0 }}>Background Jobs & Fleet Scoring</h1>
          </div>
          <p style={{ margin: '0.35rem 0 0', color: 'var(--text-muted)', fontSize: '0.875rem' }}>
            Transactional PostgreSQL outbox queue with atomic <code>FOR UPDATE SKIP LOCKED</code> claims and lease fencing.
          </p>
        </div>

        <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
          <button
            type="button"
            className="btn btn-secondary"
            onClick={fetchJobs}
            disabled={isLoading}
            style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', padding: '0.5rem 1rem' }}
          >
            <RefreshCw size={15} className={isLoading ? 'spin' : ''} />
            Refresh Queue
          </button>

          <button
            type="button"
            className="btn btn-primary"
            onClick={handleEnqueueFleetScore}
            disabled={isSubmitting}
            style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', padding: '0.5rem 1.25rem' }}
          >
            <Play size={15} />
            {isSubmitting ? 'Enqueuing Run...' : 'Enqueue Fleet Scoring Run'}
          </button>
        </div>
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
          {feedback.type === 'success' ? <CheckCircle2 size={16} /> : <AlertCircle size={16} />}
          {feedback.message}
        </div>
      )}

      {/* Queue Stats Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: '1rem' }}>
        <div style={{ backgroundColor: 'var(--bg-surface)', padding: '1.25rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-subtle)' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <span style={{ fontSize: '0.8125rem', fontWeight: 600, color: 'var(--text-muted)' }}>ACTIVE IN QUEUE</span>
            <Clock size={18} style={{ color: pendingCount > 0 ? 'var(--primary)' : 'var(--text-muted)' }} />
          </div>
          <div style={{ marginTop: '0.5rem', display: 'flex', alignItems: 'baseline', gap: '0.5rem' }}>
            <span style={{ fontSize: '1.75rem', fontWeight: 700 }}>{pendingCount}</span>
            <span style={{ fontSize: '0.8125rem', color: 'var(--text-muted)' }}>pending / leased</span>
          </div>
        </div>

        <div style={{ backgroundColor: 'var(--bg-surface)', padding: '1.25rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-subtle)' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <span style={{ fontSize: '0.8125rem', fontWeight: 600, color: 'var(--text-muted)' }}>SUCCESSFULLY PROCESSED</span>
            <CheckCircle2 size={18} style={{ color: 'var(--success)' }} />
          </div>
          <div style={{ marginTop: '0.5rem', display: 'flex', alignItems: 'baseline', gap: '0.5rem' }}>
            <span style={{ fontSize: '1.75rem', fontWeight: 700, color: 'var(--success)' }}>{deliveredCount}</span>
            <span style={{ fontSize: '0.8125rem', color: 'var(--text-muted)' }}>delivered</span>
          </div>
        </div>

        <div style={{ backgroundColor: 'var(--bg-surface)', padding: '1.25rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-subtle)' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <span style={{ fontSize: '0.8125rem', fontWeight: 600, color: 'var(--text-muted)' }}>DEAD LETTER (EXHAUSTED)</span>
            <AlertCircle size={18} style={{ color: deadLetterCount > 0 ? 'var(--danger)' : 'var(--text-muted)' }} />
          </div>
          <div style={{ marginTop: '0.5rem', display: 'flex', alignItems: 'baseline', gap: '0.5rem' }}>
            <span style={{ fontSize: '1.75rem', fontWeight: 700, color: deadLetterCount > 0 ? 'var(--danger)' : 'var(--text-muted)' }}>
              {deadLetterCount}
            </span>
            <span style={{ fontSize: '0.8125rem', color: 'var(--text-muted)' }}>failed after max retries</span>
          </div>
        </div>
      </div>

      {error && <ErrorState message={error} onRetry={fetchJobs} />}

      {/* Jobs Queue Table */}
      <div style={{ backgroundColor: 'var(--bg-surface)', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-subtle)', padding: '1.25rem' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
          <h2 style={{ fontSize: '1rem', fontWeight: 600, margin: 0 }}>Outbox Queue Registry</h2>
          <span style={{ fontSize: '0.8125rem', color: 'var(--text-muted)' }}>Total jobs: {totalJobs}</span>
        </div>

        {isLoading ? (
          <LoadingState message="Loading background outbox queue..." />
        ) : jobs.length === 0 ? (
          <div style={{ padding: '3rem 1rem', textAlign: 'center', color: 'var(--text-muted)' }}>
            <Server size={36} style={{ margin: '0 auto 0.75rem', opacity: 0.5 }} />
            <div style={{ fontWeight: 600, fontSize: '0.9375rem' }}>No outbox events queued yet</div>
            <div style={{ fontSize: '0.8125rem', marginTop: '0.25rem' }}>
              Click "Enqueue Fleet Scoring Run" above to submit a real batch scoring job.
            </div>
          </div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.875rem' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid var(--border-subtle)', color: 'var(--text-muted)', fontSize: '0.75rem', textTransform: 'uppercase' }}>
                  <th style={{ padding: '0.75rem 1rem' }}>Job ID</th>
                  <th style={{ padding: '0.75rem 1rem' }}>Event Type</th>
                  <th style={{ padding: '0.75rem 1rem' }}>Source Event ID</th>
                  <th style={{ padding: '0.75rem 1rem' }}>Status</th>
                  <th style={{ padding: '0.75rem 1rem' }}>Attempts</th>
                  <th style={{ padding: '0.75rem 1rem' }}>Result Summary</th>
                  <th style={{ padding: '0.75rem 1rem' }}>Created At</th>
                </tr>
              </thead>
              <tbody>
                {jobs.map((j) => {
                  let statusBg = 'rgba(148, 163, 184, 0.15)';
                  let statusColor = 'var(--text-muted)';
                  if (j.status === 'delivered') {
                    statusBg = 'rgba(34, 197, 94, 0.15)';
                    statusColor = 'var(--success)';
                  } else if (j.status === 'leased' || j.status === 'pending') {
                    statusBg = 'rgba(14, 165, 233, 0.15)';
                    statusColor = 'var(--primary)';
                  } else if (j.status === 'dead_letter') {
                    statusBg = 'rgba(239, 68, 68, 0.15)';
                    statusColor = 'var(--danger)';
                  }

                  return (
                    <tr key={j.id} style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                      <td style={{ padding: '0.75rem 1rem', fontFamily: 'monospace', fontWeight: 600 }}>
                        {j.id.slice(0, 8)}...
                      </td>
                      <td style={{ padding: '0.75rem 1rem' }}>
                        <span style={{ backgroundColor: 'var(--bg-canvas)', border: '1px solid var(--border-subtle)', padding: '0.15rem 0.45rem', borderRadius: 'var(--radius-sm)', fontSize: '0.75rem', fontWeight: 600 }}>
                          {j.event_type}
                        </span>
                      </td>
                      <td style={{ padding: '0.75rem 1rem', fontFamily: 'monospace', fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                        {j.source_event_id}
                      </td>
                      <td style={{ padding: '0.75rem 1rem' }}>
                        <span
                          style={{
                            padding: '0.2rem 0.5rem',
                            borderRadius: 'var(--radius-sm)',
                            fontSize: '0.75rem',
                            fontWeight: 600,
                            backgroundColor: statusBg,
                            color: statusColor,
                          }}
                        >
                          {j.status.toUpperCase()}
                        </span>
                      </td>
                      <td style={{ padding: '0.75rem 1rem', color: 'var(--text-muted)' }}>
                        {j.attempts} / {j.max_attempts}
                      </td>
                      <td style={{ padding: '0.75rem 1rem' }}>
                        {j.result ? (
                          <span style={{ fontSize: '0.8125rem' }}>
                            <strong>{j.result.total}</strong> engines (<strong>{j.result.available}</strong> valid, <strong>{j.result.unavailable}</strong> unavail)
                          </span>
                        ) : j.error_code ? (
                          <span style={{ color: 'var(--danger)', fontSize: '0.75rem' }}>Error: {j.error_code}</span>
                        ) : (
                          <span style={{ color: 'var(--text-muted)', fontSize: '0.75rem' }}>In progress...</span>
                        )}
                      </td>
                      <td style={{ padding: '0.75rem 1rem', fontSize: '0.8125rem', color: 'var(--text-muted)' }}>
                        {new Date(j.created_at).toLocaleString()}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};
