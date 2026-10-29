import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../context/AuthContext';
import { workOrdersApi, authApi } from '../services/api';
import { WorkOrder, WorkOrderHistory, EligibleAssignee, WorkOrderTransitionRecord } from '../services/types';
import { Breadcrumbs } from '../components/layout/Breadcrumbs';
import { StatusBadge } from '../components/common/Badge';
import { WorkOrderActionModal, ActionType } from '../components/work-orders/WorkOrderActionModal';
import { WorkOrderNotes } from '../components/work-orders/WorkOrderNotes';
import { LoadingState } from '../components/common/LoadingState';
import { ErrorState } from '../components/common/ErrorState';
import {
  CheckCircle,
  XCircle,
  Play,
  PauseCircle,
  UserCheck,
  AlertTriangle,
  History,
  Shield,
  ArrowRight,
  RefreshCw,
  FileText,
  AlertCircle,
} from 'lucide-react';

interface WorkOrderDetailPageProps {
  workOrderId: string;
  onNavigateBack: () => void;
  onSelectMachine: (machineId: string) => void;
}

export const WorkOrderDetailPage: React.FC<WorkOrderDetailPageProps> = ({
  workOrderId,
  onNavigateBack,
  onSelectMachine,
}) => {
  const { activeTenant, user, canApproveWorkOrders, canAssignWorkOrders, canExecuteWorkOrders } = useAuth();

  const [workOrder, setWorkOrder] = useState<WorkOrder | null>(null);
  const [history, setHistory] = useState<WorkOrderHistory | null>(null);
  const [technicians, setTechnicians] = useState<EligibleAssignee[]>([]);

  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<{ message: string; requestId?: string } | null>(null);

  // Action Modal State
  const [activeModalAction, setActiveModalAction] = useState<ActionType | null>(null);

  const fetchWorkOrder = useCallback(async () => {
    if (!activeTenant) return;
    setIsLoading(true);
    setError(null);

    try {
      const res = await workOrdersApi.getWorkOrder(activeTenant.id, workOrderId);
      setWorkOrder(res.work_order);

      const histRes = await workOrdersApi.getHistory(activeTenant.id, workOrderId);
      setHistory(histRes);
    } catch (err: any) {
      setError({ message: err.message || 'Failed to load work order', requestId: err.requestId });
    } finally {
      setIsLoading(false);
    }
  }, [activeTenant, workOrderId]);

  // Load active technicians for assignment
  useEffect(() => {
    if (!activeTenant || !canAssignWorkOrders()) return;
    authApi
      .getEligibleAssignees(activeTenant.id)
      .then((res) => {
        const eligibleTechs = res.items.filter((m) => m.active && m.user_active && m.roles.includes('technician'));
        setTechnicians(eligibleTechs);
      })
      .catch((err) => { setTechnicians([]); setError({ message: err.message || 'Unable to load eligible technicians' }); });
  }, [activeTenant, canAssignWorkOrders]);

  useEffect(() => {
    fetchWorkOrder();
  }, [fetchWorkOrder]);

  if (isLoading && !workOrder) {
    return <LoadingState message="Loading work order details, immutable evidence snapshot, and history timeline..." />;
  }

  if (error && !workOrder) {
    return <ErrorState message={error.message} requestId={error.requestId} onRetry={fetchWorkOrder} />;
  }

  if (!workOrder) return null;

  const isAssignedToCurrentUser = workOrder.assigned_technician_id === user?.id;
  const isTerminal = workOrder.status === 'completed' || workOrder.status === 'cancelled';

  // Permission guards according to state machine & role matrix
  const canApprove = (workOrder.status === 'draft') && canApproveWorkOrders();
  const canAssign = !isTerminal && canAssignWorkOrders();
  const canStart = (workOrder.status === 'approved') && (canApproveWorkOrders() || (canExecuteWorkOrders() && isAssignedToCurrentUser));
  const canBlock = (workOrder.status === 'in_progress') && (canApproveWorkOrders() || (canExecuteWorkOrders() && isAssignedToCurrentUser));
  const canResume = (workOrder.status === 'blocked') && (canApproveWorkOrders() || (canExecuteWorkOrders() && isAssignedToCurrentUser));
  const canComplete = (workOrder.status === 'in_progress') && (canApproveWorkOrders() || (canExecuteWorkOrders() && isAssignedToCurrentUser));
  const canCancel = !isTerminal && canApproveWorkOrders();
  const canAddNote = !isTerminal && (canApproveWorkOrders() || (canExecuteWorkOrders() && isAssignedToCurrentUser));

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      {/* Breadcrumbs */}
      <Breadcrumbs
        items={[
          { label: 'Work Orders', onClick: onNavigateBack },
          { label: workOrder.work_order_number },
        ]}
      />

      {/* Work Order Header */}
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
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', flexWrap: 'wrap' }}>
            <h1 style={{ fontSize: '1.625rem', fontWeight: 700 }} className="mono">
              {workOrder.work_order_number}
            </h1>
            <StatusBadge status={workOrder.status} />
            <span className="badge badge-unknown" style={{ textTransform: 'capitalize' }}>
              Priority: {workOrder.priority}
            </span>
            <span className="badge badge-unknown mono">OCC v{workOrder.version}</span>
            {workOrder.is_evidence_outdated && (
              <span className="badge badge-outdated" title="Newer observations exist">
                <AlertCircle size={13} />
                <span>Evidence Outdated</span>
              </span>
            )}
          </div>

          <h2 style={{ fontSize: '1.25rem', fontWeight: 600, marginTop: '0.5rem', color: 'var(--text-primary)' }}>
            {workOrder.title}
          </h2>

          <div style={{ fontSize: '0.8125rem', color: 'var(--text-muted)', marginTop: '0.5rem', display: 'flex', gap: '1.5rem', flexWrap: 'wrap' }}>
            <span>
              Target Machine:{' '}
              <button
                type="button"
                onClick={() => onSelectMachine(workOrder.machine_id)}
                style={{
                  background: 'none',
                  border: 'none',
                  color: 'var(--primary)',
                  cursor: 'pointer',
                  fontWeight: 600,
                  textDecoration: 'underline',
                  fontFamily: 'var(--font-mono)',
                }}
              >
                {workOrder.machine?.asset_code || workOrder.machine_id}
              </button>
            </span>

            <span>
              Assigned Technician:{' '}
              <strong style={{ color: 'var(--text-secondary)' }}>
                {workOrder.assigned_technician?.display_name || 'None (Unassigned)'}
              </strong>
            </span>

            <span>
              Created: <span className="mono">{new Date(workOrder.created_at).toLocaleString()}</span>
            </span>

            {workOrder.due_date && (
              <span>
                Due Date: <span className="mono">{workOrder.due_date}</span>
              </span>
            )}
          </div>
        </div>

        {/* Action Controls */}
        <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', alignItems: 'center' }}>
          <button
            type="button"
            className="btn btn-secondary"
            onClick={fetchWorkOrder}
            disabled={isLoading}
          >
            <RefreshCw size={14} className={isLoading ? 'animate-spin' : ''} />
            <span>Refresh</span>
          </button>

          {canApprove && (
            <button
              type="button"
              className="btn btn-primary"
              onClick={() => setActiveModalAction('approve')}
            >
              <CheckCircle size={16} />
              <span>Approve Draft</span>
            </button>
          )}

          {canAssign && (
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => setActiveModalAction('assign')}
            >
              <UserCheck size={16} />
              <span>{workOrder.assigned_technician_id ? 'Reassign Tech' : 'Assign Tech'}</span>
            </button>
          )}

          {canStart && (
            <button
              type="button"
              className="btn btn-primary"
              onClick={() => setActiveModalAction('start')}
            >
              <Play size={16} />
              <span>Start Execution</span>
            </button>
          )}

          {canBlock && (
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => setActiveModalAction('block')}
              style={{ color: 'var(--urgent-text)', borderColor: 'var(--urgent-border)' }}
            >
              <PauseCircle size={16} />
              <span>Block Work</span>
            </button>
          )}

          {canResume && (
            <button
              type="button"
              className="btn btn-primary"
              onClick={() => setActiveModalAction('resume')}
            >
              <Play size={16} />
              <span>Resume Work</span>
            </button>
          )}

          {canComplete && (
            <button
              type="button"
              className="btn btn-success"
              onClick={() => setActiveModalAction('complete')}
            >
              <CheckCircle size={16} />
              <span>Complete Work</span>
            </button>
          )}

          {canCancel && (
            <button
              type="button"
              className="btn btn-danger"
              onClick={() => setActiveModalAction('cancel')}
            >
              <XCircle size={16} />
              <span>Cancel Work Order</span>
            </button>
          )}
        </div>
      </div>

      {/* Outdated Evidence Warning Alert if applicable */}
      {workOrder.is_evidence_outdated && (
        <div className="alert alert-warning">
          <AlertTriangle size={20} style={{ flexShrink: 0 }} />
          <div>
            <strong>Outdated Prediction Evidence Detected:</strong> New telemetry observations have arrived since this draft captured its prediction snapshot (Latest stored cycle: {workOrder.current_max_observation_cycle}).
            <div style={{ marginTop: '0.25rem', fontSize: '0.8125rem' }}>
              <em>Approval Policy:</em> Approving a draft with outdated evidence is rejected by the backend with HTTP 409 (<code className="mono">outdated_evidence</code>). To proceed, cancel this draft, evaluate a current prediction, and create a fresh reviewed draft.
            </div>
          </div>
        </div>
      )}

      {/* Description & Scope */}
      <div className="card">
        <h3 style={{ fontSize: '0.9375rem', fontWeight: 600, marginBottom: '0.5rem', display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
          <FileText size={16} style={{ color: 'var(--primary)' }} />
          <span>Description &amp; Procedure Scope</span>
        </h3>
        <p style={{ color: 'var(--text-secondary)', fontSize: '0.875rem', whiteSpace: 'pre-wrap', lineHeight: 1.6 }}>
          {workOrder.description}
        </p>

        {workOrder.completion_summary && (
          <div style={{ marginTop: '1rem', padding: '0.75rem', backgroundColor: 'rgba(16, 185, 129, 0.1)', border: '1px solid var(--low-border)', borderRadius: 'var(--radius-sm)' }}>
            <strong style={{ color: 'var(--low-text)', display: 'block', marginBottom: '0.25rem' }}>
              Completion Summary:
            </strong>
            <p style={{ color: 'var(--text-primary)', fontSize: '0.875rem', whiteSpace: 'pre-wrap' }}>
              {workOrder.completion_summary}
            </p>
          </div>
        )}

        {workOrder.cancellation_reason && (
          <div style={{ marginTop: '1rem', padding: '0.75rem', backgroundColor: 'rgba(239, 68, 68, 0.1)', border: '1px solid var(--urgent-border)', borderRadius: 'var(--radius-sm)' }}>
            <strong style={{ color: 'var(--urgent-text)', display: 'block', marginBottom: '0.25rem' }}>
              Cancellation Reason:
            </strong>
            <p style={{ color: 'var(--text-primary)', fontSize: '0.875rem', whiteSpace: 'pre-wrap' }}>
              {workOrder.cancellation_reason}
            </p>
          </div>
        )}

        {workOrder.block_reason && workOrder.status === 'blocked' && (
          <div style={{ marginTop: '1rem', padding: '0.75rem', backgroundColor: 'rgba(245, 158, 11, 0.1)', border: '1px solid var(--high-border)', borderRadius: 'var(--radius-sm)' }}>
            <strong style={{ color: 'var(--high-text)', display: 'block', marginBottom: '0.25rem' }}>
              Active Block Reason:
            </strong>
            <p style={{ color: 'var(--text-primary)', fontSize: '0.875rem', whiteSpace: 'pre-wrap' }}>
              {workOrder.block_reason}
            </p>
          </div>
        )}
      </div>

      {/* Immutable Prediction Evidence Snapshot (if linked to prediction) */}
      {workOrder.origin === 'prediction' && (
        <div className="card card-elevated" style={{ borderLeft: '4px solid var(--primary)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem', flexWrap: 'wrap', gap: '0.5rem' }}>
            <h3 style={{ fontSize: '1rem', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <Shield size={18} style={{ color: 'var(--primary)' }} />
              <span>Immutable Prediction Evidence Snapshot</span>
            </h3>
            <span className="badge badge-unknown" style={{ fontSize: '0.7rem' }}>
              Snapshot Captured at Draft Creation
            </span>
          </div>

          <div className="grid-cols-4" style={{ fontSize: '0.8125rem' }}>
            <div>
              <span style={{ color: 'var(--text-muted)' }}>Estimated RUL:</span>{' '}
              <strong className="mono" style={{ fontSize: '1.125rem', color: 'var(--text-primary)' }}>
                {workOrder.evidence.rul_cycles?.toFixed(1) ?? '—'} cycles
              </strong>
            </div>

            <div>
              <span style={{ color: 'var(--text-muted)' }}>Cutoff Flight Cycle:</span>{' '}
              <strong className="mono">Cycle {workOrder.evidence.cutoff_cycle}</strong>
            </div>

            <div>
              <span style={{ color: 'var(--text-muted)' }}>Snapshot Priority:</span>{' '}
              <span className="badge badge-unknown" style={{ textTransform: 'capitalize' }}>
                {workOrder.evidence.snapshot_priority_band || 'unknown'}
              </span>
            </div>

            <div>
              <span style={{ color: 'var(--text-muted)' }}>Model Digest:</span>{' '}
              <span className="mono" style={{ fontSize: '0.75rem' }} title={workOrder.evidence.model_digest || ''}>
                {workOrder.evidence.model_digest ? `${workOrder.evidence.model_digest.substring(0, 12)}...` : '—'}
              </span>
            </div>
          </div>

          {workOrder.evidence.disclaimer && (
            <div
              style={{
                marginTop: '0.75rem',
                padding: '0.5rem 0.75rem',
                backgroundColor: 'var(--bg-subtle)',
                borderRadius: 'var(--radius-sm)',
                fontSize: '0.75rem',
                color: 'var(--text-muted)',
                fontStyle: 'italic',
                borderLeft: '2px solid var(--border-strong)',
              }}
            >
              {workOrder.evidence.disclaimer}
            </div>
          )}
        </div>
      )}

      {/* Execution Notes & Concurrency-Safe Notes Timeline */}
      <WorkOrderNotes
        tenantId={activeTenant!.id}
        workOrderId={workOrder.id}
        currentVersion={workOrder.version}
        notes={history?.notes || []}
        canAddNote={canAddNote}
        onNoteAdded={(newNote, newVersion) => {
          setWorkOrder((prev: WorkOrder | null) => (prev ? { ...prev, version: newVersion } : null));
          setHistory((prev: WorkOrderHistory | null) => (prev ? { ...prev, notes: [...prev.notes, newNote] } : null));
        }}
        onVersionConflict={fetchWorkOrder}
      />

      {/* State Transitions & Assignment History Timeline */}
      <div className="card">
        <h3 style={{ fontSize: '1rem', fontWeight: 600, marginBottom: '0.75rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <History size={18} style={{ color: 'var(--primary)' }} />
          <span>Audit &amp; Lifecycle Transition History</span>
        </h3>

        {history && history.transitions.length > 0 ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
            {history.transitions.map((t: WorkOrderTransitionRecord) => (
              <div
                key={t.id}
                style={{
                  display: 'flex',
                  alignItems: 'flex-start',
                  gap: '0.75rem',
                  fontSize: '0.8125rem',
                  padding: '0.5rem 0',
                  borderBottom: '1px solid var(--border-subtle)',
                }}
              >
                <div style={{ width: '130px', color: 'var(--text-muted)' }} className="mono">
                  {new Date(t.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', width: '220px' }}>
                  <StatusBadge status={t.from_status} />
                  <ArrowRight size={13} style={{ color: 'var(--text-muted)' }} />
                  <StatusBadge status={t.to_status} />
                </div>

                <div style={{ flex: 1 }}>
                  <strong style={{ color: 'var(--text-primary)' }}>Action: {t.action}</strong>
                  {t.reason && (
                    <div style={{ color: 'var(--text-secondary)', marginTop: '0.125rem' }}>
                      Reason: {t.reason}
                    </div>
                  )}
                  <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginTop: '0.125rem' }}>
                    Actor: {t.actor?.display_name || t.actor_id}
                  </div>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p style={{ fontSize: '0.8125rem', color: 'var(--text-muted)' }}>No recorded transitions.</p>
        )}
      </div>

      {/* Action Modal */}
      {activeModalAction && activeTenant && (
        <WorkOrderActionModal
          isOpen={!!activeModalAction}
          onClose={() => setActiveModalAction(null)}
          tenantId={activeTenant.id}
          workOrder={workOrder}
          actionType={activeModalAction}
          technicians={technicians}
          onSuccess={(updatedWo) => {
            setWorkOrder(updatedWo);
            fetchWorkOrder();
          }}
        />
      )}
    </div>
  );
};
