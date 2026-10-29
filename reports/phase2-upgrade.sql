BEGIN;

CREATE TABLE alembic_version (
    version_num VARCHAR(32) NOT NULL, 
    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);

-- Running upgrade  -> 0001_registry

CREATE EXTENSION IF NOT EXISTS btree_gist;

CREATE TABLE tenants (id uuid PRIMARY KEY DEFAULT gen_random_uuid(), name text NOT NULL, created_at timestamptz NOT NULL DEFAULT now());

CREATE TABLE users (id uuid PRIMARY KEY DEFAULT gen_random_uuid(), oidc_issuer text NOT NULL, oidc_subject text NOT NULL, display_name text NOT NULL, UNIQUE (oidc_issuer,oidc_subject));

CREATE TABLE memberships (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 tenant_id uuid NOT NULL REFERENCES tenants(id),
 user_id uuid NOT NULL REFERENCES users(id), roles text[] NOT NULL, active boolean NOT NULL DEFAULT true,
 UNIQUE (tenant_id,id),
 UNIQUE (tenant_id,user_id)
);

CREATE TABLE machines (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 tenant_id uuid NOT NULL REFERENCES tenants(id),
 asset_code text NOT NULL, name text NOT NULL, machine_type text NOT NULL, serial_number text, location text NOT NULL, criticality integer NOT NULL DEFAULT 3 CHECK (criticality BETWEEN 1 AND 5), operating_status text NOT NULL DEFAULT 'stopped' CHECK (operating_status IN ('running','stopped','maintenance','offline','retired')), version integer NOT NULL DEFAULT 1, created_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE (tenant_id,id),
 UNIQUE (tenant_id,asset_code)
);

CREATE TABLE sensors (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 tenant_id uuid NOT NULL REFERENCES tenants(id),
 sensor_code text NOT NULL, kind text NOT NULL, canonical_unit text NOT NULL, retired boolean NOT NULL DEFAULT false,
 UNIQUE (tenant_id,id),
 UNIQUE (tenant_id,sensor_code)
);

CREATE TABLE installations (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 tenant_id uuid NOT NULL REFERENCES tenants(id),
 sensor_id uuid NOT NULL, machine_id uuid NOT NULL, gateway_channel text NOT NULL, valid_from timestamptz NOT NULL, valid_to timestamptz, verified_at timestamptz, verified_by uuid, CHECK (valid_to IS NULL OR valid_to > valid_from),
 UNIQUE (tenant_id,id),
 FOREIGN KEY (tenant_id,sensor_id) REFERENCES sensors(tenant_id,id),
 FOREIGN KEY (tenant_id,machine_id) REFERENCES machines(tenant_id,id),
 FOREIGN KEY (tenant_id,verified_by) REFERENCES memberships(tenant_id,user_id)
);

ALTER TABLE users ADD COLUMN created_at timestamptz NOT NULL DEFAULT now();

ALTER TABLE memberships ADD COLUMN created_at timestamptz NOT NULL DEFAULT now();

ALTER TABLE sensors ADD COLUMN created_at timestamptz NOT NULL DEFAULT now();

ALTER TABLE installations ADD COLUMN created_at timestamptz NOT NULL DEFAULT now();

ALTER TABLE memberships ADD CONSTRAINT memberships_roles CHECK (
 cardinality(roles) > 0 AND array_position(roles, NULL) IS NULL AND
 roles <@ ARRAY['viewer','technician','manager','ml_engineer','admin']::text[]);

ALTER TABLE machines ADD CONSTRAINT machines_version CHECK (version > 0);

ALTER TABLE installations ADD CONSTRAINT installations_verification CHECK ((verified_at IS NULL) = (verified_by IS NULL));

ALTER TABLE installations ADD CONSTRAINT installations_finite_time CHECK (
 isfinite(valid_from) AND (valid_to IS NULL OR isfinite(valid_to)));

ALTER TABLE installations ADD CONSTRAINT installations_sensor_no_overlap
 EXCLUDE USING gist (tenant_id WITH =, sensor_id WITH =, tstzrange(valid_from, valid_to, '[)') WITH &&);

CREATE INDEX installations_machine ON installations(tenant_id,machine_id,valid_from);

CREATE INDEX installations_verifier ON installations(tenant_id,verified_by);

CREATE INDEX memberships_user ON memberships(user_id);

ALTER TABLE tenants ADD CONSTRAINT tenants_name_nonempty CHECK (length(btrim(name)) > 0);

ALTER TABLE users ADD CONSTRAINT users_oidc_issuer_nonempty CHECK (length(btrim(oidc_issuer)) > 0);

ALTER TABLE users ADD CONSTRAINT users_oidc_subject_nonempty CHECK (length(btrim(oidc_subject)) > 0);

ALTER TABLE users ADD CONSTRAINT users_display_name_nonempty CHECK (length(btrim(display_name)) > 0);

ALTER TABLE machines ADD CONSTRAINT machines_asset_code_nonempty CHECK (length(btrim(asset_code)) > 0);

ALTER TABLE machines ADD CONSTRAINT machines_name_nonempty CHECK (length(btrim(name)) > 0);

ALTER TABLE machines ADD CONSTRAINT machines_machine_type_nonempty CHECK (length(btrim(machine_type)) > 0);

ALTER TABLE machines ADD CONSTRAINT machines_location_nonempty CHECK (length(btrim(location)) > 0);

ALTER TABLE sensors ADD CONSTRAINT sensors_sensor_code_nonempty CHECK (length(btrim(sensor_code)) > 0);

ALTER TABLE sensors ADD CONSTRAINT sensors_kind_nonempty CHECK (length(btrim(kind)) > 0);

ALTER TABLE sensors ADD CONSTRAINT sensors_canonical_unit_nonempty CHECK (length(btrim(canonical_unit)) > 0);

ALTER TABLE installations ADD CONSTRAINT installations_gateway_channel_nonempty CHECK (length(btrim(gateway_channel)) > 0);

INSERT INTO alembic_version (version_num) VALUES ('0001_registry') RETURNING alembic_version.version_num;

COMMIT;

