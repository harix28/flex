import React, { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import { predictionsApi, mlopsApi } from '../services/api';
import { LoadingState } from '../components/common/LoadingState';
import { Cpu } from 'lucide-react';
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
} from 'recharts';

export const FailurePredictionsPage: React.FC = () => {
  const { activeTenant } = useAuth();
  const [priorities, setPriorities] = useState<any[]>([]);
  const [modelInfo, setModelInfo] = useState<any>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    if (!activeTenant) return;
    const fetchAll = async () => {
      setIsLoading(true);
      try {
        const [pRes, mRes] = await Promise.all([
          predictionsApi.getMaintenancePriorities(activeTenant.id, { limit: 100 }),
          mlopsApi.getModelInfo(activeTenant.id).catch(() => null),
        ]);
        setPriorities(pRes.items || []);
        setModelInfo(mRes);
      } catch (err) {
        // handled
      } finally {
        setIsLoading(false);
      }
    };
    fetchAll();
  }, [activeTenant]);

  // Histogram buckets for RUL distribution
  const histogramData = [
    { range: '0-15 cyc (Urgent)', count: priorities.filter((p) => p.rul_cycles !== null && p.rul_cycles <= 15).length, fill: '#dc2626' },
    { range: '16-35 cyc (High)', count: priorities.filter((p) => p.rul_cycles !== null && p.rul_cycles > 15 && p.rul_cycles <= 35).length, fill: '#d97706' },
    { range: '36-75 cyc (Medium)', count: priorities.filter((p) => p.rul_cycles !== null && p.rul_cycles > 35 && p.rul_cycles <= 75).length, fill: '#2563eb' },
    { range: '76-120 cyc (Low)', count: priorities.filter((p) => p.rul_cycles !== null && p.rul_cycles > 75 && p.rul_cycles <= 120).length, fill: '#16a34a' },
    { range: '>120 cyc (Healthy)', count: priorities.filter((p) => p.rul_cycles !== null && p.rul_cycles > 120).length, fill: '#059669' },
  ];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      <div>
        <h1 style={{ fontSize: '1.5rem', fontWeight: 700, margin: 0, color: 'var(--text-primary)' }}>
          Failure Predictions &amp; RUL Distribution
        </h1>
        <p style={{ fontSize: '0.875rem', color: 'var(--text-secondary)', marginTop: '0.25rem' }}>
          Fleet-wide Remaining Useful Life (RUL) estimates, verified model artifacts, and evaluation metrics.
        </p>
      </div>

      {/* Model Spec Card */}
      <div className="card" style={{ padding: '1.25rem', backgroundColor: '#ffffff' }}>
        <h2 style={{ fontSize: '0.95rem', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '0.75rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <Cpu size={16} color="#2563eb" />
          Active Model Bundle Specification &amp; Evaluation Benchmarks
        </h2>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1rem', fontSize: '0.8125rem' }}>
          <div style={{ padding: '0.75rem', borderRadius: '6px', backgroundColor: 'var(--bg-canvas)' }}>
            <div style={{ color: 'var(--text-muted)' }}>Model Architecture</div>
            <div style={{ fontWeight: 600, color: 'var(--text-primary)', marginTop: '0.25rem' }}>
              {modelInfo?.model_name || 'HistGradientBoosting / Random Forest'}
            </div>
          </div>
          <div style={{ padding: '0.75rem', borderRadius: '6px', backgroundColor: 'var(--bg-canvas)' }}>
            <div style={{ color: 'var(--text-muted)' }}>Dataset &amp; Split</div>
            <div style={{ fontWeight: 600, color: 'var(--text-primary)', marginTop: '0.25rem' }}>
              NASA C-MAPSS FD001 (Test Split)
            </div>
          </div>
          <div style={{ padding: '0.75rem', borderRadius: '6px', backgroundColor: 'var(--bg-canvas)' }}>
            <div style={{ color: 'var(--text-muted)' }}>Feature Window (Schema)</div>
            <div style={{ fontWeight: 600, color: 'var(--text-primary)', marginTop: '0.25rem' }}>
              cmapss-trailing-v1 (W=30, 96 feats)
            </div>
          </div>
          <div style={{ padding: '0.75rem', borderRadius: '6px', backgroundColor: 'var(--bg-canvas)' }}>
            <div style={{ color: 'var(--text-muted)' }}>Target Variable &amp; Unit</div>
            <div style={{ fontWeight: 600, color: '#2563eb', marginTop: '0.25rem' }}>
              RUL (Operating Flight Cycles)
            </div>
          </div>
        </div>
      </div>

      {/* RUL Histogram Card */}
      <div className="card" style={{ padding: '1.5rem', backgroundColor: '#ffffff' }}>
        <h2 style={{ fontSize: '1rem', fontWeight: 600, marginBottom: '0.5rem', color: 'var(--text-primary)' }}>
          Fleet Remaining Useful Life (RUL) Distribution
        </h2>
        <div style={{ fontSize: '0.8125rem', color: 'var(--text-muted)', marginBottom: '1.25rem' }}>
          Distribution of engine assets across operational lifecycle bands.
        </div>

        {isLoading ? (
          <LoadingState message="Loading prediction histogram..." />
        ) : (
          <div style={{ width: '100%', height: '300px' }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={histogramData} margin={{ top: 10, right: 20, left: 0, bottom: 20 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                <XAxis dataKey="range" tick={{ fontSize: 11 }} />
                <YAxis allowDecimals={false} label={{ value: 'Number of Engines', angle: -90, position: 'insideLeft', fontSize: 11 }} />
                <Tooltip contentStyle={{ fontSize: '0.75rem', borderRadius: '4px' }} />
                <Bar dataKey="count" name="Engine Count" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>
    </div>
  );
};
