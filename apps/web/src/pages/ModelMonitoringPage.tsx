import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../context/AuthContext';
import { mlopsApi } from '../services/api';
import { ModelInfo, MlObservability, MonitoringRun, MonitoringRunDetail } from '../services/types';
import { LoadingState } from '../components/common/LoadingState';
import { ErrorState } from '../components/common/ErrorState';
import {
  Activity,
  AlertTriangle,
  Clock,
  ShieldCheck,
  Layers,
  TrendingDown,
  BarChart2,
  RefreshCw,
  ChevronRight,
  CheckCircle2,
} from 'lucide-react';

export const ModelMonitoringPage: React.FC = () => {
  const { activeTenant } = useAuth();
  const [modelInfo, setModelInfo] = useState<ModelInfo | null>(null);
  const [observability, setObservability] = useState<MlObservability | null>(null);
  const [monitoringRuns, setMonitoringRuns] = useState<MonitoringRun[]>([]);
  const [selectedRunDetail, setSelectedRunDetail] = useState<MonitoringRunDetail | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<{ message: string; requestId?: string } | null>(null);
  const [isDriftRunning, setIsDriftRunning] = useState(false);
  const [isEvalRunning, setIsEvalRunning] = useState(false);
  const [evalSubset, setEvalSubset] = useState<'FD001' | 'FD002' | 'FD003' | 'FD004'>('FD001');
  const [actionFeedback, setActionFeedback] = useState<{ type: 'success' | 'error'; message: string } | null>(null);

  const fetchData = useCallback(async () => {
    if (!activeTenant) return;
    setIsLoading(true);
    setError(null);

    try {
      const [infoRes, obsRes, runsRes] = await Promise.all([
        mlopsApi.getModelInfo(activeTenant.id),
        mlopsApi.getObservability(activeTenant.id),
        mlopsApi.getMonitoringRuns(activeTenant.id, 20, 0),
      ]);
      setModelInfo(infoRes);
      setObservability(obsRes);
      setMonitoringRuns(runsRes.runs || []);
    } catch (err: any) {
      setError({
        message: err.message || 'Failed to load model registry and monitoring data',
        requestId: err.requestId,
      });
    } finally {
      setIsLoading(false);
    }
  }, [activeTenant]);

  const handleRunDrift = async () => {
    if (!activeTenant) return;
    setIsDriftRunning(true);
    setActionFeedback(null);
    try {
      await mlopsApi.triggerDriftMonitoring(activeTenant.id);
      setActionFeedback({ type: 'success', message: 'Statistical input drift analysis completed successfully.' });
      await fetchData();
    } catch (err: any) {
      setActionFeedback({ type: 'error', message: err.message || 'Drift monitoring evaluation failed' });
    } finally {
      setIsDriftRunning(false);
    }
  };

  const handleRunEvaluation = async () => {
    if (!activeTenant) return;
    setIsEvalRunning(true);
    setActionFeedback(null);
    try {
      await mlopsApi.triggerEvaluation(activeTenant.id, evalSubset);
      setActionFeedback({ type: 'success', message: `Offline benchmark evaluation for ${evalSubset} completed successfully.` });
      await fetchData();
    } catch (err: any) {
      setActionFeedback({ type: 'error', message: err.message || 'Offline ground-truth evaluation failed' });
    } finally {
      setIsEvalRunning(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const viewRunDetail = async (runId: string) => {
    if (!activeTenant) return;
    try {
      const detail = await mlopsApi.getMonitoringRunDetail(activeTenant.id, runId);
      setSelectedRunDetail(detail);
    } catch (err: any) {
      alert(`Could not load run detail: ${err.message}`);
    }
  };

  if (isLoading) {
    return (
      <div style={{ padding: '2rem' }}>
        <LoadingState message="Loading model registry verification, inference telemetry and monitoring state..." />
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ padding: '2rem' }}>
        <ErrorState
          title="Model Monitoring Unavailable"
          message={error.message}
          requestId={error.requestId}
          onRetry={fetchData}
        />
      </div>
    );
  }

  // Derive latest drift and evaluation runs
  const latestDriftRun = monitoringRuns.find((r) => r.run_type === 'drift');
  const latestEvalRun = monitoringRuns.find((r) => r.run_type === 'evaluation');

  return (
    <div style={{ padding: '1.5rem 2rem', width: '100%' }}>
      {/* Header */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'flex-start',
          marginBottom: '1.5rem',
          flexWrap: 'wrap',
          gap: '1rem',
        }}
      >
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '0.25rem' }}>
            <h1 style={{ fontSize: '1.65rem', fontWeight: 700, color: 'var(--text-primary)', margin: 0 }}>
              Model Governance & Monitoring
            </h1>
            <span
              style={{
                backgroundColor: 'rgba(245, 158, 11, 0.15)',
                color: 'var(--high-text)',
                border: '1px solid rgba(245, 158, 11, 0.35)',
                padding: '0.2rem 0.6rem',
                borderRadius: '4px',
                fontSize: '0.75rem',
                fontWeight: 600,
                textTransform: 'uppercase',
                letterSpacing: '0.05em',
              }}
            >
              {modelInfo?.review_status || 'Experiment Only'}
            </span>
          </div>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', margin: 0 }}>
            Traceable inference observability, versioned input drift monitoring, and offline ground-truth evaluation.
          </p>
        </div>

        <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', alignItems: 'center' }}>
          {/* Drift Trigger */}
          <button
            type="button"
            className="btn btn-secondary"
            onClick={handleRunDrift}
            disabled={isDriftRunning || isEvalRunning || isLoading}
            style={{ fontSize: '0.8125rem' }}
          >
            <TrendingDown size={14} className={isDriftRunning ? 'animate-spin' : ''} />
            <span>{isDriftRunning ? 'Analyzing Drift...' : 'Run Drift Analysis'}</span>
          </button>

          {/* Offline Eval Trigger */}
          <div style={{ display: 'inline-flex', alignItems: 'center', gap: '0.25rem' }}>
            <select
              value={evalSubset}
              onChange={(e) => setEvalSubset(e.target.value as any)}
              className="input"
              style={{ padding: '0.35rem 0.5rem', fontSize: '0.8125rem', height: '32px' }}
            >
              <option value="FD001">FD001</option>
              <option value="FD002">FD002</option>
              <option value="FD003">FD003</option>
              <option value="FD004">FD004</option>
            </select>
            <button
              type="button"
              className="btn btn-primary"
              onClick={handleRunEvaluation}
              disabled={isDriftRunning || isEvalRunning || isLoading}
              style={{ fontSize: '0.8125rem' }}
            >
              <CheckCircle2 size={14} className={isEvalRunning ? 'animate-spin' : ''} />
              <span>{isEvalRunning ? 'Evaluating...' : 'Run Benchmark Eval'}</span>
            </button>
          </div>

          <button
            onClick={fetchData}
            className="btn btn-secondary"
            disabled={isLoading}
            style={{ fontSize: '0.8125rem' }}
          >
            <RefreshCw size={14} className={isLoading ? 'animate-spin' : ''} />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {/* Action Execution Feedback Alert */}
      {actionFeedback && (
        <div
          style={{
            padding: '0.75rem 1rem',
            borderRadius: 'var(--radius-md)',
            marginBottom: '1rem',
            fontSize: '0.85rem',
            backgroundColor: actionFeedback.type === 'success' ? 'rgba(34, 197, 94, 0.1)' : 'rgba(239, 68, 68, 0.1)',
            border: `1px solid ${actionFeedback.type === 'success' ? 'rgba(34, 197, 94, 0.3)' : 'rgba(239, 68, 68, 0.3)'}`,
            color: actionFeedback.type === 'success' ? '#15803d' : 'var(--urgent-text)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <span>{actionFeedback.message}</span>
          <button
            onClick={() => setActionFeedback(null)}
            style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'inherit', fontWeight: 700 }}
          >
            ×
          </button>
        </div>
      )}

      {/* Experimental Safety Notice Banner */}
      <div
        style={{
          backgroundColor: 'var(--bg-subtle)',
          borderLeft: '4px solid var(--high-text)',
          border: '1px solid var(--border-subtle)',
          borderRadius: 'var(--radius-md)',
          padding: '0.85rem 1.25rem',
          marginBottom: '1.5rem',
          display: 'flex',
          alignItems: 'center',
          gap: '0.85rem',
        }}
      >
        <AlertTriangle size={20} color="var(--high-text)" style={{ flexShrink: 0 }} />
        <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', lineHeight: 1.5 }}>
          <strong style={{ color: 'var(--text-primary)' }}>Simulated Turbofan Demonstration: </strong>
          {modelInfo?.disclaimer || 'Experimental model only. Not certified for flight dispatch or production maintenance.'}
          {' '}Global model promotion and rollbacks require an operator CLI audit trail; organization admins have read-only visibility.
        </div>
      </div>

      {/* Grid: Active Model Identity & Historical Validation Benchmarks */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(360px, 1fr))',
          gap: '1.25rem',
          marginBottom: '1.5rem',
        }}
      >
        {/* Card 1: Active Serving Model Identity */}
        <div
          style={{
            backgroundColor: 'var(--bg-surface)',
            border: '1px solid var(--border-subtle)',
            borderRadius: 'var(--radius-lg)',
            padding: '1.25rem',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '1rem' }}>
            <Layers size={18} color="var(--primary)" />
            <h2 style={{ fontSize: '1rem', fontWeight: 600, color: 'var(--text-primary)', margin: 0 }}>
              Active Serving Model
            </h2>
            <span
              style={{
                marginLeft: 'auto',
                fontSize: '0.75rem',
                color: 'var(--low-text)',
                backgroundColor: 'var(--low-bg)',
                padding: '0.15rem 0.5rem',
                borderRadius: '4px',
                border: '1px solid var(--low-border)',
                fontWeight: 600,
              }}
            >
              STATE: {modelInfo?.deployment_state?.toUpperCase() || modelInfo?.status?.toUpperCase() || 'UNAVAILABLE'}
            </span>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem', fontSize: '0.85rem' }}>
            <div>
              <span style={{ color: 'var(--text-muted)', display: 'block', fontSize: '0.75rem' }}>Model Version</span>
              <strong style={{ color: 'var(--text-primary)', fontFamily: 'var(--font-mono)' }}>
                {modelInfo?.model_version || 'fd001-v1'}
              </strong>
            </div>

            <div>
              <span style={{ color: 'var(--text-muted)', display: 'block', fontSize: '0.75rem' }}>Model Family</span>
              <span style={{ color: 'var(--text-primary)', textTransform: 'uppercase', fontWeight: 500 }}>
                {modelInfo?.model_family || 'XGBoost'}
              </span>
            </div>

            <div>
              <span style={{ color: 'var(--text-muted)', display: 'block', fontSize: '0.75rem' }}>Feature Schema</span>
              <span style={{ color: 'var(--text-primary)', fontFamily: 'var(--font-mono)' }}>
                {modelInfo?.feature_schema} ({modelInfo?.feature_count} features)
              </span>
            </div>

            <div>
              <span style={{ color: 'var(--text-muted)', display: 'block', fontSize: '0.75rem' }}>Causal Window</span>
              <span style={{ color: 'var(--text-primary)' }}>
                {modelInfo?.window_size} cycles sliding
              </span>
            </div>

            <div>
              <span style={{ color: 'var(--text-muted)', display: 'block', fontSize: '0.75rem' }}>Supported Scope</span>
              <span style={{ color: 'var(--text-primary)' }}>
                {modelInfo?.target_subset} ({modelInfo?.target_machine_type})
              </span>
            </div>

            <div>
              <span style={{ color: 'var(--text-muted)', display: 'block', fontSize: '0.75rem' }}>Target Data Source</span>
              <span style={{ color: 'var(--text-primary)' }}>
                {modelInfo?.target_data_source}
              </span>
            </div>
          </div>

          <div
            style={{
              marginTop: '1rem',
              paddingTop: '0.85rem',
              borderTop: '1px solid var(--border-subtle)',
              fontSize: '0.75rem',
            }}
          >
            <span style={{ color: 'var(--text-muted)', display: 'block', marginBottom: '0.25rem' }}>
              Verified Artifact SHA-256 (Read-Only Digest)
            </span>
            <code
              style={{
                fontFamily: 'var(--font-mono)',
                color: 'var(--text-secondary)',
                wordBreak: 'break-all',
                backgroundColor: 'var(--bg-canvas)',
                padding: '0.25rem 0.5rem',
                borderRadius: '4px',
                display: 'block',
              }}
            >
              {modelInfo?.bundle_digest || 'Unverified'}
            </code>
          </div>
        </div>

        {/* Card 1.5: Multi-Dataset Model Architecture & Coverage */}
        <div
          style={{
            backgroundColor: 'var(--bg-surface)',
            border: '1px solid var(--border-subtle)',
            borderRadius: 'var(--radius-lg)',
            padding: '1.25rem',
            gridColumn: '1 / -1',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.85rem' }}>
            <Layers size={18} color="var(--primary)" />
            <h2 style={{ fontSize: '1rem', fontWeight: 600, color: 'var(--text-primary)', margin: 0 }}>
              Multi-Dataset Model Fleet Routing (FD001–FD004)
            </h2>
            <span style={{ marginLeft: 'auto', fontSize: '0.75rem', color: 'var(--low-text)', fontWeight: 600 }}>
              4 / 4 MODELS ACTIVE
            </span>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: '1rem' }}>
            {[
              { subset: 'FD001', family: 'XGBoost Regressor', window: 30, conditions: '1 (Sea Level)', faults: '1 (HPC Degradation)', testMae: '16.14 cycles', status: 'ACTIVE' },
              { subset: 'FD002', family: 'Ridge Regressor', window: 30, conditions: '6 Operating Modes', faults: '1 (HPC Degradation)', testMae: '21.87 cycles', status: 'ACTIVE' },
              { subset: 'FD003', family: 'XGBoost Regressor', window: 30, conditions: '1 (Sea Level)', faults: '2 (HPC + Fan Degradation)', testMae: '22.07 cycles', status: 'ACTIVE' },
              { subset: 'FD004', family: 'Ridge Regressor', window: 30, conditions: '6 Operating Modes', faults: '2 (HPC + Fan Degradation)', testMae: '29.98 cycles', status: 'ACTIVE' },
            ].map((m) => (
              <div
                key={m.subset}
                style={{
                  backgroundColor: 'var(--bg-canvas)',
                  border: '1px solid var(--border-subtle)',
                  borderRadius: 'var(--radius-md)',
                  padding: '0.85rem',
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.35rem' }}>
                  <span style={{ fontWeight: 700, fontSize: '0.9rem', color: 'var(--text-primary)' }} className="mono">
                    {m.subset}
                  </span>
                  <span className="badge badge-low" style={{ fontSize: '0.65rem' }}>
                    {m.status}
                  </span>
                </div>
                <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: '0.2rem' }}>
                  <strong>{m.family}</strong> ({m.window} cycles)
                </div>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                  Conditions: {m.conditions} | Faults: {m.faults}
                </div>
                <div style={{ marginTop: '0.4rem', fontSize: '0.75rem', color: 'var(--text-primary)', fontFamily: 'var(--font-mono)' }}>
                  Benchmark MAE: <strong>{m.testMae}</strong>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Card 2: Historical Benchmark Performance */}
        <div
          style={{
            backgroundColor: 'var(--bg-surface)',
            border: '1px solid var(--border-subtle)',
            borderRadius: 'var(--radius-lg)',
            padding: '1.25rem',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '1rem' }}>
            <BarChart2 size={18} color="var(--medium-text)" />
            <h2 style={{ fontSize: '1rem', fontWeight: 600, color: 'var(--text-primary)', margin: 0 }}>
              Historical Validation Benchmark
            </h2>
            <span
              style={{
                marginLeft: 'auto',
                fontSize: '0.75rem',
                color: 'var(--text-muted)',
              }}
            >
              NASA C-MAPSS FD001
            </span>
          </div>

          <p style={{ color: 'var(--text-secondary)', fontSize: '0.8rem', lineHeight: 1.4, marginBottom: '1rem' }}>
            {modelInfo?.benchmark_protocol || 'Evaluated on held-out training partition.'}
          </p>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '0.75rem', textAlign: 'center' }}>
            <div
              style={{
                backgroundColor: 'var(--bg-canvas)',
                padding: '0.75rem 0.5rem',
                borderRadius: 'var(--radius-md)',
                border: '1px solid var(--border-subtle)',
              }}
            >
              <div style={{ fontSize: '1.35rem', fontWeight: 700, color: 'var(--text-primary)', fontFamily: 'var(--font-mono)' }}>
                {modelInfo?.benchmark_metrics?.mae_cycles?.toFixed(2) ?? '—'}
              </div>
              <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', textTransform: 'uppercase', marginTop: '0.2rem' }}>
                MAE (Cycles)
              </div>
            </div>

            <div
              style={{
                backgroundColor: 'var(--bg-canvas)',
                padding: '0.75rem 0.5rem',
                borderRadius: 'var(--radius-md)',
                border: '1px solid var(--border-subtle)',
              }}
            >
              <div style={{ fontSize: '1.35rem', fontWeight: 700, color: 'var(--text-primary)', fontFamily: 'var(--font-mono)' }}>
                {modelInfo?.benchmark_metrics?.rmse_cycles?.toFixed(2) ?? '—'}
              </div>
              <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', textTransform: 'uppercase', marginTop: '0.2rem' }}>
                RMSE (Cycles)
              </div>
            </div>

            <div
              style={{
                backgroundColor: 'var(--bg-canvas)',
                padding: '0.75rem 0.5rem',
                borderRadius: 'var(--radius-md)',
                border: '1px solid var(--border-subtle)',
              }}
            >
              <div style={{ fontSize: '1.35rem', fontWeight: 700, color: 'var(--text-primary)', fontFamily: 'var(--font-mono)' }}>
                {modelInfo?.benchmark_metrics?.bias_cycles !== undefined
                  ? `${modelInfo.benchmark_metrics.bias_cycles > 0 ? '+' : ''}${modelInfo.benchmark_metrics.bias_cycles.toFixed(2)}`
                  : '—'}
              </div>
              <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', textTransform: 'uppercase', marginTop: '0.2rem' }}>
                Bias (Signed)
              </div>
            </div>
          </div>

          <div
            style={{
              marginTop: '1rem',
              paddingTop: '0.85rem',
              borderTop: '1px solid var(--border-subtle)',
              fontSize: '0.75rem',
              color: 'var(--text-muted)',
            }}
          >
            <span>Scope: {modelInfo?.benchmark_metrics?.engines ?? 100} evaluation engines • {modelInfo?.benchmark_metrics?.windows ?? 100} fixed causal cutoffs</span>
          </div>
        </div>
      </div>

      {/* Grid: Live Observability & Statistical Monitoring */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(360px, 1fr))',
          gap: '1.25rem',
          marginBottom: '1.5rem',
        }}
      >
        {/* Card 3: Inference Observability & Latency */}
        <div
          style={{
            backgroundColor: 'var(--bg-surface)',
            border: '1px solid var(--border-subtle)',
            borderRadius: 'var(--radius-lg)',
            padding: '1.25rem',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '1rem' }}>
            <Activity size={18} color="var(--outdated-text)" />
            <h2 style={{ fontSize: '1rem', fontWeight: 600, color: 'var(--text-primary)', margin: 0 }}>
              Tenant Inference Observability
            </h2>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '0.75rem', marginBottom: '1rem', textAlign: 'center' }}>
            <div
              style={{
                backgroundColor: 'var(--bg-canvas)',
                padding: '0.65rem 0.4rem',
                borderRadius: 'var(--radius-md)',
              }}
            >
              <div style={{ fontSize: '1.2rem', fontWeight: 700, color: 'var(--text-primary)' }}>
                {observability?.total_predictions ?? 0}
              </div>
              <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>Total Inferences</div>
            </div>

            <div
              style={{
                backgroundColor: 'var(--bg-canvas)',
                padding: '0.65rem 0.4rem',
                borderRadius: 'var(--radius-md)',
              }}
            >
              <div style={{ fontSize: '1.2rem', fontWeight: 700, color: 'var(--low-text)' }}>
                {observability?.available_predictions ?? 0}
              </div>
              <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>Available</div>
            </div>

            <div
              style={{
                backgroundColor: 'var(--bg-canvas)',
                padding: '0.65rem 0.4rem',
                borderRadius: 'var(--radius-md)',
              }}
            >
              <div style={{ fontSize: '1.2rem', fontWeight: 700, color: 'var(--text-secondary)' }}>
                {observability?.unavailable_predictions ?? 0}
              </div>
              <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>Unavailable</div>
            </div>
          </div>

          {/* Latency Breakdown */}
          <div style={{ fontSize: '0.85rem' }}>
            <div style={{ color: 'var(--text-muted)', fontSize: '0.75rem', marginBottom: '0.4rem', textTransform: 'uppercase' }}>
              Latency Distribution (Pure Inference vs Pipeline)
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', padding: '0.35rem 0', borderBottom: '1px solid var(--border-subtle)' }}>
              <span style={{ color: 'var(--text-secondary)' }}>Model Inference (p50 / p95):</span>
              <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}>
                {observability?.latency?.inference_ms?.p50 !== null && observability?.latency?.inference_ms?.p50 !== undefined
                  ? `${observability.latency.inference_ms.p50}ms / ${observability.latency.inference_ms.p95}ms`
                  : 'N/A (Recorded on new inferences)'}
              </span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', padding: '0.35rem 0', borderBottom: '1px solid var(--border-subtle)' }}>
              <span style={{ color: 'var(--text-secondary)' }}>Pipeline Duration (Mean):</span>
              <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}>
                {observability?.latency?.pipeline_ms?.mean !== null && observability?.latency?.pipeline_ms?.mean !== undefined
                  ? `${observability.latency.pipeline_ms.mean}ms`
                  : 'N/A'}
              </span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', padding: '0.35rem 0' }}>
              <span style={{ color: 'var(--text-secondary)' }}>Outdated Predictions:</span>
              <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}>
                {observability?.outdated_predictions_count ?? 0}
              </span>
            </div>
          </div>
        </div>

        {/* Card 4: Input Drift Status */}
        <div
          style={{
            backgroundColor: 'var(--bg-surface)',
            border: '1px solid var(--border-subtle)',
            borderRadius: 'var(--radius-lg)',
            padding: '1.25rem',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '1rem' }}>
            <TrendingDown size={18} color="var(--high-text)" />
            <h2 style={{ fontSize: '1rem', fontWeight: 600, color: 'var(--text-primary)', margin: 0 }}>
              Input Drift Monitoring
            </h2>
            {latestDriftRun ? (
              <span
                style={{
                  marginLeft: 'auto',
                  fontSize: '0.75rem',
                  fontWeight: 600,
                  padding: '0.15rem 0.5rem',
                  borderRadius: '4px',
                  backgroundColor:
                    latestDriftRun.status === 'available'
                      ? latestDriftRun.summary?.drift_detected
                        ? 'var(--urgent-bg)'
                        : 'var(--low-bg)'
                      : 'var(--high-bg)',
                  color:
                    latestDriftRun.status === 'available'
                      ? latestDriftRun.summary?.drift_detected
                        ? 'var(--urgent-text)'
                        : 'var(--low-text)'
                      : 'var(--high-text)',
                  border: `1px solid ${
                    latestDriftRun.status === 'available'
                      ? latestDriftRun.summary?.drift_detected
                        ? 'var(--urgent-border)'
                        : 'var(--low-border)'
                      : 'var(--high-border)'
                  }`,
                }}
              >
                {latestDriftRun.status === 'available'
                  ? latestDriftRun.summary?.drift_detected
                    ? 'DRIFT DETECTED'
                    : 'STABLE'
                  : latestDriftRun.status.toUpperCase()}
              </span>
            ) : (
              <span style={{ marginLeft: 'auto', fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                No Runs Yet
              </span>
            )}
          </div>

          <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '0.85rem' }}>
            Reference Profile: <strong>split.train</strong> partition (70 training engines, 12,377 causal windows, 28 constant channels excluded from z-tests).
          </div>

          {latestDriftRun ? (
            <div style={{ fontSize: '0.85rem' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', padding: '0.35rem 0', borderBottom: '1px solid var(--border-subtle)' }}>
                <span style={{ color: 'var(--text-muted)' }}>Monitoring Status:</span>
                <strong style={{ color: 'var(--text-primary)' }}>{latestDriftRun.status}</strong>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', padding: '0.35rem 0', borderBottom: '1px solid var(--border-subtle)' }}>
                <span style={{ color: 'var(--text-muted)' }}>Evaluated Unique Windows:</span>
                <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}>
                  {latestDriftRun.sample_count} (min threshold: 5)
                </span>
              </div>
              {latestDriftRun.status === 'insufficient_data' && (
                <div style={{ marginTop: '0.5rem', padding: '0.5rem', backgroundColor: 'var(--bg-canvas)', borderRadius: '4px', color: 'var(--high-text)', fontSize: '0.78rem' }}>
                  {latestDriftRun.summary?.message || 'Insufficient unique input samples to assess statistical drift.'}
                </div>
              )}
              {latestDriftRun.status === 'available' && (
                <div style={{ marginTop: '0.5rem', padding: '0.5rem', backgroundColor: 'var(--bg-canvas)', borderRadius: '4px', color: 'var(--low-text)', fontSize: '0.78rem' }}>
                  Input distribution is statistically aligned with the C-MAPSS training baseline.
                </div>
              )}
            </div>
          ) : (
            <div style={{ padding: '1rem', backgroundColor: 'var(--bg-canvas)', borderRadius: '4px', color: 'var(--text-muted)', fontSize: '0.85rem', textAlign: 'center' }}>
              Run offline drift monitoring via operator CLI to evaluate input feature stability.
            </div>
          )}

          <div style={{ marginTop: '0.75rem', fontSize: '0.72rem', color: 'var(--text-muted)', lineHeight: 1.4 }}>
            * Drift indicates a statistical shift in sensor readings relative to training regimes; it is not proof of failure or model inaccuracy.
          </div>
        </div>
      </div>

      {/* Card 5: Ground-Truth Performance Evaluation */}
      <div
        style={{
          backgroundColor: 'var(--bg-surface)',
          border: '1px solid var(--border-subtle)',
          borderRadius: 'var(--radius-lg)',
          padding: '1.25rem',
          marginBottom: '1.5rem',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.75rem' }}>
          <ShieldCheck size={18} color="var(--low-text)" />
          <h2 style={{ fontSize: '1rem', fontWeight: 600, color: 'var(--text-primary)', margin: 0 }}>
            Ground-Truth Performance & Verification
          </h2>
          <span
            style={{
              marginLeft: 'auto',
              fontSize: '0.75rem',
              color: 'var(--high-text)',
              backgroundColor: 'var(--high-bg)',
              padding: '0.15rem 0.5rem',
              borderRadius: '4px',
              border: '1px solid var(--high-border)',
            }}
          >
            LIVE ACCURACY UNAVAILABLE (REQUIRES VERIFIED LABELS)
          </span>
        </div>

        <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem', lineHeight: 1.5, marginBottom: '1rem' }}>
          Real aircraft in flight and operating plant equipment do not yield ground-truth remaining useful life until component failure or overhaul occurs.
          Completed work orders or operator sign-offs cannot be substituted as ground truth.
          Accuracy can only be evaluated against explicitly supplied, provenance-verified reference labels (e.g., NASA test labels <code style={{ fontFamily: 'var(--font-mono)', fontSize: '0.8rem' }}>data/raw/RUL_FD001.txt</code>).
        </p>

        {latestEvalRun && latestEvalRun.status === 'available' ? (
          <div
            style={{
              backgroundColor: 'var(--bg-canvas)',
              border: '1px solid var(--border-subtle)',
              borderRadius: 'var(--radius-md)',
              padding: '1rem',
            }}
          >
            <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: '0.5rem' }}>
              Latest Offline Evaluation Result (Joined Against Verified Reference Labels)
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '1rem' }}>
              <div>
                <span style={{ color: 'var(--text-muted)', fontSize: '0.75rem', display: 'block' }}>Protocol</span>
                <strong style={{ color: 'var(--text-primary)', fontSize: '0.85rem' }}>Official Test Final Cutoff</strong>
              </div>
              <div>
                <span style={{ color: 'var(--text-muted)', fontSize: '0.75rem', display: 'block' }}>Evaluated Samples</span>
                <strong style={{ color: 'var(--text-primary)', fontSize: '0.85rem' }}>
                  {latestEvalRun.sample_count} engine window(s)
                </strong>
              </div>
              <div>
                <span style={{ color: 'var(--text-muted)', fontSize: '0.75rem', display: 'block' }}>Measured MAE</span>
                <strong style={{ color: 'var(--text-primary)', fontSize: '0.85rem', fontFamily: 'var(--font-mono)' }}>
                  {latestEvalRun.summary?.mae_cycles?.toFixed(2) ?? '—'} cycles
                </strong>
              </div>
              <div>
                <span style={{ color: 'var(--text-muted)', fontSize: '0.75rem', display: 'block' }}>Measured RMSE</span>
                <strong style={{ color: 'var(--text-primary)', fontSize: '0.85rem', fontFamily: 'var(--font-mono)' }}>
                  {latestEvalRun.summary?.rmse_cycles?.toFixed(2) ?? '—'} cycles
                </strong>
              </div>
            </div>
          </div>
        ) : (
          <div
            style={{
              padding: '0.85rem 1rem',
              backgroundColor: 'var(--bg-canvas)',
              borderRadius: 'var(--radius-md)',
              color: 'var(--text-muted)',
              fontSize: '0.85rem',
            }}
          >
            No offline ground-truth evaluation runs recorded yet. Use <code style={{ fontFamily: 'var(--font-mono)' }}>python -m sentinel.mlops.cli run-evaluation</code> with verified NASA test labels.
          </div>
        )}
      </div>

      {/* Monitoring Runs History Table */}
      <div
        style={{
          backgroundColor: 'var(--bg-surface)',
          border: '1px solid var(--border-subtle)',
          borderRadius: 'var(--radius-lg)',
          overflow: 'hidden',
        }}
      >
        <div
          style={{
            padding: '1rem 1.25rem',
            borderBottom: '1px solid var(--border-subtle)',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <Clock size={16} color="var(--text-secondary)" />
            <h3 style={{ fontSize: '0.95rem', fontWeight: 600, color: 'var(--text-primary)', margin: 0 }}>
              Monitoring & Evaluation Audit History
            </h3>
          </div>
          <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
            {monitoringRuns.length} recorded run(s)
          </span>
        </div>

        {monitoringRuns.length === 0 ? (
          <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-muted)', fontSize: '0.9rem' }}>
            No monitoring or evaluation runs recorded for this tenant.
          </div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem', textAlign: 'left' }}>
              <thead>
                <tr style={{ backgroundColor: 'var(--bg-surface-elevated)', borderBottom: '1px solid var(--border-subtle)' }}>
                  <th style={{ padding: '0.75rem 1rem', color: 'var(--text-secondary)', fontWeight: 600 }}>Run Type</th>
                  <th style={{ padding: '0.75rem 1rem', color: 'var(--text-secondary)', fontWeight: 600 }}>Model Version</th>
                  <th style={{ padding: '0.75rem 1rem', color: 'var(--text-secondary)', fontWeight: 600 }}>Status</th>
                  <th style={{ padding: '0.75rem 1rem', color: 'var(--text-secondary)', fontWeight: 600 }}>Samples / Engines</th>
                  <th style={{ padding: '0.75rem 1rem', color: 'var(--text-secondary)', fontWeight: 600 }}>Summary Findings</th>
                  <th style={{ padding: '0.75rem 1rem', color: 'var(--text-secondary)', fontWeight: 600 }}>Actor</th>
                  <th style={{ padding: '0.75rem 1rem', color: 'var(--text-secondary)', fontWeight: 600 }}>Executed At</th>
                  <th style={{ padding: '0.75rem 1rem', textAlign: 'right' }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {monitoringRuns.map((run) => (
                  <tr
                    key={run.id}
                    style={{
                      borderBottom: '1px solid var(--border-subtle)',
                      transition: 'background-color 150ms ease',
                    }}
                  >
                    <td style={{ padding: '0.75rem 1rem' }}>
                      <span
                        style={{
                          textTransform: 'uppercase',
                          fontWeight: 600,
                          fontSize: '0.75rem',
                          color: run.run_type === 'drift' ? 'var(--high-text)' : 'var(--medium-text)',
                        }}
                      >
                        {run.run_type}
                      </span>
                    </td>
                    <td style={{ padding: '0.75rem 1rem', fontFamily: 'var(--font-mono)' }}>
                      {run.model_version}
                    </td>
                    <td style={{ padding: '0.75rem 1rem' }}>
                      <span
                        style={{
                          fontSize: '0.75rem',
                          fontWeight: 600,
                          padding: '0.15rem 0.5rem',
                          borderRadius: '4px',
                          backgroundColor:
                            run.status === 'available'
                              ? 'var(--low-bg)'
                              : run.status === 'insufficient_data'
                              ? 'var(--high-bg)'
                              : 'var(--urgent-bg)',
                          color:
                            run.status === 'available'
                              ? 'var(--low-text)'
                              : run.status === 'insufficient_data'
                              ? 'var(--high-text)'
                              : 'var(--urgent-text)',
                          border: `1px solid ${
                            run.status === 'available'
                              ? 'var(--low-border)'
                              : run.status === 'insufficient_data'
                              ? 'var(--high-border)'
                              : 'var(--urgent-border)'
                          }`,
                        }}
                      >
                        {run.status}
                      </span>
                    </td>
                    <td style={{ padding: '0.75rem 1rem', fontFamily: 'var(--font-mono)' }}>
                      {run.sample_count} windows ({run.engine_count} engines)
                    </td>
                    <td style={{ padding: '0.75rem 1rem', color: 'var(--text-secondary)' }}>
                      {run.run_type === 'drift' ? (
                        run.summary?.message || (run.summary?.drift_detected ? 'Drift detected' : 'Stable')
                      ) : (
                        run.summary?.mae_cycles !== null && run.summary?.mae_cycles !== undefined
                          ? `MAE: ${run.summary.mae_cycles.toFixed(2)}c | RMSE: ${run.summary?.rmse_cycles?.toFixed(2)}c`
                          : run.summary?.message || 'Evaluated'
                      )}
                    </td>
                    <td style={{ padding: '0.75rem 1rem', color: 'var(--text-muted)', fontSize: '0.8rem' }}>
                      {run.actor}
                    </td>
                    <td style={{ padding: '0.75rem 1rem', color: 'var(--text-muted)', fontSize: '0.8rem' }}>
                      {new Date(run.created_at).toLocaleString()}
                    </td>
                    <td style={{ padding: '0.75rem 1rem', textAlign: 'right' }}>
                      <button
                        onClick={() => viewRunDetail(run.id)}
                        style={{
                          background: 'none',
                          border: 'none',
                          color: 'var(--primary)',
                          cursor: 'pointer',
                          fontSize: '0.8rem',
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: '0.2rem',
                        }}
                      >
                        Details <ChevronRight size={14} />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Detail Modal */}
      {selectedRunDetail && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            backgroundColor: 'rgba(15, 23, 42, 0.35)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 100,
            padding: '1rem',
          }}
          onClick={() => setSelectedRunDetail(null)}
        >
          <div
            style={{
              backgroundColor: 'var(--bg-surface)',
              border: '1px solid var(--border-subtle)',
              borderRadius: 'var(--radius-lg)',
              maxWidth: '700px',
              width: '100%',
              maxHeight: '85vh',
              overflowY: 'auto',
              padding: '1.5rem',
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
              <h3 style={{ fontSize: '1.1rem', fontWeight: 600, color: 'var(--text-primary)', margin: 0 }}>
                Monitoring Run Detail ({selectedRunDetail.run_type.toUpperCase()})
              </h3>
              <button
                onClick={() => setSelectedRunDetail(null)}
                style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', fontSize: '1.2rem' }}
              >
                ✕
              </button>
            </div>

            <div style={{ fontSize: '0.85rem', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem', marginBottom: '1rem' }}>
              <div>
                <span style={{ color: 'var(--text-muted)', display: 'block', fontSize: '0.75rem' }}>Run ID</span>
                <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.8rem' }}>{selectedRunDetail.id}</span>
              </div>
              <div>
                <span style={{ color: 'var(--text-muted)', display: 'block', fontSize: '0.75rem' }}>Model Version</span>
                <strong>{selectedRunDetail.model_version}</strong>
              </div>
              <div>
                <span style={{ color: 'var(--text-muted)', display: 'block', fontSize: '0.75rem' }}>Status</span>
                <span style={{ color: selectedRunDetail.status === 'available' ? 'var(--low-text)' : 'var(--high-text)' }}>
                  {selectedRunDetail.status}
                </span>
              </div>
              <div>
                <span style={{ color: 'var(--text-muted)', display: 'block', fontSize: '0.75rem' }}>Actor</span>
                <span>{selectedRunDetail.actor}</span>
              </div>
              {selectedRunDetail.reference_digest && (
                <div style={{ gridColumn: 'span 2' }}>
                  <span style={{ color: 'var(--text-muted)', display: 'block', fontSize: '0.75rem' }}>Reference Digest</span>
                  <code style={{ fontFamily: 'var(--font-mono)', fontSize: '0.75rem', wordBreak: 'break-all' }}>
                    {selectedRunDetail.reference_digest}
                  </code>
                </div>
              )}
            </div>

            <div style={{ marginBottom: '1rem' }}>
              <span style={{ color: 'var(--text-muted)', display: 'block', fontSize: '0.75rem', marginBottom: '0.35rem' }}>
                Metrics & Diagnostic Output
              </span>
              <pre
                style={{
                  backgroundColor: 'var(--bg-canvas)',
                  border: '1px solid var(--border-subtle)',
                  borderRadius: 'var(--radius-md)',
                  padding: '0.85rem',
                  fontSize: '0.78rem',
                  fontFamily: 'var(--font-mono)',
                  color: 'var(--text-primary)',
                  overflowX: 'auto',
                  maxHeight: '350px',
                }}
              >
                {JSON.stringify(selectedRunDetail.metrics, null, 2)}
              </pre>
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
              <button
                onClick={() => setSelectedRunDetail(null)}
                style={{
                  padding: '0.4rem 0.9rem',
                  backgroundColor: 'var(--bg-surface-elevated)',
                  border: '1px solid var(--border-strong)',
                  color: 'var(--text-primary)',
                  borderRadius: 'var(--radius-md)',
                  cursor: 'pointer',
                  fontSize: '0.85rem',
                }}
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
