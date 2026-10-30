import React, { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import { predictionsApi, ingestionApi } from '../services/api';
import { Observation } from '../services/types';
import { LoadingState } from '../components/common/LoadingState';
import { Thermometer, Gauge, Zap, RefreshCw } from 'lucide-react';
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
} from 'recharts';

export const SensorAnalyticsPage: React.FC = () => {
  const { activeTenant } = useAuth();
  const [machines, setMachines] = useState<any[]>([]);
  const [selectedMachineId, setSelectedMachineId] = useState<string>('');
  const [observations, setObservations] = useState<Observation[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [selectedChannel, setSelectedChannel] = useState<'temperatures' | 'pressures' | 'speeds' | 'ratios'>('temperatures');

  useEffect(() => {
    if (!activeTenant) return;
    const fetchList = async () => {
      try {
        const res = await predictionsApi.getMaintenancePriorities(activeTenant.id, { limit: 50 });
        setMachines(res.items || []);
        if (res.items.length > 0) {
          setSelectedMachineId(res.items[0].machine_id);
        }
      } catch (err) {
        // handled
      }
    };
    fetchList();
  }, [activeTenant]);

  useEffect(() => {
    if (!activeTenant || !selectedMachineId) return;
    const fetchObs = async () => {
      setIsLoading(true);
      try {
        const res = await ingestionApi.getObservations(activeTenant.id, selectedMachineId, { limit: 120 });
        setObservations(res.items || []);
      } catch (err) {
        setObservations([]);
      } finally {
        setIsLoading(false);
      }
    };
    fetchObs();
  }, [activeTenant, selectedMachineId]);

  const chartData = observations.map((o) => {
    const s = o.sensors || [];
    return {
      cycle: o.cycle,
      // Temps
      s2_lpc: s[1] ? Math.round(s[1] * 100) / 100 : null,
      s3_hpc: s[2] ? Math.round(s[2] * 100) / 100 : null,
      s4_lpt: s[3] ? Math.round(s[3] * 100) / 100 : null,
      // Pressures
      s7_ps30: s[6] ? Math.round(s[6] * 100) / 100 : null,
      s11_stat: s[10] ? Math.round(s[10] * 100) / 100 : null,
      s12_ratio: s[11] ? Math.round(s[11] * 1000) / 1000 : null,
      // Speeds
      s8_n1: s[7] ? Math.round(s[7] * 10) / 10 : null,
      s9_n2: s[8] ? Math.round(s[8] * 10) / 10 : null,
      s14_n1c: s[13] ? Math.round(s[13] * 10) / 10 : null,
      // Ratios
      s15_bpr: s[14] ? Math.round(s[14] * 1000) / 1000 : null,
      s20_bflow: s[19] ? Math.round(s[19] * 100) / 100 : null,
      s21_tflow: s[20] ? Math.round(s[20] * 100) / 100 : null,
    };
  });

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '0.75rem' }}>
        <div>
          <h1 style={{ fontSize: '1.5rem', fontWeight: 700, margin: 0, color: 'var(--text-primary)' }}>
            Sensor Degradation Analytics
          </h1>
          <p style={{ fontSize: '0.875rem', color: 'var(--text-secondary)', marginTop: '0.25rem' }}>
            Multi-channel physical telemetry inspection across operating cycles.
          </p>
        </div>

        {/* Machine Selector */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <span style={{ fontSize: '0.8125rem', color: 'var(--text-muted)' }}>Machine Asset:</span>
          <select
            value={selectedMachineId}
            onChange={(e) => setSelectedMachineId(e.target.value)}
            style={{
              padding: '0.4rem 0.6rem',
              fontSize: '0.8125rem',
              borderRadius: '6px',
              border: '1px solid var(--border-subtle)',
              backgroundColor: '#ffffff',
            }}
          >
            {machines.map((m) => (
              <option key={m.machine_id} value={m.machine_id}>
                {m.asset_code}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Channel Group Tabs */}
      <div className="card" style={{ padding: '1rem', backgroundColor: '#ffffff' }}>
        <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
          <button
            type="button"
            onClick={() => setSelectedChannel('temperatures')}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '0.35rem',
              padding: '0.4rem 0.8rem',
              borderRadius: '6px',
              fontSize: '0.8125rem',
              fontWeight: selectedChannel === 'temperatures' ? 600 : 500,
              backgroundColor: selectedChannel === 'temperatures' ? '#2563eb' : 'var(--bg-canvas)',
              color: selectedChannel === 'temperatures' ? '#ffffff' : 'var(--text-secondary)',
              border: '1px solid var(--border-subtle)',
              cursor: 'pointer',
            }}
          >
            <Thermometer size={14} />
            Temperatures (°R)
          </button>

          <button
            type="button"
            onClick={() => setSelectedChannel('pressures')}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '0.35rem',
              padding: '0.4rem 0.8rem',
              borderRadius: '6px',
              fontSize: '0.8125rem',
              fontWeight: selectedChannel === 'pressures' ? 600 : 500,
              backgroundColor: selectedChannel === 'pressures' ? '#2563eb' : 'var(--bg-canvas)',
              color: selectedChannel === 'pressures' ? '#ffffff' : 'var(--text-secondary)',
              border: '1px solid var(--border-subtle)',
              cursor: 'pointer',
            }}
          >
            <Gauge size={14} />
            Pressures (psia)
          </button>

          <button
            type="button"
            onClick={() => setSelectedChannel('speeds')}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '0.35rem',
              padding: '0.4rem 0.8rem',
              borderRadius: '6px',
              fontSize: '0.8125rem',
              fontWeight: selectedChannel === 'speeds' ? 600 : 500,
              backgroundColor: selectedChannel === 'speeds' ? '#2563eb' : 'var(--bg-canvas)',
              color: selectedChannel === 'speeds' ? '#ffffff' : 'var(--text-secondary)',
              border: '1px solid var(--border-subtle)',
              cursor: 'pointer',
            }}
          >
            <RefreshCw size={14} />
            Rotational Speeds (rpm)
          </button>

          <button
            type="button"
            onClick={() => setSelectedChannel('ratios')}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '0.35rem',
              padding: '0.4rem 0.8rem',
              borderRadius: '6px',
              fontSize: '0.8125rem',
              fontWeight: selectedChannel === 'ratios' ? 600 : 500,
              backgroundColor: selectedChannel === 'ratios' ? '#2563eb' : 'var(--bg-canvas)',
              color: selectedChannel === 'ratios' ? '#ffffff' : 'var(--text-secondary)',
              border: '1px solid var(--border-subtle)',
              cursor: 'pointer',
            }}
          >
            <Zap size={14} />
            Flow &amp; Bleed Ratios
          </button>
        </div>
      </div>

      {/* Chart Canvas */}
      <div className="card" style={{ padding: '1.5rem', backgroundColor: '#ffffff' }}>
        {isLoading ? (
          <LoadingState message="Fetching trajectory points..." />
        ) : chartData.length === 0 ? (
          <div style={{ padding: '3rem', textAlign: 'center', color: 'var(--text-muted)' }}>No telemetry available.</div>
        ) : (
          <div style={{ width: '100%', height: '360px' }}>
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={chartData} margin={{ top: 10, right: 20, left: 0, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                <XAxis dataKey="cycle" label={{ value: 'Operating Flight Cycle', position: 'insideBottom', offset: -5, fontSize: 11 }} tick={{ fontSize: 10 }} />
                <YAxis tick={{ fontSize: 10 }} />
                <Tooltip contentStyle={{ fontSize: '0.75rem', borderRadius: '4px' }} />
                <Legend wrapperStyle={{ fontSize: '0.75rem', paddingTop: '10px' }} />

                {selectedChannel === 'temperatures' && (
                  <>
                    <Line type="monotone" dataKey="s2_lpc" stroke="#2563eb" strokeWidth={2} name="Sensor 02: LPC Outlet Temp (°R)" dot={false} />
                    <Line type="monotone" dataKey="s3_hpc" stroke="#dc2626" strokeWidth={2} name="Sensor 03: HPC Outlet Temp (°R)" dot={false} />
                    <Line type="monotone" dataKey="s4_lpt" stroke="#d97706" strokeWidth={2} name="Sensor 04: LPT Outlet Temp (°R)" dot={false} />
                  </>
                )}

                {selectedChannel === 'pressures' && (
                  <>
                    <Line type="monotone" dataKey="s7_ps30" stroke="#059669" strokeWidth={2} name="Sensor 07: Total Pressure HPC (psia)" dot={false} />
                    <Line type="monotone" dataKey="s11_stat" stroke="#7c3aed" strokeWidth={2} name="Sensor 11: Static Pressure Ps30 (psia)" dot={false} />
                    <Line type="monotone" dataKey="s12_ratio" stroke="#0891b2" strokeWidth={2} name="Sensor 12: Fuel Flow Ratio (pps/psia)" dot={false} />
                  </>
                )}

                {selectedChannel === 'speeds' && (
                  <>
                    <Line type="monotone" dataKey="s8_n1" stroke="#2563eb" strokeWidth={2} name="Sensor 08: Physical Fan Speed N1 (rpm)" dot={false} />
                    <Line type="monotone" dataKey="s9_n2" stroke="#dc2626" strokeWidth={2} name="Sensor 09: Physical Core Speed N2 (rpm)" dot={false} />
                    <Line type="monotone" dataKey="s14_n1c" stroke="#d97706" strokeWidth={2} name="Sensor 14: Corrected Fan Speed (rpm)" dot={false} />
                  </>
                )}

                {selectedChannel === 'ratios' && (
                  <>
                    <Line type="monotone" dataKey="s15_bpr" stroke="#4f46e5" strokeWidth={2} name="Sensor 15: Bypass Ratio" dot={false} />
                    <Line type="monotone" dataKey="s20_bflow" stroke="#0891b2" strokeWidth={2} name="Sensor 20: HPT Bleed Flow (lbm/s)" dot={false} />
                    <Line type="monotone" dataKey="s21_tflow" stroke="#059669" strokeWidth={2} name="Sensor 21: LPT Bleed Flow (lbm/s)" dot={false} />
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
