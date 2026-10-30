import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../context/AuthContext';
import { registryApi, ingestionApi, predictionsApi, workOrdersApi } from '../services/api';
import {
  Machine,
  Installation,
  ObservationsResponse,
  DataQualityResponse,
  Prediction,
  WorkOrder,
} from '../services/types';
import { Breadcrumbs } from '../components/layout/Breadcrumbs';
import { SensorTrendChart } from '../components/charts/SensorTrendChart';
import { PredictionCard } from '../components/predictions/PredictionCard';
import { LifetimeStageCard } from '../components/predictions/LifetimeStageCard';
import { RunPredictionModal } from '../components/predictions/RunPredictionModal';
import { WorkOrderCreateModal } from '../components/work-orders/WorkOrderCreateModal';
import { PriorityBadge, StatusBadge } from '../components/common/Badge';
import { LoadingState } from '../components/common/LoadingState';
import { ErrorState } from '../components/common/ErrorState';
import {
  Cpu,
  Wrench,
  History,
  Activity,
  Plus,
  RefreshCw,
  ChevronRight,
} from 'lucide-react';

interface MachineDetailPageProps {
  machineId: string;
  onNavigateBack: () => void;
  onSelectWorkOrder: (workOrderId: string) => void;
}

export const MachineDetailPage: React.FC<MachineDetailPageProps> = ({
  machineId,
  onNavigateBack,
  onSelectWorkOrder,
}) => {
  const { activeTenant, canCreatePredictions, canApproveWorkOrders, canExecuteWorkOrders } = useAuth();

  const [machine, setMachine] = useState<Machine | null>(null);
  const [installations, setInstallations] = useState<Installation[]>([]);
  const [observationsData, setObservationsData] = useState<ObservationsResponse | null>(null);
  const [dataQuality, setDataQuality] = useState<DataQualityResponse | null>(null);
  const [latestPrediction, setLatestPrediction] = useState<Prediction | null>(null);
  const [predictionHistory, setPredictionHistory] = useState<Prediction[]>([]);
  const [relatedWorkOrders, setRelatedWorkOrders] = useState<WorkOrder[]>([]);

  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<{ message: string; requestId?: string } | null>(null);

  // Modals
  const [isRunPredictionOpen, setIsRunPredictionOpen] = useState(false);
  const [isCreateDraftOpen, setIsCreateDraftOpen] = useState(false);
  const [draftPredictionId, setDraftPredictionId] = useState<string | undefined>(undefined);

  const fetchMachineData = useCallback(async () => {
    if (!activeTenant) return;
    setIsLoading(true);
    setError(null);

    try {
      // 1. Machine Details
      const machRes = await registryApi.getMachine(activeTenant.id, machineId);
      setMachine(machRes.machine);

      // 2. Installed Sensor Mappings
      const instRes = await registryApi.getInstallations(activeTenant.id, machineId);
      setInstallations(instRes.items);

      // 3. Sensor Observations & Quality if NASA replay
      if (machRes.machine.data_source === 'nasa_replay') {
        try {
          const qualRes = await ingestionApi.getDataQuality(activeTenant.id, machineId);
          setDataQuality(qualRes);

          const obsRes = await ingestionApi.getObservations(activeTenant.id, machineId, {
            start_cycle: 1,
            end_cycle: 500,
            limit: 500,
          });
          setObservationsData(obsRes);
        } catch {
          // No observations ingested yet
          setObservationsData(null);
          setDataQuality(null);
        }
      }

      // 4. Latest Prediction & History
      try {
        const predRes = await predictionsApi.getLatestPrediction(activeTenant.id, machineId);
        setLatestPrediction(predRes.prediction);
      } catch {
        setLatestPrediction(null);
      }

      try {
        const histRes = await predictionsApi.listPredictions(activeTenant.id, machineId, { limit: 10 });
        setPredictionHistory(histRes.items);
      } catch {
        setPredictionHistory([]);
      }

      // 5. Related Work Orders
      try {
        const woRes = await workOrdersApi.listWorkOrders(activeTenant.id, { machine_id: machineId, limit: 10 });
        setRelatedWorkOrders(woRes.items);
      } catch {
        setRelatedWorkOrders([]);
      }
    } catch (err: any) {
      setError({ message: err.message || 'Failed to load machine data', requestId: err.requestId });
    } finally {
      setIsLoading(false);
    }
  }, [activeTenant, machineId]);

  useEffect(() => {
    fetchMachineData();
  }, [fetchMachineData]);

  if (isLoading && !machine) {
    return <LoadingState message="Loading machine telemetry and historical predictions..." />;
  }

  if (error && !machine) {
    return <ErrorState message={error.message} requestId={error.requestId} onRetry={fetchMachineData} />;
  }

  if (!machine) return null;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      {/* Breadcrumbs */}
      <Breadcrumbs
        items={[
          { label: 'Fleet Overview', onClick: onNavigateBack },
          { label: 'Machines', onClick: onNavigateBack },
          { label: machine.asset_code },
        ]}
      />

      {/* Machine Header */}
      {activeTenant && machine.data_source === 'nasa_replay' && (
        <LifetimeStageCard tenantId={activeTenant.id} machineId={machine.id} />
      )}
      <div
        className="card card-elevated"
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'flex-start',
          flexWrap: 'wrap',
          gap: '1rem',
        }}
      >
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <h1 style={{ fontSize: '1.625rem', fontWeight: 700 }} className="mono">
              {machine.asset_code}
            </h1>
            <span
              className={`badge ${
                machine.lifecycle_status === 'active'
                  ? 'badge-low'
                  : machine.lifecycle_status === 'archived'
                  ? 'badge-unknown'
                  : 'badge-high'
              }`}
            >
              {machine.lifecycle_status}
            </span>
            <span className="badge badge-unknown" style={{ fontSize: '0.7rem' }}>
              {machine.data_source === 'nasa_replay' ? 'NASA Replay Asset' : 'Physical Asset'}
            </span>
          </div>
          <p style={{ fontSize: '1rem', color: 'var(--text-secondary)', marginTop: '0.25rem' }}>
            {machine.name}
          </p>
          <div style={{ fontSize: '0.8125rem', color: 'var(--text-muted)', marginTop: '0.5rem', display: 'flex', gap: '1.5rem', flexWrap: 'wrap' }}>
            <span>Type: <strong className="mono">{machine.machine_type}</strong></span>
            {machine.site && <span>Site: <strong>{machine.site}</strong></span>}
            {machine.location && <span>Location: <strong>{machine.location}</strong></span>}
            <span>Health Status: <strong style={{ fontStyle: 'italic' }}>{machine.health_status}</strong></span>
          </div>
        </div>

        {/* Action Buttons */}
        <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
          <button
            type="button"
            className="btn btn-secondary"
            onClick={fetchMachineData}
            disabled={isLoading}
          >
            <RefreshCw size={14} className={isLoading ? 'animate-spin' : ''} />
            <span>Refresh</span>
          </button>

          {canCreatePredictions() && machine.data_source === 'nasa_replay' && (
            <button
              type="button"
              className="btn btn-primary"
              onClick={() => setIsRunPredictionOpen(true)}
            >
              <Cpu size={16} />
              <span>Run RUL Prediction</span>
            </button>
          )}

          {(canApproveWorkOrders() || canExecuteWorkOrders()) && (
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => {
                setDraftPredictionId(undefined);
                setIsCreateDraftOpen(true);
              }}
            >
              <Wrench size={16} />
              <span>Draft Work Order</span>
            </button>
          )}
        </div>
      </div>

      {/* NASA C-MAPSS Replay Provenance Badge if applicable */}
      {machine.data_source === 'nasa_replay' && machine.source_binding && (
        <div
          style={{
            backgroundColor: 'var(--bg-subtle)',
            border: '1px solid var(--border-subtle)',
            borderRadius: 'var(--radius-md)',
            padding: '0.75rem 1rem',
            fontSize: '0.8125rem',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            flexWrap: 'wrap',
            gap: '0.5rem',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <Activity size={16} style={{ color: 'var(--primary)' }} />
            <span>
              <strong>NASA C-MAPSS Test Partition Provenance:</strong> Engine{' '}
              <strong className="mono">{machine.source_binding.engine_id}</strong> ({machine.source_binding.subset}, split: {machine.source_binding.split})
            </span>
          </div>
          {machine.source_binding.file_sha256 && (
            <span className="mono" style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }} title={machine.source_binding.file_sha256}>
              SHA-256: {machine.source_binding.file_sha256.substring(0, 16)}...
            </span>
          )}
        </div>
      )}

      {/* Data Quality & Telemetry Summary Card */}
      {dataQuality && (
        <div className="card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
            <h3 style={{ fontSize: '0.9375rem', fontWeight: 600 }}>Telemetry Ingestion &amp; Quality</h3>
            <span
              className={`badge ${dataQuality.is_contiguous ? 'badge-low' : 'badge-high'}`}
            >
              {dataQuality.is_contiguous ? 'Contiguous Cycles' : `${dataQuality.missing_cycle_count} Missing Cycles`}
            </span>
          </div>

          <div className="grid-cols-4" style={{ fontSize: '0.8125rem' }}>
            <div>
              <span style={{ color: 'var(--text-muted)' }}>First Stored Cycle:</span>{' '}
              <strong className="mono">Cycle {dataQuality.first_cycle ?? 'None'}</strong>
            </div>
            <div>
              <span style={{ color: 'var(--text-muted)' }}>Latest Stored Cycle:</span>{' '}
              <strong className="mono">Cycle {dataQuality.latest_cycle ?? 'None'}</strong>
            </div>
            <div>
              <span style={{ color: 'var(--text-muted)' }}>Observation Rows:</span>{' '}
              <strong className="mono">{dataQuality.observation_count}</strong>
            </div>
            <div>
              <span style={{ color: 'var(--text-muted)' }}>Latest Ingested At:</span>{' '}
              <span className="mono" style={{ fontSize: '0.75rem' }}>
                {dataQuality.latest_ingested_at ? new Date(dataQuality.latest_ingested_at).toLocaleString() : '—'}
              </span>
            </div>
          </div>

          {/* Gaps Notice */}
          {dataQuality.gaps.length > 0 && (
            <div
              style={{
                marginTop: '0.75rem',
                padding: '0.5rem 0.75rem',
                backgroundColor: 'rgba(245, 158, 11, 0.1)',
                border: '1px solid var(--high-border)',
                borderRadius: 'var(--radius-sm)',
                fontSize: '0.75rem',
                color: 'var(--high-text)',
              }}
            >
              <strong>Detected Gaps in Trajectory:</strong>{' '}
              {dataQuality.gaps.map((g) => `[Cycle ${g.start_cycle}–${g.end_cycle}]`).join(', ')}. Predictions requiring these missing cycles will remain unavailable.
            </div>
          )}
        </div>
      )}

      {/* Sensor Trend Chart & Tabular View */}
      <div>
        <h2 style={{ fontSize: '1.125rem', fontWeight: 600, marginBottom: '0.75rem' }}>
          Sensor Degradation Trends &amp; Telemetry
        </h2>
        {observationsData && observationsData.items.length > 0 ? (
          <SensorTrendChart
            observations={observationsData.items}
            channelSchema={observationsData.channel_schema}
          />
        ) : (
          <div className="card text-center" style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-muted)' }}>
            No observation cycles have been ingested for this machine yet. Import NASA C-MAPSS observations using the ingestion API to view trend plots.
          </div>
        )}
      </div>

      {/* Prediction Section */}
      <div>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
          <h2 style={{ fontSize: '1.125rem', fontWeight: 600 }}>Causal Remaining Useful Life (RUL) Prediction</h2>
          {canCreatePredictions() && machine.data_source === 'nasa_replay' && (
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => setIsRunPredictionOpen(true)}
              style={{ fontSize: '0.8125rem', padding: '0.35rem 0.75rem' }}
            >
              <Cpu size={14} />
              <span>Evaluate New Cutoff</span>
            </button>
          )}
        </div>

        {latestPrediction ? (
          <PredictionCard
            prediction={latestPrediction}
            canCreateDraft={canApproveWorkOrders() || canExecuteWorkOrders()}
            onCreateDraft={() => {
              setDraftPredictionId(latestPrediction.id);
              setIsCreateDraftOpen(true);
            }}
          />
        ) : (
          <div className="card text-center" style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-muted)' }}>
            No predictions have been evaluated for this machine yet. Run inference on stored telemetry to obtain estimated remaining useful flight cycles.
          </div>
        )}

        {/* Prediction History Table */}
        {predictionHistory.length > 0 && (
          <div style={{ marginTop: '1rem' }}>
            <h3 style={{ fontSize: '0.875rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '0.5rem', display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
              <History size={15} />
              <span>Prediction History (Persisted Provenance)</span>
            </h3>
            <div className="table-container" style={{ maxHeight: '220px' }}>
              <table className="table">
                <thead>
                  <tr>
                    <th>Evaluated At</th>
                    <th>Cutoff Cycle</th>
                    <th>Estimated RUL</th>
                    <th>Priority Band</th>
                    <th>Digest</th>
                    <th>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {predictionHistory.map((p) => (
                    <tr key={p.id}>
                      <td className="mono" style={{ fontSize: '0.75rem' }}>
                        {new Date(p.created_at).toLocaleString()}
                      </td>
                      <td className="mono">Cycle {p.requested_cutoff_cycle}</td>
                      <td className="mono">
                        {p.status === 'available' && p.rul_cycles !== null
                          ? `${p.rul_cycles.toFixed(1)} cycles`
                          : `Unavailable (${p.reason})`}
                      </td>
                      <td>
                        <PriorityBadge priority={p.priority_band} />
                      </td>
                      <td className="mono" style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }} title={p.input_digest}>
                        {p.input_digest.substring(0, 10)}...
                      </td>
                      <td>
                        {p.status === 'available' && (
                          <button
                            type="button"
                            className="btn btn-secondary"
                            onClick={() => {
                              setDraftPredictionId(p.id);
                              setIsCreateDraftOpen(true);
                            }}
                            style={{ padding: '0.2rem 0.5rem', fontSize: '0.75rem' }}
                          >
                            <span>Draft WO</span>
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>

      {/* Installed Channels / Mappings */}
      <div>
        <h2 style={{ fontSize: '1.125rem', fontWeight: 600, marginBottom: '0.75rem' }}>
          Installed Logical Sensor Channels ({installations.length})
        </h2>
        <div className="table-container" style={{ maxHeight: '240px' }}>
          <table className="table">
            <thead>
              <tr>
                <th>Channel Slot</th>
                <th>Sensor Code</th>
                <th>Kind</th>
                <th>Installed At</th>
                <th>Valid Period</th>
              </tr>
            </thead>
            <tbody>
              {installations.map((inst) => (
                <tr key={inst.id}>
                  <td className="mono" style={{ fontWeight: 600, color: 'var(--primary)' }}>
                    {inst.channel}
                  </td>
                  <td className="mono">{inst.sensor?.sensor_code || inst.sensor_id}</td>
                  <td>{inst.sensor?.kind || 'cmapss_channel'}</td>
                  <td className="mono" style={{ fontSize: '0.75rem' }}>
                    {new Date(inst.installed_at).toLocaleString()}
                  </td>
                  <td style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                    {inst.removed_at ? `Until ${new Date(inst.removed_at).toLocaleString()}` : 'Active (unbounded)'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Related Maintenance Work Orders */}
      <div>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
          <h2 style={{ fontSize: '1.125rem', fontWeight: 600 }}>Related Maintenance Work Orders</h2>
          {(canApproveWorkOrders() || canExecuteWorkOrders()) && (
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => {
                setDraftPredictionId(undefined);
                setIsCreateDraftOpen(true);
              }}
              style={{ fontSize: '0.8125rem', padding: '0.35rem 0.75rem' }}
            >
              <Plus size={14} />
              <span>Create Work Order</span>
            </button>
          )}
        </div>

        {relatedWorkOrders.length > 0 ? (
          <div className="table-container">
            <table className="table">
              <thead>
                <tr>
                  <th>Number</th>
                  <th>Title</th>
                  <th>Status</th>
                  <th>Priority</th>
                  <th>Version</th>
                  <th>Assigned Tech</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {relatedWorkOrders.map((wo) => (
                  <tr
                    key={wo.id}
                    style={{ cursor: 'pointer' }}
                    onClick={() => onSelectWorkOrder(wo.id)}
                  >
                    <td className="mono" style={{ fontWeight: 600 }}>{wo.work_order_number}</td>
                    <td>{wo.title}</td>
                    <td><StatusBadge status={wo.status} /></td>
                    <td><span className="badge badge-unknown">{wo.priority}</span></td>
                    <td className="mono">v{wo.version}</td>
                    <td>{wo.assigned_technician?.display_name || <span style={{ color: 'var(--text-muted)' }}>Unassigned</span>}</td>
                    <td onClick={(e) => e.stopPropagation()}>
                      <button
                        type="button"
                        className="btn btn-secondary"
                        onClick={() => onSelectWorkOrder(wo.id)}
                        style={{ padding: '0.25rem 0.5rem', fontSize: '0.75rem' }}
                      >
                        <span>View</span>
                        <ChevronRight size={13} />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="card text-center" style={{ padding: '1.5rem', textAlign: 'center', color: 'var(--text-muted)' }}>
            No maintenance work orders have been created for this machine yet.
          </div>
        )}
      </div>

      {/* Run Prediction Modal */}
      {isRunPredictionOpen && activeTenant && (
        <RunPredictionModal
          isOpen={isRunPredictionOpen}
          onClose={() => setIsRunPredictionOpen(false)}
          tenantId={activeTenant.id}
          machineId={machine.id}
          assetCode={machine.asset_code}
          latestCycle={dataQuality?.latest_cycle}
          onSuccess={(pred) => {
            setLatestPrediction(pred);
            fetchMachineData();
          }}
        />
      )}

      {/* Create Draft Modal */}
      {isCreateDraftOpen && activeTenant && (
        <WorkOrderCreateModal
          isOpen={isCreateDraftOpen}
          onClose={() => setIsCreateDraftOpen(false)}
          tenantId={activeTenant.id}
          machines={[machine]}
          defaultMachineId={machine.id}
          predictionId={draftPredictionId}
          onSuccess={(wo) => {
            fetchMachineData();
            onSelectWorkOrder(wo.id);
          }}
        />
      )}
    </div>
  );
};
