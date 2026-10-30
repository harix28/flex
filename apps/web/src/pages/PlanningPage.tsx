import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../context/AuthContext';
import { planningApi } from '../services/api';
import { PartItem, TechnicianSchedule, WorkOrderReadiness } from '../services/types';
import { LoadingState } from '../components/common/LoadingState';
import { ErrorState } from '../components/common/ErrorState';
import {
  Boxes,
  Users,
  CheckCircle2,
  AlertTriangle,
  Clock,
  Search,
  Wrench,
  ShieldCheck,
  RefreshCw,
  PackageCheck,
  MapPin,
} from 'lucide-react';

export const PlanningPage: React.FC = () => {
  const { activeTenant } = useAuth();
  const [activeTab, setActiveTab] = useState<'inventory' | 'shifts' | 'readiness'>('inventory');

  // Inventory state
  const [inventory, setInventory] = useState<PartItem[]>([]);
  const [inventorySearch, setInventorySearch] = useState('');
  const [isLoadingInventory, setIsLoadingInventory] = useState(false);

  // Shifts state
  const [schedules, setSchedules] = useState<TechnicianSchedule[]>([]);
  const [isLoadingShifts, setIsLoadingShifts] = useState(false);

  // Readiness state
  const [testWoId, setTestWoId] = useState('');
  const [readiness, setReadiness] = useState<WorkOrderReadiness | null>(null);
  const [isLoadingReadiness, setIsLoadingReadiness] = useState(false);
  const [readinessError, setReadinessError] = useState<string | null>(null);

  const [error, setError] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    if (!activeTenant) return;
    setError(null);
    setIsLoadingInventory(true);
    setIsLoadingShifts(true);

    try {
      const [invRes, shiftRes] = await Promise.all([
        planningApi.getInventory(activeTenant.id),
        planningApi.getShifts(activeTenant.id),
      ]);
      setInventory(invRes.items || []);
      setSchedules(shiftRes.items || []);
    } catch (err: any) {
      setError(err.message || 'Failed to load maintenance planning data');
    } finally {
      setIsLoadingInventory(false);
      setIsLoadingShifts(false);
    }
  }, [activeTenant]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleCheckReadiness = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!activeTenant || !testWoId.trim()) return;
    setIsLoadingReadiness(true);
    setReadinessError(null);
    setReadiness(null);

    try {
      const res = await planningApi.getWorkOrderReadiness(activeTenant.id, testWoId.trim());
      setReadiness(res.readiness);
    } catch (err: any) {
      setReadinessError(err.message || 'Work order not found or inaccessible in this tenant');
    } finally {
      setIsLoadingReadiness(false);
    }
  };

  const filteredInventory = inventory.filter(
    (item) =>
      item.part_number.toLowerCase().includes(inventorySearch.toLowerCase()) ||
      item.name.toLowerCase().includes(inventorySearch.toLowerCase()) ||
      item.category.toLowerCase().includes(inventorySearch.toLowerCase()) ||
      item.warehouse_bin.toLowerCase().includes(inventorySearch.toLowerCase())
  );

  const totalPartsCount = inventory.reduce((acc, p) => acc + p.stock_qty, 0);
  const shortageCount = inventory.filter((p) => p.stock_qty <= p.min_required).length;
  const onDutyTechs = schedules.filter((s) => s.is_on_duty).length;

  return (
    <div style={{ padding: '1.5rem', maxWidth: '1400px', margin: '0 auto', display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '1rem' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.625rem' }}>
            <Boxes size={24} style={{ color: 'var(--primary)' }} />
            <h1 style={{ fontSize: '1.5rem', fontWeight: 700, margin: 0 }}>Maintenance Planning & Logistics</h1>
          </div>
          <p style={{ margin: '0.35rem 0 0', color: 'var(--text-muted)', fontSize: '0.875rem' }}>
            Check available spare parts, warehouse shelf locations, and which technicians are on duty today.
          </p>
        </div>

        <button
          type="button"
          className="btn btn-secondary"
          onClick={loadData}
          disabled={isLoadingInventory || isLoadingShifts}
          style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', padding: '0.5rem 1rem' }}
        >
          <RefreshCw size={15} className={isLoadingInventory || isLoadingShifts ? 'spin' : ''} />
          Refresh Logistics
        </button>
      </div>

      {/* Summary KPI Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: '1rem' }}>
        <div style={{ backgroundColor: 'var(--bg-surface)', padding: '1.25rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-subtle)' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <span style={{ fontSize: '0.8125rem', fontWeight: 600, color: 'var(--text-muted)' }}>WAREHOUSE INVENTORY</span>
            <PackageCheck size={18} style={{ color: 'var(--primary)' }} />
          </div>
          <div style={{ marginTop: '0.5rem', display: 'flex', alignItems: 'baseline', gap: '0.5rem' }}>
            <span style={{ fontSize: '1.75rem', fontWeight: 700 }}>{totalPartsCount}</span>
            <span style={{ fontSize: '0.8125rem', color: 'var(--text-muted)' }}>units ({inventory.length} SKUs)</span>
          </div>
        </div>

        <div style={{ backgroundColor: 'var(--bg-surface)', padding: '1.25rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-subtle)' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <span style={{ fontSize: '0.8125rem', fontWeight: 600, color: 'var(--text-muted)' }}>INVENTORY SHORTAGES</span>
            <AlertTriangle size={18} style={{ color: shortageCount > 0 ? 'var(--warning)' : 'var(--success)' }} />
          </div>
          <div style={{ marginTop: '0.5rem', display: 'flex', alignItems: 'baseline', gap: '0.5rem' }}>
            <span style={{ fontSize: '1.75rem', fontWeight: 700, color: shortageCount > 0 ? 'var(--warning)' : 'var(--success)' }}>
              {shortageCount}
            </span>
            <span style={{ fontSize: '0.8125rem', color: 'var(--text-muted)' }}>SKUs below threshold</span>
          </div>
        </div>

        <div style={{ backgroundColor: 'var(--bg-surface)', padding: '1.25rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-subtle)' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <span style={{ fontSize: '0.8125rem', fontWeight: 600, color: 'var(--text-muted)' }}>HANGAR SHIFT WORKFORCE</span>
            <Users size={18} style={{ color: 'var(--primary)' }} />
          </div>
          <div style={{ marginTop: '0.5rem', display: 'flex', alignItems: 'baseline', gap: '0.5rem' }}>
            <span style={{ fontSize: '1.75rem', fontWeight: 700, color: 'var(--success)' }}>{onDutyTechs}</span>
            <span style={{ fontSize: '0.8125rem', color: 'var(--text-muted)' }}>on duty / {schedules.length} total rostered</span>
          </div>
        </div>
      </div>

      {error && <ErrorState message={error} onRetry={loadData} />}

      {/* Navigation Tabs */}
      <div style={{ borderBottom: '1px solid var(--border-subtle)', display: 'flex', gap: '1rem' }}>
        <button
          type="button"
          onClick={() => setActiveTab('inventory')}
          style={{
            padding: '0.75rem 0.5rem',
            background: 'none',
            border: 'none',
            borderBottom: activeTab === 'inventory' ? '2px solid var(--primary)' : '2px solid transparent',
            color: activeTab === 'inventory' ? 'var(--primary)' : 'var(--text-muted)',
            fontWeight: activeTab === 'inventory' ? 600 : 500,
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: '0.5rem',
          }}
        >
          <Boxes size={16} />
          Warehouse Parts Inventory ({inventory.length})
        </button>

        <button
          type="button"
          onClick={() => setActiveTab('shifts')}
          style={{
            padding: '0.75rem 0.5rem',
            background: 'none',
            border: 'none',
            borderBottom: activeTab === 'shifts' ? '2px solid var(--primary)' : '2px solid transparent',
            color: activeTab === 'shifts' ? 'var(--primary)' : 'var(--text-muted)',
            fontWeight: activeTab === 'shifts' ? 600 : 500,
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: '0.5rem',
          }}
        >
          <Clock size={16} />
          Technician Shift Rosters ({schedules.length})
        </button>

        <button
          type="button"
          onClick={() => setActiveTab('readiness')}
          style={{
            padding: '0.75rem 0.5rem',
            background: 'none',
            border: 'none',
            borderBottom: activeTab === 'readiness' ? '2px solid var(--primary)' : '2px solid transparent',
            color: activeTab === 'readiness' ? 'var(--primary)' : 'var(--text-muted)',
            fontWeight: activeTab === 'readiness' ? 600 : 500,
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: '0.5rem',
          }}
        >
          <ShieldCheck size={16} />
          Work Order Readiness Checker
        </button>
      </div>

      {/* Tab 1: Warehouse Inventory */}
      {activeTab === 'inventory' && (
        <div style={{ backgroundColor: 'var(--bg-surface)', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-subtle)', padding: '1.25rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem', flexWrap: 'wrap', gap: '0.75rem' }}>
            <div style={{ position: 'relative', width: '320px', maxWidth: '100%' }}>
              <Search size={16} style={{ position: 'absolute', left: '0.75rem', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
              <input
                type="text"
                placeholder="Search part #, name, or bin..."
                value={inventorySearch}
                onChange={(e) => setInventorySearch(e.target.value)}
                style={{
                  width: '100%',
                  padding: '0.5rem 0.75rem 0.5rem 2.25rem',
                  borderRadius: 'var(--radius-sm)',
                  border: '1px solid var(--border-subtle)',
                  backgroundColor: 'var(--bg-canvas)',
                  color: 'var(--text-primary)',
                  fontSize: '0.875rem',
                }}
              />
            </div>
            <div style={{ fontSize: '0.8125rem', color: 'var(--text-muted)' }}>
              Showing {filteredInventory.length} of {inventory.length} parts
            </div>
          </div>

          {isLoadingInventory ? (
            <LoadingState message="Fetching warehouse catalog..." />
          ) : (
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.875rem' }}>
                <thead>
                  <tr style={{ borderBottom: '1px solid var(--border-subtle)', color: 'var(--text-muted)', fontSize: '0.75rem', textTransform: 'uppercase' }}>
                    <th style={{ padding: '0.75rem 1rem' }}>Part Number</th>
                    <th style={{ padding: '0.75rem 1rem' }}>Item Description</th>
                    <th style={{ padding: '0.75rem 1rem' }}>Category</th>
                    <th style={{ padding: '0.75rem 1rem' }}>Warehouse Bin</th>
                    <th style={{ padding: '0.75rem 1rem' }}>Available Stock</th>
                    <th style={{ padding: '0.75rem 1rem' }}>Unit Cost</th>
                    <th style={{ padding: '0.75rem 1rem' }}>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredInventory.map((item) => {
                    const isLow = item.stock_qty <= item.min_required;
                    return (
                      <tr key={item.part_number} style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                        <td style={{ padding: '0.75rem 1rem', fontFamily: 'monospace', fontWeight: 600 }}>{item.part_number}</td>
                        <td style={{ padding: '0.75rem 1rem', fontWeight: 500 }}>{item.name}</td>
                        <td style={{ padding: '0.75rem 1rem', color: 'var(--text-muted)' }}>{item.category}</td>
                        <td style={{ padding: '0.75rem 1rem' }}>
                          <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.35rem', color: 'var(--text-primary)' }}>
                            <MapPin size={13} style={{ color: 'var(--primary)' }} />
                            {item.warehouse_bin}
                          </span>
                        </td>
                        <td style={{ padding: '0.75rem 1rem', fontWeight: 600 }}>
                          {item.stock_qty} <span style={{ color: 'var(--text-muted)', fontWeight: 400, fontSize: '0.75rem' }}>(min {item.min_required})</span>
                        </td>
                        <td style={{ padding: '0.75rem 1rem', color: 'var(--text-muted)' }}>
                          ${item.unit_cost_usd.toLocaleString()}
                        </td>
                        <td style={{ padding: '0.75rem 1rem' }}>
                          <span
                            style={{
                              padding: '0.2rem 0.5rem',
                              borderRadius: 'var(--radius-sm)',
                              fontSize: '0.75rem',
                              fontWeight: 600,
                              backgroundColor: isLow ? 'rgba(217, 119, 6, 0.15)' : 'rgba(34, 197, 94, 0.15)',
                              color: isLow ? 'var(--warning)' : 'var(--success)',
                            }}
                          >
                            {isLow ? 'LOW STOCK' : 'IN STOCK'}
                          </span>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Tab 2: Technician Shift Rosters */}
      {activeTab === 'shifts' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          {isLoadingShifts ? (
            <LoadingState message="Loading technician shifts..." />
          ) : (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(360px, 1fr))', gap: '1rem' }}>
              {schedules.map((tech) => (
                <div
                  key={tech.technician_id}
                  style={{
                    backgroundColor: 'var(--bg-surface)',
                    borderRadius: 'var(--radius-md)',
                    border: '1px solid var(--border-subtle)',
                    padding: '1.25rem',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '0.75rem',
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                    <div>
                      <h3 style={{ margin: 0, fontSize: '1.0625rem', fontWeight: 600 }}>{tech.name}</h3>
                      <span style={{ fontSize: '0.8125rem', color: 'var(--text-muted)' }}>Shift: {tech.shift_name.toUpperCase()} ({tech.shift_hours})</span>
                    </div>
                    <span
                      style={{
                        padding: '0.2rem 0.5rem',
                        borderRadius: 'var(--radius-sm)',
                        fontSize: '0.75rem',
                        fontWeight: 600,
                        backgroundColor: tech.is_on_duty ? 'rgba(34, 197, 94, 0.15)' : 'rgba(148, 163, 184, 0.15)',
                        color: tech.is_on_duty ? 'var(--success)' : 'var(--text-muted)',
                      }}
                    >
                      {tech.is_on_duty ? 'ON DUTY' : 'OFF DUTY'}
                    </span>
                  </div>

                  <div>
                    <span style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase' }}>
                      Certified Qualifications:
                    </span>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.35rem', marginTop: '0.35rem' }}>
                      {tech.qualifications.map((q) => (
                        <span
                          key={q}
                          style={{
                            backgroundColor: 'var(--bg-canvas)',
                            border: '1px solid var(--border-subtle)',
                            padding: '0.15rem 0.45rem',
                            borderRadius: 'var(--radius-sm)',
                            fontSize: '0.75rem',
                          }}
                        >
                          {q}
                        </span>
                      ))}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Tab 3: Work Order Readiness Checker */}
      {activeTab === 'readiness' && (
        <div style={{ backgroundColor: 'var(--bg-surface)', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-subtle)', padding: '1.5rem', display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
          <div>
            <h2 style={{ fontSize: '1.125rem', fontWeight: 600, margin: 0 }}>Check Work Order Planning Readiness</h2>
            <p style={{ margin: '0.25rem 0 0', color: 'var(--text-muted)', fontSize: '0.875rem' }}>
              Verifies warehouse part availability in storage bins and technician certification shift status.
            </p>
          </div>

          <form onSubmit={handleCheckReadiness} style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
            <input
              type="text"
              placeholder="Paste Work Order UUID (e.g. 550e8400-e29b-41d4-a716-446655440000)..."
              value={testWoId}
              onChange={(e) => setTestWoId(e.target.value)}
              style={{
                flex: 1,
                minWidth: '280px',
                padding: '0.5rem 0.75rem',
                borderRadius: 'var(--radius-sm)',
                border: '1px solid var(--border-subtle)',
                backgroundColor: 'var(--bg-canvas)',
                color: 'var(--text-primary)',
                fontSize: '0.875rem',
              }}
            />
            <button
              type="submit"
              className="btn btn-primary"
              disabled={isLoadingReadiness || !testWoId.trim()}
              style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', padding: '0.5rem 1.25rem' }}
            >
              <Wrench size={16} />
              {isLoadingReadiness ? 'Evaluating...' : 'Evaluate Readiness'}
            </button>
          </form>

          {readinessError && <ErrorState message={readinessError} />}

          {readiness && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem', marginTop: '0.5rem' }}>
              {/* Readiness Banner */}
              <div
                style={{
                  padding: '1rem',
                  borderRadius: 'var(--radius-md)',
                  backgroundColor: readiness.is_planning_ready ? 'rgba(34, 197, 94, 0.1)' : 'rgba(239, 68, 68, 0.1)',
                  border: `1px solid ${readiness.is_planning_ready ? 'var(--success)' : 'var(--danger)'}`,
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.75rem',
                }}
              >
                {readiness.is_planning_ready ? (
                  <CheckCircle2 size={24} style={{ color: 'var(--success)', flexShrink: 0 }} />
                ) : (
                  <AlertTriangle size={24} style={{ color: 'var(--danger)', flexShrink: 0 }} />
                )}
                <div>
                  <div style={{ fontWeight: 600, fontSize: '0.9375rem', color: readiness.is_planning_ready ? 'var(--success)' : 'var(--danger)' }}>
                    {readiness.readiness_summary}
                  </div>
                  <div style={{ fontSize: '0.8125rem', color: 'var(--text-muted)' }}>
                    Status: {readiness.status.toUpperCase()} | {readiness.is_planning_ready ? 'All required parts in stock and qualified technician available.' : 'Action required prior to scheduling maintenance release.'}
                  </div>
                </div>
              </div>

              {/* Blockers list */}
              {readiness.blockers.length > 0 && (
                <div style={{ backgroundColor: 'var(--bg-canvas)', padding: '1rem', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)' }}>
                  <div style={{ fontWeight: 600, fontSize: '0.8125rem', color: 'var(--danger)', marginBottom: '0.35rem' }}>
                    UNRESOLVED LOGISTICS BLOCKERS:
                  </div>
                  <ul style={{ margin: 0, paddingLeft: '1.25rem', fontSize: '0.8125rem', color: 'var(--text-muted)' }}>
                    {readiness.blockers.map((b, idx) => (
                      <li key={idx} style={{ marginTop: '0.2rem' }}>{b}</li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Parts Checklist */}
              <div>
                <h3 style={{ fontSize: '0.9375rem', fontWeight: 600, marginBottom: '0.5rem' }}>AMM Task Parts Availability</h3>
                <div style={{ overflowX: 'auto' }}>
                  <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.8125rem', textAlign: 'left' }}>
                    <thead>
                      <tr style={{ borderBottom: '1px solid var(--border-subtle)', color: 'var(--text-muted)' }}>
                        <th style={{ padding: '0.5rem 0.75rem' }}>Task Code</th>
                        <th style={{ padding: '0.5rem 0.75rem' }}>Part #</th>
                        <th style={{ padding: '0.5rem 0.75rem' }}>Part Name</th>
                        <th style={{ padding: '0.5rem 0.75rem' }}>Bin Location</th>
                        <th style={{ padding: '0.5rem 0.75rem' }}>Stock</th>
                        <th style={{ padding: '0.5rem 0.75rem' }}>Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {readiness.parts_checklist.map((p, idx) => (
                        <tr key={idx} style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                          <td style={{ padding: '0.5rem 0.75rem', fontWeight: 600 }}>{p.task_code}</td>
                          <td style={{ padding: '0.5rem 0.75rem', fontFamily: 'monospace' }}>{p.part_number}</td>
                          <td style={{ padding: '0.5rem 0.75rem' }}>{p.name}</td>
                          <td style={{ padding: '0.5rem 0.75rem' }}>{p.warehouse_bin}</td>
                          <td style={{ padding: '0.5rem 0.75rem', fontWeight: 600 }}>{p.available_stock} units</td>
                          <td style={{ padding: '0.5rem 0.75rem' }}>
                            <span
                              style={{
                                padding: '0.15rem 0.45rem',
                                borderRadius: 'var(--radius-sm)',
                                fontSize: '0.75rem',
                                fontWeight: 600,
                                backgroundColor: p.in_stock ? 'rgba(34, 197, 94, 0.15)' : 'rgba(239, 68, 68, 0.15)',
                                color: p.in_stock ? 'var(--success)' : 'var(--danger)',
                              }}
                            >
                              {p.status}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

