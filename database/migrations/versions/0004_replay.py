"""Immutable versioned replay streams, atomic batches/idempotency and observations."""
from alembic import op
revision='0004_replay'
down_revision='0003_registry'
branch_labels=None
depends_on=None


def binding_constraint(versioned):
    partitions="source_split IN ('train','test')" if versioned else "source_split='test'"
    hash_check=" AND source_file_sha256 IS NULL" if versioned else ''
    return f"""ALTER TABLE machines ADD CONSTRAINT machine_source_binding CHECK (
      (data_source IS NOT NULL AND data_source='nasa_replay' AND source_dataset IS NOT NULL AND source_dataset='C-MAPSS'
       AND source_subset IS NOT NULL AND source_subset IN ('FD001','FD002','FD003','FD004')
       AND source_engine_id IS NOT NULL AND source_engine_id>0 AND source_split IS NOT NULL AND {partitions})
      OR ((data_source IS NULL OR data_source='physical_device') AND source_dataset IS NULL AND source_subset IS NULL
          AND source_engine_id IS NULL AND source_split IS NULL {hash_check}))"""


def upgrade():
    op.execute("ALTER TABLE machines ADD COLUMN source_file_sha256 text CHECK (source_file_sha256 ~ '^[0-9a-f]{64}$')")
    op.execute('ALTER TABLE machines DROP CONSTRAINT machine_source_binding')
    op.execute(binding_constraint(True))
    op.execute('DROP INDEX machine_replay_binding')
    op.execute("""CREATE UNIQUE INDEX machine_replay_binding ON machines
      (tenant_id,source_dataset,source_subset,source_split,source_engine_id,source_file_sha256)
      NULLS NOT DISTINCT WHERE data_source='nasa_replay'""")
    op.execute("""ALTER TABLE machines ADD CONSTRAINT machine_stream_identity UNIQUE
      (tenant_id,id,source_dataset,source_subset,source_split,source_engine_id,source_file_sha256)""")
    op.execute("""CREATE FUNCTION protect_machine_source() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF ROW(OLD.tenant_id,OLD.id,OLD.data_source,OLD.source_dataset,OLD.source_subset,OLD.source_split,OLD.source_engine_id)
        IS DISTINCT FROM ROW(NEW.tenant_id,NEW.id,NEW.data_source,NEW.source_dataset,NEW.source_subset,NEW.source_split,NEW.source_engine_id)
        OR (OLD.source_file_sha256 IS NOT NULL AND NEW.source_file_sha256 IS DISTINCT FROM OLD.source_file_sha256) THEN
        RAISE EXCEPTION 'Registered source identity is immutable' USING ERRCODE='23514';
      END IF;
      RETURN NEW;
    END $$""")
    op.execute('CREATE TRIGGER machine_source_immutable BEFORE UPDATE ON machines FOR EACH ROW EXECUTE FUNCTION protect_machine_source()')
    op.execute("""CREATE TABLE replay_streams (
      id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL, machine_id uuid NOT NULL,
      dataset text NOT NULL CHECK (dataset='C-MAPSS'), subset text NOT NULL CHECK (subset IN ('FD001','FD002','FD003','FD004')),
      partition text NOT NULL CHECK (partition IN ('train','test')), engine_id integer NOT NULL CHECK (engine_id>0),
      file_sha256 text NOT NULL CHECK (file_sha256 ~ '^[0-9a-f]{64}$'), schema_version integer NOT NULL CHECK (schema_version=1),
      created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
      UNIQUE(tenant_id,machine_id), UNIQUE(tenant_id,machine_id,id),
      UNIQUE(tenant_id,dataset,subset,partition,engine_id,file_sha256),
      FOREIGN KEY(tenant_id,machine_id,dataset,subset,partition,engine_id,file_sha256)
        REFERENCES machines(tenant_id,id,source_dataset,source_subset,source_split,source_engine_id,source_file_sha256)
    )""")
    op.execute("""CREATE TABLE replay_batches (
      id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL, machine_id uuid NOT NULL, stream_id uuid NOT NULL,
      actor_id uuid NOT NULL, request_id uuid NOT NULL,
      operation text NOT NULL DEFAULT 'replay_ingest' CHECK (operation='replay_ingest'),
      idempotency_key varchar(128) NOT NULL CHECK (idempotency_key ~ '^[A-Za-z0-9._:-]{1,128}$'),
      payload_sha256 text NOT NULL CHECK (payload_sha256 ~ '^[0-9a-f]{64}$'),
      requested_count integer NOT NULL CHECK (requested_count BETWEEN 1 AND 500),
      inserted_count integer NOT NULL CHECK (inserted_count>=0), existing_count integer NOT NULL CHECK (existing_count>=0),
      first_cycle integer NOT NULL CHECK(first_cycle>0), last_cycle integer NOT NULL CHECK(last_cycle>=first_cycle),
      ingested_at timestamptz NOT NULL DEFAULT clock_timestamp(),
      CHECK (requested_count=inserted_count+existing_count),
      UNIQUE(tenant_id,machine_id,operation,idempotency_key), UNIQUE(tenant_id,machine_id,stream_id,id),
      FOREIGN KEY(tenant_id,machine_id,stream_id) REFERENCES replay_streams(tenant_id,machine_id,id),
      FOREIGN KEY(tenant_id,actor_id) REFERENCES memberships(tenant_id,user_id)
    )""")
    op.execute('CREATE INDEX replay_batches_machine_time ON replay_batches(tenant_id,machine_id,ingested_at,id)')
    op.execute("""CREATE FUNCTION replay_finite_vector(a double precision[], n integer) RETURNS boolean
      LANGUAGE sql IMMUTABLE AS $$ SELECT coalesce(array_ndims(a)=1 AND array_lower(a,1)=1 AND cardinality(a)=n
        AND NOT EXISTS(SELECT 1 FROM unnest(a) v WHERE v IS NULL OR NOT (v>'-Infinity'::double precision AND v<'Infinity'::double precision)),false) $$""")
    op.execute("""CREATE TABLE replay_observations (
      tenant_id uuid NOT NULL, machine_id uuid NOT NULL, stream_id uuid NOT NULL, cycle integer NOT NULL CHECK(cycle>0),
      batch_id uuid NOT NULL, settings double precision[] NOT NULL CHECK(replay_finite_vector(settings,3)),
      sensors double precision[] NOT NULL CHECK(replay_finite_vector(sensors,21)),
      observed_at timestamptz CHECK (observed_at IS NULL), ingested_at timestamptz NOT NULL DEFAULT clock_timestamp(),
      PRIMARY KEY(tenant_id,stream_id,cycle),
      FOREIGN KEY(tenant_id,machine_id,stream_id) REFERENCES replay_streams(tenant_id,machine_id,id),
      FOREIGN KEY(tenant_id,machine_id,stream_id,batch_id) REFERENCES replay_batches(tenant_id,machine_id,stream_id,id)
    )""")
    op.execute('CREATE INDEX replay_history_machine_cycle ON replay_observations(tenant_id,machine_id,cycle)')
    op.execute('CREATE INDEX replay_observations_batch ON replay_observations(tenant_id,machine_id,stream_id,batch_id)')
    op.execute("""CREATE FUNCTION replay_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
      BEGIN RAISE EXCEPTION 'Replay history/provenance is immutable' USING ERRCODE='23514'; END $$""")
    for table in ('replay_streams','replay_batches','replay_observations'):
        op.execute(f'CREATE TRIGGER {table}_immutable BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION replay_immutable()')


def downgrade():
    op.execute("""DO $$ BEGIN IF EXISTS(SELECT 1 FROM replay_streams)
      OR EXISTS(SELECT 1 FROM machines WHERE source_split='train' OR source_file_sha256 IS NOT NULL) THEN
      RAISE EXCEPTION 'Versioned replay records exist; destructive downgrade refused'; END IF; END $$""")
    for table in ('replay_observations','replay_batches','replay_streams'):
        op.drop_table(table)
    op.execute('DROP FUNCTION replay_immutable()')
    op.execute('DROP FUNCTION replay_finite_vector(double precision[],integer)')
    op.execute('DROP TRIGGER machine_source_immutable ON machines')
    op.execute('DROP FUNCTION protect_machine_source()')
    op.execute('ALTER TABLE machines DROP CONSTRAINT machine_stream_identity, DROP CONSTRAINT machine_source_binding')
    op.execute('DROP INDEX machine_replay_binding')
    op.execute('ALTER TABLE machines DROP COLUMN source_file_sha256')
    op.execute(binding_constraint(False))
    op.execute("CREATE UNIQUE INDEX machine_replay_binding ON machines(tenant_id,source_dataset,source_subset,source_engine_id) WHERE data_source='nasa_replay'")
