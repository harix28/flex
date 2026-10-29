BEGIN;

-- Running upgrade 0001_registry -> 0002_auth

DO $$ BEGIN
      IF EXISTS (SELECT 1 FROM memberships WHERE 'ml_engineer' = ANY(roles)) THEN
        RAISE EXCEPTION 'Resolve legacy ml_engineer memberships explicitly before Phase 3 upgrade';
      END IF;
    END $$;

ALTER TABLE memberships DROP CONSTRAINT memberships_roles;

UPDATE memberships SET roles = array_replace(roles, 'manager', 'plant_manager');

ALTER TABLE memberships ADD CONSTRAINT memberships_roles CHECK (
      cardinality(roles) > 0 AND array_position(roles, NULL) IS NULL AND
      roles <@ ARRAY['viewer','technician','plant_manager','admin']::text[]);

ALTER TABLE tenants ADD COLUMN slug text UNIQUE CHECK (slug ~ '^[a-z0-9][a-z0-9-]{1,62}$');

ALTER TABLE users
      ADD COLUMN email varchar(254) UNIQUE,
      ADD COLUMN password_hash text,
      ADD COLUMN active boolean NOT NULL DEFAULT true,
      ADD CONSTRAINT users_email_normalized CHECK (email IS NULL OR
        (email = lower(btrim(email)) AND email ~ '^[!-~]+@[!-~]+$')),
      ADD CONSTRAINT users_password_identity CHECK (password_hash IS NULL OR
        (email IS NOT NULL AND password_hash LIKE '$argon2id$%%'));

CREATE TABLE auth_sessions (
      id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
      user_id uuid NOT NULL REFERENCES users(id),
      token_hash text NOT NULL UNIQUE CHECK (token_hash ~ '^[0-9a-f]{64}$'),
      csrf_hash text NOT NULL CHECK (csrf_hash ~ '^[0-9a-f]{64}$'),
      created_at timestamptz NOT NULL DEFAULT now(),
      expires_at timestamptz NOT NULL,
      revoked_at timestamptz,
      CHECK (expires_at > created_at)
    );

CREATE INDEX auth_sessions_user ON auth_sessions(user_id);

CREATE INDEX auth_sessions_expiry ON auth_sessions(expires_at);

CREATE TABLE auth_audit_events (
      id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
      created_at timestamptz NOT NULL DEFAULT now(),
      action text NOT NULL CHECK (action IN ('login_success','login_failure','login_rate_limited',
        'logout','password_changed','membership_added','membership_changed','membership_disabled',
        'bootstrap','user_created','user_disabled')),
      actor_id uuid REFERENCES users(id),
      tenant_id uuid REFERENCES tenants(id),
      target_user_id uuid REFERENCES users(id),
      request_id uuid NOT NULL
    );

CREATE INDEX auth_audit_tenant_time ON auth_audit_events(tenant_id,created_at);

CREATE INDEX auth_audit_actor_time ON auth_audit_events(actor_id,created_at);

CREATE FUNCTION revoke_changed_user_sessions() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF NEW.password_hash IS DISTINCT FROM OLD.password_hash OR (OLD.active AND NOT NEW.active) THEN
        UPDATE auth_sessions SET revoked_at = now() WHERE user_id = NEW.id AND revoked_at IS NULL;
      END IF;
      RETURN NEW;
    END $$;

CREATE TRIGGER users_revoke_sessions AFTER UPDATE OF password_hash, active ON users
      FOR EACH ROW EXECUTE FUNCTION revoke_changed_user_sessions();

UPDATE alembic_version SET version_num='0002_auth' WHERE alembic_version.version_num = '0001_registry';

COMMIT;

