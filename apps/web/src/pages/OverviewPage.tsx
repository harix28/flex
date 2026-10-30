import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { useAuth } from '../context/AuthContext';
import { predictionsApi, ingestionApi } from '../services/api';
import {
  MaintenancePrioritiesResponse,
  PriorityBand,
  Observation,
} from '../services/types';
import { PriorityBadge } from '../components/common/Badge';
import { LoadingState } from '../components/common/LoadingState';
import {
  ShieldAlert,
  AlertTriangle,
  Clock,
  CheckCircle,
  AlertCircle,
  RefreshCw,
  Search,
  Activity,
  Thermometer,
  Gauge,
  Zap,
  Layers,
} from 'lucide-react';
import {
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
} from 'recharts';

interface OverviewPageProps {
  onSelectMachine: (machineId: string) => void;
  onNavigateToRegistry?: () => void;
}

export const OverviewPage: React.FC<OverviewPageProps> = ({
  onSelectMachine,
}) => {
  const { activeTenant } = useAuth();
  const [data, setData] = useState<MaintenancePrioritiesResponse | null>(null);
  const [selectedBand, setSelectedBand] = useState<PriorityBand | 'all'>('all');
  const [typeFilter, setTypeFilter] = useState<'all' | 'cmapss_engine'>('all');
  const [tableSearch, setTableSearch] = useState('');
  const [currentPage, setCurrentPage] = useState(1);
  const pageSize = 10;
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<{ message: string; requestId?: string } | null>(null);

  // Section E: Sensor Trends state
  const [selectedSensorMachineId, setSelectedSensorMachineId] = useState<string>('');
  const [sensorMetricCategory, setSensorMetricCategory] = useState<'temperature' | 'vibration' | 'rpm' | 'current'>('temperature');
  const [sensorTimeRange, setSensorTimeRange] = useState<'30' | '60' | 'all'>('60');
  const [sensorObservations, setSensorObservations] = useState<Observation[]>([]);
  const [isLoadingSensors, setIsLoadingSensors] = useState(false);

  const fetchPriorities = useCallback(async () => {
    if (!activeTenant) return;
    setIsLoading(true);
    setError(null);

    try {
      const res = await predictionsApi.getMaintenancePriorities(activeTenant.id, {
        limit: 100,
        offset: 0,
      });
      setData(res);
      if (res.items.length > 0 && !selectedSensorMachineId) {
        setSelectedSensorMachineId(res.items[0].machine_id);
      }
    } catch (err: any) {
      setError({
        message: err.message || 'Failed to fetch fleet maintenance priorities',
        requestId: err.requestId,
      });
    } finally {
      setIsLoading(false);
    }
  }, [activeTenant, selectedSensorMachineId]);

  useEffect(() => {
    fetchPriorities();
  }, [fetchPriorities]);

  // Fetch sensor readings for Section E
  useEffect(() => {
    if (!activeTenant || !selectedSensorMachineId) return;

    let isCancelled = false;
    const fetchTelemetry = async () => {
      setIsLoadingSensors(true);
      try {
        const limitCount = sensorTimeRange === '30' ? 30 : sensorTimeRange === '60' ? 60 : 150;
        const res = await ingestionApi.getObservations(activeTenant.id, selectedSensorMachineId, {
          limit: limitCount,
        });
        if (!isCancelled) {
          setSensorObservations(res.items || []);
        }
      } catch (err) {
        if (!isCancelled) {
          setSensorObservations([]);
        }
      } finally {
        if (!isCancelled) {
          setIsLoadingSensors(false);
        }
      }
    };

    fetchTelemetry();
    return () => {
      isCancelled = true;
    };
  }, [activeTenant, selectedSensorMachineId, sensorTimeRange]);

  const summary = data?.summary || {
    urgent: 0,
    high: 0,
    medium: 0,
    low: 0,
    outdated: 0,
    unknown: 0,
  };

  const totalMachines = data?.total ?? (data?.items?.length || 0);
  const healthyCount = summary.low;
  const warningCount = summary.medium;
  const criticalCount = summary.urgent + summary.high;
  const requiringMaintenanceCount = summary.urgent;

  // Donut chart data for Section A
  const donutData = useMemo(() => {
    return [
      { name: 'Healthy', value: healthyCount, color: '#16a34a' },
      { name: 'Warning', value: warningCount, color: '#d97706' },
      { name: 'Critical', value: criticalCount, color: '#dc2626' },
    ];
  }, [healthyCount, warningCount, criticalCount]);

  const totalEvaluated = healthyCount + warningCount + criticalCount || 1;
  const healthyPct = Math.round((healthyCount / totalEvaluated) * 100);
  const warningPct = Math.round((warningCount / totalEvaluated) * 100);
  const criticalPct = Math.round((criticalCount / totalEvaluated) * 100);

  // Line chart data for Section B (Average RUL Distribution)
  const rulTrendData = useMemo(() => {
    if (!data?.items) return [];
    return data.items.slice(0, 25).map((m) => ({
      engine: m.asset_code.replace('NASA-FD001-TEST-', 'E-'),
      rul: m.rul_cycles !== null ? Math.round(m.rul_cycles * 10) / 10 : 0,
      cutoff: m.prediction_cutoff_cycle || 0,
    }));
  }, [data]);

  // Section C: Dynamic Alerts derived from fleet state
  const alertsList = useMemo(() => {
    if (!data?.items) return [];
    const alerts: Array<{
      id: string;
      machineId: string;
      assetCode: string;
      description: string;
      timestamp: string;
      severity: 'Critical' | 'Warning' | 'Info';
    }> = [];

    data.items.forEach((m) => {
      if (m.priority_band === 'urgent') {
        alerts.push({
          id: `alert-urg-${m.machine_id}`,
          machineId: m.machine_id,
          assetCode: m.asset_code,
          description: `Critical RUL threshold reached (${m.rul_cycles?.toFixed(1) ?? 'N/A'} cycles <= 15). Immediate maintenance inspection recommended.`,
          timestamp: `Cycle ${m.prediction_cutoff_cycle || 'current'}`,
          severity: 'Critical',
        });
      } else if (m.priority_band === 'high') {
        alerts.push({
          id: `alert-high-${m.machine_id}`,
          machineId: m.machine_id,
          assetCode: m.asset_code,
          description: `Elevated wear rate (${m.rul_cycles?.toFixed(1) ?? 'N/A'} cycles <= 35). Schedule maintenance inspection.`,
          timestamp: `Cycle ${m.prediction_cutoff_cycle || 'current'}`,
          severity: 'Warning',
        });
      } else if (m.is_outdated) {
        alerts.push({
          id: `alert-out-${m.machine_id}`,
          machineId: m.machine_id,
          assetCode: m.asset_code,
          description: `Telemetry ingested since last evaluation. Re-evaluation pending.`,
          timestamp: `Cycle ${m.latest_observation_cycle || 'current'}`,
          severity: 'Info',
        });
      }
    });

    return alerts.slice(0, 5);
  }, [data]);

  // Section D: Filtered & Paginated Machines
  const filteredMachines = useMemo(() => {
    if (!data?.items) return [];
    return data.items.filter((item) => {
      // Priority band filter
      if (selectedBand !== 'all') {
        if (selectedBand === 'urgent' && item.priority_band !== 'urgent') return false;
        if (selectedBand === 'high' && item.priority_band !== 'high') return false;
        if (selectedBand === 'medium' && item.priority_band !== 'medium') return false;
        if (selectedBand === 'low' && item.priority_band !== 'low') return false;
        if (selectedBand === 'unknown' && item.priority_band !== 'unknown' && item.priority_band) return false;
      }
      // Type filter
      if (typeFilter !== 'all' && item.machine_type !== typeFilter) return false;
      // Search filter
      if (tableSearch.trim()) {
        const q = tableSearch.toLowerCase();
        const code = item.asset_code.toLowerCase();
        const name = (item.machine_name || '').toLowerCase();
        if (!code.includes(q) && !name.includes(q)) return false;
      }
      return true;
    });
  }, [data, selectedBand, typeFilter, tableSearch]);

  const totalPages = Math.ceil(filteredMachines.length / pageSize) || 1;
  const paginatedMachines = useMemo(() => {
    const start = (currentPage - 1) * pageSize;
    return filteredMachines.slice(start, start + pageSize);
  }, [filteredMachines, currentPage, pageSize]);

  // Section E: Chart data formatting for sensors
  const sensorChartData = useMemo(() => {
    return sensorObservations.map((obs) => {
      const s = obs.sensors || [];
      return {
        cycle: obs.cycle,
        // Temperature: sensor_02 (LPC outlet temp °R), sensor_03 (HPC outlet temp °R)
        temp_lpc: s[1] ? Math.round(s[1] * 100) / 100 : null,
        temp_hpc: s[2] ? Math.round(s[2] * 100) / 100 : null,
        // Vibration / Pressure: sensor_04 (LPT outlet temp / dynamic pressure), sensor_11 (Ps30 Static pressure psia)
        press_hpc: s[10] ? Math.round(s[10] * 100) / 100 : null,
        press_lpt: s[3] ? Math.round(s[3] * 10) / 10 : null,
        // RPM: sensor_08 (Fan speed N1 rpm), sensor_09 (Core speed N2 rpm)
        rpm_fan: s[7] ? Math.round(s[7] * 10) / 10 : null,
        rpm_core: s[8] ? Math.round(s[8] * 10) / 10 : null,
        // Current / Flow: sensor_14 (Corrected fan speed), sensor_15 (Bypass ratio)
        ratio_flow: s[13] ? Math.round(s[13] * 10) / 10 : null,
        ratio_bypass: s[14] ? Math.round(s[14] * 1000) / 1000 : null,
      };
    });
  }, [sensorObservations]);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      {/* Page Title & Action Bar */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.75rem' }}>
        <div>
          <h1 style={{ fontSize: '1.5rem', fontWeight: 700, color: 'var(--text-primary)', margin: 0 }}>
            Fleet Maintenance Overview
          </h1>
          <p style={{ fontSize: '0.875rem', color: 'var(--text-secondary)', marginTop: '0.25rem' }}>
            Deterministic machine health ranking, remaining useful life predictions, and multi-channel sensor telemetry.
          </p>
        </div>
        <button
          type="button"
          className="btn btn-secondary"
          onClick={fetchPriorities}
          disabled={isLoading}
          style={{ fontSize: '0.8125rem' }}
        >
          <RefreshCw size={14} className={isLoading ? 'animate-spin' : ''} />
          <span>Refresh Fleet Status</span>
        </button>
      </div>

      {error && (
        <div style={{ padding: '0.75rem 1rem', borderRadius: '6px', backgroundColor: '#fef2f2', border: '1px solid #fecaca', color: '#991b1b', fontSize: '0.875rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <AlertCircle size={16} />
          <span>{error.message}</span>
        </div>
      )}

      {/* 5 KPI METRIC CARDS */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
          gap: '1rem',
        }}
      >
        {/* KPI 1: Total Machines */}
        <div className="card" style={{ padding: '1.25rem', backgroundColor: '#ffffff', borderLeft: '4px solid #3b82f6' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', color: '#1d4ed8' }}>
            <span style={{ fontSize: '0.75rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
              Total Machines
            </span>
            <Layers size={18} />
          </div>
          <div style={{ fontSize: '2rem', fontWeight: 700, marginTop: '0.5rem', color: 'var(--text-primary)', lineHeight: 1 }}>
            {totalMachines}
          </div>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.5rem' }}>
            Active monitored fleet assets
          </div>
        </div>

        {/* KPI 2: Healthy Machines */}
        <div className="card" style={{ padding: '1.25rem', backgroundColor: '#ffffff', borderLeft: '4px solid #16a34a' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', color: '#16a34a' }}>
            <span style={{ fontSize: '0.75rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
              Healthy Machines
            </span>
            <CheckCircle size={18} />
          </div>
          <div style={{ fontSize: '2rem', fontWeight: 700, marginTop: '0.5rem', color: '#16a34a', lineHeight: 1 }}>
            {healthyCount}
          </div>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.5rem' }}>
            RUL &gt; 75 operating cycles
          </div>
        </div>

        {/* KPI 3: Warning Machines */}
        <div className="card" style={{ padding: '1.25rem', backgroundColor: '#ffffff', borderLeft: '4px solid #d97706' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', color: '#d97706' }}>
            <span style={{ fontSize: '0.75rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
              Warning Machines
            </span>
            <Clock size={18} />
          </div>
          <div style={{ fontSize: '2rem', fontWeight: 700, marginTop: '0.5rem', color: '#d97706', lineHeight: 1 }}>
            {warningCount}
          </div>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.5rem' }}>
            35 &lt; RUL &le; 75 cycles
          </div>
        </div>

        {/* KPI 4: Critical Machines */}
        <div className="card" style={{ padding: '1.25rem', backgroundColor: '#ffffff', borderLeft: '4px solid #dc2626' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', color: '#dc2626' }}>
            <span style={{ fontSize: '0.75rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
              Critical Machines
            </span>
            <AlertTriangle size={18} />
          </div>
          <div style={{ fontSize: '2rem', fontWeight: 700, marginTop: '0.5rem', color: '#dc2626', lineHeight: 1 }}>
            {criticalCount}
          </div>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.5rem' }}>
            RUL &le; 35 operating cycles
          </div>
        </div>

        {/* KPI 5: Requiring Maintenance */}
        <div className="card" style={{ padding: '1.25rem', backgroundColor: '#ffffff', borderLeft: '4px solid #991b1b' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', color: '#991b1b' }}>
            <span style={{ fontSize: '0.75rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
              Requiring Maintenance
            </span>
            <ShieldAlert size={18} />
          </div>
          <div style={{ fontSize: '2rem', fontWeight: 700, marginTop: '0.5rem', color: '#991b1b', lineHeight: 1 }}>
            {requiringMaintenanceCount}
          </div>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.5rem' }}>
            Immediate inspection (&le; 15 cycles)
          </div>
        </div>
      </div>

      {/* SECTION A & SECTION B (HEALTH OVERVIEW DONUT + AVERAGE RUL LINE CHART) */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(420px, 1fr))', gap: '1.5rem' }}>
        {/* SECTION A: Machine Health Overview */}
        <div className="card" style={{ padding: '1.5rem', backgroundColor: '#ffffff' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
            <h2 style={{ fontSize: '1rem', fontWeight: 600, margin: 0, color: 'var(--text-primary)' }}>
              Machine Health Overview
            </h2>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Fleet Distribution</span>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-around', flexWrap: 'wrap', gap: '1rem' }}>
            {/* Donut Chart */}
            <div style={{ width: '180px', height: '180px' }}>
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={donutData}
                    cx="50%"
                    cy="50%"
                    innerRadius={55}
                    outerRadius={80}
                    paddingAngle={3}
                    dataKey="value"
                  >
                    {donutData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={entry.color} />
                    ))}
                  </Pie>
                  <Tooltip
                    formatter={(val: any) => [`${val} machines`, 'Count']}
                    contentStyle={{ fontSize: '0.75rem', borderRadius: '4px' }}
                  />
                </PieChart>
              </ResponsiveContainer>
            </div>

            {/* Breakdown Table */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', minWidth: '180px' }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: '0.8125rem' }}>
                <span style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <span style={{ width: 10, height: 10, borderRadius: '50%', backgroundColor: '#16a34a' }} />
                  Healthy
                </span>
                <span style={{ fontWeight: 600 }}>{healthyCount} ({healthyPct}%)</span>
              </div>

              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: '0.8125rem' }}>
                <span style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <span style={{ width: 10, height: 10, borderRadius: '50%', backgroundColor: '#d97706' }} />
                  Warning
                </span>
                <span style={{ fontWeight: 600 }}>{warningCount} ({warningPct}%)</span>
              </div>

              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: '0.8125rem' }}>
                <span style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <span style={{ width: 10, height: 10, borderRadius: '50%', backgroundColor: '#dc2626' }} />
                  Critical
                </span>
                <span style={{ fontWeight: 600 }}>{criticalCount} ({criticalPct}%)</span>
              </div>

              <div style={{ borderTop: '1px solid var(--border-subtle)', paddingTop: '0.5rem', display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                <span>Total Fleet Evaluated</span>
                <span>{totalMachines} Units</span>
              </div>
            </div>
          </div>
        </div>

        {/* SECTION B: Average RUL Trend */}
        <div className="card" style={{ padding: '1.5rem', backgroundColor: '#ffffff' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
            <h2 style={{ fontSize: '1rem', fontWeight: 600, margin: 0, color: 'var(--text-primary)' }}>
              Remaining Useful Life (RUL) Distribution
            </h2>
            <span style={{ fontSize: '0.75rem', color: '#2563eb', fontWeight: 600 }}>Unit: Operating Cycles</span>
          </div>

          <div style={{ width: '100%', height: '180px' }}>
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={rulTrendData} margin={{ top: 5, right: 10, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                <XAxis dataKey="engine" tick={{ fontSize: 10 }} />
                <YAxis tick={{ fontSize: 10 }} unit=" cyc" />
                <Tooltip
                  formatter={(val: any) => [`${val} cycles`, 'Estimated RUL']}
                  contentStyle={{ fontSize: '0.75rem', borderRadius: '4px' }}
                />
                <Line
                  type="monotone"
                  dataKey="rul"
                  stroke="#2563eb"
                  strokeWidth={2}
                  dot={{ r: 2, fill: '#2563eb' }}
                  name="Estimated RUL (cycles)"
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.5rem', textAlign: 'center' }}>
            Real-time causal trailing predictions across ranked engine assets (cycles remaining before maintenance)
          </div>
        </div>
      </div>

      {/* SECTION C: Recent Alerts */}
      <div className="card" style={{ padding: '1.25rem', backgroundColor: '#ffffff' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.875rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <AlertCircle size={18} color="#dc2626" />
            <h2 style={{ fontSize: '1rem', fontWeight: 600, margin: 0, color: 'var(--text-primary)' }}>
              Recent Alerts
            </h2>
          </div>
          <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Latest Fleet Incidents &amp; Thresholds</span>
        </div>

        {alertsList.length === 0 ? (
          <div style={{ padding: '1rem', textAlign: 'center', color: 'var(--text-muted)', fontSize: '0.8125rem' }}>
            No active severity alerts. All machine sensor trajectories are within expected degradation boundaries.
          </div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table className="table" style={{ width: '100%', fontSize: '0.8125rem', borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid var(--border-subtle)', textAlign: 'left', color: 'var(--text-secondary)' }}>
                  <th style={{ padding: '0.5rem' }}>Severity</th>
                  <th style={{ padding: '0.5rem' }}>Machine ID</th>
                  <th style={{ padding: '0.5rem' }}>Alert Description</th>
                  <th style={{ padding: '0.5rem' }}>Cutoff Timestamp</th>
                  <th style={{ padding: '0.5rem' }}>Action</th>
                </tr>
              </thead>
              <tbody>
                {alertsList.map((alert) => (
                  <tr key={alert.id} style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                    <td style={{ padding: '0.5rem' }}>
                      {alert.severity === 'Critical' && (
                        <span style={{ fontSize: '0.75rem', fontWeight: 600, padding: '0.2rem 0.5rem', borderRadius: '4px', backgroundColor: '#fee2e2', color: '#991b1b' }}>
                          Critical
                        </span>
                      )}
                      {alert.severity === 'Warning' && (
                        <span style={{ fontSize: '0.75rem', fontWeight: 600, padding: '0.2rem 0.5rem', borderRadius: '4px', backgroundColor: '#fef3c7', color: '#92400e' }}>
                          Warning
                        </span>
                      )}
                      {alert.severity === 'Info' && (
                        <span style={{ fontSize: '0.75rem', fontWeight: 600, padding: '0.2rem 0.5rem', borderRadius: '4px', backgroundColor: '#e0f2fe', color: '#0369a1' }}>
                          Info
                        </span>
                      )}
                    </td>
                    <td style={{ padding: '0.5rem', fontWeight: 600, fontFamily: 'monospace' }}>
                      {alert.assetCode}
                    </td>
                    <td style={{ padding: '0.5rem', color: 'var(--text-primary)' }}>
                      {alert.description}
                    </td>
                    <td style={{ padding: '0.5rem', color: 'var(--text-muted)', fontFamily: 'monospace' }}>
                      {alert.timestamp}
                    </td>
                    <td style={{ padding: '0.5rem' }}>
                      <button
                        type="button"
                        onClick={() => onSelectMachine(alert.machineId)}
                        style={{
                          background: 'none',
                          border: '1px solid var(--border-subtle)',
                          borderRadius: '4px',
                          padding: '0.25rem 0.5rem',
                          fontSize: '0.75rem',
                          cursor: 'pointer',
                        }}
                      >
                        Inspect
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* SECTION D: Machine Ranking Table */}
      <div className="card" style={{ padding: '1.25rem', backgroundColor: '#ffffff' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '0.75rem', marginBottom: '1rem' }}>
          <div>
            <h2 style={{ fontSize: '1.05rem', fontWeight: 600, margin: 0, color: 'var(--text-primary)' }}>
              Machine Ranking Table
            </h2>
            <div style={{ fontSize: '0.8125rem', color: 'var(--text-muted)', marginTop: '0.2rem' }}>
              Ranked by deterministic maintenance urgency and Remaining Useful Life (RUL).
            </div>
          </div>

          {/* Search & Filter Controls */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
            {/* Search Input */}
            <div style={{ position: 'relative' }}>
              <input
                type="text"
                placeholder="Search machine..."
                value={tableSearch}
                onChange={(e) => {
                  setTableSearch(e.target.value);
                  setCurrentPage(1);
                }}
                style={{
                  padding: '0.35rem 0.65rem 0.35rem 1.75rem',
                  fontSize: '0.8125rem',
                  borderRadius: '6px',
                  border: '1px solid var(--border-subtle)',
                  backgroundColor: 'var(--bg-canvas)',
                  width: '180px',
                }}
              />
              <Search size={14} style={{ position: 'absolute', left: '0.5rem', top: '0.55rem', color: 'var(--text-muted)' }} />
            </div>

            {/* Status Filter */}
            <select
              value={selectedBand}
              onChange={(e) => {
                setSelectedBand(e.target.value as any);
                setCurrentPage(1);
              }}
              style={{
                padding: '0.35rem 0.5rem',
                fontSize: '0.8125rem',
                borderRadius: '6px',
                border: '1px solid var(--border-subtle)',
                backgroundColor: 'var(--bg-canvas)',
              }}
            >
              <option value="all">All Priorities</option>
              <option value="urgent">Urgent</option>
              <option value="high">High</option>
              <option value="medium">Medium</option>
              <option value="low">Low</option>
            </select>

            {/* Machine Type Filter */}
            <select
              value={typeFilter}
              onChange={(e) => {
                setTypeFilter(e.target.value as any);
                setCurrentPage(1);
              }}
              style={{
                padding: '0.35rem 0.5rem',
                fontSize: '0.8125rem',
                borderRadius: '6px',
                border: '1px solid var(--border-subtle)',
                backgroundColor: 'var(--bg-canvas)',
              }}
            >
              <option value="all">All Machine Types</option>
              <option value="cmapss_engine">Turbofan Engine (C-MAPSS)</option>
            </select>
          </div>
        </div>

        {/* Table View */}
        {isLoading ? (
          <LoadingState message="Loading ranked machine status..." />
        ) : filteredMachines.length === 0 ? (
          <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-muted)' }}>
            No machines match the selected filter criteria.
          </div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table className="table" style={{ width: '100%', fontSize: '0.8125rem', borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid var(--border-subtle)', textAlign: 'left', color: 'var(--text-secondary)' }}>
                  <th style={{ padding: '0.5rem' }}>Rank</th>
                  <th style={{ padding: '0.5rem' }}>Machine ID</th>
                  <th style={{ padding: '0.5rem' }}>Machine Name</th>
                  <th style={{ padding: '0.5rem' }}>Machine Type</th>
                  <th style={{ padding: '0.5rem' }}>Health Status</th>
                  <th style={{ padding: '0.5rem' }}>Predicted RUL</th>
                  <th style={{ padding: '0.5rem' }}>Failure Risk</th>
                  <th style={{ padding: '0.5rem' }}>Maintenance Priority</th>
                  <th style={{ padding: '0.5rem' }}>Last Cutoff</th>
                  <th style={{ padding: '0.5rem', textAlign: 'right' }}>Action</th>
                </tr>
              </thead>
              <tbody>
                {paginatedMachines.map((m, idx) => {
                  const globalRank = (currentPage - 1) * pageSize + idx + 1;
                  const isCritical = m.priority_band === 'urgent' || m.priority_band === 'high';
                  const isWarning = m.priority_band === 'medium';
                  const healthStatus = isCritical ? 'Critical' : isWarning ? 'Warning' : 'Healthy';
                  const failureRisk =
                    m.priority_band === 'urgent'
                      ? 'Late Stage Degradation'
                      : m.priority_band === 'high'
                      ? 'Accelerated Wear'
                      : m.priority_band === 'medium'
                      ? 'Moderate Wear'
                      : 'Normal Operation';

                  return (
                    <tr
                      key={m.machine_id}
                      style={{ borderBottom: '1px solid var(--border-subtle)', cursor: 'pointer' }}
                      onClick={() => onSelectMachine(m.machine_id)}
                    >
                      <td style={{ padding: '0.5rem', fontWeight: 600, color: 'var(--text-muted)' }}>
                        #{globalRank}
                      </td>
                      <td style={{ padding: '0.5rem', fontWeight: 600, fontFamily: 'monospace', color: 'var(--text-primary)' }}>
                        {m.asset_code}
                      </td>
                      <td style={{ padding: '0.5rem', color: 'var(--text-secondary)' }}>
                        {m.machine_name || 'Turbofan Engine'}
                      </td>
                      <td style={{ padding: '0.5rem', color: 'var(--text-muted)' }}>
                        {m.machine_type}
                      </td>
                      <td style={{ padding: '0.5rem' }}>
                        {healthStatus === 'Critical' && (
                          <span style={{ fontSize: '0.75rem', fontWeight: 600, color: '#dc2626' }}>Critical</span>
                        )}
                        {healthStatus === 'Warning' && (
                          <span style={{ fontSize: '0.75rem', fontWeight: 600, color: '#d97706' }}>Warning</span>
                        )}
                        {healthStatus === 'Healthy' && (
                          <span style={{ fontSize: '0.75rem', fontWeight: 600, color: '#16a34a' }}>Healthy</span>
                        )}
                      </td>
                      <td style={{ padding: '0.5rem', fontWeight: 700, color: '#2563eb' }}>
                        {m.rul_cycles !== null ? `${m.rul_cycles.toFixed(1)} cycles` : '—'}
                      </td>
                      <td style={{ padding: '0.5rem', fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
                        {failureRisk}
                      </td>
                      <td style={{ padding: '0.5rem' }}>
                        <PriorityBadge priority={m.priority_band} />
                      </td>
                      <td style={{ padding: '0.5rem', fontFamily: 'monospace', color: 'var(--text-muted)' }}>
                        Cycle {m.prediction_cutoff_cycle || '—'}
                      </td>
                      <td style={{ padding: '0.5rem', textAlign: 'right' }}>
                        <button
                          type="button"
                          className="btn btn-secondary"
                          onClick={(e) => {
                            e.stopPropagation();
                            onSelectMachine(m.machine_id);
                          }}
                          style={{ fontSize: '0.75rem', padding: '0.2rem 0.5rem' }}
                        >
                          View &gt;
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        {/* Pagination Bar */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '1rem', fontSize: '0.8125rem' }}>
          <span style={{ color: 'var(--text-muted)' }}>
            Showing {paginatedMachines.length} of {filteredMachines.length} machines (Page {currentPage} of {totalPages})
          </span>
          <div style={{ display: 'flex', gap: '0.5rem' }}>
            <button
              type="button"
              className="btn btn-secondary"
              disabled={currentPage <= 1}
              onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
              style={{ fontSize: '0.75rem', padding: '0.25rem 0.6rem' }}
            >
              Previous
            </button>
            <button
              type="button"
              className="btn btn-secondary"
              disabled={currentPage >= totalPages}
              onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
              style={{ fontSize: '0.75rem', padding: '0.25rem 0.6rem' }}
            >
              Next
            </button>
          </div>
        </div>
      </div>

      {/* SECTION E: Sensor Trends */}
      <div className="card" style={{ padding: '1.5rem', backgroundColor: '#ffffff' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '0.75rem', marginBottom: '1rem' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <Activity size={18} color="#2563eb" />
              <h2 style={{ fontSize: '1.05rem', fontWeight: 600, margin: 0, color: 'var(--text-primary)' }}>
                Sensor Trends &amp; Telemetry
              </h2>
            </div>
            <div style={{ fontSize: '0.8125rem', color: 'var(--text-muted)', marginTop: '0.2rem' }}>
              Multi-channel physical telemetry inspection (Temperature, Vibration, RPM, Flow/Current).
            </div>
          </div>

          {/* Machine Selector & Time Range */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
            {/* Machine dropdown */}
            <select
              value={selectedSensorMachineId}
              onChange={(e) => setSelectedSensorMachineId(e.target.value)}
              style={{
                padding: '0.35rem 0.5rem',
                fontSize: '0.8125rem',
                borderRadius: '6px',
                border: '1px solid var(--border-subtle)',
                backgroundColor: 'var(--bg-canvas)',
              }}
            >
              {(data?.items || []).slice(0, 50).map((m) => (
                <option key={m.machine_id} value={m.machine_id}>
                  {m.asset_code} ({m.priority_band?.toUpperCase()})
                </option>
              ))}
            </select>

            {/* Time range selector */}
            <div style={{ display: 'flex', border: '1px solid var(--border-subtle)', borderRadius: '6px', overflow: 'hidden' }}>
              {(['30', '60', 'all'] as const).map((r) => (
                <button
                  key={r}
                  type="button"
                  onClick={() => setSensorTimeRange(r)}
                  style={{
                    border: 'none',
                    padding: '0.3rem 0.6rem',
                    fontSize: '0.75rem',
                    backgroundColor: sensorTimeRange === r ? '#2563eb' : 'var(--bg-canvas)',
                    color: sensorTimeRange === r ? '#ffffff' : 'var(--text-secondary)',
                    fontWeight: sensorTimeRange === r ? 600 : 400,
                    cursor: 'pointer',
                  }}
                >
                  {r === 'all' ? 'All Cycles' : `Last ${r}`}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Metric Category Tabs */}
        <div style={{ display: 'flex', gap: '0.5rem', borderBottom: '1px solid var(--border-subtle)', paddingBottom: '0.5rem', marginBottom: '1rem', flexWrap: 'wrap' }}>
          <button
            type="button"
            onClick={() => setSensorMetricCategory('temperature')}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '0.35rem',
              padding: '0.35rem 0.75rem',
              borderRadius: '4px',
              fontSize: '0.8125rem',
              fontWeight: sensorMetricCategory === 'temperature' ? 600 : 500,
              backgroundColor: sensorMetricCategory === 'temperature' ? '#eff6ff' : 'transparent',
              color: sensorMetricCategory === 'temperature' ? '#1d4ed8' : 'var(--text-secondary)',
              border: sensorMetricCategory === 'temperature' ? '1px solid #bfdbfe' : '1px solid transparent',
              cursor: 'pointer',
            }}
          >
            <Thermometer size={14} />
            Temperature (°R)
          </button>

          <button
            type="button"
            onClick={() => setSensorMetricCategory('vibration')}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '0.35rem',
              padding: '0.35rem 0.75rem',
              borderRadius: '4px',
              fontSize: '0.8125rem',
              fontWeight: sensorMetricCategory === 'vibration' ? 600 : 500,
              backgroundColor: sensorMetricCategory === 'vibration' ? '#eff6ff' : 'transparent',
              color: sensorMetricCategory === 'vibration' ? '#1d4ed8' : 'var(--text-secondary)',
              border: sensorMetricCategory === 'vibration' ? '1px solid #bfdbfe' : '1px solid transparent',
              cursor: 'pointer',
            }}
          >
            <Gauge size={14} />
            Vibration &amp; Pressure (psia)
          </button>

          <button
            type="button"
            onClick={() => setSensorMetricCategory('rpm')}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '0.35rem',
              padding: '0.35rem 0.75rem',
              borderRadius: '4px',
              fontSize: '0.8125rem',
              fontWeight: sensorMetricCategory === 'rpm' ? 600 : 500,
              backgroundColor: sensorMetricCategory === 'rpm' ? '#eff6ff' : 'transparent',
              color: sensorMetricCategory === 'rpm' ? '#1d4ed8' : 'var(--text-secondary)',
              border: sensorMetricCategory === 'rpm' ? '1px solid #bfdbfe' : '1px solid transparent',
              cursor: 'pointer',
            }}
          >
            <RefreshCw size={14} />
            RPM (Fan &amp; Core)
          </button>

          <button
            type="button"
            onClick={() => setSensorMetricCategory('current')}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '0.35rem',
              padding: '0.35rem 0.75rem',
              borderRadius: '4px',
              fontSize: '0.8125rem',
              fontWeight: sensorMetricCategory === 'current' ? 600 : 500,
              backgroundColor: sensorMetricCategory === 'current' ? '#eff6ff' : 'transparent',
              color: sensorMetricCategory === 'current' ? '#1d4ed8' : 'var(--text-secondary)',
              border: sensorMetricCategory === 'current' ? '1px solid #bfdbfe' : '1px solid transparent',
              cursor: 'pointer',
            }}
          >
            <Zap size={14} />
            Current &amp; Flow Ratios
          </button>
        </div>

        {/* Interactive Chart */}
        {isLoadingSensors ? (
          <div style={{ height: '220px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <LoadingState message="Loading historical sensor observations..." />
          </div>
        ) : sensorChartData.length === 0 ? (
          <div style={{ height: '220px', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-muted)' }}>
            No sensor telemetry available for the selected machine and time range.
          </div>
        ) : (
          <div style={{ width: '100%', height: '260px' }}>
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={sensorChartData} margin={{ top: 10, right: 20, left: 0, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                <XAxis dataKey="cycle" label={{ value: 'Operating Cycle', position: 'insideBottom', offset: -5, fontSize: 10 }} tick={{ fontSize: 10 }} />
                <YAxis tick={{ fontSize: 10 }} />
                <Tooltip contentStyle={{ fontSize: '0.75rem', borderRadius: '4px' }} />
                <Legend wrapperStyle={{ fontSize: '0.75rem', paddingTop: '10px' }} />

                {sensorMetricCategory === 'temperature' && (
                  <>
                    <Line type="monotone" dataKey="temp_lpc" stroke="#2563eb" strokeWidth={2} name="LPC Outlet Temp (°R)" dot={false} />
                    <Line type="monotone" dataKey="temp_hpc" stroke="#dc2626" strokeWidth={2} name="HPC Outlet Temp (°R)" dot={false} />
                  </>
                )}

                {sensorMetricCategory === 'vibration' && (
                  <>
                    <Line type="monotone" dataKey="press_hpc" stroke="#d97706" strokeWidth={2} name="Static Pressure Ps30 (psia)" dot={false} />
                    <Line type="monotone" dataKey="press_lpt" stroke="#7c3aed" strokeWidth={2} name="LPT Dynamic Pressure (psia)" dot={false} />
                  </>
                )}

                {sensorMetricCategory === 'rpm' && (
                  <>
                    <Line type="monotone" dataKey="rpm_fan" stroke="#059669" strokeWidth={2} name="Physical Fan Speed N1 (rpm)" dot={false} />
                    <Line type="monotone" dataKey="rpm_core" stroke="#2563eb" strokeWidth={2} name="Physical Core Speed N2 (rpm)" dot={false} />
                  </>
                )}

                {sensorMetricCategory === 'current' && (
                  <>
                    <Line type="monotone" dataKey="ratio_flow" stroke="#0891b2" strokeWidth={2} name="Corrected Fan Flow" dot={false} />
                    <Line type="monotone" dataKey="ratio_bypass" stroke="#4f46e5" strokeWidth={2} name="Bypass Ratio" dot={false} />
                  </>
                )}
              </LineChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>
    </div>
  );
};
