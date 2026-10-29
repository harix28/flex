import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { SensorTrendChart } from '../components/charts/SensorTrendChart';
import { Observation } from '../services/types';

describe('SensorTrendChart', () => {
  const createSensors = (s2: number, s3: number, s4: number) => {
    const arr = new Array(21).fill(100.0);
    arr[1] = s2; // sensor_02
    arr[2] = s3; // sensor_03
    arr[3] = s4; // sensor_04
    return arr;
  };

  const mockObservations: Observation[] = [
    {
      cycle: 1,
      settings: [0.001, 0.0002, 100.0],
      sensors: createSensors(642.15, 1588.45, 1400.1),
      observed_at: '2026-03-01T10:00:00Z',
      ingested_at: '2026-03-01T10:05:00Z',
    },
    {
      cycle: 2,
      settings: [0.002, 0.0003, 100.0],
      sensors: createSensors(642.18, 1588.60, 1400.5),
      observed_at: '2026-03-01T11:00:00Z',
      ingested_at: '2026-03-01T11:05:00Z',
    },
    // GAP: Cycle 3 and 4 missing! Next is cycle 5.
    {
      cycle: 5,
      settings: [0.001, 0.0001, 100.0],
      sensors: createSensors(642.30, 1589.10, 1401.2),
      observed_at: '2026-03-01T14:00:00Z',
      ingested_at: '2026-03-01T14:05:00Z',
    },
  ];

  it('renders an honest empty state when no observations are provided', () => {
    render(<SensorTrendChart observations={[]} />);
    expect(screen.getByText('No sensor observation records stored.')).toBeInTheDocument();
  });

  it('preserves telemetry gaps by breaking lines into separate SVG paths across missing cycles', () => {
    const { container } = render(<SensorTrendChart observations={mockObservations} />);

    // In mockObservations, cycles 1 and 2 form segment 1, and cycle 5 forms segment 2.
    // For sensor_02 (which is selected by default), there must be 2 separate paths.
    const paths = container.querySelectorAll('g[data-channel="sensor_02"] path');
    expect(paths.length).toBe(2);
  });

  it('allows switching to tabular view and displays discrete cycle records', () => {
    render(<SensorTrendChart observations={mockObservations} />);

    const tableToggle = screen.getByText('View Numeric Table');
    fireEvent.click(tableToggle);

    expect(screen.getByRole('table')).toBeInTheDocument();
    expect(screen.getByText('Flight Cycle')).toBeInTheDocument();
    expect(screen.getAllByText('sensor_02').length).toBeGreaterThanOrEqual(1);

    // Verify cycles 1, 2, 5 are present
    expect(screen.getByText('Cycle 1')).toBeInTheDocument();
    expect(screen.getByText('Cycle 2')).toBeInTheDocument();
    expect(screen.getByText('Cycle 5')).toBeInTheDocument();
  });

  it('allows switching between sensor channels and operating settings', () => {
    render(<SensorTrendChart observations={mockObservations} />);

    const settingsTab = screen.getByText(/Operating Settings/i);
    fireEvent.click(settingsTab);

    expect(screen.getByText('setting_1')).toBeInTheDocument();
    expect(screen.getByText('setting_2')).toBeInTheDocument();
    expect(screen.getByText('setting_3')).toBeInTheDocument();
  });
});
