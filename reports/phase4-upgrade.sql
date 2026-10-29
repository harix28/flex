BEGIN;

-- Running upgrade 0002_auth -> 0003_registry

ALTER TABLE machines
      ADD COLUMN manufacturer text, ADD COLUMN model text, ADD COLUMN site text, ADD COLUMN area text,
      ADD COLUMN lifecycle_status text NOT NULL DEFAULT 'inactive' CHECK (lifecycle_status IN ('active','inactive','archived')),
      ADD COLUMN data_source text CHECK (data_source IN ('nasa_replay','physical_device')),
      ADD COLUMN source_dataset text, ADD COLUMN source_subset text, ADD COLUMN source_engine_id integer,
      ADD COLUMN source_split text, ADD COLUMN updated_at timestamptz NOT NULL DEFAULT now(),
      ADD CONSTRAINT machine_source_binding CHECK (
        (data_source IS NOT NULL AND data_source='nasa_replay' AND source_dataset IS NOT NULL AND source_dataset='C-MAPSS'
         AND source_subset IS NOT NULL AND source_subset IN ('FD001','FD002','FD003','FD004')
         AND source_engine_id IS NOT NULL AND source_engine_id>0 AND source_split IS NOT NULL AND source_split='test')
        OR ((data_source IS NULL OR data_source='physical_device') AND source_dataset IS NULL
            AND source_subset IS NULL AND source_engine_id IS NULL AND source_split IS NULL));

UPDATE machines SET lifecycle_status='archived' WHERE operating_status='retired';

CREATE UNIQUE INDEX machine_replay_binding ON machines(tenant_id,source_dataset,source_subset,source_engine_id) WHERE data_source='nasa_replay';

CREATE INDEX machine_registry_list ON machines(tenant_id,asset_code,id);

ALTER TABLE sensors ADD COLUMN name text, ADD COLUMN data_source text,
      ADD COLUMN channel_id text, ADD COLUMN hardware_device_id text, ADD COLUMN unit_reference text,
      ADD COLUMN updated_at timestamptz NOT NULL DEFAULT now(),
      ADD CONSTRAINT sensor_data_source CHECK (data_source IN ('nasa_replay','physical_device')),
      ADD CONSTRAINT sensor_source_channel CHECK (
        (data_source IS NOT NULL AND data_source='nasa_replay' AND channel_id IS NOT NULL
         AND channel_id ~ '^sensor_(0[1-9]|1[0-9]|2[01])$' AND kind='cmapss_channel'
         AND canonical_unit='unknown' AND unit_reference IS NULL AND hardware_device_id IS NULL)
        OR ((data_source IS NULL OR data_source='physical_device') AND channel_id IS NULL));

UPDATE sensors SET name=sensor_code;

ALTER TABLE sensors ALTER COLUMN name SET NOT NULL, ALTER COLUMN name SET DEFAULT 'unknown';

ALTER TABLE sensors ADD CONSTRAINT sensor_name_nonempty CHECK (length(btrim(name))>0);

CREATE INDEX sensor_registry_list ON sensors(tenant_id,sensor_code,id);

ALTER TABLE installations ADD COLUMN note text, ADD COLUMN updated_at timestamptz NOT NULL DEFAULT now();

ALTER TABLE installations ADD CONSTRAINT installations_slot_no_overlap
      EXCLUDE USING gist (tenant_id WITH =, machine_id WITH =, gateway_channel WITH =,
                         tstzrange(valid_from,valid_to,'[)') WITH &&);

CREATE FUNCTION registry_touch_updated() RETURNS trigger LANGUAGE plpgsql AS $$
      BEGIN NEW.updated_at=clock_timestamp(); RETURN NEW; END $$;

CREATE TRIGGER machines_touch BEFORE UPDATE ON machines FOR EACH ROW EXECUTE FUNCTION registry_touch_updated();

CREATE TRIGGER sensors_touch BEFORE UPDATE ON sensors FOR EACH ROW EXECUTE FUNCTION registry_touch_updated();

CREATE TRIGGER installations_touch BEFORE UPDATE ON installations FOR EACH ROW EXECUTE FUNCTION registry_touch_updated();

CREATE FUNCTION registry_installation_guard() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE m machines%%ROWTYPE; s sensors%%ROWTYPE;
    BEGIN
      IF TG_OP='UPDATE' THEN
        IF ROW(NEW.tenant_id,NEW.machine_id,NEW.sensor_id,NEW.gateway_channel,NEW.valid_from)
           IS DISTINCT FROM ROW(OLD.tenant_id,OLD.machine_id,OLD.sensor_id,OLD.gateway_channel,OLD.valid_from)
           OR (OLD.valid_to IS NOT NULL AND NEW.valid_to IS DISTINCT FROM OLD.valid_to) THEN
          RAISE EXCEPTION 'Installation identity/history is immutable' USING ERRCODE='23514';
        END IF;
        RETURN NEW;
      END IF;
      SELECT * INTO m FROM machines WHERE tenant_id=NEW.tenant_id AND id=NEW.machine_id FOR UPDATE;
      SELECT * INTO s FROM sensors WHERE tenant_id=NEW.tenant_id AND id=NEW.sensor_id FOR UPDATE;
      IF m.lifecycle_status='archived' OR s.retired THEN
        RAISE EXCEPTION 'Asset unavailable for new installation' USING ERRCODE='23514';
      END IF;
      IF m.data_source IS DISTINCT FROM s.data_source OR
         (s.data_source='nasa_replay' AND s.channel_id IS DISTINCT FROM NEW.gateway_channel) THEN
        RAISE EXCEPTION 'Installation source/channel mismatch' USING ERRCODE='23514';
      END IF;
      RETURN NEW;
    END $$;

CREATE TRIGGER registry_installation_guard BEFORE INSERT OR UPDATE ON installations FOR EACH ROW EXECUTE FUNCTION registry_installation_guard();

ALTER TABLE auth_audit_events ADD COLUMN target_type text, ADD COLUMN target_id uuid;

ALTER TABLE auth_audit_events DROP CONSTRAINT auth_audit_events_action_check;

ALTER TABLE auth_audit_events ADD CONSTRAINT auth_audit_events_action_check CHECK (action IN ('login_success','login_failure','login_rate_limited','logout','password_changed','membership_added','membership_changed','membership_disabled','bootstrap','user_created','user_disabled','machine_created','machine_updated','machine_archived','sensor_created','sensor_updated','installation_created','installation_removed'));

ALTER TABLE auth_audit_events ADD CONSTRAINT registry_audit_target CHECK
      ((action NOT IN ('machine_created','machine_updated','machine_archived','sensor_created','sensor_updated','installation_created','installation_removed'))
       OR (tenant_id IS NOT NULL AND actor_id IS NOT NULL AND target_id IS NOT NULL AND target_type IS NOT NULL AND target_type IN ('machine','sensor','installation')));

CREATE INDEX audit_registry_target ON auth_audit_events(tenant_id,target_type,target_id,created_at);

UPDATE alembic_version SET version_num='0003_registry' WHERE alembic_version.version_num = '0002_auth';

COMMIT;

