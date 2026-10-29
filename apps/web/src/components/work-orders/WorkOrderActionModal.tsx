import React, { useState } from 'react';
import { Modal } from '../common/Modal';
import { workOrdersApi } from '../../services/api';
import { WorkOrder, WorkOrderAction, EligibleAssignee } from '../../services/types';
import { AlertTriangle, CheckCircle, PauseCircle, Play, UserCheck, XCircle, Loader2 } from 'lucide-react';

export type ActionType = WorkOrderAction | 'assign';

interface WorkOrderActionModalProps {
  isOpen: boolean;
  onClose: () => void;
  tenantId: string;
  workOrder: WorkOrder;
  actionType: ActionType;
  technicians?: EligibleAssignee[];
  onSuccess: (updatedWorkOrder: WorkOrder) => void;
}

export const WorkOrderActionModal: React.FC<WorkOrderActionModalProps> = ({
  isOpen,
  onClose,
  tenantId,
  workOrder,
  actionType,
  technicians = [],
  onSuccess,
}) => {
  const [reason, setReason] = useState('');
  const [completionSummary, setCompletionSummary] = useState('');
  const [selectedTechId, setSelectedTechId] = useState(
    workOrder.assigned_technician_id || (technicians.length > 0 ? technicians[0].user_id : '')
  );
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const getActionTitle = () => {
    switch (actionType) {
      case 'approve':
        return `Approve Work Order ${workOrder.work_order_number}`;
      case 'cancel':
        return `Cancel Work Order ${workOrder.work_order_number}`;
      case 'start':
        return `Start Maintenance Execution (${workOrder.work_order_number})`;
      case 'block':
        return `Block Work Order ${workOrder.work_order_number}`;
      case 'resume':
        return `Resume Work Order ${workOrder.work_order_number}`;
      case 'complete':
        return `Complete Work Order ${workOrder.work_order_number}`;
      case 'assign':
        return `Assign Technician to ${workOrder.work_order_number}`;
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setIsSubmitting(true);

    try {
      let res;
      if (actionType === 'assign') {
        if (!selectedTechId) {
          throw new Error('Please select an eligible technician');
        }
        res = await workOrdersApi.assignTechnician(tenantId, workOrder.id, {
          version: workOrder.version,
          technician_id: selectedTechId,
          reason: reason.trim() || null,
        });
      } else {
        res = await workOrdersApi.transitionWorkOrder(tenantId, workOrder.id, {
          version: workOrder.version,
          action: actionType,
          reason: reason.trim() || undefined,
          completion_summary: completionSummary.trim() || undefined,
        });
      }

      onSuccess(res.work_order);
      onClose();
    } catch (err: any) {
      setError(err.message || 'Action failed');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={getActionTitle()}
      footer={
        <>
          <button
            type="button"
            className="btn btn-secondary"
            onClick={onClose}
            disabled={isSubmitting}
          >
            Cancel
          </button>
          <button
            type="submit"
            form="wo-action-form"
            className={`btn ${
              actionType === 'cancel'
                ? 'btn-danger'
                : actionType === 'complete'
                ? 'btn-success'
                : 'btn-primary'
            }`}
            disabled={isSubmitting}
          >
            {isSubmitting ? (
              <>
                <Loader2 size={16} className="animate-spin" />
                <span>Processing...</span>
              </>
            ) : actionType === 'approve' ? (
              <>
                <CheckCircle size={16} />
                <span>Approve Work Order</span>
              </>
            ) : actionType === 'start' ? (
              <>
                <Play size={16} />
                <span>Start Work</span>
              </>
            ) : actionType === 'block' ? (
              <>
                <PauseCircle size={16} />
                <span>Block Work</span>
              </>
            ) : actionType === 'complete' ? (
              <>
                <CheckCircle size={16} />
                <span>Complete Work</span>
              </>
            ) : actionType === 'assign' ? (
              <>
                <UserCheck size={16} />
                <span>Confirm Assignment</span>
              </>
            ) : (
              <>
                <XCircle size={16} />
                <span>Cancel Work Order</span>
              </>
            )}
          </button>
        </>
      }
    >
      <form id="wo-action-form" onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
        {error && (
          <div className="alert alert-danger" style={{ margin: 0 }}>
            <AlertTriangle size={18} style={{ flexShrink: 0 }} />
            <div>
              <strong>Action Failed:</strong> {error}
            </div>
          </div>
        )}

        {/* Optimistic Concurrency Control Note */}
        <div style={{ fontSize: '0.8125rem', color: 'var(--text-muted)' }}>
          Target record version: <strong className="mono">v{workOrder.version}</strong>. If another user modifies this work order concurrently, this request will be rejected to prevent silent overwrites.
        </div>

        {actionType === 'approve' && (
          <div>
            <p style={{ fontSize: '0.875rem', color: 'var(--text-secondary)', marginBottom: '0.5rem' }}>
              Confirm approval for maintenance work order <strong className="mono">{workOrder.work_order_number}</strong>.
            </p>
            {workOrder.is_evidence_outdated && (
              <div className="alert alert-warning">
                <AlertTriangle size={18} style={{ flexShrink: 0 }} />
                <div>
                  <strong>Warning:</strong> This draft has outdated prediction evidence. Newer observations have been ingested since the draft was created. <em>Per policy, the backend will reject approval with 409 (outdated_evidence).</em> You must cancel this draft and create a fresh one from the latest prediction.
                </div>
              </div>
            )}
            <p style={{ fontSize: '0.8125rem', color: 'var(--text-muted)' }}>
              Approval authorizes work execution. A technician must be assigned before execution can start.
            </p>
          </div>
        )}

        {actionType === 'assign' && (
          <>
            <div className="form-group">
              <label className="form-label" htmlFor="tech-select">
                Select Technician *
              </label>
              <select
                id="tech-select"
                className="form-control"
                value={selectedTechId}
                onChange={(e) => setSelectedTechId(e.target.value)}
                required
              >
                <option value="" disabled>Select active technician...</option>
                {technicians.map((t) => (
                  <option key={t.user_id} value={t.user_id}>
                    {t.display_name}
                  </option>
                ))}
              </select>
            </div>
            <div className="form-group">
              <label className="form-label" htmlFor="assign-reason">
                Assignment Note (optional)
              </label>
              <input
                id="assign-reason"
                type="text"
                className="form-control"
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                placeholder="e.g., Scheduled for shift B inspection"
                maxLength={200}
              />
            </div>
          </>
        )}

        {actionType === 'start' && (
          <div>
            <p style={{ fontSize: '0.875rem', color: 'var(--text-secondary)' }}>
              Transition work order to <strong>In Progress</strong>.
            </p>
            {!workOrder.assigned_technician_id && (
              <div className="alert alert-warning" style={{ marginTop: '0.5rem' }}>
                <AlertTriangle size={16} />
                <span>Notice: Work orders require an assigned technician before work can start.</span>
              </div>
            )}
          </div>
        )}

        {actionType === 'block' && (
          <div className="form-group">
            <label className="form-label" htmlFor="block-reason">
              Reason for Blocking *
            </label>
            <textarea
              id="block-reason"
              className="form-control"
              rows={3}
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="e.g., Waiting for borescope probe calibration certificate or replacement part arrival"
              required
              maxLength={500}
            />
          </div>
        )}

        {actionType === 'resume' && (
          <div>
            <p style={{ fontSize: '0.875rem', color: 'var(--text-secondary)' }}>
              Resume maintenance work order. The previous block reason will be cleared.
            </p>
          </div>
        )}

        {actionType === 'complete' && (
          <div className="form-group">
            <label className="form-label" htmlFor="complete-summary">
              Completion Summary *
            </label>
            <textarea
              id="complete-summary"
              className="form-control"
              rows={3}
              value={completionSummary}
              onChange={(e) => setCompletionSummary(e.target.value)}
              placeholder="Document visual inspection findings, clearance measurements per AMM 72-00, or corrective actions performed."
              required
              maxLength={2000}
            />
            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.25rem' }}>
              <em>Important:</em> Completion is a terminal state. Marking completed records that technician execution is finished; it does <strong>not</strong> reset machine operating cycles or certify health.
            </div>
          </div>
        )}

        {actionType === 'cancel' && (
          <div className="form-group">
            <label className="form-label" htmlFor="cancel-reason">
              Reason for Cancellation *
            </label>
            <textarea
              id="cancel-reason"
              className="form-control"
              rows={3}
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="Document why this work order is being cancelled (e.g., outdated evidence, duplicate draft, flight schedule adjustment)"
              required
              maxLength={500}
            />
            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.25rem' }}>
              Cancellation is a terminal state.
            </div>
          </div>
        )}
      </form>
    </Modal>
  );
};
