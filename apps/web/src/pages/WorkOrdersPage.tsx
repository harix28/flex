import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../context/AuthContext';
import { workOrdersApi, registryApi } from '../services/api';
import { WorkOrder, WorkOrderStatus, WorkOrderPriority, Machine } from '../services/types';
import { StatusBadge } from '../components/common/Badge';
import { WorkOrderCreateModal } from '../components/work-orders/WorkOrderCreateModal';
import { LoadingState } from '../components/common/LoadingState';
import { EmptyState } from '../components/common/EmptyState';
import { ErrorState } from '../components/common/ErrorState';
import {
  Wrench,
  Filter,
  Plus,
  RefreshCw,
  ChevronRight,
  AlertCircle,
  Calendar,
} from 'lucide-react';

interface WorkOrdersPageProps {
  onSelectWorkOrder: (workOrderId: string) => void;
}

export const WorkOrdersPage: React.FC<WorkOrdersPageProps> = ({ onSelectWorkOrder }) => {
  const { activeTenant, canApproveWorkOrders, canExecuteWorkOrders } = useAuth();

  const [workOrders, setWorkOrders] = useState<WorkOrder[]>([]);
  const [machines, setMachines] = useState<Machine[]>([]);
  const [totalCount, setTotalCount] = useState<number>(0);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<{ message: string; requestId?: string } | null>(null);

  // Filters
  const [statusFilter, setStatusFilter] = useState<WorkOrderStatus | ''>('');
  const [priorityFilter, setPriorityFilter] = useState<WorkOrderPriority | ''>('');
  const [dueFrom, setDueFrom] = useState('');
  const [dueTo, setDueTo] = useState('');

  const [limit] = useState(25);
  const [offset, setOffset] = useState(0);

  // Create Modal
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);

  const fetchWorkOrders = useCallback(async () => {
    if (!activeTenant) return;
    setIsLoading(true);
    setError(null);

    try {
      const res = await workOrdersApi.listWorkOrders(activeTenant.id, {
        status: statusFilter || undefined,
        priority: priorityFilter || undefined,
        due_from: dueFrom || undefined,
        due_to: dueTo || undefined,
        limit,
        offset,
      });
      setWorkOrders(res.items);
      setTotalCount(res.total);
    } catch (err: any) {
      setError({ message: err.message || 'Failed to list work orders', requestId: err.requestId });
    } finally {
      setIsLoading(false);
    }
  }, [activeTenant, statusFilter, priorityFilter, dueFrom, dueTo, limit, offset]);

  // Load machines for manual creation
  useEffect(() => {
    if (!activeTenant) return;
    registryApi.listMachines(activeTenant.id, { limit: 100 }).then((res) => setMachines(res.items)).catch(() => {});
  }, [activeTenant]);

  useEffect(() => {
    fetchWorkOrders();
  }, [fetchWorkOrders]);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.75rem' }}>
        <div>
          <h1 style={{ fontSize: '1.5rem', fontWeight: 700 }}>Maintenance Work Orders</h1>
          <p style={{ fontSize: '0.875rem', color: 'var(--text-secondary)', marginTop: '0.25rem' }}>
            Human review and approval gates. Predictions never automatically dispatch work or alter machinery.
          </p>
        </div>

        <div style={{ display: 'flex', gap: '0.5rem' }}>
          <button
            type="button"
            className="btn btn-secondary"
            onClick={fetchWorkOrders}
            disabled={isLoading}
          >
            <RefreshCw size={14} className={isLoading ? 'animate-spin' : ''} />
            <span>Refresh</span>
          </button>
          {(canApproveWorkOrders() || canExecuteWorkOrders()) && (
            <button
              type="button"
              className="btn btn-primary"
              onClick={() => setIsCreateModalOpen(true)}
            >
              <Plus size={16} />
              <span>New Work Order Draft</span>
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
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <Filter size={14} style={{ color: 'var(--text-muted)' }} />
          <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Status:</span>
          <select
            className="form-control"
            value={statusFilter}
            onChange={(e) => {
              setStatusFilter(e.target.value as WorkOrderStatus);
              setOffset(0);
            }}
            style={{ fontSize: '0.8125rem', padding: '0.35rem 0.65rem' }}
          >
            <option value="">All Statuses</option>
            <option value="draft">Draft (Review Pending)</option>
            <option value="approved">Approved</option>
            <option value="in_progress">In Progress</option>
            <option value="blocked">Blocked</option>
            <option value="completed">Completed (Terminal)</option>
            <option value="cancelled">Cancelled (Terminal)</option>
          </select>

          <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginLeft: '0.5rem' }}>Priority:</span>
          <select
            className="form-control"
            value={priorityFilter}
            onChange={(e) => {
              setPriorityFilter(e.target.value as WorkOrderPriority);
              setOffset(0);
            }}
            style={{ fontSize: '0.8125rem', padding: '0.35rem 0.65rem' }}
          >
            <option value="">All Priorities</option>
            <option value="critical">Critical</option>
            <option value="high">High</option>
            <option value="medium">Medium</option>
            <option value="low">Low</option>
          </select>
        </div>

        {/* Date Filters */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
          <Calendar size={14} style={{ color: 'var(--text-muted)' }} />
          <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Due Range:</span>
          <input
            type="date"
            className="form-control"
            value={dueFrom}
            onChange={(e) => {
              setDueFrom(e.target.value);
              setOffset(0);
            }}
            style={{ fontSize: '0.75rem', padding: '0.25rem 0.5rem' }}
            placeholder="From"
          />
          <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>to</span>
          <input
            type="date"
            className="form-control"
            value={dueTo}
            onChange={(e) => {
              setDueTo(e.target.value);
              setOffset(0);
            }}
            style={{ fontSize: '0.75rem', padding: '0.25rem 0.5rem' }}
            placeholder="To"
          />

          {(statusFilter || priorityFilter || dueFrom || dueTo) && (
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => {
                setStatusFilter('');
                setPriorityFilter('');
                setDueFrom('');
                setDueTo('');
                setOffset(0);
              }}
              style={{ fontSize: '0.75rem', padding: '0.25rem 0.5rem' }}
            >
              Clear
            </button>
          )}
        </div>
      </div>

      {/* Error */}
      {error && (
        <ErrorState
          message={error.message}
          requestId={error.requestId}
          onRetry={fetchWorkOrders}
        />
      )}

      {/* Table / Empty / Loading */}
      {isLoading ? (
        <LoadingState message="Loading work orders and approval states..." />
      ) : workOrders.length === 0 ? (
        <EmptyState
          title="No Work Orders Found"
          description={
            statusFilter || priorityFilter || dueFrom || dueTo
              ? 'No work orders matched the selected filter criteria.'
              : 'There are currently no maintenance work orders in this organization. Draft a work order from a machine prediction or create a manual inspection draft.'
          }
          icon={<Wrench size={24} />}
          action={
            (canApproveWorkOrders() || canExecuteWorkOrders()) ? (
              <button
                type="button"
                className="btn btn-primary"
                onClick={() => setIsCreateModalOpen(true)}
              >
                Create Work Order Draft
              </button>
            ) : undefined
          }
        />
      ) : (
        <div className="table-container">
          <table className="table">
            <thead>
              <tr>
                <th>Work Order Number</th>
                <th>Title &amp; Scope</th>
                <th>Status</th>
                <th>Priority</th>
                <th>OCC Version</th>
                <th>Assigned Technician</th>
                <th>Evidence Status</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {workOrders.map((wo) => (
                <tr
                  key={wo.id}
                  style={{ cursor: 'pointer' }}
                  onClick={() => onSelectWorkOrder(wo.id)}
                >
                  <td>
                    <span className="mono" style={{ fontWeight: 600, color: 'var(--primary)' }}>
                      {wo.work_order_number}
                    </span>
                    <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>
                      {wo.origin === 'prediction' ? 'From Model Prediction' : 'Manual Draft'}
                    </div>
                  </td>

                  <td>
                    <div style={{ fontWeight: 500, color: 'var(--text-primary)' }}>{wo.title}</div>
                    <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', maxWidth: '320px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                      {wo.description}
                    </div>
                  </td>

                  <td>
                    <StatusBadge status={wo.status} />
                  </td>

                  <td>
                    <span className="badge badge-unknown" style={{ textTransform: 'capitalize' }}>
                      {wo.priority}
                    </span>
                  </td>

                  <td>
                    <span className="badge badge-unknown mono">v{wo.version}</span>
                  </td>

                  <td>
                    {wo.assigned_technician ? (
                      <span style={{ fontSize: '0.8125rem' }}>{wo.assigned_technician.display_name}</span>
                    ) : (
                      <span style={{ fontSize: '0.8125rem', color: 'var(--text-muted)', fontStyle: 'italic' }}>
                        Unassigned
                      </span>
                    )}
                  </td>

                  <td>
                    {wo.origin === 'prediction' ? (
                      wo.is_evidence_outdated ? (
                        <span className="badge badge-outdated" title="Newer observations exist">
                          <AlertCircle size={12} />
                          <span>Outdated</span>
                        </span>
                      ) : (
                        <span className="badge badge-low">
                          <span>Current</span>
                        </span>
                      )
                    ) : (
                      <span style={{ color: 'var(--text-muted)', fontSize: '0.75rem' }}>—</span>
                    )}
                  </td>

                  <td onClick={(e) => e.stopPropagation()}>
                    <button
                      type="button"
                      className="btn btn-secondary"
                      onClick={() => onSelectWorkOrder(wo.id)}
                      style={{ padding: '0.3rem 0.6rem', fontSize: '0.75rem' }}
                    >
                      <span>Review</span>
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
              Showing {workOrders.length} of {totalCount} total work orders
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
                disabled={offset + limit >= totalCount}
                onClick={() => setOffset(offset + limit)}
                style={{ padding: '0.25rem 0.5rem', fontSize: '0.75rem' }}
              >
                Next
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Manual Draft Modal */}
      {isCreateModalOpen && activeTenant && (
        <WorkOrderCreateModal
          isOpen={isCreateModalOpen}
          onClose={() => setIsCreateModalOpen(false)}
          tenantId={activeTenant.id}
          machines={machines}
          onSuccess={(wo) => {
            fetchWorkOrders();
            onSelectWorkOrder(wo.id);
          }}
        />
      )}
    </div>
  );
};
