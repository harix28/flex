import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { PlanningPage } from '../pages/PlanningPage';
import { JobsPage } from '../pages/JobsPage';
import { IntegrationsPage } from '../pages/IntegrationsPage';
import { planningApi, jobsApi, integrationsApi, notificationsApi } from '../services/api';
import { useAuth } from '../context/AuthContext';

vi.mock('../services/api', () => ({
  planningApi: {
    getInventory: vi.fn(),
    getShifts: vi.fn(),
    getWorkOrderReadiness: vi.fn(),
  },
  jobsApi: {
    listJobs: vi.fn(),
    submitFleetScore: vi.fn(),
  },
  integrationsApi: {
    getStatus: vi.fn(),
    exportToCmms: vi.fn(),
    ingestEdgeTelemetry: vi.fn(),
  },
  notificationsApi: {
    listWebhooks: vi.fn(),
    createWebhook: vi.fn(),
    deleteWebhook: vi.fn(),
    getDispatchHistory: vi.fn(),
    testDispatch: vi.fn(),
  },
}));

vi.mock('../context/AuthContext', () => ({
  useAuth: vi.fn(),
}));

describe('Enterprise UI Pages', () => {
  const mockTenant = {
    id: '26c21516-f3ca-4b43-bc8b-f8067155e4da',
    name: 'Meridian Turbofan Maintenance',
    slug: 'meridian-turbofan',
    roles: ['admin'],
  };

  beforeEach(() => {
    vi.clearAllMocks();
    (useAuth as any).mockReturnValue({
      activeTenant: mockTenant,
      canManageRegistry: () => true,
    });
  });

  describe('PlanningPage', () => {
    it('renders warehouse parts inventory and shift workforce statistics', async () => {
      (planningApi.getInventory as any).mockResolvedValue({
        items: [
          {
            part_number: 'AMM-72-31-HPC-SEAL',
            name: 'HPC Rotor Blade Tip Seal Kit',
            category: 'compressor_high_pressure',
            warehouse_bin: 'Depot A / Bay 3 / Bin 12',
            stock_qty: 6,
            min_required: 2,
            unit_cost_usd: 1250.0,
            compatible_subsystems: ['HPC'],
          },
        ],
      });

      (planningApi.getShifts as any).mockResolvedValue({
        items: [
          {
            technician_id: 'tech-1',
            name: 'Sarah Miller',
            shift_name: 'morning',
            shift_hours: '06:00 - 14:00 UTC',
            qualifications: ['A&P Mechanic', 'Powerplant Rating'],
            is_on_duty: true,
          },
        ],
      });

      render(<PlanningPage />);

      await waitFor(() => {
        expect(screen.getByText('Maintenance Planning & Logistics')).toBeInTheDocument();
        expect(screen.getByText('HPC Rotor Blade Tip Seal Kit')).toBeInTheDocument();
        expect(screen.getByText('Depot A / Bay 3 / Bin 12')).toBeInTheDocument();
        expect(screen.getByText('IN STOCK')).toBeInTheDocument();
      });

      // Switch to shifts tab
      const shiftTabBtn = screen.getByRole('button', { name: /Technician Shift Rosters/i });
      fireEvent.click(shiftTabBtn);

      await waitFor(() => {
        expect(screen.getByText('Sarah Miller')).toBeInTheDocument();
        expect(screen.getByText('ON DUTY')).toBeInTheDocument();
        expect(screen.getByText('A&P Mechanic')).toBeInTheDocument();
      });
    });
  });

  describe('JobsPage', () => {
    it('renders outbox jobs queue and submits fleet scoring run', async () => {
      (jobsApi.listJobs as any).mockResolvedValue({
        total: 1,
        items: [
          {
            id: 'job-12345678-abcd',
            event_type: 'fleet.score',
            source_event_id: 'fleet-score-test-1',
            status: 'delivered',
            attempts: 1,
            max_attempts: 5,
            error_code: null,
            created_at: '2026-10-30T10:00:00Z',
            completed_at: '2026-10-30T10:00:05Z',
            result: { total: 25, available: 23, unavailable: 2 },
          },
        ],
      });

      (jobsApi.submitFleetScore as any).mockResolvedValue({
        job_id: 'job-99998888',
        source_event_id: 'fleet-score-new',
        status: 'pending',
        event_type: 'fleet.score',
        notice: 'Job enqueued',
      });

      render(<JobsPage />);

      await waitFor(() => {
        expect(screen.getByText('Background Jobs & Fleet Scoring')).toBeInTheDocument();
        expect(screen.getByText('DELIVERED')).toBeInTheDocument();
        expect(screen.getByText(/25/)).toBeInTheDocument();
      });

      const submitBtn = screen.getByRole('button', { name: /Enqueue Fleet Scoring Run/i });
      fireEvent.click(submitBtn);

      await waitFor(() => {
        expect(jobsApi.submitFleetScore).toHaveBeenCalledWith(mockTenant.id);
      });
    });
  });

  describe('IntegrationsPage', () => {
    it('renders IoT gateway protocols and CMMS connector policy', async () => {
      (integrationsApi.getStatus as any).mockResolvedValue({
        organization_id: mockTenant.id,
        edge_gateways: {
          protocols_supported: ['mqtt_sparkplug_b', 'opc_ua'],
          status: 'ready_for_ingestion',
          enforced_bounds: 'finite_float_3_settings_21_sensors',
        },
        cmms_adapters: {
          systems_supported: ['SAP_PM_01', 'IBM_MAXIMO_MIF'],
          policy: 'human_approval_gate_enforced',
          status: 'configured',
        },
      });

      (notificationsApi.listWebhooks as any).mockResolvedValue({
        items: [
          {
            id: 'hook-1',
            tenant_id: mockTenant.id,
            url: 'https://alerts.aviation.example.com',
            events: ['alert.urgent'],
            label: 'Test Hangar Hook',
            active: true,
            created_at: '2026-10-30T10:00:00Z',
          },
        ],
      });

      (notificationsApi.getDispatchHistory as any).mockResolvedValue({
        items: [],
      });

      render(<IntegrationsPage />);

      await waitFor(() => {
        expect(screen.getByText('Live Integrations, CMMS & Webhooks')).toBeInTheDocument();
        expect(screen.getByText('MQTT Sparkplug B')).toBeInTheDocument();
        expect(screen.getByText('OPC-UA Part 8')).toBeInTheDocument();
      });

      // Switch to CMMS tab
      const cmmsTabBtn = screen.getByRole('button', { name: /Enterprise CMMS/i });
      fireEvent.click(cmmsTabBtn);

      await waitFor(() => {
        expect(screen.getByText(/Strict Human Approval Policy Enforced/i)).toBeInTheDocument();
      });

      // Switch to Webhooks tab
      const webhooksTabBtn = screen.getByRole('button', { name: /HMAC Webhook Alerting/i });
      fireEvent.click(webhooksTabBtn);

      await waitFor(() => {
        expect(screen.getByText('Test Hangar Hook')).toBeInTheDocument();
        expect(screen.getByText('https://alerts.aviation.example.com')).toBeInTheDocument();
      });
    });
  });
});
