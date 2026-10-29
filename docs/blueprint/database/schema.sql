-- Meridian Sentinel reference baseline; proposed, not executed against PostgreSQL.

-- Apply through reviewed migrations. See database.md for semantic invariants and missing exclusion rule.

BEGIN;

CREATE TABLE tenants (id uuid PRIMARY KEY, name text NOT NULL, created_at timestamptz NOT NULL DEFAULT now());

CREATE TABLE users (id uuid PRIMARY KEY, oidc_issuer text NOT NULL, oidc_subject text NOT NULL, display_name text NOT NULL, UNIQUE (oidc_issuer,oidc_subject));

CREATE TABLE memberships (
 id uuid PRIMARY KEY,
 tenant_id uuid NOT NULL REFERENCES tenants(id),
 user_id uuid NOT NULL REFERENCES users(id), roles text[] NOT NULL, active boolean NOT NULL DEFAULT true,
 UNIQUE (tenant_id,id),
 UNIQUE (tenant_id,user_id)
);

CREATE TABLE sessions (
 id uuid PRIMARY KEY,
 tenant_id uuid NOT NULL REFERENCES tenants(id),
 user_id uuid NOT NULL, token_hash text NOT NULL UNIQUE, expires_at timestamptz NOT NULL, created_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE (tenant_id,id),
 FOREIGN KEY (tenant_id,user_id) REFERENCES memberships(tenant_id,user_id)
);

CREATE TABLE machines (
 id uuid PRIMARY KEY,
 tenant_id uuid NOT NULL REFERENCES tenants(id),
 asset_code text NOT NULL, name text NOT NULL, machine_type text NOT NULL, serial_number text, location text NOT NULL, criticality integer NOT NULL DEFAULT 3 CHECK (criticality BETWEEN 1 AND 5), operating_status text NOT NULL DEFAULT 'stopped' CHECK (operating_status IN ('running','stopped','maintenance','offline','retired')), version integer NOT NULL DEFAULT 1, created_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE (tenant_id,id),
 UNIQUE (tenant_id,asset_code)
);

CREATE TABLE sensors (
 id uuid PRIMARY KEY,
 tenant_id uuid NOT NULL REFERENCES tenants(id),
 sensor_code text NOT NULL, kind text NOT NULL, canonical_unit text NOT NULL, retired boolean NOT NULL DEFAULT false,
 UNIQUE (tenant_id,id),
 UNIQUE (tenant_id,sensor_code)
);

CREATE TABLE installations (
 id uuid PRIMARY KEY,
 tenant_id uuid NOT NULL REFERENCES tenants(id),
 sensor_id uuid NOT NULL, machine_id uuid NOT NULL, gateway_channel text NOT NULL, valid_from timestamptz NOT NULL, valid_to timestamptz, verified_at timestamptz, verified_by uuid, CHECK (valid_to IS NULL OR valid_to > valid_from),
 UNIQUE (tenant_id,id),
 FOREIGN KEY (tenant_id,sensor_id) REFERENCES sensors(tenant_id,id),
 FOREIGN KEY (tenant_id,machine_id) REFERENCES machines(tenant_id,id),
 FOREIGN KEY (tenant_id,verified_by) REFERENCES memberships(tenant_id,user_id)
);

CREATE TABLE telemetry_frames (
 id uuid PRIMARY KEY,
 tenant_id uuid NOT NULL REFERENCES tenants(id),
 machine_id uuid NOT NULL, source_event_id text NOT NULL, stream_id text NOT NULL, cycle bigint NOT NULL CHECK (cycle>=0), event_time timestamptz NOT NULL, received_at timestamptz NOT NULL DEFAULT now(), data_mode text NOT NULL CHECK (data_mode IN ('replay','synthetic','live')), settings jsonb NOT NULL DEFAULT '[]', quality_code text NOT NULL,
 UNIQUE (tenant_id,id),
 FOREIGN KEY (tenant_id,machine_id) REFERENCES machines(tenant_id,id),
 UNIQUE (tenant_id,stream_id,source_event_id)
);

CREATE TABLE readings (
 id uuid PRIMARY KEY,
 tenant_id uuid NOT NULL REFERENCES tenants(id),
 frame_id uuid NOT NULL, installation_id uuid NOT NULL, raw_value double precision NOT NULL, raw_unit text NOT NULL, canonical_value double precision, canonical_unit text, quality_code text NOT NULL,
 UNIQUE (tenant_id,id),
 FOREIGN KEY (tenant_id,frame_id) REFERENCES telemetry_frames(tenant_id,id),
 FOREIGN KEY (tenant_id,installation_id) REFERENCES installations(tenant_id,id),
 UNIQUE (tenant_id,frame_id,installation_id)
);

CREATE TABLE model_versions (
 id uuid PRIMARY KEY,
 tenant_id uuid NOT NULL REFERENCES tenants(id),
 name text NOT NULL, registry_version text NOT NULL, artifact_uri text NOT NULL, artifact_sha256 text NOT NULL, feature_schema_version text NOT NULL, compatible_machine_type text NOT NULL, window_cycles integer NOT NULL CHECK (window_cycles>0), horizon_cycles integer NOT NULL CHECK (horizon_cycles>0), manifest jsonb NOT NULL, measured_metrics jsonb NOT NULL DEFAULT '{}', created_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE (tenant_id,id),
 UNIQUE (tenant_id,name,registry_version)
);

CREATE TABLE predictions (
 id uuid PRIMARY KEY,
 tenant_id uuid NOT NULL REFERENCES tenants(id),
 machine_id uuid NOT NULL, frame_id uuid NOT NULL, model_version_id uuid, status text NOT NULL CHECK (status IN ('available','unavailable','pending')), reason text, failure_probability double precision CHECK (failure_probability BETWEEN 0 AND 1), horizon_cycles integer NOT NULL CHECK (horizon_cycles>0), rul_cycles double precision CHECK (rul_cycles>=0), interval_lower double precision, interval_upper double precision, input_start_cycle bigint, input_end_cycle bigint, policy_version text NOT NULL, created_at timestamptz NOT NULL DEFAULT now(), CHECK (interval_lower IS NULL OR interval_upper IS NULL OR interval_lower<=interval_upper), CHECK (status <> 'available' OR model_version_id IS NOT NULL), CHECK (status <> 'unavailable' OR (failure_probability IS NULL AND rul_cycles IS NULL)),
 UNIQUE (tenant_id,id),
 FOREIGN KEY (tenant_id,machine_id) REFERENCES machines(tenant_id,id),
 FOREIGN KEY (tenant_id,frame_id) REFERENCES telemetry_frames(tenant_id,id),
 FOREIGN KEY (tenant_id,model_version_id) REFERENCES model_versions(tenant_id,id)
);

CREATE UNIQUE INDEX predictions_frame_model ON predictions(tenant_id,frame_id,model_version_id) WHERE model_version_id IS NOT NULL;

CREATE UNIQUE INDEX predictions_unavailable_frame ON predictions(tenant_id,frame_id) WHERE model_version_id IS NULL;

CREATE TABLE incidents (
 id uuid PRIMARY KEY,
 tenant_id uuid NOT NULL REFERENCES tenants(id),
 machine_id uuid NOT NULL, prediction_id uuid, family text NOT NULL, severity text NOT NULL, status text NOT NULL DEFAULT 'open' CHECK (status IN ('open','acknowledged','investigating','monitoring','resolved','dismissed')), owner_id uuid, version integer NOT NULL DEFAULT 1, updated_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE (tenant_id,id),
 FOREIGN KEY (tenant_id,machine_id) REFERENCES machines(tenant_id,id),
 FOREIGN KEY (tenant_id,prediction_id) REFERENCES predictions(tenant_id,id),
 FOREIGN KEY (tenant_id,owner_id) REFERENCES memberships(tenant_id,user_id)
);

CREATE UNIQUE INDEX incidents_one_active_family ON incidents(tenant_id,machine_id,family) WHERE status IN ('open','acknowledged','investigating','monitoring');

CREATE TABLE work_orders (
 id uuid PRIMARY KEY,
 tenant_id uuid NOT NULL REFERENCES tenants(id),
 incident_id uuid NOT NULL, summary text NOT NULL, inspection_scope text NOT NULL, evidence_ids jsonb NOT NULL DEFAULT '[]', manual_references jsonb NOT NULL DEFAULT '[]', status text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','approved','assigned','in_progress','awaiting_parts','verification_pending','closed','cancelled')), approved_by uuid, approved_at timestamptz, assigned_to uuid, version integer NOT NULL DEFAULT 1, created_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE (tenant_id,id),
 FOREIGN KEY (tenant_id,incident_id) REFERENCES incidents(tenant_id,id),
 FOREIGN KEY (tenant_id,approved_by) REFERENCES memberships(tenant_id,user_id),
 FOREIGN KEY (tenant_id,assigned_to) REFERENCES memberships(tenant_id,user_id)
);

CREATE TABLE inspections (
 id uuid PRIMARY KEY,
 tenant_id uuid NOT NULL REFERENCES tenants(id),
 work_order_id uuid NOT NULL, performed_by uuid NOT NULL, outcome text NOT NULL CHECK (outcome IN ('confirmed_defect','sensor_issue','no_defect_found','unclear','preventive_repair_unknown_outcome')), findings text NOT NULL, evidence_refs jsonb NOT NULL DEFAULT '[]', verified_by uuid, verified_at timestamptz, verification_result text CHECK (verification_result IN ('pass','fail')), created_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE (tenant_id,id),
 FOREIGN KEY (tenant_id,work_order_id) REFERENCES work_orders(tenant_id,id),
 FOREIGN KEY (tenant_id,performed_by) REFERENCES memberships(tenant_id,user_id),
 FOREIGN KEY (tenant_id,verified_by) REFERENCES memberships(tenant_id,user_id)
);

CREATE TABLE audit_events (
 id uuid PRIMARY KEY,
 tenant_id uuid NOT NULL REFERENCES tenants(id),
 actor_user_id uuid, actor_kind text NOT NULL, action text NOT NULL, resource_type text NOT NULL, resource_id uuid, change_summary jsonb NOT NULL, request_id text NOT NULL, created_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE (tenant_id,id),
 FOREIGN KEY (tenant_id,actor_user_id) REFERENCES memberships(tenant_id,user_id)
);

CREATE TABLE outbox_events (
 id uuid PRIMARY KEY,
 tenant_id uuid NOT NULL REFERENCES tenants(id),
 event_type text NOT NULL, payload jsonb NOT NULL, status text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','claimed','delivered','dead_letter')), attempts integer NOT NULL DEFAULT 0, lease_until timestamptz, next_attempt_at timestamptz NOT NULL DEFAULT now(), created_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE (tenant_id,id)
);

CREATE TABLE jobs (
 id uuid PRIMARY KEY,
 tenant_id uuid NOT NULL REFERENCES tenants(id),
 job_type text NOT NULL, requested_by uuid, payload jsonb NOT NULL, status text NOT NULL DEFAULT 'queued' CHECK (status IN ('queued','running','succeeded','failed','dead_letter')), attempts integer NOT NULL DEFAULT 0, lease_until timestamptz, error_code text, created_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE (tenant_id,id),
 FOREIGN KEY (tenant_id,requested_by) REFERENCES memberships(tenant_id,user_id)
);

CREATE TABLE idempotency_records (
 id uuid PRIMARY KEY,
 tenant_id uuid NOT NULL REFERENCES tenants(id),
 actor_key text NOT NULL, route text NOT NULL, idempotency_key text NOT NULL, request_hash text NOT NULL, response_code integer, response_body jsonb, expires_at timestamptz NOT NULL,
 UNIQUE (tenant_id,id),
 UNIQUE (tenant_id,actor_key,route,idempotency_key)
);

CREATE TABLE model_release_reviews (
 id uuid PRIMARY KEY,
 tenant_id uuid NOT NULL REFERENCES tenants(id),
 model_version_id uuid NOT NULL, scope text NOT NULL, reviewer_id uuid NOT NULL, decision text NOT NULL CHECK (decision IN ('approved','rejected')), evidence_ref text NOT NULL, reviewed_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE (tenant_id,id),
 FOREIGN KEY (tenant_id,model_version_id) REFERENCES model_versions(tenant_id,id),
 FOREIGN KEY (tenant_id,reviewer_id) REFERENCES memberships(tenant_id,user_id)
);

CREATE TABLE model_deployments (
 id uuid PRIMARY KEY,
 tenant_id uuid NOT NULL REFERENCES tenants(id),
 model_version_id uuid NOT NULL, review_id uuid NOT NULL, scope text NOT NULL, deployed_by uuid NOT NULL, status text NOT NULL CHECK (status IN ('active','superseded','rolled_back')), deployed_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE (tenant_id,id),
 FOREIGN KEY (tenant_id,model_version_id) REFERENCES model_versions(tenant_id,id),
 FOREIGN KEY (tenant_id,review_id) REFERENCES model_release_reviews(tenant_id,id),
 FOREIGN KEY (tenant_id,deployed_by) REFERENCES memberships(tenant_id,user_id)
);

CREATE UNIQUE INDEX deployments_one_active_scope ON model_deployments(tenant_id,scope) WHERE status='active';

CREATE TABLE integration_deliveries (
 id uuid PRIMARY KEY,
 tenant_id uuid NOT NULL REFERENCES tenants(id),
 outbox_event_id uuid NOT NULL, connector_key text NOT NULL, external_event_id text NOT NULL, status text NOT NULL, attempts integer NOT NULL DEFAULT 0, last_error text,
 UNIQUE (tenant_id,id),
 FOREIGN KEY (tenant_id,outbox_event_id) REFERENCES outbox_events(tenant_id,id),
 UNIQUE (tenant_id,connector_key,external_event_id)
);

CREATE INDEX frames_asset_time ON telemetry_frames(tenant_id,machine_id,event_time DESC);

CREATE INDEX frames_asset_cycles ON telemetry_frames(tenant_id,machine_id,stream_id,cycle);

CREATE INDEX incidents_queue ON incidents(tenant_id,status,updated_at);

CREATE INDEX work_orders_assignee ON work_orders(tenant_id,assigned_to,status);

CREATE INDEX outbox_claim ON outbox_events(status,next_attempt_at);

COMMIT;

-- Missing installation-overlap exclusion, app-role grants/RLS and migrations are explicit implementation tasks.

-- Semantic checks: review scope/model must match deployment; references in JSON must be tenant-validated.
