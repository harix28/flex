import React, { useState } from 'react';
import { Modal } from '../common/Modal';
import { workOrdersApi } from '../../services/api';
import { WorkOrderPriority, Machine } from '../../services/types';
import { Wrench, AlertCircle, Loader2 } from 'lucide-react';

interface WorkOrderCreateModalProps {
  isOpen: boolean;
  onClose: () => void;
  tenantId: string;
  machines: Machine[];
  defaultMachineId?: string;
  predictionId?: string; // If creating from prediction
  defaultTitle?: string;
  defaultDescription?: string;
  defaultPriority?: WorkOrderPriority;
  onSuccess: (workOrder: any) => void;
}

export const WorkOrderCreateModal: React.FC<WorkOrderCreateModalProps> = ({
  isOpen,
  onClose,
  tenantId,
  machines,
  defaultMachineId,
  predictionId,
  defaultTitle = '',
  defaultDescription = '',
  defaultPriority = 'medium',
  onSuccess,
}) => {
  const [machineId, setMachineId] = useState(defaultMachineId || (machines.length > 0 ? machines[0].id : ''));
  const [title, setTitle] = useState(defaultTitle);
  const [description, setDescription] = useState(defaultDescription);
  const [priority, setPriority] = useState<WorkOrderPriority>(defaultPriority);
  const [plannedDate, setPlannedDate] = useState('');
  const [dueDate, setDueDate] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setIsSubmitting(true);

    try {
      let res;
      if (predictionId) {
        // Prediction-linked draft
        res = await workOrdersApi.createDraftFromPrediction(tenantId, predictionId, {
          title: title.trim() || undefined,
          description: description.trim() || undefined,
          priority,
          due_date: dueDate || undefined,
          planned_date: plannedDate || undefined,
        });
      } else {
        // Manual draft
        if (!machineId) {
          throw new Error('Please select a target machine');
        }
        res = await workOrdersApi.createManualDraft(tenantId, {
          machine_id: machineId,
          title: title.trim(),
          description: description.trim(),
          priority,
          due_date: dueDate || null,
          planned_date: plannedDate || null,
        });
      }

      onSuccess(res.work_order);
      onClose();
    } catch (err: any) {
      setError(err.message || 'Failed to create work order draft');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={predictionId ? 'Create Draft from Prediction' : 'Create Manual Maintenance Draft'}
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
            form="create-wo-form"
            className="btn btn-primary"
            disabled={isSubmitting}
          >
            {isSubmitting ? (
              <>
                <Loader2 size={16} className="animate-spin" />
                <span>Creating Draft...</span>
              </>
            ) : (
              <>
                <Wrench size={16} />
                <span>Create Draft Work Order</span>
              </>
            )}
          </button>
        </>
      }
    >
      <form id="create-wo-form" onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
        {error && (
          <div className="alert alert-danger" style={{ margin: 0 }}>
            <AlertCircle size={18} style={{ flexShrink: 0 }} />
            <div>{error}</div>
          </div>
        )}

        {predictionId ? (
          <div
            style={{
              padding: '0.75rem',
              backgroundColor: 'var(--bg-subtle)',
              borderRadius: 'var(--radius-sm)',
              fontSize: '0.8125rem',
              color: 'var(--text-secondary)',
            }}
          >
            <strong>Evidence Snapshot:</strong> This work order will capture an immutable snapshot of the model RUL estimate, cutoff cycle, and priority band at creation time.
          </div>
        ) : (
          <div className="form-group">
            <label className="form-label" htmlFor="wo-machine-select">
              Target Machine *
            </label>
            <select
              id="wo-machine-select"
              className="form-control"
              value={machineId}
              onChange={(e) => setMachineId(e.target.value)}
              required
            >
              <option value="" disabled>Select machine...</option>
              {machines.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.asset_code} — {m.name}
                </option>
              ))}
            </select>
          </div>
        )}

        <div className="form-group">
          <label className="form-label" htmlFor="wo-title-input">
            Work Order Title *
          </label>
          <input
            id="wo-title-input"
            type="text"
            className="form-control"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="e.g., Compressor inspection and clearance verification"
            required
            maxLength={180}
          />
        </div>

        <div className="form-group">
          <label className="form-label" htmlFor="wo-desc-input">
            Description & Inspection Scope *
          </label>
          <textarea
            id="wo-desc-input"
            className="form-control"
            rows={3}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Document scope of inspection, technical manuals referenced, and required procedures."
            required
            maxLength={4000}
          />
        </div>

        <div className="grid-cols-3">
          <div className="form-group">
            <label className="form-label" htmlFor="wo-priority-select">
              Priority Level *
            </label>
            <select
              id="wo-priority-select"
              className="form-control"
              value={priority}
              onChange={(e) => setPriority(e.target.value as WorkOrderPriority)}
            >
              <option value="low">Low</option>
              <option value="medium">Medium</option>
              <option value="high">High</option>
              <option value="critical">Critical</option>
            </select>
          </div>

          <div className="form-group">
            <label className="form-label" htmlFor="wo-planned-date">
              Planned Date
            </label>
            <input
              id="wo-planned-date"
              type="date"
              className="form-control"
              value={plannedDate}
              onChange={(e) => setPlannedDate(e.target.value)}
            />
          </div>

          <div className="form-group">
            <label className="form-label" htmlFor="wo-due-date">
              Due Date
            </label>
            <input
              id="wo-due-date"
              type="date"
              className="form-control"
              value={dueDate}
              onChange={(e) => setDueDate(e.target.value)}
            />
          </div>
        </div>

        <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
          Draft work orders require human review and explicit approval by a Plant Manager or Admin before work can be started.
        </div>
      </form>
    </Modal>
  );
};
