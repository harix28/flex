import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { PredictionCard } from '../components/predictions/PredictionCard';
import { Prediction } from '../services/types';

describe('PredictionCard', () => {
  const mockPrediction: Prediction = {
    id: 'pred-001',
    tenant_id: 't-1',
    machine_id: 'mach-001',
    stream_id: 'str-1',
    actor_id: 'usr-1',
    request_id: 'req-001',
    status: 'available',
    reason: null,
    requested_cutoff_cycle: 120,
    observed_cutoff_cycle: 120,
    input_start_cycle: 91,
    input_end_cycle: 120,
    input_window_start_cycle: 91,
    input_window_end_cycle: 120,
    input_observation_count: 30,
    input_digest: 'sha256-input',
    model_version: 'runs/fd001-v1',
    model_digest: 'sha256-model',
    bundle_digest: 'sha256-bundle',
    inference_version: 1,
    feature_schema_version: 1,
    rul_cycles: 42,
    rul_units: 'cycles',
    failure_probability: null, // must show 'Unavailable'
    interval: null, // uncertainty interval null -> must show 'Unavailable'
    diagnosis_basis: 'rul_regression_c_mapss',
    release_status: 'experimental',
    policy_version: 'v1.0',
    priority_band: 'medium',
    priority_rule: 'rul_band:40-60',
    created_at: '2026-03-01T12:00:00Z',
    idempotency_replayed: false,
    is_current: true,
    is_outdated: false,
    latest_observation_cycle: 120,
  };

  it('renders discrete estimated RUL with cycles unit', () => {
    render(<PredictionCard prediction={mockPrediction} />);
    expect(screen.getByText('42.0')).toBeInTheDocument();
    expect(screen.getByText('operating cycles')).toBeInTheDocument();
    expect(screen.getByText('Medium')).toBeInTheDocument();
    expect(screen.getByText(/rul_band:40-60/i)).toBeInTheDocument();
  });

  it('explicitly displays Unavailable for null metrics and never invents numbers', () => {
    render(<PredictionCard prediction={mockPrediction} />);
    const unavailables = screen.getAllByText(/Unavailable/i);
    // failure_probability and diagnosis must be Unavailable
    expect(unavailables.length).toBeGreaterThanOrEqual(2);
    expect(screen.queryByText('0%')).not.toBeInTheDocument();
    expect(screen.queryByText('0.00')).not.toBeInTheDocument();
  });

  it('displays experimental model disclaimer', () => {
    render(<PredictionCard prediction={mockPrediction} />);
    expect(screen.getByText(/Simulation demonstration on NASA C-MAPSS dataset/i)).toBeInTheDocument();
    expect(screen.getByText(/Not airworthiness certified/i)).toBeInTheDocument();
    expect(screen.getByText(/Release: experimental/i)).toBeInTheDocument();
  });

  it('triggers onCreateDraft when Create Draft Work Order is clicked', () => {
    const handleCreate = vi.fn();
    render(<PredictionCard prediction={mockPrediction} onCreateDraft={handleCreate} canCreateDraft={true} />);
    const btn = screen.getByText(/Create Draft Work Order/i);
    fireEvent.click(btn);
    expect(handleCreate).toHaveBeenCalledTimes(1);
  });
});
