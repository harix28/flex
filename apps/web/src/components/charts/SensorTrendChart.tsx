import React, { useState, useMemo } from 'react';
import { Observation } from '../../services/types';
import { Table, LineChart, Info } from 'lucide-react';

interface SensorTrendChartProps {
  observations: Observation[];
  channelSchema?: {
    operating_settings: string[];
    sensor_channels: string[];
  };
}

const CHANNEL_COLORS: Record<string, string> = {
  sensor_02: '#0369a1', // Total temperature at LPC outlet
  sensor_03: '#a16207', // Total temperature at HPC outlet
  sensor_04: '#b91c1c', // Total temperature at LPT outlet
  sensor_07: '#047857', // Total pressure at HPC outlet
  sensor_08: '#7e22ce', // Physical fan speed
  sensor_09: '#be185d', // Physical core speed
  sensor_11: '#0e7490', // Static pressure at HPC outlet
  sensor_12: '#4d7c0f', // Ratio of fuel flow to Ps30
  sensor_13: '#c2410c', // Corrected fan speed
  sensor_14: '#4338ca', // Corrected core speed
  sensor_15: '#0f766e', // Bypass Ratio
  sensor_17: '#854d0e', // Bleed Enthalpy
  sensor_20: '#be123c', // HPT coolant bleed
  sensor_21: '#6d28d9', // LPT coolant bleed
};

export const SensorTrendChart: React.FC<SensorTrendChartProps> = ({ observations, channelSchema }) => {
  const [activeTab, setActiveTab] = useState<'sensors' | 'settings'>('sensors');
  const [viewMode, setViewMode] = useState<'chart' | 'table'>('chart');
  
  // Default selected channels: 3 key temperature/pressure sensors that show degradation
  const [selectedSensors, setSelectedSensors] = useState<string[]>(['sensor_02', 'sensor_03', 'sensor_04']);
  const [selectedSettings, setSelectedSettings] = useState<string[]>(['setting_1', 'setting_2', 'setting_3']);

  const [hoveredPoint, setHoveredPoint] = useState<{ cycle: number; values: Record<string, number>; x: number; y: number } | null>(null);

  const availableSensors = channelSchema?.sensor_channels || [
    'sensor_01', 'sensor_02', 'sensor_03', 'sensor_04', 'sensor_05',
    'sensor_06', 'sensor_07', 'sensor_08', 'sensor_09', 'sensor_10',
    'sensor_11', 'sensor_12', 'sensor_13', 'sensor_14', 'sensor_15',
    'sensor_16', 'sensor_17', 'sensor_18', 'sensor_19', 'sensor_20', 'sensor_21'
  ];

  const availableSettings = channelSchema?.operating_settings || ['setting_1', 'setting_2', 'setting_3'];

  // Sort observations chronologically by flight cycle
  const sortedObs = useMemo(() => {
    return [...observations].sort((a, b) => a.cycle - b.cycle);
  }, [observations]);

  const toggleSensor = (sensor: string) => {
    setSelectedSensors((prev) =>
      prev.includes(sensor) ? (prev.length > 1 ? prev.filter((s) => s !== sensor) : prev) : [...prev, sensor]
    );
  };

  const toggleSetting = (setting: string) => {
    setSelectedSettings((prev) =>
      prev.includes(setting) ? (prev.length > 1 ? prev.filter((s) => s !== setting) : prev) : [...prev, setting]
    );
  };

  const activeChannels = activeTab === 'sensors' ? selectedSensors : selectedSettings;

  // Chart Dimensions & Scales
  const width = 800;
  const height = 360;
  const margin = { top: 20, right: 30, bottom: 40, left: 60 };
  const chartWidth = width - margin.left - margin.right;
  const chartHeight = height - margin.top - margin.bottom;

  const minCycle = sortedObs.length > 0 ? sortedObs[0].cycle : 1;
  const maxCycle = sortedObs.length > 0 ? sortedObs[sortedObs.length - 1].cycle : 100;
  const cycleSpan = Math.max(1, maxCycle - minCycle);

  // Normalize each channel to [0, 1] so unlike units are not mixed on an unexplained single axis,
  // but tooltips show EXACT unnormalized stored values!
  const channelStats = useMemo(() => {
    const stats: Record<string, { min: number; max: number }> = {};
    activeChannels.forEach((ch) => {
      let values: number[] = [];
      if (activeTab === 'sensors') {
        const idx = parseInt(ch.replace('sensor_', ''), 10) - 1;
        values = sortedObs.map((o) => o.sensors[idx]).filter((v) => typeof v === 'number' && !isNaN(v));
      } else {
        const idx = parseInt(ch.replace('setting_', ''), 10) - 1;
        values = sortedObs.map((o) => o.settings[idx]).filter((v) => typeof v === 'number' && !isNaN(v));
      }

      if (values.length > 0) {
        const min = Math.min(...values);
        const max = Math.max(...values);
        stats[ch] = { min, max: max === min ? min + 1 : max };
      } else {
        stats[ch] = { min: 0, max: 1 };
      }
    });
    return stats;
  }, [sortedObs, activeChannels, activeTab]);

  // Build Discontinuous SVG Path Segments (Preserve gaps; do not interpolate missing cycles)
  const channelPaths = useMemo(() => {
    const paths: Record<string, string[]> = {};
    activeChannels.forEach((ch) => {
      paths[ch] = [];
      let currentSegment: string[] = [];

      sortedObs.forEach((obs, index) => {
        let rawVal = 0;
        if (activeTab === 'sensors') {
          const idx = parseInt(ch.replace('sensor_', ''), 10) - 1;
          rawVal = obs.sensors[idx];
        } else {
          const idx = parseInt(ch.replace('setting_', ''), 10) - 1;
          rawVal = obs.settings[idx];
        }

        const x = margin.left + ((obs.cycle - minCycle) / cycleSpan) * chartWidth;
        const { min, max } = channelStats[ch] || { min: 0, max: 1 };
        const norm = (rawVal - min) / (max - min);
        const y = margin.top + chartHeight - norm * chartHeight;

        // Check if there is a cycle gap with previous observation
        if (index > 0 && obs.cycle - sortedObs[index - 1].cycle > 1) {
          // Finish previous segment and start new one
          if (currentSegment.length > 0) {
            paths[ch].push(currentSegment.join(' '));
            currentSegment = [];
          }
        }

        if (currentSegment.length === 0) {
          currentSegment.push(`M ${x.toFixed(1)} ${y.toFixed(1)}`);
        } else {
          currentSegment.push(`L ${x.toFixed(1)} ${y.toFixed(1)}`);
        }
      });

      if (currentSegment.length > 0) {
        paths[ch].push(currentSegment.join(' '));
      }
    });
    return paths;
  }, [sortedObs, activeChannels, channelStats, cycleSpan, minCycle, chartWidth, chartHeight, margin, activeTab]);

  return (
    <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
      {/* Chart Header & Controls */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.75rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <button
            type="button"
            className={`btn ${activeTab === 'sensors' ? 'btn-primary' : 'btn-secondary'}`}
            onClick={() => setActiveTab('sensors')}
            style={{ fontSize: '0.8125rem', padding: '0.35rem 0.75rem' }}
          >
            Sensor Channels (21)
          </button>
          <button
            type="button"
            className={`btn ${activeTab === 'settings' ? 'btn-primary' : 'btn-secondary'}`}
            onClick={() => setActiveTab('settings')}
            style={{ fontSize: '0.8125rem', padding: '0.35rem 0.75rem' }}
          >
            Operating Settings (3)
          </button>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <button
            type="button"
            className={`btn ${viewMode === 'chart' ? 'btn-secondary' : 'btn-secondary'}`}
            onClick={() => setViewMode(viewMode === 'chart' ? 'table' : 'chart')}
            style={{ fontSize: '0.8125rem', padding: '0.35rem 0.75rem' }}
            aria-label="Toggle between chart and tabular data"
          >
            {viewMode === 'chart' ? (
              <>
                <Table size={14} aria-hidden="true" />
                <span>View Numeric Table</span>
              </>
            ) : (
              <>
                <LineChart size={14} aria-hidden="true" />
                <span>View Trend Chart</span>
              </>
            )}
          </button>
        </div>
      </div>

      {/* Channel Selector Chips */}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.375rem', alignItems: 'center' }}>
        <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginRight: '0.25rem' }}>Active channels:</span>
        {(activeTab === 'sensors' ? availableSensors : availableSettings).map((ch) => {
          const isSelected = activeChannels.includes(ch);
          const color = CHANNEL_COLORS[ch] || 'var(--primary)';
          return (
            <button
              key={ch}
              type="button"
              onClick={() => (activeTab === 'sensors' ? toggleSensor(ch) : toggleSetting(ch))}
              style={{
                fontSize: '0.75rem',
                padding: '0.2rem 0.5rem',
                borderRadius: 'var(--radius-sm)',
                border: `1px solid ${isSelected ? color : 'var(--border-subtle)'}`,
                backgroundColor: isSelected ? 'var(--bg-subtle)' : 'transparent',
                color: isSelected ? color : 'var(--text-muted)',
                cursor: 'pointer',
                fontFamily: 'var(--font-mono)',
                display: 'inline-flex',
                alignItems: 'center',
                gap: '0.25rem',
                transition: 'all 150ms ease',
              }}
            >
              <span
                style={{
                  width: '6px',
                  height: '6px',
                  borderRadius: '50%',
                  backgroundColor: isSelected ? color : 'transparent',
                  border: `1px solid ${color}`,
                }}
              />
              {ch}
            </button>
          );
        })}
      </div>

      {/* Notice about Discontinuous Gaps & Discrete Cycles */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '0.5rem',
          fontSize: '0.75rem',
          color: 'var(--text-muted)',
          backgroundColor: 'var(--bg-subtle)',
          padding: '0.4rem 0.75rem',
          borderRadius: 'var(--radius-sm)',
        }}
      >
        <Info size={14} style={{ color: 'var(--primary)', flexShrink: 0 }} />
        <span>
          X-axis strictly tracks <strong>discrete operating flight cycles</strong>. Broken lines indicate telemetry gaps; missing readings are never interpolated.
        </span>
      </div>

      {/* Content: Empty vs Chart vs Table */}
      {sortedObs.length === 0 ? (
        <div style={{ textAlign: 'center', padding: '3rem 1rem', color: 'var(--text-muted)' }}>
          No sensor observation records stored.
        </div>
      ) : viewMode === 'chart' ? (
        <div style={{ position: 'relative', width: '100%', overflowX: 'auto' }}>
          <svg
            viewBox={`0 0 ${width} ${height}`}
            style={{ width: '100%', height: 'auto', display: 'block', minWidth: '600px' }}
            role="img"
            aria-label={`Sensor trends chart for ${activeChannels.join(', ')} over cycles ${minCycle} to ${maxCycle}`}
          >
            {/* Grid Lines */}
            {[0, 0.25, 0.5, 0.75, 1].map((pct, idx) => {
              const y = margin.top + chartHeight * pct;
              return (
                <line
                  key={`grid-y-${idx}`}
                  x1={margin.left}
                  y1={y}
                  x2={width - margin.right}
                  y2={y}
                  stroke="var(--border-subtle)"
                  strokeDasharray="4 4"
                />
              );
            })}

            {/* X-axis ticks (Cycles) */}
            {Array.from({ length: 6 }).map((_, idx) => {
              const cycleVal = Math.round(minCycle + (cycleSpan / 5) * idx);
              const x = margin.left + (chartWidth / 5) * idx;
              return (
                <g key={`x-tick-${idx}`} transform={`translate(${x}, ${height - margin.bottom + 15})`}>
                  <line x1={0} y1={-15} x2={0} y2={-10} stroke="var(--border-strong)" />
                  <text
                    textAnchor="middle"
                    fill="var(--text-muted)"
                    fontSize="11"
                    fontFamily="var(--font-mono)"
                  >
                    C{cycleVal}
                  </text>
                </g>
              );
            })}

            {/* Y-axis Label */}
            <text
              transform={`translate(15, ${margin.top + chartHeight / 2}) rotate(-90)`}
              textAnchor="middle"
              fill="var(--text-muted)"
              fontSize="11"
            >
              Normalized Value [0-1]
            </text>

            {/* X-axis Label */}
            <text
              x={margin.left + chartWidth / 2}
              y={height - 5}
              textAnchor="middle"
              fill="var(--text-secondary)"
              fontSize="12"
              fontWeight="500"
            >
              Operating Flight Cycle (Cycles)
            </text>

            {/* Paths for each channel */}
            {activeChannels.map((ch) => {
              const segments = channelPaths[ch] || [];
              const color = CHANNEL_COLORS[ch] || 'var(--primary)';
              return (
                <g key={`path-group-${ch}`} data-channel={ch}>
                  {segments.map((d, sIdx) => (
                    <path
                      key={`seg-${ch}-${sIdx}`}
                      d={d}
                      fill="none"
                      stroke={color}
                      strokeWidth="2"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    />
                  ))}
                </g>
              );
            })}

            {/* Hover Detection Overlay */}
            {sortedObs.map((obs) => {
              const x = margin.left + ((obs.cycle - minCycle) / cycleSpan) * chartWidth;
              return (
                <rect
                  key={`hover-col-${obs.cycle}`}
                  x={x - 6}
                  y={margin.top}
                  width={12}
                  height={chartHeight}
                  fill="transparent"
                  style={{ cursor: 'crosshair' }}
                  onMouseEnter={(e) => {
                    const rect = e.currentTarget.getBoundingClientRect();
                    const values: Record<string, number> = {};
                    activeChannels.forEach((ch) => {
                      if (activeTab === 'sensors') {
                        const idx = parseInt(ch.replace('sensor_', ''), 10) - 1;
                        values[ch] = obs.sensors[idx];
                      } else {
                        const idx = parseInt(ch.replace('setting_', ''), 10) - 1;
                        values[ch] = obs.settings[idx];
                      }
                    });
                    setHoveredPoint({
                      cycle: obs.cycle,
                      values,
                      x: rect.left + rect.width / 2,
                      y: rect.top,
                    });
                  }}
                  onMouseLeave={() => setHoveredPoint(null)}
                />
              );
            })}
          </svg>

          {/* Hover Tooltip */}
          {hoveredPoint && (
            <div
              style={{
                position: 'fixed',
                left: `${hoveredPoint.x + 10}px`,
                top: `${hoveredPoint.y - 40}px`,
                backgroundColor: 'var(--bg-surface-elevated)',
                border: '1px solid var(--border-strong)',
                borderRadius: 'var(--radius-sm)',
                padding: '0.5rem 0.75rem',
                boxShadow: 'var(--shadow-md)',
                pointerEvents: 'none',
                zIndex: 50,
                fontSize: '0.75rem',
              }}
            >
              <div style={{ fontWeight: 600, color: 'var(--text-primary)', marginBottom: '0.25rem' }}>
                Cycle: {hoveredPoint.cycle}
              </div>
              {Object.entries(hoveredPoint.values).map(([ch, val]) => (
                <div key={ch} style={{ display: 'flex', justifyContent: 'space-between', gap: '1rem', color: CHANNEL_COLORS[ch] || 'var(--text-secondary)' }}>
                  <span>{ch}:</span>
                  <span className="mono" style={{ fontWeight: 600 }}>
                    {typeof val === 'number' ? val.toFixed(4) : val}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      ) : (
        /* Tabular Alternative View */
        <div className="table-container" style={{ maxHeight: '380px' }}>
          <table className="table">
            <thead>
              <tr>
                <th>Flight Cycle</th>
                {activeChannels.map((ch) => (
                  <th key={ch} className="mono">
                    {ch}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {sortedObs.map((obs) => (
                <tr key={`row-cycle-${obs.cycle}`}>
                  <td className="mono" style={{ fontWeight: 600, color: 'var(--primary)' }}>
                    Cycle {obs.cycle}
                  </td>
                  {activeChannels.map((ch) => {
                    let val = 0;
                    if (activeTab === 'sensors') {
                      const idx = parseInt(ch.replace('sensor_', ''), 10) - 1;
                      val = obs.sensors[idx];
                    } else {
                      const idx = parseInt(ch.replace('setting_', ''), 10) - 1;
                      val = obs.settings[idx];
                    }
                    return (
                      <td key={`${obs.cycle}-${ch}`} className="mono">
                        {typeof val === 'number' ? val.toFixed(4) : val}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};
