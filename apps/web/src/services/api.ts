/**
 * Meridian Sentinel API Client
 *
 * Implements typed endpoints, in-memory CSRF handling, credentials inclusion,
 * request cancellation, controlled error mapping, and tenant isolation.
 * No session tokens or passwords stored in localStorage.
 */

import {
  User,
  OrganizationMembership,
  Member,
  EligibleAssignee,
  Machine,
  Sensor,
  Installation,
  ChannelCatalog,
  ObservationsResponse,
  DataQualityResponse,
  Prediction,
  MaintenancePrioritiesResponse,
  WorkOrder,
  WorkOrderHistory,
  PriorityBand,
  WorkOrderStatus,
  WorkOrderPriority,
  WorkOrderAction,
  ModelInfo,
  MlObservability,
  MonitoringRunsResponse,
  MonitoringRunDetail,
} from './types';

export class ApiError extends Error {
  public status: number;
  public code: string;
  public requestId?: string;
  public details?: any;

  constructor(status: number, code: string, message: string, requestId?: string, details?: any) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
    this.requestId = requestId;
    this.details = details;
  }
}

let inMemoryCsrfToken: string | null = null;

export function setCsrfToken(token: string | null) {
  inMemoryCsrfToken = token;
}

export function getCsrfToken(): string | null {
  return inMemoryCsrfToken;
}

export const classificationApi = {
  get: (tenantId: string, machineId: string) => request<{
    lifetime_stage: string; source_cycle: number; model_version: string; interpretation: string;
  }>(`/api/v1/organizations/${tenantId}/machines/${machineId}/lifetime-classification`),
};

interface RequestOptions extends RequestInit {
  requiresCsrf?: boolean;
  requiresCsrfProtection?: boolean;
}

async function request<T>(endpoint: string, options: RequestOptions = {}): Promise<T> {
  const { requiresCsrf = false, requiresCsrfProtection = false, headers: customHeaders, ...rest } = options;

  const headers = new Headers(customHeaders);

  if (requiresCsrfProtection) {
    headers.set('X-CSRF-Protection', '1');
  }

  if (requiresCsrf && inMemoryCsrfToken) {
    headers.set('X-CSRF-Token', inMemoryCsrfToken);
  }

  if (rest.body && !headers.has('Content-Type') && typeof rest.body === 'string') {
    headers.set('Content-Type', 'application/json');
  }

  const response = await fetch(endpoint, {
    ...rest,
    headers,
    credentials: 'include', // Host-only HttpOnly session cookie
  });

  const contentType = response.headers.get('content-type') || '';
  const isJson = contentType.includes('application/json');

  let data: any = null;
  if (isJson) {
    try {
      data = await response.json();
    } catch {
      data = null;
    }
  }

  if (!response.ok) {
    const status = response.status;
    let code = 'unknown_error';
    let message = 'An unexpected error occurred';

    if (data) {
      if (typeof data.error?.code === 'string') {
        code = data.error.code;
        message = data.error.message || formatErrorCode(code);
      } else if (typeof data.detail === 'string') {
        code = data.detail;
        message = formatErrorCode(data.detail);
      } else if (typeof data.detail === 'object' && data.detail !== null) {
        code = data.detail.code || 'validation_error';
        message = data.detail.message || JSON.stringify(data.detail);
      } else if (data.code) {
        code = data.code;
        message = data.message || formatErrorCode(data.code);
      }
    } else {
      if (status === 401) {
        code = 'authentication_required';
        message = 'Your session has expired or authentication is required. Please log in.';
      } else if (status === 403) {
        code = 'forbidden';
        message = 'You do not have permission to perform this action.';
      } else if (status === 404) {
        code = 'not_found';
        message = 'Requested resource not found.';
      } else if (status === 429) {
        code = 'rate_limited';
        message = 'Too many requests. Please wait a few moments before trying again.';
      } else if (status >= 500) {
        code = 'backend_unavailable';
        message = 'Backend service is currently unavailable. Please verify backend status.';
      }
    }

    throw new ApiError(status, code, message, data?.request_id, data);
  }

  return data as T;
}

function formatErrorCode(code: string): string {
  switch (code) {
    case 'invalid_credentials':
      return 'Invalid email or password.';
    case 'csrf_failed':
      return 'Security verification failed (CSRF token missing or expired).';
    case 'rate_limited':
      return 'Too many login attempts. Please wait before retrying.';
    case 'version_conflict':
      return 'This record was modified by another user or session. Refresh this record before retrying to prevent overwriting.';
    case 'outdated_evidence':
      return 'The draft work order references outdated prediction evidence. Cancel this draft and create a fresh one from the latest prediction.';
    case 'assignee_ineligible':
      return 'The assigned technician is currently inactive or ineligible in this organization.';
    case 'invalid_transition':
      return 'The requested status transition is not permitted from the current state.';
    case 'already_active':
      return 'An active work order already exists for this machine.';
    case 'machine_not_found':
      return 'The specified machine does not exist in this organization.';
    case 'no_tenant_membership':
      return 'No active organization membership found for your account.';
    case 'insufficient_history':
      return 'Insufficient operating cycles stored (minimum 30 cycles required for model window).';
    case 'gaps_in_history':
      return 'Missing telemetry cycles detected within the required trailing 30-cycle window.';
    case 'unsupported_machine':
      return 'Selected machine is physical or not registered for NASA C-MAPSS replay.';
    case 'unsupported_subset':
      return 'Engine subset does not match model FD001.';
    default:
      return code.replace(/_/g, ' ');
  }
}

// ==========================================
// AUTHENTICATION & ORGANIZATIONS
// ==========================================

export const authApi = {
  async login(email: string, password: string): Promise<{ csrf_token: string; organizations: OrganizationMembership[]; request_id: string }> {
    const res = await request<{ csrf_token: string; organizations: OrganizationMembership[]; request_id: string }>(
      '/api/v1/auth/login',
      {
        method: 'POST',
        requiresCsrfProtection: true,
        body: JSON.stringify({ email, password }),
      }
    );
    setCsrfToken(res.csrf_token);
    return res;
  },

  async me(): Promise<{ user: User; organizations: OrganizationMembership[]; request_id: string }> {
    return request<{ user: User; organizations: OrganizationMembership[]; request_id: string }>(
      '/api/v1/auth/me',
      { method: 'GET' }
    );
  },

  async refreshCsrf(): Promise<{ csrf_token: string; request_id: string }> {
    const res = await request<{ csrf_token: string; request_id: string }>(
      '/api/v1/auth/csrf',
      {
        method: 'GET',
        requiresCsrfProtection: true,
      }
    );
    setCsrfToken(res.csrf_token);
    return res;
  },

  async logout(): Promise<{ status: string; request_id: string }> {
    try {
      const res = await request<{ status: string; request_id: string }>(
        '/api/v1/auth/logout',
        {
          method: 'POST',
          requiresCsrf: true,
        }
      );
      return res;
    } finally {
      setCsrfToken(null);
    }
  },

  async getMembers(tenantId: string, offset = 0): Promise<{ items: Member[]; next_offset: number | null; request_id: string }> {
    return request<{ items: Member[]; next_offset: number | null; request_id: string }>(
      `/api/v1/organizations/${tenantId}/members?offset=${offset}`,
      { method: 'GET' }
    );
  },

  async getEligibleAssignees(tenantId: string): Promise<{ items: EligibleAssignee[] }> {
    const items: EligibleAssignee[] = [];
    let offset: number | null = 0;
    while (offset !== null) {
      const page: { items: EligibleAssignee[]; next_offset: number | null } = await request(
        `/api/v1/organizations/${tenantId}/work-order-assignees?offset=${offset}`,
        { method: 'GET' }
      );
      items.push(...page.items);
      offset = page.next_offset;
    }
    return { items };
  },

  async addMember(tenantId: string, userId: string, roles: string[]): Promise<{ id: string; request_id: string }> {
    return request<{ id: string; request_id: string }>(
      `/api/v1/organizations/${tenantId}/members`,
      {
        method: 'POST',
        requiresCsrf: true,
        body: JSON.stringify({ user_id: userId, roles, active: true }),
      }
    );
  },

  async updateMember(tenantId: string, memberId: string, roles: string[], active: boolean): Promise<{ status: string; request_id: string }> {
    return request<{ status: string; request_id: string }>(
      `/api/v1/organizations/${tenantId}/members/${memberId}`,
      {
        method: 'PATCH',
        requiresCsrf: true,
        body: JSON.stringify({ roles, active }),
      }
    );
  },

  async removeMember(tenantId: string, memberId: string): Promise<{ status: string; request_id: string }> {
    return request<{ status: string; request_id: string }>(
      `/api/v1/organizations/${tenantId}/members/${memberId}`,
      {
        method: 'DELETE',
        requiresCsrf: true,
      }
    );
  },
};

// ==========================================
// REGISTRY & CHANNELS
// ==========================================

export const registryApi = {
  async getChannels(tenantId: string): Promise<ChannelCatalog> {
    return request<ChannelCatalog>(
      `/api/v1/organizations/${tenantId}/registry/channels`,
      { method: 'GET' }
    );
  },

  async listMachines(
    tenantId: string,
    params: {
      limit?: number;
      offset?: number;
      asset_code?: string;
      lifecycle_status?: string;
      data_source?: string;
      machine_type?: string;
      site?: string;
    } = {}
  ): Promise<{ items: Machine[]; next_offset: number | null; request_id: string }> {
    const q = new URLSearchParams();
    if (params.limit) q.set('limit', params.limit.toString());
    if (params.offset) q.set('offset', params.offset.toString());
    if (params.asset_code) q.set('asset_code', params.asset_code);
    if (params.lifecycle_status) q.set('lifecycle_status', params.lifecycle_status);
    if (params.data_source) q.set('data_source', params.data_source);
    if (params.machine_type) q.set('machine_type', params.machine_type);
    if (params.site) q.set('site', params.site);

    return request<{ items: Machine[]; next_offset: number | null; request_id: string }>(
      `/api/v1/organizations/${tenantId}/machines?${q.toString()}`,
      { method: 'GET' }
    );
  },

  async getMachine(tenantId: string, machineId: string): Promise<{ machine: Machine; request_id: string }> {
    return request<{ machine: Machine; request_id: string }>(
      `/api/v1/organizations/${tenantId}/machines/${machineId}`,
      { method: 'GET' }
    );
  },

  async createMachine(tenantId: string, payload: any): Promise<{ machine: Machine; request_id: string }> {
    return request<{ machine: Machine; request_id: string }>(
      `/api/v1/organizations/${tenantId}/machines`,
      {
        method: 'POST',
        requiresCsrf: true,
        body: JSON.stringify(payload),
      }
    );
  },

  async patchMachine(tenantId: string, machineId: string, payload: any): Promise<{ machine: Machine; request_id: string }> {
    return request<{ machine: Machine; request_id: string }>(
      `/api/v1/organizations/${tenantId}/machines/${machineId}`,
      {
        method: 'PATCH',
        requiresCsrf: true,
        body: JSON.stringify(payload),
      }
    );
  },

  async archiveMachine(tenantId: string, machineId: string): Promise<{ machine: Machine; request_id: string }> {
    return request<{ machine: Machine; request_id: string }>(
      `/api/v1/organizations/${tenantId}/machines/${machineId}/archive`,
      {
        method: 'POST',
        requiresCsrf: true,
      }
    );
  },

  async listSensors(
    tenantId: string,
    params: {
      limit?: number;
      offset?: number;
      sensor_code?: string;
      status?: string;
      data_source?: string;
      kind?: string;
      channel_id?: string;
    } = {}
  ): Promise<{ items: Sensor[]; next_offset: number | null; request_id: string }> {
    const q = new URLSearchParams();
    if (params.limit) q.set('limit', params.limit.toString());
    if (params.offset) q.set('offset', params.offset.toString());
    if (params.sensor_code) q.set('sensor_code', params.sensor_code);
    if (params.status) q.set('status', params.status);
    if (params.data_source) q.set('data_source', params.data_source);
    if (params.kind) q.set('kind', params.kind);
    if (params.channel_id) q.set('channel_id', params.channel_id);

    return request<{ items: Sensor[]; next_offset: number | null; request_id: string }>(
      `/api/v1/organizations/${tenantId}/sensors?${q.toString()}`,
      { method: 'GET' }
    );
  },

  async createSensor(tenantId: string, payload: any): Promise<{ sensor: Sensor; request_id: string }> {
    return request<{ sensor: Sensor; request_id: string }>(
      `/api/v1/organizations/${tenantId}/sensors`,
      {
        method: 'POST',
        requiresCsrf: true,
        body: JSON.stringify(payload),
      }
    );
  },

  async getInstallations(tenantId: string, machineId: string, openOnly = false): Promise<{ items: Installation[]; next_offset: number | null; request_id: string }> {
    return request<{ items: Installation[]; next_offset: number | null; request_id: string }>(
      `/api/v1/organizations/${tenantId}/machines/${machineId}/installations?open_only=${openOnly}`,
      { method: 'GET' }
    );
  },

  async installSensor(tenantId: string, machineId: string, payload: any): Promise<{ installation: Installation; request_id: string }> {
    return request<{ installation: Installation; request_id: string }>(
      `/api/v1/organizations/${tenantId}/machines/${machineId}/installations`,
      {
        method: 'POST',
        requiresCsrf: true,
        body: JSON.stringify(payload),
      }
    );
  },

  async removeInstallation(tenantId: string, installationId: string, payload: any): Promise<{ installation: Installation; request_id: string }> {
    return request<{ installation: Installation; request_id: string }>(
      `/api/v1/organizations/${tenantId}/installations/${installationId}/remove`,
      {
        method: 'POST',
        requiresCsrf: true,
        body: JSON.stringify(payload),
      }
    );
  },
};

// ==========================================
// INGESTION & SENSOR TRENDS
// ==========================================

export const ingestionApi = {
  async getObservations(
    tenantId: string,
    machineId: string,
    params: { start_cycle?: number; end_cycle?: number; after_cycle?: number; limit?: number } = {}
  ): Promise<ObservationsResponse> {
    const q = new URLSearchParams();
    if (params.start_cycle) q.set('start_cycle', params.start_cycle.toString());
    if (params.end_cycle) q.set('end_cycle', params.end_cycle.toString());
    if (params.after_cycle !== undefined) q.set('after_cycle', params.after_cycle.toString());
    if (params.limit) q.set('limit', params.limit.toString());

    return request<ObservationsResponse>(
      `/api/v1/organizations/${tenantId}/machines/${machineId}/observations?${q.toString()}`,
      { method: 'GET' }
    );
  },

  async getDataQuality(
    tenantId: string,
    machineId: string,
    params: { start_cycle?: number; end_cycle?: number } = {}
  ): Promise<DataQualityResponse> {
    const q = new URLSearchParams();
    if (params.start_cycle) q.set('start_cycle', params.start_cycle.toString());
    if (params.end_cycle) q.set('end_cycle', params.end_cycle.toString());

    return request<DataQualityResponse>(
      `/api/v1/organizations/${tenantId}/machines/${machineId}/data-quality?${q.toString()}`,
      { method: 'GET' }
    );
  },
};

// ==========================================
// PREDICTIONS & FLEET MAINTENANCE PRIORITY
// ==========================================

export const predictionsApi = {
  async getMaintenancePriorities(
    tenantId: string,
    params: { limit?: number; offset?: number; priority_band?: PriorityBand } = {}
  ): Promise<MaintenancePrioritiesResponse> {
    const q = new URLSearchParams();
    if (params.limit) q.set('limit', params.limit.toString());
    if (params.offset) q.set('offset', params.offset.toString());
    if (params.priority_band) q.set('priority_band', params.priority_band);

    return request<MaintenancePrioritiesResponse>(
      `/api/v1/organizations/${tenantId}/maintenance-priorities?${q.toString()}`,
      { method: 'GET' }
    );
  },

  async getLatestPrediction(tenantId: string, machineId: string): Promise<{ prediction: Prediction; request_id: string }> {
    return request<{ prediction: Prediction; request_id: string }>(
      `/api/v1/organizations/${tenantId}/machines/${machineId}/predictions/latest`,
      { method: 'GET' }
    );
  },

  async listPredictions(
    tenantId: string,
    machineId: string,
    params: { limit?: number; offset?: number; status?: 'available' | 'unavailable' } = {}
  ): Promise<{ items: Prediction[]; limit: number; offset: number; total: number; request_id: string }> {
    const q = new URLSearchParams();
    if (params.limit) q.set('limit', params.limit.toString());
    if (params.offset) q.set('offset', params.offset.toString());
    if (params.status) q.set('status', params.status);

    return request<{ items: Prediction[]; limit: number; offset: number; total: number; request_id: string }>(
      `/api/v1/organizations/${tenantId}/machines/${machineId}/predictions?${q.toString()}`,
      { method: 'GET' }
    );
  },

  async runPrediction(
    tenantId: string,
    machineId: string,
    cutoffCycle?: number
  ): Promise<{ prediction: Prediction; request_id: string }> {
    return request<{ prediction: Prediction; request_id: string }>(
      `/api/v1/organizations/${tenantId}/machines/${machineId}/predictions`,
      {
        method: 'POST',
        requiresCsrf: true,
        body: JSON.stringify(cutoffCycle ? { cutoff_cycle: cutoffCycle } : {}),
      }
    );
  },

  async getPrediction(tenantId: string, predictionId: string): Promise<{ prediction: Prediction; request_id: string }> {
    return request<{ prediction: Prediction; request_id: string }>(
      `/api/v1/organizations/${tenantId}/predictions/${predictionId}`,
      { method: 'GET' }
    );
  },
};

// ==========================================
// WORK ORDERS & APPROVAL WORKFLOW
// ==========================================

export const workOrdersApi = {
  async listWorkOrders(
    tenantId: string,
    params: {
      machine_id?: string;
      status?: WorkOrderStatus;
      priority?: WorkOrderPriority;
      technician_id?: string;
      created_from?: string;
      created_to?: string;
      due_from?: string;
      due_to?: string;
      limit?: number;
      offset?: number;
    } = {}
  ): Promise<{ items: WorkOrder[]; total: number; limit: number; offset: number; request_id: string }> {
    const q = new URLSearchParams();
    if (params.machine_id) q.set('machine_id', params.machine_id);
    if (params.status) q.set('status', params.status);
    if (params.priority) q.set('priority', params.priority);
    if (params.technician_id) q.set('technician_id', params.technician_id);
    if (params.created_from) q.set('created_from', params.created_from);
    if (params.created_to) q.set('created_to', params.created_to);
    if (params.due_from) q.set('due_from', params.due_from);
    if (params.due_to) q.set('due_to', params.due_to);
    if (params.limit) q.set('limit', params.limit.toString());
    if (params.offset) q.set('offset', params.offset.toString());

    return request<{ items: WorkOrder[]; total: number; limit: number; offset: number; request_id: string }>(
      `/api/v1/organizations/${tenantId}/work-orders?${q.toString()}`,
      { method: 'GET' }
    );
  },

  async getWorkOrder(tenantId: string, workOrderId: string): Promise<{ work_order: WorkOrder; request_id: string }> {
    return request<{ work_order: WorkOrder; request_id: string }>(
      `/api/v1/organizations/${tenantId}/work-orders/${workOrderId}`,
      { method: 'GET' }
    );
  },

  async createDraftFromPrediction(
    tenantId: string,
    predictionId: string,
    payload: {
      title?: string;
      description?: string;
      priority?: WorkOrderPriority;
      due_date?: string;
      planned_date?: string;
      idempotency_key?: string;
    } = {}
  ): Promise<{ work_order: WorkOrder; request_id: string }> {
    return request<{ work_order: WorkOrder; request_id: string }>(
      `/api/v1/organizations/${tenantId}/predictions/${predictionId}/work-order-draft`,
      {
        method: 'POST',
        requiresCsrf: true,
        body: JSON.stringify(payload),
      }
    );
  },

  async createManualDraft(
    tenantId: string,
    payload: {
      machine_id: string;
      title: string;
      description: string;
      priority: WorkOrderPriority;
      due_date?: string | null;
      planned_date?: string | null;
      idempotency_key?: string;
    }
  ): Promise<{ work_order: WorkOrder; request_id: string }> {
    return request<{ work_order: WorkOrder; request_id: string }>(
      `/api/v1/organizations/${tenantId}/work-orders`,
      {
        method: 'POST',
        requiresCsrf: true,
        body: JSON.stringify(payload),
      }
    );
  },

  async updateWorkOrder(
    tenantId: string,
    workOrderId: string,
    payload: {
      version: number;
      title?: string;
      description?: string;
      priority?: WorkOrderPriority;
      due_date?: string | null;
      planned_date?: string | null;
    }
  ): Promise<{ work_order: WorkOrder; request_id: string }> {
    return request<{ work_order: WorkOrder; request_id: string }>(
      `/api/v1/organizations/${tenantId}/work-orders/${workOrderId}`,
      {
        method: 'PATCH',
        requiresCsrf: true,
        body: JSON.stringify(payload),
      }
    );
  },

  async assignTechnician(
    tenantId: string,
    workOrderId: string,
    payload: {
      version: number;
      technician_id: string;
      reason?: string | null;
    }
  ): Promise<{ work_order: WorkOrder; request_id: string }> {
    return request<{ work_order: WorkOrder; request_id: string }>(
      `/api/v1/organizations/${tenantId}/work-orders/${workOrderId}/assignment`,
      {
        method: 'POST',
        requiresCsrf: true,
        body: JSON.stringify(payload),
      }
    );
  },

  async transitionWorkOrder(
    tenantId: string,
    workOrderId: string,
    payload: {
      version: number;
      action: WorkOrderAction;
      reason?: string | null;
      completion_summary?: string | null;
    }
  ): Promise<{ work_order: WorkOrder; request_id: string }> {
    return request<{ work_order: WorkOrder; request_id: string }>(
      `/api/v1/organizations/${tenantId}/work-orders/${workOrderId}/transitions`,
      {
        method: 'POST',
        requiresCsrf: true,
        body: JSON.stringify(payload),
      }
    );
  },

  async addNote(
    tenantId: string,
    workOrderId: string,
    payload: {
      version: number;
      note_text: string;
    }
  ): Promise<{ note: any; work_order_version: number; request_id: string }> {
    return request<{ note: any; work_order_version: number; request_id: string }>(
      `/api/v1/organizations/${tenantId}/work-orders/${workOrderId}/notes`,
      {
        method: 'POST',
        requiresCsrf: true,
        body: JSON.stringify(payload),
      }
    );
  },

  async getHistory(tenantId: string, workOrderId: string): Promise<WorkOrderHistory> {
    return request<WorkOrderHistory>(
      `/api/v1/organizations/${tenantId}/work-orders/${workOrderId}/history`,
      { method: 'GET' }
    );
  },
};

// ==========================================
// SYSTEM HEALTH
// ==========================================

export const systemApi = {
  async getHealth(): Promise<{ status: string; model_loaded: boolean; mode: string }> {
    return request<{ status: string; model_loaded: boolean; mode: string }>('/health', { method: 'GET' });
  },

  async getDatabaseHealth(): Promise<{ status: string }> {
    return request<{ status: string }>('/health/database', { method: 'GET' });
  },

  async getModelReadiness(): Promise<{ status: string; model_loaded: boolean; mode: string }> {
    return request<{ status: string; model_loaded: boolean; mode: string }>('/health/ready', { method: 'GET' });
  },
};

// ==========================================
// MLOPS & MODEL MONITORING
// ==========================================

export const mlopsApi = {
  async getModelInfo(tenantId: string): Promise<ModelInfo> {
    return request<ModelInfo>(
      `/api/v1/organizations/${tenantId}/ml/model-info`,
      { method: 'GET' }
    );
  },

  async getObservability(tenantId: string): Promise<MlObservability> {
    return request<MlObservability>(
      `/api/v1/organizations/${tenantId}/ml/observability`,
      { method: 'GET' }
    );
  },

  async getMonitoringRuns(tenantId: string, limit = 20, offset = 0): Promise<MonitoringRunsResponse> {
    return request<MonitoringRunsResponse>(
      `/api/v1/organizations/${tenantId}/ml/monitoring?limit=${limit}&offset=${offset}`,
      { method: 'GET' }
    );
  },

  async getMonitoringRunDetail(tenantId: string, runId: string): Promise<MonitoringRunDetail> {
    return request<MonitoringRunDetail>(
      `/api/v1/organizations/${tenantId}/ml/monitoring/${runId}`,
      { method: 'GET' }
    );
  },
};

// ==========================================
// ADMIN ML PIPELINE (DATASET -> EDA -> RUL)
// ==========================================

export interface AdminPipelineResponse {
  status: string;
  filename: string;
  cleaning: {
    initial_rows: number;
    cleaned_rows: number;
    dropped_rows: number;
    missing_sensors_padded: string[];
    unique_engines_found: number;
  };
  eda_analysis: Record<string, {
    mean: number;
    std: number;
    min: number;
    max: number;
    degradation_slope: number;
    cycle_correlation: number;
    status: 'constant' | 'degrading' | 'active';
  }>;
  feature_engineering: {
    schema: string;
    feature_count_per_window: number;
    feature_names_sample: string[];
    windows_computed: number;
  };
  ingested_fleet: Array<{
    engine_id: number;
    asset_code: string;
    machine_id: string;
    total_cycles_ingested: number;
    estimated_rul: string;
    priority_band: string;
  }>;
  dashboard_message: string;
}

export const adminPipelineApi = {
  async processDataset(tenantId: string, file: File): Promise<AdminPipelineResponse> {
    const formData = new FormData();
    formData.append('file', file);
    return request<AdminPipelineResponse>(
      `/api/v1/organizations/${tenantId}/admin/pipeline/process-dataset`,
      {
        method: 'POST',
        body: formData,
        requiresCsrf: true,
      }
    );
  },
};

