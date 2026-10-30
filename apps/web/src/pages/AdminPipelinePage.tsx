import React, { useState, useRef } from 'react';
import { useAuth } from '../context/AuthContext';
import { adminPipelineApi, AdminPipelineResponse } from '../services/api';
import {
  UploadCloud,
  FileText,
  CheckCircle2,
  AlertTriangle,
  ArrowRight,
  Sparkles,
  BarChart2,
  Cpu,
  Layers,
  RefreshCw,
} from 'lucide-react';
import { PriorityBadge } from '../components/common/Badge';
import { LoadingState } from '../components/common/LoadingState';

interface AdminPipelinePageProps {
  onNavigateToOverview: () => void;
  onSelectMachine?: (machineId: string) => void;
}

export const AdminPipelinePage: React.FC<AdminPipelinePageProps> = ({
  onNavigateToOverview,
  onSelectMachine,
}) => {
  const { activeTenant, canManageMembers } = useAuth();
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<AdminPipelineResponse | null>(null);
  const [activeTab, setActiveTab] = useState<'eda' | 'features' | 'fleet'>('eda');
  const [edaSearch, setEdaSearch] = useState('');
  const fileInputRef = useRef<HTMLInputElement>(null);

  if (!canManageMembers()) {
    return (
      <div style={{ padding: '2rem' }}>
        <div className="card" style={{ padding: '2rem', textAlign: 'center', borderColor: 'var(--border-critical)' }}>
          <AlertTriangle size={48} color="var(--status-critical)" style={{ margin: '0 auto 1rem' }} />
          <h2 style={{ fontSize: '1.25rem', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '0.5rem' }}>
            Access Restricted: Administrator Only
          </h2>
          <p style={{ color: 'var(--text-secondary)', maxWidth: '500px', margin: '0 auto' }}>
            The Sensor Degradation Processing & ML Ingestion Pipeline requires Organization Administrator privileges (<code>members.manage</code>).
          </p>
        </div>
      </div>
    );
  }

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setSelectedFile(e.target.files[0]);
      setError(null);
      setResult(null);
    }
  };

  const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      setSelectedFile(e.dataTransfer.files[0]);
      setError(null);
      setResult(null);
    }
  };

  const handleProcess = async () => {
    if (!selectedFile || !activeTenant) return;
    setIsProcessing(true);
    setError(null);
    try {
      const response = await adminPipelineApi.processDataset(activeTenant.id, selectedFile);
      setResult(response);
    } catch (err: any) {
      setError(err?.message || 'Failed to process sensor degradation dataset');
    } finally {
      setIsProcessing(false);
    }
  };

  const sampleCsvData = `engine_id,cycle,setting_1,setting_2,setting_3,sensor_01,sensor_02,sensor_03,sensor_04,sensor_05,sensor_06,sensor_07,sensor_08,sensor_09,sensor_10,sensor_11,sensor_12,sensor_13,sensor_14,sensor_15,sensor_16,sensor_17,sensor_18,sensor_19,sensor_20,sensor_21
101,1,-0.0007,-0.0004,100.0,518.67,641.82,1589.70,1400.60,14.62,21.61,554.36,2388.06,9046.19,1.30,47.47,521.66,2388.02,8138.62,8.4195,0.03,392,2388,100.0,39.06,23.4190
101,2,0.0019,-0.0003,100.0,518.67,642.15,1591.82,1403.14,14.62,21.61,553.75,2388.04,9044.07,1.30,47.49,522.28,2388.07,8131.49,8.4318,0.03,392,2388,100.0,39.00,23.4236
101,3,-0.0043,0.0003,100.0,518.67,642.35,1587.99,1404.20,14.62,21.61,554.26,2388.08,9052.94,1.30,47.27,522.42,2388.03,8133.23,8.4178,0.03,390,2388,100.0,38.95,23.3442`;

  const downloadSampleCsv = () => {
    const blob = new Blob([sampleCsvData], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.setAttribute('href', url);
    link.setAttribute('download', 'sample_sensor_degradation.csv');
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  const edaEntries = result
    ? Object.entries(result.eda_analysis).filter(([name]) =>
        name.toLowerCase().includes(edaSearch.toLowerCase())
      )
    : [];

  return (
    <div style={{ padding: '1.5rem', display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      {/* Header Banner */}
      <div
        className="card"
        style={{
          padding: '1.5rem',
          display: 'flex',
          flexDirection: 'row',
          justifyContent: 'space-between',
          alignItems: 'flex-start',
          backgroundColor: 'var(--bg-surface)',
          borderLeft: '4px solid #2563eb',
        }}
      >
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '0.5rem' }}>
            <h1 style={{ fontSize: '1.35rem', fontWeight: 700, margin: 0, color: 'var(--text-primary)' }}>
              Admin ML Data Pipeline & Fleet Ingestion
            </h1>
            <span style={{ fontSize: '0.75rem', fontWeight: 600, padding: '0.2rem 0.5rem', borderRadius: '4px', backgroundColor: '#dbeafe', color: '#1e40af' }}>Admin Only</span>
            <span style={{ fontSize: '0.75rem', fontWeight: 600, padding: '0.2rem 0.5rem', borderRadius: '4px', backgroundColor: '#f1f5f9', color: '#475569' }}>Auto-Clean & EDA</span>
          </div>
          <p style={{ margin: 0, color: 'var(--text-secondary)', fontSize: '0.875rem', maxWidth: '850px' }}>
            Upload any degradation sensor stream (Option B flexible CSV or space-separated TXT). The system automatically validates data integrity, executes statistical EDA & degradation slopes, builds causal trailing feature vectors (W=30), predicts Remaining Useful Life (RUL), and live-updates the Fleet Maintenance Dashboard.
          </p>
        </div>
        <button
          onClick={downloadSampleCsv}
          className="button"
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '0.5rem',
            fontSize: '0.8125rem',
            padding: '0.5rem 0.875rem',
            border: '1px solid var(--border-subtle)',
            borderRadius: '6px',
            backgroundColor: 'var(--bg-canvas)',
            cursor: 'pointer',
            whiteSpace: 'nowrap',
          }}
        >
          <FileText size={15} />
          Download Sample CSV
        </button>
      </div>

      {/* File Upload Zone */}
      <div className="card" style={{ padding: '1.5rem', backgroundColor: 'var(--bg-surface)' }}>
        <h2 style={{ fontSize: '1rem', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <UploadCloud size={18} color="#2563eb" />
          Upload Sensor Degradation Stream
        </h2>

        <div
          onDragOver={(e) => e.preventDefault()}
          onDrop={handleDrop}
          onClick={() => fileInputRef.current?.click()}
          style={{
            border: '2px dashed var(--border-subtle)',
            borderRadius: '8px',
            padding: '2.5rem',
            textAlign: 'center',
            backgroundColor: selectedFile ? '#f0fdf4' : 'var(--bg-canvas)',
            cursor: 'pointer',
            transition: 'border-color 0.2s',
          }}
        >
          <input
            ref={fileInputRef}
            type="file"
            accept=".csv,.txt,.tsv"
            onChange={handleFileChange}
            style={{ display: 'none' }}
          />
          {selectedFile ? (
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '0.5rem' }}>
              <CheckCircle2 size={36} color="#16a34a" />
              <div style={{ fontWeight: 600, color: 'var(--text-primary)', fontSize: '0.95rem' }}>
                {selectedFile.name}
              </div>
              <div style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>
                {(selectedFile.size / 1024).toFixed(1)} KB · Ready to process
              </div>
              <div style={{ fontSize: '0.75rem', color: '#16a34a', marginTop: '0.25rem' }}>
                Click or drag another file to replace
              </div>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '0.5rem' }}>
              <UploadCloud size={36} color="var(--text-secondary)" />
              <div style={{ fontWeight: 600, color: 'var(--text-primary)', fontSize: '0.95rem' }}>
                Click to browse or drag and drop sensor dataset
              </div>
              <div style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>
                Supports standard C-MAPSS 26-column text format or custom CSV with header columns
              </div>
            </div>
          )}
        </div>

        {error && (
          <div
            style={{
              marginTop: '1rem',
              padding: '0.875rem 1rem',
              borderRadius: '6px',
              backgroundColor: '#fef2f2',
              border: '1px solid #fecaca',
              color: '#991b1b',
              fontSize: '0.875rem',
              display: 'flex',
              alignItems: 'center',
              gap: '0.5rem',
            }}
          >
            <AlertTriangle size={18} />
            <span>{error}</span>
          </div>
        )}

        <div style={{ marginTop: '1.25rem', display: 'flex', justifyContent: 'flex-end', gap: '0.75rem' }}>
          {selectedFile && (
            <button
              onClick={() => {
                setSelectedFile(null);
                setResult(null);
                setError(null);
              }}
              className="button"
              style={{
                padding: '0.5rem 1rem',
                border: '1px solid var(--border-subtle)',
                borderRadius: '6px',
                backgroundColor: 'transparent',
                cursor: 'pointer',
              }}
            >
              Clear
            </button>
          )}
          <button
            onClick={handleProcess}
            disabled={!selectedFile || isProcessing}
            className="button button-primary"
            style={{
              padding: '0.55rem 1.25rem',
              borderRadius: '6px',
              backgroundColor: '#2563eb',
              color: '#ffffff',
              fontWeight: 600,
              fontSize: '0.875rem',
              display: 'flex',
              alignItems: 'center',
              gap: '0.5rem',
              cursor: !selectedFile || isProcessing ? 'not-allowed' : 'pointer',
              opacity: !selectedFile || isProcessing ? 0.6 : 1,
            }}
          >
            {isProcessing ? (
              <>
                <RefreshCw size={16} className="animate-spin" />
                Cleaning, Analyzing & Ingesting...
              </>
            ) : (
              <>
                <Sparkles size={16} />
                Run Automated Cleaning, EDA & Fleet Ingestion
              </>
            )}
          </button>
        </div>
      </div>

      {isProcessing && (
        <div className="card" style={{ padding: '2rem', textAlign: 'center' }}>
          <LoadingState message="Executing pipeline: Data Cleaning -> Correlation EDA -> Feature Extraction (W=30) -> Database Registration -> RUL Prediction..." />
        </div>
      )}

      {/* Results View */}
      {result && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
          {/* Success Banner */}
          <div
            className="card"
            style={{
              padding: '1.25rem 1.5rem',
              backgroundColor: '#f0fdf4',
              borderColor: '#bbf7d0',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
              <CheckCircle2 size={24} color="#16a34a" />
              <div>
                <div style={{ fontWeight: 600, color: '#166534', fontSize: '0.95rem' }}>
                  {result.dashboard_message}
                </div>
                <div style={{ fontSize: '0.8125rem', color: '#15803d', marginTop: '0.2rem' }}>
                  Processed file <strong>{result.filename}</strong>: {result.cleaning.cleaned_rows} rows cleaned, {result.cleaning.unique_engines_found} engine stream(s) registered.
                </div>
              </div>
            </div>
            <button
              onClick={onNavigateToOverview}
              className="button button-primary"
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '0.5rem',
                backgroundColor: '#16a34a',
                color: '#ffffff',
                fontWeight: 600,
                fontSize: '0.875rem',
                padding: '0.5rem 1rem',
                borderRadius: '6px',
                border: 'none',
                cursor: 'pointer',
              }}
            >
              View on Fleet Maintenance Overview
              <ArrowRight size={16} />
            </button>
          </div>

          {/* Cleaning Summary Stats */}
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
              gap: '1rem',
            }}
          >
            <div className="card" style={{ padding: '1rem', backgroundColor: 'var(--bg-surface)' }}>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', textTransform: 'uppercase', fontWeight: 600 }}>
                Initial Raw Rows
              </div>
              <div style={{ fontSize: '1.5rem', fontWeight: 700, color: 'var(--text-primary)', marginTop: '0.25rem' }}>
                {result.cleaning.initial_rows.toLocaleString()}
              </div>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', marginTop: '0.25rem' }}>
                Total records received
              </div>
            </div>

            <div className="card" style={{ padding: '1rem', backgroundColor: 'var(--bg-surface)' }}>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', textTransform: 'uppercase', fontWeight: 600 }}>
                Cleaned Rows Ingested
              </div>
              <div style={{ fontSize: '1.5rem', fontWeight: 700, color: '#16a34a', marginTop: '0.25rem' }}>
                {result.cleaning.cleaned_rows.toLocaleString()}
              </div>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', marginTop: '0.25rem' }}>
                Validated finite & deduplicated
              </div>
            </div>

            <div className="card" style={{ padding: '1rem', backgroundColor: 'var(--bg-surface)' }}>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', textTransform: 'uppercase', fontWeight: 600 }}>
                Dropped Corrupt / Null Rows
              </div>
              <div style={{ fontSize: '1.5rem', fontWeight: 700, color: result.cleaning.dropped_rows > 0 ? '#dc2626' : 'var(--text-primary)', marginTop: '0.25rem' }}>
                {result.cleaning.dropped_rows}
              </div>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', marginTop: '0.25rem' }}>
                Non-finite or duplicate cycles
              </div>
            </div>

            <div className="card" style={{ padding: '1rem', backgroundColor: 'var(--bg-surface)' }}>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', textTransform: 'uppercase', fontWeight: 600 }}>
                Engines Ingested
              </div>
              <div style={{ fontSize: '1.5rem', fontWeight: 700, color: '#2563eb', marginTop: '0.25rem' }}>
                {result.cleaning.unique_engines_found}
              </div>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', marginTop: '0.25rem' }}>
                Asset streams mapped to fleet
              </div>
            </div>
          </div>

          {/* Navigation Tabs for Deep Dive */}
          <div className="card" style={{ padding: '1.5rem', backgroundColor: 'var(--bg-surface)' }}>
            <div
              style={{
                display: 'flex',
                gap: '1rem',
                borderBottom: '1px solid var(--border-subtle)',
                paddingBottom: '0.75rem',
                marginBottom: '1.25rem',
              }}
            >
              <button
                onClick={() => setActiveTab('eda')}
                style={{
                  background: 'none',
                  border: 'none',
                  borderBottom: activeTab === 'eda' ? '2px solid #2563eb' : 'none',
                  color: activeTab === 'eda' ? '#2563eb' : 'var(--text-secondary)',
                  fontWeight: activeTab === 'eda' ? 600 : 500,
                  fontSize: '0.9rem',
                  padding: '0.5rem 0.25rem',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.5rem',
                }}
              >
                <BarChart2 size={16} />
                Automated EDA & Degradation Slopes ({Object.keys(result.eda_analysis).length} Channels)
              </button>

              <button
                onClick={() => setActiveTab('features')}
                style={{
                  background: 'none',
                  border: 'none',
                  borderBottom: activeTab === 'features' ? '2px solid #2563eb' : 'none',
                  color: activeTab === 'features' ? '#2563eb' : 'var(--text-secondary)',
                  fontWeight: activeTab === 'features' ? 600 : 500,
                  fontSize: '0.9rem',
                  padding: '0.5rem 0.25rem',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.5rem',
                }}
              >
                <Layers size={16} />
                Feature Engineering (96 Causal Trailing Features)
              </button>

              <button
                onClick={() => setActiveTab('fleet')}
                style={{
                  background: 'none',
                  border: 'none',
                  borderBottom: activeTab === 'fleet' ? '2px solid #2563eb' : 'none',
                  color: activeTab === 'fleet' ? '#2563eb' : 'var(--text-secondary)',
                  fontWeight: activeTab === 'fleet' ? 600 : 500,
                  fontSize: '0.9rem',
                  padding: '0.5rem 0.25rem',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.5rem',
                }}
              >
                <Cpu size={16} />
                Ingested Fleet & Predictions ({result.ingested_fleet.length})
              </button>
            </div>

            {/* TAB 1: EDA Analysis */}
            {activeTab === 'eda' && (
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
                  <div style={{ fontSize: '0.875rem', color: 'var(--text-secondary)' }}>
                    Linear degradation slope \( \beta \) measures wear per operating cycle. Strong cycle correlation \( (|r| &gt; 0.4) \) identifies primary wear indicators.
                  </div>
                  <input
                    type="text"
                    placeholder="Search sensor channel..."
                    value={edaSearch}
                    onChange={(e) => setEdaSearch(e.target.value)}
                    style={{
                      padding: '0.4rem 0.75rem',
                      borderRadius: '6px',
                      border: '1px solid var(--border-subtle)',
                      backgroundColor: 'var(--bg-canvas)',
                      fontSize: '0.8125rem',
                      width: '220px',
                    }}
                  />
                </div>

                <div style={{ overflowX: 'auto' }}>
                  <table className="table" style={{ width: '100%', fontSize: '0.8125rem', borderCollapse: 'collapse' }}>
                    <thead>
                      <tr style={{ borderBottom: '1px solid var(--border-subtle)', textAlign: 'left', color: 'var(--text-secondary)' }}>
                        <th style={{ padding: '0.5rem' }}>Channel</th>
                        <th style={{ padding: '0.5rem' }}>Status</th>
                        <th style={{ padding: '0.5rem' }}>Mean</th>
                        <th style={{ padding: '0.5rem' }}>Std Dev</th>
                        <th style={{ padding: '0.5rem' }}>Min - Max</th>
                        <th style={{ padding: '0.5rem' }}>Degradation Slope (Wear/Cycle)</th>
                        <th style={{ padding: '0.5rem' }}>Cycle Correlation (r)</th>
                      </tr>
                    </thead>
                    <tbody>
                      {edaEntries.map(([sensorName, stats]) => {
                        const isDegrading = stats.status === 'degrading';
                        const isConstant = stats.status === 'constant';
                        return (
                          <tr key={sensorName} style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                            <td style={{ padding: '0.5rem', fontWeight: 600, color: 'var(--text-primary)' }}>
                              {sensorName.toUpperCase()}
                            </td>
                            <td style={{ padding: '0.5rem' }}>
                              {isDegrading ? (
                                <span style={{ fontSize: '0.75rem', fontWeight: 600, padding: '0.2rem 0.5rem', borderRadius: '4px', backgroundColor: '#fef3c7', color: '#92400e' }}>Degrading Wear</span>
                              ) : isConstant ? (
                                <span style={{ fontSize: '0.75rem', fontWeight: 600, padding: '0.2rem 0.5rem', borderRadius: '4px', backgroundColor: '#f1f5f9', color: '#64748b' }}>Constant</span>
                              ) : (
                                <span style={{ fontSize: '0.75rem', fontWeight: 600, padding: '0.2rem 0.5rem', borderRadius: '4px', backgroundColor: '#e0f2fe', color: '#0369a1' }}>Active</span>
                              )}
                            </td>
                            <td style={{ padding: '0.5rem', fontFamily: 'monospace' }}>{stats.mean.toFixed(2)}</td>
                            <td style={{ padding: '0.5rem', fontFamily: 'monospace' }}>{stats.std.toFixed(3)}</td>
                            <td style={{ padding: '0.5rem', fontFamily: 'monospace' }}>
                              [{stats.min.toFixed(2)}, {stats.max.toFixed(2)}]
                            </td>
                            <td style={{ padding: '0.5rem', fontFamily: 'monospace', color: isDegrading ? '#b45309' : 'inherit' }}>
                              {stats.degradation_slope > 0 ? `+${stats.degradation_slope.toFixed(5)}` : stats.degradation_slope.toFixed(5)}
                            </td>
                            <td style={{ padding: '0.5rem', fontFamily: 'monospace', fontWeight: Math.abs(stats.cycle_correlation) > 0.4 ? 600 : 400 }}>
                              {stats.cycle_correlation > 0 ? `+${stats.cycle_correlation.toFixed(3)}` : stats.cycle_correlation.toFixed(3)}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* TAB 2: Feature Engineering */}
            {activeTab === 'features' && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
                <div
                  style={{
                    backgroundColor: 'var(--bg-canvas)',
                    padding: '1rem',
                    borderRadius: '8px',
                    border: '1px solid var(--border-subtle)',
                  }}
                >
                  <div style={{ fontWeight: 600, color: 'var(--text-primary)', marginBottom: '0.5rem' }}>
                    Feature Pipeline Architecture: <code>{result.feature_engineering.schema}</code>
                  </div>
                  <p style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)', margin: 0 }}>
                    Constructed using a causal trailing window of up to 30 operating cycles. No future data leakage is permitted. For each of the 24 channels (3 settings + 21 sensors), 4 summary statistics are derived: <strong>last value</strong>, <strong>trailing mean</strong>, <strong>trailing standard deviation</strong>, and <strong>linear slope</strong> (24 × 4 = 96 features).
                  </p>
                </div>

                <div>
                  <div style={{ fontSize: '0.875rem', fontWeight: 600, marginBottom: '0.5rem', color: 'var(--text-primary)' }}>
                    Sample Extracted Feature Identifiers (First 10 of {result.feature_engineering.feature_count_per_window}):
                  </div>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
                    {result.feature_engineering.feature_names_sample.map((feat) => (
                      <span
                        key={feat}
                        style={{
                          backgroundColor: '#eff6ff',
                          color: '#1d4ed8',
                          padding: '0.3rem 0.6rem',
                          borderRadius: '4px',
                          fontSize: '0.75rem',
                          fontFamily: 'monospace',
                          border: '1px solid #bfdbfe',
                        }}
                      >
                        {feat}
                      </span>
                    ))}
                  </div>
                </div>

                <div style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>
                  Total trailing windows computed and ingested across engines: <strong>{result.feature_engineering.windows_computed}</strong>
                </div>
              </div>
            )}

            {/* TAB 3: Fleet Ingestion */}
            {activeTab === 'fleet' && (
              <div>
                <table className="table" style={{ width: '100%', fontSize: '0.8125rem', borderCollapse: 'collapse' }}>
                  <thead>
                    <tr style={{ borderBottom: '1px solid var(--border-subtle)', textAlign: 'left', color: 'var(--text-secondary)' }}>
                      <th style={{ padding: '0.5rem' }}>Asset Code</th>
                      <th style={{ padding: '0.5rem' }}>Stream Unit</th>
                      <th style={{ padding: '0.5rem' }}>Cycles Ingested</th>
                      <th style={{ padding: '0.5rem' }}>Predicted RUL</th>
                      <th style={{ padding: '0.5rem' }}>Maintenance Priority</th>
                      <th style={{ padding: '0.5rem' }}>Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.ingested_fleet.map((eng) => (
                      <tr key={eng.machine_id} style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                        <td style={{ padding: '0.5rem', fontWeight: 600, color: 'var(--text-primary)', fontFamily: 'monospace' }}>
                          {eng.asset_code}
                        </td>
                        <td style={{ padding: '0.5rem' }}>Engine #{eng.engine_id}</td>
                        <td style={{ padding: '0.5rem', fontFamily: 'monospace' }}>{eng.total_cycles_ingested} cycles</td>
                        <td style={{ padding: '0.5rem', fontWeight: 600, color: '#2563eb' }}>{eng.estimated_rul}</td>
                        <td style={{ padding: '0.5rem' }}>
                          <PriorityBadge priority={eng.priority_band} />
                        </td>
                        <td style={{ padding: '0.5rem' }}>
                          {onSelectMachine && (
                            <button
                              onClick={() => onSelectMachine(eng.machine_id)}
                              className="button"
                              style={{
                                padding: '0.25rem 0.5rem',
                                fontSize: '0.75rem',
                                border: '1px solid var(--border-subtle)',
                                borderRadius: '4px',
                                cursor: 'pointer',
                              }}
                            >
                              Inspect Details &gt;
                            </button>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
