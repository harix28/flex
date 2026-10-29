// Domain Types for Meridian Sentinel

export type Role = 'admin' | 'plant_manager' | 'technician' | 'viewer';

export interface User {
  id: string;
  email: string;
  display_name: string;
}

export interface OrganizationMembership {
  id: string;
  name: string;
  slug: string | null;
  roles: Role[];
}

export interface Member {
  id: string;
  user_id: string;
  roles: Role[];
  active: boolean;
  display_name: string;
  email: string;
  user_active: boolean;
}

export type MachineLifecycle = 'active' | 'inactive' | 'archived';
export type DataSource = 'nasa_replay' | 'physical_device';

export interface ReplaySourceBinding {
  dataset: string;
  subset: string;
  engine_id: number;
  split: string;
  file_sha256?: string | null;
}

export interface Machine {
  id: string;
  tenant_id: string;
  asset_code: string;
  name: string;
  machine_type: string;
  manufacturer: string | null;
  model: string | null;
  serial_number: string | null;
  site: string | null;
  area: string | null;
  location: string | null;
  lifecycle_status: MachineLifecycle;
  data_source: DataSource;
  source_binding: ReplaySourceBinding | null;
  source_label: string;
  health_status: string;
  model_compatibility: string;
  detail_api_path: string;
  created_at: string;
  updated_at: string;
}

export interface Sensor {
  id: string;
  tenant_id: string;
  sensor_code: string;
  name: string;
  kind: string;
  data_source: DataSource;
  channel_id: string | null;
  hardware_identifier: string | null;
  canonical_unit: string | null;
  unit_provenance: string | null;
  status: 'active' | 'retired';
  retired: boolean;
  created_at: string;
  updated_at: string;
}

export interface Installation {
  id: string;
  tenant_id: string;
  machine_id: string;
  sensor_id: string;
  channel: string;
  installed_at: string;
  removed_at: string | null;
  valid_from: string;
  valid_to: string | null;
  note: string | null;
  sensor?: Sensor;
}

export interface ChannelCatalog {
  operating_settings: Array<{
    id: string;
    index: number;
    description: string;
  }>;
  sensor_channels: Array<{
    id: string;
    index: number;
    description: string;
  }>;
}

export interface Observation {
  cycle: number;
  settings: number[];
  sensors: number[];
  observed_at: string | null;
  ingested_at: string;
  batch_id?: string;
}

export interface ObservationsResponse {
  machine_id: string;
  stream: {
    id: string;
    dataset: string;
    subset: string;
    partition: string;
    engine_id: number;
    file_sha256: string;
    schema_version: number;
  } | null;
  channel_schema: {
    version: number;
    operating_settings: string[];
    sensor_channels: string[];
  };
  items: Observation[];
  next_after_cycle: number | null;
  data_mode: string;
  request_id: string;
}

export interface DataQualityGap {
  start_cycle: number;
  end_cycle: number;
}

export interface DataQualityResponse {
  machine_id: string;
  stream: any | null;
  data_mode: string;
  requested_range: {
    start_cycle: number;
    end_cycle: number;
  };
  observation_count: number;
  first_cycle: number | null;
  latest_cycle: number | null;
  missing_cycle_count: number;
  gaps: DataQualityGap[];
  is_contiguous: boolean;
  latest_ingested_at: string | null;
  channel_schema: any;
  schema_compatible: boolean;
  observed_at_available: boolean;
  request_id: string;
}

export type PriorityBand = 'urgent' | 'high' | 'medium' | 'low' | 'unknown';
export type PredictionStatus = 'available' | 'unavailable';

export interface Prediction {
  id: string;
  tenant_id: string;
  machine_id: string;
  stream_id: string;
  actor_id: string;
  request_id: string;
  status: PredictionStatus;
  reason: string | null;
  requested_cutoff_cycle: number;
  observed_cutoff_cycle: number;
  input_start_cycle: number;
  input_end_cycle: number;
  input_window_start_cycle: number;
  input_window_end_cycle: number;
  input_observation_count: number;
  input_digest: string;
  model_version: string;
  model_digest: string;
  bundle_digest: string;
  inference_version: number;
  feature_schema_version: number;
  rul_cycles: number | null;
  rul_units: string;
  failure_probability: number | null;
  interval: any | null;
  diagnosis_basis: string;
  release_status: string;
  policy_version: string;
  priority_band: PriorityBand;
  priority_rule: string;
  created_at: string;
  idempotency_replayed: boolean;
  // Extended fields for latest endpoint:
  is_current?: boolean;
  is_outdated?: boolean;
  latest_observation_cycle?: number;
}

export interface MaintenancePriorityItem {
  machine_id: string;
  asset_code: string;
  machine_name: string;
  machine_type: string;
  priority_band: PriorityBand;
  rul_cycles: number | null;
  rul_units: string;
  status: PredictionStatus;
  reason: string | null;
  is_current: boolean;
  is_outdated: boolean;
  prediction_cutoff_cycle: number | null;
  latest_observation_cycle: number | null;
  explanation: string;
  prediction_id: string | null;
  model_version: string | null;
  model_digest: string | null;
  predicted_at: string | null;
}

export interface PrioritySummary {
  urgent: number;
  high: number;
  medium: number;
  low: number;
  outdated: number;
  unknown: number;
}

export interface MaintenancePrioritiesResponse {
  policy_version: string;
  policy_thresholds: {
    policy_version: string;
    urgent_max_cycles: number;
    high_max_cycles: number;
    medium_max_cycles: number;
    units: string;
    disclaimer: string;
  };
  summary: PrioritySummary;
  items: MaintenancePriorityItem[];
  limit: number;
  offset: number;
  total: number;
  request_id: string;
}

export type WorkOrderStatus = 'draft' | 'approved' | 'in_progress' | 'blocked' | 'completed' | 'cancelled';
export type WorkOrderPriority = 'critical' | 'high' | 'medium' | 'low';
export type WorkOrderAction = 'approve' | 'cancel' | 'start' | 'block' | 'resume' | 'complete';

export interface WorkOrderEvidenceSnapshot {
  prediction_id: string | null;
  model_version: string | null;
  model_digest: string | null;
  bundle_digest: string | null;
  stream_id: string | null;
  cutoff_cycle: number | null;
  rul_cycles: number | null;
  rul_units: string | null;
  prediction_status: string | null;
  release_status: string | null;
  policy_version: string | null;
  snapshot_priority_band: string | null;
  disclaimer: string | null;
}

export interface WorkOrder {
  id: string;
  tenant_id: string;
  machine_id: string;
  work_order_number: string;
  origin: 'manual' | 'prediction';
  status: WorkOrderStatus;
  version: number;
  priority: WorkOrderPriority;
  title: string;
  description: string;
  planned_date: string | null;
  due_date: string | null;
  assigned_technician_id: string | null;
  assigned_technician?: {
    id: string;
    display_name: string;
    email: string;
  } | null;
  evidence: WorkOrderEvidenceSnapshot;
  is_evidence_outdated: boolean;
  current_max_observation_cycle: number | null;
  cancellation_reason: string | null;
  block_reason: string | null;
  completion_summary: string | null;
  created_at: string;
  updated_at: string;
  approved_at: string | null;
  started_at: string | null;
  blocked_at: string | null;
  completed_at: string | null;
  cancelled_at: string | null;
  machine?: Machine;
}

export interface WorkOrderTransitionRecord {
  id: string;
  work_order_id: string;
  from_status: WorkOrderStatus;
  to_status: WorkOrderStatus;
  action: string;
  reason: string | null;
  actor_id: string;
  actor?: {
    id: string;
    display_name: string;
    email: string;
  };
  created_at: string;
}

export interface WorkOrderAssignmentRecord {
  id: string;
  work_order_id: string;
  technician_id: string;
  technician?: {
    id: string;
    display_name: string;
    email: string;
  };
  actor_id: string;
  actor?: {
    id: string;
    display_name: string;
    email: string;
  };
  reason: string | null;
  created_at: string;
}

export interface WorkOrderNoteRecord {
  id: string;
  work_order_id: string;
  author_id: string;
  author?: {
    id: string;
    display_name: string;
    email: string;
  };
  note_text: string;
  created_at: string;
}

export interface WorkOrderHistory {
  work_order_id: string;
  transitions: WorkOrderTransitionRecord[];
  assignments: WorkOrderAssignmentRecord[];
  notes: WorkOrderNoteRecord[];
  request_id: string;
}

// MLOps & Monitoring Types
export interface ModelBenchmarkMetrics {
  engines?: number;
  windows?: number;
  mae_cycles?: number;
  bias_cycles?: number;
  rmse_cycles?: number;
  engine_balanced_mae_cycles?: number;
  engine_balanced_rmse_cycles?: number;
}

export interface ModelInfo {
  status: string;
  model_version: string;
  model_family: string;
  bundle_digest: string;
  feature_schema: string;
  feature_count: number;
  window_size: number;
  target_subset: string;
  target_machine_type: string;
  target_data_source: string;
  review_status: string;
  release_status: string;
  deployment_state: string;
  benchmark_metrics: ModelBenchmarkMetrics;
  benchmark_protocol: string;
  disclaimer: string;
}

export interface LatencyStats {
  min: number | null;
  max: number | null;
  mean: number | null;
  p50?: number | null;
  p95?: number | null;
}

export interface MlObservability {
  tenant_id: string;
  total_predictions: number;
  available_predictions: number;
  unavailable_predictions: number;
  unavailable_reasons: Record<string, number>;
  latency: {
    inference_ms: LatencyStats;
    pipeline_ms: LatencyStats;
  };
  models_used: Record<string, number>;
  outdated_predictions_count: number;
}

export interface MonitoringRunSummary {
  drift_detected?: boolean | null;
  mae_cycles?: number | null;
  rmse_cycles?: number | null;
  message?: string | null;
}

export interface MonitoringRun {
  id: string;
  model_version: string;
  run_type: 'drift' | 'evaluation';
  status: 'available' | 'insufficient_data' | 'incompatible_reference' | 'failed';
  sample_count: number;
  engine_count: number;
  actor: string;
  created_at: string;
  summary: MonitoringRunSummary;
}

export interface MonitoringRunsResponse {
  runs: MonitoringRun[];
  limit: number;
  offset: number;
}

export interface MonitoringRunDetail {
  id: string;
  tenant_id: string;
  model_version: string;
  run_type: 'drift' | 'evaluation';
  status: string;
  sample_count: number;
  engine_count: number;
  reference_digest: string | null;
  actor: string;
  created_at: string;
  metrics: Record<string, any>;
}

/** Narrow assignment lookup: no membership administration or email exposure. */
export type EligibleAssignee = Omit<Member, 'email'>;
