import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { ModelMonitoringPage } from '../pages/ModelMonitoringPage';
import { mlopsApi } from '../services/api';
import { useAuth } from '../context/AuthContext';

vi.mock('../services/api', () => ({
  mlopsApi: {
    getModelInfo: vi.fn(),
    getObservability: vi.fn(),
    getMonitoringRuns: vi.fn(),
    getMonitoringRunDetail: vi.fn(),
  },
}));

vi.mock('../context/AuthContext', () => ({
  useAuth: vi.fn(),
}));

describe('ModelMonitoringPage', () => {
  const mockTenant = {
    id: 'tenant-123',
    name: 'Meridian Turbofan Maintenance',
    slug: 'meridian-turbofan',
    roles: ['admin'],
  };

  const mockModelInfo = {
    status: 'active',
    model_version: 'fd001-v1',
    model_family: 'xgboost',
    bundle_digest: '06d46a9c4f5f71aeb220ade135e52e713a0bd41f362e7caf00eda743442e7cfd',
    feature_schema: 'cmapss-trailing-v1',
    feature_count: 96,
    window_size: 30,
    target_subset: 'FD001',
    target_machine_type: 'cmapss_engine',
    target_data_source: 'nasa_replay',
    review_status: 'experiment_only',
    release_status: 'experiment_only',
    deployment_state: 'active',
    benchmark_metrics: {
      engines: 100,
      windows: 100,
      mae_cycles: 16.79,
      rmse_cycles: 21.61,
      bias_cycles: 9.89,
    },
    benchmark_protocol: '6 fixed evenly spaced causal cutoffs per held-out training engine',
    disclaimer: 'Simulated turbofan demonstration — experimental model only.',
  };

  const mockObservability = {
    tenant_id: 'tenant-123',
    total_predictions: 10,
    available_predictions: 9,
    unavailable_predictions: 1,
    unavailable_reasons: { insufficient_cycles: 1 },
    latency: {
      inference_ms: { min: 2.1, max: 8.4, mean: 4.2, p50: 3.9, p95: 7.8 },
      pipeline_ms: { min: 12.0, max: 28.5, mean: 16.2 },
    },
    models_used: { 'fd001-v1': 10 },
    outdated_predictions_count: 2,
  };

  const mockMonitoringRuns = {
    runs: [
      {
        id: 'run-eval-1',
        model_version: 'fd001-v1',
        run_type: 'evaluation' as const,
        status: 'available' as const,
        sample_count: 5,
        engine_count: 1,
        actor: 'operator:evaluation',
        created_at: '2026-10-26T17:00:00Z',
        summary: {
          mae_cycles: 24.22,
          rmse_cycles: 24.22,
        },
      },
      {
        id: 'run-drift-1',
        model_version: 'fd001-v1',
        run_type: 'drift' as const,
        status: 'insufficient_data' as const,
        sample_count: 2,
        engine_count: 1,
        actor: 'operator:monitoring',
        created_at: '2026-10-26T16:50:00Z',
        summary: {
          message: 'Insufficient unique input windows (2/5 required)',
        },
      },
    ],
    limit: 20,
    offset: 0,
  };

  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(useAuth).mockReturnValue({
      user: { id: 'u1', email: 'admin@meridian.local', display_name: 'Admin' },
      activeTenant: mockTenant as any,
      organizations: [mockTenant as any],
      isAuthenticated: true,
      isLoading: false,
      authError: null,
      login: vi.fn(),
      logout: vi.fn(),
      switchTenant: vi.fn(),
      hasRole: () => true,
      canManageRegistry: () => true,
      canManageInstallations: () => true,
      canCreatePredictions: () => true,
      canApproveWorkOrders: () => true,
      canAssignWorkOrders: () => true,
      canExecuteWorkOrders: () => true,
      canManageMembers: () => true,
      canIngestReplay: () => true,
    });

    vi.mocked(mlopsApi.getModelInfo).mockResolvedValue(mockModelInfo);
    vi.mocked(mlopsApi.getObservability).mockResolvedValue(mockObservability);
    vi.mocked(mlopsApi.getMonitoringRuns).mockResolvedValue(mockMonitoringRuns);
  });

  it('renders loading state initially', () => {
    vi.mocked(mlopsApi.getModelInfo).mockReturnValue(new Promise(() => {}));
    render(<ModelMonitoringPage />);
    expect(screen.getByText(/Loading model registry verification/i)).toBeInTheDocument();
  });

  it('renders model identity, schema, and verified bundle digest', async () => {
    render(<ModelMonitoringPage />);

    await waitFor(() => {
      expect(screen.getByText('Model Governance & Monitoring')).toBeInTheDocument();
    });

    expect(screen.getAllByText('fd001-v1').length).toBeGreaterThan(0);
    expect(screen.getByText(/cmapss-trailing-v1/)).toBeInTheDocument();
    expect(screen.getByText(/30 cycles sliding/)).toBeInTheDocument();
    expect(screen.getByText('06d46a9c4f5f71aeb220ade135e52e713a0bd41f362e7caf00eda743442e7cfd')).toBeInTheDocument();
    expect(screen.getByText(/STATE: ACTIVE/i)).toBeInTheDocument();
  });

  it('displays historical offline benchmark metrics distinctly', async () => {
    render(<ModelMonitoringPage />);

    await waitFor(() => {
      expect(screen.getByText('Historical Validation Benchmark')).toBeInTheDocument();
    });

    expect(screen.getByText('16.79')).toBeInTheDocument(); // MAE
    expect(screen.getByText('21.61')).toBeInTheDocument(); // RMSE
    expect(screen.getByText('+9.89')).toBeInTheDocument(); // Bias
  });

  it('displays inference volume and pure model latency vs pipeline duration', async () => {
    render(<ModelMonitoringPage />);

    await waitFor(() => {
      expect(screen.getByText('Tenant Inference Observability')).toBeInTheDocument();
    });

    expect(screen.getByText('10')).toBeInTheDocument(); // Total inferences
    expect(screen.getByText('9')).toBeInTheDocument(); // Available
    expect(screen.getByText('1')).toBeInTheDocument(); // Unavailable
    expect(screen.getByText(/3.9ms \/ 7.8ms/)).toBeInTheDocument(); // p50 / p95
    expect(screen.getByText(/16.2ms/)).toBeInTheDocument(); // Pipeline mean
  });

  it('clearly notes that live fleet accuracy is unavailable without verified ground truth', async () => {
    render(<ModelMonitoringPage />);

    await waitFor(() => {
      expect(screen.getByText(/LIVE ACCURACY UNAVAILABLE/i)).toBeInTheDocument();
    });

    expect(
      screen.getByText(/Completed work orders or operator sign-offs cannot be substituted as ground truth/i)
    ).toBeInTheDocument();
  });

  it('handles error state gracefully with retry button', async () => {
    vi.mocked(mlopsApi.getModelInfo).mockRejectedValueOnce(new Error('Network connection dropped'));
    render(<ModelMonitoringPage />);

    await waitFor(() => {
      expect(screen.getByText(/Model Monitoring Unavailable/i)).toBeInTheDocument();
    });
    expect(screen.getByText('Network connection dropped')).toBeInTheDocument();
  });

  it('opens details modal when clicking details on a monitoring run', async () => {
    vi.mocked(mlopsApi.getMonitoringRunDetail).mockResolvedValueOnce({
      id: 'run-eval-1',
      tenant_id: 'tenant-123',
      model_version: 'fd001-v1',
      run_type: 'evaluation',
      status: 'available',
      sample_count: 5,
      engine_count: 1,
      reference_digest: 'ref-sha256',
      actor: 'operator:evaluation',
      created_at: '2026-10-26T17:00:00Z',
      metrics: { mae_cycles: 24.22, rmse_cycles: 24.22, bias_cycles: 24.22 },
    });

    render(<ModelMonitoringPage />);

    await waitFor(() => {
      expect(screen.getByText('Monitoring & Evaluation Audit History')).toBeInTheDocument();
    });

    const detailButtons = screen.getAllByRole('button', { name: /Details/i });
    expect(detailButtons.length).toBeGreaterThan(0);
    fireEvent.click(detailButtons[0]);

    await waitFor(() => {
      expect(screen.getByText(/Monitoring Run Detail \(EVALUATION\)/i)).toBeInTheDocument();
    });
    expect(screen.getByText(/ref-sha256/)).toBeInTheDocument();
  });
});
