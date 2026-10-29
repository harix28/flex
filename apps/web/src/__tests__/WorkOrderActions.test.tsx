import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { WorkOrderActionModal } from '../components/work-orders/WorkOrderActionModal';
import { workOrdersApi } from '../services/api';
import { WorkOrder } from '../services/types';

vi.mock('../services/api', () => ({
  workOrdersApi: {
    transitionWorkOrder: vi.fn(),
    assignTechnician: vi.fn(),
  },
}));

describe('WorkOrderActionModal', () => {
  const baseOrder: WorkOrder = {
    id: 'wo-101',
    tenant_id: 't-1',
    machine_id: 'm-1',
    work_order_number: 'WO-2026-0001',
    origin: 'prediction',
    title: 'Inspect High Pressure Turbine',
    description: 'Borescope inspection requested based on causal RUL estimation.',
    priority: 'high',
    status: 'draft',
    evidence: {
      prediction_id: 'pred-100',
      model_version: 'runs/fd001-v1',
      model_digest: 'sha256-mod',
      bundle_digest: 'sha256-bun',
      stream_id: 'str-1',
      cutoff_cycle: 130,
      rul_cycles: 42,
      rul_units: 'cycles',
      prediction_status: 'available',
      release_status: 'experimental',
      policy_version: 'v1.0',
      snapshot_priority_band: 'high',
      disclaimer: 'simulated',
    },
    is_evidence_outdated: false,
    current_max_observation_cycle: 130,
    planned_date: null,
    cancellation_reason: null,
    block_reason: null,
    completion_summary: null,
    approved_at: null,
    started_at: null,
    blocked_at: null,
    completed_at: null,
    cancelled_at: null,
    assigned_technician_id: null,
    due_date: '2026-04-01T00:00:00Z',
    version: 3,
    created_at: '2026-03-01T10:00:00Z',
    updated_at: '2026-03-01T10:00:00Z',
  };

  it('renders approval dialog and submits with correct version', async () => {
    vi.mocked(workOrdersApi.transitionWorkOrder).mockResolvedValueOnce({
      work_order: {
        ...baseOrder,
        status: 'approved',
        version: 4,
      },
      request_id: 'req-44',
    });

    const onSuccess = vi.fn();
    const onClose = vi.fn();

    render(
      <WorkOrderActionModal
        isOpen={true}
        actionType="approve"
        tenantId="t-1"
        workOrder={baseOrder}
        onClose={onClose}
        onSuccess={onSuccess}
      />
    );

    expect(screen.getByText(/Approve Work Order WO-2026-0001/i)).toBeInTheDocument();
    expect(screen.getByText(/v3/i)).toBeInTheDocument();

    const submitBtn = screen.getByRole('button', { name: /Approve Work Order/i });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(workOrdersApi.transitionWorkOrder).toHaveBeenCalledWith(
        't-1',
        'wo-101',
        expect.objectContaining({ version: 3, action: 'approve' })
      );
      expect(onSuccess).toHaveBeenCalled();
    });
  });

  it('handles OCC 409 concurrency conflict by alerting the operator without silent overwrite', async () => {
    vi.mocked(workOrdersApi.transitionWorkOrder).mockRejectedValueOnce({
      status: 409,
      detail: 'concurrency_conflict: version mismatch',
      message: 'This record was modified by another user or session. State has been refreshed to prevent overwriting.',
    });

    render(
      <WorkOrderActionModal
        isOpen={true}
        actionType="approve"
        tenantId="t-1"
        workOrder={baseOrder}
        onClose={() => {}}
        onSuccess={() => {}}
      />
    );

    const submitBtn = screen.getByRole('button', { name: /Approve Work Order/i });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(
        screen.getByText(/This record was modified by another user or session/i)
      ).toBeInTheDocument();
    });
  });

  it('renders cancellation reason input and handles submission', async () => {
    vi.mocked(workOrdersApi.transitionWorkOrder).mockResolvedValueOnce({
      work_order: {
        ...baseOrder,
        status: 'cancelled',
        version: 4,
      },
      request_id: 'req-55',
    });

    const onSuccess = vi.fn();

    render(
      <WorkOrderActionModal
        isOpen={true}
        actionType="cancel"
        tenantId="t-1"
        workOrder={baseOrder}
        onClose={() => {}}
        onSuccess={onSuccess}
      />
    );

    const reasonInput = screen.getByLabelText(/Reason for Cancellation/i);
    expect(reasonInput).toBeInTheDocument();

    fireEvent.change(reasonInput, { target: { value: 'Engine retired from test cell.' } });

    const submitBtn = screen.getByRole('button', { name: /Cancel Work Order/i });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(workOrdersApi.transitionWorkOrder).toHaveBeenCalledWith(
        't-1',
        'wo-101',
        expect.objectContaining({
          version: 3,
          action: 'cancel',
          reason: 'Engine retired from test cell.',
        })
      );
      expect(onSuccess).toHaveBeenCalled();
    });
  });
});
